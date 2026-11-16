"""WCAG contrast rule: text must be readable against what is actually behind it."""

from __future__ import annotations

from ..protocol import Finding, UiNode
from .color import Color, contrast_ratio, is_large_text, to_hex, wcag_level

RULE_ID = "ux.contrast.text"


def check_contrast(
    nodes: list[UiNode],
    colors: dict[str, tuple[Color, Color]],
    device_key: str = "",
) -> list[Finding]:
    findings: list[Finding] = []
    for node in nodes:
        pair = colors.get(node.node_id)
        if pair is None:
            continue
        background, foreground = pair
        if background == foreground:
            continue  # nothing rendered to measure
        size_sp = float(node.attrs.get("text_size_dp", 14))
        bold = bool(node.attrs.get("bold", False))
        large = is_large_text(size_sp, bold)
        ratio = contrast_ratio(foreground, background)
        level = wcag_level(ratio, large)
        if level != "fail":
            continue
        required = 3.0 if large else 4.5
        findings.append(
            Finding(
                rule_id=RULE_ID,
                severity="serious" if ratio < 3.0 else "moderate",
                category="accessibility",
                message=(
                    f"Text {node.label!r} has {ratio:.2f}:1 contrast against its background; "
                    f"WCAG AA needs {required}:1"
                ),
                node_id=node.node_id,
                device_key=device_key,
                evidence={
                    "foreground": to_hex(foreground),
                    "background": to_hex(background),
                    "ratio": round(ratio, 2),
                    "required": required,
                    "text_size_sp": size_sp,
                    "large_text": large,
                },
                suggestion=(
                    "Darken the text or lighten the surface until the pair reaches "
                    f"{required}:1 (use an on-surface token from the theme, not a literal colour)"
                ),
            )
        )
    return findings
