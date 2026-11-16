"""Frame statistics: parse `dumpsys gfxinfo` into jank numbers an agent can act on."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_PERCENTILE = re.compile(r"(\d+)(?:st|nd|rd|th) percentile:\s*(\d+)ms")
_JANKY = re.compile(r"Janky frames:\s*(\d+)\s*\(([\d.]+)%\)")
_TOTAL = re.compile(r"Total frames rendered:\s*(\d+)")
_MISSED = re.compile(r"Number Missed Vsync:\s*(\d+)")
_SLOW_UI = re.compile(r"Number Slow UI thread:\s*(\d+)")

# Google's "device is janky" line sits near 5% janky frames for 60Hz scrolling.
JANK_BUDGET_PERCENT = 5.0
FRAME_BUDGET_MS_60HZ = 16.7


@dataclass
class FrameStats:
    total_frames: int = 0
    janky_frames: int = 0
    janky_percent: float = 0.0
    percentiles_ms: dict[int, int] = field(default_factory=dict)
    missed_vsync: int = 0
    slow_ui_thread: int = 0

    @property
    def worst_percentile_ms(self) -> int:
        return max(self.percentiles_ms.values(), default=0)

    def over_budget(self, budget_percent: float = JANK_BUDGET_PERCENT) -> bool:
        return self.janky_percent > budget_percent

    def to_dict(self) -> dict:
        return {
            "total_frames": self.total_frames,
            "janky_frames": self.janky_frames,
            "janky_percent": round(self.janky_percent, 2),
            "percentiles_ms": {str(k): v for k, v in sorted(self.percentiles_ms.items())},
            "missed_vsync": self.missed_vsync,
            "slow_ui_thread": self.slow_ui_thread,
        }


def parse_gfxinfo(text: str) -> FrameStats:
    stats = FrameStats()
    if match := _TOTAL.search(text):
        stats.total_frames = int(match.group(1))
    if match := _JANKY.search(text):
        stats.janky_frames = int(match.group(1))
        stats.janky_percent = float(match.group(2))
    for percentile, milliseconds in _PERCENTILE.findall(text):
        stats.percentiles_ms[int(percentile)] = int(milliseconds)
    if match := _MISSED.search(text):
        stats.missed_vsync = int(match.group(1))
    if match := _SLOW_UI.search(text):
        stats.slow_ui_thread = int(match.group(1))
    return stats
