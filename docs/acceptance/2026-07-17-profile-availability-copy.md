# Profile availability copy acceptance — 2026-07-17

## Scope

Migrate the complete pause/resume journey into the validated interface copy
catalog while preserving profile identity and material, revision-bound review,
explicit confirmation, complete live-configuration transaction semantics, and
unknown-result safety.

This slice includes expected and unexpected planning failures, pause and resume
plans, confirmation progress, committed results, every typed transaction
failure, rollback recovery, and known or unexpected operational failures. It
does not change the `ProfileAvailabilityManager` interface, configuration
projection, port policy, or host transaction implementation.

## Accepted behavior

- One catalog instance flows from profile details through expected rejection,
  unexpected planning failure, the plan, worker, committed result, and terminal
  error screens.
- Opening details or a plan performs no mutation. The plan names the profile,
  shows the resulting active-profile count, and explains the exact inbound
  removal or restoration effect before confirmation.
- Pausing preserves stable identity, credentials, endpoint, and listen-port
  intent while removing the inbound from the complete projection. Resuming
  rechecks fixed-port availability or may select an automatic port under the
  existing shared mutation lock.
- Confirmation remains explicit, suppresses duplicate execution, and prevents
  return while the complete configuration transaction is active.
- Committed pause/resume, validation failure, replacement-precondition failure,
  commit failure, successful rollback, and manual recovery remain distinct
  typed outcomes.
- Unexpected planning failure states that no operation ran. Unexpected
  post-confirmation failure claims no host, service, or desired-state result and
  requires configuration identity, service status, and apply-history
  inspection before deciding whether to retry.
- All screen-authored copy uses semantic catalog identities. Profile names,
  typed application/transaction diagnostics, and recovery instructions render
  with markup disabled and are never parsed for navigation or safety policy.
- The existing `ProfileAvailabilityManager` remains the application seam; no
  presentation-only port or test-only production interface was added.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior.

- Plan tracer red: an injected catalog reached profile details, but resume
  review still rendered hard-coded `确认恢复配置`; green rendered
  `目录确认恢复配置`.
- Unknown-result tracer red: confirmation still rendered hard-coded
  `无法确认配置状态变更`; green rendered `目录无法确认状态变更` without
  exposing the worker exception.
- Planning-failure tracer red: the read-only failure still rendered hard-coded
  `无法准备配置状态变更`; green rendered `目录无法准备状态变更` while
  preserving the no-effect statement.
- Committed-result tracer red: successful resume still rendered hard-coded
  `配置已恢复`; green rendered `目录配置已恢复` from the same injected
  catalog.
- Existing Pilot scenarios continue to prove real pause/resume projection,
  material preservation, actionable unavailable-port guidance, typed
  transaction outcomes, rollback recovery, and secret non-disclosure.

No private method, widget field, or internal collaborator is a test seam.

## Quality evidence

- Profile-availability application and Pilot gate: 25 passed.
- Full acceptance suite: 155 passed.
- Full repository suite: 589 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Literal audit found no simplified-Chinese text in
  `src/sb_manager/ui/screens/profile_availability.py`.
- The built wheel contains `sb_manager/ui/app.py`,
  `sb_manager/ui/copy_catalog.py`, and
  `sb_manager/ui/screens/profile_availability.py`; SHA-256:
  `626a6a26327533e5ac7472ff535d696c4047423a53cfdf1195f299592df9ad75`.

## Next migration boundary

Migrate profile removal through the same catalog propagation and non-markup
diagnostic contract, preserving desired-state-only versus live-transaction
scope.
