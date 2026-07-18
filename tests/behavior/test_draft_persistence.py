from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import (
    DraftPreparationUnavailableError,
    Manager,
    PlanProfileRequest,
    StateRevisionConflictError,
)
from sb_manager.application.protocol_compatibility import ActiveCoreProtocolCompatibility
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import SnellV6Material
from sb_manager.protocols.catalog import ProtocolCatalog, SnellV6Handler
from sb_manager.seams.core_status import CoreStatusObservation


class TrackingMutationLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


class PreviewCoreInspector:
    def inspect(self) -> CoreStatusObservation:
        return CoreStatusObservation(
            available=True,
            version="1.14.0-alpha.47",
            diagnostics="sing-box version 1.14.0-alpha.47",
        )


class RecordingSnellV6MaterialSource:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self) -> SnellV6Material:
        self.calls += 1
        return SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8")


class NoopDraftProfilePreparer:
    def prepare_draft(self, profile: ManagedProfile) -> ManagedProfile:
        return profile


class MutatingDraftProfilePreparer:
    def prepare_draft(self, profile: ManagedProfile) -> ManagedProfile:
        return replace(
            profile,
            profile_id="rewritten-profile",
            profile_name="rewritten-name",
            protocol=ProtocolKind.SHADOWSOCKS,
            status=ProfileStatus.APPLIED,
            protocol_material=SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"),
        )


def test_operator_can_save_and_retrieve_a_profile_draft() -> None:
    mutation_lock = TrackingMutationLock()
    manager = Manager(state_store=MemoryStateStore(), mutation_lock=mutation_lock)
    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=4433,
        )
    )

    manager.save_profile_draft(plan)

    assert mutation_lock.acquisitions == 1
    assert manager.get_installation() == ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )


def test_manager_rejects_a_plan_based_on_a_stale_revision() -> None:
    state_store = MemoryStateStore()
    first_manager = Manager(state_store=state_store)
    second_manager = Manager(state_store=state_store)
    stale_plan = first_manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=4433,
        )
    )
    winning_plan = second_manager.plan_profile(
        PlanProfileRequest(
            profile_name="平板",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=8443,
        )
    )
    second_manager.save_profile_draft(winning_plan)

    with pytest.raises(StateRevisionConflictError) as caught:
        first_manager.save_profile_draft(stale_plan)

    assert (caught.value.expected, caught.value.actual) == (0, 1)


def test_snell_draft_persistence_generates_material_once_without_core_observation() -> None:
    state_store = MemoryStateStore()
    material_source = RecordingSnellV6MaterialSource()
    manager = Manager(
        state_store=state_store,
        draft_profile_preparer=ProtocolCatalog((SnellV6Handler(material_source=material_source),)),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=PreviewCoreInspector()),
    )
    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="Snell preview",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
        )
    )

    assert material_source.calls == 0
    assert state_store.load() == ManagedInstallation.empty()

    manager.save_profile_draft(plan)

    assert plan.observed_core_version == "1.14.0-alpha.47"
    assert material_source.calls == 1
    assert state_store.load().profiles == (
        ManagedProfile(
            profile_id="profile-1",
            profile_name="Snell preview",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            protocol_material=SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"),
        ),
    )


def test_snell_draft_save_without_preparer_fails_before_desired_state_changes() -> None:
    state_store = MemoryStateStore()
    manager = Manager(
        state_store=state_store,
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=PreviewCoreInspector()),
    )
    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="Snell preview",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
        )
    )

    with pytest.raises(DraftPreparationUnavailableError, match="Snell v6"):
        manager.save_profile_draft(plan)

    assert state_store.load() == ManagedInstallation.empty()


def test_snell_draft_save_rejects_noop_preparer_before_desired_state_changes() -> None:
    state_store = MemoryStateStore()
    manager = Manager(
        state_store=state_store,
        draft_profile_preparer=NoopDraftProfilePreparer(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=PreviewCoreInspector()),
    )
    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="Snell preview",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
        )
    )

    with pytest.raises(DraftPreparationUnavailableError, match="Snell v6"):
        manager.save_profile_draft(plan)

    assert state_store.load() == ManagedInstallation.empty()


def test_snell_draft_save_rejects_preparer_that_rewrites_planned_semantics() -> None:
    state_store = MemoryStateStore()
    manager = Manager(
        state_store=state_store,
        draft_profile_preparer=MutatingDraftProfilePreparer(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=PreviewCoreInspector()),
    )
    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="Snell preview",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
        )
    )

    with pytest.raises(DraftPreparationUnavailableError, match="Snell v6"):
        manager.save_profile_draft(plan)

    assert state_store.load() == ManagedInstallation.empty()
