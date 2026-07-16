"""HTTPS client backed by the Python standard library."""

import json
import shutil
from pathlib import Path
from types import TracebackType
from typing import Protocol, cast
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class HttpResponse(Protocol):
    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> "HttpResponse": ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...


class UrlOpener(Protocol):
    def __call__(self, request: Request, timeout: float) -> HttpResponse: ...


def _default_opener(request: Request, timeout: float) -> HttpResponse:
    return cast(HttpResponse, urlopen(request, timeout=timeout))


class UrllibHttpClient:
    """Perform verified-TLS reads with bounded blocking time."""

    def __init__(
        self,
        *,
        opener: UrlOpener | None = None,
        timeout: float = 30,
    ) -> None:
        self._opener = opener or _default_opener
        self._timeout = timeout

    def get_json(self, url: str) -> object:
        request = self._request(url, accept="application/vnd.github+json")
        with self._opener(request, self._timeout) as response:
            return json.load(response)

    def download(self, url: str, destination: Path) -> None:
        request = self._request(url, accept="application/octet-stream")
        with (
            self._opener(request, self._timeout) as response,
            destination.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)

    @staticmethod
    def _request(url: str, *, accept: str) -> Request:
        if urlsplit(url).scheme != "https":
            raise ValueError("Artifact HTTP client requires HTTPS")
        return Request(
            url,
            headers={
                "Accept": accept,
                "User-Agent": "sing-box-manager/0.1",
            },
        )
