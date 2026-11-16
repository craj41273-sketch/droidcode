# Repository guidelines

Instructions for coding agents working in this repository. Humans: the same
rules apply.

## Scope

- One package, one responsibility. If a module needs a second reason to change,
  it becomes a new module under `src/droidcode/`.
- `checks/` must stay pure: no I/O, no clock, no network, no device handle.
  A rule that needs the device belongs in `audit.py`.
- The daemon and the CLI must not grow behaviour of their own. Both call
  `Harness`; anything else is drift.

## Style

- Types on every public function. Dataclasses for values, protocols for seams.
- Findings are data: `rule_id`, `severity`, `evidence`, `suggestion`. Never
  raise for a UX defect - return a finding.
- No new runtime dependency without a note in `docs/ARCHITECTURE.md` explaining
  what it buys. Pillow is the only one today.

## Working on rules

- Every new rule needs: an entry in `docs/RULES.md`, unit tests with a positive
  and a negative case, and an eval task that grades it.
- Prefer a conservative rule with `confidence < 1.0` over a rule that cries
  wolf. A noisy reviewer gets switched off.
- Thresholds come from `DesignTokens` or a documented constant, never a magic
  number inside a comparison.

## Verifying a change

```bash
pytest                      # unit + integration, no device needed
droidcode eval --dir evals/tasks --tokens evals/tokens.json
```

`pytest` alone does not prove a rule is useful; the eval suite is what tells you
whether a rule fires on the screens it should and stays quiet on the ones it
should not.

## Device work

- Mock first: reproduce any device-specific bug in `MockDevice` (a scenario
  JSON) before touching `AdbDevice`. If you cannot reproduce it in a scenario,
  you do not yet understand the bug.
- Never let a test require an emulator. Emulator-only checks belong in the
  `android-emulator` CI job, and must be skippable.
