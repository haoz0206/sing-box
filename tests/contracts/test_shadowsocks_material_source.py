from sb_manager.adapters.shadowsocks_material import SecureShadowsocksMaterialSource
from sb_manager.domain.protocol_material import ShadowsocksMaterial

EXPECTED_KEY_BYTES = 16


class FixedRandomSource:
    def uuid(self) -> str:
        raise AssertionError("Shadowsocks material does not use UUIDs")

    def token_hex(self, byte_count: int) -> str:
        raise AssertionError("Shadowsocks material requires raw bytes")

    def token_bytes(self, byte_count: int) -> bytes:
        assert byte_count == EXPECTED_KEY_BYTES
        return bytes.fromhex("f090ac3ecb1f812f2d891c2232584046")


def test_secure_shadowsocks_material_source_generates_a_16_byte_base64_key() -> None:
    source = SecureShadowsocksMaterialSource(random_source=FixedRandomSource())

    assert source.generate() == ShadowsocksMaterial(password="8JCsPssfgS8tiRwiMlhARg==")
