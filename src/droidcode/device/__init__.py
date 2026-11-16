"""Device backends.

`DeviceBackend` is the seam that makes the harness testable: every check and
tool runs against the protocol, so the deterministic `MockDevice` can stand in
for an emulator in CI and the same code drives real hardware through `AdbDevice`.
"""

from .base import DeviceBackend, DeviceError, DeviceEvent
from .mock import MockDevice, load_scenario

__all__ = ["DeviceBackend", "DeviceError", "DeviceEvent", "MockDevice", "load_scenario"]


def open_device(scenario_or_serial: str | None = None, *, use_mock: bool = True) -> DeviceBackend:
    """Factory used by the CLI: mock scenario path, or an adb serial."""
    if use_mock:
        return MockDevice(load_scenario(scenario_or_serial))
    from .adb import AdbDevice

    return AdbDevice(serial=scenario_or_serial)
