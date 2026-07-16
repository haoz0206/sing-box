"""System seam for generating VMess authentication material."""

from typing import Protocol

from sb_manager.domain.protocol_material import VmessMaterial


class VmessMaterialSource(Protocol):
    def generate(self) -> VmessMaterial: ...
