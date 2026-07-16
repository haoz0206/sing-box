import os
import subprocess
import sys
from pathlib import Path

import pytest

from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.adapters.package_environment import SubprocessPackageEnvironmentBuilder
from sb_manager.installation.package_release import (
    DependencySource,
    PackageInstallRequest,
    VersionedPackageInstaller,
)


@pytest.mark.integration
def test_built_wheel_installs_into_an_executable_versioned_release(tmp_path: Path) -> None:
    wheel_value = os.environ.get("SB_MANAGER_PACKAGE_WHEEL")
    if not wheel_value:
        pytest.skip("set SB_MANAGER_PACKAGE_WHEEL to opt in")
    wheel = Path(wheel_value).resolve()
    wheelhouse_value = os.environ.get("SB_MANAGER_PACKAGE_WHEELHOUSE")
    allow_index = os.environ.get("SB_MANAGER_PACKAGE_ALLOW_INDEX") == "1"
    if wheelhouse_value is None and not allow_index:
        pytest.skip("select SB_MANAGER_PACKAGE_WHEELHOUSE or SB_MANAGER_PACKAGE_ALLOW_INDEX=1")
    wheelhouse = Path(wheelhouse_value).resolve() if wheelhouse_value is not None else None
    dependency_source = (
        DependencySource.WHEELHOUSE if wheelhouse is not None else DependencySource.INDEX
    )
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=SubprocessPackageEnvironmentBuilder(python_binary=Path(sys.executable)),
        install_lock=FileApplyLock(tmp_path / "package-install.lock"),
    )
    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=dependency_source,
            wheelhouse=wheelhouse,
        )
    )

    result = installer.install(plan, confirmed=True)

    assert plan.current_link.is_symlink()
    assert str(plan.current_link.readlink()) == result.active_target
    for command in ("sb-manager", "sb-manager-install", "sb-manager-install-policy"):
        completed = subprocess.run(
            [str(plan.launcher_directory / command), "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert "usage:" in completed.stdout
