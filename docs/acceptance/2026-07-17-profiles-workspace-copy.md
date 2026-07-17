# Profiles workspace copy acceptance — 2026-07-17

## Scope

Make the complete desired-state inventory's task hierarchy and effect boundary
consistent with the Dashboard, while preserving every existing lifecycle
destination and capability check.

This slice covers the Profiles inventory screen. Profile detail, edit, removal,
availability, cloning, draft-apply confirmation, and guided-add screens retain
their own existing behavior and are subsequent catalog slices.

## Accepted behavior

- The workspace displays one task title, short purpose statement, and an
  always-visible statement that the inventory is read-only and every
  configuration change remains plan-first and explicit-confirmation-bound.
- Empty guidance, active/paused/draft state, automatic/fixed port wording, row
  composition, details, draft apply, and add actions render through the same
  immutable simplified-Chinese catalog as Dashboard and Settings.
- Protocol labels remain stable product identifiers rather than locale-specific
  prose.
- Details and draft-apply buttons remain capability-aware and post one typed
  `ProfileWorkspaceActionRequested` with the exact stable profile ID. They do
  not execute a mutation from the inventory screen.
- `Esc` from a child workflow preserves Profiles context; successful lifecycle
  work continues to refresh through the Dashboard rather than leaving a stale
  snapshot.
- `profiles.py` contains no simplified-Chinese literal.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior.

- Catalog tracer red: an injected marker catalog was ignored and the title
  remained `配置工作区` instead of `目录配置工作区`.
- Catalog tracer green: the same app rendered `目录配置工作区` and
  `目录添加配置` through the injected catalog.
- Safety tracer red: `#profiles-workspace-safety` did not exist.
- Safety tracer green: the workspace rendered the exact read-only,
  plan-first, explicit-confirmation statement.
- Existing Pilot scenarios continue to cover populated and empty inventory,
  one primary Dashboard creation action, details return, exact draft handoff,
  and capability-aware row actions.

No private method, screen field, or child CSS selector is a test seam.

## Quality evidence

- Profiles workspace gate: 7 passed.
- Full acceptance suite: 146 passed.
- Full repository suite: 580 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Literal audit found no simplified-Chinese text in `profiles.py`.
- The built wheel contains `sb_manager/ui/app.py`,
  `sb_manager/ui/copy_catalog.py`, and `sb_manager/ui/screens/profiles.py`;
  SHA-256:
  `b81d72bdffd739486119f0ed4a63453371ce866e5b3572fca74681ef331418ab`.

## Next migration boundary

Continue the Profiles safety journey with the profile-details and lifecycle
confirmation screens, keeping each plan/confirmation workflow as its own TDD
slice. The subsequent
[profile-details copy acceptance](2026-07-17-profile-details-copy.md) completes
the read-only detail and sensitive-disclosure portion; lifecycle confirmation
screens remain.
