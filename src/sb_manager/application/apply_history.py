"""Record and classify bounded, redacted configuration-apply history."""

import secrets
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from sb_manager.application.disclosure import (
    disclosure_secrets,
    redact_text,
    redact_transaction_result,
)
from sb_manager.seams.apply_history import (
    MAX_APPLY_HISTORY_DIAGNOSTICS,
    ApplyHistoryEntry,
    ApplyHistoryStatus,
    ApplyHistoryStore,
    ApplyHistoryStoreError,
)
from sb_manager.seams.configuration_applier import (
    ConfigurationApplier,
    ConfigurationApplyError,
)
from sb_manager.seams.state_store import StateStore
from sb_manager.transactions.apply import ApplyTransactionResult, ConfigTargetPrecondition
from sb_manager.transactions.staging import configuration_sha256

DEFAULT_APPLY_HISTORY_LIMIT = 20
MAX_APPLY_HISTORY_LIMIT = 100
TRUNCATION_MARKER = "…[已截断]"


class ApplyHistoryCondition(str, Enum):
    """Operator significance of recent configuration-apply evidence."""

    HEALTHY = "healthy"
    ATTENTION = "attention"
    ACTION_REQUIRED = "action-required"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ApplyHistoryReport:
    """A bounded newest-first history view with one operator conclusion."""

    condition: ApplyHistoryCondition
    summary: str
    entries: tuple[ApplyHistoryEntry, ...]
    diagnostics: str
    guidance: str
    limit: int


class ApplyHistoryReader(Protocol):
    """TUI-facing read-only interface for bounded apply history."""

    def read_recent(
        self,
        *,
        limit: int = DEFAULT_APPLY_HISTORY_LIMIT,
    ) -> ApplyHistoryReport: ...


class ApplyHistoryRecordingError(ConfigurationApplyError):
    """History could not start, so no host apply was attempted."""


class ApplyHistoryConfigurationApplier:
    """Make a durable start record before delegating one host transaction."""

    def __init__(
        self,
        *,
        delegate: ConfigurationApplier,
        history_store: ApplyHistoryStore,
        state_store: StateStore,
        clock: Callable[[], datetime] | None = None,
        attempt_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._delegate = delegate
        self._history_store = history_store
        self._state_store = state_store
        self._clock = clock or _utc_now
        self._attempt_id_factory = attempt_id_factory or _attempt_id

    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition,
    ) -> ApplyTransactionResult:
        started_at = self._clock()
        installation = self._state_store.load()
        entry = ApplyHistoryEntry(
            attempt_id=self._attempt_id_factory(),
            started_at=started_at,
            completed_at=None,
            status=ApplyHistoryStatus.IN_PROGRESS,
            candidate_sha256=configuration_sha256(document),
            active_profile_count=_active_profile_count(document),
            diagnostics="配置应用已开始，最终结果尚未写入。",
        )
        try:
            self._history_store.begin(entry)
        except (OSError, ApplyHistoryStoreError) as error:
            raise ApplyHistoryRecordingError(
                f"无法在主机变更前写入应用历史，未执行配置应用：{error}"
            ) from error
        secrets_to_redact = disclosure_secrets(installation, document)
        try:
            result = self._delegate.apply(document, precondition=precondition)
        except (OSError, ConfigurationApplyError) as error:
            diagnostics, redactions = redact_text(str(error), secrets_to_redact)
            self._finish_best_effort(
                entry,
                status=ApplyHistoryStatus.EXECUTION_ERROR,
                diagnostics=_bounded_diagnostics(diagnostics),
                redacted_occurrences=redactions,
            )
            operational_error = ConfigurationApplyError(diagnostics)
        else:
            redacted_result, redactions = redact_transaction_result(
                result,
                secrets_to_redact,
            )
            diagnostics = _transaction_diagnostics(redacted_result)
            self._finish_best_effort(
                entry,
                status=ApplyHistoryStatus(result.outcome.value),
                diagnostics=_bounded_diagnostics(diagnostics),
                redacted_occurrences=redactions,
            )
            return redacted_result
        raise operational_error from None

    def _finish_best_effort(
        self,
        started: ApplyHistoryEntry,
        *,
        status: ApplyHistoryStatus,
        diagnostics: str,
        redacted_occurrences: int,
    ) -> None:
        completed = ApplyHistoryEntry(
            attempt_id=started.attempt_id,
            started_at=started.started_at,
            completed_at=self._clock(),
            status=status,
            candidate_sha256=started.candidate_sha256,
            active_profile_count=started.active_profile_count,
            diagnostics=diagnostics,
            redacted_occurrences=redacted_occurrences,
        )
        with suppress(OSError, ApplyHistoryStoreError):
            self._history_store.complete(completed)


class ApplyHistoryService:
    """Classify recent durable attempts behind one small read-only interface."""

    def __init__(self, *, history_store: ApplyHistoryStore) -> None:
        self._history_store = history_store

    def read_recent(
        self,
        *,
        limit: int = DEFAULT_APPLY_HISTORY_LIMIT,
    ) -> ApplyHistoryReport:
        if not 1 <= limit <= MAX_APPLY_HISTORY_LIMIT:
            raise ValueError(f"Apply history limit must be between 1 and {MAX_APPLY_HISTORY_LIMIT}")
        try:
            entries = self._history_store.recent(limit=limit)
        except (OSError, ApplyHistoryStoreError) as error:
            return ApplyHistoryReport(
                condition=ApplyHistoryCondition.UNAVAILABLE,
                summary="无法读取配置应用历史",
                entries=(),
                diagnostics=str(error),
                guidance="检查历史文件权限与完整性; 历史未知时不要假定上次应用成功。",
                limit=limit,
            )
        if not entries:
            return ApplyHistoryReport(
                condition=ApplyHistoryCondition.HEALTHY,
                summary="尚无配置应用记录",
                entries=(),
                diagnostics="没有执行过 live configuration 应用",
                guidance="",
                limit=limit,
            )
        latest = entries[0]
        if latest.status is ApplyHistoryStatus.APPLIED:
            condition = ApplyHistoryCondition.HEALTHY
            summary = "最近一次配置应用成功"
            guidance = ""
        elif latest.status in {
            ApplyHistoryStatus.ROLLBACK_FAILED,
            ApplyHistoryStatus.EXECUTION_ERROR,
            ApplyHistoryStatus.IN_PROGRESS,
        }:
            condition = ApplyHistoryCondition.ACTION_REQUIRED
            summary = "最近一次配置应用结果需要人工确认"
            guidance = "检查 live configuration、服务健康和恢复证据后再执行新的变更。"
        else:
            condition = ApplyHistoryCondition.ATTENTION
            summary = "最近一次配置应用未完成"
            guidance = "查看失败阶段和诊断信息，修复后重新预览并确认应用。"
        return ApplyHistoryReport(
            condition=condition,
            summary=summary,
            entries=entries,
            diagnostics=f"保留最近 {len(entries)} 次应用证据",
            guidance=guidance,
            limit=limit,
        )


def _active_profile_count(document: Mapping[str, object]) -> int:
    inbounds = document.get("inbounds")
    return len(inbounds) if isinstance(inbounds, list) else 0


def _transaction_diagnostics(result: ApplyTransactionResult) -> str:
    details = [result.validation.diagnostics]
    details.extend(
        evidence.diagnostics
        for evidence in (
            result.commit,
            result.runtime_refresh,
            result.postcondition,
            result.rollback,
        )
        if evidence is not None and evidence.diagnostics
    )
    return "; ".join(detail for detail in details if detail)


def _bounded_diagnostics(diagnostics: str) -> str:
    if len(diagnostics) <= MAX_APPLY_HISTORY_DIAGNOSTICS:
        return diagnostics
    return (
        f"{diagnostics[: MAX_APPLY_HISTORY_DIAGNOSTICS - len(TRUNCATION_MARKER)]}"
        f"{TRUNCATION_MARKER}"
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _attempt_id() -> str:
    return secrets.token_hex(16)
