from collections.abc import Collection, Iterator
from contextlib import contextmanager

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_editing import (
    PlanProfileEditRequest,
    ProfileEditConfirmationRequiredError,
    ProfileEditingService,
    ProfileEditNoChangesError,
    ProfileEditPlanChangedError,
    ProfileEditPortUnavailableError,
    ProfileEditScope,
    ProfileEditValidationError,
)
from sb_manager.application.protocol_compatibility import (
    ActiveCoreProtocolCompatibility,
    CoreVersionChanged,
    ProtocolUnsupportedByCore,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import SnellV6Material
from sb_manager.protocols.catalog import MaterializedProfile, ProtocolCatalog
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.core_status import CoreStatusObservation
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256

PLANNED_REVISION = 7
COMMITTED_REVISION = 8
CONCURRENT_REVISION = 5
ORIGINAL_PORT = 4433
EDITED_PORT = 8443
AUTOMATIC_PORT = 9443


class ExplodingApplier:
    def apply(self, document: object, *, precondition: object) -> object:
        raise AssertionError("planning a profile edit must not apply configuration")


class ExplodingLock:
    def acquire(self) -> object:
        raise AssertionError("planning a profile edit must not acquire the mutation lock")


class AvailablePortSource:
    def is_available(self, port: int) -> bool:
        return True

    def choose_available(self) -> int:
        raise AssertionError("a fixed-port plan must not select an automatic port")


class UnavailablePortSource:
    def is_available(self, port: int) -> bool:
        return False

    def choose_available(self) -> int:
        raise AssertionError("an unavailable fixed port must not trigger automatic selection")


class PortBecomesUnavailableSource:
    def __init__(self) -> None:
        self.observations = iter((True, False))

    def is_available(self, port: int) -> bool:
        return next(self.observations)

    def choose_available(self) -> int:
        raise AssertionError("a fixed-port edit must not select an automatic port")


class AutomaticPortSource:
    def is_available(self, port: int) -> bool:
        raise AssertionError("an automatic-port edit must not probe a fixed port")

    def choose_available(self, *, excluded_ports: Collection[int] = ()) -> int:
        return AUTOMATIC_PORT


class ReservedAwareAutomaticPortSource:
    def is_available(self, port: int) -> bool:
        raise AssertionError("an automatic-port edit must not probe a fixed port")

    def choose_available(self, *, excluded_ports: Collection[int]) -> int:
        if EDITED_PORT not in excluded_ports:
            raise AssertionError("manager-declared ports must be excluded")
        return AUTOMATIC_PORT


class TrackingLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


class RecordingProfileHandler:
    kind = ProtocolKind.VLESS_REALITY

    def __init__(self) -> None:
        self.profile_names: list[str] = []

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        self.profile_names.append(profile.profile_name)
        return MaterializedProfile(
            profile=profile,
            inbound={
                "type": "vless",
                "tag": profile.profile_id,
                "listen_port": listen_port,
                "users": [{"name": profile.profile_name}],
            },
            connection_info=None,
        )


class RecordingSnellProfileHandler(RecordingProfileHandler):
    kind = ProtocolKind.SNELL_V6


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
    *,
    enabled: bool = True,
    status: ProfileStatus = ProfileStatus.APPLIED,
) -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-snell",
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


def reality_profile() -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-reality",
        profile_name="Reality",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )


class RecordingSuccessfulApplier:
    def __init__(self) -> None:
        self.document: object | None = None
        self.precondition: ConfigTargetPrecondition | None = None

    def apply(
        self,
        document: object,
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
            commit=CommitResult(success=True, diagnostics="committed"),
        )


class RejectingApplier:
    def apply(
        self,
        document: object,
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        return ApplyTransactionResult(
            outcome=ApplyOutcome.VALIDATION_FAILED,
            validation=ConfigValidationResult(
                valid=False,
                diagnostics="edited candidate is invalid",
            ),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
        )


def test_editing_applied_snell_under_stable_is_rejected_before_apply() -> None:
    profile = snell_profile()
    initial = ManagedInstallation(schema_version=1, revision=7, profiles=(profile,))
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RecordingSnellProfileHandler(),)),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=SequenceCoreStatusInspector("1.13.14")
        ),
    )

    with pytest.raises(ProtocolUnsupportedByCore):
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id=profile.profile_id,
                profile_name="Renamed Snell",
                server_address=None,
                listen_port=profile.listen_port,
            )
        )

    assert state_store.load() == initial


def test_editing_other_applied_profile_rejects_stable_when_active_snell_remains() -> None:
    snell = snell_profile()
    reality = reality_profile()
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=7, profiles=(snell, reality))
    )
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=SequenceCoreStatusInspector("1.13.14")
        ),
    )

    with pytest.raises(ProtocolUnsupportedByCore):
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id=reality.profile_id,
                profile_name="Renamed Reality",
                server_address=None,
                listen_port=reality.listen_port,
            )
        )


@pytest.mark.parametrize(
    "profile",
    (
        snell_profile(status=ProfileStatus.DRAFT),
        snell_profile(enabled=False),
    ),
)
def test_editing_draft_or_paused_snell_does_not_probe_core(profile: ManagedProfile) -> None:
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(profile,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(
            inspector=InspectorThatMustNotBeCalled()
        ),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id=profile.profile_id,
            profile_name="Renamed inactive Snell",
            server_address=None,
            listen_port=profile.listen_port,
        )
    )

    assert plan.observed_core_version is None


def test_snell_retaining_edit_rejects_supported_preview_version_race() -> None:
    profile = snell_profile()
    initial = ManagedInstallation(schema_version=1, revision=7, profiles=(profile,))
    state_store = MemoryStateStore(initial)
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.48")
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RecordingSnellProfileHandler(),)),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id=profile.profile_id,
            profile_name="Renamed Snell",
            server_address=None,
            listen_port=profile.listen_port,
        )
    )

    assert plan.observed_core_version == "1.14.0-alpha.47"
    with pytest.raises(CoreVersionChanged):
        editor.apply_edit(plan, confirmed=True)

    assert state_store.load() == initial


def test_applied_profile_port_edit_plan_is_read_only_and_requires_live_apply() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="proxy.example.com",
    )
    initial = ManagedInstallation(schema_version=1, revision=7, profiles=(applied,))
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address="proxy.example.com",
            listen_port=8443,
        )
    )

    assert plan.previous_listen_port == ORIGINAL_PORT
    assert plan.listen_port == EDITED_PORT
    assert plan.previous_port_selection is PortSelection.FIXED
    assert plan.port_selection is PortSelection.FIXED
    assert plan.changed_fields == ("listen_port",)
    assert plan.scope is ProfileEditScope.LIVE_CONFIGURATION
    assert plan.mutates_host is False
    assert state_store.load() == initial


def test_fixing_the_current_automatic_port_changes_only_desired_state_policy() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=ORIGINAL_PORT,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.APPLIED,
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(applied,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=UnavailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address=None,
            listen_port=ORIGINAL_PORT,
        )
    )

    assert plan.changed_fields == ("port_selection",)
    assert plan.previous_port_selection is PortSelection.AUTOMATIC
    assert plan.port_selection is PortSelection.FIXED
    assert plan.scope is ProfileEditScope.DESIRED_STATE_ONLY


def test_profile_edit_rejects_a_port_outside_the_valid_range() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditValidationError) as captured:
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="手机",
                server_address=None,
                listen_port=65_536,
            )
        )

    assert captured.value.field == "listen_port"
    assert captured.value.message == "端口必须在 1 到 65535 之间，或留空以自动选择"


def test_profile_edit_rejects_a_port_already_declared_by_another_profile() -> None:
    selected = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    other = ManagedProfile(
        profile_id="profile-2",
        profile_name="平板",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(
                schema_version=1,
                revision=7,
                profiles=(selected, other),
            )
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditValidationError) as captured:
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="手机",
                server_address=None,
                listen_port=8443,
            )
        )

    assert captured.value.field == "listen_port"
    assert captured.value.message == "端口 8443 已被配置“平板”使用"


def test_profile_edit_rejects_a_new_fixed_port_that_is_currently_unavailable() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(applied,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=UnavailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditValidationError) as captured:
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="手机",
                server_address=None,
                listen_port=8443,
            )
        )

    assert captured.value.field == "listen_port"
    assert captured.value.message == ("端口 8443 当前不可用，请选择其他端口或留空自动选择")


def test_draft_profile_edit_plan_is_read_only_and_normalizes_operator_input() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="old.example.com",
    )
    initial = ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="  新名称  ",
            server_address="  new.example.com  ",
            listen_port=4433,
        )
    )

    assert plan.profile_id == "profile-1"
    assert plan.previous_profile_name == "旧名称"
    assert plan.profile_name == "新名称"
    assert plan.previous_server_address == "old.example.com"
    assert plan.server_address == "new.example.com"
    assert plan.expected_revision == PLANNED_REVISION
    assert plan.scope is ProfileEditScope.DESIRED_STATE_ONLY
    assert plan.changed_fields == ("profile_name", "server_address")
    assert plan.mutates_host is False
    assert state_store.load() == initial


def test_profile_edit_rejects_an_empty_name_with_field_guidance() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditValidationError) as captured:
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="   ",
                server_address=None,
                listen_port=4433,
            )
        )

    assert captured.value.field == "profile_name"
    assert captured.value.message == "请输入配置名称"


def test_profile_edit_rejects_a_plan_without_observable_changes() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="现有名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="proxy.example.com",
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditNoChangesError, match="No profile fields changed"):
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="  现有名称 ",
                server_address=" proxy.example.com ",
                listen_port=4433,
            )
        )


def test_applied_profile_public_address_edit_does_not_claim_host_mutation() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="old.example.com",
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(applied,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address="new.example.com",
            listen_port=4433,
        )
    )

    assert plan.status is ProfileStatus.APPLIED
    assert plan.changed_fields == ("server_address",)
    assert plan.scope is ProfileEditScope.DESIRED_STATE_ONLY


def test_applied_profile_name_edit_requires_a_live_configuration_transaction() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="proxy.example.com",
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(applied,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="proxy.example.com",
            listen_port=4433,
        )
    )

    assert plan.changed_fields == ("profile_name",)
    assert plan.scope is ProfileEditScope.LIVE_CONFIGURATION


def test_paused_profile_name_edit_changes_only_desired_state() -> None:
    paused = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
        server_address="proxy.example.com",
    )
    editor = ProfileEditingService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(paused,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="proxy.example.com",
            listen_port=4433,
        )
    )

    assert plan.changed_fields == ("profile_name",)
    assert plan.scope is ProfileEditScope.DESIRED_STATE_ONLY


def test_profile_edit_requires_confirmation_before_lock_or_mutation() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    initial = ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
            listen_port=4433,
        )
    )

    with pytest.raises(ProfileEditConfirmationRequiredError):
        editor.apply_edit(plan, confirmed=False)

    assert state_store.load() == initial


def test_confirmed_draft_edit_commits_only_desired_state() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="old.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=7,
            profiles=(draft,),
            expected_config_sha256="a" * 64,
        )
    )
    lock = TrackingLock()
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=lock,
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="new.example.com",
            listen_port=4433,
        )
    )

    result = editor.apply_edit(plan, confirmed=True)

    assert lock.acquisitions == 1
    assert result.scope is ProfileEditScope.DESIRED_STATE_ONLY
    assert result.committed_revision == COMMITTED_REVISION
    assert result.transaction is None
    assert state_store.load() == ManagedInstallation(
        schema_version=1,
        revision=8,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="新名称",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
                server_address="new.example.com",
            ),
        ),
        expected_config_sha256="a" * 64,
    )


def test_confirmed_applied_name_edit_rebuilds_live_configuration_before_state_commit() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="proxy.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=7,
            profiles=(applied,),
            expected_config_sha256="a" * 64,
        )
    )
    handler = RecordingProfileHandler()
    applier = RecordingSuccessfulApplier()
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((handler,)),
        port_source=AvailablePortSource(),
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="proxy.example.com",
            listen_port=4433,
        )
    )

    result = editor.apply_edit(plan, confirmed=True)

    expected_document = {
        "inbounds": [
            {
                "type": "vless",
                "tag": "profile-1",
                "listen_port": 4433,
                "users": [{"name": "新名称"}],
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    assert handler.profile_names == ["新名称"]
    assert applier.document == expected_document
    assert applier.precondition == ConfigTargetPrecondition.matching_sha256("a" * 64)
    assert result.scope is ProfileEditScope.LIVE_CONFIGURATION
    assert result.committed_revision == COMMITTED_REVISION
    assert result.transaction is not None
    assert result.transaction.outcome is ApplyOutcome.APPLIED
    edited = state_store.load()
    assert edited.profiles[0].profile_name == "新名称"
    assert edited.expected_config_sha256 == configuration_sha256(expected_document)


def test_confirmed_applied_port_edit_rebuilds_live_configuration_before_state_commit() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="proxy.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=7,
            profiles=(applied,),
            expected_config_sha256="a" * 64,
        )
    )
    applier = RecordingSuccessfulApplier()
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RecordingProfileHandler(),)),
        port_source=AvailablePortSource(),
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address="proxy.example.com",
            listen_port=8443,
        )
    )

    result = editor.apply_edit(plan, confirmed=True)

    expected_document = {
        "inbounds": [
            {
                "type": "vless",
                "tag": "profile-1",
                "listen_port": 8443,
                "users": [{"name": "手机"}],
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    assert applier.document == expected_document
    assert applier.precondition == ConfigTargetPrecondition.matching_sha256("a" * 64)
    assert result.scope is ProfileEditScope.LIVE_CONFIGURATION
    assert result.committed_revision == COMMITTED_REVISION
    edited = state_store.load()
    assert edited.profiles[0].listen_port == EDITED_PORT
    assert edited.profiles[0].port_selection is PortSelection.FIXED
    assert edited.expected_config_sha256 == configuration_sha256(expected_document)


def test_port_becoming_unavailable_after_review_prevents_any_edit() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    initial = ManagedInstallation(
        schema_version=1,
        revision=7,
        profiles=(applied,),
        expected_config_sha256="a" * 64,
    )
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=PortBecomesUnavailableSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address=None,
            listen_port=8443,
        )
    )

    with pytest.raises(ProfileEditPortUnavailableError) as captured:
        editor.apply_edit(plan, confirmed=True)

    assert captured.value.port == EDITED_PORT
    assert str(captured.value) == "端口 8443 在确认后已不可用，请重新预览"
    assert state_store.load() == initial


def test_confirmed_applied_edit_can_select_and_persist_an_automatic_port() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=7,
            profiles=(applied,),
            expected_config_sha256="a" * 64,
        )
    )
    applier = RecordingSuccessfulApplier()
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RecordingProfileHandler(),)),
        port_source=AutomaticPortSource(),
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address=None,
            listen_port=None,
        )
    )

    result = editor.apply_edit(plan, confirmed=True)

    assert plan.listen_port is None
    assert plan.port_selection is PortSelection.AUTOMATIC
    assert result.committed_revision == COMMITTED_REVISION
    assert result.listen_port == AUTOMATIC_PORT
    assert applier.document == {
        "inbounds": [
            {
                "type": "vless",
                "tag": "profile-1",
                "listen_port": 9443,
                "users": [{"name": "手机"}],
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    edited = state_store.load().profiles[0]
    assert edited.listen_port == AUTOMATIC_PORT
    assert edited.port_selection is PortSelection.AUTOMATIC


def test_automatic_port_edit_excludes_ports_declared_by_other_profiles() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=ORIGINAL_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    reserved_draft = ManagedProfile(
        profile_id="profile-2",
        profile_name="平板",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=EDITED_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=7,
            profiles=(applied, reserved_draft),
            expected_config_sha256="a" * 64,
        )
    )
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RecordingProfileHandler(),)),
        port_source=ReservedAwareAutomaticPortSource(),
        applier=RecordingSuccessfulApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address=None,
            listen_port=None,
        )
    )

    result = editor.apply_edit(plan, confirmed=True)

    assert result.committed_revision == COMMITTED_REVISION
    edited_profiles = state_store.load().profiles
    assert edited_profiles[0].listen_port == AUTOMATIC_PORT
    assert edited_profiles[1].listen_port == EDITED_PORT


def test_failed_live_profile_edit_preserves_desired_state() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="仍在使用",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    initial = ManagedInstallation(
        schema_version=1,
        revision=7,
        profiles=(applied,),
        expected_config_sha256="a" * 64,
    )
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RecordingProfileHandler(),)),
        port_source=AvailablePortSource(),
        applier=RejectingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="不会提交",
            server_address=None,
            listen_port=4433,
        )
    )

    result = editor.apply_edit(plan, confirmed=True)

    assert result.committed_revision is None
    assert result.transaction is not None
    assert result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED
    assert state_store.load() == initial


def test_profile_edit_rejects_a_stale_desired_state_revision() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
            listen_port=4433,
        )
    )
    state_store.save(ManagedInstallation(schema_version=1, revision=5, profiles=(draft,)))

    with pytest.raises(StateRevisionConflictError, match="changed from 4 to 5"):
        editor.apply_edit(plan, confirmed=True)

    assert state_store.load().revision == CONCURRENT_REVISION


def test_profile_edit_reports_revision_conflict_when_another_session_made_same_edit() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(draft,))
    )
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
            listen_port=4433,
        )
    )
    state_store.save(
        ManagedInstallation(
            schema_version=1,
            revision=5,
            profiles=(
                ManagedProfile(
                    profile_id="profile-1",
                    profile_name="新名称",
                    protocol=ProtocolKind.VLESS_REALITY,
                    listen_port=4433,
                    port_selection=PortSelection.FIXED,
                    status=ProfileStatus.DRAFT,
                ),
            ),
        )
    )

    with pytest.raises(StateRevisionConflictError, match="changed from 4 to 5"):
        editor.apply_edit(plan, confirmed=True)


def test_profile_edit_rejects_same_revision_content_that_no_longer_matches_plan() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧名称",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=4, profiles=(draft,))
    )
    editor = ProfileEditingService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        port_source=AvailablePortSource(),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
            listen_port=4433,
        )
    )
    state_store.save(
        ManagedInstallation(
            schema_version=1,
            revision=4,
            profiles=(
                ManagedProfile(
                    profile_id="profile-1",
                    profile_name="被篡改的名称",
                    protocol=ProtocolKind.VLESS_REALITY,
                    listen_port=4433,
                    port_selection=PortSelection.FIXED,
                    status=ProfileStatus.DRAFT,
                ),
            ),
        )
    )

    with pytest.raises(ProfileEditPlanChangedError, match="no longer matches"):
        editor.apply_edit(plan, confirmed=True)
