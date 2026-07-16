from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.profile_apply import (
    ApplyConfirmationRequiredError,
    ApplyProfileRequest,
    ProfileApplyService,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import Hysteria2Material
from sb_manager.protocols.catalog import (
    Hysteria2Handler,
    ProfileConnectionInfo,
    ProtocolCatalog,
    RealityHandler,
)
from sb_manager.protocols.reality import RealityMaterial
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.tls.catalog import AcmeTlsHandler, AcmeTlsIntent, TlsCatalog
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
)

FIXED_LISTEN_PORT = 4433
EXPECTED_COMMITTED_REVISION = 2
EXPECTED_SECOND_PROFILE_REVISION = 3


class TrackingApplyLock:
    def __init__(self) -> None:
        self.acquisitions = 0

    @contextmanager
    def acquire(self) -> Iterator[None]:
        self.acquisitions += 1
        yield


class FixedRealityMaterialSource:
    def generate(self) -> RealityMaterial:
        return RealityMaterial(
            user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
            private_key="private-key-value",
            public_key="public-key-value",
            short_id="0123456789abcdef",
            server_name="www.cloudflare.com",
        )


class FixedHysteria2MaterialSource:
    def generate(self) -> Hysteria2Material:
        return Hysteria2Material(password="hy2-password")


def reality_catalog() -> ProtocolCatalog:
    return ProtocolCatalog((RealityHandler(material_source=FixedRealityMaterialSource()),))


def hysteria2_catalog() -> ProtocolCatalog:
    return ProtocolCatalog(
        (
            Hysteria2Handler(
                material_source=FixedHysteria2MaterialSource(),
                tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
            ),
        )
    )


class FixedPortSource:
    def is_available(self, port: int) -> bool:
        assert port == FIXED_LISTEN_PORT
        return True

    def choose_available(self) -> int:
        raise AssertionError("a fixed port must not request an automatic port")


class RecordingSuccessfulApplier:
    def __init__(self) -> None:
        self.document: Mapping[str, object] | None = None

    def apply(self, document: Mapping[str, object]) -> ApplyTransactionResult:
        self.document = document
        return ApplyTransactionResult(
            outcome=ApplyOutcome.APPLIED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
            postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
            rollback=None,
        )


def test_confirmed_reality_draft_is_applied_and_committed_to_desired_state() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=FIXED_LISTEN_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    )
    applier = RecordingSuccessfulApplier()
    apply_lock = TrackingApplyLock()
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=reality_catalog(),
        port_source=FixedPortSource(),
        applier=applier,
        apply_lock=apply_lock,
    )

    result = service.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_COMMITTED_REVISION
    assert apply_lock.acquisitions == 1
    assert result.transaction.outcome is ApplyOutcome.APPLIED
    assert result.connection_info == ProfileConnectionInfo(
        server_address="vpn.example.com",
        server_port=FIXED_LISTEN_PORT,
        share_uri=(
            "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
            "?encryption=none&flow=xtls-rprx-vision&security=reality"
            "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
            "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
        ),
    )
    assert applier.document == {
        "inbounds": [
            {
                "type": "vless",
                "tag": "profile-1",
                "listen": "::",
                "listen_port": FIXED_LISTEN_PORT,
                "users": [
                    {
                        "name": "手机",
                        "uuid": "bf000d23-0752-40b4-affe-68f7707a9661",
                        "flow": "xtls-rprx-vision",
                    }
                ],
                "tls": {
                    "enabled": True,
                    "server_name": "www.cloudflare.com",
                    "reality": {
                        "enabled": True,
                        "handshake": {
                            "server": "www.cloudflare.com",
                            "server_port": 443,
                        },
                        "private_key": "private-key-value",
                        "short_id": ["0123456789abcdef"],
                    },
                },
            }
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    assert state_store.load() == ManagedInstallation(
        schema_version=1,
        revision=EXPECTED_COMMITTED_REVISION,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=FIXED_LISTEN_PORT,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=FixedRealityMaterialSource().generate(),
                server_address="vpn.example.com",
            ),
        ),
    )


def test_unconfirmed_profile_apply_is_rejected_before_external_effects() -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=FIXED_LISTEN_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    initial = ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    applier = RecordingSuccessfulApplier()
    apply_lock = TrackingApplyLock()
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=reality_catalog(),
        port_source=FixedPortSource(),
        applier=applier,
        apply_lock=apply_lock,
    )

    with pytest.raises(ApplyConfirmationRequiredError):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id="profile-1",
                expected_revision=1,
                confirmed=False,
            )
        )

    assert applier.document is None
    assert apply_lock.acquisitions == 0
    assert state_store.load() == initial


def test_applying_a_second_profile_preserves_existing_applied_inbounds() -> None:
    existing_material = RealityMaterial(
        user_uuid="749b1cc8-3f43-4fc6-9c3a-32fc67d83c3d",
        private_key="existing-private-key",
        public_key="existing-public-key",
        short_id="fedcba9876543210",
        server_name="www.example.org",
    )
    existing = ManagedProfile(
        profile_id="profile-1",
        profile_name="平板",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        protocol_material=existing_material,
    )
    candidate = ManagedProfile(
        profile_id="profile-2",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=FIXED_LISTEN_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=2,
            profiles=(existing, candidate),
        )
    )
    applier = RecordingSuccessfulApplier()
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=reality_catalog(),
        port_source=FixedPortSource(),
        applier=applier,
        apply_lock=TrackingApplyLock(),
    )

    result = service.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-2",
            expected_revision=2,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_SECOND_PROFILE_REVISION
    assert applier.document is not None
    inbounds = applier.document["inbounds"]
    assert isinstance(inbounds, list)
    assert [inbound["tag"] for inbound in inbounds] == ["profile-1", "profile-2"]
    assert inbounds[0]["users"][0]["uuid"] == existing_material.user_uuid
    assert state_store.load().profiles[0] == existing
    assert state_store.load().profiles[1].status is ProfileStatus.APPLIED


def test_hysteria2_apply_includes_top_level_certificate_providers(tmp_path: Path) -> None:
    profile = ManagedProfile(
        profile_id="profile-3",
        profile_name="移动网络",
        protocol=ProtocolKind.HYSTERIA2,
        listen_port=FIXED_LISTEN_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=1, profiles=(profile,))
    )
    applier = RecordingSuccessfulApplier()
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=hysteria2_catalog(),
        port_source=FixedPortSource(),
        applier=applier,
        apply_lock=TrackingApplyLock(),
    )

    service.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-3",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert applier.document is not None
    assert applier.document["certificate_providers"] == [
        {
            "type": "acme",
            "tag": "tls-profile-3",
            "domain": ["vpn.example.com"],
            "email": "operator@example.com",
            "data_directory": str(tmp_path / "acme"),
            "key_type": "p256",
        }
    ]
