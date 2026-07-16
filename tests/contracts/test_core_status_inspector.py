from pathlib import Path

from sb_manager.adapters.sing_box_core_status import SingBoxCoreStatusInspector
from sb_manager.seams.core_status import CoreStatusObservation


def _write_executable(path: Path, body: str) -> Path:
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_core_status_inspector_returns_the_self_reported_version(tmp_path: Path) -> None:
    binary = _write_executable(
        tmp_path / "sing-box",
        "print('sing-box version 1.14.0-alpha.45')\n",
    )

    observation = SingBoxCoreStatusInspector(binary=binary).inspect()

    assert observation == CoreStatusObservation(
        available=True,
        version="1.14.0-alpha.45",
        diagnostics="sing-box version 1.14.0-alpha.45",
    )


def test_core_status_inspector_treats_malformed_output_as_unavailable(tmp_path: Path) -> None:
    binary = _write_executable(tmp_path / "sing-box", "print('unexpected output')\n")

    observation = SingBoxCoreStatusInspector(binary=binary).inspect()

    assert observation.available is False
    assert observation.version is None
    assert "unexpected output" in observation.diagnostics


def test_core_status_inspector_reports_a_missing_binary_without_raising(
    tmp_path: Path,
) -> None:
    binary = tmp_path / "missing-sing-box"

    observation = SingBoxCoreStatusInspector(binary=binary).inspect()

    assert observation.available is False
    assert observation.version is None
    assert str(binary) in observation.diagnostics
