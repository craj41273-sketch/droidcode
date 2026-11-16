"""Server-rendered report page. No build step, no JavaScript framework."""

from __future__ import annotations

from html import escape

SEVERITY_COLOURS = {
    "critical": "#8E1B1B",
    "serious": "#A34A00",
    "moderate": "#6B5B00",
    "minor": "#3D4B57",
}

STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: #F7FAFC; color: #16202A;
       font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
header { background: #1B4D6B; color: #fff; padding: 34px 24px 28px; }
.wrap { max-width: 1040px; margin: 0 auto; }
h1 { margin: 0 0 6px; font-size: 27px; letter-spacing: -0.3px; }
header p { margin: 0; color: #C9DCE8; max-width: 62ch; }
main { padding: 26px 24px 60px; }
.meta { display: flex; gap: 26px; flex-wrap: wrap; margin: 0 0 26px; color: #4A5A68; font-size: 13px; }
.meta b { color: #16202A; }
.card { background: #fff; border: 1px solid #DCE5EC; border-radius: 10px; padding: 18px 20px; margin-bottom: 18px; }
.card h2 { margin: 0 0 2px; font-size: 17px; }
.card .goal { color: #5A6B79; font-size: 13px; margin: 0 0 12px; }
.tally { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; font-size: 12.5px; }
.chip { border-radius: 999px; padding: 2px 10px; border: 1px solid currentColor; font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: .5px;
     color: #6B7C8A; border-bottom: 1px solid #DCE5EC; padding: 6px 8px; }
td { padding: 8px; border-bottom: 1px solid #EDF2F6; vertical-align: top; }
tr:last-child td { border-bottom: 0; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; color: #1B4D6B; }
.fix { color: #4A5A68; }
.clean { color: #1F6F54; font-weight: 600; }
footer { border-top: 1px solid #DCE5EC; padding: 18px 24px 40px; color: #5A6B79; font-size: 13px; }
footer a { color: #1B4D6B; }
a { color: #1B4D6B; }
"""


def _chip(severity: str, count: int) -> str:
    colour = SEVERITY_COLOURS.get(severity, "#3D4B57")
    return f'<span class="chip" style="color:{colour}">{escape(severity)} {count}</span>'


def _row(finding: dict) -> str:
    return (
        "<tr>"
        f'<td><span style="color:{SEVERITY_COLOURS.get(finding["severity"], "#3D4B57")};'
        f'font-weight:600">{escape(finding["severity"])}</span></td>'
        f"<td><code>{escape(finding['rule_id'])}</code></td>"
        f"<td><code>{escape(finding.get('node_id') or '-')}</code></td>"
        f"<td>{escape(finding['message'])}</td>"
        f'<td class="fix">{escape(finding.get("suggestion", ""))}</td>'
        "</tr>"
    )


def _card(report: dict) -> str:
    findings = report["findings"]
    tally = "".join(
        _chip(severity, count) for severity, count in report["by_severity"].items() if count
    ) or '<span class="clean">no findings</span>'

    if findings:
        rows = "".join(_row(finding) for finding in findings)
        body = (
            "<table><thead><tr><th>Severity</th><th>Rule</th><th>Node</th>"
            "<th>Finding</th><th>Suggested fix</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
        )
    else:
        body = '<p class="clean">Passes every rule in the set - this is the false-positive control.</p>'

    return (
        '<section class="card">'
        f"<h2>{escape(report['scenario_id'])}</h2>"
        f'<p class="goal">{escape(report.get("goal", ""))}</p>'
        f'<div class="tally">{tally}</div>'
        f"{body}"
        "</section>"
    )


def render_page(reports: list[dict]) -> str:
    cards = "".join(_card(report) for report in reports)
    total = sum(len(report["findings"]) for report in reports)
    nodes = sum(report["nodes_seen"] for report in reports)
    ids = ", ".join(report["scenario_id"] for report in reports)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>droidcode - Android UI/UX audit</title>
<style>{STYLE}</style>
</head>
<body>
<header><div class="wrap">
  <h1>droidcode</h1>
  <p>An agentic coding harness for Android phone UI/UX design and testing. Every audit below is
  computed live on a deterministic mock device - the same rule set, no emulator.</p>
</div></header>
<main><div class="wrap">
  <p class="meta">
    <span><b>{len(reports)}</b> screens</span>
    <span><b>{nodes}</b> nodes inspected</span>
    <span><b>{total}</b> findings</span>
    <span>rules: contrast, targets, labels, text fit, spacing, tokens, jank</span>
  </p>
  {cards}
</div></main>
<footer><div class="wrap">
  JSON: <a href="/api/audit/checkout_low_contrast">/api/audit/&lt;scenario&gt;</a> &nbsp;
  <a href="/api/tools">/api/tools</a> &nbsp; <a href="/api/scenarios">/api/scenarios</a> &nbsp;
  <a href="/docs">OpenAPI</a><br>
  Scenarios: {escape(ids)}
</div></footer>
</body>
</html>"""
