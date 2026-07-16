from io import BytesIO
from pathlib import Path
from urllib.request import Request

from sb_manager.adapters.urllib_http import UrllibHttpClient


class FakeResponse(BytesIO):
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeOpener:
    def __init__(self, *payloads: bytes) -> None:
        self._payloads = iter(payloads)
        self.requests: list[tuple[Request, float]] = []

    def __call__(self, request: Request, timeout: float) -> FakeResponse:
        self.requests.append((request, timeout))
        return FakeResponse(next(self._payloads))


def test_https_client_reads_json_and_streams_downloads(tmp_path: Path) -> None:
    opener = FakeOpener(b'{"immutable": true}', b"archive bytes")
    client = UrllibHttpClient(opener=opener, timeout=7.5)

    metadata = client.get_json("https://api.github.com/releases/1")
    destination = tmp_path / "artifact.tar.gz"
    client.download("https://github.com/releases/artifact.tar.gz", destination)

    assert metadata == {"immutable": True}
    assert destination.read_bytes() == b"archive bytes"
    assert [(request.full_url, timeout) for request, timeout in opener.requests] == [
        ("https://api.github.com/releases/1", 7.5),
        ("https://github.com/releases/artifact.tar.gz", 7.5),
    ]
    assert opener.requests[0][0].get_header("Accept") == "application/vnd.github+json"
    assert opener.requests[1][0].get_header("Accept") == "application/octet-stream"


def test_https_client_rejects_non_https_urls() -> None:
    client = UrllibHttpClient(opener=FakeOpener(), timeout=1)

    try:
        client.get_json("http://api.github.com/releases/1")
    except ValueError as error:
        assert str(error) == "Artifact HTTP client requires HTTPS"
    else:
        raise AssertionError("non-HTTPS URL must be rejected")
