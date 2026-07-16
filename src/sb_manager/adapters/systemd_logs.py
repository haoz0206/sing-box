"""Bounded, read-only systemd journal capture."""

import subprocess
from pathlib import Path

from sb_manager.seams.runtime_logs import MAX_RUNTIME_LOG_LIMIT, RuntimeLogCapture


class SystemdJournalLogSource:
    """Read one service unit through journalctl without following the journal."""

    def __init__(
        self,
        *,
        binary: str | Path = "journalctl",
        service_name: str = "sing-box.service",
        timeout_seconds: float = 5,
    ) -> None:
        self._binary = str(binary)
        self._service_name = service_name
        self._timeout_seconds = timeout_seconds

    def read_recent(self, *, limit: int) -> RuntimeLogCapture:
        _validate_limit(limit)
        try:
            completed = subprocess.run(
                [
                    self._binary,
                    "--unit",
                    self._service_name,
                    "--lines",
                    str(limit),
                    "--no-pager",
                    "--output",
                    "short-iso",
                    "--quiet",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return RuntimeLogCapture(
                available=False,
                source_label="systemd journal",
                lines=(),
                diagnostics=str(error),
            )
        output = (
            completed.stdout if completed.returncode == 0 else completed.stderr or completed.stdout
        )
        if completed.returncode != 0:
            return RuntimeLogCapture(
                available=False,
                source_label="systemd journal",
                lines=(),
                diagnostics=output.strip(),
            )
        lines = tuple(line for line in output.splitlines() if line.strip() != "-- No entries --")
        return RuntimeLogCapture(
            available=True,
            source_label="systemd journal",
            lines=lines[-limit:],
        )


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_RUNTIME_LOG_LIMIT:
        raise ValueError(f"Runtime log limit must be between 1 and {MAX_RUNTIME_LOG_LIMIT}")
