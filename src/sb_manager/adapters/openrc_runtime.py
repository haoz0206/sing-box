"""OpenRC implementation of the runtime seam."""

import subprocess
from pathlib import Path

from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult


class OpenRCRuntime:
    """Restart and observe sing-box through OpenRC."""

    def __init__(
        self,
        *,
        binary: str | Path = "rc-service",
        service_name: str = "sing-box",
    ) -> None:
        self._binary = str(binary)
        self._service_name = service_name

    def refresh(self) -> RuntimeRefreshResult:
        success, diagnostics = self._run(self._service_name, "restart")
        return RuntimeRefreshResult(success=success, diagnostics=diagnostics)

    def check_health(self) -> RuntimePostcondition:
        healthy, diagnostics = self._run(self._service_name, "status")
        return RuntimePostcondition(healthy=healthy, diagnostics=diagnostics)

    def recovery_instructions(self) -> tuple[str, ...]:
        return (
            f"运行 rc-service {self._service_name} restart。",
            f"运行 rc-service {self._service_name} status。",
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
