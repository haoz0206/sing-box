# Capability-aware operations workspace acceptance — 2026-07-17

## Scope

Move routine operations out of miscellaneous dashboard controls and into one
task-oriented Textual workspace without changing the safety policy of the
existing core-update, service-log, or apply-history workflows.

## Accepted behavior

- The dashboard exposes one `打开运维中心` navigation action and no direct core
  update control.
- `o` opens the operations workspace; the former `c` shortcut no longer jumps
  directly into a host-mutation form.
- Opening the workspace does not plan a core update, read service logs, read
  apply history, or mutate the host.
- Available capabilities are grouped into core management and runtime evidence.
- Missing capabilities render explicit startup-mode explanations and no dead
  buttons.
- Core selection opens the existing exact-version planning form without
  planning or activating anything eagerly.
- Service logs and apply history are read only after their respective controls
  are selected, and continue through their existing bounded, disclosure-safe
  screens.

## Test seam and evidence

- Confirmed Seam A: Textual `App.run_test()` and Pilot only; tests click visible
  controls, press visible shortcuts, and assert mounted screen content.
- Focused operations workspace acceptance: `7 passed`.
- Affected keyboard/core/operations acceptance set: `16 passed`.
- Complete repository suite: `549 passed, 18 skipped`.
- Ruff check passed; Ruff format reported `246 files already formatted`.
- Strict mypy passed for `152 source files`.
- Source distribution and wheel built successfully, both including
  `sb_manager/ui/screens/operations.py`.
- Wheel SHA-256:
  `f5992d9e4123966b3c0bf890725491082ccdd84ba18c77e7140908201282edf9`.

## External release boundary

This navigation slice adds no privileged host mutation. Stable-release status
still requires the separately authorized live systemd/OpenRC host acceptance
and the supported stable sing-box 1.14 release gate.
