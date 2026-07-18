import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from sb_manager.adapters.github_artifacts import GitHubArtifactSource
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    ArtifactIntegrityError,
    ArtifactTrustError,
    CoreArtifactRequest,
    CoreArtifactTrustMode,
    CoreRelease,
    CoreReleaseChannel,
    PlannedCoreArtifact,
    VerifiedCoreArtifact,
)


class FakeHttpClient:
    def __init__(self, *, metadata: object, payload: bytes) -> None:
        self._metadata = metadata
        self._payload = payload
        self.json_urls: list[str] = []
        self.downloads: list[tuple[str, Path]] = []

    def get_json(self, url: str) -> object:
        self.json_urls.append(url)
        return self._metadata

    def download(self, url: str, destination: Path) -> None:
        self.downloads.append((url, destination))
        destination.write_bytes(self._payload)


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


def test_latest_stable_channel_resolves_exact_immutable_release_without_downloading() -> None:
    http = FakeHttpClient(
        metadata={
            "tag_name": "v1.13.14",
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "published_at": "2026-06-25T09:11:52Z",
        },
        payload=b"must not be downloaded",
    )

    release = GitHubArtifactSource(http_client=http).latest(CoreReleaseChannel.STABLE)

    assert release == CoreRelease(
        channel=CoreReleaseChannel.STABLE,
        version="1.13.14",
        prerelease=False,
    )
    assert http.json_urls == ["https://api.github.com/repos/SagerNet/sing-box/releases/latest"]
    assert http.downloads == []


def test_latest_preview_channel_selects_first_trusted_prerelease_without_downloading() -> None:
    http = FakeHttpClient(
        metadata=[
            {
                "tag_name": "v1.13.14",
                "draft": False,
                "prerelease": False,
                "immutable": True,
            },
            {
                "tag_name": "v1.14.0-alpha.48",
                "draft": True,
                "prerelease": True,
                "immutable": True,
            },
            {
                "tag_name": "v1.14.0-alpha.47",
                "draft": False,
                "prerelease": True,
                "immutable": False,
            },
            {
                "tag_name": "v1.14.0-alpha.46",
                "draft": False,
                "prerelease": True,
                "immutable": True,
                "published_at": "2026-07-17T04:50:20Z",
            },
        ],
        payload=b"must not be downloaded",
    )

    release = GitHubArtifactSource(http_client=http).latest(CoreReleaseChannel.PREVIEW)

    assert release == CoreRelease(
        channel=CoreReleaseChannel.PREVIEW,
        version="1.14.0-alpha.46",
        prerelease=True,
    )
    assert http.json_urls == [
        "https://api.github.com/repos/SagerNet/sing-box/releases?per_page=100"
    ]
    assert http.downloads == []


def test_release_discovery_rejects_a_non_version_tag() -> None:
    http = FakeHttpClient(
        metadata={
            "tag_name": "vlatest",
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "published_at": "2026-06-25T09:11:52Z",
        },
        payload=b"must not be downloaded",
    )

    with pytest.raises(ArtifactTrustError, match="valid version"):
        GitHubArtifactSource(http_client=http).latest(CoreReleaseChannel.STABLE)

    assert http.downloads == []


def test_release_discovery_rejects_unpublished_metadata() -> None:
    http = FakeHttpClient(
        metadata={
            "tag_name": "v1.13.14",
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "published_at": None,
        },
        payload=b"must not be downloaded",
    )

    with pytest.raises(ArtifactTrustError, match="published"):
        GitHubArtifactSource(http_client=http).latest(CoreReleaseChannel.STABLE)

    assert http.downloads == []


def test_official_immutable_release_asset_is_verified_before_staging(tmp_path: Path) -> None:
    version = "1.14.0-alpha.45"
    asset_name = f"sing-box-{version}-linux-amd64.tar.gz"
    download_url = f"https://github.com/SagerNet/sing-box/releases/download/v{version}/{asset_name}"
    payload = b"release archive bytes"
    sha256 = hashlib.sha256(payload).hexdigest()
    http = FakeHttpClient(
        metadata={
            "draft": False,
            "prerelease": True,
            "immutable": True,
            "assets": [
                {
                    "name": asset_name,
                    "browser_download_url": download_url,
                    "digest": f"sha256:{sha256}",
                }
            ],
        },
        payload=payload,
    )

    artifact = GitHubArtifactSource(http_client=http).acquire(
        CoreArtifactRequest(
            version=version,
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        ),
        destination_directory=tmp_path,
    )

    archive_path = tmp_path / asset_name
    assert artifact == VerifiedCoreArtifact(
        version=version,
        architecture=ArtifactArchitecture.AMD64,
        asset_name=asset_name,
        archive_path=archive_path,
        sha256=sha256,
    )
    assert archive_path.read_bytes() == payload
    assert http.json_urls == [
        f"https://api.github.com/repos/SagerNet/sing-box/releases/tags/v{version}"
    ]
    assert len(http.downloads) == 1
    downloaded_url, temporary_path = http.downloads[0]
    assert downloaded_url == download_url
    assert temporary_path.parent == tmp_path
    assert temporary_path != archive_path
    assert not temporary_path.exists()


@pytest.mark.parametrize(
    ("metadata_override", "diagnostic"),
    (
        ({"immutable": False}, "immutable"),
        ({"draft": True}, "draft"),
    ),
)
def test_untrusted_release_metadata_is_rejected_before_download(
    tmp_path: Path,
    metadata_override: dict[str, object],
    diagnostic: str,
) -> None:
    metadata: dict[str, object] = {
        "draft": False,
        "prerelease": False,
        "immutable": True,
        "assets": [],
    }
    metadata.update(metadata_override)
    http = FakeHttpClient(metadata=metadata, payload=b"unused")

    with pytest.raises(ArtifactTrustError, match=diagnostic):
        GitHubArtifactSource(http_client=http).acquire(
            CoreArtifactRequest(
                version="1.14.0",
                architecture=ArtifactArchitecture.AMD64,
            ),
            destination_directory=tmp_path,
        )

    assert http.downloads == []


def test_prerelease_requires_explicit_permission(tmp_path: Path) -> None:
    http = FakeHttpClient(
        metadata={
            "draft": False,
            "prerelease": True,
            "immutable": True,
            "assets": [],
        },
        payload=b"unused",
    )

    with pytest.raises(ArtifactTrustError, match=r"(?i)prerelease"):
        GitHubArtifactSource(http_client=http).acquire(
            CoreArtifactRequest(
                version="1.14.0-alpha.45",
                architecture=ArtifactArchitecture.AMD64,
            ),
            destination_directory=tmp_path,
        )

    assert http.downloads == []


def test_missing_sha256_digest_is_rejected_before_download(tmp_path: Path) -> None:
    version = "1.14.0"
    asset_name = f"sing-box-{version}-linux-arm64.tar.gz"
    http = FakeHttpClient(
        metadata={
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "assets": [
                {
                    "name": asset_name,
                    "browser_download_url": "https://github.com/SagerNet/sing-box/releases/download/asset",
                    "digest": None,
                }
            ],
        },
        payload=b"unused",
    )

    with pytest.raises(ArtifactTrustError, match="SHA-256"):
        GitHubArtifactSource(http_client=http).acquire(
            CoreArtifactRequest(
                version=version,
                architecture=ArtifactArchitecture.ARM64,
            ),
            destination_directory=tmp_path,
        )

    assert http.downloads == []


def test_digest_mismatch_removes_untrusted_download(tmp_path: Path) -> None:
    version = "1.14.0"
    asset_name = f"sing-box-{version}-linux-amd64.tar.gz"
    download_url = f"https://github.com/SagerNet/sing-box/releases/download/v{version}/{asset_name}"
    http = FakeHttpClient(
        metadata={
            "draft": False,
            "prerelease": False,
            "immutable": True,
            "assets": [
                {
                    "name": asset_name,
                    "browser_download_url": download_url,
                    "digest": f"sha256:{'0' * 64}",
                }
            ],
        },
        payload=b"tampered bytes",
    )

    with pytest.raises(ArtifactIntegrityError, match="SHA-256 mismatch"):
        GitHubArtifactSource(http_client=http).acquire(
            CoreArtifactRequest(
                version=version,
                architecture=ArtifactArchitecture.AMD64,
            ),
            destination_directory=tmp_path,
        )

    assert not (tmp_path / asset_name).exists()


@pytest.mark.parametrize("version", ("", "../1.14.0", "1.14.0/asset"))
def test_artifact_request_rejects_unsafe_versions(version: str) -> None:
    with pytest.raises(ValueError, match="version"):
        CoreArtifactRequest(
            version=version,
            architecture=ArtifactArchitecture.AMD64,
        )
