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

## sing-box

Generated configuration targets sing-box 1.14 or newer because shared ACME
certificate providers use the 1.14 `certificate_provider` schema. A future
artifact installer must enforce this minimum before apply.
