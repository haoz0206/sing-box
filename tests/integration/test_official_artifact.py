import os
from pathlib import Path

import pytest

from sb_manager.adapters.github_artifacts import GitHubArtifactSource
from sb_manager.adapters.urllib_http import UrllibHttpClient
from sb_manager.artifacts.staging import CoreArtifactStager
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreArtifactRequest


@pytest.mark.integration
def test_official_release_is_acquired_verified_and_staged(tmp_path: Path) -> None:
    if os.environ.get("SB_MANAGER_ARTIFACT_DOWNLOAD") != "download":
        pytest.skip("set SB_MANAGER_ARTIFACT_DOWNLOAD=download to authorize an artifact download")
    version = os.environ.get("SB_MANAGER_ARTIFACT_VERSION")
    architecture = os.environ.get("SB_MANAGER_ARTIFACT_ARCHITECTURE")
    if version is None or architecture is None:
        pytest.fail("SB_MANAGER_ARTIFACT_VERSION and SB_MANAGER_ARTIFACT_ARCHITECTURE are required")
    try:
        selected_architecture = ArtifactArchitecture(architecture)
    except ValueError:
        pytest.fail("SB_MANAGER_ARTIFACT_ARCHITECTURE must be amd64 or arm64")

    artifact = GitHubArtifactSource(http_client=UrllibHttpClient()).acquire(
        CoreArtifactRequest(
            version=version,
            architecture=selected_architecture,
            allow_prerelease=os.environ.get("SB_MANAGER_ARTIFACT_ALLOW_PRERELEASE") == "1",
        ),
        destination_directory=tmp_path / "downloads",
    )
    staged = CoreArtifactStager().stage(
        artifact,
        destination_directory=tmp_path / "staging",
    )

    assert staged.version == version
    assert staged.architecture is selected_architecture
    assert staged.binary_path.is_file()
    assert staged.source_sha256 == artifact.sha256
