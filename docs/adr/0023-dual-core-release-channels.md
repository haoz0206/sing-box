# ADR-0023: Resolve stable and preview core channels before exact activation

Status: Accepted  
Date: 2026-07-17

## Context

Operators want two maintained sing-box tracks without repeatedly copying a
version string from GitHub: the latest stable release and the latest upstream
preview release. GitHub labels every alpha, beta, and release candidate as a
prerelease, so naming the second channel only “beta” would misrepresent the
artifact currently selected. Channel discovery also changes over time, while
the existing acquisition and privileged activation seams require an exact,
reviewable version.

The initial observed releases on 2026-07-17 are stable `1.13.14` and preview
`1.14.0-alpha.46`. These values are evidence for acceptance tests and the
software manual, not constants embedded in production policy.

## Decision

1. The application exposes two semantic channels: `stable` and `preview`.
   User-facing copy may explain preview as the requested beta/testing channel,
   but must display the actual alpha, beta, or rc version returned upstream.
2. Stable resolves only a published, non-draft, immutable release with
   `prerelease=false`. Preview resolves only a published, non-draft, immutable
   release with `prerelease=true`.
3. Discovery is read-only. It returns one exact version and channel identity;
   it never downloads, installs, activates, or edits desired state.
4. A later update plan freezes the discovered exact version, architecture,
   asset name, source, warning identities, and observed active/installed state.
   Confirmation never authorizes a moving “latest” target.
5. Exact-version acquisition continues through ADR-0003. Preview acquisition
   retains explicit prerelease consent even when discovery originated from the
   preview channel.
6. Installed core releases will be catalogued from manager-owned immutable
   distributions and manifests. Switching channels may atomically select an
   already installed exact target; otherwise the plan acquires and activates
   the frozen channel release. Arbitrary paths and unverified directories are
   never switch candidates.
7. The TUI must distinguish update, already-current, and retained-release
   switch plans. Confirmed switching is non-returning until typed terminal
   evidence is available, and an unclassified post-confirmation failure remains
   an unknown activation result.
8. Every user-visible channel slice updates `docs/MANUAL.md` in the same commit.
   The manual must not describe planned controls as already available.

## Consequences

- Upstream version movement changes discovery results but cannot change an
  already reviewed plan.
- Stable and preview can evolve independently without hardcoded release values.
- The preview channel can currently select an alpha release without calling it
  a beta artifact.
- Offline switching is possible only after an exact release has been installed
  and catalogued by the manager.
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
