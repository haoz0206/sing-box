# Stable Digest-Pinned Fallback Design

**Status:** Approved direction, awaiting written-spec review  
**Date:** 2026-07-18  
**Scope:** Python TUI core update workflow for official sing-box Stable and Preview channels

## Decision

Add a digest-pinned fallback for an official, published, non-draft Stable release when GitHub reports that release as non-immutable. The application freezes the exact version, architecture, asset name, download URL, and API-provided SHA-256 before asking the user to confirm. Execution accepts only those reviewed values and verifies the downloaded bytes against the frozen digest.

Immutable releases remain the preferred path. Preview keeps its existing immutable-release requirement; a mutable prerelease is never accepted by this fallback.

## Problem

The current Stable release, `v1.13.14`, is published and provides a per-asset SHA-256 through GitHub, but GitHub reports `immutable=false`. The current acquisition policy rejects it, so the Stable channel is unavailable even though the generated configuration has been verified against both supported core lines.

Simply allowing a mutable release would create a moving target. Today, acquisition can re-fetch release metadata after planning; if the upstream asset changes between review and download, the user would no longer be executing the artifact they approved. The update plan therefore needs to carry immutable evidence of the intended bytes, even when the hosting release object is mutable.

## Goals

- Keep automatic latest-Stable discovery usable with the current official release.
- Freeze byte identity before confirmation: exact version, architecture, asset, URL, and SHA-256.
- Make the weaker release-level guarantee visible and require explicit confirmation.
- Reject upstream metadata drift rather than silently replacing a reviewed plan.
- Preserve the immutable Preview path without relaxing prerelease policy.
- Keep network access out of the privileged helper.
- Preserve archive safety, binary self-version verification, activation, and rollback guarantees.
- Define public test seams suitable for TDD and sustainable maintenance.

## Non-goals

- Accepting drafts, unpublished releases, or mutable prereleases.
- Accepting arbitrary repositories, URLs, asset names, or caller-provided remote digests.
- Treating a digest-pinned mutable release as equivalent to a GitHub immutable release.
- Weakening archive traversal checks, executable validation, installed-manifest integrity, or privileged-helper validation.
- Adding a general-purpose package manager or a mirror trust system.

## Domain Model and Interfaces

Introduce a frozen artifact-evidence value owned by the application layer:

```python
@dataclass(frozen=True)
class PlannedCoreArtifact:
    version: CoreVersion
    architecture: CoreArchitecture
    asset_name: str
    download_url: str
    sha256: Sha256Digest
    trust_mode: CoreArtifactTrustMode
    release_immutable: bool
    prerelease: bool


class CoreArtifactTrustMode(Enum):
    IMMUTABLE_RELEASE = "immutable-release"
    DIGEST_PINNED_STABLE = "digest-pinned-stable"
```

The artifact-source boundary becomes explicitly two-phase:

```python
class CoreArtifactSource(Protocol):
    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact: ...

    def acquire(
        self,
        artifact: PlannedCoreArtifact,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact: ...
```

`inspect` resolves and validates official metadata, then returns all evidence that must survive confirmation. `acquire` receives that evidence rather than a looser version request. It revalidates upstream metadata and the downloaded bytes against the frozen object.

`CoreUpdateService.plan` calls `inspect` and embeds `PlannedCoreArtifact` in `CoreUpdatePlan`. Both exact-version and channel workflows use the same planning path. Channel discovery remains responsible only for selecting the allowed Stable or Preview version; artifact inspection remains responsible for byte identity and transport trust. This keeps release-policy and artifact-integrity responsibilities separate without duplicating acquisition logic.

The plan exposes a structured warning identity, `DIGEST_PINNED_MUTABLE_RELEASE`, rather than presentation text. The TUI owns wording and localization; the application owns when confirmation is mandatory.

## Trust Policy

### Immutable release path

The existing policy remains authoritative:

- official sing-box repository;
- published, non-draft release;
- expected tag, architecture, asset name, and browser-download URL;
- valid API-provided SHA-256;
- release reported immutable;
- downloaded bytes match the inspected SHA-256.

Stable or Preview may use this stronger path when their release is immutable.

### Digest-pinned Stable fallback

The fallback is allowed only when every condition below holds:

- the source is the hard-coded official sing-box repository;
- the release is published and not a draft;
- `prerelease=false`, so the artifact belongs to Stable policy;
- the tag exactly matches the requested version;
- the asset name exactly matches the expected operating system and architecture;
- the browser-download URL exactly matches the expected official release URL;
- GitHub API metadata supplies a syntactically valid SHA-256 digest;
- the plan records `release_immutable=false` and `DIGEST_PINNED_STABLE`.

Caller-supplied URLs or digests cannot create this trust mode. The HTTP adapter derives all evidence from the official API response and validates it against local expectations.

Before downloading, `acquire` re-fetches the exact tag metadata and requires version, prerelease status, draft/published status, asset name, URL, digest, and immutable flag to equal the frozen plan. Any difference is metadata drift and stops the operation before host mutation. After downloading, the byte hash must equal the same frozen SHA-256. This second check detects replacement after the metadata revalidation request.

A mutable prerelease is rejected, including when it has a digest. Preview therefore remains protected by the immutable-release requirement.

## User Interaction

The review screen displays:

- channel and exact version;
- target architecture;
- exact asset name;
- full frozen SHA-256;
- trust mode;
- a warning that the Stable release is not immutable upstream, while this operation is pinned to the displayed digest.

The digest-pinned fallback always requires explicit confirmation. Confirmation authorizes only the frozen plan, not “whatever is currently latest.” If metadata drifts or the hash differs, the application reports that the reviewed artifact changed and asks the user to plan again. It does not retry execution with new evidence.

Already-current and retained-offline-switch flows stay unchanged. A retained artifact already has locally verified identity and its plan continues to display its exact digest.

Failures remain classified by mutation boundary:

- planning, metadata drift, download, digest mismatch, staging, or binary self-check: no host mutation; safe to retry by creating a fresh plan;
- privileged activation or helper communication failure: host result may be unknown and must not be described as safely retryable without reconciliation.

## Non-blocking TUI Planning

Artifact inspection adds network I/O to planning. The exact-version form currently invokes planning synchronously, so both exact-version and channel planning must run through a Textual worker.

While planning, the initiating control is disabled and the screen shows progress without exposing secrets. Completion opens the review screen with the frozen evidence. A planning error restores controls and shows a bounded, actionable error. Leaving the screen or superseding a request prevents stale worker results from opening a confirmation screen.

No network request occurs after confirmation inside the privileged helper. The unprivileged application downloads and verifies the exact artifact, stages it, and passes only verified local inputs to the helper.

## End-to-End Data Flow

```text
choose channel or exact version
  -> resolve allowed version and architecture
  -> inspect official release metadata and asset
  -> validate policy and freeze PlannedCoreArtifact
  -> display version, asset, digest, trust warning
  -> explicit user confirmation
  -> re-fetch exact metadata and compare with frozen evidence
  -> download and hash bytes against frozen SHA-256
  -> safely extract, stage, and verify binary self-version
  -> invoke no-network privileged activation
  -> reconcile manifest and report the final state
```

At no point may a later stage substitute a newer version, different asset, changed URL, or changed digest into the confirmed plan.

## TDD Seams and Test Strategy

Tests are written before each implementation slice and exercise public behavior.

### HTTP adapter contract seam

- accepts an official non-immutable Stable release with a valid API digest;
- retains the immutable path for Stable and Preview;
- rejects drafts, unpublished releases, wrong tags, unexpected assets, unexpected URLs, absent/invalid digests, and mutable prereleases;
- rejects metadata drift in any frozen field before download;
- rejects downloaded bytes that differ from the frozen digest;
- returns typed evidence and typed failures without leaking transport details upward.

### Application planning seam

- `CoreUpdatePlan` contains the complete frozen artifact and trust mode;
- digest-pinned Stable produces the structured warning and requires confirmation;
- acquisition receives the exact evidence object from the confirmed plan;
- a stale or altered plan cannot be executed;
- retained and already-current behavior remains unchanged.

### TUI Pilot seam

- exact-version and channel planning remain responsive while inspection runs;
- controls are disabled and restored correctly;
- the review screen renders version, architecture, asset, full digest, and warning;
- no acquisition or activation occurs before confirmation;
- cancellation and stale workers do not execute or open obsolete review screens;
- drift/hash failures use the safe pre-mutation message, while helper failures retain unknown-result wording.

### Official artifact integration seam

- acquire the current official Stable artifact in an isolated destination and prove version, digest, archive safety, and rollback behavior;
- retain the current immutable Preview artifact integration as a regression test;
- keep external release tests explicitly separated from deterministic local unit and contract suites.

## Error Model

Add stable, typed application errors for:

- unsupported mutable prerelease;
- missing or invalid official asset digest;
- frozen release metadata changed;
- downloaded artifact digest mismatch;
- planning superseded or cancelled where the UI needs to suppress stale results.

User-facing messages identify the failed stage and next safe action. Logs may include version, asset name, URL host/path, expected digest, and observed digest, but never credentials, authorization headers, or raw API responses.

## Documentation and Architecture Records

The implementation change updates, in the same logical series:

- ADR-0003 to supersede the blanket rejection of non-immutable releases with the tightly scoped Stable fallback;
- ADR-0023 to record the two-phase frozen-evidence plan/acquire interface;
- `docs/SDD.md` for trust boundaries, domain objects, workers, and error semantics;
- `docs/MANUAL.md` for the warning, digest review, confirmation, and retry guidance;
- `docs/SUPPORT.md` for Stable/Preview policy and known upstream constraints;
- acceptance evidence for both official channels.

Existing installed manifests already store artifact digests, so no persistent-data migration is required.

## Implementation Slices

1. Add failing domain and application tests for frozen evidence, trust modes, and confirmation policy.
2. Introduce the typed evidence model and two-phase artifact-source interface.
3. Add failing HTTP contract tests, then implement immutable and digest-pinned Stable inspection/acquisition.
4. Add failing exact-version and channel application tests, then carry evidence unchanged through plan and execution.
5. Add failing TUI Pilot tests, then move exact-version inspection to a worker and render the review warning.
6. Run isolated official Stable and Preview artifact acceptance tests.
7. Update ADRs, SDD, manual, support matrix, and acceptance evidence.
8. Run formatting, lint, type checking, deterministic tests, external integration tests, and package build before the final implementation commit.

Each slice should produce a focused, reviewable commit once its tests and documentation are coherent. No slice may relax the privileged-helper boundary.

## Acceptance Criteria

- The latest official Stable can be planned when `immutable=false` only through `DIGEST_PINNED_STABLE`.
- Preview still rejects any non-immutable prerelease.
- The plan freezes exact version, architecture, asset name, URL, SHA-256, and trust metadata before confirmation.
- The TUI displays the full digest and an explicit mutable-release warning, and requires confirmation.
- Exact-version and channel inspection do not block the Textual event loop.
- Execution revalidates all frozen metadata and rejects any drift before host mutation.
- Downloaded bytes must match the frozen SHA-256.
- The privileged helper performs no networking and receives only verified local artifacts.
- Existing archive, binary-version, activation, rollback, and manifest-integrity checks remain enforced.
- Deterministic unit, contract, application, and TUI suites pass.
- Isolated official-artifact tests pass for the supported Stable and Preview releases.
- User and developer documentation describe the same trust model and recovery behavior as the code.

## Security Rationale

This design does not make a mutable release immutable. It makes a single reviewed operation content-addressed: confirmation binds execution to one digest, and execution fails closed if upstream metadata or bytes diverge. GitHub release immutability remains stronger because it also constrains the publisher's release object; that stronger signal stays preferred and mandatory for Preview. The Stable fallback is deliberately narrow, visible, auditable, and isolated from privileged network access.
