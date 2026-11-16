"""A deterministic, in-memory Android device.

It renders a scenario (JSON) into a real PIL image and a real uiautomator XML
hierarchy, so the same checks that run on hardware run in CI with no emulator,
no flakiness, and no GPU. Scenarios double as eval fixtures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from ..checks.color import parse_hex
from ..protocol import Bounds, DeviceSpec
from .base import DeviceError, DeviceEvent


@dataclass
class Widget:
    id: str
    class_name: str = "android.view.View"
    text: str = ""
    content_desc: str = ""
    bounds: Bounds = field(default_factory=lambda: Bounds(0, 0, 0, 0))
    bg: str = "#FFFFFF"
    fg: str = "#000000"
    text_size_dp: float = 14.0
    clickable: bool = False
    enabled: bool = True
    bold: bool = False
    radius_dp: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "Widget":
        return cls(
            id=data["id"],
            class_name=data.get("class_name", "android.view.View"),
            text=data.get("text", ""),
            content_desc=data.get("content_desc", ""),
            bounds=Bounds.from_list(data["bounds"]),
            bg=data.get("bg", "#FFFFFF"),
            fg=data.get("fg", "#000000"),
            text_size_dp=float(data.get("text_size_dp", 14)),
            clickable=bool(data.get("clickable", False)),
            enabled=bool(data.get("enabled", True)),
            bold=bool(data.get("bold", False)),
            radius_dp=float(data.get("radius_dp", 0)),
        )


def load_scenario(source: str | Path | dict | None) -> dict:
    """Load a scenario, also accepting an eval task file that wraps one."""
    if source is None:
        return {"name": "empty", "spec": {"width_px": 1080, "height_px": 2400}, "widgets": []}
    data = source if isinstance(source, dict) else json.loads(Path(source).read_text())
    if "widgets" not in data and isinstance(data.get("scenario"), dict):
        return data["scenario"]
    return data


class MockDevice:
    """Implements `DeviceBackend` against a scenario description."""

    def __init__(self, scenario: dict) -> None:
        self.scenario = scenario
        self._spec = DeviceSpec.from_dict(scenario.get("spec", {"width_px": 1080, "height_px": 2400}))
        if scenario.get("name") and not self._spec.name:
            # Readable device keys make reports and screenshots self-describing.
            self._spec.name = str(scenario["name"])
        self.background = scenario.get("background", "#FFFFFF")
        self.package = scenario.get("package", "com.example.app")
        self.widgets = [Widget.from_dict(w) for w in scenario.get("widgets", [])]
        self._events: list[DeviceEvent] = []
        self._started = False
        self._typed = ""

    # -- lifecycle ---------------------------------------------------------
    @property
    def spec(self) -> DeviceSpec:
        return self._spec

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def events(self) -> list[DeviceEvent]:
        return list(self._events)

    # -- observation -------------------------------------------------------
    def screenshot(self) -> Image.Image:
        if not self._started:
            raise DeviceError("device not started")
        image = Image.new("RGB", (self._spec.width_px, self._spec.height_px), parse_hex(self.background))
        draw = ImageDraw.Draw(image)
        for widget in self.widgets:
            self._paint(draw, widget)
        return image

    def _paint(self, draw: ImageDraw.ImageDraw, widget: Widget) -> None:
        box = widget.bounds
        fill = parse_hex(widget.bg)
        draw.rectangle([box.left, box.top, box.right - 1, box.bottom - 1], fill=fill)
        if not widget.text:
            return
        # Simulate glyph coverage: a band of ink at the text baseline. Wide
        # enough to sample a foreground colour, thin enough to leave the
        # background modal inside the box.
        ink = parse_hex(widget.fg)
        density = self._spec.density * self._spec.font_scale
        glyph_px = int(widget.text_size_dp * density)
        width = min(box.width - 8, max(4, int(len(widget.text) * glyph_px * 0.55)))
        height = max(2, int(glyph_px * 0.7))
        top = box.top + max(1, (box.height - height) // 2)
        left = box.left + 4
        step = max(2, glyph_px // 3)
        x = left
        while x < left + width:
            draw.rectangle([x, top, min(x + step - 1, left + width - 1), top + height - 1], fill=ink)
            x += step

    def dump_tree(self) -> str:
        if not self._started:
            raise DeviceError("device not started")
        nodes = []
        for index, widget in enumerate(self.widgets):
            attrs = {
                "index": index,
                "text": widget.text,
                "resource-id": widget.id,
                "class": widget.class_name,
                "package": self.package,
                "content-desc": widget.content_desc,
                "clickable": str(widget.clickable).lower(),
                "enabled": str(widget.enabled).lower(),
                "visible-to-user": "true",
                "bounds": self._bounds_attr(widget.bounds),
                "text-size-dp": widget.text_size_dp,
                "bold": str(widget.bold).lower(),
                "corner-radius-dp": widget.radius_dp,
            }
            rendered = " ".join(f'{key}="{value}"' for key, value in attrs.items())
            nodes.append(f"  <node {rendered} />")
        body = "\n".join(nodes)
        return (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>\n"
            f'<hierarchy rotation="0">\n'
            f'  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" '
            f'package="{self.package}" content-desc="" clickable="false" enabled="true" '
            f'bounds="[0,0][{self._spec.width_px},{self._spec.height_px}]">\n'
            f"{body}\n"
            "  </node>\n"
            "</hierarchy>\n"
        )

    @staticmethod
    def _bounds_attr(bounds: Bounds) -> str:
        return f"[{bounds.left},{bounds.top}][{bounds.right},{bounds.bottom}]"

    # -- input -------------------------------------------------------------
    def tap(self, x: int, y: int) -> None:
        target = next((w for w in self.widgets if w.clickable and w.bounds.contains(x, y)), None)
        self._events.append(
            DeviceEvent("tap", {"x": x, "y": y, "target": target.id if target else None})
        )
        if target is None:
            raise DeviceError(f"no clickable target at ({x}, {y})")

    def long_press(self, x: int, y: int, duration_ms: int = 600) -> None:
        self._events.append(DeviceEvent("long_press", {"x": x, "y": y, "duration_ms": duration_ms}))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._events.append(
            DeviceEvent("swipe", {"from": [x1, y1], "to": [x2, y2], "duration_ms": duration_ms})
        )

    def type_text(self, text: str) -> None:
        self._typed += text
        self._events.append(DeviceEvent("type", {"text": text}))

    def press_back(self) -> None:
        self._events.append(DeviceEvent("back"))

    def shell(self, command: str) -> str:
        self._events.append(DeviceEvent("shell", {"command": command}))
        if "gfxinfo" in command:
            return self.scenario.get("gfxinfo", "")
        if "wm density" in command:
            return f"Physical density: {self._spec.density_dpi}"
        return ""

    @property
    def typed_text(self) -> str:
        return self._typed

    def tapped_targets(self) -> list[str]:
        return [e.detail["target"] for e in self._events if e.kind == "tap" and e.detail.get("target")]
