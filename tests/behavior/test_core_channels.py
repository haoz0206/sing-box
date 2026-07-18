from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.core_update import (
    CoreChannelPlan,
    CoreChannelPlanKind,
    CoreChannelPlanningError,
    CoreChannelPlanValidationError,
    CoreChannelService,
    CoreDesiredStateChangedError,
    CoreUpdatePlan,
    CoreUpdateService,
    PlanCoreChannelRequest,
)
from sb_manager.application.protocol_compatibility import (
    CoreTargetIncompatibleWithDesiredState,
    ProtocolCompatibilityPolicy,
)
from sb_manager.artifacts.installation import (
    CoreActivation,
    CoreReleaseIdentity,
    InstalledCoreRelease,
)
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
    CoreRelease,
    CoreReleaseChannel,
    PlannedCoreArtifact,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest

INITIAL_REVISION = 7
CHANGED_REVISION = 8
PLAN_REVISION = 9


class FixedReleaseSource:
    def __init__(self, release: CoreRelease) -> None:
        self.release = release
        self.channels: list[CoreReleaseChannel] = []

    def latest(self, channel: CoreReleaseChannel) -> CoreRelease:
        self.channels.append(channel)
        return self.release


class ImmediateApplyLock:
    def __init__(self) -> None:
        self.entries = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.entries += 1
        yield


class RecordingStateStore(MemoryStateStore):
    def __init__(self, initial: ManagedInstallation) -> None:
        super().__init__(initial)
        self.load_calls = 0
        self.save_calls: list[ManagedInstallation] = []

    def load(self) -> ManagedInstallation:
        self.load_calls += 1
        return super().load()

    def save(self, installation: ManagedInstallation) -> None:
        self.save_calls.append(installation)
        super().save(installation)


class FixedCoreInventory:
    def __init__(self, *releases: InstalledCoreRelease) -> None:
        self.releases = releases
        self.calls = 0

    def list_installed(self) -> tuple[InstalledCoreRelease, ...]:
        self.calls += 1
        return self.releases


class UnexpectedCoreUpdater:
    def plan(self, request: object) -> object:
        raise AssertionError("an already-current channel must not create an acquisition plan")

    def execute(self, plan: object, *, confirmed: bool) -> object:
        raise AssertionError("an already-current channel must not acquire a release")


class UnexpectedCoreSwitcher:
    def switch_core(self, request: object) -> object:
        raise AssertionError("an already-current channel must not invoke the helper")


class RecordingCoreSwitcher:
    def __init__(self) -> None:
        self.requests: list[CoreSwitchRequest] = []

    def switch_core(self, request: CoreSwitchRequest) -> CoreActivation:
        self.requests.append(request)
        return CoreActivation(
            version=request.target.version,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
            binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
            activated_target="versions/preview",
            previous_target="versions/stable",
        )


class RecordingArtifactSource:
    def __init__(self) -> None:
        self.inspect_requests: list[CoreArtifactRequest] = []
        self.acquisitions: list[PlannedCoreArtifact] = []

    def inspect(self, request: CoreArtifactRequest) -> PlannedCoreArtifact:
        self.inspect_requests.append(request)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        return PlannedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            download_url=(
                "https://github.com/SagerNet/sing-box/releases/download/"
                f"v{request.version}/{asset_name}"
            ),
            sha256="c" * 64,
            trust_mode=CoreArtifactTrustMode.IMMUTABLE_RELEASE,
            release_immutable=True,
            prerelease=True,
        )

    def acquire(
        self,
        artifact: PlannedCoreArtifact,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        self.acquisitions.append(artifact)
        destination_directory.mkdir(parents=True, exist_ok=True)
        archive_path = destination_directory / artifact.asset_name
        archive_path.write_bytes(b"verified preview archive")
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
            distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
            binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
            activated_target="versions/preview",
            previous_target="versions/stable",
        )


def snell_installation(
    *, revision: int = INITIAL_REVISION, enabled: bool = True
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
                status=ProfileStatus.APPLIED,
                enabled=enabled,
            ),
        ),
    )


def retained_stable_inventory() -> FixedCoreInventory:
    return FixedCoreInventory(
        InstalledCoreRelease(
            version="1.14.0-alpha.47",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="b" * 64,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
            target="versions/preview",
            active=True,
        ),
        InstalledCoreRelease(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
            target="versions/stable",
            active=False,
        ),
    )


def test_channel_plan_records_the_loaded_desired_state_revision() -> None:
    source = FixedReleaseSource(
        CoreRelease(
            channel=CoreReleaseChannel.STABLE,
            version="1.13.14",
            prerelease=False,
        )
    )
    inventory = FixedCoreInventory(
        InstalledCoreRelease(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
            target="versions/stable",
            active=True,
        )
    )
    channels = CoreChannelService(
        release_source=source,
        core_inventory=inventory,
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=UnexpectedCoreSwitcher(),
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=PLAN_REVISION, profiles=())
        ),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )

    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.STABLE,
            architecture=ArtifactArchitecture.AMD64,
        )
    )

    assert plan.expected_state_revision == PLAN_REVISION


def test_stable_channel_reports_already_current_without_download_or_switch() -> None:
    source = FixedReleaseSource(
        CoreRelease(
            channel=CoreReleaseChannel.STABLE,
            version="1.13.14",
            prerelease=False,
        )
    )
    inventory = FixedCoreInventory(
        InstalledCoreRelease(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
            distribution_directory=Path(f"/opt/sing-box-manager/core/versions/1.13.14-{'a' * 64}"),
            target=f"versions/1.13.14-{'a' * 64}",
            active=True,
        )
    )
    channels = CoreChannelService(
        release_source=source,
        core_inventory=inventory,
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=UnexpectedCoreSwitcher(),
        state_store=MemoryStateStore(),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )

    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.STABLE,
            architecture=ArtifactArchitecture.AMD64,
        )
    )

    assert plan.kind is CoreChannelPlanKind.ALREADY_CURRENT
    assert plan.channel is CoreReleaseChannel.STABLE
    assert plan.version == "1.13.14"
    assert plan.prerelease is False
    assert plan.requires_confirmation is False
    assert plan.target is not None
    assert plan.target.source_sha256 == "a" * 64
    assert plan.expected_active == plan.target
    assert plan.exact_update is None
    assert source.channels == [CoreReleaseChannel.STABLE]
    assert inventory.calls == 1


def test_channel_discovery_rejects_a_release_from_a_different_channel() -> None:
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=CoreReleaseChannel.PREVIEW,
                version="1.14.0-alpha.46",
                prerelease=True,
            )
        ),
        core_inventory=FixedCoreInventory(),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=UnexpectedCoreSwitcher(),
        state_store=MemoryStateStore(),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )

    with pytest.raises(CoreChannelPlanningError, match="requested stable"):
        channels.plan(
            PlanCoreChannelRequest(
                channel=CoreReleaseChannel.STABLE,
                architecture=ArtifactArchitecture.AMD64,
            )
        )


@pytest.mark.parametrize(
    ("channel", "prerelease"),
    (
        (CoreReleaseChannel.STABLE, True),
        (CoreReleaseChannel.PREVIEW, False),
    ),
)
def test_channel_discovery_rejects_an_inconsistent_prerelease_classification(
    channel: CoreReleaseChannel,
    prerelease: bool,
) -> None:
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=channel,
                version="1.14.0-alpha.46" if prerelease else "1.13.14",
                prerelease=prerelease,
            )
        ),
        core_inventory=FixedCoreInventory(),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=UnexpectedCoreSwitcher(),
        state_store=MemoryStateStore(),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )

    with pytest.raises(CoreChannelPlanningError, match="prerelease classification"):
        channels.plan(
            PlanCoreChannelRequest(
                channel=channel,
                architecture=ArtifactArchitecture.AMD64,
            )
        )


def test_preview_channel_switches_to_a_retained_release_without_acquisition() -> None:
    source = FixedReleaseSource(
        CoreRelease(
            channel=CoreReleaseChannel.PREVIEW,
            version="1.14.0-alpha.46",
            prerelease=True,
        )
    )
    inventory = FixedCoreInventory(
        InstalledCoreRelease(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
            target="versions/stable",
            active=True,
        ),
        InstalledCoreRelease(
            version="1.14.0-alpha.46",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="b" * 64,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
            target="versions/preview",
            active=False,
        ),
    )
    switcher = RecordingCoreSwitcher()
    apply_lock = ImmediateApplyLock()
    channels = CoreChannelService(
        release_source=source,
        core_inventory=inventory,
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=MemoryStateStore(),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=apply_lock,
    )

    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.PREVIEW,
            architecture=ArtifactArchitecture.AMD64,
        )
    )
    result = channels.execute(plan, confirmed=True)

    assert plan.kind is CoreChannelPlanKind.SWITCH_RETAINED
    assert plan.requires_confirmation is True
    assert plan.exact_update is None
    assert plan.target is not None
    assert plan.expected_active is not None
    assert switcher.requests == [
        CoreSwitchRequest(
            target=plan.target,
            expected_active=plan.expected_active,
        )
    ]
    assert apply_lock.entries == 1
    assert result.activation.version == "1.14.0-alpha.46"


def test_missing_preview_channel_acquires_and_activates_the_discovered_exact_release(
    tmp_path: Path,
) -> None:
    release_source = FixedReleaseSource(
        CoreRelease(
            channel=CoreReleaseChannel.PREVIEW,
            version="1.14.0-alpha.46",
            prerelease=True,
        )
    )
    inventory = FixedCoreInventory(
        InstalledCoreRelease(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
            distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
            target="versions/stable",
            active=True,
        )
    )
    artifacts = RecordingArtifactSource()
    activator = RecordingCoreActivator()
    state_store = MemoryStateStore()
    compatibility = ProtocolCompatibilityPolicy()
    apply_lock = ImmediateApplyLock()
    channels = CoreChannelService(
        release_source=release_source,
        core_inventory=inventory,
        core_updater=CoreUpdateService(
            artifact_source=artifacts,
            core_activator=activator,
            incoming_directory=tmp_path / "incoming",
            state_store=state_store,
            compatibility=compatibility,
            apply_lock=apply_lock,
        ),
        core_switcher=UnexpectedCoreSwitcher(),
        state_store=state_store,
        compatibility=compatibility,
        apply_lock=apply_lock,
    )

    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.PREVIEW,
            architecture=ArtifactArchitecture.AMD64,
        )
    )
    result = channels.execute(plan, confirmed=True)

    assert plan.kind is CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE
    assert plan.requires_confirmation is True
    assert plan.target is None
    assert plan.exact_update is not None
    assert plan.exact_update.version == "1.14.0-alpha.46"
    assert plan.exact_update.allow_prerelease is True
    assert plan.expected_state_revision == plan.exact_update.expected_state_revision
    assert artifacts.inspect_requests == [
        CoreArtifactRequest(
            version="1.14.0-alpha.46",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    ]
    assert artifacts.acquisitions == [plan.exact_update.artifact]
    assert artifacts.acquisitions[0] is plan.exact_update.artifact
    assert activator.requests == [
        CoreActivationRequest(
            version="1.14.0-alpha.46",
            architecture=ArtifactArchitecture.AMD64,
            sha256="c" * 64,
        )
    ]
    assert apply_lock.entries == 1
    assert result.activation.version == "1.14.0-alpha.46"


def test_retained_stable_channel_is_blocked_by_an_applied_snell_profile() -> None:
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=CoreReleaseChannel.STABLE,
                version="1.13.14",
                prerelease=False,
            )
        ),
        core_inventory=retained_stable_inventory(),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=MemoryStateStore(snell_installation()),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )

    with pytest.raises(CoreTargetIncompatibleWithDesiredState) as captured:
        channels.plan(
            PlanCoreChannelRequest(
                channel=CoreReleaseChannel.STABLE,
                architecture=ArtifactArchitecture.AMD64,
            )
        )

    assert captured.value.blocking_profile_ids == ("profile-7",)
    assert captured.value.blocking_profile_names == ("private-snell",)
    assert switcher.requests == []


def test_retained_preview_channel_allows_an_applied_snell_profile() -> None:
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=CoreReleaseChannel.PREVIEW,
                version="1.14.0-alpha.47",
                prerelease=True,
            )
        ),
        core_inventory=FixedCoreInventory(
            InstalledCoreRelease(
                version="1.13.14",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="a" * 64,
                distribution_directory=Path("/opt/sing-box-manager/core/versions/stable"),
                target="versions/stable",
                active=True,
            ),
            InstalledCoreRelease(
                version="1.14.0-alpha.47",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="b" * 64,
                distribution_directory=Path("/opt/sing-box-manager/core/versions/preview"),
                target="versions/preview",
                active=False,
            ),
        ),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=MemoryStateStore(snell_installation()),
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )

    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.PREVIEW,
            architecture=ArtifactArchitecture.AMD64,
        )
    )
    channels.execute(plan, confirmed=True)

    assert plan.kind is CoreChannelPlanKind.SWITCH_RETAINED
    assert len(switcher.requests) == 1


def test_fresh_retained_stable_plan_succeeds_after_snell_is_paused() -> None:
    store = MemoryStateStore(snell_installation())
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=CoreReleaseChannel.STABLE,
                version="1.13.14",
                prerelease=False,
            )
        ),
        core_inventory=retained_stable_inventory(),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=store,
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )
    store.save(snell_installation(revision=CHANGED_REVISION, enabled=False))

    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.STABLE,
            architecture=ArtifactArchitecture.AMD64,
        )
    )
    channels.execute(plan, confirmed=True)

    assert plan.expected_state_revision == CHANGED_REVISION
    assert len(switcher.requests) == 1


def test_retained_switch_rechecks_target_compatibility_before_privileged_switch() -> None:
    store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=CoreReleaseChannel.STABLE,
                version="1.13.14",
                prerelease=False,
            )
        ),
        core_inventory=retained_stable_inventory(),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=store,
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )
    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.STABLE,
            architecture=ArtifactArchitecture.AMD64,
        )
    )
    store.save(snell_installation(revision=INITIAL_REVISION))

    with pytest.raises(CoreTargetIncompatibleWithDesiredState):
        channels.execute(plan, confirmed=True)

    assert switcher.requests == []


def test_stale_retained_switch_stops_before_compatibility_and_privileged_switch() -> None:
    store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=FixedReleaseSource(
            CoreRelease(
                channel=CoreReleaseChannel.STABLE,
                version="1.13.14",
                prerelease=False,
            )
        ),
        core_inventory=retained_stable_inventory(),
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=store,
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )
    plan = channels.plan(
        PlanCoreChannelRequest(
            channel=CoreReleaseChannel.STABLE,
            architecture=ArtifactArchitecture.AMD64,
        )
    )
    store.save(snell_installation(revision=CHANGED_REVISION))

    with pytest.raises(CoreDesiredStateChangedError) as captured:
        channels.execute(plan, confirmed=True)

    assert captured.value.expected == INITIAL_REVISION
    assert captured.value.actual == CHANGED_REVISION
    assert switcher.requests == []


def test_forged_retained_plan_is_rejected_before_state_or_privileged_switch() -> None:
    release_source = FixedReleaseSource(
        CoreRelease(
            channel=CoreReleaseChannel.PREVIEW,
            version="1.14.0-alpha.47",
            prerelease=True,
        )
    )
    inventory = FixedCoreInventory()
    state_store = RecordingStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=release_source,
        core_inventory=inventory,
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
        state_store=state_store,
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=ImmediateApplyLock(),
    )
    forged = CoreChannelPlan(
        kind=CoreChannelPlanKind.SWITCH_RETAINED,
        channel=CoreReleaseChannel.PREVIEW,
        version="1.14.0-alpha.47",
        architecture=ArtifactArchitecture.AMD64,
        prerelease=True,
        requires_confirmation=True,
        target=CoreReleaseIdentity(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
        ),
        expected_active=CoreReleaseIdentity(
            version="1.14.0-alpha.47",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="b" * 64,
        ),
        exact_update=None,
        expected_state_revision=INITIAL_REVISION,
    )

    with pytest.raises(CoreChannelPlanValidationError):
        channels.execute(forged, confirmed=True)

    assert state_store.load_calls == 0
    assert state_store.save_calls == []
    assert release_source.channels == []
    assert inventory.calls == 0
    assert switcher.requests == []


@pytest.mark.parametrize(
    "changes",
    (
        {"version": "1.13.14"},
        {"architecture": ArtifactArchitecture.ARM64},
        {"prerelease": False},
        {"channel": CoreReleaseChannel.STABLE},
        {"expected_state_revision": CHANGED_REVISION},
        {
            "target": CoreReleaseIdentity(
                version="1.14.0-alpha.47",
                architecture=ArtifactArchitecture.AMD64,
                source_sha256="c" * 64,
            )
        },
    ),
    ids=("version", "architecture", "prerelease", "channel", "revision", "target"),
)
def test_forged_acquisition_plan_is_rejected_before_state_or_external_seams(
    tmp_path: Path,
    changes: dict[str, object],
) -> None:
    state_store = RecordingStateStore(
        ManagedInstallation(schema_version=1, revision=INITIAL_REVISION, profiles=())
    )
    artifacts = RecordingArtifactSource()
    activator = RecordingCoreActivator()
    apply_lock = ImmediateApplyLock()
    updater = CoreUpdateService(
        artifact_source=artifacts,
        core_activator=activator,
        incoming_directory=tmp_path / "incoming",
        state_store=state_store,
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=apply_lock,
    )
    exact_update = CoreUpdatePlan(
        artifact=PlannedCoreArtifact(
            version="1.14.0-alpha.47",
            architecture=ArtifactArchitecture.AMD64,
            asset_name="sing-box-1.14.0-alpha.47-linux-amd64.tar.gz",
            download_url="https://example.invalid/sing-box-preview.tar.gz",
            sha256="c" * 64,
            trust_mode=CoreArtifactTrustMode.IMMUTABLE_RELEASE,
            release_immutable=True,
            prerelease=True,
        ),
        mutates_host=False,
        warnings=(),
        expected_state_revision=INITIAL_REVISION,
    )
    valid = CoreChannelPlan(
        kind=CoreChannelPlanKind.ACQUIRE_AND_ACTIVATE,
        channel=CoreReleaseChannel.PREVIEW,
        version=exact_update.version,
        architecture=exact_update.architecture,
        prerelease=exact_update.allow_prerelease,
        requires_confirmation=True,
        target=None,
        expected_active=CoreReleaseIdentity(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
        ),
        exact_update=exact_update,
        expected_state_revision=exact_update.expected_state_revision,
    )
    forged = replace(valid, **changes)
    release_source = FixedReleaseSource(
        CoreRelease(
            channel=CoreReleaseChannel.PREVIEW,
            version=exact_update.version,
            prerelease=True,
        )
    )
    inventory = FixedCoreInventory()
    switcher = RecordingCoreSwitcher()
    channels = CoreChannelService(
        release_source=release_source,
        core_inventory=inventory,
        core_updater=updater,
        core_switcher=switcher,
        state_store=state_store,
        compatibility=ProtocolCompatibilityPolicy(),
        apply_lock=apply_lock,
    )

    with pytest.raises(CoreChannelPlanValidationError):
        channels.execute(forged, confirmed=True)

    assert state_store.load_calls == 0
    assert state_store.save_calls == []
    assert release_source.channels == []
    assert inventory.calls == 0
    assert artifacts.inspect_requests == []
    assert artifacts.acquisitions == []
    assert activator.requests == []
    assert switcher.requests == []
