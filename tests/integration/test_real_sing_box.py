import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from sb_manager.adapters.generated_configuration import ProjectedGeneratedConfigurationInspector
from sb_manager.adapters.sing_box_core_status import SingBoxCoreStatusInspector
from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.application.configuration_projection import ManagedConfigurationProjector
from sb_manager.application.protocol_compatibility import (
    ProtocolCompatibilityPolicy,
    ProtocolUnsupportedByCore,
)
from sb_manager.cli import create_protocol_catalog
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.privileged.config_policy import ManagedConfigurationPolicy
from sb_manager.protocols.catalog import ProtocolCatalog
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent
from sb_manager.transactions.staging import ConfigurationStager
from sb_manager.transports.catalog import (
    GrpcTransportIntent,
    TransportIntent,
    WebSocketTransportIntent,
)


@pytest.mark.integration
def test_generated_configuration_inspector_uses_real_sing_box_check(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    catalog = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    )
    inspector = ProjectedGeneratedConfigurationInspector(
        projector=ManagedConfigurationProjector(protocol_catalog=catalog),
        stager=ConfigurationStager(parent=tmp_path),
        validator=SingBoxConfigValidator(binary=real_sing_box_binary),
    )

    observation = inspector.inspect(ManagedInstallation(schema_version=1, revision=0, profiles=()))

    assert observation.valid is True
    assert observation.diagnostics == "sing-box check completed successfully"


@pytest.fixture(scope="session")
def real_sing_box_binary() -> Path:
    configured = os.environ.get("SB_MANAGER_REAL_SING_BOX")
    if configured is None:
        pytest.skip("set SB_MANAGER_REAL_SING_BOX to run real sing-box integration checks")
    binary = Path(configured)
    if not binary.is_file():
        pytest.fail(f"SB_MANAGER_REAL_SING_BOX is not a file: {binary}")
    return binary


def _materialize_snell_v6_document(real_sing_box_binary: Path) -> dict[str, object]:
    materialized = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    ).materialize(
        ManagedProfile(
            profile_name="official-snell-v6-fixture",
            protocol=ProtocolKind.SNELL_V6,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="profile-1",
            server_address="proxy.example.com",
        ),
        listen_port=18443,
    )
    return {
        "inbounds": [materialized.inbound],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }


def _write_json_document(path: Path, document: dict[str, object]) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _inspect_configured_core_version(real_sing_box_binary: Path) -> str:
    observation = SingBoxCoreStatusInspector(binary=real_sing_box_binary).inspect()
    if not observation.available or observation.version is None:
        pytest.fail(f"configured sing-box did not report an exact version: {real_sing_box_binary}")
    return observation.version


@pytest.mark.integration
def test_capable_real_sing_box_accepts_generated_snell_v6_configuration(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    core_version = _inspect_configured_core_version(real_sing_box_binary)
    compatibility = ProtocolCompatibilityPolicy()
    if not compatibility.supports(ProtocolKind.SNELL_V6, core_version):
        pytest.skip(f"configured core {core_version} predates Snell v6 support")
    compatibility.require_supported(ProtocolKind.SNELL_V6, core_version)

    document = _materialize_snell_v6_document(real_sing_box_binary)
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    assert len(inbounds) == 1
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    psk = inbound["psk"]
    assert isinstance(psk, str)
    assert inbound == {
        "type": "snell",
        "tag": "profile-1",
        "listen": "::",
        "listen_port": 18443,
        "version": 6,
        "psk": psk,
        "mode": "default",
    }
    assert document["outbounds"] == [{"type": "direct", "tag": "direct"}]
    ManagedConfigurationPolicy().validate(document)
    config_path = _write_json_document(tmp_path / "snell-v6.json", document)

    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

    assert result.valid
    if psk in result.diagnostics:
        pytest.fail("sing-box check diagnostics disclosed the generated Snell PSK")


@pytest.mark.integration
def test_legacy_real_sing_box_rejects_snell_v6_before_configuration(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    core_version = _inspect_configured_core_version(real_sing_box_binary)
    compatibility = ProtocolCompatibilityPolicy()
    if compatibility.supports(ProtocolKind.SNELL_V6, core_version):
        pytest.skip(f"configured core {core_version} already supports Snell v6")

    with pytest.raises(ProtocolUnsupportedByCore) as caught:
        compatibility.require_supported(ProtocolKind.SNELL_V6, core_version)

    assert caught.value.protocol is ProtocolKind.SNELL_V6
    assert caught.value.observed_version == core_version
    assert tuple(tmp_path.iterdir()) == ()


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


@pytest.mark.integration
def test_real_sing_box_accepts_trusted_operator_tls_files(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    fixture_directory = Path(__file__).parents[1] / "fixtures/tls"
    trusted_tls_directory = tmp_path / "trusted-tls"
    trusted_tls_directory.mkdir()
    certificate = trusted_tls_directory / "server.crt"
    key = trusted_tls_directory / "server.key"
    shutil.copyfile(fixture_directory / "server.crt", certificate)
    shutil.copyfile(fixture_directory / "server.key", key)
    certificate.chmod(0o644)
    key.chmod(0o600)
    materialized = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    ).materialize(
        ManagedProfile(
            profile_name="operator-tls-fixture",
            protocol=ProtocolKind.TROJAN,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="profile-1",
            tls_intent=OperatorFileTlsIntent(
                server_name="proxy.example.com",
                certificate_path=certificate,
                key_path=key,
            ),
        ),
        listen_port=18443,
    )
    document: dict[str, object] = {
        "inbounds": [materialized.inbound],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    ManagedConfigurationPolicy(
        trusted_tls_directory=trusted_tls_directory,
        expected_root_uid=os.geteuid(),
    ).validate(document)
    config_path = tmp_path / "operator-tls.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

    assert result.valid, result.diagnostics


@pytest.mark.integration
def test_real_sing_box_accepts_configuration_after_final_profile_removal(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    document = ManagedConfigurationProjector(protocol_catalog=ProtocolCatalog(())).project(())
    config_path = tmp_path / "no-profiles.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

    assert result.valid, result.diagnostics
    ManagedConfigurationPolicy().validate(document)


@pytest.mark.integration
def test_real_sing_box_accepts_paused_and_resumed_profile_projections(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    catalog = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    )
    materialized = catalog.materialize(
        ManagedProfile(
            profile_name="availability-fixture",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="profile-1",
        ),
        listen_port=18443,
    )
    projector = ManagedConfigurationProjector(protocol_catalog=catalog)
    projections = {
        "paused": projector.project((replace(materialized.profile, enabled=False),)),
        "resumed": projector.project((materialized.profile,)),
    }

    for availability, document in projections.items():
        config_path = tmp_path / f"{availability}-profile.json"
        config_path.write_text(json.dumps(document), encoding="utf-8")

        result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

        assert result.valid, result.diagnostics
        ManagedConfigurationPolicy().validate(document)

    assert projections["paused"]["inbounds"] == []
    resumed_inbounds = projections["resumed"]["inbounds"]
    assert isinstance(resumed_inbounds, list)
    assert resumed_inbounds[0]["tag"] == "profile-1"


@pytest.mark.integration
def test_real_sing_box_accepts_reprojected_applied_profile_edit(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    edited_port = 19443
    catalog = create_protocol_catalog(
        sing_box_binary=real_sing_box_binary,
        reality_server_name="www.cloudflare.com",
    )
    materialized = catalog.materialize(
        ManagedProfile(
            profile_name="旧名称",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="profile-1",
            server_address="proxy.example.com",
        ),
        listen_port=18443,
    )
    edited = replace(materialized.profile, profile_name="新名称", listen_port=edited_port)
    document = ManagedConfigurationProjector(protocol_catalog=catalog).project((edited,))
    config_path = tmp_path / "edited-profile.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

    assert result.valid, result.diagnostics
    ManagedConfigurationPolicy().validate(document)
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    assert inbound["listen_port"] == edited_port
    users = inbound["users"]
    assert isinstance(users, list)
    assert users[0]["name"] == "新名称"
