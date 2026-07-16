"""System seam for generating AnyTLS authentication material."""

from typing import Protocol

from sb_manager.domain.protocol_material import AnyTlsMaterial


class AnyTlsMaterialSource(Protocol):
    """Generate a secure AnyTLS password."""

    def generate(self) -> AnyTlsMaterial: ...
