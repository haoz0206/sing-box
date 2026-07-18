from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import (
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


def test_snell_draft_persistence_does_not_persist_core_observation() -> None:
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

    manager.save_profile_draft(plan)

    assert plan.observed_core_version == "1.14.0-alpha.47"
    assert state_store.load().profiles == (
        ManagedProfile(
            profile_id="profile-1",
            profile_name="Snell preview",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
        ),
    )
