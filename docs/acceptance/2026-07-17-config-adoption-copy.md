# Exact-fingerprint configuration-adoption copy acceptance — 2026-07-17

## Scope

This record covers loading and reviewing one unmanaged live-configuration
fingerprint, explicit confirmation, guarded progress, classified rejection,
successful desired-state evidence, unexpected read-only planning failure, and
an unknown post-confirmation result.

## Accepted behavior

- Dashboard and diagnostics entry paths pass the same validated interface copy
  catalog into the existing `ConfigAdopter.plan/adopt` workflow.
- Loading, exact-fingerprint review, confirmation, non-returning progress,
  typed rejection, terminal evidence, and unknown-result recovery render from
  the catalog with exact template placeholder validation.
- SHA-256 fingerprints, committed revisions, and typed diagnostics remain
  literal evidence with markup disabled.
- Adoption never imports profiles or changes the live configuration. A
  classified rejection states that this workflow made no change.
- An unexpected planning failure hides the exception and states that no
  replacement precondition was recorded. An unexpected confirmed failure hides
  the exception, treats the desired-state result as unknown, and requires fresh
  live-configuration-identity inspection before retry.
- While confirmation is running, the action is disabled and return navigation
  is unavailable. Success exposes an explicit return action that clears stale
  workflow screens and recomposes the dashboard.

## Evidence

- Focused application and Textual Pilot journey tests: `68 passed`.
- Full test suite: `611 passed, 18 skipped` in `172.95s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `259 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 161 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `b34f92d33aa82a238954169625253d14325f1fcf32dafa179bdcf92614e1bcc0`.
- The configuration-adoption screen implementation contains no locale-authored
  text.
