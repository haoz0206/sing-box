"""Public seam for generating Snell v6 pre-shared key material."""

from typing import Protocol

from sb_manager.domain.protocol_material import SnellV6Material


class SnellV6MaterialSource(Protocol):
    """Generate one correctly encoded Snell v6 pre-shared key."""

    def generate(self) -> SnellV6Material: ...
