from droidcode.perf import parse_gfxinfo

SAMPLE = """Applications Graphics Acceleration Info:
Total frames rendered: 1200
Janky frames: 96 (8.00%)
50th percentile: 4ms
90th percentile: 11ms
99th percentile: 27ms
Number Missed Vsync: 12
Number Slow UI thread: 30
"""


def test_parse_gfxinfo_extracts_every_field():
    stats = parse_gfxinfo(SAMPLE)
    assert stats.total_frames == 1200
    assert stats.janky_frames == 96
    assert stats.janky_percent == 8.0
    assert stats.percentiles_ms == {50: 4, 90: 11, 99: 27}
    assert stats.missed_vsync == 12
    assert stats.slow_ui_thread == 30
    assert stats.worst_percentile_ms == 27


def test_budget_check():
    assert parse_gfxinfo(SAMPLE).over_budget() is True
    calm = parse_gfxinfo("Total frames rendered: 500\nJanky frames: 5 (1.00%)")
    assert calm.over_budget() is False


def test_empty_input_is_safe():
    stats = parse_gfxinfo("")
    assert stats.total_frames == 0 and stats.worst_percentile_ms == 0


def test_to_dict_serialises_percentiles_as_strings():
    payload = parse_gfxinfo(SAMPLE).to_dict()
    assert payload["percentiles_ms"] == {"50": 4, "90": 11, "99": 27}
    assert payload["janky_percent"] == 8.0
