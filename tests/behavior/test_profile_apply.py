from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.profile_apply import (
    ApplyConfirmationRequiredError,
    ApplyProfileRequest,
    ProfileApplyPlan,
    ProfileApplyService,
    ProfileMaterializationError,
)
from sb_manager.application.protocol_compatibility import (
    ActiveCoreProtocolCompatibility,
    CoreVersionChanged,
    CoreVersionUnknown,
    ProtocolUnsupportedByCore,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import Hysteria2Material, SnellV6Material
from sb_manager.protocols.catalog import (
    ConnectionPayload,
    ConnectionPayloadKind,
    Hysteria2Handler,
    ProfileConnectionInfo,
    ProtocolCatalog,
    RealityHandler,
    SnellV6Handler,
)
from sb_manager.protocols.reality import RealityMaterial
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.core_status import CoreStatusObservation
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.tls.catalog import (
    AcmeTlsHandler,
    AcmeTlsIntent,
    OperatorFileTlsHandler,
    OperatorFileTlsIntent,
    TlsCatalog,
)
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import configuration_sha256

FIXED_LISTEN_PORT = 4433
EXPECTED_COMMITTED_REVISION = 2
EXPECTED_SECOND_PROFILE_REVISION = 3
EXPECTED_CORE_INSPECTIONS = 2


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


class RecordingSnellV6MaterialSource:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self) -> SnellV6Material:
        self.calls += 1
        return SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8")


class RecordingRealityMaterialSource:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self) -> RealityMaterial:
        self.calls += 1
        return FixedRealityMaterialSource().generate()


class SequenceCoreStatusInspector:
    def __init__(self, *versions: str) -> None:
        self._versions = iter(versions)
        self.calls = 0

    def inspect(self) -> CoreStatusObservation:
        self.calls += 1
        version = next(self._versions)
        return CoreStatusObservation(
            available=True,
            version=version,
            diagnostics=f"sing-box version {version}",
        )


class RecordingAutomaticPortSource:
    def __init__(self) -> None:
        self.calls = 0

    def is_available(self, port: int) -> bool:
        raise AssertionError("automatic Snell apply must choose a port")

    def choose_available(self) -> int:
        self.calls += 1
        return 18443


class PortSourceThatMustNotBeCalled:
    def is_available(self, port: int) -> bool:
        raise AssertionError("compatibility must be checked before fixed-port inspection")

    def choose_available(self) -> int:
        raise AssertionError("compatibility must be checked before automatic port selection")


class ApplierThatMustNotBeCalled:
    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition | None = None,
    ) -> ApplyTransactionResult:
        raise AssertionError("compatibility must be checked before host apply")


def snell_draft() -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-7",
        profile_name="Snell preview",
        protocol=ProtocolKind.SNELL_V6,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.DRAFT,
        server_address="proxy.example.com",
    )


def active_snell_profile() -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-snell",
        profile_name="Active Snell preview",
        protocol=ProtocolKind.SNELL_V6,
        listen_port=18443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=True,
        protocol_material=SnellV6Material(psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"),
    )


def reality_draft() -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-reality",
        profile_name="Reality draft",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.DRAFT,
        server_address="proxy.example.com",
    )


def snell_catalog(source: RecordingSnellV6MaterialSource) -> ProtocolCatalog:
    return ProtocolCatalog((SnellV6Handler(material_source=source),))


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


def hysteria2_catalog_with_file_tls() -> ProtocolCatalog:
    return ProtocolCatalog(
        (
            Hysteria2Handler(
                material_source=FixedHysteria2MaterialSource(),
                tls_catalog=TlsCatalog((AcmeTlsHandler(), OperatorFileTlsHandler())),
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
        self.precondition: ConfigTargetPrecondition | None = None

    def apply(
        self,
        document: Mapping[str, object],
        *,
        precondition: ConfigTargetPrecondition | None = None,
    ) -> ApplyTransactionResult:
        self.document = document
        self.precondition = precondition
        return ApplyTransactionResult(
            outcome=ApplyOutcome.APPLIED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
            postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
            rollback=None,
        )


def test_snell_apply_rechecks_active_core_before_material_or_host_mutation() -> None:
    draft = snell_draft()
    initial = ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    material_source = RecordingSnellV6MaterialSource()
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.13.14")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=snell_catalog(material_source),
        port_source=PortSourceThatMustNotBeCalled(),
        applier=ApplierThatMustNotBeCalled(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    plan = service.plan_profile("profile-7")

    assert plan == ProfileApplyPlan(
        profile_id="profile-7",
        profile_name="Snell preview",
        expected_revision=1,
        observed_core_version="1.14.0-alpha.47",
    )
    with pytest.raises(ProtocolUnsupportedByCore):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id=plan.profile_id,
                expected_revision=plan.expected_revision,
                expected_core_version=plan.observed_core_version,
                confirmed=True,
            )
        )

    assert inspector.calls == EXPECTED_CORE_INSPECTIONS
    assert material_source.calls == 0
    assert state_store.load() == initial


def test_snell_apply_succeeds_when_confirmation_observes_matching_preview() -> None:
    draft = snell_draft()
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    )
    material_source = RecordingSnellV6MaterialSource()
    port_source = RecordingAutomaticPortSource()
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.47")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=snell_catalog(material_source),
        port_source=port_source,
        applier=RecordingSuccessfulApplier(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    plan = service.plan_profile("profile-7")

    result = service.apply_profile(
        ApplyProfileRequest(
            profile_id=plan.profile_id,
            expected_revision=plan.expected_revision,
            expected_core_version=plan.observed_core_version,
            confirmed=True,
        )
    )

    assert result.committed_revision == EXPECTED_COMMITTED_REVISION
    assert material_source.calls == 1
    assert port_source.calls == 1
    assert state_store.load().profiles[0].status is ProfileStatus.APPLIED


def test_snell_apply_rejects_supported_preview_version_race_before_mutation() -> None:
    draft = snell_draft()
    initial = ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    material_source = RecordingSnellV6MaterialSource()
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.48")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=snell_catalog(material_source),
        port_source=PortSourceThatMustNotBeCalled(),
        applier=ApplierThatMustNotBeCalled(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    plan = service.plan_profile("profile-7")

    with pytest.raises(CoreVersionChanged):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id=plan.profile_id,
                expected_revision=plan.expected_revision,
                expected_core_version=plan.observed_core_version,
                confirmed=True,
            )
        )

    assert material_source.calls == 0
    assert state_store.load() == initial


def test_snell_apply_requires_planned_core_version_evidence() -> None:
    draft = snell_draft()
    initial = ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    material_source = RecordingSnellV6MaterialSource()
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=snell_catalog(material_source),
        port_source=PortSourceThatMustNotBeCalled(),
        applier=ApplierThatMustNotBeCalled(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    with pytest.raises(CoreVersionUnknown):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id=draft.profile_id,
                expected_revision=initial.revision,
                confirmed=True,
            )
        )

    assert inspector.calls == 0
    assert material_source.calls == 0
    assert state_store.load() == initial


def test_reality_apply_plan_rejects_stable_core_when_active_snell_is_retained() -> None:
    draft = reality_draft()
    initial = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(active_snell_profile(), draft),
    )
    state_store = MemoryStateStore(initial)
    material_source = RecordingRealityMaterialSource()
    inspector = SequenceCoreStatusInspector("1.13.14")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RealityHandler(material_source=material_source),)),
        port_source=PortSourceThatMustNotBeCalled(),
        applier=ApplierThatMustNotBeCalled(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )

    with pytest.raises(ProtocolUnsupportedByCore):
        service.plan_profile(draft.profile_id)

    assert inspector.calls == 1
    assert material_source.calls == 0
    assert state_store.load() == initial


def test_reality_apply_rechecks_retained_snell_before_material_or_host_mutation() -> None:
    draft = reality_draft()
    initial = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(active_snell_profile(), draft),
    )
    state_store = MemoryStateStore(initial)
    material_source = RecordingRealityMaterialSource()
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.13.14")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RealityHandler(material_source=material_source),)),
        port_source=PortSourceThatMustNotBeCalled(),
        applier=ApplierThatMustNotBeCalled(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    plan = service.plan_profile(draft.profile_id)

    with pytest.raises(ProtocolUnsupportedByCore):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id=plan.profile_id,
                expected_revision=plan.expected_revision,
                confirmed=True,
                expected_core_version=plan.observed_core_version,
            )
        )

    assert inspector.calls == EXPECTED_CORE_INSPECTIONS
    assert material_source.calls == 0
    assert state_store.load() == initial


def test_reality_apply_rejects_retained_snell_supported_version_race() -> None:
    draft = reality_draft()
    initial = ManagedInstallation(
        schema_version=1,
        revision=1,
        profiles=(active_snell_profile(), draft),
    )
    state_store = MemoryStateStore(initial)
    material_source = RecordingRealityMaterialSource()
    inspector = SequenceCoreStatusInspector("1.14.0-alpha.47", "1.14.0-alpha.48")
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog((RealityHandler(material_source=material_source),)),
        port_source=PortSourceThatMustNotBeCalled(),
        applier=ApplierThatMustNotBeCalled(),
        apply_lock=TrackingApplyLock(),
        core_compatibility=ActiveCoreProtocolCompatibility(inspector=inspector),
    )
    plan = service.plan_profile(draft.profile_id)

    with pytest.raises(CoreVersionChanged):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id=plan.profile_id,
                expected_revision=plan.expected_revision,
                confirmed=True,
                expected_core_version=plan.observed_core_version,
            )
        )

    assert inspector.calls == EXPECTED_CORE_INSPECTIONS
    assert material_source.calls == 0
    assert state_store.load() == initial


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
        payload=ConnectionPayload(
            kind=ConnectionPayloadKind.URI,
            content=(
                "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
                "?encryption=none&flow=xtls-rprx-vision&security=reality"
                "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
                "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
            ),
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
    assert applier.precondition == ConfigTargetPrecondition.absent()
    assert applier.document is not None
    committed_config_sha256 = configuration_sha256(applier.document)
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
        expected_config_sha256=committed_config_sha256,
    )


def test_apply_requires_the_live_configuration_fingerprint_recorded_in_desired_state() -> None:
    reviewed_config_sha256 = "a" * 64
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=FIXED_LISTEN_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=1,
            profiles=(draft,),
            expected_config_sha256=reviewed_config_sha256,
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

    service.apply_profile(
        ApplyProfileRequest(
            profile_id="profile-1",
            expected_revision=1,
            confirmed=True,
        )
    )

    assert applier.precondition == ConfigTargetPrecondition.matching_sha256(reviewed_config_sha256)
    assert applier.document is not None
    assert state_store.load().expected_config_sha256 == configuration_sha256(applier.document)


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


def test_missing_operator_tls_files_are_an_actionable_apply_error(tmp_path: Path) -> None:
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="已有证书",
        protocol=ProtocolKind.HYSTERIA2,
        listen_port=FIXED_LISTEN_PORT,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        tls_intent=OperatorFileTlsIntent(
            server_name="vpn.example.com",
            certificate_path=tmp_path / "missing.crt",
            key_path=tmp_path / "missing.key",
        ),
    )
    initial = ManagedInstallation(schema_version=1, revision=1, profiles=(draft,))
    state_store = MemoryStateStore(initial)
    applier = RecordingSuccessfulApplier()
    service = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=hysteria2_catalog_with_file_tls(),
        port_source=FixedPortSource(),
        applier=applier,
        apply_lock=TrackingApplyLock(),
    )

    with pytest.raises(ProfileMaterializationError, match="TLS certificate file is unavailable"):
        service.apply_profile(
            ApplyProfileRequest(
                profile_id="profile-1",
                expected_revision=1,
                confirmed=True,
            )
        )

    assert applier.document is None
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


def test_hysteria2_apply_uses_inline_acme_compatible_with_both_channels(tmp_path: Path) -> None:
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
    assert "certificate_providers" not in applier.document
    inbounds = applier.document["inbounds"]
    assert isinstance(inbounds, list)
    inbound = inbounds[0]
    assert isinstance(inbound, dict)
    assert inbound["tls"] == {
        "enabled": True,
        "server_name": "vpn.example.com",
        "acme": {
            "domain": ["vpn.example.com"],
            "email": "operator@example.com",
            "data_directory": str(tmp_path / "acme"),
        },
    }
