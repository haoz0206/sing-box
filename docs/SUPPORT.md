# Supported platform matrix

Status: pre-release support contract  
Last updated: 2026-07-18

## Python

The supported interpreter matrix is CPython 3.10 through 3.14. Every push and
pull request runs pytest, Ruff, and mypy across that matrix. The newest matrix
member also builds the wheel and source distribution. PyPy and Python 3.9 or
older are not supported.

## Host operating systems

The manager targets Linux servers reached through a terminal or SSH session.

| Host family | Runtime adapter | Support level |
|---|---|---|
| Debian 12 | systemd | wheel + sudo policy accepted in pinned container; live host smoke pending |
| Debian 13 | systemd | target; acceptance pending |
| Ubuntu 24.04 | systemd | wheel + sudo policy accepted in pinned container; live host smoke pending |
| Ubuntu 22.04 | systemd | target; acceptance pending |
| Alpine 3.20 | OpenRC | wheel + doas policy accepted in pinned container; live host smoke pending |
| Alpine newer than 3.20 | OpenRC | target; acceptance pending |
| Other Linux | systemd/OpenRC | best effort after adapter contract tests |
| macOS/Windows/BSD | none | unsupported as managed hosts |

Unit, behavior, command, and headless TUI tests remain rootless and
network-independent. Privileged host smoke tests are separate and explicitly
opt in.

## Distribution policy acceptance

The pinned-container acceptance installs the built wheel into a root-owned
venv, creates a dedicated non-root operator group, installs a native sudo/doas
policy through `sb-manager-install-policy`, verifies file modes and group
ownership, proves argument-free `-n` access reaches the helper, and proves an
extra helper argument is denied by the authorization layer.

For a release run, prefer a reviewed dependency wheelhouse:

```bash
.venv/bin/python -m build
.venv/bin/python -m sb_manager.release.distro_policy_acceptance \
  --wheel dist/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse
```

`--allow-index` is an explicit alternative for development acceptance. Use
`--network host` only when the configured package proxy is bound to host
loopback. Images are referenced by immutable platform digest in the tool.
Passing this acceptance does not exercise systemd or OpenRC as PID 1 and is not
equivalent to the live runtime smoke below.
The Debian and Ubuntu cases retry transient apt transport failures up to five
times. All cases also retry transient bootstrap package downloads up to five
times with an explicit read timeout. Exhausted retries still fail acceptance.

The real configuration integration check is also opt in. Point
`SB_MANAGER_REAL_SING_BOX` at a trusted compatible sing-box executable and run:

```bash
.venv/bin/pytest -q -m integration
```

The official artifact path has a separate network authorization. In this
example the unprivileged side acquires and hashes the archive, then directly
invokes the root-side activation service logic in an isolated root. That logic
re-copies, re-hashes, safely stages, self-verifies, atomically activates, and
rolls back the current pre-release:

```bash
SB_MANAGER_ARTIFACT_DOWNLOAD=download \
SB_MANAGER_ARTIFACT_VERSION=1.14.0-alpha.47 \
SB_MANAGER_ARTIFACT_ARCHITECTURE=amd64 \
SB_MANAGER_ARTIFACT_ALLOW_PRERELEASE=1 \
SB_MANAGER_ARTIFACT_TRUST_MODE=immutable-release \
SB_MANAGER_ARTIFACT_SHA256=39387ea20a1b44fc123c106fb4b2cf961b98f5550e55a516f446498a163336e1 \
.venv/bin/pytest -q tests/integration/test_official_artifact.py
```

This integration test does not invoke the privileged-helper subprocess or prove
its JSON protocol, EUID check, or sudo/doas authorization. Those boundaries are
covered separately by protocol, adapter, and distribution-policy tests; live
authorization on each target host remains a distinct release acceptance step.

## Host runtime smoke

The packaged acceptance module defaults to a read-only JSON plan. It prints a
confirmation bound to the exact init system and service, plus the recovery
commands, without observing or changing the service:

```bash
.venv/bin/python -m sb_manager.release.host_runtime_acceptance \
  --runtime systemd \
  --service sing-box.service
```

Run the mutating phase only on an approved acceptance host with a recoverable,
already-healthy sing-box service. Copy the exact confirmation from the plan:

```bash
.venv/bin/python -m sb_manager.release.host_runtime_acceptance \
  --runtime systemd \
  --service sing-box.service \
  --confirm-service-refresh refresh:systemd:sing-box.service
```

The command refuses to refresh a service that is not healthy beforehand. It
then refreshes through the production adapter and requires a healthy
postcondition; failures include the adapter's recovery commands. Use `openrc`
and service name `sing-box` on Alpine. An alternate command path can be supplied
through `--runtime-binary`.

The equivalent pytest marker remains available for release automation. Its
authorization value is also bound to the exact runtime and service:

```bash
SB_MANAGER_HOST_SMOKE=refresh:systemd:sing-box.service \
SB_MANAGER_HOST_RUNTIME=systemd \
SB_MANAGER_HOST_SERVICE=sing-box.service \
.venv/bin/pytest -q -m host
```

Without `SB_MANAGER_HOST_SMOKE`, the test skips before inspecting the service.
A mismatched value fails before invoking the runtime. Providing this harness is
not evidence that a target distribution has passed live runtime acceptance;
each row remains pending until the command succeeds on an approved,
recoverable host.

## sing-box

Generated configuration currently uses the strictly allowlisted inline ACME
shape shared by sing-box 1.13 and 1.14. On 2026-07-18 the complete real-binary
suite passed all 15 cases against official Stable `1.13.14` and Preview
`1.14.0-alpha.47`. That covers every supported protocol plus both WebSocket and
gRPC variants for VLESS and VMess. Inline ACME is deprecated in 1.14 and is
scheduled for removal in 1.16, so a version-capability projection is required
before either supported channel reaches 1.16.

Artifact trust remains a separate release gate. On 2026-07-18 the opt-in
official-artifact acceptance passed unprivileged download and exact digest
verification plus direct root-side activation-service re-copying, re-hashing,
safe staging, version self-verification, isolated activation, and rollback for
both current discoveries. It did not traverse the helper subprocess, JSON
protocol, EUID check, or sudo/doas authorization described above.

| Channel | Observed version | Trust mode | Official amd64 SHA-256 |
|---|---|---|---|
| Stable | `1.13.14` | `digest-pinned-stable` | `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697` |
| Preview | `1.14.0-alpha.47` | `immutable-release` | `39387ea20a1b44fc123c106fb4b2cf961b98f5550e55a516f446498a163336e1` |

These are dated acceptance observations, not production constants or a promise
that either channel will retain the same version or digest. Stable used the
reviewed ADR-0003 digest-pinned fallback because GitHub reported
`immutable=false`; Preview remained immutable. Re-running this live acceptance
depends on GitHub API/CDN availability, DNS, TLS, rate limits, upstream metadata
stability, and available bandwidth, so elapsed time and transient failures can
vary independently of deterministic contract tests.

To reproduce the Stable observation, bind both the expected trust mode and the
full digest explicitly:

```bash
SB_MANAGER_ARTIFACT_DOWNLOAD=download \
SB_MANAGER_ARTIFACT_VERSION=1.13.14 \
SB_MANAGER_ARTIFACT_ARCHITECTURE=amd64 \
SB_MANAGER_ARTIFACT_ALLOW_PRERELEASE=0 \
SB_MANAGER_ARTIFACT_TRUST_MODE=digest-pinned-stable \
SB_MANAGER_ARTIFACT_SHA256=f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697 \
.venv/bin/pytest -q tests/integration/test_official_artifact.py
```
