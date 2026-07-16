"""Public seam for managing and observing the sing-box runtime."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class RuntimeKind(str, Enum):
    """Init systems supported by the production runtime composition seam."""

    SYSTEMD = "systemd"
    OPENRC = "openrc"


@dataclass(frozen=True, slots=True)
class RuntimeRefreshResult:
    """Outcome of asking the init system to load committed configuration."""

    success: bool
    diagnostics: str


@dataclass(frozen=True, slots=True)
class RuntimePostcondition:
    """Observed runtime condition after a refresh attempt."""

    healthy: bool
    diagnostics: str


class Runtime(Protocol):
    """Init-system-neutral runtime operations used by apply transactions."""

    def refresh(self) -> RuntimeRefreshResult: ...

    def check_health(self) -> RuntimePostcondition: ...

    def recovery_instructions(self) -> tuple[str, ...]: ...
