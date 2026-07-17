"""In-memory apply-history adapter for behavior tests and ephemeral use."""

from sb_manager.seams.apply_history import (
    ApplyHistoryEntry,
    ApplyHistoryStatus,
    ApplyHistoryStoreError,
)


class MemoryApplyHistoryStore:
    """Retain ordered attempts with the same begin/complete invariants as disk."""

    def __init__(self) -> None:
        self._entries: list[ApplyHistoryEntry] = []

    def begin(self, entry: ApplyHistoryEntry) -> None:
        if entry.status is not ApplyHistoryStatus.IN_PROGRESS:
            raise ApplyHistoryStoreError("A new apply history entry must be in progress")
        if any(existing.attempt_id == entry.attempt_id for existing in self._entries):
            raise ApplyHistoryStoreError("Apply history attempt ID already exists")
        self._entries.append(entry)

    def complete(self, entry: ApplyHistoryEntry) -> None:
        if entry.status is ApplyHistoryStatus.IN_PROGRESS:
            raise ApplyHistoryStoreError("Completed apply history cannot remain in progress")
        matches = [
            index
            for index, existing in enumerate(self._entries)
            if existing.attempt_id == entry.attempt_id
        ]
        if len(matches) != 1:
            raise ApplyHistoryStoreError("Apply history attempt does not exist exactly once")
        current = self._entries[matches[0]]
        if current.status is not ApplyHistoryStatus.IN_PROGRESS:
            raise ApplyHistoryStoreError("Apply history attempt is already complete")
        if (
            entry.started_at != current.started_at
            or entry.candidate_sha256 != current.candidate_sha256
            or entry.active_profile_count != current.active_profile_count
        ):
            raise ApplyHistoryStoreError("Completed apply history changed immutable evidence")
        self._entries[matches[0]] = entry

    def recent(self, *, limit: int) -> tuple[ApplyHistoryEntry, ...]:
        if limit < 1:
            raise ValueError("Apply history limit must be positive")
        return tuple(reversed(self._entries[-limit:]))
