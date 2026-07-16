import subprocess
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from sb_manager.installation.package_release import (
    DependencySource,
    PackageInstallError,
    PackageInstallRequest,
    PackageRollbackRequest,
    VersionedPackageInstaller,
)
from sb_manager.seams.apply_lock import ApplyLockUnavailableError
from sb_manager.seams.package_environment import PackageEnvironmentBuildRequest

FIXTURE_WHEEL_SHA256 = "777c21316077b0e0863655a8d054895a63c397224d4350894f28e82a00af2397"
LAUNCHER_MODE = 0o755
PACKAGE_COMMANDS = (
    "sb-manager",
    "sb-manager-privileged",
    "sb-manager-install-policy",
    "sb-manager-install",
)


class FixtureEnvironmentBuilder:
    def __init__(self, *, label: str = "0.1.0") -> None:
        self.label = label

    def build(self, request: PackageEnvironmentBuildRequest) -> None:
        command_directory = request.release_directory / "venv/bin"
        command_directory.mkdir(parents=True)
        for command in PACKAGE_COMMANDS:
            command_path = command_directory / command
            command_path.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                f"print('fixture {command} {self.label}', *sys.argv[1:])\n",
                encoding="utf-8",
            )
            command_path.chmod(0o755)


class FailingEnvironmentBuilder:
    def build(self, request: PackageEnvironmentBuildRequest) -> None:
        request.release_directory.mkdir(parents=True)
        raise RuntimeError("pip failed while resolving dependencies")


class SourceReplacingEnvironmentBuilder(FixtureEnvironmentBuilder):
    def __init__(self, *, source_wheel: Path) -> None:
        super().__init__()
        self.source_wheel = source_wheel

    def build(self, request: PackageEnvironmentBuildRequest) -> None:
        self.source_wheel.write_bytes(b"replaced after plan validation")
        with zipfile.ZipFile(request.wheel_path) as archive:
            metadata = archive.read("sing_box_manager-0.1.0.dist-info/METADATA")
        assert b"Version: 0.1.0" in metadata
        super().build(request)


class UnavailableInstallLock:
    @contextmanager
    def acquire(self) -> Iterator[None]:
        raise ApplyLockUnavailableError(Path("/run/lock/sing-box-manager-package.lock"))
        yield


def _write_fixture_wheel(path: Path, *, version: str = "0.1.0") -> Path:
    metadata = zipfile.ZipInfo(f"sing_box_manager-{version}.dist-info/METADATA")
    metadata.date_time = (2026, 1, 1, 0, 0, 0)
    metadata.compress_type = zipfile.ZIP_STORED
    wheel = zipfile.ZipInfo(f"sing_box_manager-{version}.dist-info/WHEEL")
    wheel.date_time = metadata.date_time
    wheel.compress_type = zipfile.ZIP_STORED
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            metadata,
            f"Metadata-Version: 2.4\nName: sing-box-manager\nVersion: {version}\n",
        )
        archive.writestr(wheel, "Wheel-Version: 1.0\nTag: py3-none-any\n")
    return path


def test_operator_can_preview_one_versioned_package_release_without_host_mutation(
    tmp_path: Path,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )

    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    assert plan.package_version == "0.1.0"
    assert plan.wheel_sha256 == FIXTURE_WHEEL_SHA256
    assert plan.release_directory == root / f"releases/0.1.0-{FIXTURE_WHEEL_SHA256}"
    assert plan.current_link == root / "current"
    assert plan.launcher_directory == root / "bin"
    assert plan.dependency_source is DependencySource.INDEX
    assert plan.mutates_host is False
    assert not root.exists()


def test_confirmed_install_activates_all_commands_through_stable_launchers(
    tmp_path: Path,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    result = installer.install(plan, confirmed=True)

    assert result.package_version == "0.1.0"
    assert result.release_directory == plan.release_directory
    assert result.active_target == f"releases/0.1.0-{FIXTURE_WHEEL_SHA256}"
    assert result.previous_target is None
    assert plan.current_link.is_symlink()
    assert str(plan.current_link.readlink()) == result.active_target
    assert plan.release_directory.stat().st_mode & 0o777 == LAUNCHER_MODE
    for command in PACKAGE_COMMANDS:
        launcher = plan.launcher_directory / command
        assert launcher.is_file()
        assert not launcher.is_symlink()
        assert launcher.stat().st_mode & 0o777 == LAUNCHER_MODE
    completed = subprocess.run(
        [str(plan.launcher_directory / "sb-manager"), "--probe"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "fixture sb-manager 0.1.0 --probe\n"


def test_operator_can_preview_rollback_to_one_exact_retained_release(
    tmp_path: Path,
) -> None:
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    first_wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    first_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=first_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    installer.install(first_plan, confirmed=True)
    second_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    second_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=second_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    second = installer.install(second_plan, confirmed=True)

    rollback_plan = installer.plan_rollback(
        PackageRollbackRequest(target_release=first_plan.release_directory.name)
    )

    assert rollback_plan.active_target == second.active_target
    assert rollback_plan.target_release == first_plan.release_directory.name
    assert rollback_plan.target_directory == first_plan.release_directory
    assert rollback_plan.current_link == root / "current"
    assert rollback_plan.mutates_host is False
    assert str(rollback_plan.current_link.readlink()) == second.active_target


def test_package_rollback_requires_explicit_confirmation(tmp_path: Path) -> None:
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    first_wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    first_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=first_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    installer.install(first_plan, confirmed=True)
    second_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    second_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=second_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    second = installer.install(second_plan, confirmed=True)
    rollback_plan = installer.plan_rollback(
        PackageRollbackRequest(target_release=first_plan.release_directory.name)
    )

    with pytest.raises(PackageInstallError, match="explicit confirmation"):
        installer.rollback(rollback_plan, confirmed=False)

    assert str(rollback_plan.current_link.readlink()) == second.active_target


def test_confirmed_rollback_atomically_reactivates_the_exact_retained_release(
    tmp_path: Path,
) -> None:
    root = tmp_path / "opt/sing-box-manager"
    first_installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(label="0.1.0"),
    )
    first_wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    first_plan = first_installer.plan(
        PackageInstallRequest(
            wheel_path=first_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    first = first_installer.install(first_plan, confirmed=True)
    second_installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(label="0.2.0"),
    )
    second_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    second_plan = second_installer.plan(
        PackageInstallRequest(
            wheel_path=second_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    second = second_installer.install(second_plan, confirmed=True)
    rollback_plan = second_installer.plan_rollback(
        PackageRollbackRequest(target_release=first_plan.release_directory.name)
    )

    result = second_installer.rollback(rollback_plan, confirmed=True)

    assert result.active_target == first.active_target
    assert result.previous_target == second.active_target
    assert str(rollback_plan.current_link.readlink()) == first.active_target
    completed = subprocess.run(
        [str(first_plan.launcher_directory / "sb-manager"), "--after-rollback"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "fixture sb-manager 0.1.0 --after-rollback\n"


def test_rollback_rechecks_that_retained_release_remains_immutable(
    tmp_path: Path,
) -> None:
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    first_wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    first_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=first_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    installer.install(first_plan, confirmed=True)
    second_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    second_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=second_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    second = installer.install(second_plan, confirmed=True)
    rollback_plan = installer.plan_rollback(
        PackageRollbackRequest(target_release=first_plan.release_directory.name)
    )
    target_command = first_plan.release_directory / "venv/bin/sb-manager"
    target_command.chmod(0o775)

    with pytest.raises(PackageInstallError, match="writable by group or other"):
        installer.rollback(rollback_plan, confirmed=True)

    assert str(rollback_plan.current_link.readlink()) == second.active_target


def test_rollback_rejects_a_plan_after_active_release_changes(tmp_path: Path) -> None:
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    first_wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    first_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=first_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    installer.install(first_plan, confirmed=True)
    second_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    second_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=second_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    installer.install(second_plan, confirmed=True)
    stale_plan = installer.plan_rollback(
        PackageRollbackRequest(target_release=first_plan.release_directory.name)
    )
    third_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.3.0-py3-none-any.whl",
        version="0.3.0",
    )
    third_plan = installer.plan(
        PackageInstallRequest(
            wheel_path=third_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    third = installer.install(third_plan, confirmed=True)

    with pytest.raises(PackageInstallError, match="no longer matches"):
        installer.rollback(stale_plan, confirmed=True)

    assert str(stale_plan.current_link.readlink()) == third.active_target


def test_failed_upgrade_preserves_the_active_release_and_launcher_behavior(
    tmp_path: Path,
) -> None:
    root = tmp_path / "opt/sing-box-manager"
    first_wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    first_installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    first_plan = first_installer.plan(
        PackageInstallRequest(
            wheel_path=first_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )
    first = first_installer.install(first_plan, confirmed=True)
    next_wheel = _write_fixture_wheel(
        tmp_path / "sing_box_manager-0.2.0-py3-none-any.whl",
        version="0.2.0",
    )
    failing_installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FailingEnvironmentBuilder(),
    )
    next_plan = failing_installer.plan(
        PackageInstallRequest(
            wheel_path=next_wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    with pytest.raises(PackageInstallError, match="environment build failed"):
        failing_installer.install(next_plan, confirmed=True)

    assert str(first_plan.current_link.readlink()) == first.active_target
    assert not next_plan.release_directory.exists()
    completed = subprocess.run(
        [str(first_plan.launcher_directory / "sb-manager"), "--still-active"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "fixture sb-manager 0.1.0 --still-active\n"


def test_confirmed_install_builds_only_from_the_privately_verified_wheel(
    tmp_path: Path,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=SourceReplacingEnvironmentBuilder(source_wheel=wheel),
    )
    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    result = installer.install(plan, confirmed=True)

    assert result.active_target == f"releases/0.1.0-{FIXTURE_WHEEL_SHA256}"
    assert wheel.read_bytes() == b"replaced after plan validation"
    assert not (plan.release_directory / wheel.name).exists()
    completed = subprocess.run(
        [str(plan.launcher_directory / "sb-manager"), "--verified-copy"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "fixture sb-manager 0.1.0 --verified-copy\n"


def test_install_rejects_an_existing_package_root_writable_by_other_users(
    tmp_path: Path,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    root.mkdir(parents=True)
    root.chmod(0o777)
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    with pytest.raises(PackageInstallError, match="writable by group or other"):
        installer.install(plan, confirmed=True)

    assert not plan.current_link.exists()
    assert not plan.release_directory.exists()


def test_install_lock_contention_leaves_the_host_untouched(tmp_path: Path) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
        install_lock=UnavailableInstallLock(),
    )
    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    with pytest.raises(ApplyLockUnavailableError):
        installer.install(plan, confirmed=True)

    assert not root.exists()


def test_install_rejects_an_active_package_target_outside_versioned_releases(
    tmp_path: Path,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    root.mkdir(parents=True)
    (root / "current").symlink_to(tmp_path / "operator-controlled", target_is_directory=True)
    installer = VersionedPackageInstaller(
        root=root,
        environment_builder=FixtureEnvironmentBuilder(),
    )
    plan = installer.plan(
        PackageInstallRequest(
            wheel_path=wheel,
            dependency_source=DependencySource.INDEX,
        )
    )

    with pytest.raises(PackageInstallError, match="outside versioned releases"):
        installer.install(plan, confirmed=True)

    assert not plan.release_directory.exists()
    assert plan.current_link.is_symlink()
