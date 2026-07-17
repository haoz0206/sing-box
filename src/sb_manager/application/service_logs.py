"""Bounded and redacted service logs for operator-facing troubleshooting."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.application.disclosure import (
    persisted_secrets,
    redact_text,
)
from sb_manager.seams.runtime_logs import MAX_RUNTIME_LOG_LIMIT, RuntimeLogSource
from sb_manager.seams.state_store import StateStore

DEFAULT_LOG_LIMIT = 200
MAX_LOG_LIMIT = MAX_RUNTIME_LOG_LIMIT
MAX_LOG_LINE_LENGTH = 4096
TRUNCATION_MARKER = "…[已截断]"


class ServiceLogCondition(str, Enum):
    """Stable states the TUI can render without parsing command diagnostics."""

    AVAILABLE = "available"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ServiceLogReport:
    """One safe, bounded view of recent service evidence."""

    condition: ServiceLogCondition
    source_label: str
    lines: tuple[str, ...]
    diagnostics: str
    redacted_occurrences: int
    limit: int


class ServiceLogReader(Protocol):
    """TUI-facing read-only service-log interface."""

    def read_recent(self, *, limit: int = DEFAULT_LOG_LIMIT) -> ServiceLogReport: ...


class ServiceLogService:
    """Apply one conservative disclosure policy to every runtime log adapter."""

    def __init__(self, *, state_store: StateStore, log_source: RuntimeLogSource) -> None:
        self._state_store = state_store
        self._log_source = log_source

    def read_recent(self, *, limit: int = DEFAULT_LOG_LIMIT) -> ServiceLogReport:
        if not 1 <= limit <= MAX_LOG_LIMIT:
            raise ValueError(f"Service log limit must be between 1 and {MAX_LOG_LIMIT}")
        installation = self._state_store.load()
        secrets = persisted_secrets(installation)
        capture = self._log_source.read_recent(limit=limit)
        diagnostics, diagnostic_redactions = redact_text(capture.diagnostics, secrets)
        if not capture.available:
            return ServiceLogReport(
                condition=ServiceLogCondition.UNAVAILABLE,
                source_label=capture.source_label,
                lines=(),
                diagnostics=diagnostics,
                redacted_occurrences=diagnostic_redactions,
                limit=limit,
            )

        lines: list[str] = []
        redacted_occurrences = diagnostic_redactions
        for raw_line in capture.lines[-limit:]:
            line, replacements = redact_text(raw_line, secrets)
            redacted_occurrences += replacements
            if len(line) > MAX_LOG_LINE_LENGTH:
                line = f"{line[: MAX_LOG_LINE_LENGTH - len(TRUNCATION_MARKER)]}{TRUNCATION_MARKER}"
            lines.append(line)
        return ServiceLogReport(
            condition=(ServiceLogCondition.AVAILABLE if lines else ServiceLogCondition.EMPTY),
            source_label=capture.source_label,
            lines=tuple(lines),
            diagnostics=diagnostics,
            redacted_occurrences=redacted_occurrences,
            limit=limit,
        )
