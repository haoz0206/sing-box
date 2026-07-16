from pathlib import Path

import pytest

from sb_manager.application.core_update import (
    CoreArtifactAcquisitionError,
    CorePrereleaseConsentRequiredError,
    CoreUpdateConfirmationRequiredError,
    CoreUpdateService,
    PlanCoreUpdateRequest,
)
from sb_manager.artifacts.installation import CoreActivation
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest


class RecordingArtifactSource:
    def __init__(self) -> None:
        self.calls: list[tuple[CoreArtifactRequest, Path]] = []

    def acquire(
        self,
        request: CoreArtifactRequest,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        self.calls.append((request, destination_directory))
        destination_directory.mkdir(parents=True, exist_ok=True)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        archive_path = destination_directory / asset_name
        archive_path.write_bytes(b"verified archive")
        return VerifiedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            archive_path=archive_path,
            sha256="a" * 64,
        )


class RecordingCoreActivator:
    def __init__(self) -> None:
        self.requests: list[CoreActivationRequest] = []

    def activate_core(self, request: CoreActivationRequest) -> CoreActivation:
        self.requests.append(request)
        return CoreActivation(
            version=request.version,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/release"),
            binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
            activated_target="versions/release",
            previous_target="versions/previous",
        )


class FailingArtifactSource:
    def acquire(
        self,
        request: CoreArtifactRequest,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        raise OSError("network unavailable")


def service(
    tmp_path: Path,
) -> tuple[CoreUpdateService, RecordingArtifactSource, RecordingCoreActivator]:
    source = RecordingArtifactSource()
    activator = RecordingCoreActivator()
    return (
        CoreUpdateService(
            artifact_source=source,
            core_activator=activator,
            incoming_directory=tmp_path / "incoming",
        ),
        source,
        activator,
    )


def test_core_update_plan_is_pure_and_exposes_exact_artifact(tmp_path: Path) -> None:
    core_updates, source, _ = service(tmp_path)

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    assert plan.asset_name == "sing-box-1.14.0-linux-amd64.tar.gz"
    assert plan.source == "SagerNet/sing-box immutable GitHub release"
    assert plan.mutates_host is False
    assert plan.warnings == ()
    assert source.calls == []


def test_prerelease_plan_requires_explicit_consent(tmp_path: Path) -> None:
    core_updates, source, _ = service(tmp_path)

    with pytest.raises(CorePrereleaseConsentRequiredError, match="prerelease"):
        core_updates.plan(
            PlanCoreUpdateRequest(
                version="1.14.0-alpha.45",
                architecture=ArtifactArchitecture.AMD64,
                allow_prerelease=False,
            )
        )

    assert source.calls == []


def test_execution_requires_confirmation_before_download(tmp_path: Path) -> None:
    core_updates, source, _ = service(tmp_path)
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    with pytest.raises(CoreUpdateConfirmationRequiredError, match="confirmation"):
        core_updates.execute(plan, confirmed=False)

    assert source.calls == []


def test_confirmed_update_acquires_activates_and_removes_incoming_archive(
    tmp_path: Path,
) -> None:
    core_updates, source, activator = service(tmp_path)
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.ARM64,
            allow_prerelease=True,
        )
    )

    result = core_updates.execute(plan, confirmed=True)

    assert source.calls == [
        (
            CoreArtifactRequest(
                version="1.14.0-alpha.45",
                architecture=ArtifactArchitecture.ARM64,
                allow_prerelease=True,
            ),
            tmp_path / "incoming",
        )
    ]
    assert activator.requests == [
        CoreActivationRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.ARM64,
            sha256="a" * 64,
        )
    ]
    assert result.activation.version == "1.14.0-alpha.45"
    assert list((tmp_path / "incoming").iterdir()) == []


def test_acquisition_failure_is_classified_before_privileged_activation(tmp_path: Path) -> None:
    activator = RecordingCoreActivator()
    core_updates = CoreUpdateService(
        artifact_source=FailingArtifactSource(),
        core_activator=activator,
        incoming_directory=tmp_path / "incoming",
    )
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    with pytest.raises(CoreArtifactAcquisitionError, match="network unavailable"):
        core_updates.execute(plan, confirmed=True)

    assert activator.requests == []
