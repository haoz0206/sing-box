from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.config_adoption import (
    AdoptionConfirmationRequiredError,
    ConfigAdoptionService,
    LiveConfigChangedError,
)
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.config_target import LiveConfigObservation

EXPECTED_INSPECTION_COUNT = 2


class MutableConfigInspector:
    def __init__(self, observation: LiveConfigObservation) -> None:
        self.observation = observation
        self.inspections = 0

    def inspect(self) -> LiveConfigObservation:
        self.inspections += 1
        return self.observation


class TrackingApplyLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


def test_adoption_plan_identifies_one_existing_config_without_mutating_state() -> None:
    initial = ManagedInstallation.empty()
    state_store = MemoryStateStore(initial)
    inspector = MutableConfigInspector(LiveConfigObservation(exists=True, sha256="a" * 64))
    adoption = ConfigAdoptionService(
        state_store=state_store,
        config_inspector=inspector,
        mutation_lock=TrackingApplyLock(),
    )

    plan = adoption.plan()

    assert plan.base_revision == 0
    assert plan.config_sha256 == "a" * 64
    assert plan.mutates_host is False
    assert plan.imports_profiles is False
    assert state_store.load() == initial


def test_confirmed_adoption_rechecks_and_records_the_reviewed_fingerprint() -> None:
    state_store = MemoryStateStore()
    inspector = MutableConfigInspector(LiveConfigObservation(exists=True, sha256="b" * 64))
    lock = TrackingApplyLock()
    adoption = ConfigAdoptionService(
        state_store=state_store,
        config_inspector=inspector,
        mutation_lock=lock,
    )
    plan = adoption.plan()

    result = adoption.adopt(plan, confirmed=True)

    assert result.committed_revision == 1
    assert result.config_sha256 == "b" * 64
    assert state_store.load() == ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(),
        expected_config_sha256="b" * 64,
    )
    assert inspector.inspections == EXPECTED_INSPECTION_COUNT
    assert lock.acquisitions == 1


def test_adoption_requires_confirmation_and_rejects_change_after_review() -> None:
    state_store = MemoryStateStore()
    inspector = MutableConfigInspector(LiveConfigObservation(exists=True, sha256="c" * 64))
    adoption = ConfigAdoptionService(
        state_store=state_store,
        config_inspector=inspector,
        mutation_lock=TrackingApplyLock(),
    )
    plan = adoption.plan()

    with pytest.raises(AdoptionConfirmationRequiredError):
        adoption.adopt(plan, confirmed=False)

    inspector.observation = LiveConfigObservation(exists=True, sha256="d" * 64)
    with pytest.raises(LiveConfigChangedError):
        adoption.adopt(plan, confirmed=True)

    assert state_store.load() == ManagedInstallation.empty()
