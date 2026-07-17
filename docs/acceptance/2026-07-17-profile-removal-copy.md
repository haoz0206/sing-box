# Profile removal copy acceptance — 2026-07-17

## Scope

Migrate the complete profile-removal journey into the validated interface copy
catalog while preserving desired-state-only draft removal, complete
live-configuration replacement for an applied profile, revision-bound review,
explicit confirmation, and conservative unknown-result handling.

This slice includes the draft and live impact plans, confirmation progress,
committed results, every typed transaction failure, rollback recovery, missing
transaction evidence, and known or unexpected planning and operational
failures. It does not change the `ProfileRemover` interface, configuration
projection, desired-state commit ordering, or host transaction implementation.

## Accepted behavior

- One catalog instance flows from profile details through the removal plan,
  confirmation worker, every result branch, planning failure, and operational
  failure.
- Opening details or a removal plan performs no mutation. The plan names the
  exact profile, distinguishes draft-only removal from live replacement, shows
  remaining profile and applied counts, and requires explicit confirmation.
- Draft removal commits desired state without changing sing-box. Applied
  removal projects the complete remaining configuration and advances desired
  state only after a successful host transaction.
- Applied success, validation failure, replacement-precondition failure, commit
  failure, successful rollback, and failed rollback with manual recovery remain
  distinct typed outcomes.
- A missing host transaction never claims success. It reports that desired
  state was not committed and requires configuration identity, service status,
  and apply-history inspection before deciding whether to retry.
- Expected operational errors preserve their typed diagnostics. Unexpected
  failures do not disclose exception text and do not infer host, service, or
  desired-state success.
- All screen-authored copy uses semantic catalog identities. Profile values,
  typed transaction diagnostics, and recovery instructions render with markup
  disabled and are never parsed for navigation or safety policy.
- The existing `ProfileRemover` plan/execute seam remains deep; no
  presentation-only port or test-only production interface was introduced.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior.

- Plan tracer red: an injected catalog reached profile details, but removal
  review still rendered hard-coded `确认移除配置`; green rendered
  `目录确认移除配置`.
- Draft-result tracer red: confirmed removal still rendered hard-coded
  `草案已移除`; green rendered `目录草案已移除` from the same catalog.
- Unknown-result tracer red: the terminal error title and later its hidden-error
  details and recovery guidance remained hard-coded; green rendered all three
  injected catalog markers without exposing the exception.
- Planning-failure tracer red: read-only planning failure still rendered local
  title, details, and retry guidance; green rendered the injected catalog
  markers while preserving the no-effect claim.
- Missing-transaction red: the result only suggested checking service status;
  green requires configuration identity, service status, and apply-history
  inspection before retry.
- Pilot regression scenarios cover precondition failure, commit failure,
  successful rollback, failed rollback, literal Rich-like diagnostics, and
  literal manual recovery steps.

No private method, widget field, or internal collaborator is a test seam.

## Quality evidence

- Profile-removal application and Pilot gate: 24 passed.
- Full acceptance suite: 164 passed.
- Full repository suite: 598 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Literal audit found no simplified-Chinese text in
  `src/sb_manager/ui/screens/profile_removal.py`.
- The built wheel contains `sb_manager/ui/app.py`,
  `sb_manager/ui/copy_catalog.py`, and
  `sb_manager/ui/screens/profile_removal.py`; SHA-256:
  `fee35515e524acecf6d714f4ef83a3b4bbb367f8cd59063147f609cd8aa03dde`.

## Next migration boundary

Continue migrating remaining user-visible journeys through the same catalog
propagation and non-markup diagnostic contract.
