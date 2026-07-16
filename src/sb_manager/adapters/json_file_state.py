import json
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, TypedDict, cast

from sb_manager.domain.installation import (
    CURRENT_SCHEMA_VERSION,
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    Hysteria2Material,
    ProtocolMaterial,
    RealityMaterial,
    ShadowsocksMaterial,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.seams.state_store import UnsupportedStateSchemaError
from sb_manager.tls.catalog import (
    AcmeTlsIntent,
    OperatorFileTlsIntent,
    TlsIntent,
)
from sb_manager.transports.catalog import (
    GrpcTransportIntent,
    TransportIntent,
    WebSocketTransportIntent,
)


class RealityMaterialData(TypedDict):
    user_uuid: str
    private_key: str
    public_key: str
    short_id: str
    server_name: str


class TaggedRealityMaterialData(TypedDict):
    kind: Literal["vless-reality"]
    user_uuid: str
    private_key: str
    public_key: str
    short_id: str
    server_name: str


class TaggedShadowsocksMaterialData(TypedDict):
    kind: Literal["shadowsocks-2022"]
    password: str


class TaggedHysteria2MaterialData(TypedDict):
    kind: Literal["hysteria2"]
    password: str


class TaggedTrojanMaterialData(TypedDict):
    kind: Literal["trojan"]
    password: str


class TaggedAnyTlsMaterialData(TypedDict):
    kind: Literal["anytls"]
    password: str


class TaggedTuicMaterialData(TypedDict):
    kind: Literal["tuic"]
    user_uuid: str
    password: str


class TaggedVlessMaterialData(TypedDict):
    kind: Literal["vless-tls"]
    user_uuid: str


class TaggedVmessMaterialData(TypedDict):
    kind: Literal["vmess-tls"]
    user_uuid: str


ProtocolMaterialData = (
    TaggedRealityMaterialData
    | TaggedShadowsocksMaterialData
    | TaggedHysteria2MaterialData
    | TaggedTrojanMaterialData
    | TaggedAnyTlsMaterialData
    | TaggedTuicMaterialData
    | TaggedVlessMaterialData
    | TaggedVmessMaterialData
)


class AcmeTlsIntentData(TypedDict):
    kind: Literal["acme"]
    server_name: str
    email: str
    data_directory: str


class OperatorFileTlsIntentData(TypedDict):
    kind: Literal["operator-files"]
    server_name: str
    certificate_path: str
    key_path: str


TlsIntentData = AcmeTlsIntentData | OperatorFileTlsIntentData


class WebSocketTransportIntentData(TypedDict):
    kind: Literal["websocket"]
    path: str
    host: str | None


class GrpcTransportIntentData(TypedDict):
    kind: Literal["grpc"]
    service_name: str


TransportIntentData = WebSocketTransportIntentData | GrpcTransportIntentData


class ProfileData(TypedDict):
    profile_id: str
    profile_name: str
    protocol: str
    listen_port: int | None
    port_selection: str
    status: str
    reality_material: RealityMaterialData | None
    protocol_material: ProtocolMaterialData | None
    server_address: str | None
    tls_intent: TlsIntentData | None
    transport_intent: TransportIntentData | None


class InstallationData(TypedDict):
    schema_version: int
    revision: int
    profiles: list[ProfileData]
    expected_config_sha256: str | None


class JsonFileStateStore:
    """Atomically persist manager desired state as readable JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.backup_path = path.with_name(f"{path.name}.bak")

    def load(self) -> ManagedInstallation:
        if not self.path.exists():
            return ManagedInstallation.empty()
        with self.path.open(encoding="utf-8") as state_file:
            data = cast(InstallationData, json.load(state_file))
        if data["schema_version"] != CURRENT_SCHEMA_VERSION:
            raise UnsupportedStateSchemaError(
                supported=CURRENT_SCHEMA_VERSION,
                found=data["schema_version"],
            )
        return ManagedInstallation(
            schema_version=data["schema_version"],
            revision=data["revision"],
            profiles=tuple(self._profile_from_data(profile) for profile in data["profiles"]),
            expected_config_sha256=data.get("expected_config_sha256"),
        )

    def save(self, installation: ManagedInstallation) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_current_state()
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                json.dump(
                    self._installation_to_data(installation),
                    temporary_file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                temporary_file.write("\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _backup_current_state(self) -> None:
        if not self.path.exists():
            return

        temporary_path: Path | None = None
        try:
            with (
                self.path.open("rb") as current_file,
                NamedTemporaryFile(
                    mode="wb",
                    dir=self.path.parent,
                    prefix=f".{self.backup_path.name}.",
                    delete=False,
                ) as temporary_file,
            ):
                temporary_path = Path(temporary_file.name)
                shutil.copyfileobj(current_file, temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(self.backup_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _installation_to_data(installation: ManagedInstallation) -> InstallationData:
        return InstallationData(
            schema_version=installation.schema_version,
            revision=installation.revision,
            expected_config_sha256=installation.expected_config_sha256,
            profiles=[
                ProfileData(
                    profile_id=profile.profile_id,
                    profile_name=profile.profile_name,
                    protocol=profile.protocol.value,
                    listen_port=profile.listen_port,
                    port_selection=profile.port_selection.value,
                    status=profile.status.value,
                    reality_material=None,
                    protocol_material=JsonFileStateStore._material_to_data(
                        profile.protocol_material
                    ),
                    server_address=profile.server_address,
                    tls_intent=JsonFileStateStore._tls_intent_to_data(profile.tls_intent),
                    transport_intent=JsonFileStateStore._transport_intent_to_data(
                        profile.transport_intent
                    ),
                )
                for profile in installation.profiles
            ],
        )

    @staticmethod
    def _profile_from_data(data: ProfileData) -> ManagedProfile:
        tagged_material_data = data.get("protocol_material")
        material_data = data.get("reality_material")
        return ManagedProfile(
            profile_id=data.get("profile_id", ""),
            profile_name=data["profile_name"],
            protocol=ProtocolKind(data["protocol"]),
            listen_port=data["listen_port"],
            port_selection=PortSelection(data["port_selection"]),
            status=ProfileStatus(data["status"]),
            protocol_material=(
                JsonFileStateStore._material_from_data(tagged_material_data)
                if tagged_material_data is not None
                else (
                    RealityMaterial(
                        user_uuid=material_data["user_uuid"],
                        private_key=material_data["private_key"],
                        public_key=material_data["public_key"],
                        short_id=material_data["short_id"],
                        server_name=material_data["server_name"],
                    )
                    if material_data is not None
                    else None
                )
            ),
            server_address=data.get("server_address"),
            tls_intent=(
                JsonFileStateStore._tls_intent_from_data(tls_data)
                if (tls_data := data.get("tls_intent")) is not None
                else None
            ),
            transport_intent=(
                JsonFileStateStore._transport_intent_from_data(transport_data)
                if (transport_data := data.get("transport_intent")) is not None
                else None
            ),
        )

    @staticmethod
    def _material_to_data(material: ProtocolMaterial | None) -> ProtocolMaterialData | None:
        if isinstance(material, RealityMaterial):
            data: ProtocolMaterialData | None = TaggedRealityMaterialData(
                kind="vless-reality",
                user_uuid=material.user_uuid,
                private_key=material.private_key,
                public_key=material.public_key,
                short_id=material.short_id,
                server_name=material.server_name,
            )
        elif isinstance(material, ShadowsocksMaterial):
            data = TaggedShadowsocksMaterialData(
                kind="shadowsocks-2022",
                password=material.password,
            )
        elif isinstance(material, Hysteria2Material):
            data = TaggedHysteria2MaterialData(
                kind="hysteria2",
                password=material.password,
            )
        elif isinstance(material, TrojanMaterial):
            data = TaggedTrojanMaterialData(
                kind="trojan",
                password=material.password,
            )
        elif isinstance(material, AnyTlsMaterial):
            data = TaggedAnyTlsMaterialData(
                kind="anytls",
                password=material.password,
            )
        elif isinstance(material, TuicMaterial):
            data = TaggedTuicMaterialData(
                kind="tuic",
                user_uuid=material.user_uuid,
                password=material.password,
            )
        elif isinstance(material, VlessMaterial):
            data = TaggedVlessMaterialData(
                kind="vless-tls",
                user_uuid=material.user_uuid,
            )
        elif isinstance(material, VmessMaterial):
            data = TaggedVmessMaterialData(
                kind="vmess-tls",
                user_uuid=material.user_uuid,
            )
        elif material is None:
            data = None
        else:
            raise TypeError(f"Unregistered protocol material: {type(material).__name__}")
        return data

    @staticmethod
    def _material_from_data(data: ProtocolMaterialData) -> ProtocolMaterial:
        if data["kind"] == "vless-reality":
            material: ProtocolMaterial = RealityMaterial(
                user_uuid=data["user_uuid"],
                private_key=data["private_key"],
                public_key=data["public_key"],
                short_id=data["short_id"],
                server_name=data["server_name"],
            )
        elif data["kind"] == "shadowsocks-2022":
            material = ShadowsocksMaterial(password=data["password"])
        elif data["kind"] == "hysteria2":
            material = Hysteria2Material(password=data["password"])
        elif data["kind"] == "trojan":
            material = TrojanMaterial(password=data["password"])
        elif data["kind"] == "anytls":
            material = AnyTlsMaterial(password=data["password"])
        elif data["kind"] == "tuic":
            material = TuicMaterial(user_uuid=data["user_uuid"], password=data["password"])
        elif data["kind"] == "vless-tls":
            material = VlessMaterial(user_uuid=data["user_uuid"])
        else:
            material = VmessMaterial(user_uuid=data["user_uuid"])
        return material

    @staticmethod
    def _tls_intent_to_data(intent: TlsIntent | None) -> TlsIntentData | None:
        if isinstance(intent, AcmeTlsIntent):
            return AcmeTlsIntentData(
                kind="acme",
                server_name=intent.server_name,
                email=intent.email,
                data_directory=str(intent.data_directory),
            )
        if isinstance(intent, OperatorFileTlsIntent):
            return OperatorFileTlsIntentData(
                kind="operator-files",
                server_name=intent.server_name,
                certificate_path=str(intent.certificate_path),
                key_path=str(intent.key_path),
            )
        if intent is None:
            return None
        raise TypeError(f"Unregistered TLS intent: {type(intent).__name__}")

    @staticmethod
    def _tls_intent_from_data(data: TlsIntentData) -> TlsIntent:
        if data["kind"] == "acme":
            return AcmeTlsIntent(
                server_name=data["server_name"],
                email=data["email"],
                data_directory=Path(data["data_directory"]),
            )
        return OperatorFileTlsIntent(
            server_name=data["server_name"],
            certificate_path=Path(data["certificate_path"]),
            key_path=Path(data["key_path"]),
        )

    @staticmethod
    def _transport_intent_to_data(
        intent: TransportIntent | None,
    ) -> TransportIntentData | None:
        if isinstance(intent, WebSocketTransportIntent):
            return WebSocketTransportIntentData(
                kind="websocket",
                path=intent.path,
                host=intent.host,
            )
        if isinstance(intent, GrpcTransportIntent):
            return GrpcTransportIntentData(kind="grpc", service_name=intent.service_name)
        return None

    @staticmethod
    def _transport_intent_from_data(data: TransportIntentData) -> TransportIntent:
        if data["kind"] == "websocket":
            return WebSocketTransportIntent(path=data["path"], host=data["host"])
        return GrpcTransportIntent(service_name=data["service_name"])
