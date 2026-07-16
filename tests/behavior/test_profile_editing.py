from collections.abc import Iterator
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
    ProfileEditScope,
    ProfileEditValidationError,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.protocols.catalog import MaterializedProfile, ProtocolCatalog
from sb_manager.seams.config_validator import ConfigValidationResult
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


class ExplodingApplier:
    def apply(self, document: object, *, precondition: object) -> object:
        raise AssertionError("planning a profile edit must not apply configuration")


class ExplodingLock:
    def acquire(self) -> object:
        raise AssertionError("planning a profile edit must not acquire the mutation lock")


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
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="  新名称  ",
            server_address="  new.example.com  ",
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
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditValidationError) as captured:
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="   ",
                server_address=None,
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
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    with pytest.raises(ProfileEditNoChangesError, match="No profile fields changed"):
        editor.plan_edit(
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="  现有名称 ",
                server_address=" proxy.example.com ",
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
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="手机",
            server_address="new.example.com",
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
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="proxy.example.com",
        )
    )

    assert plan.changed_fields == ("profile_name",)
    assert plan.scope is ProfileEditScope.LIVE_CONFIGURATION


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
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
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
        applier=ExplodingApplier(),
        apply_lock=lock,
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="new.example.com",
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
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address="proxy.example.com",
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
        applier=RejectingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="不会提交",
            server_address=None,
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
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
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
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
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
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = editor.plan_edit(
        PlanProfileEditRequest(
            profile_id="profile-1",
            profile_name="新名称",
            server_address=None,
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
