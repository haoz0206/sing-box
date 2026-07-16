"""System seam for generating VLESS authentication material."""

from typing import Protocol

from sb_manager.domain.protocol_material import VlessMaterial


class VlessMaterialSource(Protocol):
    """Generate a secure VLESS UUID."""

    def generate(self) -> VlessMaterial: ...
