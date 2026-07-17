# Purpose-first profile recommendation acceptance — 2026-07-17

## Scope

This record covers the purpose-first add-profile journey, its pure protocol
recommendation policy, exact protocol/transport variant identity, advanced
direct selection, handoff to every existing guided form, and production package
composition. The follow-up acceptance also covers stable rationale identities,
complete interface-copy-catalog rendering, and same-page recovery from an
unexpected advisor failure.

## Original evidence

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

## Copy-catalog follow-up evidence

- Full local suite: `604 passed, 18 skipped`.
- Focused semantic-policy and Textual Pilot tests: `18 passed`.
- Ruff formatting: `259 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 161 source files`.
- Git whitespace check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `aa3b6bb5f15e71c94e3f393cd5719c94a6924e2b072c044d315fd405ec400c77`.

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
- Application recommendation reports contain stable variant and rationale
  identities rather than locale-authored reason and tradeoff strings.
- Purpose, ranking, reason/tradeoff, error, recovery-action, and all ten direct
  choice labels flow from one validated copy catalog with exact placeholder
  validation.
- An unexpected advisor failure hides the exception and offers direct protocol
  selection on the recovery page; a selected variant still opens its existing
  guided form.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this interaction slice.
