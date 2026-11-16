"""Audit one screen across light/dark and 1.0/2.0 font scale.

    python examples/dark_mode_matrix.py
"""

import json
from pathlib import Path

from droidcode.audit import compare_reports, run_matrix, summarise
from droidcode.device.mock import MockDevice, load_scenario
from droidcode.tokens import DesignTokens

ROOT = Path(__file__).resolve().parents[1]
BASE = load_scenario(ROOT / "evals" / "tasks" / "checkout_low_contrast.json")

CONFIGS = [
    {"name": "light-1.0", "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440}},
    {"name": "dark-1.0", "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440, "dark": True}},
    {"name": "light-2.0", "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440, "font_scale": 2.0}},
]


def main() -> None:
    tokens = DesignTokens.load(ROOT / "evals" / "tokens.json")
    devices = [MockDevice({**BASE, **config}) for config in CONFIGS]
    reports = run_matrix(devices, tokens=tokens)
    print(json.dumps(summarise(reports), indent=2))
    print(json.dumps(compare_reports(reports), indent=2))


if __name__ == "__main__":
    main()
