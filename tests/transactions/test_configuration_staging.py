import json
from pathlib import Path

from sb_manager.transactions.staging import ConfigurationStager


def test_configuration_is_staged_in_an_isolated_temporary_directory(
    tmp_path: Path,
) -> None:
    document = {
        "inbounds": [{"type": "vless", "tag": "profile-phone"}],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    staged_root: Path

    with ConfigurationStager(parent=tmp_path).stage(document) as staged:
        staged_root = staged.root
        assert staged.root.parent == tmp_path
        assert staged.config_path == staged.root / "config.json"
        assert json.loads(staged.config_path.read_text(encoding="utf-8")) == document

    assert not staged_root.exists()
