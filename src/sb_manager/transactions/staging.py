"""Isolated filesystem staging for generated configuration."""

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True, slots=True)
class StagedConfiguration:
    """Paths owned by one temporary configuration workspace."""

    root: Path
    config_path: Path


class ConfigurationStager:
    """Write generated configuration inside a disposable workspace."""

    def __init__(self, *, parent: Path) -> None:
        self._parent = parent

    @contextmanager
    def stage(self, document: Mapping[str, object]) -> Iterator[StagedConfiguration]:
        self._parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".sb-manager-", dir=self._parent) as temporary:
            root = Path(temporary)
            config_path = root / "config.json"
            with config_path.open("w", encoding="utf-8") as config_file:
                json.dump(document, config_file, ensure_ascii=False, indent=2, sort_keys=True)
                config_file.write("\n")
            yield StagedConfiguration(root=root, config_path=config_path)
