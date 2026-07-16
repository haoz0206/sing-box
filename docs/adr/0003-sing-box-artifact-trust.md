# ADR-0003: Trust exact immutable sing-box release artifacts

Status: Accepted  
Date: 2026-07-16

## Context

The manager needs to acquire sing-box without turning a privileged update into
an implicit remote-code execution path. "Latest" is not reproducible,
prereleases require deliberate consent, archives can contain unsafe paths, and
TLS alone does not prove that downloaded bytes match the published asset.

GitHub's Releases API exposes an asset `digest` such as `sha256:...`. Immutable
releases lock their tag and assets and provide release attestations:

- <https://docs.github.com/en/rest/releases/releases>
- <https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases>

## Decision

The initial network source is the official `SagerNet/sing-box` GitHub Releases
repository. Acquisition follows these rules:

1. The request names an exact version and supported Linux Go architecture.
   There is no implicit `latest` request.
2. A prerelease is rejected unless the request explicitly permits it.
3. The release must be published, non-draft, and immutable.
4. Exactly one expected asset name must exist:
   `sing-box-{version}-linux-{architecture}.tar.gz`.
5. The API must provide a `sha256` digest. Missing, malformed, or unsupported
   digests fail closed.
6. Downloaded bytes are hashed and compared with constant-time equality before
   any archive member is read or executable is run.
7. Staging reads only regular files below the archive's single expected root.
   It never calls unrestricted `extractall`, and rejects links, absolute paths,
   traversal, duplicate core binaries, and a missing core binary.
8. The staged `sing-box` executable must self-report the requested version
   before it can cross the privileged installation seam.
9. Acquisition and staging run without root. A later minimal privileged seam
   performs the atomic host replacement from a verified staged manifest.

The first supported architectures are `amd64` and `arm64`. Platform expansion
requires fixture and host evidence before adding another enum member.

## Consequences

- Updates are reproducible and auditable by version, asset name, and digest.
- GitHub metadata and asset delivery are both required; offline installation
  will use a separate local-file adapter with an operator-supplied digest.
- Older mutable releases or releases without API digests are intentionally
  unsupported by the network adapter.
- The manager cannot silently follow upstream prereleases.
- Privilege is not required for network access, parsing, hashing, extraction,
  or binary inspection.

## Rejected alternatives

### Execute the upstream install script

Rejected because it combines discovery, download, host mutation, and privilege
without preserving a typed plan or manager-owned rollback boundary.

### Trust HTTPS without an asset digest

Rejected because transport security does not bind downloaded bytes to the
release metadata selected by the operator.

### Download the latest release automatically

Rejected because the result changes over time and can cross stable/prerelease
or compatibility boundaries without an explicit plan.
