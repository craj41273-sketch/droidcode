"""Score the harness against task fixtures.

Each task is a scenario plus the findings a correct harness must produce. The
score is F1 over (rule_id, node_id) pairs, which punishes both misses and
noise - the failure mode that makes a UI reviewer useless.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..audit import Auditor
from ..device.mock import MockDevice, load_scenario
from ..tokens import DesignTokens


@dataclass
class TaskResult:
    task_id: str
    expected: list[tuple[str, str]]
    found: list[tuple[str, str]]
    missing: list[tuple[str, str]] = field(default_factory=list)
    extra: list[tuple[str, str]] = field(default_factory=list)

    @property
    def precision(self) -> float:
        if not self.found:
            return 1.0
        return len(set(self.found) & set(self.expected)) / len(set(self.found))

    @property
    def recall(self) -> float:
        if not self.expected:
            return 1.0
        return len(set(self.found) & set(self.expected)) / len(set(self.expected))

    @property
    def f1(self) -> float:
        precision, recall = self.precision, self.recall
        return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

    def to_dict(self) -> dict:
        return {
            "task": self.task_id,
            "expected": [f"{r}::{n}" for r, n in self.expected],
            "found": [f"{r}::{n}" for r, n in self.found],
            "missing": [f"{r}::{n}" for r, n in self.missing],
            "extra": [f"{r}::{n}" for r, n in self.extra],
            "precision": round(self.precision, 3),
            "recall": round(self.recall, 3),
            "f1": round(self.f1, 3),
        }


def run_task(task: dict, tokens: DesignTokens) -> TaskResult:
    """Run one task. Only `grade` rules are scored.

    A task grades the rules it is about, the way a test asserts the behaviour it
    covers; findings from other rules are reported but not counted. Without that
    separation every new heuristic would retroactively "break" old tasks.
    """
    scenario = task.get("scenario")
    if scenario is None and task.get("scenario_file"):
        scenario = load_scenario(Path(task["scenario_file"]))
    device = MockDevice(load_scenario(scenario))
    report = Auditor(device, tokens=tokens, package=task.get("package", "")).run()
    expected = [(item["rule_id"], item.get("node_id", "")) for item in task.get("expect", [])]
    graded = set(task.get("grade") or [rule for rule, _ in expected])
    found = [(finding.rule_id, finding.node_id) for finding in report.findings if finding.rule_id in graded]
    return TaskResult(
        task_id=task["id"],
        expected=expected,
        found=found,
        missing=sorted(set(expected) - set(found)),
        extra=sorted(set(found) - set(expected)),
    )


def run_evals(directory: Path, tokens_path: str | None = None) -> dict:
    tokens = DesignTokens.load(tokens_path) if tokens_path else DesignTokens()
    results = []
    for path in sorted(Path(directory).glob("*.json")):
        results.append(run_task(json.loads(path.read_text()), tokens))
    passed = sum(1 for result in results if not result.missing and not result.extra)
    return {
        "tasks": len(results),
        "passed": passed,
        "mean_f1": round(sum(r.f1 for r in results) / len(results), 3) if results else 0.0,
        "results": [r.to_dict() for r in results],
    }
