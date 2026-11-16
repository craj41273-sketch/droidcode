import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from droidcode.tokens import DesignTokens  # noqa: E402

TOKENS_PATH = ROOT / "evals" / "tokens.json"


@pytest.fixture
def tokens() -> DesignTokens:
    return DesignTokens.load(TOKENS_PATH)


@pytest.fixture
def good_scenario() -> dict:
    """A screen with no defects: used as the false-positive control."""
    return {
        "name": "good",
        "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
        "background": "#FFFFFF",
        "widgets": [
            {
                "id": "title",
                "class_name": "android.widget.TextView",
                "text": "Profile",
                "bounds": [40, 200, 600, 290],
                "bg": "#FFFFFF",
                "fg": "#1C1B1F",
                "text_size_dp": 24,
            },
            {
                "id": "btn_save",
                "class_name": "android.widget.Button",
                "text": "Save",
                "bounds": [40, 1797, 1040, 1929],
                "bg": "#6750A4",
                "fg": "#FFFFFF",
                "text_size_dp": 16,
                "clickable": True,
            },
        ],
    }
