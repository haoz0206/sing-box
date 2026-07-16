"""Root package release command with a safe read-only default."""

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from sb_manager.adapters.package_environment import SubprocessPackageEnvironmentBuilder
from sb_manager.installation.package_release import (
    DependencySource,
    PackageInstallError,
    PackageInstallPlan,
    PackageInstallRequest,
    PackageInstallResult,
    VersionedPackageInstaller,
)

HOST_ROOT = Path("/opt/sing-box-manager")
PYTHON_BINARY = Path("/usr/bin/python3")
EX_CONFIG = 78
EX_NOPERM = 77


def main(argv: Sequence[str] | None = None) -> None:
    """Preview one exact versioned package release without host mutation."""
    parser = argparse.ArgumentParser(
        prog="sb-manager-install",
        description="安装版本化、可原子激活的 sing-box manager Python 包",
    )
    parser.add_argument("--wheel", required=True, type=Path, help="本地 manager wheel")
    dependency_source = parser.add_mutually_exclusive_group(required=True)
    dependency_source.add_argument("--wheelhouse", type=Path)
    dependency_source.add_argument(
        "--allow-index",
        action="store_true",
        help="显式允许 pip 从当前配置的 package index 解析依赖",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="确认执行预览中的版本化安装和原子激活",
    )
    arguments = parser.parse_args(argv)
    request = PackageInstallRequest(
        wheel_path=arguments.wheel,
        dependency_source=(
            DependencySource.WHEELHOUSE
            if arguments.wheelhouse is not None
            else DependencySource.INDEX
        ),
        wheelhouse=arguments.wheelhouse,
    )
    installer = VersionedPackageInstaller(
        root=HOST_ROOT,
        environment_builder=SubprocessPackageEnvironmentBuilder(python_binary=PYTHON_BINARY),
    )
    try:
        plan = installer.plan(request)
    except (PackageInstallError, OSError, ValueError) as error:
        _write_error(error="plan-rejected", message=str(error))
        raise SystemExit(EX_CONFIG) from error
    if not arguments.confirm:
        _write_plan(plan)
        return
    if os.geteuid() != 0:
        _write_error(
            error="privilege-required",
            message="Confirmed package installation must run as root",
        )
        raise SystemExit(EX_NOPERM)
    try:
        result = installer.install(plan, confirmed=True)
    except (PackageInstallError, OSError, ValueError) as error:
        _write_error(error="install-rejected", message=str(error))
        raise SystemExit(EX_CONFIG) from error
    _write_result(result)


def _write_plan(plan: PackageInstallPlan) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "status": "planned",
                "package_version": plan.package_version,
                "wheel_path": str(plan.wheel_path),
                "wheel_sha256": plan.wheel_sha256,
                "release_directory": str(plan.release_directory),
                "current_link": str(plan.current_link),
                "launcher_directory": str(plan.launcher_directory),
                "dependency_source": plan.dependency_source.value,
                "wheelhouse": str(plan.wheelhouse) if plan.wheelhouse is not None else None,
                "mutates_host": plan.mutates_host,
            },
            sort_keys=True,
        )
        + "\n"
    )


def _write_result(result: PackageInstallResult) -> None:
    sys.stdout.write(
        json.dumps(
            {
                "status": "installed",
                "package_version": result.package_version,
                "release_directory": str(result.release_directory),
                "launcher_directory": str(result.launcher_directory),
                "active_target": result.active_target,
                "previous_target": result.previous_target,
            },
            sort_keys=True,
        )
        + "\n"
    )


def _write_error(*, error: str, message: str) -> None:
    sys.stderr.write(
        json.dumps(
            {
                "status": "error",
                "error": error,
                "message": message,
            },
            sort_keys=True,
        )
        + "\n"
    )
