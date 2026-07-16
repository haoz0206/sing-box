"""Secure VLESS authentication material generation."""

from sb_manager.domain.protocol_material import VlessMaterial
from sb_manager.seams.random_source import RandomSource


class SecureVlessMaterialSource:
    """Generate a random UUID for transported VLESS."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> VlessMaterial:
        return VlessMaterial(user_uuid=self._random_source.uuid())
