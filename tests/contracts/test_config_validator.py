from pathlib import Path

from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.seams.config_validator import ConfigValidationResult


def test_sing_box_validator_reports_missing_binary_as_actionable_failure(
    tmp_path: Path,
) -> None:
    missing_binary = tmp_path / "missing-sing-box"
    config_path = tmp_path / "config.json"
    config_path.write_text("{}\n", encoding="utf-8")

    result = SingBoxConfigValidator(binary=missing_binary).validate(config_path)

    assert result == ConfigValidationResult(
        valid=False,
        diagnostics=f"sing-box executable not found: {missing_binary}",
    )


def test_sing_box_validator_reports_check_failure_with_diagnostics(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}\n", encoding="utf-8")
    argument_log = tmp_path / "arguments.txt"
    fake_sing_box = tmp_path / "sing-box"
    fake_sing_box.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(argument_log)!r}).write_text('\\n'.join(sys.argv[1:]), encoding='utf-8')\n"
        "print('configuration is invalid', file=sys.stderr)\n"
        "raise SystemExit(23)\n",
        encoding="utf-8",
    )
    fake_sing_box.chmod(0o755)

    result = SingBoxConfigValidator(binary=fake_sing_box).validate(config_path)

    assert result == ConfigValidationResult(
        valid=False,
        diagnostics="configuration is invalid",
    )
    assert argument_log.read_text(encoding="utf-8").splitlines() == [
        "check",
        "-c",
        str(config_path),
    ]
