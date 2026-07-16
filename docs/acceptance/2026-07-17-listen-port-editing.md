# Transactional listen-port editing acceptance — 2026-07-17

Audited implementation: the repository state identified by the exact wheel
SHA-256 recorded below.

## Capability verdict

An existing profile can now change its listening port without being removed and
recreated. A numeric value selects a fixed port; a blank value changes the
profile to automatic port selection. The edit preview distinguishes the actual
port change from the selection-policy change before confirmation.

For an applied profile, the confirmed edit reprojects the complete managed
configuration and uses the existing validate, replace, restart, and rollback
transaction. Port availability is checked while planning and checked again
under the shared apply lock before mutation. Concurrent occupation is reported
as a typed, recoverable conflict and leaves desired and live state unchanged.
Automatic selection excludes ports already declared by other managed profiles.
The committed result reports the actual selected port rather than the blank
automatic-selection request.

## Repository-local evidence

- The focused behavior, Textual journey, production-composition, and port-source
  contract suites pass: 55 passed.
- The complete pytest suite passes without root or network authorization: 343
  passed and 16 opt-in integration cases skipped.
- Behavior coverage includes range validation, managed-profile conflicts, host
  occupation, confirmation-time races, automatic selection, policy-only edits,
  full configuration reprojection, transaction success, and rollback safety.
- Sixteen Textual edit journeys cover prefilled input, fixed-port preview,
  automatic selection, the actual committed port, stale revisions, conflicts,
  failures, and the compact 80-by-24 terminal layout.
- Ruff formatting and lint checks pass for all 183 files.
- mypy passes for all 113 source files.
- `git diff --check` passes.
- The complete generated-protocol integration suite passes the real
  `sing-box 1.14.0-alpha.45 check`: 13 passed, including the reprojected applied
  profile port edit.
- The wheel and source distribution build successfully.
- The exact wheel SHA-256 is
  `26e79335833e66b0f9b0eb59b7d5b122df4f22182e4572389543d6022292b57d`.
  That wheel passes the isolated package-release install test and the pinned
  Debian 12, Ubuntu 24.04, and Alpine 3.20 package/authorization acceptance.

## Remaining release gates

1. Run the opt-in systemd smoke on approved, recoverable Debian 12 and Ubuntu
   24.04 hosts.
2. Run the opt-in OpenRC smoke on an approved, recoverable Alpine 3.20 host.
3. Repeat the real configuration and artifact suites after upstream publishes
   stable sing-box 1.14. The currently validated artifact is
   `sing-box 1.14.0-alpha.45`.
