from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.application.profile_cloning import (
    PlanProfileCloneRequest,
    ProfileCloneConfirmationRequiredError,
    ProfileCloneFacet,
    ProfileCloneNameError,
    ProfileCloneNotFoundError,
    ProfileCloneSourceChangedError,
    ProfileCloningService,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import VlessMaterial
from sb_manager.tls.catalog import AcmeTlsIntent
from sb_manager.transports.catalog import WebSocketTransportIntent

SOURCE_REVISION = 7
COMMITTED_REVISION = 8


class TrackingApplyLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


def source_profile() -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_TLS,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=False,
        protocol_material=VlessMaterial(user_uuid="source-secret-uuid"),
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=Path("/var/lib/sing-box-manager/acme"),
        ),
        transport_intent=WebSocketTransportIntent(path="/proxy", host="cdn.example.com"),
    )


def installation(*extra_profiles: ManagedProfile) -> ManagedInstallation:
    return ManagedInstallation(
        schema_version=1,
        revision=SOURCE_REVISION,
        profiles=(source_profile(), *extra_profiles),
        expected_config_sha256="a" * 64,
    )


def test_clone_plan_suggests_a_unique_name_without_mutating_or_locking() -> None:
    existing_copy = ManagedProfile(
        profile_id="profile-2",
        profile_name="手机 副本",
        protocol=ProtocolKind.SHADOWSOCKS,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(installation(existing_copy))
    lock = TrackingApplyLock()
    cloner = ProfileCloningService(state_store=state_store, mutation_lock=lock)

    plan = cloner.plan(PlanProfileCloneRequest(source_profile_id="profile-1"))

    assert plan.base_revision == SOURCE_REVISION
    assert plan.source_profile_name == "手机"
    assert plan.profile_name == "手机 副本 2"
    assert plan.protocol is ProtocolKind.VLESS_TLS
    assert plan.copied_facets == (
        ProfileCloneFacet.PROTOCOL,
        ProfileCloneFacet.SERVER_ADDRESS,
        ProfileCloneFacet.TLS_STRATEGY,
        ProfileCloneFacet.TRANSPORT,
    )
    assert plan.reset_facets == (
        ProfileCloneFacet.CREDENTIALS,
        ProfileCloneFacet.LISTEN_PORT,
        ProfileCloneFacet.RUNTIME_STATUS,
    )
    assert plan.mutates_host is False
    assert state_store.load() == installation(existing_copy)
    assert lock.acquisitions == 0


def test_clone_plan_normalizes_name_and_rejects_blank_or_duplicate_names() -> None:
    state_store = MemoryStateStore(installation())
    cloner = ProfileCloningService(
        state_store=state_store,
        mutation_lock=TrackingApplyLock(),
    )

    plan = cloner.plan(
        PlanProfileCloneRequest(
            source_profile_id="profile-1",
            profile_name="  平板  ",
        )
    )

    assert plan.profile_name == "平板"
    with pytest.raises(ProfileCloneNameError, match="名称不能为空"):
        cloner.plan(
            PlanProfileCloneRequest(
                source_profile_id="profile-1",
                profile_name="   ",
            )
        )
    with pytest.raises(ProfileCloneNameError, match="名称已存在"):
        cloner.plan(
            PlanProfileCloneRequest(
                source_profile_id="profile-1",
                profile_name="手机",
            )
        )


def test_clone_requires_confirmation_before_acquiring_the_lock() -> None:
    lock = TrackingApplyLock()
    cloner = ProfileCloningService(
        state_store=MemoryStateStore(installation()),
        mutation_lock=lock,
    )
    plan = cloner.plan(PlanProfileCloneRequest(source_profile_id="profile-1"))

    with pytest.raises(ProfileCloneConfirmationRequiredError):
        cloner.clone(plan, confirmed=False)

    assert lock.acquisitions == 0


def test_confirmed_clone_copies_intent_but_resets_secrets_port_and_runtime() -> None:
    state_store = MemoryStateStore(installation())
    lock = TrackingApplyLock()
    cloner = ProfileCloningService(state_store=state_store, mutation_lock=lock)
    plan = cloner.plan(
        PlanProfileCloneRequest(
            source_profile_id="profile-1",
            profile_name="平板",
        )
    )

    result = cloner.clone(plan, confirmed=True)

    committed = state_store.load()
    clone = committed.profiles[-1]
    assert result.profile_id == "profile-8"
    assert result.profile_name == "平板"
    assert result.committed_revision == COMMITTED_REVISION
    assert committed.revision == COMMITTED_REVISION
    assert committed.expected_config_sha256 == "a" * 64
    assert committed.profiles[0] == source_profile()
    assert clone == ManagedProfile(
        profile_id="profile-8",
        profile_name="平板",
        protocol=ProtocolKind.VLESS_TLS,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.DRAFT,
        protocol_material=None,
        server_address="vpn.example.com",
        tls_intent=source_profile().tls_intent,
        transport_intent=source_profile().transport_intent,
    )
    assert lock.acquisitions == 1


def test_clone_rejects_a_stale_plan_without_changing_desired_state() -> None:
    state_store = MemoryStateStore(installation())
    cloner = ProfileCloningService(
        state_store=state_store,
        mutation_lock=TrackingApplyLock(),
    )
    plan = cloner.plan(PlanProfileCloneRequest(source_profile_id="profile-1"))
    changed = ManagedInstallation(
        schema_version=1,
        revision=COMMITTED_REVISION,
        profiles=installation().profiles,
        expected_config_sha256="a" * 64,
    )
    state_store.save(changed)

    with pytest.raises(StateRevisionConflictError):
        cloner.clone(plan, confirmed=True)

    assert state_store.load() == changed


def test_clone_rejects_source_intent_changed_without_a_revision_increment() -> None:
    state_store = MemoryStateStore(installation())
    cloner = ProfileCloningService(
        state_store=state_store,
        mutation_lock=TrackingApplyLock(),
    )
    plan = cloner.plan(PlanProfileCloneRequest(source_profile_id="profile-1"))
    tampered = ManagedInstallation(
        schema_version=1,
        revision=SOURCE_REVISION,
        profiles=(replace(source_profile(), server_address="changed.example.com"),),
        expected_config_sha256="a" * 64,
    )
    state_store.save(tampered)

    with pytest.raises(ProfileCloneSourceChangedError):
        cloner.clone(plan, confirmed=True)

    assert state_store.load() == tampered


def test_clone_reports_a_missing_source_during_plan_and_confirmation() -> None:
    state_store = MemoryStateStore(installation())
    cloner = ProfileCloningService(
        state_store=state_store,
        mutation_lock=TrackingApplyLock(),
    )
    with pytest.raises(ProfileCloneNotFoundError):
        cloner.plan(PlanProfileCloneRequest(source_profile_id="missing"))

    plan = cloner.plan(PlanProfileCloneRequest(source_profile_id="profile-1"))
    state_store.save(
        ManagedInstallation(
            schema_version=1,
            revision=SOURCE_REVISION,
            profiles=(),
            expected_config_sha256="a" * 64,
        )
    )
    with pytest.raises(ProfileCloneNotFoundError):
        cloner.clone(plan, confirmed=True)
