# Dashboard semantic recommendation copy acceptance — 2026-07-17

## Scope

Move Dashboard recommendation wording out of application policy without
changing which evidence wins, which destination opens, or whether an action is
available.

## Accepted behavior

- `DashboardRecommendation` returns a stable recommendation identity, an
  optional structured draft count, and an optional typed action.
- `DashboardAction` returns only its stable navigation identity and optional
  profile identity; neither application type carries presentation-ready copy.
- The Textual presentation adapter renders every recommendation summary and
  primary-action label through the validated simplified-Chinese catalog.
- Readiness and certificate findings keep their detailed guidance on the
  evidence screen. The Dashboard presents one stable, bounded next step rather
  than copying arbitrary report guidance into its primary hierarchy.
- Failed, pending, blocking, draft, maintenance, empty, and healthy priority;
  capability-aware action withholding; and all existing destinations remain
  unchanged.
- Reinspection status uses the same catalog identities as initial inspection,
  leaving no simplified-Chinese literal in the Dashboard implementation range.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior. A marker catalog was
injected through `ManagerAppInterfaceTools`; before implementation, the empty
Dashboard still rendered the application-owned copy and the tracer failed with
`建议：创建第一个配置` instead of `建议：从目录开始首个配置`. After the
semantic identities and presentation adapter were added, the same test passed
and the primary action rendered `目录中的创建动作` from the catalog adapter.

Existing application-interface tests continue to specify recommendation
priority using semantic identities, while Dashboard Pilot scenarios verify the
user-visible wording and navigation. No private method or internal collaborator
is a test seam.

## Quality evidence

- Semantic-copy tracer: 1 passed, 44 deselected.
- Focused recommendation and Dashboard gate: 58 passed.
- Full acceptance suite: 144 passed.
- Full repository suite: 578 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Structural and literal audits found no former recommendation/action copy fields
  and no simplified-Chinese literal in the complete Dashboard implementation
  range.
- The built wheel contains `sb_manager/application/dashboard.py`,
  `sb_manager/ui/app.py`, and `sb_manager/ui/copy_catalog.py`; SHA-256:
  `ff58a0c4845bc178d67cb91c14da10d67e81cdb09ed94f942745cb9aab88414b`.

## Next migration boundary

Migrate the Profiles workspace's complete safety journey into the validated
catalog before considering another locale. The subsequent
[Profiles workspace copy acceptance](2026-07-17-profiles-workspace-copy.md)
completes the inventory workspace, and the subsequent
[profile-details copy acceptance](2026-07-17-profile-details-copy.md) completes
its read-only details and sensitive-disclosure entry. Lifecycle confirmation
screens remain separate migration slices.
