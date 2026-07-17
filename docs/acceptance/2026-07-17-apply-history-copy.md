# Apply-history presentation and recovery acceptance — 2026-07-17

## Scope

This record covers the bounded read-only Apply History screen opened from
either Diagnostics Center or Operations, including every typed outcome,
unknown-result evidence, empty, typed unavailable, missing-detail,
unexpected-failure, initial-load, and explicit-refresh states. Durable recording
and classification stay behind the existing `ApplyHistoryReader` interface.

## Accepted behavior

- One injected interface copy catalog flows through both navigation entries and
  owns the title, exact read-only retention disclosure, all eight typed outcome
  labels, entry templates, unknown-result warning, empty state, typed
  unavailable wrapper, missing-detail fallback, initial/repeated loading states,
  generic failure recovery, and refresh label.
- Application report conclusions, UTC timestamps, candidate SHA-256 values,
  active-profile counts, bounded redacted diagnostics, and redaction counts
  render literally in markup-disabled widgets. Bracketed evidence cannot become
  styling or select behavior.
- `in-progress` remains an explicit unknown host result that tells the operator
  to inspect host state. The screen never infers success from desired state or
  offers an apply retry.
- Empty and unavailable remain distinct typed states. Empty history never
  becomes a blank page; unavailable history preserves already-sanitized
  application diagnostics or uses the catalog fallback when none exists.
- An exception raised before a typed report is discarded and never rendered;
  generic recovery keeps an explicit read-only retry enabled.
- Initial loading and explicit refresh run through the existing exclusive
  worker, request the configured newest-entry bound, and keep refresh disabled
  until a terminal report or generic failure is shown.
- The screen still performs no persistence, apply attempt, subprocess call,
  state inference, export, or privileged-helper call. No new application or
  system seam was introduced.
- The Apply History screen contains no locale-authored Han text.

## Evidence

- Focused application, adapter-contract, and Textual Pilot tests: `53 passed`
  in `29.24s`.
- Full test suite: `643 passed, 18 skipped` in `199.57s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `262 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 164 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `acb77bdcaa4a16ca2c563361b75c8ec4f0e237d33cefe091793a80af059970a4`.
