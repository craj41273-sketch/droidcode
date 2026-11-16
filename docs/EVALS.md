# Evals

A UI reviewer that finds everything is as useless as one that finds nothing.
The eval suite exists to measure both directions.

## Task shape

```json
{
  "id": "checkout_low_contrast",
  "goal": "Find the accessibility and target-size defects on the checkout screen",
  "grade": ["ux.contrast.text", "ux.target.min_size"],
  "scenario": { "name": "checkout", "widgets": [ ... ] },
  "expect": [
    {"rule_id": "ux.contrast.text", "node_id": "btn_pay"},
    {"rule_id": "ux.target.min_size", "node_id": "btn_cancel"}
  ]
}
```

- **`grade`** limits scoring to the rules the task is about, the way a unit test
  asserts only the behaviour it covers. Without it, every new heuristic would
  retroactively "break" every old task.
- **`scenario`** is a `MockDevice` screen - the same fixture the mock renders,
  so a task cannot drift from the harness it grades.
- **`expect`** is the ground truth: `(rule_id, node_id)` pairs.

## Scoring

Precision, recall and F1 over `(rule_id, node_id)`. A task passes only when
nothing is missing *and* nothing extra was reported within the graded rules.

```
$ droidcode eval --dir evals/tasks --tokens evals/tokens.json
{"tasks": 3, "passed": 3, "mean_f1": 1.0, ...}
```

## The three tasks shipped today

| Task | Grades | Why it exists |
|---|---|---|
| `checkout_low_contrast` | contrast, target size | The classic: pale text and a thumb-sized miss |
| `settings_unlabelled_icon` | missing label | Screen-reader blocker with no visual symptom |
| `clean_profile_screen` | all six rules | **False-positive control**: a good screen must score zero findings |

The clean-screen task is the important one. It is what stops a rule from being
"improved" into noise.

## Growing the suite

Add tasks that encode real bugs found in real apps, one per failure mode:
dark-mode-only contrast failures, RTL mirroring, font scale 2.0 truncation,
edge-to-edge insets, keyboard-overlap, and Compose `Canvas` text. A rule without
a task is a guess; a task without a rule is a bug report.
