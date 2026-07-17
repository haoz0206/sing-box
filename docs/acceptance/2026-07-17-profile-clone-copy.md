# Profile template clone copy acceptance — 2026-07-17

## Scope

Migrate the complete secret-free profile-template journey into the validated
interface copy catalog while preserving revision-bound planning, explicit
copied/reset semantics, editable-name review, desired-state-only confirmation,
and conservative unknown-result handling.

This slice includes localized facet-list construction, the form and review/edit
loop, confirmation progress, stale-state guidance, committed results, expected
validation diagnostics, and unexpected planning or operational failures. It
does not change the `ProfileCloner` interface, reusable/reset facet policy,
shared mutation lock, or desired-state commit implementation.

## Accepted behavior

- One catalog instance flows from profile details through initial planning,
  copied/reset facet labels, form controls, review, confirmation, committed
  result, planning failure, and unknown-result guidance.
- Opening details, the clone form, and review performs no mutation. The operator
  sees which non-secret facets are reused and which sensitive or conflicting
  facets are reset before confirmation.
- The copied/reset list grammar belongs to the locale catalog rather than the
  screen, so labels, separators, and conjunctions cannot become partially
  translated.
- Confirmation remains revision- and source-intent-bound under the shared
  mutation lock. A successful clone creates one independent automatic-port
  draft without invoking host configuration, runtime, helper, or material
  generation.
- Typed name and stale-state errors remain actionable. Unexpected planning
  failure says no draft was created; unexpected confirmed failure hides the
  exception and reports only the desired-state result as unknown.
- A revision conflict disables confirmation for the stale plan. Returning to
  edit and successfully reviewing a fresh plan re-enables confirmation and can
  complete against the new desired-state revision.
- Profile names, validation diagnostics, review summaries, and result evidence
  render as literal non-markup text.
- The existing `ProfileCloner.plan/clone` seam remains deep; no presentation-
  only or test-only production interface was introduced.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior.

- Form-title tracer red: an injected catalog reached profile details, but the
  clone form still rendered hard-coded `以现有配置创建新草案`; green rendered
  `目录创建模板草案`.
- Facet tracer red: copied semantics still rendered hard-coded
  `将复用：协议和服务器地址`; green used injected facet labels, separator,
  conjunction, and framing from the same catalog.
- Review/result tracer red: the review still rendered hard-coded
  `确认模板草案`; green propagated the catalog through review and committed
  result states.
- Planning-failure tracer red: initial planning still rendered hard-coded title,
  hidden-error details, and recovery guidance; green rendered all injected
  catalog markers without disclosing the exception.
- Operational-failure tracer red: confirmed unexpected failure still rendered
  hard-coded unknown-result guidance; green rendered all injected markers and
  preserved the desired-state-only uncertainty boundary.
- A Pilot regression scenario uses Rich-like profile names and proves form,
  review, and result evidence render literally.
- Stale-confirmation red: a revision conflict re-enabled confirmation for the
  invalid plan; green disables it until the operator returns to edit and reviews
  a fresh plan, after which confirmation succeeds.

No private method, widget field, or internal collaborator is a test seam.

## Quality evidence

- Profile-clone application and Pilot gate: 17 passed.
- Full acceptance suite: 168 passed.
- Full repository suite: 602 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Literal audit found no simplified-Chinese text in
  `src/sb_manager/ui/screens/profile_cloning.py`.
- The built wheel contains `sb_manager/ui/app.py`,
  `sb_manager/ui/copy_catalog.py`, and
  `sb_manager/ui/screens/profile_cloning.py`; SHA-256:
  `c0486b7582a2178e86dfba16c47a44ed385cb7f1e22b77ff9991158cb11f9ecf`.

## Next migration boundary

Continue migrating the remaining user-visible TUI journeys through the same
catalog propagation and non-markup diagnostic contract.
