# Conservative listener ownership diagnostics acceptance — 2026-07-17

## Scope

This record covers protocol-specific expected listener derivation, the Linux
`/proc` listener/owner adapter, conservative application classification,
diagnostics-center and Textual integration, production composition, package
construction, and supported-distribution installation policy.

## Evidence

- Full local suite: `461 passed, 18 skipped`.
- Focused listener application, adapter, diagnostics, Textual, and production
  composition set: `75 passed`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 135 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Source distribution and wheel build: passed; the wheel contains the listener
  seam, application policy, `/proc` adapter, diagnostics integration, and
  non-markup Textual presentation.
- Package release install integration from the exact wheel: `1 passed`.
- Distribution policy acceptance using host networking for the configured
  host-loopback package proxy:
  - Debian 12 / sudo: passed;
  - Ubuntu 24.04 / sudo: passed;
  - Alpine 3.20 / doas: passed.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `5f2374b1df4cfe1798640e970a7e6e03eefe2df180c44b01ba534c389202efbb`.
- A final CodeGraph cross-check against generated protocol implementations
  caught and removed an incorrect initial UDP expectation for Shadowsocks. The
  accepted mapping now follows its explicit `network: tcp` projection.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- Only enabled profiles in `APPLIED` state create expected runtime endpoints.
  Draft and paused profiles remain valid desired state without a listener.
- VLESS Reality/TLS, VMess TLS, Trojan, AnyTLS, and the current Shadowsocks
  projection expect TCP. Hysteria2 and TUIC expect UDP.
- Duplicate expectations collapse to one endpoint; TCP and UDP on the same
  numeric port remain distinct.
- The production adapter reads TCP/UDP IPv4 and IPv6 kernel tables without a
  subprocess, shell, network call, optional OS package, or init-system branch.
- TCP listen state and unconnected UDP state remain transport-specific. Other
  socket states and ports not requested by the application are ignored.
- IPv4 and IPv6 socket inodes for one endpoint are combined before ownership
  is classified.
- Visible socket inodes are joined to `/proc/<pid>/fd` and bounded process
  names. PID and descriptor traversal have hard limits.
- Every observed inode must have complete process evidence, and every visible
  owner must be exactly `sing-box`, before the result is healthy.
- A missing listener or completely observed foreign owner is action-required.
  Hidden descriptors, inaccessible `/proc`, process races, unresolved owners,
  and scan-limit exhaustion are attention, never false healthy ownership.
- Process names have control characters replaced and length capped before
  entering application diagnostics.
- Textual renders all dynamic diagnostics-center content with markup disabled,
  preserving bracketed process names as literal evidence.
- Diagnostics remain read-only. The slice does not bind ports, restart a
  service, write desired state, invoke the privileged helper, or install host
  inspection tools.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when
  released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this read-only interaction slice.
