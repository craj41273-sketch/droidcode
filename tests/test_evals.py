from pathlib import Path

from droidcode.evals.runner import run_evals, run_task
from droidcode.tokens import DesignTokens

ROOT = Path(__file__).resolve().parents[1]


def test_repository_eval_suite_passes():
    result = run_evals(ROOT / "evals" / "tasks", str(ROOT / "evals" / "tokens.json"))
    assert result["tasks"] == 3
    assert result["passed"] == result["tasks"]
    assert result["mean_f1"] == 1.0


def test_task_scores_missing_and_extra_findings():
    task = {
        "id": "deliberately-wrong",
        "grade": ["ux.contrast.text"],
        "scenario": {
            "name": "x",
            "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
            "widgets": [
                {"id": "ok", "text": "Readable", "bounds": [40, 400, 1040, 532], "bg": "#FFFFFF", "fg": "#1C1B1F"},
            ],
        },
        "expect": [{"rule_id": "ux.contrast.text", "node_id": "ghost"}],
    }
    result = run_task(task, DesignTokens.load(ROOT / "evals" / "tokens.json"))
    assert result.missing == [("ux.contrast.text", "ghost")]
    assert result.recall == 0.0
    assert result.precision == 1.0
    assert result.f1 == 0.0


def test_ungraded_rules_do_not_affect_the_score():
    task = {
        "id": "graded-subset",
        "grade": ["a11y.label.missing"],
        "scenario": {
            "name": "y",
            "spec": {"width_px": 1080, "height_px": 2400, "density_dpi": 440},
            "widgets": [
                {"id": "pale", "text": "Pay", "bounds": [40, 400, 1040, 532], "bg": "#FFFFFF", "fg": "#EEEEEE"},
            ],
        },
        "expect": [],
    }
    result = run_task(task, DesignTokens.load(ROOT / "evals" / "tokens.json"))
    assert result.found == []      # the contrast finding exists but is not graded
    assert result.f1 == 1.0
