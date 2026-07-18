# Stable Digest-Pinned Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Python TUI safely discover, review, acquire, and activate the latest official Stable release even when GitHub marks it mutable, while keeping Preview immutable-only and binding every confirmed operation to frozen artifact evidence.

**Architecture:** Add a typed `PlannedCoreArtifact` at the artifact-source seam, split the GitHub adapter into `inspect` and `acquire`, and embed the inspected evidence in `CoreUpdatePlan`. Exact-version and channel screens render the same digest/trust evidence; all network planning runs in Textual workers, while the privileged helper remains local-only and unchanged.

**Tech Stack:** Python 3.12+, frozen dataclasses and protocols, Textual worker/Pilot APIs, urllib HTTP adapter, pytest/pytest-asyncio, Ruff, mypy strict, setuptools build.

**Approved design:** `docs/superpowers/specs/2026-07-18-stable-digest-fallback-design.md`

---

## File Map

- `src/sb_manager/seams/artifact_source.py`: trusted artifact evidence, trust modes, typed trust failures, and the final two-phase protocol.
- `src/sb_manager/adapters/github_artifacts.py`: official release discovery, metadata inspection, drift detection, download, and byte verification.
- `src/sb_manager/application/core_update.py`: consent policy, frozen update plans, channel plan composition, and pre-/post-mutation failure classification.
- `src/sb_manager/ui/core_artifact_copy.py`: shared mapping from artifact trust/warning identities to semantic copy keys.
- `src/sb_manager/ui/copy_catalog.py`: validated Simplified Chinese planning, trust, digest, progress, and recovery messages.
- `src/sb_manager/ui/screens/core_update.py`: non-blocking exact-version planning and frozen evidence review.
- `src/sb_manager/ui/screens/core_channels.py`: channel review of the same exact artifact evidence.
- `tests/contracts/test_artifact_source.py`: GitHub metadata and download contract.
- `tests/behavior/test_core_update.py`: application plan/execute behavior.
- `tests/behavior/test_core_channels.py`: channel composition and frozen exact-update propagation.
- `tests/acceptance/test_core_update_journey.py`: exact-version Textual Pilot journey and worker behavior.
- `tests/acceptance/test_core_channel_journey.py`: Stable/Preview review evidence in Textual Pilot.
- `tests/integration/test_official_artifact.py`: opt-in official artifact acquisition, activation, and rollback.
- `docs/adr/0003-sing-box-artifact-trust.md`: scoped exception to immutable-only release policy.
- `docs/adr/0023-dual-core-release-channels.md`: final Stable/Preview discovery and confirmation policy.
- `docs/SDD.md`: interfaces, trust boundaries, workers, and typed failures.
- `docs/MANUAL.md`: operator review, confirmation, failure, and retry guidance.
- `docs/SUPPORT.md`: supported channels and verified upstream evidence.
- `docs/acceptance/2026-07-18-stable-digest-fallback.md`: commands and evidence from both official channels.

## Task 1: Trusted Artifact Evidence Values

**Model tier:** Medium or lower; isolated value objects and deterministic tests.

**Files:**
- Modify: `src/sb_manager/seams/artifact_source.py`
- Modify: `tests/contracts/test_artifact_source.py`

- [ ] **Step 1: Write failing value-object tests**

Import `replace` from `dataclasses`, then append imports for `CoreArtifactTrustMode` and `PlannedCoreArtifact`, and add:

```python
def planned_artifact(
    *,
    trust_mode: CoreArtifactTrustMode = CoreArtifactTrustMode.IMMUTABLE_RELEASE,
    immutable: bool = True,
    prerelease: bool = False,
) -> PlannedCoreArtifact:
    version = "1.14.0-alpha.47" if prerelease else "1.13.14"
    asset_name = f"sing-box-{version}-linux-amd64.tar.gz"
    return PlannedCoreArtifact(
        version=version,
        architecture=ArtifactArchitecture.AMD64,
        asset_name=asset_name,
        download_url=(
            f"https://github.com/SagerNet/sing-box/releases/download/v{version}/{asset_name}"
        ),
        sha256="a" * 64,
        trust_mode=trust_mode,
        release_immutable=immutable,
        prerelease=prerelease,
    )


def test_planned_artifact_accepts_consistent_immutable_evidence() -> None:
    artifact = planned_artifact(prerelease=True)

    assert artifact.trust_mode is CoreArtifactTrustMode.IMMUTABLE_RELEASE
    assert artifact.release_immutable is True
    assert artifact.prerelease is True


def test_planned_artifact_accepts_digest_pinned_stable_evidence() -> None:
    artifact = planned_artifact(
        trust_mode=CoreArtifactTrustMode.DIGEST_PINNED_STABLE,
        immutable=False,
    )

    assert artifact.sha256 == "a" * 64


@pytest.mark.parametrize(
    ("trust_mode", "immutable", "prerelease"),
    (
        (CoreArtifactTrustMode.IMMUTABLE_RELEASE, False, False),
        (CoreArtifactTrustMode.DIGEST_PINNED_STABLE, True, False),
        (CoreArtifactTrustMode.DIGEST_PINNED_STABLE, False, True),
    ),
)
def test_planned_artifact_rejects_inconsistent_trust_evidence(
    trust_mode: CoreArtifactTrustMode,
    immutable: bool,
    prerelease: bool,
) -> None:
    with pytest.raises(ValueError, match="trust evidence"):
        planned_artifact(
            trust_mode=trust_mode,
            immutable=immutable,
            prerelease=prerelease,
        )


def test_planned_artifact_rejects_an_invalid_digest() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        replace(planned_artifact(), sha256="not-a-digest")
```

- [ ] **Step 2: Run the new tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/contracts/test_artifact_source.py -q
```

Expected: collection fails because the new evidence types are not defined.

- [ ] **Step 3: Add the evidence types and typed errors**

In `src/sb_manager/seams/artifact_source.py`, add these definitions after `ArtifactTrustError` and before `VerifiedCoreArtifact`:

```python
class MutablePrereleaseArtifactError(ArtifactTrustError):
    """A prerelease cannot use the mutable Stable fallback."""


class ArtifactDigestUnavailableError(ArtifactTrustError):
    """Official metadata has no usable SHA-256 for the expected asset."""


class ArtifactMetadataChangedError(ArtifactTrustError):
    """Upstream evidence no longer matches the operator-reviewed plan."""


class CoreArtifactTrustMode(str, Enum):
    """Release-level guarantee used to bind one reviewed artifact."""

    IMMUTABLE_RELEASE = "immutable-release"
    DIGEST_PINNED_STABLE = "digest-pinned-stable"


@dataclass(frozen=True, slots=True)
class PlannedCoreArtifact:
    """Exact official artifact evidence frozen before operator confirmation."""

    version: str
    architecture: ArtifactArchitecture
    asset_name: str
    download_url: str
    sha256: str
    trust_mode: CoreArtifactTrustMode
    release_immutable: bool
    prerelease: bool

    def __post_init__(self) -> None:
        CoreArtifactRequest(version=self.version, architecture=self.architecture)
        if re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None:
            raise ValueError("Planned artifact SHA-256 is invalid")
        trust_is_consistent = (
            self.trust_mode is CoreArtifactTrustMode.IMMUTABLE_RELEASE
            and self.release_immutable
        ) or (
            self.trust_mode is CoreArtifactTrustMode.DIGEST_PINNED_STABLE
            and not self.release_immutable
            and not self.prerelease
        )
        if not trust_is_consistent:
            raise ValueError("Planned artifact trust evidence is inconsistent")
```

Update `VerifiedCoreArtifact`'s docstring from “immutable release metadata” to “the frozen artifact evidence.” Do not change the acquisition protocol yet; this keeps the commit independently green.

- [ ] **Step 4: Run focused verification and prove GREEN**

Run:

```bash
rtk .venv/bin/pytest tests/contracts/test_artifact_source.py -q
rtk .venv/bin/ruff check src/sb_manager/seams/artifact_source.py tests/contracts/test_artifact_source.py
rtk .venv/bin/mypy src
```

Expected: all artifact-source tests pass, Ruff reports no errors, and mypy reports no issues.

- [ ] **Step 5: Commit the evidence values**

```bash
rtk git add src/sb_manager/seams/artifact_source.py tests/contracts/test_artifact_source.py
rtk git commit -m "feat: model frozen core artifact evidence"
```

## Task 2: Official GitHub Metadata Inspection

**Model tier:** Standard; security-sensitive adapter contract with several metadata invariants.

**Files:**
- Modify: `src/sb_manager/adapters/github_artifacts.py`
- Modify: `tests/contracts/test_artifact_source.py`

- [ ] **Step 1: Make the fake HTTP client support ordered metadata responses**

Replace `FakeHttpClient.__init__` and `get_json` with:

```python
class FakeHttpClient:
    def __init__(
        self,
        *,
        metadata: object,
        payload: bytes,
        later_metadata: tuple[object, ...] = (),
    ) -> None:
        self._metadata_responses = [metadata, *later_metadata]
        self._payload = payload
        self.json_urls: list[str] = []
        self.downloads: list[tuple[str, Path]] = []

    def get_json(self, url: str) -> object:
        self.json_urls.append(url)
        index = min(len(self.json_urls) - 1, len(self._metadata_responses) - 1)
        return self._metadata_responses[index]
```

Keep `download` unchanged.

- [ ] **Step 2: Write failing inspection-policy tests**

Import `ArtifactDigestUnavailableError`, `CoreArtifactTrustMode`, and `MutablePrereleaseArtifactError` from the seam, then add a `release_metadata` helper and the following tests:

```python
def release_metadata(
    *,
    version: str,
    prerelease: bool,
    immutable: bool,
    digest: str,
) -> dict[str, object]:
    asset_name = f"sing-box-{version}-linux-amd64.tar.gz"
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": prerelease,
        "immutable": immutable,
        "published_at": "2026-07-18T00:00:00Z",
        "assets": [
            {
                "name": asset_name,
                "browser_download_url": (
                    "https://github.com/SagerNet/sing-box/releases/download/"
                    f"v{version}/{asset_name}"
                ),
                "digest": f"sha256:{digest}",
            }
        ],
    }


def test_inspect_freezes_nonimmutable_stable_asset_evidence() -> None:
    version = "1.13.14"
    digest = "f" * 64
    http = FakeHttpClient(
        metadata=release_metadata(
            version=version,
            prerelease=False,
            immutable=False,
            digest=digest,
        ),
        payload=b"unused",
    )

    artifact = GitHubArtifactSource(http_client=http).inspect(
        CoreArtifactRequest(version=version, architecture=ArtifactArchitecture.AMD64)
    )

    assert artifact.version == version
    assert artifact.sha256 == digest
    assert artifact.trust_mode is CoreArtifactTrustMode.DIGEST_PINNED_STABLE
    assert artifact.release_immutable is False
    assert artifact.prerelease is False
    assert http.downloads == []


def test_inspect_keeps_immutable_preview_on_the_stronger_path() -> None:
    version = "1.14.0-alpha.47"
    http = FakeHttpClient(
        metadata=release_metadata(
            version=version,
            prerelease=True,
            immutable=True,
            digest="e" * 64,
        ),
        payload=b"unused",
    )

    artifact = GitHubArtifactSource(http_client=http).inspect(
        CoreArtifactRequest(
            version=version,
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    )

    assert artifact.trust_mode is CoreArtifactTrustMode.IMMUTABLE_RELEASE
    assert artifact.prerelease is True


def test_inspect_rejects_a_mutable_prerelease() -> None:
    version = "1.14.0-beta.1"
    http = FakeHttpClient(
        metadata=release_metadata(
            version=version,
            prerelease=True,
            immutable=False,
            digest="d" * 64,
        ),
        payload=b"unused",
    )

    with pytest.raises(MutablePrereleaseArtifactError):
        GitHubArtifactSource(http_client=http).inspect(
            CoreArtifactRequest(
                version=version,
                architecture=ArtifactArchitecture.AMD64,
                allow_prerelease=True,
            )
        )


@pytest.mark.parametrize(
    ("override", "diagnostic"),
    (
        ({"tag_name": "v1.13.13"}, "tag"),
        ({"published_at": None}, "published"),
        ({"draft": True}, "draft"),
        ({"prerelease": True}, "classification"),
        ({"immutable": None}, "immutable"),
    ),
)
def test_inspect_rejects_inconsistent_release_metadata(
    override: dict[str, object],
    diagnostic: str,
) -> None:
    metadata = release_metadata(
        version="1.13.14",
        prerelease=False,
        immutable=False,
        digest="c" * 64,
    )
    metadata.update(override)
    http = FakeHttpClient(metadata=metadata, payload=b"unused")

    with pytest.raises(ArtifactTrustError, match=diagnostic):
        GitHubArtifactSource(http_client=http).inspect(
            CoreArtifactRequest(
                version="1.13.14",
                architecture=ArtifactArchitecture.AMD64,
            )
        )
```

Change the existing missing/invalid digest assertions to expect `ArtifactDigestUnavailableError`.

- [ ] **Step 3: Run inspection tests and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/contracts/test_artifact_source.py -q
```

Expected: failures report that `GitHubArtifactSource.inspect` does not exist and digest errors use the broad type.

- [ ] **Step 4: Implement read-only inspection without changing acquisition**

Import `ArtifactDigestUnavailableError`, `CoreArtifactTrustMode`, `MutablePrereleaseArtifactError`, and `PlannedCoreArtifact`, then add this method structure in `src/sb_manager/adapters/github_artifacts.py`:

```python
from sb_manager.seams.artifact_source import (
    ArtifactDigestUnavailableError,
    CoreArtifactTrustMode,
    MutablePrereleaseArtifactError,
    PlannedCoreArtifact,
)

def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact:
    metadata = self._release_metadata(request, require_immutable=False)
    asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
    asset = self._find_asset(metadata, asset_name)
    sha256 = self._sha256(asset)
    download_url = self._download_url(asset, request=request, asset_name=asset_name)
    immutable = metadata["immutable"]
    prerelease = metadata["prerelease"]
    if not isinstance(immutable, bool) or not isinstance(prerelease, bool):
        raise ArtifactTrustError("Release immutable/prerelease metadata is invalid")
    if not immutable and prerelease:
        raise MutablePrereleaseArtifactError("Mutable prereleases are not trusted")
    return PlannedCoreArtifact(
        version=request.version,
        architecture=request.architecture,
        asset_name=asset_name,
        download_url=download_url,
        sha256=sha256,
        trust_mode=(
            CoreArtifactTrustMode.IMMUTABLE_RELEASE
            if immutable
            else CoreArtifactTrustMode.DIGEST_PINNED_STABLE
        ),
        release_immutable=immutable,
        prerelease=prerelease,
    )
```

Refactor `_release_metadata` to accept `require_immutable: bool = True` so the existing `acquire(CoreArtifactRequest)` path remains immutable-only in this commit. Validate exact tag, published state, Boolean immutable/prerelease fields, metadata prerelease classification from the portion before build metadata (`"-" in request.version.partition("+")[0]`), and consent before returning. Change `_sha256` to raise `ArtifactDigestUnavailableError` for missing or malformed digests.

Use this complete validation body:

```python
def _release_metadata(
    self,
    request: CoreArtifactRequest,
    *,
    require_immutable: bool = True,
) -> Mapping[object, object]:
    raw_metadata = self._http_client.get_json(self._RELEASE_API.format(version=request.version))
    if not isinstance(raw_metadata, Mapping):
        raise ArtifactTrustError("Release metadata is not a JSON object")
    if raw_metadata.get("tag_name") != f"v{request.version}":
        raise ArtifactTrustError("Release tag does not match the requested version")
    if raw_metadata.get("draft") is not False:
        raise ArtifactTrustError("Refusing a draft release")
    self._require_published(raw_metadata)
    immutable = raw_metadata.get("immutable")
    prerelease = raw_metadata.get("prerelease")
    if not isinstance(immutable, bool):
        raise ArtifactTrustError("Release immutable metadata is invalid")
    if not isinstance(prerelease, bool):
        raise ArtifactTrustError("Release prerelease metadata is invalid")
    if prerelease != ("-" in request.version.partition("+")[0]):
        raise ArtifactTrustError("Release prerelease classification is inconsistent")
    if prerelease and not request.allow_prerelease:
        raise ArtifactTrustError("Prerelease requires explicit permission")
    if require_immutable and not immutable:
        raise ArtifactTrustError("Release is not immutable")
    return raw_metadata
```

Update every existing acquisition metadata fixture to include the exact `tag_name` and a non-empty `published_at`; prefer the `release_metadata` helper where the test does not intentionally omit or corrupt one of those fields. This ensures stronger validation does not invalidate unrelated contract cases.

Do not relax Stable discovery yet. This prevents a partially implemented user-visible fallback between commits.

- [ ] **Step 5: Run contract and static checks**

Run:

```bash
rtk .venv/bin/pytest tests/contracts/test_artifact_source.py -q
rtk .venv/bin/ruff check src/sb_manager/adapters/github_artifacts.py tests/contracts/test_artifact_source.py
rtk .venv/bin/mypy src
```

Expected: all pass; the existing immutable acquisition behavior remains green.

- [ ] **Step 6: Commit read-only inspection**

```bash
rtk git add src/sb_manager/adapters/github_artifacts.py tests/contracts/test_artifact_source.py
rtk git commit -m "feat: inspect official core artifact evidence"
```

## Task 3: Freeze Evidence in Application Plans and Revalidate on Acquisition

**Model tier:** Highest available; this slice changes the trust boundary and cross-layer protocol.

**Files:**
- Modify: `src/sb_manager/seams/artifact_source.py`
- Modify: `src/sb_manager/adapters/github_artifacts.py`
- Modify: `src/sb_manager/application/core_update.py`
- Modify: `tests/contracts/test_artifact_source.py`
- Modify: `tests/behavior/test_core_update.py`
- Modify: `tests/behavior/test_core_channels.py`
- Modify: `tests/acceptance/test_core_update_journey.py`
- Modify: `tests/acceptance/test_core_channel_journey.py`
- Modify: `tests/acceptance/test_keyboard_navigation_journey.py`

- [ ] **Step 1: Write failing application tests for frozen evidence**

Replace `RecordingArtifactSource` in `tests/behavior/test_core_update.py` with the complete final-protocol fake below. Individual tests may replace `inspected_artifact` to select immutable Preview evidence:

```python
class RecordingArtifactSource:
    def __init__(self) -> None:
        version = "1.13.14"
        asset_name = f"sing-box-{version}-linux-amd64.tar.gz"
        self.inspected_artifact = PlannedCoreArtifact(
            version=version,
            architecture=ArtifactArchitecture.AMD64,
            asset_name=asset_name,
            download_url=(
                "https://github.com/SagerNet/sing-box/releases/download/"
                f"v{version}/{asset_name}"
            ),
            sha256="a" * 64,
            trust_mode=CoreArtifactTrustMode.DIGEST_PINNED_STABLE,
            release_immutable=False,
            prerelease=False,
        )
        self.inspect_requests: list[CoreArtifactRequest] = []
        self.acquisitions: list[tuple[PlannedCoreArtifact, Path]] = []

    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact:
        self.inspect_requests.append(request)
        requested_prerelease = "-" in request.version.partition("+")[0]
        return replace(
            self.inspected_artifact,
            version=request.version,
            architecture=request.architecture,
            asset_name=(
                f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
            ),
            download_url=(
                "https://github.com/SagerNet/sing-box/releases/download/"
                f"v{request.version}/sing-box-{request.version}-linux-"
                f"{request.architecture.value}.tar.gz"
            ),
            prerelease=requested_prerelease,
            trust_mode=(
                CoreArtifactTrustMode.IMMUTABLE_RELEASE
                if requested_prerelease
                else CoreArtifactTrustMode.DIGEST_PINNED_STABLE
            ),
            release_immutable=requested_prerelease,
        )

    def acquire(
        self,
        artifact: PlannedCoreArtifact,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        self.acquisitions.append((artifact, destination_directory))
        destination_directory.mkdir(parents=True, exist_ok=True)
        archive_path = destination_directory / artifact.asset_name
        archive_path.write_bytes(b"verified archive")
        return VerifiedCoreArtifact(
            version=artifact.version,
            architecture=artifact.architecture,
            asset_name=artifact.asset_name,
            archive_path=archive_path,
            sha256=artifact.sha256,
        )
```

Import `replace`, `CoreArtifactTrustMode`, and `PlannedCoreArtifact`, then add:

```python
def test_core_update_plan_freezes_inspected_artifact(tmp_path: Path) -> None:
    core_updates, source, _ = service(tmp_path)

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    assert plan.artifact == source.inspected_artifact
    assert plan.version == "1.13.14"
    assert plan.asset_name == source.inspected_artifact.asset_name
    assert plan.warnings == (CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE,)
    assert source.acquisitions == []


def test_confirmed_update_passes_the_identical_frozen_evidence_to_acquisition(
    tmp_path: Path,
) -> None:
    core_updates, source, _ = service(tmp_path)
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    core_updates.execute(plan, confirmed=True)

    assert source.acquisitions == [(plan.artifact, tmp_path / "incoming")]
```

Retain the prerelease warning test, but make its fake inspection return immutable prerelease evidence. Update `tests/behavior/test_core_channels.py` so its updater fixtures construct `CoreUpdatePlan(artifact=..., mutates_host=False, warnings=...)`; add an assertion that an `ACQUIRE_AND_ACTIVATE` channel plan carries the exact evidence returned by its updater.

Update the existing behavior assertions to distinguish read-only inspection from mutation: planning records exactly one `inspect_request`, prerelease rejection records none, `confirmed=False` records no acquisition, and confirmed execution records one `(plan.artifact, incoming_directory)` acquisition. Give `FailingArtifactSource` a valid `inspect` result and make only its `acquire` raise `OSError("network unavailable")`, proving the error remains pre-activation.

Mechanically update every acceptance fake found by `rtk rg -l 'CoreUpdatePlan\(' tests/acceptance` to construct a valid `PlannedCoreArtifact` and pass it as `artifact=`. Preserve the existing version, architecture, prerelease classification, warning tuple, and visible behavior; these compatibility edits add no new TUI expectations in this task.

- [ ] **Step 2: Write failing adapter drift and byte-identity tests**

Import `ArtifactMetadataChangedError`, then add:

```python
def test_acquire_rejects_metadata_drift_before_download(tmp_path: Path) -> None:
    version = "1.13.14"
    original = release_metadata(
        version=version,
        prerelease=False,
        immutable=False,
        digest="a" * 64,
    )
    changed = release_metadata(
        version=version,
        prerelease=False,
        immutable=False,
        digest="b" * 64,
    )
    http = FakeHttpClient(metadata=original, later_metadata=(changed,), payload=b"unused")
    source = GitHubArtifactSource(http_client=http)
    artifact = source.inspect(
        CoreArtifactRequest(version=version, architecture=ArtifactArchitecture.AMD64)
    )

    with pytest.raises(ArtifactMetadataChangedError, match="changed"):
        source.acquire(artifact, destination_directory=tmp_path)

    assert http.downloads == []


def test_acquire_hashes_bytes_against_the_frozen_digest(tmp_path: Path) -> None:
    version = "1.13.14"
    metadata = release_metadata(
        version=version,
        prerelease=False,
        immutable=False,
        digest="0" * 64,
    )
    http = FakeHttpClient(metadata=metadata, later_metadata=(metadata,), payload=b"changed")
    source = GitHubArtifactSource(http_client=http)
    artifact = source.inspect(
        CoreArtifactRequest(version=version, architecture=ArtifactArchitecture.AMD64)
    )

    with pytest.raises(ArtifactIntegrityError, match="SHA-256 mismatch"):
        source.acquire(artifact, destination_directory=tmp_path)

    assert not (tmp_path / artifact.asset_name).exists()
```

Also change the Stable discovery fixture to `immutable=False` and keep its expected `CoreRelease(STABLE, "1.13.14", False)` result. Preview discovery continues to skip every `immutable=False` prerelease.

- [ ] **Step 3: Run the focused suites and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/behavior/test_core_update.py tests/behavior/test_core_channels.py tests/contracts/test_artifact_source.py -q
```

Expected: failures show that plans do not contain `artifact`, the protocol has no `inspect`, mutable Stable discovery is rejected, and acquisition still accepts a request rather than frozen evidence.

- [ ] **Step 4: Change the seam to its final two-phase protocol**

Replace `CoreArtifactSource` with:

```python
class CoreArtifactSource(Protocol):
    """Inspect, then acquire one exact verified official sing-box archive."""

    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact: ...

    def acquire(
        self,
        artifact: PlannedCoreArtifact,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact: ...
```

- [ ] **Step 5: Embed evidence in `CoreUpdatePlan`**

In `src/sb_manager/application/core_update.py`, add the trust-mode imports and warning, then replace the plan fields with:

```python
class CoreUpdateWarning(str, Enum):
    PRERELEASE_COMPATIBILITY_RISK = "prerelease-compatibility-risk"
    DIGEST_PINNED_MUTABLE_RELEASE = "digest-pinned-mutable-release"


@dataclass(frozen=True, slots=True)
class CoreUpdatePlan:
    """Read-only review of one artifact whose byte identity is frozen."""

    artifact: PlannedCoreArtifact
    mutates_host: bool
    warnings: tuple[CoreUpdateWarning, ...]

    @property
    def version(self) -> str:
        return self.artifact.version

    @property
    def architecture(self) -> ArtifactArchitecture:
        return self.artifact.architecture

    @property
    def asset_name(self) -> str:
        return self.artifact.asset_name

    @property
    def allow_prerelease(self) -> bool:
        return self.artifact.prerelease

    @property
    def source(self) -> str:
        return "SagerNet/sing-box official GitHub release"
```

Replace `CoreUpdateService.plan` and the acquisition portion of `execute` with:

```python
def plan(self, request: PlanCoreUpdateRequest) -> CoreUpdatePlan:
    artifact_request = CoreArtifactRequest(
        version=request.version,
        architecture=request.architecture,
        allow_prerelease=request.allow_prerelease,
    )
    requested_prerelease = "-" in artifact_request.version.partition("+")[0]
    if requested_prerelease and not artifact_request.allow_prerelease:
        raise CorePrereleaseConsentRequiredError(
            f"Core version {artifact_request.version} is a prerelease"
        )
    artifact = self._artifact_source.inspect(artifact_request)
    if (
        artifact.version != artifact_request.version
        or artifact.architecture is not artifact_request.architecture
        or artifact.prerelease is not requested_prerelease
    ):
        raise CoreArtifactAcquisitionError(
            "Artifact inspection returned evidence inconsistent with the request"
        )
    warnings: list[CoreUpdateWarning] = []
    if artifact.prerelease:
        warnings.append(CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK)
    if artifact.trust_mode is CoreArtifactTrustMode.DIGEST_PINNED_STABLE:
        warnings.append(CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE)
    return CoreUpdatePlan(
        artifact=artifact,
        mutates_host=False,
        warnings=tuple(warnings),
    )

def execute(self, plan: CoreUpdatePlan, *, confirmed: bool) -> CoreUpdateResult:
    if not confirmed:
        raise CoreUpdateConfirmationRequiredError("Core update requires explicit confirmation")
    try:
        artifact = self._artifact_source.acquire(
            plan.artifact,
            destination_directory=self._incoming_directory,
        )
    except Exception as error:
        raise CoreArtifactAcquisitionError(str(error)) from error
    try:
        activation = self._core_activator.activate_core(
            CoreActivationRequest(
                version=artifact.version,
                architecture=artifact.architecture,
                sha256=artifact.sha256,
            )
        )
    finally:
        artifact.archive_path.unlink(missing_ok=True)
    return CoreUpdateResult(activation=activation)
```

This composes warnings in stable order: prerelease first, digest-pinned mutable second.

- [ ] **Step 6: Revalidate the frozen object in the GitHub adapter**

Change `GitHubArtifactSource.acquire` to:

```python
def acquire(
    self,
    artifact: PlannedCoreArtifact,
    *,
    destination_directory: Path,
) -> VerifiedCoreArtifact:
    observed = self.inspect(
        CoreArtifactRequest(
            version=artifact.version,
            architecture=artifact.architecture,
            allow_prerelease=artifact.prerelease,
        )
    )
    if observed != artifact:
        raise ArtifactMetadataChangedError(
            f"Official artifact metadata changed for {artifact.asset_name}; create a new plan"
        )
    destination_directory.mkdir(parents=True, exist_ok=True)
    archive_path = destination_directory / artifact.asset_name
    temporary_path: Path | None = None
    try:
        with NamedTemporaryFile(
            dir=destination_directory,
            prefix=f".{artifact.asset_name}.",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
        self._http_client.download(artifact.download_url, temporary_path)
        actual_sha256 = self._hash(temporary_path)
        if not hmac.compare_digest(actual_sha256, artifact.sha256):
            raise ArtifactIntegrityError(
                f"SHA-256 mismatch for {artifact.asset_name}: "
                f"expected {artifact.sha256}, got {actual_sha256}"
            )
        temporary_path.replace(archive_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return VerifiedCoreArtifact(
        version=artifact.version,
        architecture=artifact.architecture,
        asset_name=artifact.asset_name,
        archive_path=archive_path,
        sha256=artifact.sha256,
    )
```

Finally, relax only Stable discovery by removing its `immutable is True` requirement. Require `immutable` to be Boolean, but leave mutable/immutable asset policy to `inspect`. Preview discovery must still select only `immutable=True` prereleases.

Update existing acquisition-contract URL assertions to expect two exact-tag metadata reads—one during `inspect` and one during `acquire`—followed by one download. Update every behavior fake that implements `CoreArtifactSource`, including `RecordingArtifactSource` in `tests/behavior/test_core_channels.py`, to implement both final protocol methods.

- [ ] **Step 7: Run focused and full deterministic verification**

Run:

```bash
rtk .venv/bin/pytest tests/contracts/test_artifact_source.py tests/behavior/test_core_update.py tests/behavior/test_core_channels.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/acceptance/test_keyboard_navigation_journey.py -q
rtk .venv/bin/pytest -q
rtk .venv/bin/ruff check src/sb_manager/seams/artifact_source.py src/sb_manager/adapters/github_artifacts.py src/sb_manager/application/core_update.py tests/contracts/test_artifact_source.py tests/behavior/test_core_update.py tests/behavior/test_core_channels.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/acceptance/test_keyboard_navigation_journey.py
rtk .venv/bin/mypy src
```

Expected: focused suites and the full deterministic suite pass; Ruff and mypy are clean.

- [ ] **Step 8: Commit the frozen plan/acquire boundary**

```bash
rtk git add src/sb_manager/seams/artifact_source.py src/sb_manager/adapters/github_artifacts.py src/sb_manager/application/core_update.py tests/contracts/test_artifact_source.py tests/behavior/test_core_update.py tests/behavior/test_core_channels.py tests/acceptance/test_core_update_journey.py tests/acceptance/test_core_channel_journey.py tests/acceptance/test_keyboard_navigation_journey.py
rtk git commit -m "feat: freeze core evidence before acquisition"
```

## Task 4: Non-blocking Exact-Version Planning and Review

**Model tier:** Standard; Textual worker lifecycle and cross-file semantic copy.

**Files:**
- Create: `src/sb_manager/ui/core_artifact_copy.py`
- Modify: `src/sb_manager/ui/copy_catalog.py`
- Modify: `src/sb_manager/ui/screens/core_update.py`
- Modify: `tests/acceptance/test_core_update_journey.py`

- [ ] **Step 1: Write failing Pilot tests for worker responsiveness and frozen evidence**

Update the acceptance fake plans to use `PlannedCoreArtifact`. Add a blocking updater backed by `threading.Event`, then add:

```python
async def test_exact_version_planning_runs_without_blocking_the_tui() -> None:
    updater = BlockingPlanningCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*"1.13.14")
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert updater.started.wait(timeout=1)
        assert app.screen.query_one("#preview-core-update", Button).disabled is True
        assert app.screen.query_one("#core-update-form-error", Static).content == (
            "正在检查官方发行元数据并冻结制品摘要…"
        )

        updater.release.set()
        await pilot.pause()
        assert app.screen.query_one("#core-update-plan-sha256", Static).content == (
            f"制品 SHA-256：{'a' * 64}"
        )


async def test_leaving_exact_planning_does_not_open_a_stale_review() -> None:
    updater = BlockingPlanningCoreUpdater()
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*"1.13.14")
        await pilot.click("#preview-core-update")
        assert updater.started.wait(timeout=1)

        await pilot.press("escape")
        updater.release.set()
        await pilot.pause()

        assert len(app.screen.query("#core-update-plan")) == 0


async def test_digest_pinned_stable_review_shows_trust_warning() -> None:
    updater = RecordingCoreUpdater(trust_mode=CoreArtifactTrustMode.DIGEST_PINNED_STABLE)
    app = ManagerApp(core_updater=updater)

    async with app.run_test() as pilot:
        await open_core_form(pilot)
        await pilot.click("#core-version")
        await pilot.press(*"1.13.14")
        await pilot.click("#preview-core-update")
        await pilot.pause()

        assert app.screen.query_one("#core-update-plan-trust", Static).content == (
            "信任方式：Stable 摘要冻结"
        )
        assert app.screen.query_one("#core-update-warning-0", Static).content == (
            "上游 Stable release 可变；本次操作只接受上方已冻结的 SHA-256。"
        )
```

Update the custom marker catalog with semantic keys for planning progress, SHA-256, trust mode, and the mutable-release warning.

- [ ] **Step 2: Run the exact journey and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/acceptance/test_core_update_journey.py -q
```

Expected: failures show synchronous planning, missing digest/trust widgets, and missing copy keys.

- [ ] **Step 3: Add semantic copy identities and shared mappings**

Add these `UiText` members and corresponding validated templates:

```python
CORE_UPDATE_FORM_PLANNING = "core_update.form.planning"
CORE_UPDATE_PLAN_SHA256 = "core_update.plan.sha256"
CORE_UPDATE_PLAN_TRUST = "core_update.plan.trust"
CORE_UPDATE_TRUST_IMMUTABLE = "core_update.trust.immutable"
CORE_UPDATE_TRUST_DIGEST_PINNED = "core_update.trust.digest_pinned"
CORE_UPDATE_PLAN_WARNING_MUTABLE_RELEASE = "core_update.plan.warning.mutable_release"
```

Templates:

```python
UiText.CORE_UPDATE_FORM_PLANNING: "正在检查官方发行元数据并冻结制品摘要…",
UiText.CORE_UPDATE_PLAN_SHA256: "制品 SHA-256：{sha256}",
UiText.CORE_UPDATE_PLAN_TRUST: "信任方式：{trust}",
UiText.CORE_UPDATE_TRUST_IMMUTABLE: "上游 immutable release",
UiText.CORE_UPDATE_TRUST_DIGEST_PINNED: "Stable 摘要冻结",
UiText.CORE_UPDATE_PLAN_WARNING_MUTABLE_RELEASE: (
    "上游 Stable release 可变；本次操作只接受上方已冻结的 SHA-256。"
),
```

Declare expected fields `{"sha256"}` and `{"trust"}` for the parameterized keys.

Create `src/sb_manager/ui/core_artifact_copy.py`:

```python
"""Map typed artifact evidence to validated interface copy identities."""

from sb_manager.application.core_update import CoreUpdateWarning
from sb_manager.seams.artifact_source import CoreArtifactTrustMode
from sb_manager.ui.copy_catalog import UiText

WARNING_COPY: dict[CoreUpdateWarning, UiText] = {
    CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK: UiText.CORE_UPDATE_PLAN_WARNING_PRERELEASE,
    CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE: (
        UiText.CORE_UPDATE_PLAN_WARNING_MUTABLE_RELEASE
    ),
}

TRUST_COPY: dict[CoreArtifactTrustMode, UiText] = {
    CoreArtifactTrustMode.IMMUTABLE_RELEASE: UiText.CORE_UPDATE_TRUST_IMMUTABLE,
    CoreArtifactTrustMode.DIGEST_PINNED_STABLE: UiText.CORE_UPDATE_TRUST_DIGEST_PINNED,
}
```

- [ ] **Step 4: Render frozen evidence on the exact review screen**

Import `TRUST_COPY` and `WARNING_COPY` from the new module. After the asset widget, render:

```python
yield Static(
    self.copy.text(UiText.CORE_UPDATE_PLAN_SHA256, sha256=self.plan.artifact.sha256),
    id="core-update-plan-sha256",
    markup=False,
)
yield Static(
    self.copy.text(
        UiText.CORE_UPDATE_PLAN_TRUST,
        trust=self.copy.text(TRUST_COPY[self.plan.artifact.trust_mode]),
    ),
    id="core-update-plan-trust",
    markup=False,
)
```

Keep warnings in tuple order and keep `markup=False`.

- [ ] **Step 5: Move exact planning into an exclusive worker**

Add `self._planning_generation = 0` in `CoreUpdateFormScreen.__init__`. In `preview_core_update`, validate the architecture, construct `PlanCoreUpdateRequest`, increment the generation, disable the preview button, show `CORE_UPDATE_FORM_PLANNING`, and call `prepare_plan(request, generation)`.

Add:

```python
@work(thread=True, exclusive=True)
def prepare_plan(self, request: PlanCoreUpdateRequest, generation: int) -> None:
    try:
        plan = self.core_updater.plan(request)
    except ValueError:
        self.app.call_from_thread(
            self._finish_planning_error,
            generation,
            UiText.CORE_UPDATE_FORM_ERROR_INVALID_VERSION,
        )
        return
    except CorePrereleaseConsentRequiredError:
        self.app.call_from_thread(
            self._finish_planning_error,
            generation,
            UiText.CORE_UPDATE_FORM_ERROR_PRERELEASE_CONSENT,
        )
        return
    except Exception:
        self.app.call_from_thread(self._show_unexpected_planning_error, generation)
        return
    self.app.call_from_thread(self._show_plan, generation, plan)

def _planning_is_current(self, generation: int) -> bool:
    return generation == self._planning_generation and self.app.screen is self

def _restore_planning_controls(self) -> None:
    self.query_one("#preview-core-update", Button).disabled = False

def _finish_planning_error(self, generation: int, key: UiText) -> None:
    if not self._planning_is_current(generation):
        return
    self._restore_planning_controls()
    self.query_one("#core-update-form-error", Static).update(self.copy.text(key))

def _show_unexpected_planning_error(self, generation: int) -> None:
    if not self._planning_is_current(generation):
        return
    self._restore_planning_controls()
    self.app.push_screen(CoreUpdatePlanningErrorScreen(self.copy))

def _show_plan(self, generation: int, plan: CoreUpdatePlan) -> None:
    if not self._planning_is_current(generation):
        return
    self._restore_planning_controls()
    self.query_one("#core-update-form-error", Static).update("")
    self.app.push_screen(_CoreUpdatePlanScreen(self.core_updater, plan, self.copy))
```

- [ ] **Step 6: Run Pilot, catalog, and static checks**

Run:

```bash
rtk .venv/bin/pytest tests/acceptance/test_core_update_journey.py -q
rtk .venv/bin/ruff check src/sb_manager/ui/core_artifact_copy.py src/sb_manager/ui/copy_catalog.py src/sb_manager/ui/screens/core_update.py tests/acceptance/test_core_update_journey.py
rtk .venv/bin/mypy src
```

Expected: all pass; the blocking fake proves the event loop remains responsive and stale completion is suppressed.

- [ ] **Step 7: Commit exact-version interaction changes**

```bash
rtk git add src/sb_manager/ui/core_artifact_copy.py src/sb_manager/ui/copy_catalog.py src/sb_manager/ui/screens/core_update.py tests/acceptance/test_core_update_journey.py
rtk git commit -m "feat: review frozen evidence in core update tui"
```

## Task 5: Channel Review Uses the Same Artifact Evidence

**Model tier:** Medium or lower; focused presentation adaptation using types created above.

**Files:**
- Modify: `src/sb_manager/ui/screens/core_channels.py`
- Modify: `tests/acceptance/test_core_channel_journey.py`

- [ ] **Step 1: Write failing channel review tests**

Change `MissingPreviewChannels` to construct an immutable `PlannedCoreArtifact`. Add `MissingStableChannels` whose exact update uses `DIGEST_PINNED_STABLE` and the mutable warning. Add:

```python
async def test_missing_stable_review_displays_frozen_digest_and_mutable_warning() -> None:
    channels = MissingStableChannels()
    app = ManagerApp(
        core_updater=NeverCalledExactUpdater(),
        core_channel_manager=channels,
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-operations")
        await pilot.click("#manage-core-channels")
        await pilot.click("#inspect-stable-channel")
        await pilot.pause()

        assert app.screen.query_one("#core-channel-plan-asset", Static).content == (
            "发行资产：sing-box-1.13.14-linux-amd64.tar.gz"
        )
        assert app.screen.query_one("#core-channel-plan-sha256", Static).content == (
            f"制品 SHA-256：{'f' * 64}"
        )
        assert app.screen.query_one("#core-channel-plan-trust", Static).content == (
            "信任方式：Stable 摘要冻结"
        )
        assert app.screen.query_one("#core-channel-warning-0", Static).content == (
            "上游 Stable release 可变；本次操作只接受上方已冻结的 SHA-256。"
        )
```

Extend the Preview acquisition test to assert immutable trust and its full digest. Retained-switch tests continue to assert local target/current digests and no download evidence widgets.

- [ ] **Step 2: Run the channel journey and prove RED**

Run:

```bash
rtk .venv/bin/pytest tests/acceptance/test_core_channel_journey.py -q
```

Expected: acquisition review lacks asset, digest, trust, and structured warning widgets.

- [ ] **Step 3: Render exact-update evidence for acquisition plans**

Import shared `TRUST_COPY` and `WARNING_COPY`. In `CoreChannelPlanScreen.compose`, when `self.plan.exact_update is not None`, render:

```python
artifact = self.plan.exact_update.artifact
yield Static(
    self.copy.text(UiText.CORE_UPDATE_PLAN_ASSET, asset=artifact.asset_name),
    id="core-channel-plan-asset",
    markup=False,
)
yield Static(
    self.copy.text(UiText.CORE_UPDATE_PLAN_SHA256, sha256=artifact.sha256),
    id="core-channel-plan-sha256",
    markup=False,
)
yield Static(
    self.copy.text(
        UiText.CORE_UPDATE_PLAN_TRUST,
        trust=self.copy.text(TRUST_COPY[artifact.trust_mode]),
    ),
    id="core-channel-plan-trust",
    markup=False,
)
for index, warning in enumerate(self.plan.exact_update.warnings):
    yield Static(
        self.copy.text(WARNING_COPY[warning]),
        id=f"core-channel-warning-{index}",
        markup=False,
    )
```

For retained Preview switches, retain the existing prerelease compatibility warning because there is no `exact_update`. Do not show a mutable-release warning for retained local artifacts.

- [ ] **Step 4: Run channel and regression checks**

Run:

```bash
rtk .venv/bin/pytest tests/acceptance/test_core_channel_journey.py tests/acceptance/test_core_update_journey.py -q
rtk .venv/bin/ruff check src/sb_manager/ui/screens/core_channels.py tests/acceptance/test_core_channel_journey.py
rtk .venv/bin/mypy src
```

Expected: both journeys pass; retained switching and exact-version review remain unchanged except for the added trusted evidence.

- [ ] **Step 5: Commit channel review evidence**

```bash
rtk git add src/sb_manager/ui/screens/core_channels.py tests/acceptance/test_core_channel_journey.py
rtk git commit -m "feat: show artifact trust in channel plans"
```

## Task 6: Verify Current Official Stable and Preview Artifacts

**Model tier:** Standard; external integration with rollback and upstream evidence.

**Files:**
- Modify: `tests/integration/test_official_artifact.py`
- Create: `docs/acceptance/2026-07-18-stable-digest-fallback.md`

- [ ] **Step 1: Add trust-mode assertion to the opt-in integration test**

Import `CoreArtifactTrustMode`. After planning and before execution, add:

```python
expected_trust_mode = os.environ.get("SB_MANAGER_ARTIFACT_TRUST_MODE")
if expected_trust_mode is None:
    pytest.fail("SB_MANAGER_ARTIFACT_TRUST_MODE is required")
assert plan.artifact.trust_mode is CoreArtifactTrustMode(expected_trust_mode)
assert len(plan.artifact.sha256) == 64
```

- [ ] **Step 2: Run the test without opt-in and prove it remains isolated**

Run:

```bash
rtk .venv/bin/pytest tests/integration/test_official_artifact.py -q
```

Expected: one skipped test and no network download.

- [ ] **Step 3: Run official Stable acquisition/activation/rollback**

Run:

```bash
rtk env SB_MANAGER_ARTIFACT_DOWNLOAD=download SB_MANAGER_ARTIFACT_VERSION=1.13.14 SB_MANAGER_ARTIFACT_ARCHITECTURE=amd64 SB_MANAGER_ARTIFACT_TRUST_MODE=digest-pinned-stable .venv/bin/pytest tests/integration/test_official_artifact.py -q -rs
```

Expected: pass; the downloaded archive matches the frozen API digest, self-reports `1.13.14`, activates in the isolated root, and rolls back to no active target.

- [ ] **Step 4: Run official Preview acquisition/activation/rollback**

Run:

```bash
rtk env SB_MANAGER_ARTIFACT_DOWNLOAD=download SB_MANAGER_ARTIFACT_VERSION=1.14.0-alpha.47 SB_MANAGER_ARTIFACT_ARCHITECTURE=amd64 SB_MANAGER_ARTIFACT_ALLOW_PRERELEASE=1 SB_MANAGER_ARTIFACT_TRUST_MODE=immutable-release .venv/bin/pytest tests/integration/test_official_artifact.py -q -rs
```

Expected: pass with immutable Preview evidence and isolated rollback.

If upstream has published a newer Stable or Preview by execution time, first inspect the official API, substitute the newly discovered exact versions in these two commands, and record both the observed timestamp and versions. Never change production code to hardcode those observed values.

- [ ] **Step 5: Record acceptance evidence**

Create `docs/acceptance/2026-07-18-stable-digest-fallback.md` with the exact commands, UTC execution time, discovered versions, asset names, trust modes, frozen SHA-256 values, test results, and rollback result. State that external availability and upstream metadata are non-deterministic inputs, while all local suites remain opt-in and deterministic.

- [ ] **Step 6: Commit integration coverage and evidence**

```bash
rtk git add tests/integration/test_official_artifact.py docs/acceptance/2026-07-18-stable-digest-fallback.md
rtk git commit -m "test: verify digest-pinned stable artifact"
```

## Task 7: Align ADRs, SDD, Support Matrix, and User Manual

**Model tier:** Medium or lower for editing; highest available specification review because trust wording is normative.

**Files:**
- Modify: `docs/adr/0003-sing-box-artifact-trust.md`
- Modify: `docs/adr/0023-dual-core-release-channels.md`
- Modify: `docs/SDD.md`
- Modify: `docs/MANUAL.md`
- Modify: `docs/SUPPORT.md`

- [ ] **Step 1: Amend ADR-0003 with the scoped fallback**

Change the title to “Trust exact sing-box release artifacts,” add an amendment date, and replace the blanket immutable rule with:

```markdown
3. Immutable official releases remain preferred. A published, non-draft,
   non-prerelease Stable release may use `digest-pinned-stable` only when the
   official API supplies the expected asset URL and SHA-256 before confirmation.
   Preview remains immutable-only.
4. The unprivileged plan freezes version, architecture, asset name, URL,
   SHA-256, prerelease classification, immutable flag, and trust mode. Execution
   re-fetches the exact tag and rejects any metadata drift before downloading.
```

Update consequences to distinguish release immutability from operation-level content addressing. Keep HTTPS-only-without-digest and privileged-network alternatives rejected.

- [ ] **Step 2: Amend ADR-0023 with frozen artifact evidence**

Replace “Stable resolves only ... immutable” with the approved Stable fallback; keep Preview immutable-only. State that an acquisition channel plan embeds `PlannedCoreArtifact`, while already-current/retained plans use manager-owned manifest identities.

- [ ] **Step 3: Update SDD implementation truth**

Document:

- `CoreArtifactTrustMode`, `PlannedCoreArtifact`, and the two-phase protocol signatures;
- Stable mutable fallback predicates and Preview rejection;
- exact metadata re-fetch plus frozen byte hash;
- exact-version and channel planning workers;
- safe pre-mutation drift/hash failure versus unknown post-helper result;
- unchanged no-network privileged helper and rollback boundary;
- TDD seams and opt-in official integration tests.

Remove the pending Stable artifact-trust item because this slice resolves it.

- [ ] **Step 4: Update the user manual**

Replace immutable-only guidance with an operator-facing description of both trust modes. Explain that Stable fallback shows the full SHA-256 and requires confirmation, metadata changes force a fresh plan, Preview remains immutable-only, and acquisition failures before activation leave the active core unchanged. Do not expose internal class names in the manual.

- [ ] **Step 5: Update the support matrix**

Record the exact Stable and Preview versions and evidence observed in Task 6. Distinguish dynamic channel policy from dated acceptance evidence; do not claim those versions are production constants.

- [ ] **Step 6: Verify documentation consistency**

Run:

```bash
rtk rg -n "immutable=false|immutable-only|digest-pinned|摘要冻结|Stable|Preview" docs/adr/0003-sing-box-artifact-trust.md docs/adr/0023-dual-core-release-channels.md docs/SDD.md docs/MANUAL.md docs/SUPPORT.md
rtk rg -n "pending: resolution of the latest Stable artifact-trust conflict" docs/SDD.md
rtk git diff --check
```

Expected: the first command shows consistent Stable/Preview policy; the obsolete pending text has no matches; diff check is clean.

- [ ] **Step 7: Commit normative and user documentation**

```bash
rtk git add docs/adr/0003-sing-box-artifact-trust.md docs/adr/0023-dual-core-release-channels.md docs/SDD.md docs/MANUAL.md docs/SUPPORT.md
rtk git commit -m "docs: explain stable digest trust policy"
```

## Task 8: Full Verification and Final Cross-Slice Review

**Model tier:** Highest available; completion audit, security review, and cross-slice consistency.

**Files:**
- Verify all files changed since `0b3a7fb`
- Modify only files required to fix verified issues

- [ ] **Step 1: Format and prove formatting is stable**

Run:

```bash
rtk .venv/bin/ruff format .
rtk .venv/bin/ruff format --check .
```

Expected: the check reports all files already formatted after the first command.

- [ ] **Step 2: Run lint and strict typing**

Run:

```bash
rtk .venv/bin/ruff check .
rtk .venv/bin/mypy src
```

Expected: no Ruff violations and no mypy issues.

- [ ] **Step 3: Run the complete deterministic suite**

Run:

```bash
rtk .venv/bin/pytest -q
```

Expected: all deterministic tests pass; opt-in external tests are skipped unless explicitly authorized.

- [ ] **Step 4: Build the distributable package**

Run:

```bash
rtk .venv/bin/python -m build
```

Expected: source distribution and wheel build successfully.

- [ ] **Step 5: Audit the actual diff against every design acceptance criterion**

Run:

```bash
rtk git diff --stat 0b3a7fb..HEAD
rtk git log --oneline 0b3a7fb..HEAD
rtk git status --short
```

Then verify directly that:

- Stable mutable fallback is restricted to official published non-prereleases with an API digest;
- Preview mutable metadata is rejected;
- confirmation renders and binds the exact digest;
- metadata drift and byte mismatch stop before activation;
- exact-version planning is non-blocking and stale-safe;
- the privileged helper has no new HTTP dependency;
- manual, SDD, ADRs, support matrix, and acceptance evidence agree.

- [ ] **Step 6: Run the required two-stage final review**

Dispatch a fresh specification reviewer over `0b3a7fb..HEAD`. Fix every gap and re-run the affected tests. Only after specification approval, dispatch a fresh code-quality/security reviewer over the same range. Fix every issue and re-run the full deterministic gates.

- [ ] **Step 7: Close review findings with focused commits**

For each finding, return to the owning task above, add its exact failing regression test, implement the smallest correction, run that task's named focused checks, and stage only the exact paths listed in that task. Use `rtk git commit -m "fix: close stable fallback review findings"` only after the reviewer confirms the correction. Skip this commit when review produces no changes. End with a clean worktree and do not push without separate authorization.
