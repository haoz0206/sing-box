from sb_manager.adapters.snell_material import SecureSnellV6MaterialSource
from sb_manager.domain.protocol_material import SnellV6Material

EXPECTED_PSK_BYTES = 32


class FixedRandomSource:
    def uuid(self) -> str:
        raise AssertionError("Snell material does not use UUIDs")

    def token_hex(self, byte_count: int) -> str:
        raise AssertionError("Snell material requires raw bytes")

    def token_bytes(self, byte_count: int) -> bytes:
        assert byte_count == EXPECTED_PSK_BYTES
        return bytes.fromhex("ff" * EXPECTED_PSK_BYTES)


def test_secure_snell_v6_material_source_generates_url_safe_unpadded_psk() -> None:
    source = SecureSnellV6MaterialSource(random_source=FixedRandomSource())

    assert source.generate() == SnellV6Material(psk="__________________________________________8")
