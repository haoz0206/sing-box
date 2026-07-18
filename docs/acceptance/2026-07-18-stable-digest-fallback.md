# Official Stable digest fallback and Preview acceptance — 2026-07-18

## Scope and execution time

This acceptance verifies the current official Linux amd64 Stable and trusted
Preview artifacts through the manager's real artifact planning, acquisition,
staging, activation, and rollback path. It was executed on 2026-07-18 in the
Asia/Shanghai project timezone; the explicit execution timestamp is
`2026-07-18T07:27:40Z` UTC.

The authoritative source was the
[SagerNet/sing-box official repository](https://github.com/SagerNet/sing-box)
and its exact-version GitHub Releases API endpoint at
`https://api.github.com/repos/SagerNet/sing-box/releases/tags/v{version}`. The
manager's existing `GitHubArtifactSource.inspect` and `UrllibHttpClient` path
read the official metadata. No headers or raw responses were recorded.

## Authoritative artifact evidence

### Stable

- Version: `1.13.14`
- Asset: `sing-box-1.13.14-linux-amd64.tar.gz`
- Trust mode: `digest-pinned-stable`
- GitHub release immutable: `False`
- GitHub release prerelease: `False`
- SHA-256: `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`

### Preview

- Version: `1.14.0-alpha.47`
- Asset: `sing-box-1.14.0-alpha.47-linux-amd64.tar.gz`
- Trust mode: `immutable-release`
- GitHub release immutable: `True`
- GitHub release prerelease: `True`
- SHA-256: `39387ea20a1b44fc123c106fb4b2cf961b98f5550e55a516f446498a163336e1`

These versions and digests are dated acceptance evidence, not production
constants. Stable and Preview channels continue to discover current releases
dynamically under the production trust policy.

## Commands and observed results

The default deterministic invocation remained opt-in and performed no
download:

```console
rtk .venv/bin/pytest tests/integration/test_official_artifact.py -q -rs
```

Observed result: `1 skipped in 0.05s`; the skip required an explicit
`SB_MANAGER_ARTIFACT_DOWNLOAD=download` authorization.

The exact official Stable acceptance command was:

```console
rtk env SB_MANAGER_ARTIFACT_DOWNLOAD=download SB_MANAGER_ARTIFACT_VERSION=1.13.14 SB_MANAGER_ARTIFACT_ARCHITECTURE=amd64 SB_MANAGER_ARTIFACT_TRUST_MODE=digest-pinned-stable SB_MANAGER_ARTIFACT_SHA256=f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697 .venv/bin/pytest tests/integration/test_official_artifact.py -q -rs
```

Observed result: `1 passed in 5.77s`.

The exact official Preview acceptance command was:

```console
rtk env SB_MANAGER_ARTIFACT_DOWNLOAD=download SB_MANAGER_ARTIFACT_VERSION=1.14.0-alpha.47 SB_MANAGER_ARTIFACT_ARCHITECTURE=amd64 SB_MANAGER_ARTIFACT_ALLOW_PRERELEASE=1 SB_MANAGER_ARTIFACT_TRUST_MODE=immutable-release SB_MANAGER_ARTIFACT_SHA256=39387ea20a1b44fc123c106fb4b2cf961b98f5550e55a516f446498a163336e1 .venv/bin/pytest tests/integration/test_official_artifact.py -q -rs
```

Observed result: `1 passed in 25.96s`.

## What the acceptance proves

For each exact release, the live test proves that:

- planning freezes the official asset metadata, SHA-256, and expected trust
  mode;
- acquisition performs a second metadata inspection which matched the reviewed
  plan during this run;
- the downloaded bytes match the planned SHA-256 digest;
- archive extraction uses the safe staging and distribution validation path;
- the staged `sing-box` binary reports the exact requested version;
- activation switches only an isolated temporary installation root; and
- rollback removes that activation and restores the root to no active target.

The deterministic contract tests in `tests/contracts/test_artifact_source.py`
separately prove that metadata drift between planning and acquisition is
rejected before any artifact download. The live happy-path runs did not induce
metadata drift.

## External nondeterminism boundary

This live acceptance depends on GitHub API and CDN availability, GitHub rate
limits, upstream metadata stability, available bandwidth, TLS, and DNS. A later
run can fail because any of those external conditions changed. The normal
deterministic test suite does not depend on them: without the explicit download
opt-in, this integration test skips before requiring version, architecture, or
trust-mode environment values and before making any network request.

The unrelated untracked `uv.lock` was present during acceptance and remained
untouched. This note does not claim a full-suite result because the full suite
was not run for this acceptance.
