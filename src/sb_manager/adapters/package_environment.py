"""Subprocess adapter for isolated manager package environments."""

import subprocess
from pathlib import Path

from sb_manager.seams.package_environment import PackageEnvironmentBuildRequest

VENV_TIMEOUT_SECONDS = 120
PIP_TIMEOUT_SECONDS = 600


class PackageEnvironmentBuildError(RuntimeError):
    """The selected Python runtime could not build a complete release environment."""


class SubprocessPackageEnvironmentBuilder:
    """Create a venv and install one private wheel with an explicit dependency source."""

    def __init__(self, *, python_binary: str | Path) -> None:
        self._python_binary = str(python_binary)

    def build(self, request: PackageEnvironmentBuildRequest) -> None:
        if request.allow_index and request.wheelhouse is not None:
            raise PackageEnvironmentBuildError(
                "Index dependency mode cannot also select a wheelhouse"
            )
        if not request.allow_index and request.wheelhouse is None:
            raise PackageEnvironmentBuildError("Offline dependency mode requires a wheelhouse")
        environment_directory = request.release_directory / "venv"
        if environment_directory.exists() or environment_directory.is_symlink():
            raise PackageEnvironmentBuildError(
                f"Release environment already exists: {environment_directory}"
            )
        self._run(
            [self._python_binary, "-m", "venv", str(environment_directory)],
            timeout=VENV_TIMEOUT_SECONDS,
            role="create package environment",
        )
        install_command = [
            str(environment_directory / "bin/python"),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
        ]
        if request.wheelhouse is not None:
            install_command.extend(("--no-index", "--find-links", str(request.wheelhouse)))
        install_command.append(str(request.wheel_path))
        self._run(
            install_command,
            timeout=PIP_TIMEOUT_SECONDS,
            role="install manager package",
        )

    @staticmethod
    def _run(command: list[str], *, timeout: int, role: str) -> None:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PackageEnvironmentBuildError(f"Unable to {role}: {error}") from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise PackageEnvironmentBuildError(
                diagnostics or f"Unable to {role}: exit status {completed.returncode}"
            )
