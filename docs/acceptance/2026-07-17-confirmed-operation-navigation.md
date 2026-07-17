# Confirmed-operation navigation acceptance — 2026-07-17

## Scope

This slice closes a Textual navigation race shared by explicitly confirmed
background operations. Previously, Escape could remove a confirmation screen
while its worker continued, allowing a result or error to appear over an
unrelated destination. Application use cases, host adapters, privileged
requests, and transaction semantics are unchanged.

## Accepted behavior

- Escape returns normally before explicit confirmation.
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

## Verification evidence

- Red evidence: the slow first-apply Pilot journey left the confirmation screen
  while the worker continued and therefore could not find its confirmation UI.
- Focused slow-worker navigation and guard-release regression: `1 passed`.
- Affected Textual journey files: `94 passed` during migration.
- Full test suite: `529 passed, 18 skipped`.
- Static gates: Ruff lint passed, all `242` files are formatted, mypy passed for
  `150` source files, and `git diff --check` passed.
- Release build produced both sdist and wheel successfully. Wheel SHA-256:
  `454b449b51089d8c93377279b84718b9ccf73634ce180f84b46052bbd5245837`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Stable sing-box 1.14 and
authorized live systemd/OpenRC smoke tests remain external release gates.
