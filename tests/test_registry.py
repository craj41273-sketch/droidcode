import pytest

from droidcode.device.mock import MockDevice
from droidcode.registry import (
    RISK_DEVICE,
    PermissionPolicy,
    ToolRegistry,
    build_registry,
)

SCENARIO = {
    "name": "demo",
    "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
    "widgets": [
        {"id": "btn", "text": "Pay now", "bounds": [40, 1800, 1040, 1932], "bg": "#6750A4", "fg": "#FFFFFF", "clickable": True},
    ],
}


@pytest.fixture
def device() -> MockDevice:
    device = MockDevice(SCENARIO)
    device.start()
    return device


def test_registry_exposes_a_schema_for_every_tool(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    specs = registry.specs()
    assert {spec["name"] for spec in specs} >= {
        "ui.dump_tree", "ui.find", "ui.tap", "ui.type", "ui.swipe",
        "screen.capture", "screen.diff", "design.audit", "perf.frames",
    }
    for spec in specs:
        assert spec["description"]
        assert spec["input_schema"]["type"] == "object"
        assert spec["risk"] in {"read", "device", "write"}


def test_find_returns_bounds_and_centre(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("ui.find", {"text": "Pay now"})
    assert result.ok
    assert result.output["node_id"] == "btn"
    assert result.output["center"] == [540, 1866]


def test_tap_by_text_drives_the_device(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path, policy=PermissionPolicy(auto_approve_risk={"read", RISK_DEVICE}))
    result = registry.call("ui.tap", {"text": "Pay now"})
    assert result.ok
    assert device.tapped_targets() == ["btn"]


def test_unknown_tool_is_reported_not_raised(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("ui.explode", {})
    assert result.ok is False
    assert "unknown tool" in result.error


def test_missing_required_argument_is_rejected(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("ui.type", {})
    assert result.ok is False
    assert "missing required" in result.error


def test_device_risk_tools_require_approval_by_default(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("ui.tap", {"x": 10, "y": 10})
    assert result.ok is False
    assert "requires approval" in result.error


def test_deny_list_wins(device, tmp_path):
    policy = PermissionPolicy(deny={"design.audit"})
    registry = build_registry(device, screenshots_dir=tmp_path, policy=policy)
    result = registry.call("design.audit", {})
    assert result.ok is False
    assert "denied" in result.error


def test_read_tools_run_without_approval(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("ui.dump_tree", {})
    assert result.ok
    assert result.output["tree"]["class_name"] == "android.widget.FrameLayout"


def test_audit_tool_returns_findings(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("design.audit", {"screenshots_dir": str(tmp_path)})
    assert result.ok
    assert "findings" in result.output
    assert (tmp_path / "demo.png").exists()


def test_capture_writes_a_png(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    result = registry.call("screen.capture", {"name": "home"})
    assert result.ok
    assert (tmp_path / "home.png").exists()


def test_duplicate_registration_is_refused(device, tmp_path):
    registry = build_registry(device, screenshots_dir=tmp_path)
    tool = registry.get("ui.find")
    with pytest.raises(ValueError):
        registry.register(tool)


def test_handler_exceptions_are_contained(device, tmp_path):
    registry = ToolRegistry()
    from droidcode.registry import Tool

    registry.register(Tool("boom", "always fails", {"type": "object"}, "read", lambda _: 1 / 0))
    result = registry.call("boom", {})
    assert result.ok is False
    assert "ZeroDivisionError" in result.error
