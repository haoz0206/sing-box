"""Secure Trojan authentication material generation."""

from sb_manager.domain.protocol_material import TrojanMaterial
from sb_manager.seams.random_source import RandomSource

TROJAN_PASSWORD_BYTES = 16


class SecureTrojanMaterialSource:
    """Generate a 128-bit Trojan password as hexadecimal text."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> TrojanMaterial:
        return TrojanMaterial(password=self._random_source.token_hex(TROJAN_PASSWORD_BYTES))
