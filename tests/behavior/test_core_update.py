from pathlib import Path

import pytest

from sb_manager.application.core_update import (
    CoreArtifactAcquisitionError,
    CorePrereleaseConsentRequiredError,
    CoreUpdateConfirmationRequiredError,
    CoreUpdateService,
    CoreUpdateWarning,
    PlanCoreUpdateRequest,
)
from sb_manager.artifacts.installation import CoreActivation
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    CoreArtifactTrustMode,
    PlannedCoreArtifact,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest


class RecordingArtifactSource:
    def __init__(self) -> None:
        self.inspect_requests: list[CoreArtifactRequest] = []
        self.inspected_artifacts: list[PlannedCoreArtifact] = []
        self.acquisitions: list[tuple[PlannedCoreArtifact, Path]] = []

    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact:
        self.inspect_requests.append(request)
        prerelease = "-" in request.version.partition("+")[0]
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        artifact = PlannedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            download_url=(
                "https://github.com/SagerNet/sing-box/releases/download/"
                f"v{request.version}/{asset_name}"
            ),
            sha256="a" * 64,
            trust_mode=(
                CoreArtifactTrustMode.IMMUTABLE_RELEASE
                if prerelease
                else CoreArtifactTrustMode.DIGEST_PINNED_STABLE
            ),
            release_immutable=prerelease,
            prerelease=prerelease,
        )
        self.inspected_artifacts.append(artifact)
        return artifact

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


class FailingArtifactSource(RecordingArtifactSource):
    def acquire(
        self,
        artifact: PlannedCoreArtifact,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        self.acquisitions.append((artifact, destination_directory))
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
    assert plan.version == "1.14.0"
    assert plan.architecture is ArtifactArchitecture.AMD64
    assert plan.allow_prerelease is False
    assert plan.source == "SagerNet/sing-box official GitHub release"
    assert plan.mutates_host is False
    assert plan.warnings == (CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE,)
    assert source.inspect_requests == [
        CoreArtifactRequest(
            version="1.14.0",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    ]
    assert plan.artifact is source.inspected_artifacts[0]
    assert source.acquisitions == []


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

    assert source.inspect_requests == []
    assert source.acquisitions == []


def test_prerelease_plan_returns_semantic_warning_after_consent(tmp_path: Path) -> None:
    core_updates, source, _ = service(tmp_path)

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    )

    assert plan.warnings == (CoreUpdateWarning.PRERELEASE_COMPATIBILITY_RISK,)
    assert source.inspect_requests == [
        CoreArtifactRequest(
            version="1.14.0-alpha.45",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    ]
    assert source.acquisitions == []


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

    assert source.acquisitions == []


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

    assert len(source.acquisitions) == 1
    acquired_artifact, destination = source.acquisitions[0]
    assert acquired_artifact is plan.artifact
    assert destination == tmp_path / "incoming"
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
    source = FailingArtifactSource()
    activator = RecordingCoreActivator()
    core_updates = CoreUpdateService(
        artifact_source=source,
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

    assert len(source.inspect_requests) == 1
    assert source.acquisitions == [(plan.artifact, tmp_path / "incoming")]
    assert activator.requests == []


def test_build_metadata_hyphen_does_not_make_a_stable_version_prerelease(tmp_path: Path) -> None:
    core_updates, source, _ = service(tmp_path)

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0+vendor-build",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    assert plan.allow_prerelease is False
    assert plan.artifact.prerelease is False
    assert plan.warnings == (CoreUpdateWarning.DIGEST_PINNED_MUTABLE_RELEASE,)
    assert len(source.inspect_requests) == 1
