# Profile edit copy acceptance — 2026-07-17

## Scope

Migrate the complete profile-edit journey into the validated interface copy
catalog while preserving its revision-bound plan, explicit confirmation,
desired-state versus live-configuration effect boundary, typed transaction
outcomes, and unknown-result safety policy.

This slice includes the edit form, unexpected planning failure, normalized
change plan, confirmation progress state, every terminal transaction result,
confirmation-time port and revision conflicts, and known or unexpected
operational failures. It does not change the `ProfileEditor` interface or host
transaction implementation.

## Accepted behavior

- The profile-details catalog instance flows through the form, plan, worker
  result, and every nested failure screen; opening the form performs no plan or
  mutation.
- Stable ID, protocol, credentials, TLS, and transport remain unchanged. The
  operator edits only name, public server address, and fixed or automatic
  listen-port intent.
- The plan shows normalized before/after values and explicitly distinguishes a
  desired-state-only save from a full live configuration validation, service
  refresh, health check, and rollback transaction.
- No effect occurs during preview. Confirmation is explicit, suppresses
  duplicate execution, and prevents return while its worker is active.
- Desired-state-only success, live success, validation failure, replacement-
  precondition failure, commit failure, successful rollback, and manual
  recovery remain distinct typed terminal outcomes.
- An unexpected planning failure discloses no exception and states that nothing
  ran. An unexpected post-confirmation failure claims no state and directs the
  operator to configuration identity, service status, and apply history before
  deciding whether to retry.
- All screen-authored copy renders through semantic catalog identities. Dynamic
  profile values, application diagnostics, transaction evidence, and recovery
  instructions render with markup disabled and are never parsed to choose an
  action or safety conclusion.
- Application-provided validation and transaction diagnostics remain typed,
  disclosure-safe evidence at the existing `ProfileEditor` seam; this slice
  does not add a presentation-only port or test-only adapter.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior.

- Catalog propagation tracer red: an injected marker reached profile details,
  but the form still rendered hard-coded `编辑配置`.
- First green: form and normalized plan rendered `目录编辑配置` and
  `目录确认配置变更` from the same injected catalog.
- Result tracer red: confirmed desired-state success still rendered hard-coded
  `配置已更新`; green rendered `目录配置已更新`.
- Unknown-result tracer red: the terminal failure still rendered hard-coded
  `无法确认配置编辑结果`; green rendered the injected catalog marker without
  exposing the worker exception.
- Planning-failure tracer red: the read-only failure still rendered hard-coded
  `无法准备配置编辑`; green rendered the injected marker while preserving the
  no-effect statement.
- Existing Pilot scenarios continue to prove form prefill, normalization,
  desired/live impact, validation focus, confirmation, refresh, port conflict,
  revision conflict, every transaction outcome, rollback recovery, and secret
  non-disclosure.

No private method, widget field, or internal collaborator is a test seam.

## Quality evidence

- Profile-edit application and Pilot gate: 43 passed.
- Full acceptance suite: 152 passed.
- Full repository suite: 586 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Literal audit found no simplified-Chinese text in
  `src/sb_manager/ui/screens/profile_editing.py`.
- The built wheel contains `sb_manager/ui/app.py`,
  `sb_manager/ui/copy_catalog.py`, and
  `sb_manager/ui/screens/profile_editing.py`; SHA-256:
  `fd3ae15e1f012b5d6ef7a54f71cf74e941a42e2a408300a59ac7cc41c6b8bc23`.

## Next migration boundary

Audit the remaining profile lifecycle journeys (availability, removal, and
template cloning) for the same complete catalog propagation and non-markup
diagnostic contract.
