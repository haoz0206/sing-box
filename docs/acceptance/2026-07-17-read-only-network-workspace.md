# Read-only Network workspace acceptance — 2026-07-17

## Scope

Add the missing Network destination from the SDD information architecture as a
human-readable desired-state workspace. Keep runtime observation in Diagnostics
and keep firewall mutation deferred until a separate adapter and recovery
design are accepted.

## Accepted behavior

- Dashboard exposes one visible `查看网络概览` action and a contextual `n`
  shortcut; `?` documents it and child screens suppress it like other printable
  dashboard shortcuts.
- Empty desired state explains that no listener port or public address intent
  exists.
- Populated desired state distinguishes enabled, paused, and draft profiles;
  TCP/UDP transport; fixed and apply-time automatic ports; and public address
  intent without claiming any runtime fact.
- Opening Network performs no DNS lookup, socket inspection, reachability test,
  public-IP discovery, or firewall read/write, and exposes no firewall mutation
  control.
- One `network_inventory` application interface owns protocol-to-transport
  mapping. Listener diagnostics consume its deduplicated enabled endpoints, so
  paused and draft rows remain visible intent without becoming runtime
  expectations.

## Test seam and evidence

- Confirmed Seam A: Textual `App.run_test()` and Pilot only for new user
  behavior; existing listener-diagnostics behavior remains the regression seam
  for the shared endpoint projection.
- Focused Network, keyboard, and listener-diagnostics set: `13 passed`.
- Dashboard visibility regression set after horizontal navigation repair:
  `14 passed`.
- Complete acceptance suite: `135 passed`.
- Complete repository suite: `556 passed, 18 skipped`.
- Ruff check passed; Ruff format reported `252 files already formatted`;
  strict mypy passed for `156 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully, both including
  `sb_manager/application/network_inventory.py` and
  `sb_manager/ui/screens/network.py`.
- Wheel SHA-256:
  `07a9cfd2ca86119ad502863ca944799a1f7f549b5ec3a74aee7652dc6d21a1d7`.

## External release boundary

This slice is a pure desired-state projection and Textual navigation change. It
does not widen privileged host mutation. Stable-release status still requires
the supported stable sing-box 1.14 gate and separately authorized live
systemd/OpenRC acceptance on recoverable hosts.
