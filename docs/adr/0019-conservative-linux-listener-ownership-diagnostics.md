# ADR 0019: Conservative Linux listener ownership diagnostics

- Status: Accepted
- Date: 2026-07-17

## Context

An applied profile records a listener port, and runtime health can prove that
the service is active, but neither fact proves that the expected TCP or UDP
endpoint exists or that sing-box owns it. The existing `SocketPortSource`
answers a different apply-time question: whether a candidate wildcard TCP port
can be bound. Treating a failed bind as runtime ownership would confuse a
legitimate sing-box listener with a foreign conflict and would ignore
transport-specific UDP behavior.

The product needs actionable evidence without adding shell parsing to Textual,
depending on optional `ss`/`netstat` packages, broadening the privileged helper,
or reporting a healthy owner when process descriptors are hidden by host
permissions.

## Decision

Add a separate read-only `ListenerSource` seam. The application supplies only
the transport-specific endpoints derived from enabled, applied profiles. The
mapping follows the generated inbound behavior: VLESS, VMess, Trojan and
AnyTLS expect TCP; Hysteria2 and TUIC expect UDP; the current Shadowsocks 2022
projection explicitly expects TCP. Draft and paused profiles do not imply a
runtime listener.

The Linux adapter reads the kernel's `/proc/net/tcp`, `tcp6`, `udp`, and `udp6`
tables. TCP state `0A` and unconnected UDP state `07` are treated as listeners.
It retains only requested ports, joins IPv4 and IPv6 socket inodes, and maps
those inodes to visible `/proc/<pid>/fd` socket links and the bounded
`/proc/<pid>/comm` process name. It performs no network call, subprocess, shell,
or host mutation. PID and descriptor traversal have hard limits; reaching a
limit degrades ownership completeness instead of blocking the diagnostics
worker or truncating evidence silently.

An endpoint is healthy only when every observed socket inode has complete
process evidence and every owner name is exactly `sing-box`. A missing listener
or completely observed foreign owner is action-required. An inaccessible
socket table, hidden descriptor, process-exit race, scan limit, missing owner,
or partially visible ownership is attention. Merely seeing a listener never
becomes an ownership claim. The application preserves all endpoint details so
an action-required finding can still show adjacent unknown evidence.

Process names are capped and control characters are replaced before they enter
application diagnostics. The diagnostics screen renders every dynamic title,
summary, detail, guidance, and failure message with Textual markup disabled, so
an operator-controlled process name cannot become terminal markup.

Production composition always installs the `/proc` source because supported
systemd and OpenRC targets are Linux. The existing privileged helper allowlist
is unchanged. Hosts that hide root-owned descriptors from the unprivileged TUI
receive an explicit unknown result and guidance to recheck with suitable
read-only visibility; the product does not silently escalate.

## Consequences

- Apply-time availability and runtime ownership remain separate, accurately
  named interfaces.
- The same adapter works on Debian, Ubuntu, and Alpine without an additional
  package or init-system branch.
- Dual-stack and dual-transport listeners are compared as distinct expected
  endpoints while duplicate profile expectations collapse to one host probe.
- Ordinary users may see attention rather than healthy ownership on hardened
  `/proc` mounts. This is honest evidence, not a service-health failure.
- Confirming ownership on such hosts later requires a narrowly designed
  privileged observation request, not a relaxed interpretation in this slice.

## Rejected alternatives

### Reuse bind failure as ownership evidence

Rejected because bind failure proves only unavailability. It cannot identify
the listener, reliably model UDP, or distinguish sing-box from a conflict.

### Parse `ss -lntup` or `netstat`

Rejected because these commands are optional on minimal distributions, their
human output varies, and process identity remains permission-dependent.
Kernel tables provide a stable Linux boundary without a shell or package
dependency.

### Treat every expected listening port as healthy

Rejected because a foreign process can occupy the exact endpoint while the
sing-box service is active but misconfigured.

### Add arbitrary `/proc` reads to the privileged helper

Rejected because the current helper is a fixed mutation protocol. A privileged
observation extension needs its own request schema, output bounds, authorization
policy, and disclosure review.
