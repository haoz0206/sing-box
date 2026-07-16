"""Secure VMess authentication material generation."""

from sb_manager.domain.protocol_material import VmessMaterial
from sb_manager.seams.random_source import RandomSource


class SecureVmessMaterialSource:
    def __init__(self, *, random_source: RandomSource) -> None:
        self._random_source = random_source

    def generate(self) -> VmessMaterial:
        return VmessMaterial(user_uuid=self._random_source.uuid())
