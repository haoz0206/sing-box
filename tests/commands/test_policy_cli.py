import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from sb_manager import policy_cli
from sb_manager.installation.privileged_policy import HELPER_RELATIVE_PATH

SUDO_POLICY_MODE = 0o440


class AcceptingValidator:
    def validate(self, provider: object, path: Path) -> None:
        assert path.read_text(encoding="utf-8")


class CurrentUserOwnership:
    def set(self, path: Path, *, uid: int, gid: int) -> None:
        assert uid == os.geteuid()
        assert gid == os.getegid()


def write_helper(root: Path) -> None:
    helper = root / HELPER_RELATIVE_PATH
    helper.parent.mkdir(parents=True)
    helper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    helper.chmod(0o755)


def test_root_command_installs_selected_policy_and_emits_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "host"
    root.mkdir()
    write_helper(root)
    monkeypatch.setattr(policy_cli, "HOST_ROOT", root)
    monkeypatch.setattr(policy_cli, "ROOT_UID", os.getuid())
    monkeypatch.setattr(policy_cli.os, "geteuid", os.getuid)
    monkeypatch.setattr(
        policy_cli.grp,
        "getgrnam",
        lambda name: SimpleNamespace(gr_gid=os.getgid()),
    )
    monkeypatch.setattr(
        policy_cli,
        "SubprocessAuthorizationPolicyValidator",
        AcceptingValidator,
    )
    monkeypatch.setattr(policy_cli, "PosixFileOwnership", CurrentUserOwnership)

    policy_cli.main(
        [
            "--authorization",
            "sudo",
            "--group",
            "sing-box-manager",
            "--confirm",
        ]
    )

    result = json.loads(capsys.readouterr().out)
    policy_path = root / "etc/sudoers.d/sing-box-manager"
    assert result == {
        "authorization_path": str(policy_path),
        "helper_path": str(root / HELPER_RELATIVE_PATH),
        "provider": "sudo",
        "status": "installed",
    }
    assert stat.S_IMODE(policy_path.stat().st_mode) == SUDO_POLICY_MODE


def test_command_without_confirmation_prints_plan_without_root_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(policy_cli, "HOST_ROOT", tmp_path)
    monkeypatch.setattr(policy_cli.os, "geteuid", lambda: 1000)

    policy_cli.main(["--authorization", "sudo", "--group", "sing-box-manager"])

    result = json.loads(capsys.readouterr().out)
    assert result == {
        "authorization_path": str(tmp_path / "etc/sudoers.d/sing-box-manager"),
        "directories": [
            {"mode": "0750", "path": str(tmp_path / "var/lib/sing-box-manager")},
            {
                "mode": "0770",
                "path": str(tmp_path / "var/lib/sing-box-manager/incoming"),
            },
            {"mode": "0700", "path": str(tmp_path / "var/lib/sing-box-manager/work")},
            {"mode": "0700", "path": str(tmp_path / "var/lib/sing-box-manager/acme")},
            {"mode": "0755", "path": str(tmp_path / "opt/sing-box-manager/core")},
            {"mode": "0755", "path": str(tmp_path / "etc/sing-box")},
            {"mode": "0755", "path": str(tmp_path / "etc/sing-box-manager/tls")},
        ],
        "group": "sing-box-manager",
        "helper_path": str(tmp_path / HELPER_RELATIVE_PATH),
        "provider": "sudo",
        "status": "planned",
    }
    assert list(tmp_path.iterdir()) == []


def test_confirmed_non_root_command_fails_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(policy_cli, "HOST_ROOT", tmp_path)
    monkeypatch.setattr(policy_cli.os, "geteuid", lambda: 1000)

    with pytest.raises(SystemExit) as exit_info:
        policy_cli.main(["--authorization", "sudo", "--confirm"])

    assert exit_info.value.code == policy_cli.EX_NOPERM
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "privilege-required"
    assert list(tmp_path.iterdir()) == []
