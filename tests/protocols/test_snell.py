import pytest

from sb_manager.protocols.snell import (
    SnellV6ConnectionInfo,
    SnellV6ConnectionSpec,
    SnellV6InboundSpec,
    SnellV6Protocol,
)

PSK = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"


def test_snell_v6_produces_the_exact_managed_inbound() -> None:
    spec = SnellV6InboundSpec(tag="profile-2", listen_port=8443, psk=PSK)

    assert SnellV6Protocol().build_inbound(spec) == {
        "type": "snell",
        "tag": "profile-2",
        "listen": "::",
        "listen_port": 8443,
        "version": 6,
        "psk": PSK,
        "mode": "default",
    }


def test_snell_v6_produces_a_stable_surge_policy_from_profile_id() -> None:
    spec = SnellV6ConnectionSpec(
        profile_id="profile-2",
        server_address="vpn.example.com",
        server_port=8443,
        psk=PSK,
    )

    assert SnellV6Protocol().build_connection_info(spec) == SnellV6ConnectionInfo(
        server_address="vpn.example.com",
        server_port=8443,
        psk=PSK,
        surge_policy=(f"Snell-5de8039bde5d = snell, vpn.example.com, 8443, psk={PSK}, version=6"),
    )


@pytest.mark.parametrize("invalid_psk", ("x" * 42, "!" + "x" * 42))
def test_snell_v6_rejects_invalid_psk_length_and_alphabet_without_echoing_secret(
    invalid_psk: str,
) -> None:
    with pytest.raises(ValueError) as caught:
        SnellV6Protocol().build_inbound(
            SnellV6InboundSpec(tag="profile-2", listen_port=8443, psk=invalid_psk)
        )

    assert str(caught.value) == "Managed Snell v6 PSK must be 43 URL-safe characters"
    assert invalid_psk not in str(caught.value)
