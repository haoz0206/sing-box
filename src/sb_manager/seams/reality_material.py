"""Public seam for generating VLESS Reality credentials."""

from typing import Protocol

from sb_manager.domain.protocol_material import RealityMaterial


class RealityMaterialGenerationError(RuntimeError):
    """The external key generator could not produce usable material."""

    def __init__(self, diagnostics: str) -> None:
        super().__init__("Unable to generate Reality material")
        self.diagnostics = diagnostics


class RealityMaterialSource(Protocol):
    """Generate complete material for one Reality profile."""

    def generate(self) -> RealityMaterial: ...
