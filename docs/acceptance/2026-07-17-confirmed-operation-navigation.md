# Confirmed-operation navigation acceptance — 2026-07-17

## Scope

This slice closes a Textual navigation race shared by explicitly confirmed
background operations. Previously, Escape could remove a confirmation screen
while its worker continued, allowing a result or error to appear over an
unrelated destination. Application use cases, host adapters, privileged
requests, and transaction semantics are unchanged.

## Accepted behavior

- Escape returns normally before explicit confirmation.
- The shared confirmation module receives the journey copy catalog; its visible
  Escape description is rendered from `common.cancel` rather than screen-local
  text.
- A second confirmation acquires a one-shot shared navigation guard before the
  worker starts and suppresses duplicate execution.
- While the worker is in flight, Escape cannot remove the originating screen,
  the Footer return binding is visibly disabled, and operation-specific progress
  text states that completion is required before returning.
- Success, classified failure, retryable failure, unknown result, same-screen
  completion, and typed dismissal release the guard on the UI thread before
  presenting their terminal state.
- Closing a terminal result returns to an unlocked confirmation screen; Escape
  can then continue to its parent without starting the operation again.
- Escape never cancels or claims to cancel host or desired-state work.

## Covered workflows

- first profile apply;
- profile edit, removal, and pause/resume;
- exact live-configuration adoption;
- desired-state recovery;
- profile-template cloning;
- sing-box core installation/update.
- unreadable interface-preference reset.

## Verification evidence

- Red evidence: the slow first-apply Pilot journey left the confirmation screen
  while the worker continued and therefore could not find its confirmation UI.
- Follow-up red evidence: a marker catalog reached the core-update confirmation
  content but its real Footer still rendered the hardcoded `取消` description.
- Catalogued cancellation and parent-form preservation regression: `1 passed`.
- All affected confirmed-workflow Textual journeys: `142 passed`.
- Focused slow-worker navigation and guard-release regression: `1 passed`.
- Affected Textual journey files: `94 passed` during migration.
- Full test suite: `654 passed, 18 skipped`.
- Static gates: Ruff lint passed, all `263` files are formatted, mypy passed for
  `164` source files, and `git diff --check` passed.
- Release build produced both sdist and wheel successfully. Wheel SHA-256:
  `03c44f3362baeb72b542533b7b333952fb6511bd6eb8251f6285797f3139dd60`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Stable sing-box 1.14 and
authorized live systemd/OpenRC smoke tests remain external release gates.
