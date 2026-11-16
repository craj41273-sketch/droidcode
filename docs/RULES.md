# Rule catalogue

Every rule is a pure function returning `Finding` objects. `severity` follows
the impact on a user, not on the diff: a control a screen reader cannot name is
`critical`, an off-grid gap is `minor`.

| Rule id | Severity | Category | What it catches | Confidence |
|---|---|---|---|---|
| `a11y.label.missing` | critical | accessibility | Clickable node with no text and no content description | 1.0 |
| `ux.contrast.text` | serious / moderate | accessibility | Text below WCAG AA (4.5:1, or 3:1 for large text) against its measured background | 1.0 |
| `ux.target.min_size` | serious | accessibility | Clickable area under 48dp in either dimension | 1.0 |
| `ux.text.overflow` | moderate | visual | Label whose estimated rendered width exceeds its box at the current font scale | 0.6 |
| `ux.spacing.grid` | minor | visual | Vertical gap between siblings off the 4dp spacing grid | 0.7 |
| `design.token.drift` | minor | design-system | Rendered colour further than dE 3.0 from every theme token | 0.8 |
| `perf.jank.budget` | serious | performance | Over 5% janky frames in `dumpsys gfxinfo` | 1.0 |

## Thresholds and where they come from

- **Contrast** - WCAG 2.2 relative luminance; large text is >= 24sp regular or
  >= 18.66sp bold (18pt / 14pt bold). Measured on rendered pixels.
- **Touch target** - 48dp, Material Design 3 `minimumInteractiveComponentSize`.
  Overridable per project through `tokens.touch_target_dp`.
- **Spacing** - 4dp grid by default (`tokens.grid_dp`), 8dp is a common
  alternative; tolerance 0.5dp.
- **Colour drift** - CIE76 delta-E with tolerance 3.0 (a just-noticeable
  difference is ~2.3), against `tokens.colors`.
- **Jank** - 5% janky frames, the budget Google uses for "smooth" scrolling at
  60Hz; frame budget 16.7ms.

## Adding a rule

1. Write it in `checks/` as `check_<thing>(nodes, spec, tokens) -> list[Finding]`.
2. Test the positive case, the negative case, and the boundary.
3. Add a row here, with an honest confidence.
4. Add an eval task that grades it, and check the whole suite still scores 1.0.
