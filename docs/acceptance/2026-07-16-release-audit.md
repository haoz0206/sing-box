# Release readiness audit — 2026-07-16

Audited implementation: the repository state identified by the final wheel
SHA-256 recorded below.

## Verdict

The repository-local first-release scope is complete and suitable for a
pre-release candidate. A stable manager release remains blocked by two external
acceptance gates: live init-system smoke tests on approved recoverable hosts,
and publication of stable sing-box 1.14.

## Repository-local evidence

- The complete pytest suite passes without root or network authorization: 307
  passed and 16 opt-in integration cases skipped.
- Ruff formatting and lint checks pass for the repository.
- mypy passes for all 111 source files.
- `git diff --check` passes.
- The wheel and source distribution build successfully.
- Every generated protocol configuration, including VLESS/VMess WebSocket and
  gRPC variants plus operator-file TLS and the quiescent zero-inbound document
  produced after final-profile removal, passes the real
  `sing-box 1.14.0-alpha.45 check` integration suite: 13 passed, including
  reprojection after an applied-profile name edit.
- The official artifact acceptance downloads the immutable alpha.45 release,
  verifies and stages it, activates it atomically, and proves rollback.
- The final wheel SHA-256 is
  `f89dfff7ea4362485547430a2f70713208bda5237c53d1fe11a6a616e2faabdd`.
  That exact wheel passed the pinned Debian 12, Ubuntu 24.04, and Alpine 3.20
  package and authorization acceptance.
- Host policy installation now emits a read-only plan by default and mutates
  only after explicit `--confirm`.
- Package rollback targets one complete retained release identity, emits a
  read-only plan, requires root confirmation, rechecks immutable release trust
  under the package lock, and atomically switches the stable launchers.
- Reopening the TUI exposes each persisted draft's apply action and sends the
  selected stable profile ID plus current revision through the existing
  confirmation and background-apply path.
- Profile details expose planned removal. Draft removal is desired-state-only;
  applied removal transactionally projects and applies the remaining profiles,
  commits desired state only after host success, and preserves the selected
  profile when validation, commit, runtime health, or rollback does not succeed.
- Profile details expose a prefilled metadata editor. Plans normalize the name
  and public address, bind to one desired-state revision, and explain whether
  confirmation is desired-state-only or requires a complete live transaction;
  every typed failure keeps desired state uncommitted and guides the operator
  toward retry, fresh planning, or exact recovery steps.

## External release gates

1. Run the opt-in systemd smoke on approved Debian 12 and Ubuntu 24.04 hosts
   with a recoverable, initially healthy `sing-box.service`, using the exact
   `refresh:systemd:sing-box.service` confirmation printed by the read-only
   plan.
2. Run the opt-in OpenRC smoke on an approved Alpine 3.20 host with a
   recoverable, initially healthy `sing-box` service, using the exact
   `refresh:openrc:sing-box` confirmation printed by the read-only plan.
3. After upstream publishes stable sing-box 1.14, repeat the real configuration
   and official artifact suites against that stable release. As of this audit,
   upstream's latest validated 1.14 artifact is
   [1.14.0-alpha.45](https://github.com/SagerNet/sing-box/releases/tag/v1.14.0-alpha.45),
   which GitHub marks as a pre-release.

## Deferred after first stable

- Caddy edge orchestration and its separate artifact/runtime trust model.
- Protocol/port/TLS profile editing and diagnostics-center workflows beyond the
  create, metadata edit, persist, resume, apply, planned removal, rollback, and
  core-update release slice.
