# Desired-state recovery copy and result-boundary acceptance — 2026-07-17

## Scope

This record covers startup classification, exact primary/backup review,
confirmation, guarded progress, precondition rejection, durable success
evidence, read-only reinspection failure, and unknown post-confirmation state
recovery results.

## Accepted behavior

- Recoverable, unsupported-schema, unavailable-backup, and unexpected startup
  states render from the same validated interface copy catalog.
- Review exposes the exact primary and backup SHA-256 values plus the backup
  revision and profile count. Dynamic fingerprints, typed diagnostics, and the
  corrupt archive path render literally with markup disabled.
- Confirmed recovery disables duplicate activation and return navigation until
  a terminal result is known.
- A typed precondition mismatch proves no replacement ran, terminates the stale
  review, and does not offer direct retry.
- A broader storage failure or unexpected confirmed exception is an unknown
  mutation result: exception text is hidden, no file-state claim is made, and
  the operator is directed to inspect primary, backup, and archive identity
  before retry.
- Success shows the restored revision, profile count, and corrupt archive path.
  An explicit action then clears stale workflow screens and recomposes the
  dashboard from the recovered desired state.

## Evidence

- Focused application, adapter-contract, and Textual Pilot tests: `16 passed`.
- Full test suite: `616 passed, 18 skipped` in `176.01s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `259 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 161 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `2069340db2358d269d82affeeda7d1c6df09f05018cfbc0927225d98c1f4e672`.
- The desired-state recovery screen implementation contains no locale-authored
  text.
