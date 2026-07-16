# Generated configuration diagnostics acceptance — 2026-07-17

Audited implementation: the repository state identified by the exact wheel
SHA-256 recorded below.

## Capability verdict

The diagnostics center now proves whether the current desired-state snapshot
can be reprojected into one complete manager-owned document and accepted by the
configured sing-box validator before the operator enters an apply workflow. The
check uses disposable staging and never reads or replaces the live target.

Projection failures, semantic rejection, unavailable staging, and successful
validation remain typed outcomes. Validator diagnostics redact every persisted
protocol-material value before entering the application or Textual modules. A
missing core is reported as the prerequisite and retains the existing trusted
core-management action instead of being misclassified as invalid configuration.
Independent desired-state, live-identity, readiness, and runtime evidence remains
visible when this check fails.

## Repository-local evidence

- The focused diagnostics behavior, adapter contract, production-composition,
  and Textual journey suites pass: 49 passed.
- The complete pytest suite passes without root or network authorization: 354
  passed and 17 opt-in integration cases skipped.
- Behavior coverage includes valid and invalid observations, typed probe
  failure, missing-core classification and priority, and preservation of
  independent runtime evidence.
- Adapter coverage exercises complete projection, disposable staging, validator
  delegation, unprojectable applied profiles, staging failure, silent-success
  normalization, and persisted protocol-material redaction.
- The Textual journey proves that rejection details and recovery guidance are
  visible through public user controls.
- Ruff formatting and lint checks pass for all 186 files.
- mypy passes for all 115 source files.
- `git diff --check` passes.
- The complete generated-protocol integration suite passes the real
  `sing-box 1.14.0-alpha.45 check`: 14 passed, including the production
  generated-configuration inspector and its stable success normalization.
- The wheel and source distribution build successfully.
- The exact wheel SHA-256 is
  `cd3b3157cf910d69003cfc10305e5a634f6a66a77b9a148e26536cb82f020247`.
  That wheel passes the isolated package-release install test and the pinned
  Debian 12, Ubuntu 24.04, and Alpine 3.20 package/authorization acceptance.

## Remaining release gates

1. Run the opt-in systemd smoke on approved, recoverable Debian 12 and Ubuntu
   24.04 hosts.
2. Run the opt-in OpenRC smoke on an approved, recoverable Alpine 3.20 host.
3. Repeat the real configuration and artifact suites after upstream publishes
   stable sing-box 1.14. The currently validated artifact is
   `sing-box 1.14.0-alpha.45`.
