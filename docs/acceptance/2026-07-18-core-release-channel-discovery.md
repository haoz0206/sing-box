# Core release channel discovery acceptance — 2026-07-18

## Scope

This record covers read-only resolution of the official sing-box stable and
preview channels to one exact trusted release. It does not cover installed-core
inventory, update planning, activation, retained-release switching, or TUI
channel controls.

## Accepted behavior

- `stable` resolves the official latest published, non-draft, immutable,
  non-prerelease release to one exact version.
- `preview` scans the official release listing in upstream order and resolves
  the first published, non-draft, immutable prerelease. Stable, draft, and
  mutable entries are not candidates.
- Preview preserves the actual upstream alpha, beta, or release-candidate
  version string instead of labelling every prerelease as beta.
- Discovery validates the upstream `v` tag as a semantic artifact version and
  fails closed for malformed or unpublished metadata.
- Discovery calls only the JSON metadata boundary. It performs no artifact
  download, filesystem mutation, installation, activation, or privileged work.
- Current observed release numbers remain documentation evidence rather than
  constants in production discovery policy.

## Evidence

- Artifact source contract suite: `13 passed`.
- Full local suite: `659 passed, 18 skipped in 216.61s`.
- Ruff formatting: `263 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 164 source files`.
- Git whitespace check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `b0ea9ad6784ff753bed8b9911fe3c225f96b3a5faf93252dab984b8d79801821`.

The 18 skipped tests remain explicit opt-in external gates for live host,
distribution/package, real sing-box, and official artifact environments.
