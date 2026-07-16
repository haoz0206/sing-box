import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

from sb_manager import package_cli
from sb_manager.seams.package_environment import PackageEnvironmentBuildRequest

FIXTURE_WHEEL_SHA256 = "777c21316077b0e0863655a8d054895a63c397224d4350894f28e82a00af2397"
EX_NOPERM = 77
PACKAGE_COMMANDS = (
    "sb-manager",
    "sb-manager-privileged",
    "sb-manager-install-policy",
    "sb-manager-install",
)


class FixtureEnvironmentBuilder:
    def build(self, request: PackageEnvironmentBuildRequest) -> None:
        command_directory = request.release_directory / "venv/bin"
        command_directory.mkdir(parents=True)
        for command in PACKAGE_COMMANDS:
            command_path = command_directory / command
            command_path.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                f"print('installed {command} 0.1.0', *sys.argv[1:])\n",
                encoding="utf-8",
            )
            command_path.chmod(0o755)


def _fixture_environment_builder(*, python_binary: object) -> FixtureEnvironmentBuilder:
    assert python_binary
    return FixtureEnvironmentBuilder()


def _write_fixture_wheel(path: Path) -> Path:
    metadata = zipfile.ZipInfo("sing_box_manager-0.1.0.dist-info/METADATA")
    metadata.date_time = (2026, 1, 1, 0, 0, 0)
    metadata.compress_type = zipfile.ZIP_STORED
    wheel = zipfile.ZipInfo("sing_box_manager-0.1.0.dist-info/WHEEL")
    wheel.date_time = metadata.date_time
    wheel.compress_type = zipfile.ZIP_STORED
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            metadata,
            "Metadata-Version: 2.4\nName: sing-box-manager\nVersion: 0.1.0\n",
        )
        archive.writestr(wheel, "Wheel-Version: 1.0\nTag: py3-none-any\n")
    return path


def test_package_command_previews_exact_release_without_root_or_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    monkeypatch.setattr(package_cli, "HOST_ROOT", root)

    package_cli.main(["--wheel", str(wheel), "--allow-index"])

    output = json.loads(capsys.readouterr().out)
    assert output == {
        "status": "planned",
        "package_version": "0.1.0",
        "wheel_path": str(wheel),
        "wheel_sha256": FIXTURE_WHEEL_SHA256,
        "release_directory": str(root / f"releases/0.1.0-{FIXTURE_WHEEL_SHA256}"),
        "current_link": str(root / "current"),
        "launcher_directory": str(root / "bin"),
        "dependency_source": "index",
        "wheelhouse": None,
        "mutates_host": False,
    }
    assert not root.exists()


def test_confirmed_package_install_requires_root_before_host_mutation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    monkeypatch.setattr(package_cli, "HOST_ROOT", root)
    monkeypatch.setattr(os, "geteuid", lambda: 1000)

    with pytest.raises(SystemExit) as exit_info:
        package_cli.main(["--wheel", str(wheel), "--allow-index", "--confirm"])

    assert exit_info.value.code == EX_NOPERM
    assert json.loads(capsys.readouterr().err) == {
        "status": "error",
        "error": "privilege-required",
        "message": "Confirmed package installation must run as root",
    }
    assert not root.exists()


def test_confirmed_package_command_installs_and_reports_the_active_release(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel = _write_fixture_wheel(tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl")
    root = tmp_path / "opt/sing-box-manager"
    monkeypatch.setattr(package_cli, "HOST_ROOT", root)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        package_cli,
        "SubprocessPackageEnvironmentBuilder",
        _fixture_environment_builder,
    )

    package_cli.main(["--wheel", str(wheel), "--allow-index", "--confirm"])

    output = json.loads(capsys.readouterr().out)
    active_target = f"releases/0.1.0-{FIXTURE_WHEEL_SHA256}"
    assert output == {
        "status": "installed",
        "package_version": "0.1.0",
        "release_directory": str(root / active_target),
        "launcher_directory": str(root / "bin"),
        "active_target": active_target,
        "previous_target": None,
    }
    completed = subprocess.run(
        [str(root / "bin/sb-manager"), "--from-install-command"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "installed sb-manager 0.1.0 --from-install-command\n"
