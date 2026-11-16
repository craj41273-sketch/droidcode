"""Colour maths: WCAG contrast and CIELAB distance. No dependencies, all pure.

This module sits below both `checks` and `tokens`, so neither imports the other.
"""

from __future__ import annotations

Color = tuple[int, int, int]


def parse_hex(value: str) -> Color:
    raw = value.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) == 8:  # #AARRGGBB, as Android writes it
        raw = raw[2:]
    if len(raw) != 6:
        raise ValueError(f"not a colour: {value!r}")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def to_hex(color: Color) -> str:
    return "#{:02X}{:02X}{:02X}".format(*color)


def _linearise(channel: int) -> float:
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(color: Color) -> float:
    """WCAG 2.2 relative luminance."""
    red, green, blue = (_linearise(c) for c in color)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: Color, background: Color) -> float:
    """WCAG contrast ratio, 1.0 to 21.0."""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def wcag_level(ratio: float, large_text: bool = False) -> str:
    """'AAA', 'AA', 'AA-large', or 'fail' for the given ratio."""
    if large_text:
        if ratio >= 4.5:
            return "AAA"
        return "AA" if ratio >= 3.0 else "fail"
    if ratio >= 7.0:
        return "AAA"
    return "AA" if ratio >= 4.5 else "fail"


def is_large_text(text_size_sp: float, bold: bool = False) -> bool:
    """WCAG 'large text': >=18pt, or >=14pt bold. 1pt ~= 1.333sp."""
    if bold:
        return text_size_sp >= 14 * 4 / 3
    return text_size_sp >= 18 * 4 / 3


def rgb_to_lab(color: Color) -> tuple[float, float, float]:
    """sRGB -> CIE L*a*b* (D65), used for design-token distance."""
    red, green, blue = (_linearise(c) for c in color)
    x = (0.4124 * red + 0.3576 * green + 0.1805 * blue) / 0.95047
    y = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 1.00000
    z = (0.0193 * red + 0.1192 * green + 0.9505 * blue) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def delta_e(color_a: Color, color_b: Color) -> float:
    """CIE76 colour difference. ~2.3 is a just-noticeable difference."""
    lab_a = rgb_to_lab(color_a)
    lab_b = rgb_to_lab(color_b)
    return sum((a - b) ** 2 for a, b in zip(lab_a, lab_b)) ** 0.5
