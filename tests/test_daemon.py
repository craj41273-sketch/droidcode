import json

import pytest

from droidcode.client import DaemonClient, DaemonError
from droidcode.daemon import HarnessServer, serve_in_thread
from droidcode.harness import Harness

SCENARIO = {
    "name": "demo",
    "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
    "widgets": [
        {"id": "btn", "text": "Pay now", "bounds": [40, 1800, 1040, 1932], "bg": "#FFFFFF", "fg": "#EEEEEE", "clickable": True},
    ],
}


@pytest.fixture
def server(tmp_path):
    harness = Harness.from_scenario(SCENARIO, screenshots_dir=tmp_path)
    socket_path = str(tmp_path / "droidcode.sock")
    server, thread = serve_in_thread(harness, socket_path)
    yield socket_path
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def test_ping_over_a_real_socket(server):
    client = DaemonClient(server)
    assert client.ping()["pong"] is True


def test_tool_listing_over_the_socket(server):
    names = {spec["name"] for spec in DaemonClient(server).tools()}
    assert "design.audit" in names


def test_tool_call_over_the_socket(server):
    result = DaemonClient(server).call_tool("ui.find", {"text": "Pay now"})
    assert result["ok"] is True
    assert result["output"]["node_id"] == "btn"


def test_audit_over_the_socket(server):
    report = DaemonClient(server).audit()
    assert report["by_severity"]["serious"] >= 1


def test_session_lifecycle_over_the_socket(server):
    client = DaemonClient(server)
    session_id = client.create_session("check the checkout screen")
    result = client.run_session(session_id, script=[{"name": "ui.dump_tree"}, {"name": "design.audit"}])
    assert result["status"] == "done"
    assert [step["call"]["name"] for step in result["steps"]] == ["ui.dump_tree", "design.audit"]


def test_unknown_method_is_reported(tmp_path):
    server_impl = HarnessServer(Harness.from_scenario(SCENARIO, screenshots_dir=tmp_path))
    reply = json.loads(server_impl.handle_line(json.dumps({"id": 1, "method": "nope"})))
    assert reply["ok"] is False
    assert "unknown method" in reply["error"]


def test_malformed_json_is_reported(tmp_path):
    server_impl = HarnessServer(Harness.from_scenario(SCENARIO, screenshots_dir=tmp_path))
    reply = json.loads(server_impl.handle_line("{not json"))
    assert reply["ok"] is False
    assert "bad json" in reply["error"]


def test_unknown_session_raises_on_the_client(server):
    with pytest.raises(DaemonError):
        DaemonClient(server).run_session("does-not-exist")
