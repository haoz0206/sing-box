from collections.abc import Mapping
from datetime import datetime, timezone

import pytest

from sb_manager.adapters.memory_apply_history import MemoryApplyHistoryStore
from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.apply_history import (
    MAX_APPLY_HISTORY_DIAGNOSTICS,
    ApplyHistoryCondition,
    ApplyHistoryConfigurationApplier,
    ApplyHistoryService,
    ApplyHistoryStatus,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import TuicMaterial
from sb_manager.seams.apply_history import ApplyHistoryEntry, ApplyHistoryStoreError
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    ConfigTargetPrecondition,
)


class RecordingConfigurationApplier:
    def __init__(self, result: ApplyTransactionResult) -> None:
        self.result = result
        self.calls: list[tuple[Mapping[str, object], ConfigTargetPrecondition]] = []

    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        self.calls.append((document, precondition))
        return self.result


class FailingBeginHistoryStore(MemoryApplyHistoryStore):
    def begin(self, entry: ApplyHistoryEntry) -> None:
        raise ApplyHistoryStoreError("history directory is read-only")


class FailingCompleteHistoryStore(MemoryApplyHistoryStore):
    def complete(self, entry: ApplyHistoryEntry) -> None:
        raise ApplyHistoryStoreError("history replace failed")


def applied_result() -> ApplyTransactionResult:
    return ApplyTransactionResult(
        outcome=ApplyOutcome.APPLIED,
        validation=ConfigValidationResult(valid=True, diagnostics="configuration valid"),
        commit=CommitResult(success=True, diagnostics="configuration committed"),
        runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="service refreshed"),
        postcondition=RuntimePostcondition(healthy=True, diagnostics="service active"),
        rollback=None,
    )


def validation_failed_result(diagnostics: str) -> ApplyTransactionResult:
    return ApplyTransactionResult(
        outcome=ApplyOutcome.VALIDATION_FAILED,
        validation=ConfigValidationResult(valid=False, diagnostics=diagnostics),
        commit=None,
        runtime_refresh=None,
        postcondition=None,
        rollback=None,
    )


def test_successful_configuration_apply_is_visible_in_durable_history() -> None:
    now = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)
    store = MemoryApplyHistoryStore()
    delegate = RecordingConfigurationApplier(applied_result())
    applier = ApplyHistoryConfigurationApplier(
        delegate=delegate,
        history_store=store,
        state_store=MemoryStateStore(),
        clock=lambda: now,
        attempt_id_factory=lambda: "attempt-001",
    )
    document = {"inbounds": [], "outbounds": []}
    precondition = ConfigTargetPrecondition.absent()

    result = applier.apply(document, precondition=precondition)
    report = ApplyHistoryService(history_store=store).read_recent()

    assert result is delegate.result
    assert delegate.calls == [(document, precondition)]
    assert report.condition is ApplyHistoryCondition.HEALTHY
    assert report.summary == "最近一次配置应用成功"
    assert len(report.entries) == 1
    entry = report.entries[0]
    assert entry.attempt_id == "attempt-001"
    assert entry.status is ApplyHistoryStatus.APPLIED
    assert entry.started_at == now
    assert entry.completed_at == now
    assert entry.active_profile_count == 0
    assert entry.candidate_sha256 == (
        "9a70d68278f92a6354ec949cbf064b3199d947cc779f26d05d7681b633c96d9f"
    )


def test_history_start_failure_blocks_apply_before_host_mutation() -> None:
    delegate = RecordingConfigurationApplier(applied_result())
    applier = ApplyHistoryConfigurationApplier(
        delegate=delegate,
        history_store=FailingBeginHistoryStore(),
        state_store=MemoryStateStore(),
        clock=lambda: datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc),
        attempt_id_factory=lambda: "attempt-001",
    )

    with pytest.raises(
        ConfigurationApplyError,
        match="未执行配置应用",
    ):
        applier.apply(
            {"inbounds": [], "outbounds": []},
            precondition=ConfigTargetPrecondition.absent(),
        )

    assert delegate.calls == []


def test_history_completion_failure_preserves_unknown_start_without_reclassifying_apply() -> None:
    now = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)
    store = FailingCompleteHistoryStore()
    delegate = RecordingConfigurationApplier(applied_result())
    applier = ApplyHistoryConfigurationApplier(
        delegate=delegate,
        history_store=store,
        state_store=MemoryStateStore(),
        clock=lambda: now,
        attempt_id_factory=lambda: "attempt-001",
    )

    result = applier.apply(
        {"inbounds": [], "outbounds": []},
        precondition=ConfigTargetPrecondition.absent(),
    )
    report = ApplyHistoryService(history_store=store).read_recent()

    assert result.outcome is ApplyOutcome.APPLIED
    assert report.condition is ApplyHistoryCondition.ACTION_REQUIRED
    assert report.entries[0].status is ApplyHistoryStatus.IN_PROGRESS
    assert report.summary == "最近一次配置应用结果需要人工确认"


def test_failed_apply_history_redacts_persisted_material_and_remains_actionable() -> None:
    secret = "tuic-password-from-state"
    installation = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="TUIC",
                protocol=ProtocolKind.TUIC,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=TuicMaterial(
                    user_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    password=secret,
                ),
            ),
        ),
    )
    now = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)
    store = MemoryApplyHistoryStore()
    applier = ApplyHistoryConfigurationApplier(
        delegate=RecordingConfigurationApplier(
            validation_failed_result(f"inbound rejected material {secret}")
        ),
        history_store=store,
        state_store=MemoryStateStore(installation),
        clock=lambda: now,
        attempt_id_factory=lambda: "attempt-002",
    )

    applier.apply(
        {"inbounds": [{"type": "tuic"}], "outbounds": []},
        precondition=ConfigTargetPrecondition.matching_sha256("a" * 64),
    )
    report = ApplyHistoryService(history_store=store).read_recent()

    assert report.condition is ApplyHistoryCondition.ATTENTION
    assert report.summary == "最近一次配置应用未完成"
    assert report.entries[0].status is ApplyHistoryStatus.VALIDATION_FAILED
    assert report.entries[0].active_profile_count == 1
    assert report.entries[0].redacted_occurrences == 1
    assert secret not in report.entries[0].diagnostics
    assert "[已脱敏]" in report.entries[0].diagnostics


def test_apply_history_diagnostics_are_bounded_before_persistence() -> None:
    now = datetime(2026, 7, 17, 8, 30, tzinfo=timezone.utc)
    store = MemoryApplyHistoryStore()
    applier = ApplyHistoryConfigurationApplier(
        delegate=RecordingConfigurationApplier(
            validation_failed_result("x" * (MAX_APPLY_HISTORY_DIAGNOSTICS + 100))
        ),
        history_store=store,
        state_store=MemoryStateStore(),
        clock=lambda: now,
        attempt_id_factory=lambda: "attempt-003",
    )

    applier.apply(
        {"inbounds": [], "outbounds": []},
        precondition=ConfigTargetPrecondition.absent(),
    )

    entry = store.recent(limit=1)[0]
    assert len(entry.diagnostics) == MAX_APPLY_HISTORY_DIAGNOSTICS
    assert entry.diagnostics.endswith("…[已截断]")
