"""Shared value types. Everything serialises to plain JSON."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

# Material Design 3 reference density: 160 dpi == 1 dp.
REFERENCE_DPI = 160.0


@dataclass(frozen=True)
class Bounds:
    """A rectangle in device pixels."""

    left: int
    top: int
    right: int
    bottom: int

    @classmethod
    def from_list(cls, values: list[int]) -> "Bounds":
        if len(values) != 4:
            raise ValueError(f"bounds need 4 values, got {values!r}")
        return cls(*(int(v) for v in values))

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def to_dict(self) -> list[int]:
        return [self.left, self.top, self.right, self.bottom]


@dataclass
class DeviceSpec:
    """One point in the device matrix: size, density, font scale, theme, direction."""

    width_px: int
    height_px: int
    density_dpi: int = 420
    font_scale: float = 1.0
    dark: bool = False
    rtl: bool = False
    locale: str = "en-IN"
    name: str = ""

    @property
    def density(self) -> float:
        return self.density_dpi / REFERENCE_DPI

    def px_to_dp(self, px: float) -> float:
        return px / self.density

    def dp_to_px(self, dp: float) -> int:
        return int(round(dp * self.density))

    def scaled_dp_to_px(self, dp: float) -> int:
        """Font-scaled conversion: sp grows with the user's font size setting."""
        return int(round(dp * self.density * self.font_scale))

    @property
    def key(self) -> str:
        if self.name:
            return self.name
        direction = "rtl" if self.rtl else "ltr"
        theme = "dark" if self.dark else "light"
        return f"{self.width_px}x{self.height_px}@{self.density_dpi}fs{self.font_scale:g}-{theme}-{direction}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "density_dpi": self.density_dpi,
            "font_scale": self.font_scale,
            "dark": self.dark,
            "rtl": self.rtl,
            "locale": self.locale,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeviceSpec":
        return cls(
            width_px=int(data["width_px"]),
            height_px=int(data["height_px"]),
            density_dpi=int(data.get("density_dpi", 420)),
            font_scale=float(data.get("font_scale", 1.0)),
            dark=bool(data.get("dark", False)),
            rtl=bool(data.get("rtl", False)),
            locale=str(data.get("locale", "en-IN")),
            name=str(data.get("name", "")),
        )


@dataclass
class UiNode:
    """A node of the accessibility/view hierarchy, as an agent sees the screen."""

    node_id: str
    class_name: str = ""
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    bounds: Bounds = field(default_factory=lambda: Bounds(0, 0, 0, 0))
    clickable: bool = False
    enabled: bool = True
    visible: bool = True
    children: list["UiNode"] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)

    def walk(self) -> Iterator["UiNode"]:
        yield self
        for child in self.children:
            yield from child.walk()

    @property
    def label(self) -> str:
        return self.text or self.content_desc

    def has_accessible_name(self) -> bool:
        return bool((self.text or "").strip() or (self.content_desc or "").strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "class_name": self.class_name,
            "resource_id": self.resource_id,
            "text": self.text,
            "content_desc": self.content_desc,
            "bounds": self.bounds.to_dict(),
            "clickable": self.clickable,
            "enabled": self.enabled,
            "visible": self.visible,
            "attrs": dict(self.attrs),
            "children": [c.to_dict() for c in self.children],
        }


SEVERITIES = ("critical", "serious", "moderate", "minor")


@dataclass
class Finding:
    """One result from one rule on one node in one device configuration."""

    rule_id: str
    severity: str
    category: str
    message: str
    node_id: str = ""
    device_key: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.severity not in SEVERITIES:
            raise ValueError(f"unknown severity {self.severity!r}")

    def dedupe_key(self) -> tuple[str, str]:
        return (self.rule_id, self.node_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "node_id": self.node_id,
            "device_key": self.device_key,
            "evidence": dict(self.evidence),
            "suggestion": self.suggestion,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Finding":
        return cls(
            rule_id=data["rule_id"],
            severity=data["severity"],
            category=data.get("category", ""),
            message=data.get("message", ""),
            node_id=data.get("node_id", ""),
            device_key=data.get("device_key", ""),
            evidence=dict(data.get("evidence", {})),
            suggestion=data.get("suggestion", ""),
            confidence=float(data.get("confidence", 1.0)),
        )


def severity_rank(severity: str) -> int:
    """Lower is worse, so sorted() puts the important findings first."""
    try:
        return SEVERITIES.index(severity)
    except ValueError:
        return len(SEVERITIES)
