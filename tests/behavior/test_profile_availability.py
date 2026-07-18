from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_availability import (
    PlanProfileAvailabilityRequest,
    ProfileAvailability,
    ProfileAvailabilityConfirmationRequiredError,
    ProfileAvailabilityDraftError,
    ProfileAvailabilityNoChangeError,
    ProfileAvailabilityNotFoundError,
    ProfileAvailabilityPlan,
    ProfileAvailabilityPlanChangedError,
    ProfileAvailabilityService,
    ProfileResumePortUnavailableError,
)
from sb_manager.application.protocol_compatibility import (
    ActiveCoreProtocolCompatibility,
    CoreVersionChanged,
    CoreVersionUnknown,
    ProtocolUnsupportedByCore,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import RealityMaterial, SnellV6Material
from sb_manager.protocols.catalog import ProtocolCatalog, RealityHandler, SnellV6Handler
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.core_status import CoreStatusObservation
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256

AUTOMATIC_RESUME_PORT = 9443
EXPECTED_PORT_PROBES = 2
PLANNED_REVISION = 4
EXPECTED_COMMITTED_REVISION = 5
EXPECTED_CORE_INSPECTIONS = 2


class ExplodingApplier:
    def apply(self, document: object, *, precondition: object) -> object:
        raise AssertionError("planning availability must not apply configuration")


class ExplodingLock:
    def acquire(self) -> object:
        raise AssertionError("planning availability must not acquire the mutation lock")


class ExplodingPortSource:
    def is_available(self, port: int) -> bool:
        raise AssertionError("pausing a profile must not probe its port")

    def choose_available(self) -> int:
        raise AssertionError("pausing a profile must not choose a port")


class UnavailablePortSource:
    def is_available(self, port: int) -> bool:
        return False

    def choose_available(self) -> int:
        raise AssertionError("a fixed port must not choose an automatic port")


class PortBecomesUnavailableSource:
    def __init__(self) -> None:
        self.probes = 0

    def is_available(self, port: int) -> bool:
        self.probes += 1
        return self.probes == 1

    def choose_available(self) -> int:
        raise AssertionError("a fixed port must not choose an automatic port")


class AvailableFixedPortSource:
    def __init__(self) -> None:
        self.probes = 0

    def is_available(self, port: int) -> bool:
        self.probes += 1
        return True

    def choose_available(self) -> int:
        raise AssertionError("a fixed port must not choose an automatic port")


class ExplodingRealityMaterialSource:
    def generate(self) -> RealityMaterial:
        raise AssertionError("resume must reuse persisted protocol material")


class ExplodingSnellMaterialSource:
    def generate(self) -> SnellV6Material:
        raise AssertionError("resume must reuse persisted Snell material")


class SequenceCoreStatusInspector:
    def __init__(self, *versions: str) -> None:
        self._versions = iter(versions)
        self.calls = 0

    def inspect(self) -> CoreStatusObservation:
        self.calls += 1
        version = next(self._versions)
        return CoreStatusObservation(
            available=True,
            version=version,
            diagnostics=f"sing-box version {version}",
        )


class InspectorThatMustNotBeCalled:
    def inspect(self) -> CoreStatusObservation:
        raise AssertionError("inactive Snell profiles must not inspect the core")


def snell_profile(
    *, enabled: bool, status: ProfileStatus = ProfileStatus.APPLIED
) -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-7",
        profile_name="Snell preview",
        protocol=ProtocolKind.SNELL_V6,
        listen_port=18443,
        port_selection=PortSelection.FIXED,
        status=status,
        enabled=enabled,
        protocol_material=(
            SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8")
            if status is ProfileStatus.APPLIED
            else None
        ),
    )


def reality_profile(*, enabled: bool) -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-reality",
        profile_name="Reality",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=enabled,
        protocol_material=RealityMaterial(
            user_uuid="11111111-1111-4111-8111-111111111111",
            private_key="private-key",
            public_key="public-key",
            short_id="0123456789abcdef",
            server_name="www.cloudflare.com",
        ),
    )


def snell_catalog() -> ProtocolCatalog:
    return ProtocolCatalog((SnellV6Handler(material_source=ExplodingSnellMaterialSource()),))


class AutomaticResumePortSource:
    def __init__(self) -> None:
        self.excluded_ports: frozenset[int] | None = None

    def is_available(self, port: int) -> bool:
        return False

    def choose_available(self, *, excluded_ports: frozenset[int] = frozenset()) -> int:
        self.excluded_ports = excluded_ports
        return 9443


class TrackingLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


class RecordingSuccessfulApplier:
    def __init__(self) -> None:
        self.document: Mapping[str, object] | None = None
        self.precondition: ConfigTargetPrecondition | None = None

    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        self.document = document
        self.precondition = precondition
        return ApplyTransactionResult(
            outcome=ApplyOutcome.APPLIED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
            postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
            rollback=None,
        )


class RejectingApplier:
    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        return ApplyTransactionResult(
            outcome=ApplyOutcome.VALIDATION_FAILED,
            validation=ConfigValidationResult(
                valid=False,
                diagnostics="paused candidate is invalid",
            ),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
        )


def test_snell_resume_rechecks_active_core_before_port_or_apply() -> None:
    profile = snell_profile(enabled=False)
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    state_store = MemoryStateStore(initial)
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=snell_catalog(),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=SequenceCoreStatusInspector("1.13.14")
        ),
    )

    with pytest.raises(ProtocolUnsupportedByCore):
        service.plan_change(
            PlanProfileAvailabilityRequest(
                profile_id=profile.profile_id,
                target=ProfileAvailability.ACTIVE,
            )
        )

    assert state_store.load() == initial


def test_snell_resume_succeeds_with_matching_preview() -> None:
    profile = snell_profile(enabled=False)
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    )
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.47")
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=snell_catalog(),
        port_source=AvailableFixedPortSource(),
        applier=RecordingSuccessfulApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id=profile.profile_id,
            target=ProfileAvailability.ACTIVE,
        )
    )
    result = service.apply_change(plan, confirmed=True)

    assert plan.observed_core_version == "1.14.0-alpha.47"
    assert result.availability is ProfileAvailability.ACTIVE
    assert result.committed_revision == EXPECTED_COMMITTED_REVISION
    assert inspector.calls == EXPECTED_CORE_INSPECTIONS


def test_pausing_last_active_snell_under_stable_is_recovery_safe() -> None:
    profile = snell_profile(enabled=True)
    inspector = InspectorThatMustNotBeCalled()
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    )
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=snell_catalog(),
        port_source=ExplodingPortSource(),
        applier=RecordingSuccessfulApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id=profile.profile_id,
            target=ProfileAvailability.PAUSED,
        )
    )
    result = service.apply_change(plan, confirmed=True)

    assert plan.observed_core_version is None
    assert result.availability is ProfileAvailability.PAUSED
    assert state_store.load().profiles[0].enabled is False


@pytest.mark.parametrize(
    ("profile", "target", "error"),
    (
        (
            snell_profile(enabled=True, status=ProfileStatus.DRAFT),
            ProfileAvailability.PAUSED,
            ProfileAvailabilityDraftError,
        ),
        (
            snell_profile(enabled=False),
            ProfileAvailability.PAUSED,
            ProfileAvailabilityNoChangeError,
        ),
    ),
)
def test_draft_and_already_paused_snell_do_not_probe_core(
    profile: ManagedProfile,
    target: ProfileAvailability,
    error: type[Exception],
) -> None:
    service = ProfileAvailabilityService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
        ),
        protocol_catalog=snell_catalog(),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=InspectorThatMustNotBeCalled()
        ),
    )

    with pytest.raises(error):
        service.plan_change(
            PlanProfileAvailabilityRequest(profile_id=profile.profile_id, target=target)
        )


def test_snell_resume_rejects_supported_preview_version_race_before_apply() -> None:
    profile = snell_profile(enabled=False)
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    state_store = MemoryStateStore(initial)
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.48")
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=snell_catalog(),
        port_source=AvailableFixedPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id=profile.profile_id,
            target=ProfileAvailability.ACTIVE,
        )
    )

    with pytest.raises(CoreVersionChanged):
        service.apply_change(plan, confirmed=True)


def test_snell_resume_rejects_forged_plan_without_core_version_evidence() -> None:
    profile = snell_profile(enabled=False)
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    state_store = MemoryStateStore(initial)
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47")
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=snell_catalog(),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    forged_plan = ProfileAvailabilityPlan(
        profile_id=profile.profile_id,
        profile_name=profile.profile_name,
        current=ProfileAvailability.PAUSED,
        target=ProfileAvailability.ACTIVE,
        expected_revision=initial.revision,
        remaining_active_profile_count=1,
        port_selection=profile.port_selection,
        recorded_listen_port=profile.listen_port,
        port_may_change=False,
        requires_live_apply=True,
        observed_core_version=None,
    )

    with pytest.raises(CoreVersionUnknown):
        service.apply_change(forged_plan, confirmed=True)

    assert inspector.calls == 1
    assert state_store.load() == initial


def test_reality_resume_freezes_version_when_active_snell_is_retained() -> None:
    snell = snell_profile(enabled=True)
    reality = reality_profile(enabled=False)
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(snell, reality))
    state_store = MemoryStateStore(initial)
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.48")
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailableFixedPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id=reality.profile_id,
            target=ProfileAvailability.ACTIVE,
        )
    )

    assert plan.observed_core_version == "1.14.0-alpha.47"
    with pytest.raises(CoreVersionChanged):
        service.apply_change(plan, confirmed=True)
    assert inspector.calls == EXPECTED_CORE_INSPECTIONS
    assert state_store.load() == initial


def test_pausing_one_active_snell_freezes_version_for_retained_snell() -> None:
    selected = snell_profile(enabled=True)
    retained = replace(
        snell_profile(enabled=True),
        profile_id="profile-8",
        profile_name="Retained Snell preview",
        listen_port=18444,
    )
    initial = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(selected, retained),
    )
    state_store = MemoryStateStore(initial)
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.48")
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=snell_catalog(),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id=selected.profile_id,
            target=ProfileAvailability.PAUSED,
        )
    )

    assert plan.observed_core_version == "1.14.0-alpha.47"
    with pytest.raises(CoreVersionChanged):
        service.apply_change(plan, confirmed=True)
    assert inspector.calls == EXPECTED_CORE_INSPECTIONS
    assert state_store.load() == initial

    assert state_store.load() == initial


def test_applied_profile_can_plan_pause_without_host_effects() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="临时暂停",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    service = ProfileAvailabilityService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )

    assert plan.profile_id == "profile-1"
    assert plan.profile_name == "临时暂停"
    assert plan.current is ProfileAvailability.ACTIVE
    assert plan.target is ProfileAvailability.PAUSED
    assert plan.expected_revision == PLANNED_REVISION
    assert plan.remaining_active_profile_count == 0
    assert plan.requires_live_apply is True


def test_pause_plan_rejects_profile_that_is_already_paused() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="已暂停",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    service = ProfileAvailabilityService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileAvailabilityNoChangeError, match="already paused"):
        service.plan_change(
            PlanProfileAvailabilityRequest(
                profile_id="profile-1",
                target=ProfileAvailability.PAUSED,
            )
        )


def test_draft_profile_must_be_applied_instead_of_resumed() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="尚未应用",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    service = ProfileAvailabilityService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileAvailabilityDraftError, match="apply the draft"):
        service.plan_change(
            PlanProfileAvailabilityRequest(
                profile_id="profile-1",
                target=ProfileAvailability.ACTIVE,
            )
        )


def test_missing_profile_has_a_typed_availability_error() -> None:
    service = ProfileAvailabilityService(
        state_store=MemoryStateStore(),
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileAvailabilityNotFoundError, match="profile-missing"):
        service.plan_change(
            PlanProfileAvailabilityRequest(
                profile_id="profile-missing",
                target=ProfileAvailability.PAUSED,
            )
        )


def test_confirmed_pause_transaction_removes_inbound_and_preserves_profile() -> None:
    material = RealityMaterial(
        user_uuid="11111111-1111-4111-8111-111111111111",
        private_key="private-key",
        public_key="public-key",
        short_id="0123456789abcdef",
        server_name="www.cloudflare.com",
    )
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="维护中的配置",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        protocol_material=material,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=4,
            profiles=(profile,),
            expected_config_sha256="a" * 64,
        )
    )
    applier = RecordingSuccessfulApplier()
    apply_lock = TrackingLock()
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=applier,
        apply_lock=apply_lock,
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )

    result = service.apply_change(plan, confirmed=True)

    expected_document = {
        "inbounds": [],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    assert result.transaction.outcome is ApplyOutcome.APPLIED
    assert result.committed_revision == plan.expected_revision + 1
    assert result.availability is ProfileAvailability.PAUSED
    assert result.listen_port == profile.listen_port
    assert apply_lock.acquisitions == 1
    assert applier.document == expected_document
    assert applier.precondition == ConfigTargetPrecondition.matching_sha256("a" * 64)
    committed = state_store.load()
    assert committed.revision == plan.expected_revision + 1
    assert committed.profiles == (replace(profile, enabled=False),)
    assert committed.expected_config_sha256 == configuration_sha256(expected_document)


def test_rejected_pause_transaction_does_not_commit_desired_state() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="保持在线",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    initial = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(profile,),
        expected_config_sha256="a" * 64,
    )
    state_store = MemoryStateStore(initial)
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=RejectingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )

    result = service.apply_change(plan, confirmed=True)

    assert result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED
    assert result.committed_revision is None
    assert result.availability is ProfileAvailability.ACTIVE
    assert result.listen_port == profile.listen_port
    assert state_store.load() == initial


def test_availability_change_requires_confirmation_before_lock_or_apply() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="保持在线",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    state_store = MemoryStateStore(initial)
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )

    with pytest.raises(ProfileAvailabilityConfirmationRequiredError):
        service.apply_change(plan, confirmed=False)

    assert state_store.load() == initial


def test_availability_change_rejects_stale_desired_state_revision() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="并发变更",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    )
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )
    state_store.save(ManagedInstallation(schema_version=1, revision=5, profiles=(profile,)))

    with pytest.raises(StateRevisionConflictError, match="changed from 4 to 5"):
        service.apply_change(plan, confirmed=True)

    assert state_store.load().revision == plan.expected_revision + 1
    assert state_store.load().profiles == (profile,)


def test_availability_change_rechecks_profile_state_under_lock() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="并发变更",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    )
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=ExplodingPortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.PAUSED,
        )
    )
    state_store.save(
        ManagedInstallation(
            schema_version=1,
            revision=4,
            profiles=(replace(profile, enabled=False),),
        )
    )

    with pytest.raises(ProfileAvailabilityPlanChangedError, match="no longer matches"):
        service.apply_change(plan, confirmed=True)


def test_fixed_port_resume_plan_rejects_unavailable_port() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="等待恢复",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    service = ProfileAvailabilityService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=UnavailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileResumePortUnavailableError, match="Port 4433"):
        service.plan_change(
            PlanProfileAvailabilityRequest(
                profile_id="profile-1",
                target=ProfileAvailability.ACTIVE,
            )
        )


def test_fixed_port_resume_rechecks_availability_under_lock() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="端口竞态",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(profile,))
    )
    port_source = PortBecomesUnavailableSource()
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=port_source,
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.ACTIVE,
        )
    )

    with pytest.raises(ProfileResumePortUnavailableError, match="Port 4433"):
        service.apply_change(plan, confirmed=True)

    assert port_source.probes == EXPECTED_PORT_PROBES
    assert state_store.load().profiles == (profile,)


def test_confirmed_fixed_port_resume_restores_inbound_and_preserved_material() -> None:
    material = RealityMaterial(
        user_uuid="11111111-1111-4111-8111-111111111111",
        private_key="private-key",
        public_key="public-key",
        short_id="0123456789abcdef",
        server_name="www.cloudflare.com",
    )
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="恢复配置",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
        protocol_material=material,
        server_address="proxy.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=5,
            profiles=(profile,),
            expected_config_sha256="b" * 64,
        )
    )
    port_source = AvailableFixedPortSource()
    applier = RecordingSuccessfulApplier()
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(
            (RealityHandler(material_source=ExplodingRealityMaterialSource()),)
        ),
        port_source=port_source,
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.ACTIVE,
        )
    )

    assert plan.port_selection is PortSelection.FIXED
    assert plan.recorded_listen_port == profile.listen_port
    assert plan.port_may_change is False

    result = service.apply_change(plan, confirmed=True)

    assert result.transaction.outcome is ApplyOutcome.APPLIED
    assert result.committed_revision == plan.expected_revision + 1
    assert result.availability is ProfileAvailability.ACTIVE
    assert result.listen_port == profile.listen_port
    assert port_source.probes == EXPECTED_PORT_PROBES
    assert applier.precondition == ConfigTargetPrecondition.matching_sha256("b" * 64)
    assert applier.document is not None
    assert [inbound["tag"] for inbound in applier.document["inbounds"]] == ["profile-1"]
    committed = state_store.load()
    assert committed.profiles == (replace(profile, enabled=True),)
    assert committed.profiles[0].protocol_material == material


def test_automatic_resume_selects_new_port_under_lock_when_recorded_port_is_busy() -> None:
    target_material = RealityMaterial(
        user_uuid="11111111-1111-4111-8111-111111111111",
        private_key="target-private-key",
        public_key="target-public-key",
        short_id="0123456789abcdef",
        server_name="www.cloudflare.com",
    )
    existing_material = RealityMaterial(
        user_uuid="22222222-2222-4222-8222-222222222222",
        private_key="existing-private-key",
        public_key="existing-public-key",
        short_id="fedcba9876543210",
        server_name="www.example.org",
    )
    target = ManagedProfile(
        profile_id="profile-1",
        profile_name="自动恢复",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.APPLIED,
        enabled=False,
        protocol_material=target_material,
    )
    existing = ManagedProfile(
        profile_id="profile-2",
        profile_name="保持在线",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        protocol_material=existing_material,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=6,
            profiles=(target, existing),
            expected_config_sha256="c" * 64,
        )
    )
    port_source = AutomaticResumePortSource()
    applier = RecordingSuccessfulApplier()
    service = ProfileAvailabilityService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(
            (RealityHandler(material_source=ExplodingRealityMaterialSource()),)
        ),
        port_source=port_source,
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = service.plan_change(
        PlanProfileAvailabilityRequest(
            profile_id="profile-1",
            target=ProfileAvailability.ACTIVE,
        )
    )

    assert plan.port_selection is PortSelection.AUTOMATIC
    assert plan.recorded_listen_port == target.listen_port
    assert plan.port_may_change is True

    result = service.apply_change(plan, confirmed=True)

    assert result.committed_revision == plan.expected_revision + 1
    assert result.listen_port == AUTOMATIC_RESUME_PORT
    assert port_source.excluded_ports == frozenset({8443})
    assert applier.document is not None
    assert [inbound["listen_port"] for inbound in applier.document["inbounds"]] == [
        9443,
        8443,
    ]
    assert state_store.load().profiles[0] == replace(
        target,
        enabled=True,
        listen_port=9443,
    )
