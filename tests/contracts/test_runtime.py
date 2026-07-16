from pathlib import Path

from sb_manager.adapters.openrc_runtime import OpenRCRuntime
from sb_manager.adapters.systemd_runtime import SystemdRuntime
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult


def test_systemd_runtime_refreshes_and_checks_the_service(tmp_path: Path) -> None:
    argument_log = tmp_path / "arguments.txt"
    fake_systemctl = tmp_path / "systemctl"
    fake_systemctl.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"log = Path({str(argument_log)!r})\n"
        "with log.open('a', encoding='utf-8') as output:\n"
        "    output.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1] == 'is-active':\n"
        "    print('active')\n"
        "else:\n"
        "    print('service reloaded')\n",
        encoding="utf-8",
    )
    fake_systemctl.chmod(0o755)
    runtime = SystemdRuntime(binary=fake_systemctl, service_name="sing-box.service")

    refresh = runtime.refresh()
    postcondition = runtime.check_health()

    assert refresh == RuntimeRefreshResult(success=True, diagnostics="service reloaded")
    assert postcondition == RuntimePostcondition(healthy=True, diagnostics="active")
    assert argument_log.read_text(encoding="utf-8").splitlines() == [
        "reload-or-restart sing-box.service",
        "is-active sing-box.service",
    ]
    assert runtime.recovery_instructions() == (
        "运行 systemctl restart sing-box.service。",
        "运行 systemctl status sing-box.service --no-pager。",
    )


def test_openrc_runtime_refreshes_and_checks_the_service(tmp_path: Path) -> None:
    argument_log = tmp_path / "arguments.txt"
    fake_rc_service = tmp_path / "rc-service"
    fake_rc_service.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"log = Path({str(argument_log)!r})\n"
        "with log.open('a', encoding='utf-8') as output:\n"
        "    output.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "print('service operation succeeded')\n",
        encoding="utf-8",
    )
    fake_rc_service.chmod(0o755)
    runtime = OpenRCRuntime(binary=fake_rc_service, service_name="sing-box")

    refresh = runtime.refresh()
    postcondition = runtime.check_health()

    assert refresh == RuntimeRefreshResult(
        success=True,
        diagnostics="service operation succeeded",
    )
    assert postcondition == RuntimePostcondition(
        healthy=True,
        diagnostics="service operation succeeded",
    )
    assert argument_log.read_text(encoding="utf-8").splitlines() == [
        "sing-box restart",
        "sing-box status",
    ]
    assert runtime.recovery_instructions() == (
        "运行 rc-service sing-box restart。",
        "运行 rc-service sing-box status。",
    )
