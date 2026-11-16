import pytest

from droidcode.checks.color import (
    contrast_ratio,
    delta_e,
    is_large_text,
    parse_hex,
    relative_luminance,
    to_hex,
    wcag_level,
)


def test_parse_hex_formats():
    assert parse_hex("#FFFFFF") == (255, 255, 255)
    assert parse_hex("FFF") == (255, 255, 255)
    assert parse_hex("#80FF0000") == (255, 0, 0)  # Android AARRGGBB drops alpha
    with pytest.raises(ValueError):
        parse_hex("nope")


def test_to_hex_round_trip():
    assert to_hex(parse_hex("#6750A4")) == "#6750A4"


def test_contrast_ratio_extremes():
    black, white = parse_hex("#000000"), parse_hex("#FFFFFF")
    assert contrast_ratio(black, white) == pytest.approx(21.0)
    assert contrast_ratio(white, white) == pytest.approx(1.0)
    assert contrast_ratio(white, black) == contrast_ratio(black, white)


def test_relative_luminance_matches_wcag_reference():
    assert relative_luminance((255, 255, 255)) == pytest.approx(1.0)
    assert relative_luminance((0, 0, 0)) == pytest.approx(0.0)
    assert relative_luminance((255, 0, 0)) == pytest.approx(0.2126, abs=1e-4)


def test_wcag_levels():
    assert wcag_level(7.5) == "AAA"
    assert wcag_level(4.6) == "AA"
    assert wcag_level(3.1) == "fail"
    assert wcag_level(3.1, large_text=True) == "AA"
    assert wcag_level(2.9, large_text=True) == "fail"


def test_large_text_thresholds():
    # WCAG large text: 18pt regular (24sp) or 14pt bold (18.66sp)
    assert is_large_text(24) is True
    assert is_large_text(23.9) is False
    assert is_large_text(19, bold=True) is True
    assert is_large_text(18, bold=True) is False


def test_delta_e_orders_similar_before_different():
    base = parse_hex("#6750A4")
    near = parse_hex("#6750A5")
    far = parse_hex("#00FF00")
    assert delta_e(base, base) == pytest.approx(0.0)
    assert delta_e(base, near) < 2.0 < delta_e(base, far)
