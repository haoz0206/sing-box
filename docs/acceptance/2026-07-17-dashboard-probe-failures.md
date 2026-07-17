# Dashboard probe-failure acceptance — 2026-07-17

## Scope

This slice prevents unexpected runtime-health or host-readiness probe exceptions
from crashing the Textual worker or leaving the dashboard indefinitely loading.
It changes only read-only dashboard orchestration and introduces no host effect
or new application/system seam.

## Accepted behavior

- An unexpected runtime-health exception becomes `服务状态：无法检查`.
- An unexpected host-readiness exception becomes `主机准备度：无法检查`.
- The dashboard recommends reinspection instead of inferring that creating or
  applying a profile is the safest next action.
- Raw exception content is not rendered in the UI.
- Detail actions remain disabled when there is no valid report to inspect.
- Runtime and readiness each expose an explicit read-only retry action.
- A successful retry replaces the conservative state with the fresh typed
  report and restores the corresponding detail action.
- Retrying does not mutate configuration, desired state, core artifacts, or the
  managed runtime.

## Verification evidence

- Red evidence: the readiness journey initially failed with
  `textual.worker.WorkerFailed` and remained at `主机准备度：正在检查…`.
- Red evidence: the runtime journey initially had no independent retry action
  and incorrectly enabled stale diagnostics after probe failure.
- Focused failure/recovery journeys: `2 passed`.
- Complete first-profile/dashboard acceptance file: `36 passed`.
- Full test suite: `504 passed, 18 skipped`.
- Ruff format: `239 files already formatted`.
- Ruff lint passed.
- Strict mypy passed for `147 source files`.
- `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `903e595dc48d8e55edd632ee8dc21f4405629db9996a59553dc9cc2bd850a306`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, or runtime adapter changed. Previously accepted real-core,
wheel-install, and Debian 12 / Ubuntu 24.04 / Alpine 3.20 container evidence
therefore remains applicable. Stable sing-box 1.14 verification and authorized
live systemd/OpenRC smoke tests remain external release gates.
