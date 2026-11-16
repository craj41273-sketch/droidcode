"""Real hardware / emulator backend over `adb`.

Not exercised in CI (there is no device there); the contract is identical to
`MockDevice`, and `tests/test_adb_backend.py` checks command construction with a
recording stub instead of a phone.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image

from ..protocol import DeviceSpec
from .base import DeviceError, DeviceEvent


class AdbDevice:
    def __init__(self, serial: str | None = None, adb_path: str = "adb", timeout_s: float = 30.0) -> None:
        self.adb_path = adb_path
        self.serial = serial
        self.timeout_s = timeout_s
        self._events: list[DeviceEvent] = []
        self._spec: DeviceSpec | None = None

    # -- plumbing ----------------------------------------------------------
    def _base(self) -> list[str]:
        if shutil.which(self.adb_path) is None:
            raise DeviceError(f"{self.adb_path!r} not found on PATH")
        command = [self.adb_path]
        if self.serial:
            command += ["-s", self.serial]
        return command

    def _run(self, args: list[str], binary: bool = False) -> bytes | str:
        try:
            completed = subprocess.run(
                self._base() + args,
                capture_output=True,
                timeout=self.timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise DeviceError(f"adb timed out: {' '.join(args)}") from error
        if completed.returncode != 0:
            raise DeviceError(completed.stderr.decode("utf-8", "replace").strip() or "adb failed")
        return completed.stdout if binary else completed.stdout.decode("utf-8", "replace")

    # -- lifecycle ---------------------------------------------------------
    @property
    def spec(self) -> DeviceSpec:
        if self._spec is None:
            size = str(self._run(["shell", "wm", "size"])).strip()
            density = str(self._run(["shell", "wm", "density"])).strip()
            width, height = 1080, 2400
            for token in size.replace(":", " ").split():
                if "x" in token and token.replace("x", "").isdigit():
                    width, height = (int(part) for part in token.split("x"))
                    break
            dpi = 420
            for token in density.replace(":", " ").split():
                if token.isdigit():
                    dpi = int(token)
                    break
            self._spec = DeviceSpec(width_px=width, height_px=height, density_dpi=dpi)
        return self._spec

    def start(self) -> None:
        self._run(["wait-for-device"])
        self._events.append(DeviceEvent("start", {"serial": self.serial}))

    def stop(self) -> None:
        self._events.append(DeviceEvent("stop"))

    def events(self) -> list[DeviceEvent]:
        return list(self._events)

    # -- observation -------------------------------------------------------
    def screenshot(self) -> Image.Image:
        raw = self._run(["exec-out", "screencap", "-p"], binary=True)
        if not raw:
            raise DeviceError("empty screencap")
        return Image.open(BytesIO(raw)).convert("RGB")

    def dump_tree(self) -> str:
        remote = "/sdcard/window_dump.xml"
        self._run(["shell", "uiautomator", "dump", remote])
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / "window_dump.xml"
            self._run(["pull", remote, str(local)])
            return local.read_text(encoding="utf-8", errors="replace")

    # -- input -------------------------------------------------------------
    def tap(self, x: int, y: int) -> None:
        self._run(["shell", "input", "tap", str(x), str(y)])
        self._events.append(DeviceEvent("tap", {"x": x, "y": y}))

    def long_press(self, x: int, y: int, duration_ms: int = 600) -> None:
        self._run(["shell", "input", "swipe", str(x), str(y), str(x), str(y), str(duration_ms)])
        self._events.append(DeviceEvent("long_press", {"x": x, "y": y, "duration_ms": duration_ms}))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._run(
            ["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)]
        )
        self._events.append(DeviceEvent("swipe", {"from": [x1, y1], "to": [x2, y2]}))

    def type_text(self, text: str) -> None:
        escaped = text.replace(" ", "%s")
        self._run(["shell", "input", "text", escaped])
        self._events.append(DeviceEvent("type", {"text": text}))

    def press_back(self) -> None:
        self._run(["shell", "input", "keyevent", "4"])
        self._events.append(DeviceEvent("back"))

    def shell(self, command: str) -> str:
        self._events.append(DeviceEvent("shell", {"command": command}))
        return str(self._run(["shell", *command.split()]))
