from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.profile_details import ProfileDetailsService
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import RealityMaterial
from sb_manager.protocols.catalog import ConnectionPayloadKind, ProtocolCatalog, RealityHandler

LISTEN_PORT = 4433


class GenerationMustNotRun:
    def generate(self) -> RealityMaterial:
        raise AssertionError("reading an applied profile must reuse persisted material")


def test_applied_profile_details_rebuild_connection_information_from_desired_state() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="phone-profile",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=LISTEN_PORT,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                server_address="vpn.example.com",
                protocol_material=RealityMaterial(
                    user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
                    private_key="private-key-value",
                    public_key="public-key-value",
                    short_id="0123456789abcdef",
                    server_name="www.cloudflare.com",
                ),
            ),
        ),
    )
    service = ProfileDetailsService(
        state_store=MemoryStateStore(installation),
        protocol_catalog=ProtocolCatalog((RealityHandler(material_source=GenerationMustNotRun()),)),
    )

    details = service.get_profile_details("phone-profile")

    assert details.profile_id == "phone-profile"
    assert details.profile_name == "手机"
    assert details.status is ProfileStatus.APPLIED
    assert details.enabled is True
    assert details.connection_info is not None
    assert details.connection_info.server_address == "vpn.example.com"
    assert details.connection_info.server_port == LISTEN_PORT
    assert details.connection_info.payload.kind is ConnectionPayloadKind.URI
    assert details.connection_info.payload.content == (
        "vless://bf000d23-0752-40b4-affe-68f7707a9661@vpn.example.com:4433"
        "?encryption=none&flow=xtls-rprx-vision&security=reality"
        "&sni=www.cloudflare.com&fp=chrome&pbk=public-key-value"
        "&sid=0123456789abcdef&type=tcp#%E6%89%8B%E6%9C%BA"
    )
