import os
from pathlib import Path

import pytest

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.adapters.github_artifacts import GitHubArtifactSource
from sb_manager.adapters.urllib_http import UrllibHttpClient
from sb_manager.artifacts.installation import CoreDistributionInstaller
from sb_manager.artifacts.staging import CoreArtifactStager
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreArtifactRequest


@pytest.mark.integration
def test_official_release_is_acquired_staged_and_atomically_activated(tmp_path: Path) -> None:
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
    installer = CoreDistributionInstaller(
        installation_root=tmp_path / "installation",
        apply_lock=FileApplyLock(tmp_path / "install.lock"),
    )
    activation = installer.activate(staged)

    assert staged.version == version
    assert staged.architecture is selected_architecture
    assert staged.binary_path.is_file()
    assert staged.source_sha256 == artifact.sha256
    assert activation.binary_path.resolve() == activation.distribution_directory / "sing-box"

    rollback = installer.rollback(activation)

    assert rollback.active_target is None
    assert rollback.binary_path is None
    assert not (tmp_path / "installation/current").exists()
