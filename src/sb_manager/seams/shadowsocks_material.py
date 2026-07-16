"""Public seam for generating Shadowsocks 2022 key material."""

from typing import Protocol

from sb_manager.domain.protocol_material import ShadowsocksMaterial


class ShadowsocksMaterialSource(Protocol):
    """Generate one correctly encoded Shadowsocks 2022 key."""

    def generate(self) -> ShadowsocksMaterial: ...
