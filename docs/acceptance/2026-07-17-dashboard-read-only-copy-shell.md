# Dashboard read-only copy shell acceptance — 2026-07-17

## Scope

Make the Dashboard's effect boundary obvious before an operator interprets
background evidence, and continue the interface-copy migration without
silently treating application recommendation strings as localized.

## Accepted behavior

- Empty and populated dashboards state that checks are read-only, do not modify
  the host, and that every change still requires plan review and explicit
  confirmation.
- The scope statement does not disable safe navigation or the existing single
  primary action.
- Application subtitle, contextual binding descriptions, Dashboard titles,
  initial and terminal runtime/readiness/certificate states, profile counts,
  workspace navigation, detail/retry controls, and empty guidance render from
  the immutable simplified-Chinese catalog.
- Probe failures remain non-disclosing and retryable, successful observations
  retain their established wording, and dashboard refresh behavior is
  unchanged.
- Recommendation summaries and primary-action labels remain owned by the
  application recommendation interface in this slice. They are explicitly the
  next migration unit; no second locale is exposed prematurely.

## Test seam

Confirmed Seam A remains the public interface. Textual Pilot observes the scope
statement and continues through the first-profile action, while existing
Dashboard Pilot scenarios cover populated, healthy, failed, retry, readiness,
certificate, refresh, and navigation states. No new test seam is introduced.

## Quality evidence

- Focused Dashboard gate: 57 passed.
- Full acceptance suite: 143 passed.
- Full repository suite: 577 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files.
- `git diff --check` passed, and the Dashboard status-shell range contains no
  remaining simplified-Chinese literals outside the catalog.
- The built wheel contains `sb_manager/ui/app.py` and
  `sb_manager/ui/copy_catalog.py`; SHA-256:
  `8964c322596e2cfcc8026d58f17f31b2fae54a34be5720ece62ff357d1ae2c75`.

## Next migration boundary

Replace presentation-ready `DashboardRecommendation.summary` and
`DashboardAction.label` values with semantic identities and catalog rendering,
while preserving the application's recommendation priority and stable action
navigation. This boundary was completed in the subsequent
[Dashboard semantic recommendation copy acceptance](2026-07-17-dashboard-semantic-recommendation-copy.md).
