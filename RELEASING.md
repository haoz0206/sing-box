# Release Guide

Sing-box Manager uses Semantic Versioning and immutable `vX.Y.Z` Git tags. During the `0.x` phase,
minor releases may contain interface changes; release notes must call them out explicitly.

## Cadence

- Target one feature release each month when the release gates are satisfied; do not publish empty
  calendar-only releases.
- Publish patch releases as needed for regressions and security fixes.
- Use `-alpha.N`, `-beta.N`, or `-rc.N` tags when broader operator evidence is still required.

## Release gates

1. The target change set is on protected `main` and all required CI and security checks pass.
2. `pyproject.toml` contains the intended version and `CHANGELOG.md` moves relevant entries from
   `Unreleased` into a dated version section.
3. Supported Python versions pass unit, behavior, lint, format, typing, build, and wheel smoke tests.
4. Relevant Stable and Preview sing-box binaries pass the opt-in compatibility suite.
5. Required distribution policy and authorized systemd/OpenRC host evidence is recorded.
6. Privileged, compatibility, migration, artifact-trust, and rollback boundaries are documented.

## Publishing

After the release pull request is merged:

```bash
git switch main
git pull --ff-only
git tag -a v0.1.0 -m "Sing-box Manager 0.1.0"
git push origin v0.1.0
```

The tag must canonically match the package version; for example, the SemVer tag `v0.2.0-rc.1`
matches the Python package version `0.2.0rc1`. The protected `Publish GitHub release` workflow
reuses the complete CI matrix, builds wheel and sdist, validates package metadata, creates SHA-256
checksums, records build provenance, and publishes a generated GitHub Release. The `release`
environment should require maintainer approval.

Published tags must never be moved or reused. If a release is incorrect, fix forward with a new
patch version and document rollback or mitigation. PyPI publishing is intentionally out of scope
until a separate trusted-publishing policy is approved.
