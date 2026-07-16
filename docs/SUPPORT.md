# Supported platform matrix

Status: pre-release support contract  
Last updated: 2026-07-16

## Python

The supported interpreter matrix is CPython 3.10 through 3.14. Every push and
pull request runs pytest, Ruff, and mypy across that matrix. The newest matrix
member also builds the wheel and source distribution. PyPy and Python 3.9 or
older are not supported.

## Host operating systems

The manager targets Linux servers reached through a terminal or SSH session.

| Host family | Runtime adapter | Support level |
|---|---|---|
| Debian 12/13 | systemd | target; opt-in host smoke test required before stable release |
| Ubuntu 22.04/24.04 | systemd | target; opt-in host smoke test required before stable release |
| Alpine 3.20+ | OpenRC | target; opt-in host smoke test required before stable release |
| Other Linux | systemd/OpenRC | best effort after adapter contract tests |
| macOS/Windows/BSD | none | unsupported as managed hosts |

Unit, behavior, command, and headless TUI tests remain rootless and
network-independent. Privileged host smoke tests are separate and explicitly
opt in.

The real configuration integration check is also opt in. Point
`SB_MANAGER_REAL_SING_BOX` at a trusted compatible sing-box executable and run:

```bash
.venv/bin/pytest -q -m integration
```

## Host runtime smoke

The host marker exercises the production runtime adapter by refreshing the
configured service and then checking its health. It changes live service state.
Run it only on an approved acceptance host with a recoverable sing-box service:

```bash
SB_MANAGER_HOST_SMOKE=refresh \
SB_MANAGER_HOST_RUNTIME=systemd \
SB_MANAGER_HOST_SERVICE=sing-box.service \
.venv/bin/pytest -q -m host
```

Use `openrc` and service name `sing-box` on Alpine. An alternate command path
can be supplied through `SB_MANAGER_HOST_RUNTIME_BINARY`. Without the exact
`SB_MANAGER_HOST_SMOKE=refresh` authorization, the test skips before invoking
the runtime. Providing this harness is not evidence that a target distribution
has passed; each row remains pending until the command succeeds on that host.

## sing-box

Generated configuration currently targets the sing-box 1.14 pre-release schema
because shared ACME certificate providers use `certificate_provider`. It was
last verified against official `1.14.0-alpha.45` on 2026-07-16. That verification
covers every supported protocol plus both WebSocket and gRPC variants for VLESS
and VMess.

There is no stable 1.14 release at the time of that verification. This is
pre-release compatibility and blocks a stable manager release until sing-box
1.14 becomes stable and the suite passes against it. A future artifact installer
must enforce the accepted core version before apply.
