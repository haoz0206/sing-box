"""Public read-only seam for manager-installed core release inventory."""

from typing import Protocol

from sb_manager.artifacts.installation import InstalledCoreRelease


class CoreInventory(Protocol):
    """List exact retained identities without mutating the host."""

    def list_installed(self) -> tuple[InstalledCoreRelease, ...]: ...
