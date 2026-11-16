"""The device protocol every backend implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from PIL import Image

from ..protocol import DeviceSpec


class DeviceError(RuntimeError):
    """A device operation failed (no device, timeout, bad state)."""


@dataclass
class DeviceEvent:
    """Something that happened on the device, in order."""

    kind: str
    detail: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DeviceBackend(Protocol):
    @property
    def spec(self) -> DeviceSpec: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def screenshot(self) -> Image.Image: ...

    def dump_tree(self) -> str: ...

    def tap(self, x: int, y: int) -> None: ...

    def long_press(self, x: int, y: int, duration_ms: int = 600) -> None: ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None: ...

    def type_text(self, text: str) -> None: ...

    def press_back(self) -> None: ...

    def shell(self, command: str) -> str: ...

    def events(self) -> list[DeviceEvent]: ...
