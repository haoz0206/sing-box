from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_removal import (
    ProfileRemovalConfirmationRequiredError,
    ProfileRemovalScope,
    ProfileRemovalService,
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
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256

PLANNED_REVISION = 7
DRAFT_REMOVAL_REVISION = 8
APPLIED_REMOVAL_REVISION = 5


class ExplodingApplier:
    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        raise AssertionError("a removal plan must not apply configuration")


class ExplodingLock:
    def acquire(self) -> None:
        raise AssertionError("a removal plan must not acquire the mutation lock")


class TrackingLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


class RecordingRealityHandler:
    kind = ProtocolKind.VLESS_REALITY

    def __init__(self) -> None:
        self.profile_ids: list[str] = []

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        self.profile_ids.append(profile.profile_id)
        return MaterializedProfile(
            profile=profile,
            inbound={
                "type": "vless",
                "tag": profile.profile_id,
                "listen_port": listen_port,
            },
            connection_info=None,
        )


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
            validation=ConfigValidationResult(valid=False, diagnostics="invalid"),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
        )


def test_draft_profile_removal_plan_is_read_only_and_desired_state_only() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="临时测试",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
    )
    remover = ProfileRemovalService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = remover.plan_removal("profile-1")

    assert plan.profile_id == "profile-1"
    assert plan.profile_name == "临时测试"
    assert plan.protocol is ProtocolKind.VLESS_REALITY
    assert plan.status is ProfileStatus.DRAFT
    assert plan.expected_revision == PLANNED_REVISION
    assert plan.scope is ProfileRemovalScope.DESIRED_STATE_ONLY
    assert plan.remaining_profile_count == 0
    assert plan.remaining_applied_count == 0
    assert plan.mutates_host is False
    assert state_store.load().profiles == (draft,)


def test_paused_applied_profile_removal_changes_only_desired_state() -> None:
    paused = ManagedProfile(
        profile_id="profile-1",
        profile_name="已暂停",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
    )
    remover = ProfileRemovalService(
        state_store=MemoryStateStore(
            ManagedInstallation(schema_version=1, revision=7, profiles=(paused,))
        ),
        protocol_catalog=ProtocolCatalog(()),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )

    plan = remover.plan_removal("profile-1")

    assert plan.status is ProfileStatus.APPLIED
    assert plan.scope is ProfileRemovalScope.DESIRED_STATE_ONLY


def test_profile_removal_requires_confirmation_before_lock_or_mutation() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="临时测试",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    initial = ManagedInstallation(schema_version=1, revision=7, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    remover = ProfileRemovalService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        applier=ExplodingApplier(),
        apply_lock=ExplodingLock(),
    )
    plan = remover.plan_removal("profile-1")

    with pytest.raises(ProfileRemovalConfirmationRequiredError):
        remover.remove_profile(plan, confirmed=False)

    assert state_store.load() == initial


def test_confirmed_draft_removal_commits_only_desired_state() -> None:
    applied = ManagedProfile(
        profile_id="profile-1",
        profile_name="正在使用",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    draft = ManagedProfile(
        profile_id="profile-2",
        profile_name="临时测试",
        protocol=ProtocolKind.SHADOWSOCKS,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=7,
            profiles=(applied, draft),
            expected_config_sha256="a" * 64,
        )
    )
    lock = TrackingLock()
    remover = ProfileRemovalService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        applier=ExplodingApplier(),
        apply_lock=lock,
    )
    plan = remover.plan_removal("profile-2")

    result = remover.remove_profile(plan, confirmed=True)

    assert lock.acquisitions == 1
    assert result.scope is ProfileRemovalScope.DESIRED_STATE_ONLY
    assert result.committed_revision == DRAFT_REMOVAL_REVISION
    assert result.remaining_profile_count == 1
    assert result.transaction is None
    assert state_store.load() == ManagedInstallation(
        schema_version=1,
        revision=8,
        profiles=(applied,),
        expected_config_sha256="a" * 64,
    )


def test_confirmed_applied_removal_rebuilds_live_configuration_before_state_commit() -> None:
    target = ManagedProfile(
        profile_id="profile-1",
        profile_name="旧手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    survivor = ManagedProfile(
        profile_id="profile-2",
        profile_name="平板",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=4,
            profiles=(target, survivor),
            expected_config_sha256="a" * 64,
        )
    )
    handler = RecordingRealityHandler()
    applier = RecordingSuccessfulApplier()
    remover = ProfileRemovalService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((handler,)),
        applier=applier,
        apply_lock=TrackingLock(),
    )
    plan = remover.plan_removal("profile-1")

    result = remover.remove_profile(plan, confirmed=True)

    expected_document = {
        "inbounds": [
            {
                "type": "vless",
                "tag": "profile-2",
                "listen_port": 8443,
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    assert plan.scope is ProfileRemovalScope.LIVE_CONFIGURATION
    assert handler.profile_ids == ["profile-2"]
    assert applier.document == expected_document
    assert applier.precondition == ConfigTargetPrecondition.matching_sha256("a" * 64)
    assert result.scope is ProfileRemovalScope.LIVE_CONFIGURATION
    assert result.committed_revision == APPLIED_REMOVAL_REVISION
    assert result.remaining_profile_count == 1
    assert result.transaction is not None
    assert result.transaction.outcome is ApplyOutcome.APPLIED
    assert state_store.load() == ManagedInstallation(
        schema_version=1,
        revision=5,
        profiles=(survivor,),
        expected_config_sha256=configuration_sha256(expected_document),
    )


def test_failed_live_removal_keeps_profile_and_desired_state_revision() -> None:
    target = ManagedProfile(
        profile_id="profile-1",
        profile_name="仍在使用",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
    )
    initial = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(target,),
        expected_config_sha256="a" * 64,
    )
    state_store = MemoryStateStore(initial)
    remover = ProfileRemovalService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        applier=RejectingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = remover.plan_removal("profile-1")

    result = remover.remove_profile(plan, confirmed=True)

    assert result.committed_revision is None
    assert result.transaction is not None
    assert result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED
    assert state_store.load() == initial


def test_profile_removal_rejects_a_stale_desired_state_revision() -> None:
    target = ManagedProfile(
        profile_id="profile-1",
        profile_name="临时测试",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    initial = ManagedInstallation(schema_version=1, revision=4, profiles=(target,))
    state_store = MemoryStateStore(initial)
    remover = ProfileRemovalService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(()),
        applier=ExplodingApplier(),
        apply_lock=TrackingLock(),
    )
    plan = remover.plan_removal("profile-1")
    state_store.save(ManagedInstallation(schema_version=1, revision=5, profiles=(target,)))

    with pytest.raises(StateRevisionConflictError, match="changed from 4 to 5"):
        remover.remove_profile(plan, confirmed=True)

    assert state_store.load().revision == APPLIED_REMOVAL_REVISION
