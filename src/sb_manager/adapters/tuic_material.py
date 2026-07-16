"""Secure TUIC authentication material generation."""

from sb_manager.domain.protocol_material import TuicMaterial
from sb_manager.seams.random_source import RandomSource

TUIC_PASSWORD_BYTES = 16


class SecureTuicMaterialSource:
    """Generate a UUID and 128-bit hexadecimal password for TUIC."""

    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> TuicMaterial:
        return TuicMaterial(
            user_uuid=self._random_source.uuid(),
            password=self._random_source.token_hex(TUIC_PASSWORD_BYTES),
        )
