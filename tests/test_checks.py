from droidcode.checks.contrast import check_contrast
from droidcode.checks.layout import (
    check_missing_label,
    check_spacing_grid,
    check_text_overflow,
    check_touch_target,
)
from droidcode.checks.tokens import check_token_drift
from droidcode.color import parse_hex
from droidcode.protocol import Bounds, DeviceSpec, UiNode

SPEC = DeviceSpec(width_px=1080, height_px=2400, density_dpi=440)  # 1dp == 2.75px


def node(node_id: str, bounds, **kwargs) -> UiNode:
    return UiNode(node_id=node_id, bounds=Bounds.from_list(bounds), **kwargs)


def test_touch_target_flags_small_clickables():
    small = node("btn", [0, 0, 100, 100], clickable=True)   # 36x36dp
    big = node("ok", [0, 0, 132, 132], clickable=True)      # 48x48dp
    findings = check_touch_target([small, big], SPEC)
    assert [f.node_id for f in findings] == ["btn"]
    assert findings[0].evidence["width_dp"] == 36.4
    assert findings[0].severity == "serious"


def test_touch_target_threshold_is_configurable():
    node_40dp = node("btn", [0, 0, 110, 110], clickable=True)
    assert check_touch_target([node_40dp], SPEC, min_dp=48) != []
    assert check_touch_target([node_40dp], SPEC, min_dp=40) == []


def test_missing_label_only_hits_unlabelled_nodes():
    unlabelled = node("icon", [0, 0, 100, 100], clickable=True, class_name="ImageButton")
    described = node("ok", [0, 0, 100, 100], clickable=True, content_desc="Back")
    findings = check_missing_label([unlabelled, described])
    assert [f.node_id for f in findings] == ["icon"]
    assert findings[0].severity == "critical"


def test_spacing_grid_flags_off_grid_gaps():
    parent = UiNode(node_id="root", children=[
        node("a", [0, 0, 100, 100]),
        node("b", [0, 103, 100, 200]),   # 3px gap == 1.1dp, off a 4dp grid
    ])
    findings = check_spacing_grid(parent, SPEC, grid_dp=4)
    assert len(findings) == 1
    assert findings[0].node_id == "b"


def test_spacing_grid_accepts_on_grid_gaps():
    parent = UiNode(node_id="root", children=[
        node("a", [0, 0, 100, 100]),
        node("b", [0, 111, 100, 200]),   # 11px gap == 4dp
    ])
    assert check_spacing_grid(parent, SPEC, grid_dp=4) == []


def test_text_overflow_estimates_against_box_width():
    wide = node("wide", [0, 0, 1000, 100], text="Short", attrs={"text_size_dp": 16})
    narrow = node("narrow", [0, 0, 100, 100], text="A very long label indeed", attrs={"text_size_dp": 16})
    findings = check_text_overflow([wide, narrow], SPEC)
    assert [f.node_id for f in findings] == ["narrow"]
    assert findings[0].confidence < 1.0


def test_text_overflow_respects_font_scale():
    scaled = DeviceSpec(width_px=1080, height_px=2400, density_dpi=440, font_scale=2.0)
    label = node("label", [0, 0, 600, 100], text="Settings and privacy", attrs={"text_size_dp": 16})
    assert check_text_overflow([label], SPEC) == []
    assert check_text_overflow([label], scaled) != []


def test_contrast_flags_low_ratio_text():
    pale = node("pale", [0, 0, 100, 100], text="Pay now", attrs={"text_size_dp": 16})
    colors = {"pale": (parse_hex("#FFFFFF"), parse_hex("#EEEEEE"))}
    findings = check_contrast([pale], colors)
    assert len(findings) == 1
    assert findings[0].rule_id == "ux.contrast.text"
    assert findings[0].evidence["required"] == 4.5


def test_contrast_uses_large_text_threshold():
    big = node("big", [0, 0, 100, 100], text="Title", attrs={"text_size_dp": 28})
    colors = {"big": (parse_hex("#FFFFFF"), parse_hex("#A0A0A0"))}  # ~2.6:1
    findings = check_contrast([big], colors)
    assert findings[0].evidence["large_text"] is True
    assert findings[0].evidence["required"] == 3.0


def test_contrast_passes_when_ratio_is_sufficient():
    dark = node("dark", [0, 0, 100, 100], text="Body", attrs={"text_size_dp": 16})
    assert check_contrast([dark], {"dark": (parse_hex("#FFFFFF"), parse_hex("#1C1B1F"))}) == []


def test_token_drift_flags_off_theme_colour(tokens):
    off = node("btn", [0, 0, 100, 100], text="Go")
    on = node("ok", [0, 0, 100, 100], text="Go")
    colors = {
        "btn": (parse_hex("#FFFFFF"), parse_hex("#FF00AA")),
        "ok": (parse_hex("#FFFFFF"), parse_hex("#1C1B1F")),
    }
    findings = check_token_drift([off, on], colors, tokens)
    assert [f.node_id for f in findings] == ["btn"]
    assert findings[0].evidence["role"] == "foreground"


def test_token_drift_is_silent_without_tokens():
    from droidcode.tokens import DesignTokens

    off = node("btn", [0, 0, 100, 100], text="Go")
    assert check_token_drift([off], {"btn": ((255, 255, 255), (255, 0, 170))}, DesignTokens()) == []
