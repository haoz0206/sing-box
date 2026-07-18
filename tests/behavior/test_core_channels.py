from pathlib import Path

import pytest

from sb_manager.application.core_update import (
    CoreChannelPlanKind,
    CoreChannelPlanningError,
    CoreChannelService,
    CoreUpdateService,
    PlanCoreChannelRequest,
)
from sb_manager.artifacts.installation import CoreActivation, InstalledCoreRelease
from sb_manager.seams.artifact_source import (
    ArtifactArchitecture,
    CoreArtifactRequest,
    CoreRelease,
    CoreReleaseChannel,
    VerifiedCoreArtifact,
)
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest


class FixedReleaseSource:
    def __init__(self, release: CoreRelease) -> None:
        self.release = release
        self.channels: list[CoreReleaseChannel] = []

    def latest(self, channel: CoreReleaseChannel) -> CoreRelease:
        self.channels.append(channel)
        return self.release


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
        self.requests: list[CoreArtifactRequest] = []

    def acquire(
        self,
        request: CoreArtifactRequest,
        *,
        destination_directory: Path,
    ) -> VerifiedCoreArtifact:
        self.requests.append(request)
        destination_directory.mkdir(parents=True, exist_ok=True)
        asset_name = f"sing-box-{request.version}-linux-{request.architecture.value}.tar.gz"
        archive_path = destination_directory / asset_name
        archive_path.write_bytes(b"verified preview archive")
        return VerifiedCoreArtifact(
            version=request.version,
            architecture=request.architecture,
            asset_name=asset_name,
            archive_path=archive_path,
            sha256="c" * 64,
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
    channels = CoreChannelService(
        release_source=source,
        core_inventory=inventory,
        core_updater=UnexpectedCoreUpdater(),
        core_switcher=switcher,
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
    channels = CoreChannelService(
        release_source=release_source,
        core_inventory=inventory,
        core_updater=CoreUpdateService(
            artifact_source=artifacts,
            core_activator=activator,
            incoming_directory=tmp_path / "incoming",
        ),
        core_switcher=UnexpectedCoreSwitcher(),
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
    assert artifacts.requests == [
        CoreArtifactRequest(
            version="1.14.0-alpha.46",
            architecture=ArtifactArchitecture.AMD64,
            allow_prerelease=True,
        )
    ]
    assert activator.requests == [
        CoreActivationRequest(
            version="1.14.0-alpha.46",
            architecture=ArtifactArchitecture.AMD64,
            sha256="c" * 64,
        )
    ]
    assert result.activation.version == "1.14.0-alpha.46"
