"""Design tokens: the single source of truth a UI is judged against.

A design system exports these (Figma variables, a Compose `Theme.kt`, or a
Style Dictionary build). droidcode consumes them so "does this screen match the
design system?" becomes a measurement instead of an opinion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .color import Color, delta_e, parse_hex

DEFAULT_GRID_DP = 4.0
DEFAULT_TOUCH_TARGET_DP = 48.0


@dataclass
class DesignTokens:
    colors: dict[str, Color] = field(default_factory=dict)
    spacing_dp: list[float] = field(default_factory=lambda: [4, 8, 12, 16, 24, 32, 48])
    radius_dp: list[float] = field(default_factory=lambda: [0, 8, 12, 16, 28])
    type_scale_sp: list[float] = field(default_factory=lambda: [11, 12, 14, 16, 22, 24, 28, 32, 36, 45])
    grid_dp: float = DEFAULT_GRID_DP
    touch_target_dp: float = DEFAULT_TOUCH_TARGET_DP
    colour_tolerance: float = 3.0

    @classmethod
    def from_dict(cls, data: dict) -> "DesignTokens":
        colors = {name: parse_hex(value) for name, value in data.get("colors", {}).items()}
        return cls(
            colors=colors,
            spacing_dp=[float(v) for v in data.get("spacing_dp", cls().spacing_dp)],
            radius_dp=[float(v) for v in data.get("radius_dp", cls().radius_dp)],
            type_scale_sp=[float(v) for v in data.get("type_scale_sp", cls().type_scale_sp)],
            grid_dp=float(data.get("grid_dp", DEFAULT_GRID_DP)),
            touch_target_dp=float(data.get("touch_target_dp", DEFAULT_TOUCH_TARGET_DP)),
            colour_tolerance=float(data.get("colour_tolerance", 3.0)),
        )

    @classmethod
    def load(cls, path: str | Path) -> "DesignTokens":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def nearest_color(self, color: Color) -> tuple[str, float]:
        if not self.colors:
            return ("", float("inf"))
        name, distance = min(
            ((name, delta_e(color, value)) for name, value in self.colors.items()),
            key=lambda item: item[1],
        )
        return name, distance

    def is_on_scale(self, value_dp: float, scale: list[float], tolerance: float = 0.75) -> bool:
        return any(abs(value_dp - candidate) <= tolerance for candidate in scale)
