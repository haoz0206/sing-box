# ADR-0023: Resolve stable and preview core channels before exact activation

Status: Accepted  
Date: 2026-07-17
Amended: 2026-07-18

## Context

Operators want two maintained sing-box tracks without repeatedly copying a
version string from GitHub: the latest stable release and the latest upstream
preview release. GitHub labels every alpha, beta, and release candidate as a
prerelease, so naming the second channel only “beta” would misrepresent the
artifact currently selected. Channel discovery also changes over time, while
the existing acquisition and privileged activation seams require an exact,
reviewable version.

The later acceptance observation on 2026-07-18 resolved stable `1.13.14` and
preview `1.14.0-alpha.47`. These dated values are evidence for acceptance tests
and the software manual, not constants embedded in production policy.

## Decision

1. The application exposes two semantic channels: `stable` and `preview`.
   User-facing copy may explain preview as the requested beta/testing channel,
   but must display the actual alpha, beta, or rc version returned upstream.
2. Stable resolves a published, non-draft release with `prerelease=false` and
   prefers `immutable-release`. When upstream reports Stable as mutable, it may
   use ADR-0003's `digest-pinned-stable` fallback only with the exact official
   asset URL and API SHA-256. Preview resolves a published, non-draft,
   immutable release with `prerelease=true`; mutable Preview artifacts remain
   rejected.
3. Discovery is read-only but requires upstream network access. It returns one
   exact version and channel identity; it never downloads an artifact, installs,
   activates, or edits desired state.
4. A later acquisition plan embeds a `PlannedCoreArtifact`, freezing the
   discovered exact version, architecture, asset name, official URL, SHA-256,
   trust mode, release flags, warning identities, and observed
   active/installed state. Confirmation never authorizes a moving “latest”
   target. Acquisition re-inspects the frozen upstream metadata and rejects
   drift before download.
5. Exact-version acquisition continues through ADR-0003. Preview acquisition
   retains explicit prerelease consent even when discovery originated from the
   preview channel.
6. Installed core releases will be catalogued from manager-owned immutable
   distributions and manifests. Switching channels may atomically select an
   already installed exact target; otherwise the plan acquires and activates
   the frozen channel release. Arbitrary paths and unverified directories are
   never switch candidates.
   Each newly installed distribution contains one schema-versioned manager
   manifest written before the distribution is atomically published. The
   manifest freezes version, architecture, and source SHA-256; all three must
   match the directory identity and a self-verifying `sing-box` binary before
   the release is listed. Pre-manifest distributions may remain active but are
   not silently promoted to retained switch candidates.
   After network-backed channel discovery has generated them, already-current
   and retained-switch plans use only these local manifest identities. Reviewing
   and executing those frozen plans perform no download or upstream access.
7. The TUI must distinguish update, already-current, and retained-release
   switch plans. Confirmed switching is non-returning until typed terminal
   evidence is available, and an unclassified post-confirmation failure remains
   an unknown activation result.
8. Every user-visible channel slice updates `docs/MANUAL.md` in the same commit.
   The manual must not describe planned controls as already available.

## Consequences

- Upstream version movement changes discovery results but cannot change an
  already reviewed plan.
- Stable and preview can evolve independently without hardcoded release values,
  while making their different trust floors explicit.
- The preview channel can currently select an alpha release without calling it
  a beta artifact.
- The channel entry and its planning step still require network discovery. A
  separate local-only entry would be required to promise fully offline switching.
- Existing pre-manifest distributions remain usable but require exact
  reacquisition before they become trusted retained-switch candidates.
- Release discovery, installed-release inspection, network acquisition, and
  privileged switching remain separate seams with distinct failure evidence.

## Rejected alternatives

### Hardcode the current stable and beta versions

Rejected because values become stale and make ordinary upgrades require a code
release.

### Pass `latest` through the privileged helper

Rejected because root would perform network-dependent discovery and the
confirmed target could change after review.

### Treat every prerelease as beta

Rejected because upstream currently publishes alpha releases and the operator
must see the actual compatibility stage.
