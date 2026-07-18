"""Discover and acquire trusted sing-box releases from official GitHub metadata."""

import hashlib
import hmac
import re
from collections.abc import Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.seams.artifact_source import (
    ArtifactIntegrityError,
    ArtifactTrustError,
    CoreArtifactRequest,
    CoreRelease,
    CoreReleaseChannel,
    VerifiedCoreArtifact,
)
from sb_manager.seams.http_client import HttpClient


class GitHubArtifactSource:
    """Resolve and verify exact immutable SagerNet releases before exposing them."""

    _RELEASE_API = "https://api.github.com/repos/SagerNet/sing-box/releases/tags/v{version}"
    _LATEST_RELEASE_API = "https://api.github.com/repos/SagerNet/sing-box/releases/latest"
    _RELEASES_API = "https://api.github.com/repos/SagerNet/sing-box/releases?per_page=100"
    _DOWNLOAD_ROOT = "https://github.com/SagerNet/sing-box/releases/download"

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client

    def latest(self, channel: CoreReleaseChannel) -> CoreRelease:
        """Resolve a channel to an exact release without acquiring its asset."""

        if channel is CoreReleaseChannel.PREVIEW:
            raw_releases = self._http_client.get_json(self._RELEASES_API)
            if not isinstance(raw_releases, list):
                raise ArtifactTrustError("Release list is not a JSON array")
            for raw_release in raw_releases:
                if (
                    isinstance(raw_release, Mapping)
                    and raw_release.get("draft") is False
                    and raw_release.get("prerelease") is True
                    and raw_release.get("immutable") is True
                ):
                    self._require_published(raw_release)
                    return CoreRelease(
                        channel=channel,
                        version=self._version_from_tag(raw_release.get("tag_name")),
                        prerelease=True,
                    )
            raise ArtifactTrustError("No trusted preview release is available")

        raw_metadata = self._http_client.get_json(self._LATEST_RELEASE_API)
        if not isinstance(raw_metadata, Mapping):
            raise ArtifactTrustError("Release metadata is not a JSON object")
        if raw_metadata.get("draft") is not False:
            raise ArtifactTrustError("Refusing a draft release")
        if raw_metadata.get("immutable") is not True:
            raise ArtifactTrustError("Release is not immutable")
        if raw_metadata.get("prerelease") is not False:
            raise ArtifactTrustError("Stable channel requires a non-prerelease")
        self._require_published(raw_metadata)
        return CoreRelease(
            channel=channel,
            version=self._version_from_tag(raw_metadata.get("tag_name")),
            prerelease=False,
        )

    @staticmethod
    def _version_from_tag(raw_tag: object) -> str:
        if not isinstance(raw_tag, str):
            raise ArtifactTrustError("Release tag is not a valid version")
        match = re.fullmatch(
            r"v([0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?)",
            raw_tag,
        )
        if match is None:
            raise ArtifactTrustError("Release tag is not a valid version")
        return match.group(1)

    @staticmethod
    def _require_published(metadata: Mapping[object, object]) -> None:
        published_at = metadata.get("published_at")
        if not isinstance(published_at, str) or not published_at:
            raise ArtifactTrustError("Release is not published")

    def acquire(
        self,
        request: CoreArtifactRequest,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        metadata = self._release_metadata(request)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        asset = self._find_asset(metadata, asset_name)
        expected_sha256 = self._sha256(asset)
        download_url = self._download_url(asset, request=request, asset_name=asset_name)

        destination_directory.mkdir(parents=True, exist_ok=True)
        archive_path = destination_directory / asset_name
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                dir=destination_directory,
                prefix=f".{asset_name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
            self._http_client.download(download_url, temporary_path)
            actual_sha256 = self._hash(temporary_path)
            if not hmac.compare_digest(actual_sha256, expected_sha256):
                raise ArtifactIntegrityError(
                    f"SHA-256 mismatch for {asset_name}: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            temporary_path.replace(archive_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return VerifiedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            archive_path=archive_path,
            sha256=expected_sha256,
        )

    def _release_metadata(self, request: CoreArtifactRequest) -> Mapping[object, object]:
        raw_metadata = self._http_client.get_json(self._RELEASE_API.format(version=request.version))
        if not isinstance(raw_metadata, Mapping):
            raise ArtifactTrustError("Release metadata is not a JSON object")
        if raw_metadata.get("draft") is not False:
            raise ArtifactTrustError("Refusing a draft release")
        if raw_metadata.get("immutable") is not True:
            raise ArtifactTrustError("Release is not immutable")
        if raw_metadata.get("prerelease") is True and not request.allow_prerelease:
            raise ArtifactTrustError("Prerelease requires explicit permission")
        return raw_metadata

    @staticmethod
    def _find_asset(metadata: Mapping[object, object], asset_name: str) -> Mapping[object, object]:
        raw_assets = metadata.get("assets")
        if not isinstance(raw_assets, list):
            raise ArtifactTrustError("Release assets are missing")
        matches = [
            asset
            for asset in raw_assets
            if isinstance(asset, Mapping) and asset.get("name") == asset_name
        ]
        if len(matches) != 1:
            raise ArtifactTrustError(
                f"Expected exactly one release asset named {asset_name}, found {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _sha256(asset: Mapping[object, object]) -> str:
        digest = asset.get("digest")
        if not isinstance(digest, str):
            raise ArtifactTrustError("Release asset has no SHA-256 digest")
        match = re.fullmatch(r"sha256:([0-9a-fA-F]{64})", digest)
        if match is None:
            raise ArtifactTrustError("Release asset has no valid SHA-256 digest")
        return match.group(1).lower()

    def _download_url(
        self,
        asset: Mapping[object, object],
        *,
        request: CoreArtifactRequest,
        asset_name: str,
    ) -> str:
        expected = f"{self._DOWNLOAD_ROOT}/v{request.version}/{asset_name}"
        actual = asset.get("browser_download_url")
        if actual != expected:
            raise ArtifactTrustError(f"Unexpected release asset URL: {actual!r}")
        return expected

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as artifact_file:
            while chunk := artifact_file.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
