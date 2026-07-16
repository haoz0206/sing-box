import hashlib
from pathlib import Path

import pytest

from sb_manager.adapters.file_config_target import FileConfigurationTargetInspector
from sb_manager.seams.config_target import ConfigTargetInspectionError, LiveConfigObservation


def test_file_config_inspector_reports_absence_and_exact_bytes(tmp_path: Path) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    inspector = FileConfigurationTargetInspector(config_path=config_path)

    assert inspector.inspect() == LiveConfigObservation(exists=False, sha256=None)

    content = b'{"inbounds":[]}\n'
    config_path.parent.mkdir(parents=True)
    config_path.write_bytes(content)

    assert inspector.inspect() == LiveConfigObservation(
        exists=True,
        sha256=hashlib.sha256(content).hexdigest(),
    )


def test_file_config_inspector_rejects_non_regular_target(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.mkdir()

    with pytest.raises(ConfigTargetInspectionError, match="regular file"):
        FileConfigurationTargetInspector(config_path=config_path).inspect()


def test_file_config_inspector_rejects_dangling_symlink(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.symlink_to(tmp_path / "missing.json")

    with pytest.raises(ConfigTargetInspectionError, match="regular file"):
        FileConfigurationTargetInspector(config_path=config_path).inspect()
