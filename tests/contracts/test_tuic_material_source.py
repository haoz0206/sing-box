from sb_manager.adapters.tuic_material import SecureTuicMaterialSource
from sb_manager.domain.protocol_material import TuicMaterial

EXPECTED_PASSWORD_BYTES = 16


class FixedRandomSource:
    def uuid(self) -> str:
        return "2dd61d93-75d8-4da4-ac0e-6aece7eac365"

    def token_hex(self, byte_count: int) -> str:
        assert byte_count == EXPECTED_PASSWORD_BYTES
        return "0123456789abcdef0123456789abcdef"

    def token_bytes(self, byte_count: int) -> bytes:
        raise AssertionError("TUIC password uses hexadecimal text")


def test_secure_tuic_material_source_generates_uuid_and_16_byte_password() -> None:
    source = SecureTuicMaterialSource(random_source=FixedRandomSource())

    assert source.generate() == TuicMaterial(
        user_uuid="2dd61d93-75d8-4da4-ac0e-6aece7eac365",
        password="0123456789abcdef0123456789abcdef",
    )
