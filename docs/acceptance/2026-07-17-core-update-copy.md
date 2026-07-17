# Core-update copy and result-boundary acceptance — 2026-07-17

## Scope

This record covers the exact-version core-update entry, form validation,
semantic prerelease warning, immutable review plan, confirmed progress,
activation evidence, pre-activation acquisition failure, unexpected planning
failure, and unknown privileged activation result.

## Accepted behavior

- Operations, host-readiness, and diagnostic actions pass the same validated
  interface copy catalog into the existing core-update workflow.
- The application plan returns `CoreUpdateWarning` identities and contains no
  locale-authored warning text.
- Invalid exact-version input and missing prerelease consent render actionable
  catalog guidance instead of raw lower-level exception messages.
- Form, plan, warning, progress, result, planning-failure, acquisition-failure,
  and unknown-result text comes from the validated catalog with exact template
  placeholder checks.
- Version, architecture, asset name, source, filesystem paths, activation
  targets, and typed diagnostics remain literal evidence with markup disabled.
- An unexpected planning failure performs no download or activation and hides
  the exception. An unexpected post-confirmation failure never claims success,
  hides the exception, and requires current-link, helper-log, and version
  inspection before any retry.

## Evidence

- Focused core-update and entry-path regression set: `37 passed`.
- Full local suite: `609 passed, 18 skipped`.
- Ruff formatting: `259 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 161 source files`.
- Git whitespace check: passed.
- Core-update application and screen files contain no locale-authored text.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `3955441e748340dbf9d96d3df78d655641466e91c1b0c1cf97924a3384905d51`.

The 18 skipped tests remain explicit opt-in external gates for live host,
distribution-container, and upstream artifact environments.
