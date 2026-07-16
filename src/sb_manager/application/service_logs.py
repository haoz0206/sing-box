"""Bounded and redacted service logs for operator-facing troubleshooting."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    Hysteria2Material,
    RealityMaterial,
    ShadowsocksMaterial,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.seams.runtime_logs import MAX_RUNTIME_LOG_LIMIT, RuntimeLogSource
from sb_manager.seams.state_store import StateStore

DEFAULT_LOG_LIMIT = 200
MAX_LOG_LIMIT = MAX_RUNTIME_LOG_LIMIT
MAX_LOG_LINE_LENGTH = 4096
MIN_EXACT_SECRET_LENGTH = 8
MIN_PRINTABLE_CODE_POINT = 32
REDACTION_MARKER = "[已脱敏]"
TRUNCATION_MARKER = "…[已截断]"

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-_])")
_URI_USERINFO = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)([^@\s/]+)@")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)([\"']?\b(?:password|passwd|secret|token|(?:access|refresh)[_ -]?token|"
    r"auth(?:entication|orization)?|credential|api[_ -]?key|private[_ -]?key|uuid|"
    r"short[_ -]?id)\b[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|(?:(?:Bearer|Basic)\s+)?[^\s,;&}]+)"
)


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
        secrets = _persisted_secrets(installation)
        capture = self._log_source.read_recent(limit=limit)
        diagnostics, diagnostic_redactions = _redact_text(capture.diagnostics, secrets)
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
            line, replacements = _redact_text(raw_line, secrets)
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


def _redact_text(text: str, secrets: tuple[str, ...]) -> tuple[str, int]:
    sanitized = _sanitize_controls(text)
    replacements = 0

    def redact_uri(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return f"{match.group(1)}{REDACTION_MARKER}@"

    sanitized = _URI_USERINFO.sub(redact_uri, sanitized)

    def redact_assignment(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return f"{match.group(1)}{REDACTION_MARKER}"

    sanitized = _SENSITIVE_ASSIGNMENT.sub(redact_assignment, sanitized)
    for secret in secrets:
        occurrences = sanitized.count(secret)
        if occurrences:
            sanitized = sanitized.replace(secret, REDACTION_MARKER)
            replacements += occurrences
    return sanitized, replacements


def _sanitize_controls(text: str) -> str:
    without_ansi = _ANSI_ESCAPE.sub("", text)
    return "".join(
        character
        for character in without_ansi
        if character in "\n\t" or ord(character) >= MIN_PRINTABLE_CODE_POINT
    )


def _persisted_secrets(installation: ManagedInstallation) -> tuple[str, ...]:
    values: set[str] = set()
    for profile in installation.profiles:
        material = profile.protocol_material
        candidates: tuple[str, ...]
        if isinstance(material, RealityMaterial):
            candidates = (material.user_uuid, material.private_key, material.short_id)
        elif isinstance(
            material,
            (ShadowsocksMaterial, Hysteria2Material, TrojanMaterial, AnyTlsMaterial),
        ):
            candidates = (material.password,)
        elif isinstance(material, TuicMaterial):
            candidates = (material.user_uuid, material.password)
        elif isinstance(material, (VlessMaterial, VmessMaterial)):
            candidates = (material.user_uuid,)
        else:
            candidates = ()
        values.update(value for value in candidates if len(value) >= MIN_EXACT_SECRET_LENGTH)
    return tuple(sorted(values, key=len, reverse=True))
