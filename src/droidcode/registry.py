"""Tool registry: the only way an agent touches a device or a repo.

Every tool declares a JSON schema, a risk class, and a handler. The registry
validates arguments before dispatch, and the permission policy decides whether a
call runs, is refused, or needs a human. This is the same shape as jcode's tool
layer: schema-first, risk-tagged, gated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .audit import Auditor
from .device.base import DeviceBackend, DeviceError
from .protocol import UiNode
from .tokens import DesignTokens
from .uitree import find_by_resource_id, find_by_text, parse
from .vision import diff_ratio

RISK_READ = "read"        # observes; cannot change state
RISK_DEVICE = "device"    # drives the device (input, navigation)
RISK_WRITE = "write"      # changes files or the app


class ToolError(RuntimeError):
    pass


@dataclass
class ToolResult:
    ok: bool
    output: Any = None
    error: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok, "output": self.output, "error": self.error}


Handler = Callable[[dict[str, Any]], Any]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    risk: str
    handler: Handler

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "risk": self.risk,
        }


@dataclass
class PermissionPolicy:
    """Default-deny on anything that writes, auto-approve reads."""

    allow: set[str] = field(default_factory=set)
    deny: set[str] = field(default_factory=set)
    auto_approve_risk: set[str] = field(default_factory=lambda: {RISK_READ})

    def decide(self, tool: Tool) -> str:
        if tool.name in self.deny:
            return "deny"
        if tool.name in self.allow or tool.risk in self.auto_approve_risk:
            return "allow"
        return "ask"


class ToolRegistry:
    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        self.policy = policy or PermissionPolicy()

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolError(f"unknown tool {name!r}") from None

    def names(self) -> list[str]:
        return sorted(self._tools)

    def specs(self) -> list[dict]:
        return [self._tools[name].to_dict() for name in self.names()]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        arguments = arguments or {}
        try:
            tool = self.get(name)
        except ToolError as error:
            return ToolResult(ok=False, error=str(error))

        # Validate before asking for approval: never prompt a human for a call
        # that could not have run anyway.
        missing = [
            key
            for key in tool.input_schema.get("required", [])
            if key not in arguments
        ]
        if missing:
            return ToolResult(ok=False, error=f"missing required argument(s): {', '.join(missing)}")

        decision = self.policy.decide(tool)
        if decision == "deny":
            return ToolResult(ok=False, error=f"tool {name!r} is denied by policy")
        if decision == "ask":
            return ToolResult(
                ok=False,
                error=f"tool {name!r} requires approval (risk={tool.risk}); grant it or run interactively",
            )

        try:
            return ToolResult(ok=True, output=tool.handler(arguments))
        except (ToolError, DeviceError) as error:
            return ToolResult(ok=False, error=str(error))
        except Exception as error:  # a tool must never take the session down
            return ToolResult(ok=False, error=f"{type(error).__name__}: {error}")


def _node_summary(node: UiNode) -> dict:
    return {
        "node_id": node.node_id,
        "class_name": node.class_name,
        "text": node.text,
        "content_desc": node.content_desc,
        "bounds": node.bounds.to_dict(),
        "center": list(node.bounds.center),
        "clickable": node.clickable,
    }


def _resolve(device: DeviceBackend, arguments: dict[str, Any]) -> UiNode:
    root = parse(device.dump_tree())
    if "resource_id" in arguments:
        node = find_by_resource_id(root, arguments["resource_id"])
    elif "text" in arguments:
        node = find_by_text(root, arguments["text"])
    else:
        raise ToolError("pass either 'text' or 'resource_id'")
    if node is None:
        raise ToolError(f"no node matching {arguments}")
    return node


def build_registry(
    device: DeviceBackend,
    tokens: DesignTokens | None = None,
    package: str = "",
    screenshots_dir: str | Path = "artifacts/screens",
    policy: PermissionPolicy | None = None,
) -> ToolRegistry:
    tokens = tokens or DesignTokens()
    registry = ToolRegistry(policy=policy)

    def dump_tree(arguments: dict[str, Any]) -> dict:
        root = parse(device.dump_tree())
        return {"tree": root.to_dict(), "format": arguments.get("format", "json")}

    def find(arguments: dict[str, Any]) -> dict:
        return _node_summary(_resolve(device, arguments))

    def tap(arguments: dict[str, Any]) -> dict:
        if "x" in arguments and "y" in arguments:
            x, y = int(arguments["x"]), int(arguments["y"])
        else:
            node = _resolve(device, arguments)
            x, y = node.bounds.center
        device.tap(x, y)
        return {"tapped": [x, y]}

    def type_text(arguments: dict[str, Any]) -> dict:
        device.type_text(arguments["text"])
        return {"typed": arguments["text"]}

    def swipe(arguments: dict[str, Any]) -> dict:
        spec = device.spec
        mid_x, mid_y = spec.width_px // 2, spec.height_px // 2
        span = spec.height_px // 3
        direction = arguments.get("direction", "up")
        vectors = {
            "up": (mid_x, mid_y + span, mid_x, mid_y - span),
            "down": (mid_x, mid_y - span, mid_x, mid_y + span),
            "left": (mid_x + span, mid_y, mid_x - span, mid_y),
            "right": (mid_x - span, mid_y, mid_x + span, mid_y),
        }
        if direction not in vectors:
            raise ToolError(f"unknown direction {direction!r}")
        x1, y1, x2, y2 = vectors[direction]
        device.swipe(x1, y1, x2, y2)
        return {"swiped": direction}

    def capture(arguments: dict[str, Any]) -> dict:
        name = arguments.get("name", "capture")
        target = Path(screenshots_dir) / f"{name}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        device.screenshot().save(target)
        return {"path": str(target)}

    def screen_diff(arguments: dict[str, Any]) -> dict:
        from PIL import Image

        before = Image.open(arguments["before"])
        after = Image.open(arguments["after"])
        ratio, bbox = diff_ratio(before, after)
        return {"changed_ratio": round(ratio, 5), "bbox": bbox.to_dict() if bbox else None}

    def audit(arguments: dict[str, Any]) -> dict:
        report = Auditor(device, tokens=tokens, package=package).run(
            screenshots_dir=arguments.get("screenshots_dir", screenshots_dir)
        )
        return report.to_dict()

    def frames(arguments: dict[str, Any]) -> dict:
        from .perf import parse_gfxinfo

        raw = device.shell(f"dumpsys gfxinfo {arguments.get('package', package)}")
        return parse_gfxinfo(raw).to_dict()

    def tokens_nearest(arguments: dict[str, Any]) -> dict:
        from .checks.color import parse_hex, to_hex

        color = parse_hex(arguments["hex"])
        name, distance = tokens.nearest_color(color)
        return {"hex": to_hex(color), "nearest": name, "delta_e": round(distance, 2)}

    registry.register(
        Tool(
            name="ui.dump_tree",
            description="Read the current view/accessibility hierarchy as JSON.",
            input_schema={"type": "object", "properties": {"format": {"type": "string", "enum": ["json"]}}},
            risk=RISK_READ,
            handler=dump_tree,
        )
    )
    registry.register(
        Tool(
            name="ui.find",
            description="Locate a node by visible text or resource id; returns bounds and tap centre.",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}, "resource_id": {"type": "string"}},
            },
            risk=RISK_READ,
            handler=find,
        )
    )
    registry.register(
        Tool(
            name="ui.tap",
            description="Tap a node (by text/resource id) or explicit pixel coordinates.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "resource_id": {"type": "string"},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                },
            },
            risk=RISK_DEVICE,
            handler=tap,
        )
    )
    registry.register(
        Tool(
            name="ui.type",
            description="Type text into the focused field.",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            risk=RISK_DEVICE,
            handler=type_text,
        )
    )
    registry.register(
        Tool(
            name="ui.swipe",
            description="Swipe up/down/left/right across the middle of the screen.",
            input_schema={
                "type": "object",
                "properties": {"direction": {"type": "string", "enum": ["up", "down", "left", "right"]}},
            },
            risk=RISK_DEVICE,
            handler=swipe,
        )
    )
    registry.register(
        Tool(
            name="screen.capture",
            description="Capture a screenshot to the artifacts directory.",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            risk=RISK_READ,
            handler=capture,
        )
    )
    registry.register(
        Tool(
            name="screen.diff",
            description="Compare two screenshots: changed pixel ratio and changed region.",
            input_schema={
                "type": "object",
                "properties": {"before": {"type": "string"}, "after": {"type": "string"}},
                "required": ["before", "after"],
            },
            risk=RISK_READ,
            handler=screen_diff,
        )
    )
    registry.register(
        Tool(
            name="design.audit",
            description="Run the full UX rule set (contrast, targets, labels, spacing, text fit, tokens, jank).",
            input_schema={"type": "object", "properties": {"screenshots_dir": {"type": "string"}}},
            risk=RISK_READ,
            handler=audit,
        )
    )
    registry.register(
        Tool(
            name="perf.frames",
            description="Frame statistics (jank %, p50/p90/p99) for a package.",
            input_schema={"type": "object", "properties": {"package": {"type": "string"}}},
            risk=RISK_READ,
            handler=frames,
        )
    )
    registry.register(
        Tool(
            name="design.tokens.nearest",
            description="Map a colour to the nearest design token and report the distance.",
            input_schema={
                "type": "object",
                "properties": {"hex": {"type": "string"}},
                "required": ["hex"],
            },
            risk=RISK_READ,
            handler=tokens_nearest,
        )
    )
    return registry


def dumps(specs: list[dict]) -> str:
    return json.dumps(specs, indent=2)
