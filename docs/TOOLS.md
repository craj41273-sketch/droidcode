# Tool surface

Every tool declares a JSON schema, a risk class and a handler. The registry
validates arguments first, then the permission policy decides: `allow`,
`deny`, or `ask`. Reads are auto-approved; anything that drives the device or
writes files needs an explicit grant.

| Tool | Risk | Arguments | Returns |
|---|---|---|---|
| `ui.dump_tree` | read | - | Full view hierarchy as JSON |
| `ui.find` | read | `text` or `resource_id` | Node summary with bounds and tap centre |
| `ui.tap` | device | `text` / `resource_id`, or `x`,`y` | Coordinates tapped |
| `ui.type` | device | `text` | Echo of what was typed |
| `ui.swipe` | device | `direction` (up/down/left/right) | Direction swiped |
| `screen.capture` | read | `name` | Path to the saved PNG |
| `screen.diff` | read | `before`, `after` | Changed-pixel ratio and changed region |
| `design.audit` | read | `screenshots_dir` | Full audit report (findings, severity counts) |
| `perf.frames` | read | `package` | Jank %, p50/p90/p99, missed vsync |
| `design.tokens.nearest` | read | `hex` | Nearest token name and delta-E |

## Why risk classes

An agent that can tap can also tap "Pay", "Delete account", or a permission
dialog. Splitting risk from capability lets the harness say yes to *looking* and
ask before *acting*, without the agent needing to know which is which. A CI job
typically runs with `auto_approve_risk={"read"}` and a scripted session; an
interactive developer session grants `device` for the tools it needs.

## Adding a tool

```python
registry.register(
    Tool(
        name="gradle.screenshot_test",
        description="Run Roborazzi/Paparazzi screenshot tests for a module.",
        input_schema={"type": "object", "properties": {"module": {"type": "string"}}, "required": ["module"]},
        risk=RISK_DEVICE,
        handler=run_screenshot_tests,
    )
)
```

Handlers raise `ToolError` for expected failures; anything else is contained by
the registry and returned as an error result, never as a crash.
