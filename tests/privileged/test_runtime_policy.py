from pathlib import Path

import pytest

from sb_manager.privileged.runtime_policy import HostRuntimePolicyError, create_host_runtime


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_active_systemd_marker_selects_fixed_systemd_service(tmp_path: Path) -> None:
    marker = tmp_path / "run/systemd/system"
    marker.mkdir(parents=True)
    runtime = create_host_runtime(
        systemd_marker=marker,
        systemd_binary=executable(tmp_path / "usr/bin/systemctl"),
        openrc_binary=tmp_path / "sbin/rc-service",
    )

    assert runtime.recovery_instructions() == (
        "运行 systemctl restart sing-box.service。",
        "运行 systemctl status sing-box.service --no-pager。",
    )


def test_openrc_binary_is_used_only_without_active_systemd(tmp_path: Path) -> None:
    runtime = create_host_runtime(
        systemd_marker=tmp_path / "run/systemd/system",
        systemd_binary=tmp_path / "usr/bin/systemctl",
        openrc_binary=executable(tmp_path / "sbin/rc-service"),
    )

    assert runtime.recovery_instructions() == (
        "运行 rc-service sing-box restart。",
        "运行 rc-service sing-box status。",
    )


def test_fixed_openrc_path_may_be_a_symlink_to_an_executable(tmp_path: Path) -> None:
    target = executable(tmp_path / "libexec/rc-service")
    fixed_path = tmp_path / "sbin/rc-service"
    fixed_path.parent.mkdir(parents=True)
    fixed_path.symlink_to(target)

    runtime = create_host_runtime(
        systemd_marker=tmp_path / "run/systemd/system",
        systemd_binary=tmp_path / "usr/bin/systemctl",
        openrc_binary=fixed_path,
    )

    assert runtime.recovery_instructions()[0] == "运行 rc-service sing-box restart。"


def test_host_without_supported_active_init_system_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(HostRuntimePolicyError, match="systemd or OpenRC"):
        create_host_runtime(
            systemd_marker=tmp_path / "run/systemd/system",
            systemd_binary=tmp_path / "usr/bin/systemctl",
            openrc_binary=tmp_path / "sbin/rc-service",
        )
