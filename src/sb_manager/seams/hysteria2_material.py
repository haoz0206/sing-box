"""Public seam for generating Hysteria2 authentication material."""

from typing import Protocol

from sb_manager.domain.protocol_material import Hysteria2Material


class Hysteria2MaterialSource(Protocol):
    """Generate one Hysteria2 authentication password."""

    def generate(self) -> Hysteria2Material: ...
