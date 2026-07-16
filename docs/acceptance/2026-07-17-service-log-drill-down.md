# Bounded redacted service-log drill-down acceptance — 2026-07-17

## Scope

This record covers the init-neutral read-only log seam, native systemd and
OpenRC adapters, application-level bounding/control cleaning/credential
redaction, the diagnostics-center drill-down and refresh journey, production
composition, package construction, and supported-distribution installation
policy.

## Evidence

- Full local suite: `445 passed, 18 skipped`.
- Focused service-log behavior, adapter, Textual, and composition set:
  `15 passed`.
- Ruff formatting: `215 files already formatted` after the final format pass.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 132 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Source distribution and wheel build: passed; the wheel contains both log
  adapters, the application policy, the public seam, and the Textual screen.
- Package release install integration from the exact wheel: `1 passed`.
- Direct Alpine 3.20 BusyBox evidence: `logread --help` exposes only `-f` and
  `-F`; the OpenRC adapter therefore uses a no-argument snapshot and local
  literal filtering rather than the unsupported `-e` assumption found during
  the first implementation pass.
- Distribution policy acceptance using host networking for the configured
  host-loopback package proxy:
  - Debian 12 / sudo: passed;
  - Ubuntu 24.04 / sudo: passed;
  - Alpine 3.20 / doas: passed.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `00b53c69b04fe734c30ee1cbdfffe91ce25eb0002629d86023d8bdf7f9dce8f0`.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- The diagnostics center offers “查看近期服务日志” only when a
  `ServiceLogReader` capability is composed. It remains a secondary read-only
  drill-down and does not replace the report's single prioritized action.
- Opening and refreshing the view runs in a Textual worker and asks for the
  latest 200 lines; the UI remains free of subprocess and redaction policy.
- Requests outside 1–500 lines fail before an adapter is called. The
  application reapplies the requested tail bound even when a source returns
  more lines.
- systemd uses the exact read-only `journalctl` unit, line, no-pager, and
  short-ISO/quiet arguments without a shell or follow mode. Its no-entry
  informational marker becomes the same empty typed state as zero output.
- OpenRC calls `logread` without unsupported flags, case-insensitively filters
  the finite syslog snapshot by the literal configured service name, and then
  applies the requested tail bound. Unrelated daemon lines are excluded.
- Both adapters use a five-second command timeout. Missing binaries,
  non-zero commands, permissions, and other observation failures produce typed
  unavailability rather than changing runtime health or the host.
- Both adapters decode UTF-8 with replacement, so malformed bytes remain visible
  as safe replacement characters instead of terminating diagnostics.
- An accessible source with no matching lines is distinct from an inaccessible
  source.
- Persisted Reality, Shadowsocks, Hysteria2, Trojan, AnyTLS, TUIC, VLESS, and
  VMess authentication material is eligible for exact redaction.
- Common password, secret, token, authentication/authorization, credential,
  UUID, private-key, short-ID, URI userinfo, query-value, and JSON key/value
  forms are redacted even when their values are not yet in desired state.
- Adapter failure diagnostics pass through the same disclosure policy.
- ANSI sequences and non-printing controls are removed. Each resulting line,
  including its truncation marker, is at most 4096 characters.
- Textual renders the final log body with markup disabled, reports the source
  and number of redactions, explains empty and unavailable states, and keeps
  explicit retry available.
- Production composition selects `journalctl` for systemd and `logread` for
  OpenRC, honors a literal custom service name and an optional
  `--runtime-log-binary`, and uses the same `JsonFileStateStore` snapshot as the
  rest of the manager.
- The workflow does not call refresh/start/stop, write desired state, invoke
  the privileged helper, follow a journal, or export unrestricted logs.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when
  released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this read-only interaction slice.
