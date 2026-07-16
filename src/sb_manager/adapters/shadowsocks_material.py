"""Secure Shadowsocks 2022 material generation."""

import base64

from sb_manager.domain.protocol_material import ShadowsocksMaterial
from sb_manager.seams.random_source import RandomSource

SHADOWSOCKS_2022_KEY_BYTES = 16


class SecureShadowsocksMaterialSource:
    """Generate a 16-byte AEAD 2022 key encoded as standard base64."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> ShadowsocksMaterial:
        password = base64.b64encode(
            self._random_source.token_bytes(SHADOWSOCKS_2022_KEY_BYTES)
        ).decode()
        return ShadowsocksMaterial(password=password)
