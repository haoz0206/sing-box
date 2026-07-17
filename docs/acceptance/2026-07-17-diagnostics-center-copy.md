# Diagnostics-center presentation and recovery acceptance — 2026-07-17

## Scope

This record covers the read-only prioritized Diagnostics Center from initial
background inspection through healthy/actionable presentation, typed
navigation, explicit recheck, missing evidence, and an unexpected top-level
inspection failure. Service-log and apply-history drill-down pages remain
separate journeys.

## Accepted behavior

- One injected interface copy catalog owns the title, initial/recheck progress,
  healthy and actionable overall summaries, recommendation framing, healthy
  no-action fallback, every condition marker, item-title and next-step
  templates, missing-detail fallback, typed adoption label, refresh control,
  supported drill-down labels, and generic failure recovery.
- A fully healthy `DiagnosticsCenterReport` returns no presentation-ready
  recommendation. The Textual catalog renders the locale-specific no-action
  guidance while priority selection for actionable reports remains inside the
  application module.
- Report titles, summaries, diagnostics, and guidance remain literal evidence
  in markup-disabled widgets. Catalog templates cannot turn adapter evidence
  into navigation or severity policy.
- Initial inspection and explicit recheck execute in the existing worker seam;
  the refresh action remains disabled while either observation is in flight.
- An exception raised before a typed report is discarded, never rendered, and
  leaves an explicit read-only retry enabled.
- The recommended button still follows the typed highest-priority action and
  only appears when its existing destination capability is available. Opening
  it does not execute adoption or core activation.
- The diagnostics-center screen contains no locale-authored Han text. No new
  application or system seam was introduced.

## Evidence

- Focused application and Textual Pilot tests: `51 passed` in `12.39s`.
- Full test suite: `627 passed, 18 skipped` in `178.67s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `262 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 164 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `07d590865e8e0183995a96b72385203e2a1759874b2c0f819000ca4b13610675`.
