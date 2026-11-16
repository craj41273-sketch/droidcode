"""Layout rules: touch targets, labels, spacing rhythm, text fit."""

from __future__ import annotations

from ..protocol import Finding, UiNode, severity_rank

RULE_TOUCH = "ux.target.min_size"
RULE_LABEL = "a11y.label.missing"
RULE_SPACING = "ux.spacing.grid"
RULE_TEXT_FIT = "ux.text.overflow"

# Rough advance width of a glyph as a fraction of its size, for Roboto/Inter.
GLYPH_WIDTH_FACTOR = 0.55


def check_touch_target(
    nodes: list[UiNode],
    spec,
    min_dp: float = 48.0,
    device_key: str = "",
) -> list[Finding]:
    findings: list[Finding] = []
    for node in nodes:
        width_dp = spec.px_to_dp(node.bounds.width)
        height_dp = spec.px_to_dp(node.bounds.height)
        smallest = min(width_dp, height_dp)
        if smallest >= min_dp:
            continue
        findings.append(
            Finding(
                rule_id=RULE_TOUCH,
                severity="serious",
                category="accessibility",
                message=(
                    f"Touch target {node.label or node.node_id!r} is "
                    f"{width_dp:.0f}x{height_dp:.0f}dp, below the {min_dp:.0f}dp minimum"
                ),
                node_id=node.node_id,
                device_key=device_key,
                evidence={"width_dp": round(width_dp, 1), "height_dp": round(height_dp, 1)},
                suggestion=(
                    "Increase the tappable area with padding or minimumInteractiveComponentSize, "
                    "keeping the visual size unchanged"
                ),
            )
        )
    return findings


def check_missing_label(nodes: list[UiNode], device_key: str = "") -> list[Finding]:
    findings: list[Finding] = []
    for node in nodes:
        if node.has_accessible_name():
            continue
        findings.append(
            Finding(
                rule_id=RULE_LABEL,
                severity="critical",
                category="accessibility",
                message=f"Interactive {node.class_name or 'node'} has no text or content description",
                node_id=node.node_id,
                device_key=device_key,
                evidence={"class_name": node.class_name, "resource_id": node.resource_id},
                suggestion=(
                    "Give the control a contentDescription (Compose: Modifier.semantics) "
                    "or an adjacent visible label"
                ),
            )
        )
    return findings


def check_spacing_grid(root: UiNode, spec, grid_dp: float = 4.0, device_key: str = "") -> list[Finding]:
    """Sibling gaps should sit on the spacing grid; off-grid gaps break rhythm."""
    findings: list[Finding] = []
    for parent in root.walk():
        children = [c for c in parent.children if c.visible]
        if len(children) < 2:
            continue
        ordered = sorted(children, key=lambda c: (c.bounds.top, c.bounds.left))
        for first, second in zip(ordered, ordered[1:]):
            gap_px = second.bounds.top - first.bounds.bottom
            if gap_px <= 0:
                continue
            gap_dp = spec.px_to_dp(gap_px)
            remainder = gap_dp % grid_dp
            off_by = min(remainder, grid_dp - remainder)
            if off_by <= 0.5:
                continue
            findings.append(
                Finding(
                    rule_id=RULE_SPACING,
                    severity="minor",
                    category="visual",
                    message=(
                        f"Vertical gap of {gap_dp:.1f}dp between "
                        f"{first.label or first.node_id!r} and {second.label or second.node_id!r} "
                        f"is off the {grid_dp:.0f}dp grid"
                    ),
                    node_id=second.node_id,
                    device_key=device_key,
                    evidence={"gap_dp": round(gap_dp, 1), "grid_dp": grid_dp},
                    suggestion=f"Snap the spacing to the nearest multiple of {grid_dp:.0f}dp",
                    confidence=0.7,
                )
            )
    return findings


def check_text_overflow(nodes: list[UiNode], spec, device_key: str = "") -> list[Finding]:
    """Estimate whether a label fits its box at the current font scale.

    Uses the declared text size when the backend can supply it (Compose
    semantics dump) and falls back to 14sp. Deliberately conservative: this is
    a smell detector, and the screenshot diff is the ground truth.
    """
    findings: list[Finding] = []
    for node in nodes:
        text = (node.text or "").strip()
        if not text or node.bounds.width <= 0:
            continue
        size_sp = float(node.attrs.get("text_size_dp", 14))
        estimated_px = len(text) * size_sp * GLYPH_WIDTH_FACTOR * spec.density * spec.font_scale
        available_px = node.bounds.width
        if estimated_px <= available_px * 1.02:
            continue
        findings.append(
            Finding(
                rule_id=RULE_TEXT_FIT,
                severity="moderate",
                category="visual",
                message=(
                    f"Label {text!r} needs about {estimated_px:.0f}px at font scale "
                    f"{spec.font_scale:g} but the box is {available_px}px wide"
                ),
                node_id=node.node_id,
                device_key=device_key,
                evidence={
                    "estimated_px": round(estimated_px),
                    "available_px": available_px,
                    "font_scale": spec.font_scale,
                },
                suggestion=(
                    "Allow wrapping or ellipsis (maxLines + TextOverflow.Ellipsis), "
                    "or move the label to a wider container"
                ),
                confidence=0.6,
            )
        )
    return findings


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (severity_rank(f.severity), f.rule_id, f.node_id))
