"""The HTTP surface: JSON endpoints and the server-rendered report page."""

import pytest

pytest.importorskip("fastapi", reason="web extras not installed")

from fastapi.testclient import TestClient  # noqa: E402

from webapp.app import app  # noqa: E402

client = TestClient(app)


def test_healthz_reports_scenario_count():
    payload = client.get("/healthz").json()
    assert payload["ok"] is True
    assert payload["scenarios"] >= 3


def test_scenarios_are_listed():
    ids = {item["id"] for item in client.get("/api/scenarios").json()}
    assert {"checkout_low_contrast", "clean_profile_screen"} <= ids


def test_audit_returns_findings_for_a_defective_screen():
    payload = client.get("/api/audit/checkout_low_contrast").json()
    assert payload["scenario_id"] == "checkout_low_contrast"
    assert payload["by_severity"]["serious"] >= 1
    assert any(f["rule_id"] == "ux.contrast.text" for f in payload["findings"])


def test_clean_screen_audits_clean():
    payload = client.get("/api/audit/clean_profile_screen").json()
    assert payload["findings"] == []


def test_unknown_scenario_is_404():
    assert client.get("/api/audit/does-not-exist").status_code == 404


def test_tool_surface_is_exposed():
    names = {tool["name"] for tool in client.get("/api/tools").json()}
    assert "design.audit" in names
    assert "ui.tap" in names


def test_index_renders_every_scenario():
    response = client.get("/")
    assert response.status_code == 200
    body = response.text
    assert "droidcode" in body
    assert body.count("<section class=\"card\">") == 3
    assert "ux.contrast.text" in body


def test_page_escapes_scenario_text():
    from webapp.page import render_page

    html = render_page([
        {
            "scenario_id": "<script>x</script>",
            "goal": "",
            "findings": [],
            "by_severity": {"critical": 0, "serious": 0, "moderate": 0, "minor": 0},
            "nodes_seen": 0,
        }
    ])
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
