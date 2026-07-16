"""System seam for generating Trojan authentication material."""

from typing import Protocol

from sb_manager.domain.protocol_material import TrojanMaterial


class TrojanMaterialSource(Protocol):
    """Generate a secure Trojan password."""

    def generate(self) -> TrojanMaterial: ...
