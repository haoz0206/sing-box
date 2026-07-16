"""Read-only seam for Linux listener and process-ownership evidence."""

from collections.abc import Collection
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ListenerTransport(str, Enum):
    """Network transports represented by generated sing-box inbounds."""

    TCP = "tcp"
    UDP = "udp"


@dataclass(frozen=True, slots=True)
class ListenerEndpoint:
    """One transport-specific local port expected by desired state."""

    port: int
    transport: ListenerTransport


@dataclass(frozen=True, slots=True)
class ListenerOwner:
    """Visible process evidence for one listening socket."""

    pid: int
    process_name: str | None


@dataclass(frozen=True, slots=True)
class ListenerObservation:
    """Observed listener plus the bounded ownership evidence available for it."""

    endpoint: ListenerEndpoint
    owners: tuple[ListenerOwner, ...]
    ownership_complete: bool


@dataclass(frozen=True, slots=True)
class ListenerInspection:
    """Host observations for only the endpoints requested by the application."""

    observations: tuple[ListenerObservation, ...]
    diagnostics: str = ""


class ListenerInspectionError(RuntimeError):
    """Linux listener evidence could not be read safely."""


class ListenerSource(Protocol):
    """Observe listener presence and process ownership without changing the host."""

    def inspect(self, endpoints: Collection[ListenerEndpoint]) -> ListenerInspection: ...
