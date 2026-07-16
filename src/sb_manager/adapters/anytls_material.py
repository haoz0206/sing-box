"""Secure AnyTLS authentication material generation."""

from sb_manager.domain.protocol_material import AnyTlsMaterial
from sb_manager.seams.random_source import RandomSource

ANYTLS_PASSWORD_BYTES = 16


class SecureAnyTlsMaterialSource:
    """Generate a 128-bit AnyTLS password as hexadecimal text."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> AnyTlsMaterial:
        return AnyTlsMaterial(password=self._random_source.token_hex(ANYTLS_PASSWORD_BYTES))
