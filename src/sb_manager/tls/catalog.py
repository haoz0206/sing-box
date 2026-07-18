"""Deep TLS catalog for server fragments and client verification policy."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar, Protocol, TypeAlias


class TlsKind(str, Enum):
    """TLS material strategies supported by desired state."""

    ACME = "acme"
    OPERATOR_FILES = "operator-files"


class TlsMaterialError(ValueError):
    """An operator-provided TLS file is absent or unusable."""

    def __init__(self, *, path: Path, role: str) -> None:
        super().__init__(f"TLS {role} file is unavailable: {path}")
        self.path = path
        self.role = role


@dataclass(frozen=True, slots=True)
class AcmeTlsIntent:
    """Request a publicly trusted certificate through sing-box ACME."""

    kind: ClassVar[TlsKind] = TlsKind.ACME

    server_name: str
    email: str
    data_directory: Path


@dataclass(frozen=True, slots=True)
class OperatorFileTlsIntent:
    """Use certificate and private-key PEM files already on the host."""

    kind: ClassVar[TlsKind] = TlsKind.OPERATOR_FILES

    server_name: str
    certificate_path: Path
    key_path: Path


TlsIntent: TypeAlias = AcmeTlsIntent | OperatorFileTlsIntent


@dataclass(frozen=True, slots=True)
class TlsClientPolicy:
    """Settings a client must use to verify the server certificate."""

    server_name: str
    insecure: bool


@dataclass(frozen=True, slots=True)
class TlsArtifacts:
    """Consistent server TLS, top-level providers, and client policy."""

    server: dict[str, object]
    certificate_providers: tuple[dict[str, object], ...]
    client: TlsClientPolicy


class TlsHandler(Protocol):
    """Internal adapter interface selected by TLS intent kind."""

    kind: TlsKind

    def materialize(self, intent: TlsIntent, tag: str) -> TlsArtifacts: ...


class TlsCatalog:
    """Hide certificate strategy details behind one materialization operation."""

    def __init__(self, handlers: Iterable[TlsHandler]) -> None:
        self._handlers = {handler.kind: handler for handler in handlers}

    def materialize(self, intent: TlsIntent, tag: str) -> TlsArtifacts:
        return self._handlers[intent.kind].materialize(intent, tag)


class AcmeTlsHandler:
    """Build the inline ACME shape shared by sing-box 1.13 and 1.14."""

    kind = TlsKind.ACME

    def materialize(self, intent: TlsIntent, tag: str) -> TlsArtifacts:
        if not isinstance(intent, AcmeTlsIntent):
            raise TypeError("ACME handler received a non-ACME intent")
        return TlsArtifacts(
            server={
                "enabled": True,
                "server_name": intent.server_name,
                "acme": {
                    "domain": [intent.server_name],
                    "email": intent.email,
                    "data_directory": str(intent.data_directory),
                },
            },
            certificate_providers=(),
            client=TlsClientPolicy(
                server_name=intent.server_name,
                insecure=False,
            ),
        )


class OperatorFileTlsHandler:
    """Reference operator-managed certificate and key files directly."""

    kind = TlsKind.OPERATOR_FILES

    def materialize(self, intent: TlsIntent, tag: str) -> TlsArtifacts:
        if not isinstance(intent, OperatorFileTlsIntent):
            raise TypeError("File TLS handler received a non-file intent")
        for role, path in (
            ("certificate", intent.certificate_path),
            ("private-key", intent.key_path),
        ):
            if not path.is_file():
                raise TlsMaterialError(path=path, role=role)
        return TlsArtifacts(
            server={
                "enabled": True,
                "server_name": intent.server_name,
                "certificate_path": str(intent.certificate_path),
                "key_path": str(intent.key_path),
            },
            certificate_providers=(),
            client=TlsClientPolicy(
                server_name=intent.server_name,
                insecure=False,
            ),
        )
