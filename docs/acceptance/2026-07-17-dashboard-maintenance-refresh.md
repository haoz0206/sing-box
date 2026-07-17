# Dashboard maintenance and refresh acceptance — 2026-07-17

## Scope

This slice closes two related dashboard gaps: lifecycle workflows previously
recomposed the root view without restarting its observations, and managed
certificate maintenance was visible only after opening the diagnostics center.

Primary test seam: confirmed Seam A, Textual `App.run_test()` plus Pilot.
Production composition is verified through confirmed Seam E.

## Accepted behavior

- Returning after a successful profile lifecycle change clears old runtime,
  readiness, and certificate evidence, recomposes current desired state, and
  restarts every configured dashboard observation.
- Lifecycle screens emit one UI-level dashboard refresh request and do not know
  which inspectors the root application has configured.
- Managed-certificate inspection runs independently in a background worker and
  shows only `状态正常`, `建议关注`, `需要处理`, or `无法检查` on the dashboard.
- Urgent certificate guidance precedes unapplied drafts. Attention guidance is
  presented after an unapplied draft, preserving the more immediate action.
- Unexpected certificate probe exceptions are discarded, never rendered, and
  leave an explicit read-only recheck action enabled.
- Production direct and privileged composition reuse the exact same
  `CertificateDiagnosticsService` instance for dashboard status and detailed
  diagnostics policy; no new privileged operation is introduced.

## TDD evidence

- Dashboard-refresh red: after successful profile removal, the recomposed page
  remained at `服务状态：正在检查…` and performed only one inspection (`1 failed`).
- Action-required red: `ManagerAppHostTools` had no certificate-maintenance
  capability (`1 failed`).
- Attention red: an attention report was incorrectly presented as normal
  (`1 failed`).
- Failure red: an unexpected certificate probe escaped the worker and left the
  dashboard indefinitely checking (`1 failed`).
- Production-composition red: `create_app()` left the dashboard certificate
  diagnostics unset (`1 failed`).
- Focused dashboard-refresh green: `1 passed`.
- Focused certificate-state green: `3 passed`.
- Focused production-composition green: `1 passed`.
- Complete affected first-profile, removal, editing, availability, cloning,
  state-recovery, and CLI files: `112 passed`.
- Full suite: `529 passed, 18 skipped`.
- Static gates: Ruff lint passed, all `241` files are formatted, mypy passed for
  `149` source files, and `git diff --check` passed.
- Release build produced both sdist and wheel; wheel inspection confirms
  `sb_manager/ui/messages.py` is packaged. Wheel SHA-256:
  `a0fe4b2dbf95c4875296454b5afa9eb86d4eb8b64cf9fae6f55bc28158d6f5e4`.

## Release boundary

This change adds no network request, certificate mutation, private-key read,
privileged request, configuration projection, or host mutation. The existing
certificate source remains bounded by its direct or fixed-helper adapter.
Stable sing-box 1.14 and authorized live systemd/OpenRC smoke tests remain
external release gates.
