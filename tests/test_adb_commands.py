import subprocess
from io import BytesIO

import pytest
from PIL import Image

from droidcode.device.adb import AdbDevice
from droidcode.device.base import DeviceError


class Recorder:
    """Stands in for `adb`: records the command line, returns canned output."""

    def __init__(self, stdout=b"", returncode=0, stderr=b""):
        self.calls: list[list[str]] = []
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, command, **kwargs):
        self.calls.append(list(command))
        return subprocess.CompletedProcess(command, self.returncode, self.stdout, self.stderr)


@pytest.fixture(autouse=True)
def fake_adb_on_path(monkeypatch):
    """Pretend the adb binary exists; the tests assert command construction."""
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/adb")


@pytest.fixture
def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_tap_builds_the_expected_adb_command(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    AdbDevice(serial="emulator-5554").tap(100, 200)
    assert recorder.calls[0] == ["adb", "-s", "emulator-5554", "shell", "input", "tap", "100", "200"]


def test_typing_escapes_spaces(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(subprocess, "run", recorder)
    AdbDevice().type_text("hello world")
    assert recorder.calls[0][-1] == "hello%sworld"


def test_screenshot_decodes_png(monkeypatch, png_bytes):
    monkeypatch.setattr(subprocess, "run", Recorder(stdout=png_bytes))
    image = AdbDevice().screenshot()
    assert image.size == (4, 4)
    assert image.getpixel((0, 0)) == (1, 2, 3)


def test_failed_adb_call_becomes_device_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", Recorder(returncode=1, stderr=b"device offline"))
    with pytest.raises(DeviceError, match="device offline"):
        AdbDevice().tap(1, 1)


def test_missing_adb_binary_is_reported(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(DeviceError, match="not found"):
        AdbDevice(adb_path="adb-nope").tap(1, 1)


def test_spec_is_derived_from_wm_output(monkeypatch):
    outputs = iter(["Physical size: 1080x2400", "Physical density: 440"])
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, next(outputs).encode(), b""),
    )
    spec = AdbDevice().spec
    assert (spec.width_px, spec.height_px, spec.density_dpi) == (1080, 2400, 440)
