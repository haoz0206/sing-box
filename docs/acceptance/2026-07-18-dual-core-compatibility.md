# Dual-core configuration compatibility acceptance — 2026-07-18

## Scope

This record separates configuration compatibility from artifact acquisition
trust for the current official Stable `1.13.14` and Preview
`1.14.0-alpha.47` releases.

## Root cause and decision

The previous projection used the shared `certificate_provider` structure added
in sing-box 1.14. Stable 1.13.14 rejected that field for every ACME-backed
protocol: the first real-binary run produced `8 failed, 7 passed`. Official
sing-box documentation states that inline `tls.acme` remains accepted in 1.14,
is deprecated there, and is scheduled for removal in 1.16.

ADR-0024 therefore selects the strictly allowlisted inline ACME subset as the
common shape for the current dual-channel compatibility window. The privileged
policy accepts only `domain`, `email`, and `data_directory`, binds the domain to
TLS `server_name`, and fixes the data directory. It does not accept arbitrary
inline ACME capability.

## Evidence

- Current Stable metadata: `v1.13.14`, published, non-draft,
  `prerelease=false`, `immutable=false`.
- Stable amd64 asset digest observed from the official GitHub API and matched
  after download:
  `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697`.
- Stable 1.13.14 safe-staged real-binary configuration suite:
  `15 passed in 0.47s`.
- Current Preview metadata: `v1.14.0-alpha.47`, published, non-draft,
  `prerelease=true`, `immutable=true`.
- Preview official acquisition, digest verification, safe staging, isolated
  activation, and rollback: `1 passed in 5.57s` (repeated with retained
  temporary evidence: `1 passed in 5.77s`).
- Preview 1.14.0-alpha.47 real-binary configuration suite:
  `15 passed in 0.50s`.
- Focused TLS, protocol, privileged-policy, application, and CLI set:
  `58 passed in 1.92s`.
- Complete rootless, network-independent suite:
  `676 passed, 18 skipped in 220.92s`.
- Ruff formatting: `268 files left unchanged`.
- Ruff lint: `All checks passed`.
- mypy source check: `Success: no issues found in 167 source files`.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `816e0d5fdffe54fd96480aa99ed3ef3ec42fdaf63c4667be2eba76380cb16b24`.

## Remaining release boundary

Stable configuration compatibility is accepted, but Stable production network
acquisition is not. ADR-0003 requires an immutable GitHub release, while the
current Stable release reports `immutable=false`. The manager continues to fail
closed. Supporting Stable acquisition requires an explicit trust-policy
decision; this acceptance record does not silently weaken that policy.

The remaining default-suite skips are explicit opt-in package, live-host,
real-binary, and official-artifact gates. The real-binary and Preview artifact
subsets listed above were run explicitly; package and live init-system gates
remain pending.
