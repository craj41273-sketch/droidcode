from droidcode.device.mock import MockDevice
from droidcode.registry import PermissionPolicy, build_registry
from droidcode.session import (
    AuditFirstModel,
    ScriptedModel,
    Session,
    ToolCall,
    estimate_tokens,
    run_session,
)

SCENARIO = {
    "name": "demo",
    "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
    "widgets": [
        {"id": "btn", "text": "Pay now", "bounds": [40, 1800, 1040, 1932], "bg": "#FFFFFF", "fg": "#EEEEEE", "clickable": True},
    ],
}


def make_registry(tmp_path):
    device = MockDevice(SCENARIO)
    device.start()
    return build_registry(device, screenshots_dir=tmp_path)


def test_scripted_model_runs_calls_in_order(tmp_path):
    registry = make_registry(tmp_path)
    session = Session(goal="inspect the screen")
    model = ScriptedModel([ToolCall("ui.dump_tree"), ToolCall("design.audit")])
    run_session(session, model, registry)
    assert [step.call.name for step in session.steps] == ["ui.dump_tree", "design.audit"]
    assert session.status == "done"
    assert session.stop_reason == "model finished"


def test_tool_failure_does_not_end_the_session(tmp_path):
    registry = make_registry(tmp_path)
    session = Session(goal="try a bad tool")
    model = ScriptedModel([ToolCall("ui.find", {"text": "nope"}), ToolCall("ui.dump_tree")])
    run_session(session, model, registry)
    assert session.steps[0].result.ok is False
    assert session.steps[1].result.ok is True
    assert len(session.steps) == 2


def test_max_turns_stops_a_looping_model(tmp_path):
    registry = make_registry(tmp_path)
    session = Session(goal="loop")
    model = ScriptedModel([ToolCall("ui.dump_tree")] * 10)
    run_session(session, model, registry, max_turns=3)
    assert len(session.steps) == 3
    assert session.status == "stopped"
    assert "max_turns" in session.stop_reason


def test_context_budget_stops_the_loop(tmp_path):
    registry = make_registry(tmp_path)
    session = Session(goal="budget", budget_tokens=1)
    run_session(session, ScriptedModel([ToolCall("ui.dump_tree")]), registry)
    assert session.status == "stopped"
    assert session.stop_reason == "context budget exhausted"
    # the first call runs; the budget is checked before the next turn
    assert len(session.steps) == 1


def test_audit_first_model_is_deterministic(tmp_path):
    registry = make_registry(tmp_path)
    session = Session(goal="audit")
    run_session(session, AuditFirstModel(), registry)
    assert [step.call.name for step in session.steps] == ["design.audit", "screen.capture"]
    report = session.steps[0].result.output
    assert report["by_severity"]["serious"] >= 1


def test_transcript_serialises(tmp_path):
    registry = make_registry(tmp_path)
    session = Session(goal="serialise")
    run_session(session, ScriptedModel([ToolCall("ui.dump_tree")]), registry)
    payload = session.to_dict()
    assert payload["steps"][0]["call"]["name"] == "ui.dump_tree"
    assert payload["used_tokens"] > 0
    assert payload["status"] == "done"


def test_token_estimate_grows_with_payload():
    assert estimate_tokens({"a": 1}) >= 1
    assert estimate_tokens({"a": "x" * 400}) > estimate_tokens({"a": 1})


def test_device_risk_tools_are_gated_inside_a_session(tmp_path):
    device = MockDevice(SCENARIO)
    device.start()
    registry = build_registry(device, screenshots_dir=tmp_path, policy=PermissionPolicy())
    session = Session(goal="tap")
    run_session(session, ScriptedModel([ToolCall("ui.tap", {"text": "Pay now"})]), registry)
    assert session.steps[0].result.ok is False
    assert "requires approval" in session.steps[0].result.error
    assert device.tapped_targets() == []
