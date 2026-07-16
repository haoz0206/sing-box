"""Secure Hysteria2 authentication material generation."""

from sb_manager.domain.protocol_material import Hysteria2Material
from sb_manager.seams.random_source import RandomSource

HYSTERIA2_PASSWORD_BYTES = 16


class SecureHysteria2MaterialSource:
    """Generate a 128-bit Hysteria2 password as hexadecimal text."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> Hysteria2Material:
        return Hysteria2Material(password=self._random_source.token_hex(HYSTERIA2_PASSWORD_BYTES))
