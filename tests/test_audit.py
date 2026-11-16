from droidcode.audit import Auditor, compare_reports, run_matrix, summarise
from droidcode.device.mock import MockDevice


def test_clean_screen_produces_no_findings(good_scenario, tokens):
    report = Auditor(MockDevice(good_scenario), tokens=tokens).run()
    assert report.findings == []
    assert report.nodes_seen == 3


def test_defective_screen_reports_the_expected_rules(tokens):
    scenario = {
        "name": "bad",
        "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
        "widgets": [
            {"id": "pale", "text": "Pay now", "bounds": [40, 400, 1040, 532], "bg": "#FFFFFF", "fg": "#EEEEEE", "text_size_dp": 16, "clickable": True},
            {"id": "tiny", "text": "x", "bounds": [40, 700, 90, 750], "bg": "#FFFFFF", "fg": "#1C1B1F", "clickable": True},
        ],
    }
    report = Auditor(MockDevice(scenario), tokens=tokens).run()
    rules = {finding.rule_id for finding in report.findings}
    assert {"ux.contrast.text", "ux.target.min_size"} <= rules


def test_findings_are_deduplicated_and_sorted(good_scenario, tokens):
    scenario = dict(good_scenario)
    scenario["widgets"] = [
        {"id": "a", "text": "x", "bounds": [40, 400, 90, 450], "bg": "#FFFFFF", "fg": "#1C1B1F", "clickable": True},
        {"id": "b", "text": "y", "bounds": [40, 500, 90, 550], "bg": "#FFFFFF", "fg": "#1C1B1F", "clickable": True},
    ]
    report = Auditor(MockDevice(scenario), tokens=tokens).run()
    keys = [finding.dedupe_key() for finding in report.findings]
    assert len(keys) == len(set(keys))
    severities = [finding.severity for finding in report.findings]
    order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
    assert severities == sorted(severities, key=order.get)


def test_report_serialises_and_renders_markdown(good_scenario, tokens, tmp_path):
    report = Auditor(MockDevice(good_scenario), tokens=tokens).run(screenshots_dir=tmp_path)
    payload = report.to_dict()
    assert payload["by_severity"]["critical"] == 0
    assert report.screenshot_path.endswith(".png")
    markdown = report.to_markdown()
    assert "UX audit" in markdown
    assert "passes the current rule set" in markdown


def test_jank_budget_becomes_a_finding(tokens):
    scenario = {
        "name": "slow",
        "package": "com.example.slow",
        "spec": {"width_px": 1080, "height_px": 2400},
        "widgets": [],
        "gfxinfo": "Total frames rendered: 400\nJanky frames: 60 (15.00%)\n99th percentile: 40ms",
    }
    report = Auditor(MockDevice(scenario), tokens=tokens, package="com.example.slow").run()
    assert any(f.rule_id == "perf.jank.budget" for f in report.findings)
    assert report.frame_stats.janky_percent == 15.0


def test_matrix_finds_configuration_specific_findings(tokens):
    base = {
        "widgets": [
            {"id": "label", "text": "Settings and privacy", "bounds": [40, 400, 640, 490], "bg": "#FFFFFF", "fg": "#1C1B1F", "text_size_dp": 16},
        ]
    }
    normal = {**base, "name": "normal", "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440}}
    scaled = {**base, "name": "large-font", "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440, "font_scale": 2.0}}

    reports = run_matrix([MockDevice(normal), MockDevice(scaled)], tokens=tokens)
    assert len(reports) == 2
    comparison = compare_reports(reports)
    assert comparison.get("ux.text.overflow") == ["large-font"]
    summary = summarise(reports)
    assert summary["configurations"] == 2
    assert summary["config_specific"]["ux.text.overflow"] == ["large-font"]


def test_summary_pass_flag(good_scenario, tokens):
    report = Auditor(MockDevice(good_scenario), tokens=tokens).run()
    assert summarise([report])["pass"] is True
