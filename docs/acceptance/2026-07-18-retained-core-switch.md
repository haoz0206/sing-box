# Retained core catalog and switch acceptance — 2026-07-18

## Scope

This record covers manager-manifested installed-core inventory and the
no-network privileged operation that switches between two exact retained
release identities. It does not claim that Stable/Preview application plans or
TUI channel controls are available yet.

## Accepted behavior

- A newly installed distribution publishes a schema-versioned manager manifest
  before its immutable version directory becomes visible.
- The manifest freezes version, architecture, and source archive SHA-256.
- The read-only catalog lists only real, manifest-backed directories whose
  manifest matches the directory identity and whose `sing-box` binary
  self-verifies the exact version.
- Pre-manifest directories can remain active but are not silently offered as
  retained switch candidates.
- A retained switch receives target and reviewed-active identities, never a
  caller-selected filesystem path.
- Under the shared core lock, switching rechecks both manifests and binaries,
  verifies that `current` still matches the reviewed active identity, and then
  atomically replaces the relative `current` link.
- The helper `switch-core` operation performs no network access and does not
  read an incoming artifact.
- Existing or versions-directory symlinks are rejected before manifest writes
  or activation.

## Evidence

- Focused installation/helper regression set: `30 passed, 1 skipped`.
- Full local suite: `665 passed, 18 skipped in 215.69s`.
- Ruff formatting: `264 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 165 source files`.
- Git whitespace check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `d1d8cb64abba91e8282feee0727ae1c003d3e7225bc14e15a0ae8400eef65cf4`.

The 18 skipped tests remain explicit opt-in external gates for live host,
distribution/package, real sing-box, and official artifact environments.
