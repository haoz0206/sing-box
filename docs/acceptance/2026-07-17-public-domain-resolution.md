# Public domain resolution diagnostics acceptance — 2026-07-17

Audited implementation: the repository state identified by the exact wheel
SHA-256 recorded below.

## Capability verdict

The diagnostics center now resolves every normalized public server address and
TLS server name in one desired-state snapshot before the operator relies on a
certificate or shared client endpoint. Repeated domains are queried once,
literal IP endpoints are counted without DNS, and invalid host text becomes
typed per-domain evidence.

The production inspector uses one isolated Python standard-library worker for
the complete domain batch and enforces one total timeout. It passes domains as
separate process arguments, validates the worker response, performs no writes,
and does not receive credentials or generated configuration. Partial failures
retain successful A/AAAA evidence. DNS failures remain attention findings, so
configuration, core, and runtime action-required findings keep priority.

## Repository-local evidence

- The focused diagnostics behavior, DNS adapter contract, production-composition,
  and Textual journey suites pass: 59 passed.
- The complete pytest suite passes without root or external network
  authorization: 369 passed and 17 opt-in integration cases skipped.
- Behavior coverage includes complete success, complete failure, partial
  failure, unavailable inspection, no public names, IP-only endpoints, stable
  guidance, and preservation of independent runtime evidence.
- Adapter coverage exercises case and terminal-dot normalization, deduplication,
  public and TLS names, literal IP deduplication, malformed URL classification,
  typed result invariants, localhost resolution, and a zero-timeout worker.
- Production composition resolves persisted `localhost` desired state through
  the installed diagnostics graph, while Textual Pilot proves that unresolved
  domain evidence and recovery guidance are visible through user controls.
- Ruff formatting and lint checks pass for all 189 files.
- mypy passes for all 117 source files.
- `git diff --check` passes.
- The complete generated-protocol integration suite passes the real
  `sing-box 1.14.0-alpha.45 check`: 14 passed.
- The wheel and source distribution build successfully.
- The exact wheel SHA-256 is
  `177f1d63d23c5f5e43e9a35033b98bf236b1dbf9791022e969a1cf51e4315881`.
  That wheel passes the isolated package-release install test and the pinned
  Debian 12, Ubuntu 24.04, and Alpine 3.20 package/authorization acceptance.

## Remaining release gates

1. Run the opt-in systemd smoke on approved, recoverable Debian 12 and Ubuntu
   24.04 hosts.
2. Run the opt-in OpenRC smoke on an approved, recoverable Alpine 3.20 host.
3. Repeat the real configuration and artifact suites after upstream publishes
   stable sing-box 1.14. The currently validated artifact is
   `sing-box 1.14.0-alpha.45`.
