import pytest

from droidcode.protocol import Bounds, DeviceSpec, Finding, severity_rank


def test_bounds_geometry():
    bounds = Bounds.from_list([10, 20, 30, 60])
    assert bounds.width == 20
    assert bounds.height == 40
    assert bounds.center == (20, 40)
    assert bounds.contains(10, 20)
    assert not bounds.contains(30, 60)  # right/bottom edges are exclusive


def test_bounds_rejects_wrong_arity():
    with pytest.raises(ValueError):
        Bounds.from_list([1, 2, 3])


def test_dp_conversions_use_density_and_font_scale():
    spec = DeviceSpec(width_px=1080, height_px=2400, density_dpi=440, font_scale=1.3)
    assert spec.density == pytest.approx(2.75)
    assert spec.dp_to_px(48) == 132
    assert spec.px_to_dp(132) == pytest.approx(48)
    # sp scales with the user's font size setting, dp does not
    assert spec.scaled_dp_to_px(16) == pytest.approx(57, abs=1)


def test_device_key_encodes_configuration():
    spec = DeviceSpec(1080, 2400, 440, dark=True, rtl=True)
    assert spec.key == "1080x2400@440fs1-dark-rtl"


def test_spec_round_trips_through_dict():
    spec = DeviceSpec(720, 1600, 320, font_scale=1.5, dark=True, locale="hi-IN")
    assert DeviceSpec.from_dict(spec.to_dict()) == spec


def test_finding_rejects_unknown_severity():
    with pytest.raises(ValueError):
        Finding(rule_id="x", severity="catastrophic", category="c", message="m")


def test_findings_sort_by_severity():
    findings = [
        Finding(rule_id="a", severity="minor", category="c", message="m"),
        Finding(rule_id="b", severity="critical", category="c", message="m"),
        Finding(rule_id="c", severity="moderate", category="c", message="m"),
    ]
    assert [f.severity for f in sorted(findings, key=lambda f: severity_rank(f.severity))] == [
        "critical",
        "moderate",
        "minor",
    ]
