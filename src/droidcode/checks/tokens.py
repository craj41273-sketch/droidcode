"""Design-token conformance: colours and radii must come from the theme."""

from __future__ import annotations

from ..protocol import Finding, UiNode
from ..tokens import DesignTokens
from .color import Color, delta_e, to_hex

RULE_ID = "design.token.drift"


def check_token_drift(
    nodes: list[UiNode],
    colors: dict[str, tuple[Color, Color]],
    tokens: DesignTokens,
    device_key: str = "",
) -> list[Finding]:
    if not tokens.colors:
        return []
    findings: list[Finding] = []
    for node in nodes:
        pair = colors.get(node.node_id)
        if pair is None:
            continue
        for role, color in (("background", pair[0]), ("foreground", pair[1])):
            name, distance = tokens.nearest_color(color)
            if distance <= tokens.colour_tolerance:
                continue
            findings.append(
                Finding(
                    rule_id=RULE_ID,
                    severity="minor",
                    category="design-system",
                    message=(
                        f"{role.title()} {to_hex(color)} on {node.label or node.node_id!r} "
                        f"is not a theme colour (closest: {name}, dE={distance:.1f})"
                    ),
                    node_id=node.node_id,
                    device_key=device_key,
                    evidence={
                        "role": role,
                        "color": to_hex(color),
                        "nearest_token": name,
                        "delta_e": round(distance, 2),
                    },
                    suggestion=f"Use the {name} token instead of a hard-coded colour",
                    confidence=0.8,
                )
            )
    return findings
