"""The audit pipeline: one screen, one configuration, every rule, one report.

This is the unit of work the agent optimises. It is deliberately deterministic:
same scenario in, same findings out, which is what makes it usable as an eval
target and as a CI gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from PIL import Image

from . import uitree
from .checks.contrast import check_contrast
from .checks.layout import (
    check_missing_label,
    check_spacing_grid,
    check_text_overflow,
    check_touch_target,
    sort_findings,
)
from .checks.tokens import check_token_drift
from .device.base import DeviceBackend
from .perf import FrameStats, parse_gfxinfo
from .protocol import Finding, UiNode
from .tokens import DesignTokens
from .vision import estimate_colors, node_colors


@dataclass
class AuditReport:
    device_key: str
    spec: dict
    findings: list[Finding] = field(default_factory=list)
    frame_stats: FrameStats | None = None
    screenshot_path: str = ""
    nodes_seen: int = 0

    def by_rule(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.rule_id] = counts.get(finding.rule_id, 0) + 1
        return dict(sorted(counts.items()))

    def by_severity(self) -> dict[str, int]:
        counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "device_key": self.device_key,
            "spec": self.spec,
            "nodes_seen": self.nodes_seen,
            "screenshot": self.screenshot_path,
            "frame_stats": self.frame_stats.to_dict() if self.frame_stats else None,
            "by_severity": self.by_severity(),
            "by_rule": self.by_rule(),
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# UX audit - {self.device_key}",
            "",
            f"- Nodes inspected: {self.nodes_seen}",
            f"- Findings: {len(self.findings)} "
            + ", ".join(f"{k} {v}" for k, v in self.by_severity().items() if v),
        ]
        if self.frame_stats:
            stats = self.frame_stats
            lines.append(
                f"- Jank: {stats.janky_percent:.2f}% of {stats.total_frames} frames, "
                f"p99 {stats.percentiles_ms.get(99, 0)}ms"
            )
        lines.append("")
        if not self.findings:
            lines.append("No findings. Screen passes the current rule set.")
            return "\n".join(lines)
        lines.append("| Severity | Rule | Node | Message | Fix |")
        lines.append("|---|---|---|---|---|")
        for finding in self.findings:
            lines.append(
                f"| {finding.severity} | `{finding.rule_id}` | `{finding.node_id}` | "
                f"{finding.message} | {finding.suggestion} |"
            )
        return "\n".join(lines)


class Auditor:
    """Runs the rule set over one device configuration."""

    def __init__(
        self,
        device: DeviceBackend,
        tokens: DesignTokens | None = None,
        package: str = "",
    ) -> None:
        self.device = device
        self.tokens = tokens or DesignTokens()
        self.package = package

    def run(self, screenshots_dir: str | Path | None = None) -> AuditReport:
        device = self.device
        device.start()
        spec = device.spec
        image = device.screenshot()
        root = uitree.parse(device.dump_tree())
        nodes = uitree.flatten(root)

        targets = uitree.clickables(root)
        text_nodes = uitree.labelled_text(root)
        measured = {n.node_id: n for n in [*targets, *text_nodes]}
        colors = {node_id: node_colors(image, node) for node_id, node in measured.items()}

        findings: list[Finding] = []
        findings += check_contrast(text_nodes, colors, device_key=spec.key)
        findings += check_touch_target(targets, spec, self.tokens.touch_target_dp, device_key=spec.key)
        findings += check_missing_label(targets, device_key=spec.key)
        findings += check_spacing_grid(root, spec, self.tokens.grid_dp, device_key=spec.key)
        findings += check_text_overflow(text_nodes, spec, device_key=spec.key)
        findings += check_token_drift(list(measured.values()), colors, self.tokens, device_key=spec.key)

        frame_stats = None
        if self.package:
            raw = device.shell(f"dumpsys gfxinfo {self.package}")
            if raw.strip():
                frame_stats = parse_gfxinfo(raw)
                if frame_stats.over_budget():
                    findings.append(
                        Finding(
                            rule_id="perf.jank.budget",
                            severity="serious",
                            category="performance",
                            message=(
                                f"{frame_stats.janky_percent:.1f}% of {frame_stats.total_frames} "
                                "frames are janky, over the 5% budget"
                            ),
                            device_key=spec.key,
                            evidence=frame_stats.to_dict(),
                            suggestion=(
                                "Profile the scrolling surface; check recomposition, "
                                "image decoding on the main thread, and layout thrash"
                            ),
                        )
                    )

        screenshot_path = ""
        if screenshots_dir is not None:
            target = Path(screenshots_dir) / f"{_slug(spec.key)}.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target)
            screenshot_path = str(target)

        return AuditReport(
            device_key=spec.key,
            spec=spec.to_dict(),
            findings=sort_findings(_dedupe(findings)),
            frame_stats=frame_stats,
            screenshot_path=screenshot_path,
            nodes_seen=len(nodes),
        )


def _dedupe(findings: Iterable[Finding]) -> list[Finding]:
    seen: set[tuple[str, str]] = set()
    unique: list[Finding] = []
    for finding in findings:
        key = finding.dedupe_key()
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    return unique


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value)


def run_matrix(
    devices: list[DeviceBackend],
    tokens: DesignTokens | None = None,
    package: str = "",
    screenshots_dir: str | Path | None = None,
) -> list[AuditReport]:
    """Audit the same screen across several configurations (size, theme, direction)."""
    return [
        Auditor(device, tokens=tokens, package=package).run(screenshots_dir=screenshots_dir)
        for device in devices
    ]


def compare_reports(reports: list[AuditReport]) -> dict[str, list[str]]:
    """Find findings that appear in some configurations but not others.

    A rule that only fires at font scale 2.0 or in RTL is a scaling bug, not a
    design flaw: the comparison is what turns a pile of reports into a verdict.
    """
    by_rule: dict[str, set[str]] = {}
    for report in reports:
        for finding in report.findings:
            by_rule.setdefault(finding.rule_id, set()).add(report.device_key)

    if not reports:
        return {}
    all_keys = {report.device_key for report in reports}
    comparison: dict[str, list[str]] = {}
    for rule_id, keys in sorted(by_rule.items()):
        if keys != all_keys:
            comparison[rule_id] = sorted(keys)
    return comparison


def summarise(reports: list[AuditReport]) -> dict:
    total = sum(len(report.findings) for report in reports)
    worst: dict[str, int] = {}
    for report in reports:
        for finding in report.findings:
            worst[finding.severity] = worst.get(finding.severity, 0) + 1
    return {
        "configurations": len(reports),
        "findings": total,
        "by_severity": worst,
        "config_specific": compare_reports(reports),
        "pass": all(
            not any(f.severity in ("critical", "serious") for f in report.findings)
            for report in reports
        ),
    }
