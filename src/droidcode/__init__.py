"""droidcode - an agentic coding harness for Android phone UI/UX design and testing.

The package is organised the way jcode organises its crates: one module per
concern, with a hard dependency edge from `protocol` outward and no cycles.

    protocol   shared value types (device spec, UI nodes, findings)
    uitree     view-hierarchy parsing and querying
    device/    backends: mock (deterministic, CI) and adb (real hardware)
    checks/    pure UI/UX rules: contrast, targets, tokens, spacing, text
    vision     screenshot capture, colour sampling, region diffing
    perf       frame-statistics parsing (jank, percentiles)
    audit      composes checks over a device x configuration matrix
    registry   tool registry, JSON schemas, risk + permission gating
    session    transcript, context budget, turn loop
    daemon     long-lived server exposing the tool surface over a socket
    client     SDK client for the daemon
    cli        `droidcode` entry point
"""

__version__ = "0.1.0"
