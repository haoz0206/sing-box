from pathlib import Path

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.core_update import (
    CoreArtifactAcquisitionError,
    CoreDesiredStateChangedError,
    CorePrereleaseConsentRequiredError,
    CoreUpdateConfirmationRequiredError,
    CoreUpdateService,
    CoreUpdateWarning,
    PlanCoreUpdateRequest,
)
from sb_manager.application.protocol_compatibility import (
    CoreTargetIncompatibleWithDesiredState,
    ProtocolCompatibilityPolicy,
)
from sb_manager.artifacts.installation import CoreActivation
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    CoreArtifactTrustMode,
    PlannedCoreArtifact,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest

INITIAL_REVISION = 7
CHANGED_REVISION = 8


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


def test_core_update_plan_records_the_loaded_desired_state_revision(tmp_path: Path) -> None:
    source = RecordingArtifactSource()
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    core_updates = CoreUpdateService(
        artifact_source=source,
        core_activator=RecordingCoreActivator(),
        incoming_directory=tmp_path / "incoming",
        state_store=state_store,
        compatibility=ProtocolCompatibilityPolicy(),
    )

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    assert plan.expected_state_revision == INITIAL_REVISION


def test_desired_state_changed_error_exposes_revisions_without_state_details() -> None:
    error = CoreDesiredStateChangedError(expected=INITIAL_REVISION, actual=CHANGED_REVISION)

    assert error.expected == INITIAL_REVISION
    assert error.actual == CHANGED_REVISION
    assert str(error) == "Desired state changed from revision 7 to 8"


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
            state_store=MemoryStateStore(),
            compatibility=ProtocolCompatibilityPolicy(),
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
        state_store=MemoryStateStore(),
        compatibility=ProtocolCompatibilityPolicy(),
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


def snell_installation(
    *,
    revision: int = INITIAL_REVISION,
    status: ProfileStatus = ProfileStatus.APPLIED,
    enabled: bool = True,
) -> ManagedInstallation:
    return ManagedInstallation(
        schema_version=1,
        revision=revision,
        profiles=(
            ManagedProfile(
                profile_id="profile-7",
                profile_name="private-snell",
                protocol=ProtocolKind.SNELL_V6,
                listen_port=8388,
                port_selection=PortSelection.FIXED,
                status=status,
                enabled=enabled,
            ),
        ),
    )


def test_exact_stable_update_is_blocked_by_an_applied_snell_profile(
    tmp_path: Path,
) -> None:
    source = RecordingArtifactSource()
    core_updates = CoreUpdateService(
        artifact_source=source,
        core_activator=RecordingCoreActivator(),
        incoming_directory=tmp_path / "incoming",
        state_store=MemoryStateStore(snell_installation()),
        compatibility=ProtocolCompatibilityPolicy(),
    )

    with pytest.raises(CoreTargetIncompatibleWithDesiredState) as captured:
        core_updates.plan(
            PlanCoreUpdateRequest(
                version="1.13.14",
                architecture=ArtifactArchitecture.AMD64,
                allow_prerelease=False,
            )
        )

    assert captured.value.blocking_profile_ids == ("profile-7",)
    assert captured.value.blocking_profile_names == ("private-snell",)
    assert source.inspect_requests == []
    assert source.acquisitions == []


@pytest.mark.parametrize(
    ("status", "enabled"),
    (
        (ProfileStatus.DRAFT, True),
        (ProfileStatus.APPLIED, False),
    ),
)
def test_inactive_snell_does_not_block_an_exact_stable_update(
    tmp_path: Path,
    status: ProfileStatus,
    enabled: bool,
) -> None:
    core_updates = CoreUpdateService(
        artifact_source=RecordingArtifactSource(),
        core_activator=RecordingCoreActivator(),
        incoming_directory=tmp_path / "incoming",
        state_store=MemoryStateStore(snell_installation(status=status, enabled=enabled)),
        compatibility=ProtocolCompatibilityPolicy(),
    )

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )

    assert plan.version == "1.13.14"


def test_exact_preview_update_allows_an_applied_snell_profile(tmp_path: Path) -> None:
    core_updates = CoreUpdateService(
        artifact_source=RecordingArtifactSource(),
        core_activator=RecordingCoreActivator(),
        incoming_directory=tmp_path / "incoming",
        state_store=MemoryStateStore(snell_installation()),
        compatibility=ProtocolCompatibilityPolicy(),
    )

    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0-alpha.47",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    )

    assert plan.version == "1.14.0-alpha.47"


def test_core_update_rejects_a_changed_desired_state_before_acquisition(
    tmp_path: Path,
) -> None:
    source = RecordingArtifactSource()
    store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    core_updates = CoreUpdateService(
        artifact_source=source,
        core_activator=RecordingCoreActivator(),
        incoming_directory=tmp_path / "incoming",
        state_store=store,
        compatibility=ProtocolCompatibilityPolicy(),
    )
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.14.0-alpha.47",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    )
    store.save(snell_installation(revision=CHANGED_REVISION))

    with pytest.raises(CoreDesiredStateChangedError) as captured:
        core_updates.execute(plan, confirmed=True)

    assert captured.value.expected == INITIAL_REVISION
    assert captured.value.actual == CHANGED_REVISION
    assert str(captured.value) == "Desired state changed from revision 7 to 8"
    assert source.acquisitions == []


def test_core_update_rechecks_target_compatibility_before_acquisition(
    tmp_path: Path,
) -> None:
    source = RecordingArtifactSource()
    store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    core_updates = CoreUpdateService(
        artifact_source=source,
        core_activator=RecordingCoreActivator(),
        incoming_directory=tmp_path / "incoming",
        state_store=store,
        compatibility=ProtocolCompatibilityPolicy(),
    )
    plan = core_updates.plan(
        PlanCoreUpdateRequest(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=False,
        )
    )
    store.save(snell_installation(revision=INITIAL_REVISION))

    with pytest.raises(CoreTargetIncompatibleWithDesiredState):
        core_updates.execute(plan, confirmed=True)

    assert source.acquisitions == []


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
