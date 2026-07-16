"""Validate sudoers and doas fragments with their native system parsers."""

import subprocess
from pathlib import Path

from sb_manager.installation.privileged_policy import (
    AuthorizationProvider,
    HostPolicyInstallError,
)

VALIDATION_TIMEOUT_SECONDS = 10


class AuthorizationPolicyValidationError(HostPolicyInstallError):
    """The native authorization parser rejected or could not read a policy."""


class SubprocessAuthorizationPolicyValidator:
    """Invoke fixed parser binaries without a shell or mutable environment path."""

    def __init__(
        self,
        *,
        sudo_validator: Path = Path("/usr/sbin/visudo"),
        doas_validator: Path = Path("/usr/bin/doas"),
    ) -> None:
        self._sudo_validator = sudo_validator
        self._doas_validator = doas_validator

    def validate(self, provider: AuthorizationProvider, path: Path) -> None:
        command = (
            [str(self._sudo_validator), "-cf", str(path)]
            if provider is AuthorizationProvider.SUDO
            else [str(self._doas_validator), "-C", str(path)]
        )
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=VALIDATION_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise AuthorizationPolicyValidationError(
                f"Unable to execute {provider.value} policy validator: {error}"
            ) from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise AuthorizationPolicyValidationError(
                diagnostics
                or f"{provider.value} policy validator exited with status {completed.returncode}"
            )
