import pytest

from droidcode.device.base import DeviceError
from droidcode.device.mock import MockDevice, load_scenario
from droidcode.uitree import find_by_resource_id, parse

SCENARIO = {
    "name": "demo",
    "package": "com.example.app",
    "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
    "background": "#FFFFFF",
    "widgets": [
        {"id": "btn", "text": "Pay now", "bounds": [40, 1800, 1040, 1932], "bg": "#6750A4", "fg": "#FFFFFF", "clickable": True},
        {"id": "label", "text": "Total", "bounds": [40, 200, 400, 290], "bg": "#FFFFFF", "fg": "#1C1B1F"},
    ],
    "gfxinfo": "Total frames rendered: 100\nJanky frames: 2 (2.00%)\n99th percentile: 14ms",
}


def test_device_must_be_started():
    device = MockDevice(SCENARIO)
    with pytest.raises(DeviceError):
        device.screenshot()


def test_screenshot_matches_spec_and_paints_widgets():
    device = MockDevice(SCENARIO)
    device.start()
    image = device.screenshot()
    assert image.size == (1080, 2400)
    assert image.getpixel((500, 1866))[0] > 90   # inside the button fill
    assert image.getpixel((5, 5)) == (255, 255, 255)


def test_dump_tree_round_trips_through_the_parser():
    device = MockDevice(SCENARIO)
    device.start()
    root = parse(device.dump_tree())
    button = find_by_resource_id(root, "btn")
    assert button is not None
    assert button.bounds.to_dict() == [40, 1800, 1040, 1932]
    assert button.attrs["text_size_dp"] == 14.0


def test_tap_hits_clickable_widget():
    device = MockDevice(SCENARIO)
    device.start()
    device.tap(500, 1866)
    assert device.tapped_targets() == ["btn"]


def test_tap_outside_any_control_raises():
    device = MockDevice(SCENARIO)
    device.start()
    with pytest.raises(DeviceError):
        device.tap(5, 5)


def test_input_and_navigation_are_recorded():
    device = MockDevice(SCENARIO)
    device.start()
    device.type_text("42")
    device.press_back()
    device.swipe(10, 10, 10, 900)
    kinds = [event.kind for event in device.events()]
    assert kinds == ["type", "back", "swipe"]
    assert device.typed_text == "42"


def test_shell_returns_scenario_fixtures():
    device = MockDevice(SCENARIO)
    device.start()
    assert "Janky frames" in device.shell("dumpsys gfxinfo com.example.app")
    assert "440" in device.shell("wm density")
    assert device.shell("whoami") == ""


def test_load_scenario_accepts_dicts_and_paths(tmp_path):
    assert load_scenario(SCENARIO)["name"] == "demo"
    path = tmp_path / "scenario.json"
    path.write_text(__import__("json").dumps(SCENARIO))
    assert load_scenario(path)["name"] == "demo"
    assert load_scenario(None)["widgets"] == []
