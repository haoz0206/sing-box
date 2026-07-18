"""Secure Snell v6 material generation."""

import base64

from sb_manager.domain.protocol_material import SnellV6Material
from sb_manager.seams.random_source import RandomSource

SNELL_V6_PSK_BYTES = 32


class SecureSnellV6MaterialSource:
    """Generate a 32-byte Snell v6 PSK encoded as unpadded URL-safe base64."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> SnellV6Material:
        psk = (
            base64.urlsafe_b64encode(self._random_source.token_bytes(SNELL_V6_PSK_BYTES))
            .decode()
            .rstrip("=")
        )
        return SnellV6Material(psk=psk)
