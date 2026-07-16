from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation


class UnsupportedStateSchemaError(ValueError):
    """Stored desired state uses a schema this manager cannot interpret."""

    def __init__(self, *, supported: int, found: int) -> None:
        super().__init__(f"Unsupported state schema {found}; supported schema is {supported}")
        self.supported = supported
        self.found = found


class StateStore(Protocol):
    """Persistence seam for manager-owned desired state."""

    def load(self) -> ManagedInstallation: ...

    def save(self, installation: ManagedInstallation) -> None: ...
