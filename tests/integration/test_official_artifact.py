import os
import re
from pathlib import Path

import pytest

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.adapters.github_artifacts import GitHubArtifactSource
from sb_manager.adapters.urllib_http import UrllibHttpClient
from sb_manager.application.core_update import CoreUpdateService, PlanCoreUpdateRequest
from sb_manager.artifacts.installation import CoreDistributionInstaller
from sb_manager.privileged.core_install import (
    PrivilegedCoreInstallPolicy,
    PrivilegedCoreInstallService,
)
from sb_manager.seams.artifact_source import ArtifactArchitecture, CoreArtifactTrustMode


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
    expected_trust_mode_value = os.environ.get("SB_MANAGER_ARTIFACT_TRUST_MODE")
    expected_sha256 = os.environ.get("SB_MANAGER_ARTIFACT_SHA256")
    if expected_trust_mode_value is None:
        pytest.fail("SB_MANAGER_ARTIFACT_TRUST_MODE is required")
    if expected_sha256 is None:
        pytest.fail("SB_MANAGER_ARTIFACT_SHA256 is required")
    try:
        expected_trust_mode = CoreArtifactTrustMode(expected_trust_mode_value)
    except ValueError:
        pytest.fail(
            "SB_MANAGER_ARTIFACT_TRUST_MODE must be immutable-release or digest-pinned-stable"
        )
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        pytest.fail(
            "SB_MANAGER_ARTIFACT_SHA256 must be exactly 64 lowercase hexadecimal characters"
        )

    policy = PrivilegedCoreInstallPolicy(
        incoming_directory=tmp_path / "incoming",
        working_directory=tmp_path / "work",
        installation_root=tmp_path / "installation",
        lock_path=tmp_path / "install.lock",
    )
    core_updates = CoreUpdateService(
        artifact_source=GitHubArtifactSource(http_client=UrllibHttpClient()),
        core_activator=PrivilegedCoreInstallService(policy=policy),
        incoming_directory=policy.incoming_directory,
    )
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version=version,
            architecture=selected_architecture,
            allow_prerelease=os.environ.get("SB_MANAGER_ARTIFACT_ALLOW_PRERELEASE") == "1",
        )
    )
    assert plan.artifact.trust_mode is expected_trust_mode
    assert plan.artifact.sha256 == expected_sha256
    activation = core_updates.execute(plan, confirmed=True).activation

    assert activation.version == version
    assert activation.binary_path.resolve() == activation.distribution_directory / "sing-box"

    rollback = CoreDistributionInstaller(
        installation_root=policy.installation_root,
        apply_lock=FileApplyLock(policy.lock_path),
    ).rollback(activation)

    assert rollback.active_target is None
    assert rollback.binary_path is None
    assert not (tmp_path / "installation/current").exists()
