from sb_manager.adapters.hysteria2_material import SecureHysteria2MaterialSource
from sb_manager.domain.protocol_material import Hysteria2Material

EXPECTED_PASSWORD_BYTES = 16


class FixedRandomSource:
    def uuid(self) -> str:
        raise AssertionError("Hysteria2 material does not use UUIDs")

    def token_hex(self, byte_count: int) -> str:
        assert byte_count == EXPECTED_PASSWORD_BYTES
        return "0123456789abcdef0123456789abcdef"

    def token_bytes(self, byte_count: int) -> bytes:
        raise AssertionError("Hysteria2 password uses hexadecimal text")


def test_secure_hysteria2_material_source_generates_a_16_byte_hex_password() -> None:
    source = SecureHysteria2MaterialSource(random_source=FixedRandomSource())

    assert source.generate() == Hysteria2Material(password="0123456789abcdef0123456789abcdef")
