"""System seam for generating TUIC authentication material."""

from typing import Protocol

from sb_manager.domain.protocol_material import TuicMaterial


class TuicMaterialSource(Protocol):
    """Generate a secure TUIC UUID and password."""

    def generate(self) -> TuicMaterial: ...
