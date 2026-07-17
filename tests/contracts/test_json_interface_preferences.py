import json
import os
import stat
from pathlib import Path

import pytest

from sb_manager.adapters.json_interface_preferences import (
    MAX_PREFERENCE_DOCUMENT_BYTES,
    JsonInterfacePreferenceStore,
)
from sb_manager.application.interface_preferences import (
    ColorScheme,
    InterfacePreferences,
    PreferenceResetConflictError,
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


def test_preference_reset_refuses_a_file_changed_after_review(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preferences.json"
    reviewed = b'{"schema_version": 2, "color_scheme": "light"}\n'
    changed = b'{"schema_version": 3, "color_scheme": "dark"}\n'
    path.write_bytes(reviewed)
    store = JsonInterfacePreferenceStore(path)
    candidate = store.inspect_reset_candidate()
    path.write_bytes(changed)

    with pytest.raises(PreferenceResetConflictError):
        store.reset_candidate(
            expected_sha256=candidate.expected_sha256,
            preferences=InterfacePreferences(),
        )

    assert path.read_bytes() == changed
    assert not candidate.archive_path.exists()


def test_oversized_preferences_are_not_loaded_or_prepared_for_automatic_reset(
    tmp_path: Path,
) -> None:
    path = tmp_path / "preferences.json"
    valid_prefix = b'{"schema_version": 1, "color_scheme": "dark"}'
    path.write_bytes(valid_prefix + b" " * (MAX_PREFERENCE_DOCUMENT_BYTES + 1 - len(valid_prefix)))
    store = JsonInterfacePreferenceStore(path)

    with pytest.raises(PreferenceStoreError):
        store.load()
    with pytest.raises(PreferenceStoreError):
        store.inspect_reset_candidate()

    assert path.stat().st_size == MAX_PREFERENCE_DOCUMENT_BYTES + 1


def test_preference_reset_never_overwrites_an_archive_created_during_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "preferences.json"
    original = b'{"schema_version": 2, "color_scheme": "light"}\n'
    competing_archive = b"created-by-another-process"
    path.write_bytes(original)
    store = JsonInterfacePreferenceStore(path)
    candidate = store.inspect_reset_candidate()
    real_link = os.link

    def publish_after_competitor(source: str | Path, destination: str | Path) -> None:
        Path(destination).write_bytes(competing_archive)
        real_link(source, destination)

    monkeypatch.setattr(os, "link", publish_after_competitor)

    with pytest.raises(PreferenceStoreError):
        store.reset_candidate(
            expected_sha256=candidate.expected_sha256,
            preferences=InterfacePreferences(),
        )

    assert path.read_bytes() == original
    assert candidate.archive_path.read_bytes() == competing_archive
