"""Fixed host runtime selection for the privileged configuration operation."""

import os
from pathlib import Path

from sb_manager.adapters.openrc_runtime import OpenRCRuntime
from sb_manager.adapters.systemd_runtime import SystemdRuntime
from sb_manager.seams.runtime import Runtime


class HostRuntimePolicyError(RuntimeError):
    """The host has no usable init system allowed by privileged policy."""


def create_host_runtime(
    *,
    systemd_marker: Path = Path("/run/systemd/system"),
    systemd_binary: Path = Path("/usr/bin/systemctl"),
    openrc_binary: Path = Path("/sbin/rc-service"),
) -> Runtime:
    """Select only the fixed active systemd or OpenRC adapter."""
    if systemd_marker.is_dir():
        if _is_executable(systemd_binary):
            return SystemdRuntime(binary=systemd_binary, service_name="sing-box.service")
        raise HostRuntimePolicyError(
            f"Active systemd host has no executable policy binary: {systemd_binary}"
        )
    if _is_executable(openrc_binary):
        return OpenRCRuntime(binary=openrc_binary, service_name="sing-box")
    raise HostRuntimePolicyError("Host has no supported active systemd or OpenRC runtime")


def _is_executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)
