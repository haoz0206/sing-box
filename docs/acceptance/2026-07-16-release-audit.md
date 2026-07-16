# Release readiness audit — 2026-07-16

Audited implementation: `adcebbc` (`feat: resume saved drafts from dashboard`).

## Verdict

The repository-local first-release scope is complete and suitable for a
pre-release candidate. A stable manager release remains blocked by two external
acceptance gates: live init-system smoke tests on approved recoverable hosts,
and publication of stable sing-box 1.14.

## Repository-local evidence

- The complete pytest suite passes without root or network authorization.
- Ruff formatting and lint checks pass for the repository.
- mypy passes for all 88 source files.
- `git diff --check` passes.
- The wheel and source distribution build successfully.
- Every generated protocol configuration, including VLESS/VMess WebSocket and
  gRPC variants plus operator-file TLS, passes the real
  `sing-box 1.14.0-alpha.45 check` integration suite: 11 passed and 1 skipped
  host-only case.
- The official artifact acceptance downloads the immutable alpha.45 release,
  verifies and stages it, activates it atomically, and proves rollback.
- The final wheel SHA-256 is
  `0af9c451139288d8c709438e11a81005a0c8280fb8004329fcc5de8586d1a234`.
  That exact wheel passed the pinned Debian 12, Ubuntu 24.04, and Alpine 3.20
  package and authorization acceptance.
- Host policy installation now emits a read-only plan by default and mutates
  only after explicit `--confirm`.
- Reopening the TUI exposes each persisted draft's apply action and sends the
  selected stable profile ID plus current revision through the existing
  confirmation and background-apply path.

## External release gates

1. Run the opt-in systemd smoke on approved Debian 12 and Ubuntu 24.04 hosts
   with a recoverable `sing-box.service`.
2. Run the opt-in OpenRC smoke on an approved Alpine 3.20 host with a
   recoverable `sing-box` service.
3. After upstream publishes stable sing-box 1.14, repeat the real configuration
   and official artifact suites against that stable release. As of this audit,
   upstream's latest validated 1.14 artifact is
   [1.14.0-alpha.45](https://github.com/SagerNet/sing-box/releases/tag/v1.14.0-alpha.45),
   which GitHub marks as a pre-release.

## Deferred after first stable

- Caddy edge orchestration and its separate artifact/runtime trust model.
- Broader profile editing, deletion, and diagnostics-center workflows beyond
  the create, persist, resume, apply, rollback, and core-update release slice.
