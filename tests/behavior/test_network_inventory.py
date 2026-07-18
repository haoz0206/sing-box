from sb_manager.application.network_inventory import build_network_inventory
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import SnellV6Material
from sb_manager.seams.listener_source import ListenerEndpoint, ListenerTransport


def test_applied_snell_v6_profile_contributes_a_tcp_listener_endpoint() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-7",
                profile_name="Snell preview",
                protocol=ProtocolKind.SNELL_V6,
                listen_port=18443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=SnellV6Material(
                    psk="AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"
                ),
            ),
        ),
    )

    inventory = build_network_inventory(installation)

    assert inventory.active_listener_endpoints == (
        ListenerEndpoint(port=18443, transport=ListenerTransport.TCP),
    )
