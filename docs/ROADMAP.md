# Roadmap

## v0.1 - the vertical slice (this repository)

- [x] Device seam: deterministic mock + adb backend
- [x] Seven rules with evidence, severity and suggested fixes
- [x] Audit pipeline, configuration matrix, config-specific diffing
- [x] Tool registry with schemas, risk classes, permission gating
- [x] Session loop with transcript and context budget
- [x] Daemon + SDK client over a unix socket
- [x] Eval suite with a false-positive control
- [x] 89 tests, no device required

## v0.2 - the design side

- [ ] **Compose semantics dump** - read `text_size`, `font_weight`,
  `corner_radius` and `semantics` labels from a debug build, so typography and
  shape rules become exact instead of estimated.
- [ ] **Token ingestion** - parse a Compose `Theme.kt` / Style Dictionary build
  into `DesignTokens` instead of hand-written JSON.
- [ ] **Screenshot-test integration** - drive Paparazzi/Roborazzi to render
  every `@Preview` headlessly, and audit them without an emulator.
- [ ] **Layout rules** - alignment, optical margin, baseline consistency,
  elevation/shadow ladder, one-primary-action-per-screen.

## v0.3 - the agent

- [ ] **Provider adapter** - an Anthropic/OpenAI `Model` implementation with
  prompt caching, so the loop drives a real model.
- [ ] **Fix-and-verify loop** - agent edits Compose source, rebuilds, re-audits
  the same screen, and proves the finding is gone and no new one appeared.
- [ ] **Patch tools** - `repo.apply_patch`, `gradle.assemble`, `gradle.lint`,
  gated as writes.
- [ ] **Context compaction** - screenshots are large; summarise old turns and
  keep the finding set, not the pixels.

## v0.4 - scale

- [ ] **Swarms** - one agent per screen, a coordinator that owns the design
  system, conflict notices when two agents touch the same theme file.
- [ ] **Device farm** - pool emulators across densities and API levels, queue
  audits, reuse warm boots.
- [ ] **CI gate** - `droidcode audit --fail-on serious` as a required check,
  with the report posted to the pull request.
- [ ] **Baseline mode** - accept existing findings, fail only on new ones, so a
  legacy app can adopt the harness without a 400-item backlog.

## Explicitly not planned

- Golden-image pixel tests as the primary signal. They encode one device, one
  font renderer, one OS build; they break constantly and teach nothing about
  the user's experience. Region diffing stays a tool, not a gate.
- A hosted service. The harness is a library and a daemon; where it runs is the
  team's business.
