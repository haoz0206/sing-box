"""Deep catalog for consistent server and client V2Ray transport fragments."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebSocketTransportIntent:
    """WebSocket request path and optional client Host header."""

    path: str
    host: str | None = None


@dataclass(frozen=True, slots=True)
class GrpcTransportIntent:
    """gRPC service name shared by server and client."""

    service_name: str


TransportIntent = WebSocketTransportIntent | GrpcTransportIntent


@dataclass(frozen=True, slots=True)
class TransportArtifacts:
    """Matching server and client transport fragments."""

    server: dict[str, object]
    client: dict[str, object]


class TransportCatalog:
    """Hide transport-specific server/client differences behind one operation."""

    def materialize(self, intent: TransportIntent) -> TransportArtifacts:
        if isinstance(intent, WebSocketTransportIntent):
            server: dict[str, object] = {"type": "ws", "path": intent.path}
            client = dict(server)
            if intent.host is not None:
                client["headers"] = {"Host": intent.host}
        else:
            server = {"type": "grpc", "service_name": intent.service_name}
            client = dict(server)
        return TransportArtifacts(server=server, client=client)
