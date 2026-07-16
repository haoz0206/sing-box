"""Acquire trusted sing-box archives from official GitHub Releases."""

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
    VerifiedCoreArtifact,
)
from sb_manager.seams.http_client import HttpClient


class GitHubArtifactSource:
    """Verify exact immutable SagerNet release assets before exposing them."""

    _RELEASE_API = "https://api.github.com/repos/SagerNet/sing-box/releases/tags/v{version}"
    _DOWNLOAD_ROOT = "https://github.com/SagerNet/sing-box/releases/download"

    def __init__(self, *, http_client: HttpClient) -> None:
        self._http_client = http_client

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
