"""Read-only seam for bounded init-system service log capture."""

from dataclasses import dataclass
from typing import Protocol

MAX_RUNTIME_LOG_LIMIT = 500


@dataclass(frozen=True, slots=True)
class RuntimeLogCapture:
    """Raw adapter evidence before application-level sanitization and redaction."""

    available: bool
    source_label: str
    lines: tuple[str, ...]
    diagnostics: str = ""


class RuntimeLogSource(Protocol):
    """Capture a bounded recent view without mutating the service or host."""

    def read_recent(self, *, limit: int) -> RuntimeLogCapture: ...
