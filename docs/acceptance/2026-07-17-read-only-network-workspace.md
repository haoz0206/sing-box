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
- One injected interface copy catalog owns the title, exact read-only scope,
  empty state, lifecycle counts and labels, fixed/automatic port labels, row
  templates, public-address heading, and missing-address fallback. Profile
  names, transports, fixed ports, and declared addresses remain literal
  non-markup evidence; the Network screen contains no locale-authored Han text.
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
- Focused Network workspace Pilot tests: `4 passed` in `1.40s`.
- Focused Network, keyboard, and listener-diagnostics set: `15 passed` in
  `2.82s`.
- Complete repository suite: `647 passed, 18 skipped` in `200.39s`.
- Ruff check passed; Ruff format reported `262 files already formatted`;
  strict mypy passed for `164 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully, both including
  `sb_manager/application/network_inventory.py` and
  `sb_manager/ui/screens/network.py`.
- Wheel SHA-256:
  `3597efa13d0bb5424988d152f3d05b96663ae2b29eb59e7450fb7858686bd8dc`.

## External release boundary

This slice is a pure desired-state projection and Textual navigation change. It
does not widen privileged host mutation. Stable-release status still requires
the supported stable sing-box 1.14 gate and separately authorized live
systemd/OpenRC acceptance on recoverable hosts.
