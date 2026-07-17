# Unknown mutation-result acceptance — 2026-07-17

## Scope

This slice prevents unclassified exceptions after explicit confirmation from
crashing the Textual worker in the two primary host-mutation journeys: profile
configuration apply and sing-box core activation. It changes only terminal UI
orchestration and does not alter either application interface or host adapter.

## Accepted behavior

- Existing typed validation, commit, rollback, artifact-acquisition, helper,
  and activation failures retain their existing evidence and guidance.
- An unclassified exception after profile-apply confirmation becomes a complete
  unknown result for live configuration, runtime, and desired state.
- An unclassified exception after core-update confirmation becomes an unknown
  activation result because failure timing relative to the atomic switch is not
  known.
- Raw exception text is not retained or rendered.
- Unknown-result screens do not claim rollback, unchanged state, or successful
  desired-state commit.
- The operator is directed to read-only configuration identity, runtime health,
  apply-history, helper-log, current-link, and version checks as appropriate.
- No automatic or one-click retry is offered.

## Verification evidence

- Red evidence: an unexpected profile-apply exception produced
  `textual.worker.WorkerFailed` and left the confirmation screen active.
- Red evidence: an unexpected core-update exception produced
  `textual.worker.WorkerFailed` and left the activation plan active.
- Focused unknown-result journeys: `2 passed`.
- Complete profile-apply and core-update acceptance files: `41 passed`.
- Full test suite: `508 passed, 18 skipped`.
- Ruff format reported `239 files already formatted`; Ruff lint passed.
- Strict mypy passed for `147 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `92378ca8f43e9dffb92f0649fdfc248462ae072d5fd25d6988280d96c47b46c5`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Previously accepted
real-core, wheel-install, and Debian 12 / Ubuntu 24.04 / Alpine 3.20 container
evidence therefore remains applicable. Stable sing-box 1.14 verification and
authorized live systemd/OpenRC smoke tests remain external release gates.
