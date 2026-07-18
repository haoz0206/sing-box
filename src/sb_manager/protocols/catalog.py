"""Deep protocol catalog for materialization and artifact generation."""

from collections.abc import Iterable
from dataclasses import dataclass, replace
from enum import Enum
from typing import Protocol

from sb_manager.domain.installation import ManagedProfile, ProfileStatus, ProtocolKind
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    Hysteria2Material,
    RealityMaterial,
    ShadowsocksMaterial,
    SnellV6Material,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.protocols.anytls import (
    AnyTlsConnectionSpec,
    AnyTlsInboundSpec,
    AnyTlsProtocol,
)
from sb_manager.protocols.hysteria2 import (
    Hysteria2ConnectionSpec,
    Hysteria2InboundSpec,
    Hysteria2Protocol,
)
from sb_manager.protocols.reality import (
    RealityConnectionSpec,
    RealityInboundSpec,
    RealityProtocol,
)
from sb_manager.protocols.shadowsocks import (
    ShadowsocksConnectionSpec,
    ShadowsocksInboundSpec,
    ShadowsocksProtocol,
)
from sb_manager.protocols.snell import (
    SnellV6ConnectionSpec,
    SnellV6InboundSpec,
    SnellV6Protocol,
)
from sb_manager.protocols.trojan import (
    TrojanConnectionSpec,
    TrojanInboundSpec,
    TrojanProtocol,
)
from sb_manager.protocols.tuic import TuicConnectionSpec, TuicInboundSpec, TuicProtocol
from sb_manager.protocols.vless_tls import (
    VlessTlsConnectionSpec,
    VlessTlsInboundSpec,
    VlessTlsProtocol,
)
from sb_manager.protocols.vmess_tls import (
    VmessTlsConnectionSpec,
    VmessTlsInboundSpec,
    VmessTlsProtocol,
)
from sb_manager.seams.anytls_material import AnyTlsMaterialSource
from sb_manager.seams.hysteria2_material import Hysteria2MaterialSource
from sb_manager.seams.reality_material import RealityMaterialSource
from sb_manager.seams.shadowsocks_material import ShadowsocksMaterialSource
from sb_manager.seams.snell_material import SnellV6MaterialSource
from sb_manager.seams.trojan_material import TrojanMaterialSource
from sb_manager.seams.tuic_material import TuicMaterialSource
from sb_manager.seams.vless_material import VlessMaterialSource
from sb_manager.seams.vmess_material import VmessMaterialSource
from sb_manager.tls.catalog import TlsCatalog
from sb_manager.transports.catalog import TransportCatalog


class UnsupportedProtocolError(ValueError):
    """No catalog handler owns the requested protocol kind."""


class ProtocolMaterialMismatchError(ValueError):
    """Persisted material does not belong to the profile's protocol kind."""


class IncompleteAppliedProfileError(ValueError):
    """An applied profile is missing material required to rebuild its inbound."""


class ConnectionPayloadKind(str, Enum):
    URI = "uri"
    SURGE_POLICY = "surge-policy"


@dataclass(frozen=True, slots=True)
class ConnectionPayload:
    kind: ConnectionPayloadKind
    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ConnectionPayloadKind):
            raise ValueError("Unsupported connection payload kind")
        if not self.content:
            raise ValueError("Connection payload cannot be empty")


@dataclass(frozen=True, slots=True)
class ProfileConnectionInfo:
    """Protocol-neutral connection information consumed by application and UI."""

    server_address: str
    server_port: int
    payload: ConnectionPayload


@dataclass(frozen=True, slots=True)
class MaterializedProfile:
    """Consistent desired state, inbound, and optional client information."""

    profile: ManagedProfile
    inbound: dict[str, object]
    connection_info: ProfileConnectionInfo | None
    certificate_providers: tuple[dict[str, object], ...] = ()


class ProtocolHandler(Protocol):
    """Internal adapter interface selected by the catalog."""

    kind: ProtocolKind

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile: ...


class ProtocolCatalog:
    """Hide protocol selection and materialization behind one operation."""

    def __init__(self, handlers: Iterable[ProtocolHandler]) -> None:
        self._handlers = {handler.kind: handler for handler in handlers}

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        try:
            handler = self._handlers[profile.protocol]
        except KeyError as error:
            raise UnsupportedProtocolError(profile.protocol.value) from error
        return handler.materialize(profile, listen_port)


class RealityHandler:
    """Own Reality material, inbound, and connection behavior."""

    kind = ProtocolKind.VLESS_REALITY

    def __init__(self, *, material_source: RealityMaterialSource) -> None:
        self._material_source = material_source

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, RealityMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)

        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = RealityProtocol()
        inbound = protocol.build_inbound(
            RealityInboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                user_uuid=material.user_uuid,
                server_name=material.server_name,
                private_key=material.private_key,
                short_id=material.short_id,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                RealityConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    user_uuid=material.user_uuid,
                    server_name=material.server_name,
                    public_key=material.public_key,
                    short_id=material.short_id,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
        )


class Hysteria2Handler:
    """Own Hysteria2 material, TLS, inbound, and connection behavior."""

    kind = ProtocolKind.HYSTERIA2

    def __init__(
        self,
        *,
        material_source: Hysteria2MaterialSource,
        tls_catalog: TlsCatalog,
    ) -> None:
        self._material_source = material_source
        self._tls_catalog = tls_catalog

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, Hysteria2Material):
            raise ProtocolMaterialMismatchError(profile.profile_id)
        if profile.tls_intent is None:
            raise IncompleteAppliedProfileError(f"{profile.profile_id}: TLS intent")

        tls = self._tls_catalog.materialize(
            profile.tls_intent,
            tag=f"tls-{profile.profile_id}",
        )
        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = Hysteria2Protocol()
        inbound = protocol.build_inbound(
            Hysteria2InboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                password=material.password,
                tls=tls.server,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                Hysteria2ConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    password=material.password,
                    tls=tls.client,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
            certificate_providers=tls.certificate_providers,
        )


class TrojanHandler:
    """Own Trojan material, TLS, inbound, and connection behavior."""

    kind = ProtocolKind.TROJAN

    def __init__(
        self,
        *,
        material_source: TrojanMaterialSource,
        tls_catalog: TlsCatalog,
    ) -> None:
        self._material_source = material_source
        self._tls_catalog = tls_catalog

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, TrojanMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)
        if profile.tls_intent is None:
            raise IncompleteAppliedProfileError(f"{profile.profile_id}: TLS intent")

        tls = self._tls_catalog.materialize(
            profile.tls_intent,
            tag=f"tls-{profile.profile_id}",
        )
        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = TrojanProtocol()
        inbound = protocol.build_inbound(
            TrojanInboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                password=material.password,
                tls=tls.server,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                TrojanConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    password=material.password,
                    tls=tls.client,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
            certificate_providers=tls.certificate_providers,
        )


class AnyTlsHandler:
    """Own AnyTLS material, TLS, inbound, and connection behavior."""

    kind = ProtocolKind.ANYTLS

    def __init__(
        self,
        *,
        material_source: AnyTlsMaterialSource,
        tls_catalog: TlsCatalog,
    ) -> None:
        self._material_source = material_source
        self._tls_catalog = tls_catalog

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, AnyTlsMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)
        if profile.tls_intent is None:
            raise IncompleteAppliedProfileError(f"{profile.profile_id}: TLS intent")

        tls = self._tls_catalog.materialize(
            profile.tls_intent,
            tag=f"tls-{profile.profile_id}",
        )
        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = AnyTlsProtocol()
        inbound = protocol.build_inbound(
            AnyTlsInboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                password=material.password,
                tls=tls.server,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                AnyTlsConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    password=material.password,
                    tls=tls.client,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
            certificate_providers=tls.certificate_providers,
        )


class TuicHandler:
    """Own TUIC material, TLS, inbound, and connection behavior."""

    kind = ProtocolKind.TUIC

    def __init__(self, *, material_source: TuicMaterialSource, tls_catalog: TlsCatalog) -> None:
        self._material_source = material_source
        self._tls_catalog = tls_catalog

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, TuicMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)
        if profile.tls_intent is None:
            raise IncompleteAppliedProfileError(f"{profile.profile_id}: TLS intent")

        tls = self._tls_catalog.materialize(
            profile.tls_intent,
            tag=f"tls-{profile.profile_id}",
        )
        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = TuicProtocol()
        inbound = protocol.build_inbound(
            TuicInboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                user_uuid=material.user_uuid,
                password=material.password,
                tls=tls.server,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                TuicConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    user_uuid=material.user_uuid,
                    password=material.password,
                    tls=tls.client,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
            certificate_providers=tls.certificate_providers,
        )


class VlessTlsHandler:
    """Own VLESS material, TLS, transport, and connection behavior."""

    kind = ProtocolKind.VLESS_TLS

    def __init__(
        self,
        *,
        material_source: VlessMaterialSource,
        tls_catalog: TlsCatalog,
        transport_catalog: TransportCatalog,
    ) -> None:
        self._material_source = material_source
        self._tls_catalog = tls_catalog
        self._transport_catalog = transport_catalog

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, VlessMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)
        if profile.tls_intent is None or profile.transport_intent is None:
            raise IncompleteAppliedProfileError(f"{profile.profile_id}: TLS/transport intent")

        tls = self._tls_catalog.materialize(
            profile.tls_intent,
            tag=f"tls-{profile.profile_id}",
        )
        transport = self._transport_catalog.materialize(profile.transport_intent)
        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = VlessTlsProtocol()
        inbound = protocol.build_inbound(
            VlessTlsInboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                user_uuid=material.user_uuid,
                tls=tls.server,
                transport=transport.server,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                VlessTlsConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    user_uuid=material.user_uuid,
                    tls=tls.client,
                    transport=transport.client,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
            certificate_providers=tls.certificate_providers,
        )


class VmessTlsHandler:
    """Own VMess material, TLS, transport, and connection behavior."""

    kind = ProtocolKind.VMESS_TLS

    def __init__(
        self,
        *,
        material_source: VmessMaterialSource,
        tls_catalog: TlsCatalog,
        transport_catalog: TransportCatalog,
    ) -> None:
        self._material_source = material_source
        self._tls_catalog = tls_catalog
        self._transport_catalog = transport_catalog

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, VmessMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)
        if profile.tls_intent is None or profile.transport_intent is None:
            raise IncompleteAppliedProfileError(f"{profile.profile_id}: TLS/transport intent")

        tls = self._tls_catalog.materialize(profile.tls_intent, tag=f"tls-{profile.profile_id}")
        transport = self._transport_catalog.materialize(profile.transport_intent)
        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = VmessTlsProtocol()
        inbound = protocol.build_inbound(
            VmessTlsInboundSpec(
                tag=profile.profile_id,
                profile_name=profile.profile_name,
                listen_port=listen_port,
                user_uuid=material.user_uuid,
                tls=tls.server,
                transport=transport.server,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                VmessTlsConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    user_uuid=material.user_uuid,
                    tls=tls.client,
                    transport=transport.client,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
            certificate_providers=tls.certificate_providers,
        )


class ShadowsocksHandler:
    """Own Shadowsocks material, inbound, and connection behavior."""

    kind = ProtocolKind.SHADOWSOCKS

    def __init__(self, *, material_source: ShadowsocksMaterialSource) -> None:
        self._material_source = material_source

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, ShadowsocksMaterial):
            raise ProtocolMaterialMismatchError(profile.profile_id)

        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = ShadowsocksProtocol()
        inbound = protocol.build_inbound(
            ShadowsocksInboundSpec(
                tag=profile.profile_id,
                listen_port=listen_port,
                password=material.password,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                ShadowsocksConnectionSpec(
                    profile_name=profile.profile_name,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    password=material.password,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.URI,
                    content=specific.share_uri,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
        )


class SnellV6Handler:
    """Own Snell v6 material, inbound, and Surge connection behavior."""

    kind = ProtocolKind.SNELL_V6

    def __init__(self, *, material_source: SnellV6MaterialSource) -> None:
        self._material_source = material_source

    def materialize(self, profile: ManagedProfile, listen_port: int) -> MaterializedProfile:
        material = profile.protocol_material
        if material is None:
            if profile.status is ProfileStatus.APPLIED:
                raise IncompleteAppliedProfileError(profile.profile_id)
            material = self._material_source.generate()
        if not isinstance(material, SnellV6Material):
            raise ProtocolMaterialMismatchError(profile.profile_id)

        applied_profile = replace(
            profile,
            listen_port=listen_port,
            status=ProfileStatus.APPLIED,
            protocol_material=material,
        )
        protocol = SnellV6Protocol()
        inbound = protocol.build_inbound(
            SnellV6InboundSpec(
                tag=profile.profile_id,
                listen_port=listen_port,
                psk=material.psk,
            )
        )
        connection_info = None
        if profile.server_address is not None:
            specific = protocol.build_connection_info(
                SnellV6ConnectionSpec(
                    profile_id=profile.profile_id,
                    server_address=profile.server_address,
                    server_port=listen_port,
                    psk=material.psk,
                )
            )
            connection_info = ProfileConnectionInfo(
                server_address=specific.server_address,
                server_port=specific.server_port,
                payload=ConnectionPayload(
                    kind=ConnectionPayloadKind.SURGE_POLICY,
                    content=specific.surge_policy,
                ),
            )
        return MaterializedProfile(
            profile=applied_profile,
            inbound=inbound,
            connection_info=connection_info,
        )
