# Service-log presentation and recovery acceptance — 2026-07-17

## Scope

This record covers the bounded read-only Service Logs screen opened from either
Diagnostics Center or Operations, including available, empty, typed
unavailable, missing-detail, unexpected-failure, initial-load, and explicit
refresh states. Systemd/OpenRC capture and application disclosure behavior stay
behind the existing `ServiceLogReader` interface.

## Accepted behavior

- One injected interface copy catalog flows through both navigation entries and
  owns the title, exact read-only line-bound disclosure, source and redaction
  templates, empty state, typed unavailable wrapper, missing-detail fallback,
  initial/repeated loading states, generic failure recovery, and refresh label.
- Source labels, sanitized log lines, and typed diagnostics render literally in
  markup-disabled widgets. Bracketed evidence cannot become styling or select
  behavior.
- Available, empty, and unavailable remain distinct typed states. Empty results
  never become a blank page; unavailable results preserve already-redacted
  application diagnostics or use the catalog fallback when none exists.
- An exception raised before a typed report is discarded and never rendered;
  generic recovery keeps an explicit read-only retry enabled.
- Initial loading and explicit refresh run through the existing exclusive
  worker, request the configured bound, and keep the refresh action disabled
  until a terminal report or generic failure is shown.
- The screen still performs no subprocess parsing, secret discovery, service
  mutation, journal following, export, or privileged-helper call. No new
  application or system seam was introduced.
- The Service Logs screen contains no locale-authored Han text.

## Evidence

- Focused application, adapter-contract, and Textual Pilot tests: `22 passed`
  in `8.99s`.
- Full test suite: `634 passed, 18 skipped` in `192.95s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `262 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 164 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `7befa6c9fdcae132113171ce388fb275f727e2d4658234938cfead670dd12242`.
