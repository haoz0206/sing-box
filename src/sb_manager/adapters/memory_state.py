from sb_manager.domain.installation import ManagedInstallation


class MemoryStateStore:
    """In-memory desired-state adapter for tests and pre-apply TUI work."""

    def __init__(self, initial: ManagedInstallation | None = None) -> None:
        self._installation = initial or ManagedInstallation.empty()

    def load(self) -> ManagedInstallation:
        return self._installation

    def save(self, installation: ManagedInstallation) -> None:
        self._installation = installation
