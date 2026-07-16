"""Public seam for host port observations and automatic selection."""

from collections.abc import Collection
from typing import Protocol


class PortSource(Protocol):
    """Observe fixed ports or choose one for an automatic profile."""

    def is_available(self, port: int) -> bool: ...

    def choose_available(self, *, excluded_ports: Collection[int] = ()) -> int: ...
