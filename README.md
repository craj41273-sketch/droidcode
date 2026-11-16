# droidcode

**An agentic coding harness for Android phone UI/UX design and testing.**

droidcode gives a coding agent eyes and hands on an Android screen: it can read
the view hierarchy, tap and type, capture and diff frames, run a deterministic
UX rule set (contrast, touch targets, labels, spacing, text fit, design tokens,
jank), and report findings an agent can act on. It is built the way
[jcode](https://github.com/1jehuang/jcode) is built - a daemon, a schema-first
tool surface, a session loop with a context budget, and evals - but pointed at
Android UI instead of a terminal.

```
$ droidcode audit --scenario evals/tasks/checkout_low_contrast.json --tokens evals/tokens.json
# UX audit - checkout

- Nodes inspected: 4
- Findings: 6 serious 2, moderate 1, minor 3

| Severity | Rule | Node | Message | Fix |
|---|---|---|---|---|
| serious | `ux.contrast.text` | `btn_pay` | Text 'Pay now' has 1.16:1 contrast... | Darken the text or lighten the surface |
| serious | `ux.target.min_size` | `btn_cancel` | Touch target 'Cancel' is 29x15dp... | Increase the tappable area |
```

## Install

```bash
pip install -e ".[dev]"     # Python 3.11+, Pillow
pytest                      # 89 tests, no device required
```

## Quickstart

```bash
# 1. what can the agent do?
droidcode tools

# 2. audit a screen (mock device, no emulator needed)
droidcode audit --scenario evals/tasks/checkout_low_contrast.json --tokens evals/tokens.json

# 3. drive a real phone or emulator over adb
droidcode audit --adb --serial emulator-5554 --tokens evals/tokens.json --package com.example.app

# 4. run a goal through the turn loop
droidcode session --goal "check the checkout screen" --scenario evals/tasks/checkout_low_contrast.json

# 5. serve the harness once, drive it from anything
droidcode daemon --socket /tmp/droidcode.sock
python -c "from droidcode.client import DaemonClient; print(DaemonClient('/tmp/droidcode.sock').audit()['by_severity'])"

# 6. score the harness itself
droidcode eval --dir evals/tasks --tokens evals/tokens.json
```

## Web surface

`webapp/` wraps the harness in a small FastAPI service - three JSON endpoints and
one server-rendered report page - sized for a free hosting tier. It ships a
`render.yaml` blueprint; see `docs/DEPLOY.md`.

```bash
pip install -r requirements.txt && pip install -e .
uvicorn webapp.app:app --port 8000    # http://localhost:8000
```

## How it fits together

```
device/  mock (deterministic, CI)   adb (hardware/emulator)
            \                        /
             \                      /
protocol -> uitree -> vision -> checks -> audit -> registry -> session
                                                          \-> daemon -> client
```

| Module | Responsibility |
|---|---|
| `protocol` | Device spec, bounds, UI nodes, findings. All JSON. |
| `uitree` | Parse `uiautomator dump` XML; find, filter, flatten. |
| `vision` | Screenshot colour sampling and region diffing. |
| `checks` | Pure rules: contrast, targets, labels, spacing, text fit, tokens. |
| `perf` | `dumpsys gfxinfo` -> jank %, p50/p90/p99. |
| `audit` | Compose checks over a device x configuration matrix. |
| `registry` | Tool schemas, risk classes, permission gating. |
| `session` | Transcript, context budget, model-agnostic turn loop. |
| `daemon` / `client` | Unix-socket JSON-lines server and SDK client. |
| `webapp` | FastAPI service: JSON API plus a server-rendered report page. |
| `evals` | Task fixtures with known-good findings, scored by F1. |

## Design commitments

1. **Colour comes from pixels, not from the hierarchy.** Android does not
   expose rendered colour, so contrast is measured from the frame - which also
   catches tinted, themed and canvas-drawn UI.
2. **The device is a protocol.** Every rule runs against `DeviceBackend`, so CI
   runs the identical checks with no emulator, no flake and no GPU.
3. **Rules are pure functions.** `(nodes, spec, tokens) -> findings`. No I/O,
   no clock, no network: trivially testable, deterministic, diffable.
4. **Risk-tagged tools, default-deny.** Reading is auto-approved; tapping,
   typing and file writes need an explicit grant.
5. **Measure the harness, not just the app.** `evals/` scores the rule set with
   F1, including a false-positive control task.

See `docs/ARCHITECTURE.md`, `docs/RULES.md`, `docs/TOOLS.md`, `docs/EVALS.md`
and `docs/ROADMAP.md`.
