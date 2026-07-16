"""systemd implementation of the runtime seam."""

import subprocess
from pathlib import Path

from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult


class SystemdRuntime:
    """Refresh and observe sing-box through systemd."""

    def __init__(
        self,
        *,
        binary: str | Path = "systemctl",
        service_name: str = "sing-box.service",
    ) -> None:
        self._binary = str(binary)
        self._service_name = service_name

    def refresh(self) -> RuntimeRefreshResult:
        success, diagnostics = self._run("reload-or-restart", self._service_name)
        return RuntimeRefreshResult(success=success, diagnostics=diagnostics)

    def check_health(self) -> RuntimePostcondition:
        healthy, diagnostics = self._run("is-active", self._service_name)
        return RuntimePostcondition(healthy=healthy, diagnostics=diagnostics)

    def recovery_instructions(self) -> tuple[str, ...]:
        return (
            f"运行 systemctl restart {self._service_name}。",
            f"运行 systemctl status {self._service_name} --no-pager。",
        )

    def _run(self, *arguments: str) -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                [self._binary, *arguments],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            return False, str(error)
        return completed.returncode == 0, (completed.stderr or completed.stdout).strip()
