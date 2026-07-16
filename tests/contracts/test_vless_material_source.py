from sb_manager.adapters.vless_material import SecureVlessMaterialSource
from sb_manager.domain.protocol_material import VlessMaterial


class FixedRandomSource:
    def uuid(self) -> str:
        return "bf000d23-0752-40b4-affe-68f7707a9661"

    def token_hex(self, byte_count: int) -> str:
        raise AssertionError("VLESS material only uses a UUID")

    def token_bytes(self, byte_count: int) -> bytes:
        raise AssertionError("VLESS material only uses a UUID")


def test_secure_vless_material_source_generates_a_uuid() -> None:
    source = SecureVlessMaterialSource(random_source=FixedRandomSource())

    assert source.generate() == VlessMaterial(user_uuid="bf000d23-0752-40b4-affe-68f7707a9661")
