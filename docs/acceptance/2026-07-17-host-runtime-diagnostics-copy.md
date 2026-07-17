# Host runtime diagnostics copy acceptance — 2026-07-17

## Scope

This record covers the read-only host-runtime drill-down available when the
complete diagnostics center is not composed, including healthy and unhealthy
observations, missing diagnostics, recovery guidance, and return navigation.

## Accepted behavior

- The dashboard continues to load the injected `HostDiagnostics` seam in a
  worker and enables drill-down only after a typed report exists.
- One injected interface copy catalog renders the page title, typed
  healthy/unhealthy summary, missing-detail fallback, recovery heading, empty
  recovery state, and numbered-step template.
- Runtime diagnostics and adapter-provided recovery instructions remain literal
  evidence with markup disabled.
- Healthy evidence shows no recovery heading or steps. Unhealthy evidence keeps
  every provided recovery instruction in order.
- `Esc` returns to the existing dashboard context without triggering a probe,
  mutation, or dashboard-stack rebuild.
- The root application imports one `HostDiagnosticsScreen`; all presentation
  policy stays in the dedicated host-diagnostics module. Neither module contains
  locale-authored Han text.

## Evidence

- Focused Textual journey: `55 passed` in `58.28s`.
- Full test suite: `621 passed, 18 skipped` in `182.51s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `261 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 163 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `75cb38b8c18abbdb1924fc3a69e584bc05038ff2160b12fd064c7054539cae74`.
- The root application and host-diagnostics module contain no locale-authored
  Han text.
