from pathlib import Path

from sb_manager.adapters.openrc_logs import OpenRCLogSource
from sb_manager.adapters.systemd_logs import SystemdJournalLogSource
from sb_manager.seams.runtime_logs import RuntimeLogCapture


def _write_fake_command(
    tmp_path: Path,
    *,
    name: str,
    output: str,
    returncode: int = 0,
) -> tuple[Path, Path]:
    argument_log = tmp_path / f"{name}-arguments.txt"
    command = tmp_path / name
    command.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(argument_log)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n"
        f"sys.stdout.write({output!r})\n"
        f"raise SystemExit({returncode})\n",
        encoding="utf-8",
    )
    command.chmod(0o755)
    return command, argument_log


def test_systemd_log_source_uses_a_read_only_bounded_journal_query(tmp_path: Path) -> None:
    journalctl, argument_log = _write_fake_command(
        tmp_path,
        name="journalctl",
        output="first\nsecond\n",
    )

    capture = SystemdJournalLogSource(
        binary=journalctl,
        service_name="sing-box.service",
    ).read_recent(limit=80)

    assert capture == RuntimeLogCapture(
        available=True,
        source_label="systemd journal",
        lines=("first", "second"),
    )
    assert argument_log.read_text(encoding="utf-8") == (
        "--unit sing-box.service --lines 80 --no-pager --output short-iso --quiet"
    )


def test_systemd_no_entries_marker_is_an_empty_available_capture(tmp_path: Path) -> None:
    journalctl, _ = _write_fake_command(
        tmp_path,
        name="journalctl",
        output="-- No entries --\n",
    )

    capture = SystemdJournalLogSource(binary=journalctl).read_recent(limit=20)

    assert capture == RuntimeLogCapture(
        available=True,
        source_label="systemd journal",
        lines=(),
    )


def test_log_capture_replaces_malformed_utf8_instead_of_aborting_diagnostics(
    tmp_path: Path,
) -> None:
    journalctl = tmp_path / "journalctl"
    journalctl.write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.stdout.buffer.write(b'valid \\xff line\\n')\n",
        encoding="utf-8",
    )
    journalctl.chmod(0o755)

    capture = SystemdJournalLogSource(binary=journalctl).read_recent(limit=20)

    assert capture == RuntimeLogCapture(
        available=True,
        source_label="systemd journal",
        lines=("valid � line",),
    )


def test_openrc_log_source_filters_syslog_and_applies_the_bound_locally(tmp_path: Path) -> None:
    logread, argument_log = _write_fake_command(
        tmp_path,
        name="logread",
        output=("unrelated daemon line\nsing-box old\nSING-BOX first\nsing-box second\n"),
    )

    capture = OpenRCLogSource(binary=logread, service_name="sing-box").read_recent(limit=2)

    assert capture == RuntimeLogCapture(
        available=True,
        source_label="OpenRC syslog",
        lines=("SING-BOX first", "sing-box second"),
    )
    assert argument_log.read_text(encoding="utf-8") == ""


def test_log_sources_return_typed_unavailability_for_command_failure(tmp_path: Path) -> None:
    journalctl, _ = _write_fake_command(
        tmp_path,
        name="journalctl",
        output="permission denied\n",
        returncode=1,
    )
    logread, _ = _write_fake_command(
        tmp_path,
        name="logread",
        output="log buffer unavailable\n",
        returncode=1,
    )

    assert SystemdJournalLogSource(binary=journalctl).read_recent(limit=20) == RuntimeLogCapture(
        available=False,
        source_label="systemd journal",
        lines=(),
        diagnostics="permission denied",
    )
    assert OpenRCLogSource(binary=logread).read_recent(limit=20) == RuntimeLogCapture(
        available=False,
        source_label="OpenRC syslog",
        lines=(),
        diagnostics="log buffer unavailable",
    )


def test_log_sources_return_typed_unavailability_when_binary_is_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    systemd = SystemdJournalLogSource(binary=missing).read_recent(limit=20)
    openrc = OpenRCLogSource(binary=missing).read_recent(limit=20)

    assert not systemd.available
    assert systemd.lines == ()
    assert str(missing) in systemd.diagnostics
    assert not openrc.available
    assert openrc.lines == ()
    assert str(missing) in openrc.diagnostics
