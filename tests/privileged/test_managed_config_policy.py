import os
from copy import deepcopy
from pathlib import Path

import pytest

from sb_manager.cli import create_protocol_catalog
from sb_manager.domain.installation import (
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.privileged.config_policy import ManagedConfigurationPolicy
from sb_manager.privileged.errors import PrivilegedInputError
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent
from sb_manager.transports.catalog import GrpcTransportIntent, WebSocketTransportIntent

ACME_DIRECTORY = Path("/var/lib/sing-box-manager/acme")
GENERATED_SNELL_PSK_LENGTH = 43


def snell_document() -> dict[str, object]:
    return {
        "inbounds": [
            {
                "type": "snell",
                "tag": "profile-7",
                "listen": "::",
                "listen_port": 18443,
                "version": 6,
                "psk": "0123456789ab",
                "mode": "default",
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }


def write_fake_sing_box(tmp_path: Path) -> Path:
    binary = tmp_path / "sing-box"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "if sys.argv[1:3] == ['generate', 'reality-keypair']:\n"
        "    print('PrivateKey: private-key-value')\n"
        "    print('PublicKey: public-key-value')\n"
        "else:\n"
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def generated_document(  # noqa: PLR0913 - compact product-catalog fixture builder
    tmp_path: Path,
    protocol: ProtocolKind,
    *,
    transport: WebSocketTransportIntent | GrpcTransportIntent | None = None,
    tls_intent: AcmeTlsIntent | OperatorFileTlsIntent | None = None,
    profile_id: str = "profile-1",
    listen_port: int = 18443,
) -> dict[str, object]:
    if tls_intent is None and protocol not in {
        ProtocolKind.VLESS_REALITY,
        ProtocolKind.SHADOWSOCKS,
    }:
        tls_intent = AcmeTlsIntent(
            server_name="proxy.example.com",
            email="operator@example.com",
            data_directory=ACME_DIRECTORY,
        )
    catalog = create_protocol_catalog(
        sing_box_binary=write_fake_sing_box(tmp_path),
        reality_server_name="www.cloudflare.com",
    )
    profile = ManagedProfile(
        profile_id=profile_id,
        profile_name="安全入口",
        protocol=protocol,
        listen_port=listen_port,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        tls_intent=tls_intent,
        transport_intent=transport,
    )
    profile = catalog.prepare_draft(profile)
    materialized = catalog.materialize(
        profile,
        listen_port=listen_port,
    )
    document: dict[str, object] = {
        "inbounds": [materialized.inbound],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    if materialized.certificate_providers:
        document["certificate_providers"] = list(materialized.certificate_providers)
    return document


@pytest.mark.parametrize(
    ("protocol", "transport"),
    (
        (ProtocolKind.VLESS_REALITY, None),
        (ProtocolKind.SNELL_V6, None),
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
)
def test_every_product_generated_protocol_is_inside_privileged_policy(
    tmp_path: Path,
    protocol: ProtocolKind,
    transport: WebSocketTransportIntent | GrpcTransportIntent | None,
) -> None:
    document = generated_document(tmp_path, protocol, transport=transport)
    if protocol is ProtocolKind.SNELL_V6:
        inbounds = document["inbounds"]
        assert isinstance(inbounds, list)
        inbound = inbounds[0]
        assert isinstance(inbound, dict)
        psk = inbound["psk"]
        assert isinstance(psk, str)
        assert len(psk) == GENERATED_SNELL_PSK_LENGTH

    ManagedConfigurationPolicy().validate(document)


def test_bounded_snell_v6_is_inside_privileged_policy() -> None:
    ManagedConfigurationPolicy().validate(snell_document())


def test_snell_psk_accepts_the_maximum_ascii_length() -> None:
    document = snell_document()
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    inbound["psk"] = "a" * 255

    ManagedConfigurationPolicy().validate(document)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("version", 5),
        ("version", True),
        ("version", "6"),
        ("mode", "unshaped"),
        ("mode", "unsafe-raw"),
        ("mode", 6),
    ),
)
def test_snell_version_and_mode_are_exact(field: str, value: object) -> None:
    document = snell_document()
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    inbound[field] = value

    with pytest.raises(
        PrivilegedInputError,
        match=r"^Managed snell version or mode is invalid$",
    ):
        ManagedConfigurationPolicy().validate(document)


@pytest.mark.parametrize(
    ("field", "value", "missing"),
    (
        ("version", None, True),
        ("psk", None, True),
        ("mode", None, True),
        ("users", [], False),
        ("userkey", "unsafe", False),
        ("tls", {"enabled": True}, False),
        ("transport", {"type": "tcp"}, False),
        ("sniff", True, False),
    ),
)
def test_snell_fields_are_exact(field: str, value: object, missing: bool) -> None:
    document = snell_document()
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    if missing:
        inbound.pop(field)
    else:
        inbound[field] = value

    with pytest.raises(PrivilegedInputError, match="Managed snell inbound fields"):
        ManagedConfigurationPolicy().validate(document)


@pytest.mark.parametrize(
    ("psk", "message"),
    (
        ("a" * 11, "Managed snell psk length is invalid"),
        ("a" * 256, "Managed snell psk length is invalid"),
        ("密钥不应泄露", "Managed snell psk must be ASCII"),
        ("", "Managed snell psk length is invalid"),
        (None, "Managed snell psk length is invalid"),
        (123, "Managed snell psk length is invalid"),
    ),
)
def test_snell_psk_is_bounded_ascii_without_secret_disclosure(
    psk: object,
    message: str,
) -> None:
    document = snell_document()
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    inbound["psk"] = psk

    with pytest.raises(PrivilegedInputError) as captured:
        ManagedConfigurationPolicy().validate(document)

    assert str(captured.value) == message
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    if isinstance(psk, str) and psk:
        assert psk not in str(captured.value)


def test_unknown_top_level_capability_is_rejected(tmp_path: Path) -> None:
    document = generated_document(tmp_path, ProtocolKind.SHADOWSOCKS)
    document["log"] = {"output": "/root/leak.log"}

    with pytest.raises(PrivilegedInputError, match="top-level fields"):
        ManagedConfigurationPolicy().validate(document)


def test_multiple_profiles_with_inline_acme_are_allowed(tmp_path: Path) -> None:
    shadowsocks = generated_document(tmp_path, ProtocolKind.SHADOWSOCKS)
    hysteria2 = generated_document(
        tmp_path,
        ProtocolKind.HYSTERIA2,
        profile_id="profile-2",
        listen_port=18444,
    )
    shadow_inbounds = shadowsocks["inbounds"]
    hysteria_inbounds = hysteria2["inbounds"]
    assert isinstance(shadow_inbounds, list)
    assert isinstance(hysteria_inbounds, list)
    document: dict[str, object] = {
        "inbounds": [*shadow_inbounds, *hysteria_inbounds],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }

    ManagedConfigurationPolicy().validate(document)


def test_unknown_inbound_field_is_rejected(tmp_path: Path) -> None:
    document = generated_document(tmp_path, ProtocolKind.SHADOWSOCKS)
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    inbound["sniff"] = True

    with pytest.raises(PrivilegedInputError, match="shadowsocks inbound fields"):
        ManagedConfigurationPolicy().validate(document)


def test_inline_acme_cannot_select_a_root_write_directory(tmp_path: Path) -> None:
    document = generated_document(tmp_path, ProtocolKind.HYSTERIA2)
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    tls = inbound["tls"]
    assert isinstance(tls, dict)
    acme = tls["acme"]
    assert isinstance(acme, dict)
    acme["data_directory"] = "/root/.ssh"

    with pytest.raises(PrivilegedInputError, match="inline ACME data directory"):
        ManagedConfigurationPolicy().validate(document)


def test_inline_acme_domain_must_match_tls_server_name(tmp_path: Path) -> None:
    document = generated_document(tmp_path, ProtocolKind.TROJAN)
    inbounds = document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    tls = inbound["tls"]
    assert isinstance(tls, dict)
    acme = tls["acme"]
    assert isinstance(acme, dict)
    acme["domain"] = ["attacker.example.com"]

    with pytest.raises(PrivilegedInputError, match="inline ACME domain"):
        ManagedConfigurationPolicy().validate(document)


def test_operator_tls_files_must_be_real_root_owned_files_under_fixed_directory(
    tmp_path: Path,
) -> None:
    trusted_tls_directory = tmp_path / "trusted-tls"
    trusted_tls_directory.mkdir()
    certificate = trusted_tls_directory / "server.crt"
    key = trusted_tls_directory / "server.key"
    certificate.write_text("certificate", encoding="utf-8")
    key.write_text("key", encoding="utf-8")
    certificate.chmod(0o644)
    key.chmod(0o600)
    policy = ManagedConfigurationPolicy(
        trusted_tls_directory=trusted_tls_directory,
        expected_root_uid=os.geteuid(),
    )
    document = generated_document(
        tmp_path,
        ProtocolKind.TROJAN,
        tls_intent=OperatorFileTlsIntent(
            server_name="proxy.example.com",
            certificate_path=certificate,
            key_path=key,
        ),
    )

    policy.validate(document)

    outside_document = deepcopy(document)
    inbounds = outside_document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    tls = inbound["tls"]
    assert isinstance(tls, dict)
    tls["key_path"] = str(tmp_path / "outside.key")
    with pytest.raises(PrivilegedInputError, match="trusted TLS directory"):
        policy.validate(outside_document)

    key.unlink()
    outside = tmp_path / "outside.key"
    outside.write_text("key", encoding="utf-8")
    key.symlink_to(outside)
    with pytest.raises(PrivilegedInputError, match="symlink"):
        policy.validate(document)


def test_policy_accepts_no_inbounds_after_final_profile_removal() -> None:
    ManagedConfigurationPolicy().validate(
        {
            "inbounds": [],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
    )
