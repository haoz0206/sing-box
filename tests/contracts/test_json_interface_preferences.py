import json
import stat
from pathlib import Path

import pytest

from sb_manager.adapters.json_interface_preferences import JsonInterfacePreferenceStore
from sb_manager.application.interface_preferences import (
    ColorScheme,
    InterfacePreferences,
    PreferenceStoreError,
)

PRIVATE_FILE_MODE = 0o600


def test_json_preference_store_round_trips_one_private_schema_v1_document(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config/sing-box-manager/preferences.json"
    store = JsonInterfacePreferenceStore(path)

    assert store.load() is None

    store.save(InterfacePreferences(color_scheme=ColorScheme.LIGHT))

    assert store.load() == InterfacePreferences(color_scheme=ColorScheme.LIGHT)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "color_scheme": "light",
    }
    assert stat.S_IMODE(path.stat().st_mode) == PRIVATE_FILE_MODE
    assert tuple(path.parent.glob(f".{path.name}.*")) == ()


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        '{"schema_version": 2, "color_scheme": "dark"}',
        '{"schema_version": 1, "color_scheme": "blue"}',
        '{"schema_version": 1}',
        '{"schema_version": 1, "color_scheme": "dark", "unknown": true}',
    ],
)
def test_json_preference_store_rejects_noncanonical_documents(
    tmp_path: Path,
    payload: str,
) -> None:
    path = tmp_path / "preferences.json"
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(PreferenceStoreError):
        JsonInterfacePreferenceStore(path).load()


def test_json_preference_store_refuses_a_symbolic_link_without_touching_its_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "operator-owned.json"
    target.write_text(
        '{"schema_version": 1, "color_scheme": "dark"}\n',
        encoding="utf-8",
    )
    path = tmp_path / "preferences.json"
    path.symlink_to(target)
    store = JsonInterfacePreferenceStore(path)

    with pytest.raises(PreferenceStoreError):
        store.load()
    with pytest.raises(PreferenceStoreError):
        store.save(InterfacePreferences(color_scheme=ColorScheme.LIGHT))

    assert path.is_symlink()
    assert target.read_text(encoding="utf-8") == ('{"schema_version": 1, "color_scheme": "dark"}\n')


def test_json_preference_store_preserves_an_existing_future_schema(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preferences.json"
    original = b'{"schema_version": 2, "color_scheme": "light"}\n'
    path.write_bytes(original)

    with pytest.raises(PreferenceStoreError):
        JsonInterfacePreferenceStore(path).save(InterfacePreferences(color_scheme=ColorScheme.DARK))

    assert path.read_bytes() == original
    assert tuple(path.parent.glob(f".{path.name}.*")) == ()
