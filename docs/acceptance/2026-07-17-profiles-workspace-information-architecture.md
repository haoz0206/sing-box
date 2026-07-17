# Dashboard / Profiles information architecture acceptance — 2026-07-17

## Scope

Separate host overview from profile lifecycle work without changing any
desired-state, confirmation, or host-mutation policy. Dashboard remains the
status and recommendation surface; Profiles becomes the complete inventory and
task-entry surface.

## Accepted behavior

- Dashboard renders service/readiness/certificate status, aggregate profile
  counts, one safest recommendation, host actions, and navigation; it does not
  render complete profile rows or per-row lifecycle buttons.
- The empty Dashboard contains exactly one primary creation action and a
  secondary visible entry to the empty Profiles workspace.
- `p` and `管理配置` open the same Profiles workspace.
- Profiles renders every desired-state row and exposes add, details, and draft
  apply only when their corresponding application capability is available.
- Row controls emit one typed action message with a stable enum identity and
  exact profile ID. The root application does not listen to child-screen CSS
  selectors or parse translated labels.
- `Escape` from profile details returns to Profiles. A successful lifecycle
  operation discards stale child snapshots and returns to a recomposed
  Dashboard whose observations restart against current desired state.

## Test seam and evidence

- Confirmed Seam A: Textual `App.run_test()` and Pilot only; tests press visible
  shortcuts, click visible controls, and assert mounted screen content.
- Focused Profiles and keyboard acceptance: `9 passed`.
- Complete acceptance suite: `133 passed`.
- Complete repository suite: `554 passed, 18 skipped`.
- Ruff check passed; Ruff format reported `249 files already formatted`;
  strict mypy passed for `154 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully, both including
  `sb_manager/ui/labels.py` and `sb_manager/ui/screens/profiles.py`.
- Wheel SHA-256:
  `7122b5205122223f73c41bc8192a61eebbd54bdf258acde7c37b06e808da4d92`.

## External release boundary

This slice changes Textual navigation and screen ownership only. It adds no
privileged host mutation and does not widen an existing application seam.
Stable-release status still requires the supported stable sing-box 1.14 gate
and separately authorized live systemd/OpenRC acceptance on recoverable hosts.
