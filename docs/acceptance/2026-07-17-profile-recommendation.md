# Purpose-first profile recommendation acceptance — 2026-07-17

## Scope

This record covers the purpose-first add-profile journey, its pure protocol
recommendation policy, exact protocol/transport variant identity, advanced
direct selection, handoff to every existing guided form, and production package
composition.

## Evidence

- Full local suite: `409 passed, 18 skipped`.
- Focused recommendation/application/TUI tests: `15 passed`.
- Existing first-profile and CLI composition regression set: `61 passed`.
- Ruff formatting: `197 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 121 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Package release install integration: `1 passed` against the exact wheel.
- Distribution policy acceptance:
  - Debian 12 / sudo: passed;
  - Ubuntu 24.04 / sudo: passed;
  - Alpine 3.20 / doas: passed.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `95863bb19627fdbd544a13a0a2c74f446b12ff21cfdb17eb6025704e4b7d0b70`.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- Adding a profile starts with general, low-latency, restricted-network, or
  compatibility intent instead of a flat protocol list.
- Every purpose produces exactly three distinct ordered variants with a visible
  reason and tradeoff.
- Hysteria2 recommendations disclose their UDP dependency and the upstream
  warning about more obvious UDP proxy characteristics.
- Restricted-network recommendations explicitly avoid promising universal
  connectivity or censorship bypass.
- `ProtocolVariant` distinguishes VLESS/VMess WebSocket and gRPC forms without
  changing persisted `ProtocolKind` or transport intent.
- Selecting a recommendation only opens the existing guided form; no desired
  state or host mutation occurs.
- Advanced operators can still select all ten supported variants directly.
- All existing protocol/TLS/transport form journeys remain green through the
  new navigation path.
- Production `ManagerApp` composition exposes the same recommendation advisor
  exercised by the TUI.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this interaction slice.
