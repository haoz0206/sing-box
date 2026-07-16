# Profile pause/resume acceptance — 2026-07-17

## Scope

This record covers the revision-bound, transactional pause/resume slice for an
applied profile. It verifies persistence compatibility, complete configuration
projection, fixed and automatic port behavior, Textual operator journeys,
production composition, package installation, and supported distribution
authorization policies.

## Evidence

- Full local suite: `393 passed, 18 skipped`.
- Ruff formatting: `193 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 119 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed`, including both a paused zero-inbound
  projection and its resumed inbound projection.
- Package release install integration: `1 passed` against the exact wheel.
- Distribution policy acceptance:
  - Debian 12 / sudo: passed;
  - Ubuntu 24.04 / sudo: passed;
  - Alpine 3.20 / doas: passed.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `2eb2400f532df0556033129e1f422c5e6066331839bf9fefb05decc14a6a37b4`.

The full suite's 18 skips are explicit opt-in external checks, chiefly live
systemd/OpenRC host execution and tests requiring separately configured release
inputs.

## Accepted behavior

- `APPLIED` remains lifecycle history; `enabled` records current participation
  in the live configuration.
- Legacy state without `enabled` loads as online.
- Pause preserves stable profile ID, protocol material, endpoint, actual port,
  and port-selection intent while removing only that inbound.
- Resume reuses a fixed port only after preview and under-lock checks; automatic
  resume can select a new port under the lock while excluding other declared
  ports.
- Desired state advances only after a successful complete host transaction.
- Validation, precondition, commit, rollback, and rollback-failure outcomes
  remain distinct and actionable in the TUI.
- Paused profile edits and removal are desired-state-only.

## Remaining external release gates

- Repeat the real-core gate against the upstream stable sing-box 1.14 release;
  this run used `1.14.0-alpha.45` because stable 1.14 is not yet available.
- Run the separately authorized live systemd and OpenRC host smoke harnesses on
  approved recoverable hosts.

These external gates do not invalidate the slice acceptance, but they continue
to block calling the overall project a stable production replacement.
