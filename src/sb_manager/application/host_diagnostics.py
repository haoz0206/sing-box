"""Typed, read-only host diagnostics for operator-facing workflows."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.seams.runtime import Runtime


class HostCondition(str, Enum):
    """High-level runtime condition that the TUI can present without parsing text."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True, slots=True)
class HostDiagnosticsReport:
    """One actionable, read-only observation of the managed runtime."""

    condition: HostCondition
    summary: str
    diagnostics: str
    recovery_instructions: tuple[str, ...]


class HostDiagnostics(Protocol):
    """Application seam consumed by the dashboard background worker."""

    def inspect(self) -> HostDiagnosticsReport: ...


class RuntimeHostDiagnostics:
    """Translate init-system observations into stable operator language."""

    def __init__(self, *, runtime: Runtime) -> None:
        self._runtime = runtime

    def inspect(self) -> HostDiagnosticsReport:
        postcondition = self._runtime.check_health()
        if postcondition.healthy:
            return HostDiagnosticsReport(
                condition=HostCondition.HEALTHY,
                summary="sing-box 服务运行正常",
                diagnostics=postcondition.diagnostics,
                recovery_instructions=(),
            )
        return HostDiagnosticsReport(
            condition=HostCondition.UNHEALTHY,
            summary="sing-box 服务未通过健康检查",
            diagnostics=postcondition.diagnostics,
            recovery_instructions=self._runtime.recovery_instructions(),
        )
