# Architecture

## The problem

An Android UI has no compiler error. "This button is hard to read" is a
judgement, made late, by a human, on one device. An agent that writes Android UI
needs three things a general coding agent does not have: a way to *see* a
rendered screen, a way to *act* on it, and a way to *judge* it deterministically
enough to know whether its fix worked.

droidcode supplies those three, and nothing else.

## Layers

```
protocol        value types, no dependencies
  |
uitree   vision   color   perf        parsing and measurement, pure
  |        |        |       |
checks/*        tokens                rules: (nodes, spec, tokens) -> findings
  |               |
audit           device/{base,mock,adb}
  |               |
registry (tool schemas, risk, permissions)
  |
session (turn loop, transcript, budget)     harness (owns device + registry)
  |                                             |
daemon -> client                               cli
```

Dependencies point downward only. `protocol`, `color`, `uitree`, `vision`,
`perf` and `checks` never import `device`, `audit`, `registry` or `session`.
That is what lets the rule set be tested without a device, and what keeps the
mock backend honest: if a check needed a real phone, it could not be pure.

## The device seam

`DeviceBackend` is the whole contract: `screenshot()`, `dump_tree()`, `tap()`,
`swipe()`, `type_text()`, `shell()`. Two implementations:

- **`MockDevice`** renders a scenario JSON (widgets with bounds, colours, text)
  into a real PIL image and a real `uiautomator` XML hierarchy. Deterministic,
  instant, no GPU. Scenarios are also the eval fixtures - the same artefact
  proves the harness works and grades it.
- **`AdbDevice`** drives a phone or emulator through `adb`. Not exercised in
  CI; command construction is tested with a recording stub instead.

Because the mock produces genuine pixels, colour sampling, contrast maths and
image diffing are exercised for real in CI, not stubbed out.

## Why colour is sampled, not read

Android does not expose the rendered colour of a view. `UiAutomator` gives you
bounds and text; theme attributes, tints, ripples, elevation overlays, disabled
alphas and Compose `Canvas` drawing all change what the user actually sees. So
`vision.estimate_colors` takes the modal colour inside a node's box as the
background and the most frequent clearly-different colour as the ink. That is
how a design reviewer looks at a screenshot, and it stays correct when the
theme changes under you.

## Findings are the unit of work

A `Finding` is `(rule_id, severity, category, node_id, device_key, evidence,
suggestion, confidence)`. It serialises to JSON, renders to Markdown, dedupes on
`(rule_id, node_id)`, and sorts by severity. Everything upstream of the agent -
the CLI, the daemon, the eval scorer, a CI gate - consumes findings and nothing
else, so a new rule needs no new plumbing.

## The matrix

One screen is not a UI. `audit.run_matrix` runs the same rule set across
configurations - small/large, light/dark, LTR/RTL, font scale 1.0/2.0 - and
`compare_reports` surfaces findings that appear in *some* configurations only.
That comparison is the difference between a bug list and a verdict: a rule that
fires only at font scale 2.0 is a scaling defect, not a design opinion.

## The harness and the daemon

`Harness` owns one device, one registry and the sessions that use them. The CLI
constructs a harness per invocation; the daemon constructs one and keeps it
alive so an editor plugin, a CI job and an agent can share a warm emulator. The
wire protocol is newline-delimited JSON over a unix socket: `ping`,
`tools.list`, `tool.call`, `audit.run`, `session.create`, `session.run`,
`session.get`. A bad request returns an error and never kills the daemon.

## Deliberate non-goals (v0.1)

- No model provider. `Model` is a protocol; `ScriptedModel` and
  `AuditFirstModel` make the loop testable today, and a provider plugs in
  without touching the tool layer.
- No parallel swarms. One session at a time per harness; the daemon can serve
  many clients, but agent-to-agent messaging is out of scope until the single
  agent is measurably good.
- No pixel-perfect golden images. Region diffing is available as a tool; a
  golden-image suite is a project decision, not a harness default.
