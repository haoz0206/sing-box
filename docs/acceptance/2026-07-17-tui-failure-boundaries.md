# TUI failure-boundary acceptance — 2026-07-17

## Scope

This slice closes remaining unclassified failures at high-value Textual seams:
desired-state startup inspection and recovery, existing-configuration adoption,
purpose recommendation, new-profile planning, profile-detail reads, and
core-update planning. Application interfaces and host adapters remain
unchanged.

## Accepted behavior

- Typed validation, missing-profile, stale-state, inspection, and activation
  errors retain their existing actionable presentation.
- An unclassified startup state inspection renders a read-only safe page instead
  of preventing the TUI from mounting; mutation controls are absent.
- An unclassified confirmed recovery treats primary, backup, and corrupt-file
  archive results as unknown and forbids direct retry.
- Adoption planning failures claim no mutation; confirmed adoption failures keep
  the no-host-mutation guarantee while treating the desired-state replacement
  precondition as unknown.
- Recommendation failure does not block advanced direct protocol selection.
- New-profile, profile-detail, and core-update planning failures are
  non-disclosing and state that no draft, host mutation, download, or activation
  was performed as appropriate.
- Raw exception text is never rendered and no automatic retry is offered.

## Verification evidence

- Red evidence: all eight unexpected failures escaped their Textual event,
  worker, or compose boundary and exposed a private test token in the traceback.
- New focused boundary journeys: `8 passed`.
- Complete state-recovery, first-profile, recommendation, and core-update
  acceptance files: `58 passed`.
- Full test suite: `525 passed, 18 skipped`.
- Static gates: Ruff lint passed, all `239` files are formatted, mypy passed for
  `147` source files, and `git diff --check` passed.
- Release build produced both sdist and wheel successfully. Wheel SHA-256:
  `6f09f66e5a5be1cf9386de705eee88d7c100aae47684f98fdbffdb0586864c32`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Stable sing-box 1.14 and
authorized live systemd/OpenRC smoke tests remain external release gates.
