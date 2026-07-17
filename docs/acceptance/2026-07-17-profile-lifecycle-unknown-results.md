# Profile lifecycle unknown-result acceptance — 2026-07-17

## Scope

This slice extends conservative post-confirmation failure handling across the
remaining profile lifecycle journeys: editing, removal, and pause/resume. It
changes only Textual orchestration and presentation; application interfaces,
transaction outcomes, projection, and host adapters remain unchanged.

## Accepted behavior

- Existing typed validation, stale-plan, port, helper, transaction, rollback,
  and recovery failures retain their exact diagnostics and safety claims.
- An unclassified exception after edit confirmation becomes an unknown result
  for server configuration, service state, and desired state.
- The same conservative result applies after confirmed profile removal or
  pause/resume.
- Raw exception text is discarded and is not rendered in any Textual widget.
- Unknown-result screens do not claim rollback, unchanged state, or a
  successful desired-state commit.
- The operator is directed to read-only configuration identity, service status,
  and apply-history checks before deciding whether to retry.
- No automatic or one-click retry is offered.

## Verification evidence

- Red evidence: each unexpected lifecycle exception produced
  `textual.worker.WorkerFailed`, exposed the exception in the test traceback,
  and left its confirmation screen active.
- Focused unknown-result and preserved typed-error checks: `6 passed`.
- Complete edit, removal, and availability acceptance files: `32 passed`.
- Full test suite: `511 passed, 18 skipped`.
- Ruff format reported `239 files already formatted`; Ruff lint passed.
- Strict mypy passed for `147 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `9b9c2de7c31077b60f1e4cf5db4326a89f275f6ebaa1598360f78c1dce0ad8a5`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Previously accepted
real-core, wheel-install, and Debian 12 / Ubuntu 24.04 / Alpine 3.20 container
evidence therefore remains applicable. Stable sing-box 1.14 verification and
authorized live systemd/OpenRC smoke tests remain external release gates.
