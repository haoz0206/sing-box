from sb_manager.transports.catalog import (
    GrpcTransportIntent,
    TransportArtifacts,
    TransportCatalog,
    WebSocketTransportIntent,
)


def test_transport_catalog_materializes_websocket_server_and_client_fragments() -> None:
    catalog = TransportCatalog()

    artifacts = catalog.materialize(
        WebSocketTransportIntent(
            path="/proxy",
            host="cdn.example.com",
        )
    )

    assert artifacts == TransportArtifacts(
        server={"type": "ws", "path": "/proxy"},
        client={
            "type": "ws",
            "path": "/proxy",
            "headers": {"Host": "cdn.example.com"},
        },
    )


def test_transport_catalog_materializes_matching_grpc_fragments() -> None:
    artifacts = TransportCatalog().materialize(GrpcTransportIntent(service_name="ProxyService"))

    assert artifacts == TransportArtifacts(
        server={"type": "grpc", "service_name": "ProxyService"},
        client={"type": "grpc", "service_name": "ProxyService"},
    )
