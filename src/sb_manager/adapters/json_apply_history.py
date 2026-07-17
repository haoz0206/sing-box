"""Atomic bounded JSON storage for secret-free configuration-apply history."""

import json
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.seams.apply_history import (
    ApplyHistoryEntry,
    ApplyHistoryStatus,
    ApplyHistoryStoreError,
)

SCHEMA_VERSION = 1
DEFAULT_MAX_ENTRIES = 100
MAX_HISTORY_BYTES = 1024 * 1024
_ROOT_FIELDS = {"schema_version", "entries"}
_ENTRY_FIELDS = {
    "attempt_id",
    "started_at",
    "completed_at",
    "status",
    "candidate_sha256",
    "active_profile_count",
    "diagnostics",
    "redacted_occurrences",
}


class JsonApplyHistoryStore:
    """Preserve an atomic newest-bounded ledger without candidate documents."""

    def __init__(self, *, path: Path, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("Apply history retention must be positive")
        self._path = path
        self._max_entries = max_entries

    def begin(self, entry: ApplyHistoryEntry) -> None:
        if entry.status is not ApplyHistoryStatus.IN_PROGRESS:
            raise ApplyHistoryStoreError("A new apply history entry must be in progress")
        entries = list(self._load())
        if any(existing.attempt_id == entry.attempt_id for existing in entries):
            raise ApplyHistoryStoreError("Apply history attempt ID already exists")
        entries.append(entry)
        self._save(tuple(entries[-self._max_entries :]))

    def complete(self, entry: ApplyHistoryEntry) -> None:
        if entry.status is ApplyHistoryStatus.IN_PROGRESS:
            raise ApplyHistoryStoreError("Completed apply history cannot remain in progress")
        entries = list(self._load())
        matches = [
            index for index, current in enumerate(entries) if current.attempt_id == entry.attempt_id
        ]
        if len(matches) != 1:
            raise ApplyHistoryStoreError("Apply history attempt does not exist exactly once")
        current = entries[matches[0]]
        if current.status is not ApplyHistoryStatus.IN_PROGRESS:
            raise ApplyHistoryStoreError("Apply history attempt is already complete")
        if (
            entry.started_at != current.started_at
            or entry.candidate_sha256 != current.candidate_sha256
            or entry.active_profile_count != current.active_profile_count
        ):
            raise ApplyHistoryStoreError("Completed apply history changed immutable evidence")
        entries[matches[0]] = entry
        self._save(tuple(entries))

    def recent(self, *, limit: int) -> tuple[ApplyHistoryEntry, ...]:
        if limit < 1:
            raise ValueError("Apply history limit must be positive")
        entries = self._load()
        return tuple(reversed(entries[-limit:]))

    def _load(self) -> tuple[ApplyHistoryEntry, ...]:
        if self._path.is_symlink():
            raise ApplyHistoryStoreError("Apply history path must not be a symbolic link")
        try:
            content = self._path.read_bytes()
        except FileNotFoundError:
            return ()
        except OSError as error:
            raise ApplyHistoryStoreError(f"Unable to read apply history: {error}") from error
        if len(content) > MAX_HISTORY_BYTES:
            raise ApplyHistoryStoreError(
                f"Apply history exceeds the {MAX_HISTORY_BYTES}-byte limit"
            )
        try:
            document = json.loads(content, object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ApplyHistoryStoreError(f"Apply history is not valid JSON: {error}") from error
        root = _object(document, fields=_ROOT_FIELDS, role="root")
        schema_version = root["schema_version"]
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or schema_version != SCHEMA_VERSION
        ):
            raise ApplyHistoryStoreError(
                f"Unsupported apply history schema version: {schema_version!r}"
            )
        raw_entries = root["entries"]
        if not isinstance(raw_entries, list):
            raise ApplyHistoryStoreError("Apply history entries must be a list")
        if len(raw_entries) > self._max_entries:
            raise ApplyHistoryStoreError("Apply history exceeds configured retention")
        entries = tuple(_entry(value) for value in raw_entries)
        if len({entry.attempt_id for entry in entries}) != len(entries):
            raise ApplyHistoryStoreError("Apply history contains duplicate attempt IDs")
        return entries

    def _save(self, entries: tuple[ApplyHistoryEntry, ...]) -> None:
        document = {
            "schema_version": SCHEMA_VERSION,
            "entries": [_serialize_entry(entry) for entry in entries],
        }
        content = (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        if len(content) > MAX_HISTORY_BYTES:
            raise ApplyHistoryStoreError(
                f"Apply history exceeds the {MAX_HISTORY_BYTES}-byte limit"
            )
        temporary_path: Path | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.is_symlink():
                raise ApplyHistoryStoreError("Apply history path must not be a symbolic link")
            with NamedTemporaryFile(
                mode="wb",
                dir=self._path.parent,
                prefix=f".{self._path.name}.",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            temporary_path.chmod(0o600)
            temporary_path.replace(self._path)
            temporary_path = None
            _sync_directory(self._path.parent)
        except ApplyHistoryStoreError:
            raise
        except OSError as error:
            raise ApplyHistoryStoreError(f"Unable to write apply history: {error}") from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


def _entry(value: object) -> ApplyHistoryEntry:
    item = _object(value, fields=_ENTRY_FIELDS, role="entry")
    status_value = _string(item["status"], role="entry.status")
    try:
        status = ApplyHistoryStatus(status_value)
        completed_at = _optional_datetime(item["completed_at"], role="entry.completed_at")
        active_profile_count = _integer(
            item["active_profile_count"], role="entry.active_profile_count"
        )
        redacted_occurrences = _integer(
            item["redacted_occurrences"], role="entry.redacted_occurrences"
        )
        return ApplyHistoryEntry(
            attempt_id=_string(item["attempt_id"], role="entry.attempt_id"),
            started_at=_datetime(item["started_at"], role="entry.started_at"),
            completed_at=completed_at,
            status=status,
            candidate_sha256=_string(item["candidate_sha256"], role="entry.candidate_sha256"),
            active_profile_count=active_profile_count,
            diagnostics=_string(item["diagnostics"], role="entry.diagnostics"),
            redacted_occurrences=redacted_occurrences,
        )
    except ValueError as error:
        raise ApplyHistoryStoreError(str(error)) from error


def _serialize_entry(entry: ApplyHistoryEntry) -> dict[str, object]:
    return {
        "attempt_id": entry.attempt_id,
        "started_at": entry.started_at.isoformat(),
        "completed_at": (
            entry.completed_at.isoformat() if entry.completed_at is not None else None
        ),
        "status": entry.status.value,
        "candidate_sha256": entry.candidate_sha256,
        "active_profile_count": entry.active_profile_count,
        "diagnostics": entry.diagnostics,
        "redacted_occurrences": entry.redacted_occurrences,
    }


def _unique_object(pairs: Iterable[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ApplyHistoryStoreError(f"Apply history contains duplicate field: {key}")
        result[key] = value
    return result


def _object(value: object, *, fields: set[str], role: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ApplyHistoryStoreError(f"Apply history {role} must be an object")
    if set(value) != fields:
        raise ApplyHistoryStoreError(
            f"Apply history {role} fields must be exactly {sorted(fields)}"
        )
    return value


def _string(value: object, *, role: str) -> str:
    if not isinstance(value, str):
        raise ApplyHistoryStoreError(f"Apply history {role} must be a string")
    return value


def _integer(value: object, *, role: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ApplyHistoryStoreError(f"Apply history {role} must be an integer")
    return value


def _datetime(value: object, *, role: str) -> datetime:
    if not isinstance(value, str):
        raise ApplyHistoryStoreError(f"Apply history {role} must be a datetime string")
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        raise ApplyHistoryStoreError(
            f"Apply history {role} must be an ISO 8601 datetime"
        ) from error


def _optional_datetime(value: object, *, role: str) -> datetime | None:
    return None if value is None else _datetime(value, role=role)


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
