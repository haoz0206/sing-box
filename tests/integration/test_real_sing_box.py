import json
import os
from pathlib import Path

import pytest

from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.cli import create_protocol_catalog
from sb_manager.domain.installation import (
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.privileged.config_policy import ManagedConfigurationPolicy
from sb_manager.tls.catalog import AcmeTlsIntent
from sb_manager.transports.catalog import (
    GrpcTransportIntent,
    TransportIntent,
    WebSocketTransportIntent,
)


@pytest.fixture(scope="session")
def real_sing_box_binary() -> Path:
    configured = os.environ.get("SB_MANAGER_REAL_SING_BOX")
    if configured is None:
        pytest.skip("set SB_MANAGER_REAL_SING_BOX to run real sing-box integration checks")
    binary = Path(configured)
    if not binary.is_file():
        pytest.fail(f"SB_MANAGER_REAL_SING_BOX is not a file: {binary}")
    return binary


@pytest.mark.integration
@pytest.mark.parametrize(
    ("protocol", "transport"),
    (
        (ProtocolKind.VLESS_REALITY, None),
        (ProtocolKind.SHADOWSOCKS, None),
        (ProtocolKind.HYSTERIA2, None),
        (ProtocolKind.TROJAN, None),
        (ProtocolKind.ANYTLS, None),
        (ProtocolKind.TUIC, None),
        (ProtocolKind.VLESS_TLS, WebSocketTransportIntent(path="/vless")),
        (ProtocolKind.VLESS_TLS, GrpcTransportIntent(service_name="vless-grpc")),
        (ProtocolKind.VMESS_TLS, WebSocketTransportIntent(path="/vmess")),
        (ProtocolKind.VMESS_TLS, GrpcTransportIntent(service_name="vmess-grpc")),
    ),
    ids=(
        "vless-reality",
        "shadowsocks-2022",
        "hysteria2",
        "trojan",
        "anytls",
        "tuic",
        "vless-websocket",
        "vless-grpc",
        "vmess-websocket",
        "vmess-grpc",
    ),
)
def test_real_sing_box_accepts_product_generated_configuration(
    real_sing_box_binary: Path,
    tmp_path: Path,
    protocol: ProtocolKind,
    transport: TransportIntent | None,
) -> None:
    tls_intent = (
        None
        if protocol in {ProtocolKind.VLESS_REALITY, ProtocolKind.SHADOWSOCKS}
        else AcmeTlsIntent(
            server_name="proxy.example.com",
            email="operator@example.com",
            data_directory=Path("/var/lib/sing-box-manager/acme"),
        )
    )
    materialized = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    ).materialize(
        ManagedProfile(
            profile_name="release-fixture",
            protocol=protocol,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="profile-1",
            tls_intent=tls_intent,
            transport_intent=transport,
        ),
        listen_port=18443,
    )
    document: dict[str, object] = {
        "inbounds": [materialized.inbound],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    if materialized.certificate_providers:
        document["certificate_providers"] = list(materialized.certificate_providers)
    ManagedConfigurationPolicy().validate(document)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

    assert result.valid, result.diagnostics
