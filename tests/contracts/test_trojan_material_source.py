from sb_manager.adapters.trojan_material import SecureTrojanMaterialSource
from sb_manager.domain.protocol_material import TrojanMaterial

EXPECTED_PASSWORD_BYTES = 16


class FixedRandomSource:
    def uuid(self) -> str:
        raise AssertionError("Trojan material does not use UUIDs")

    def token_hex(self, byte_count: int) -> str:
        assert byte_count == EXPECTED_PASSWORD_BYTES
        return "0123456789abcdef0123456789abcdef"

    def token_bytes(self, byte_count: int) -> bytes:
        raise AssertionError("Trojan password uses hexadecimal text")


def test_secure_trojan_material_source_generates_a_16_byte_hex_password() -> None:
    source = SecureTrojanMaterialSource(random_source=FixedRandomSource())

    assert source.generate() == TrojanMaterial(password="0123456789abcdef0123456789abcdef")
