"""Public seam for bounded HTTPS reads used by artifact adapters."""

from pathlib import Path
from typing import Protocol


class HttpClient(Protocol):
    """Read structured metadata or stream one response to a file."""

    def get_json(self, url: str) -> object: ...

    def download(self, url: str, destination: Path) -> None: ...
