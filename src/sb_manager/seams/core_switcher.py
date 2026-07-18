"""Public seam for switching between exact manager-installed core releases."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.artifacts.installation import CoreActivation, CoreReleaseIdentity


class CoreSwitchError(RuntimeError):
    """One requested retained-release switch did not produce trusted evidence."""


@dataclass(frozen=True, slots=True)
class CoreSwitchRequest:
    """Target and reviewed active identities allowed across the privileged seam."""

    target: CoreReleaseIdentity
    expected_active: CoreReleaseIdentity


class CoreSwitcher(Protocol):
    """Switch to one retained release without acquiring an archive."""

    def switch_core(self, request: CoreSwitchRequest) -> CoreActivation: ...
