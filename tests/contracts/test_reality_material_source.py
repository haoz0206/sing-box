from pathlib import Path

import pytest

from sb_manager.adapters.reality_material import SingBoxRealityMaterialSource
from sb_manager.protocols.reality import RealityMaterial
from sb_manager.seams.reality_material import RealityMaterialGenerationError

EXPECTED_SHORT_ID_BYTES = 8


class FixedRandomSource:
    def uuid(self) -> str:
        return "bf000d23-0752-40b4-affe-68f7707a9661"

    def token_hex(self, byte_count: int) -> str:
        assert byte_count == EXPECTED_SHORT_ID_BYTES
        return "0123456789abcdef"


class RandomSourceThatMustNotBeCalled:
    def uuid(self) -> str:
        raise AssertionError("random values must not be consumed after key generation failure")

    def token_hex(self, byte_count: int) -> str:
        raise AssertionError("random values must not be consumed after key generation failure")


def test_reality_material_source_combines_secure_values_and_sing_box_keys(
    tmp_path: Path,
) -> None:
    argument_log = tmp_path / "arguments.txt"
    fake_sing_box = tmp_path / "sing-box"
    fake_sing_box.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(argument_log)!r}).write_text(' '.join(sys.argv[1:]), encoding='utf-8')\n"
        "print('PrivateKey: private-key-value')\n"
        "print('PublicKey: public-key-value')\n",
        encoding="utf-8",
    )
    fake_sing_box.chmod(0o755)
    source = SingBoxRealityMaterialSource(
        binary=fake_sing_box,
        random_source=FixedRandomSource(),
        server_name="www.cloudflare.com",
    )

    material = source.generate()

    assert material == RealityMaterial(
        user_uuid="bf000d23-0752-40b4-affe-68f7707a9661",
        private_key="private-key-value",
        public_key="public-key-value",
        short_id="0123456789abcdef",
        server_name="www.cloudflare.com",
    )
    assert argument_log.read_text(encoding="utf-8") == "generate reality-keypair"


def test_reality_material_source_classifies_sing_box_failure(tmp_path: Path) -> None:
    fake_sing_box = tmp_path / "sing-box"
    fake_sing_box.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('key generation unavailable', file=sys.stderr)\n"
        "raise SystemExit(42)\n",
        encoding="utf-8",
    )
    fake_sing_box.chmod(0o755)
    source = SingBoxRealityMaterialSource(
        binary=fake_sing_box,
        random_source=RandomSourceThatMustNotBeCalled(),
        server_name="www.cloudflare.com",
    )

    with pytest.raises(RealityMaterialGenerationError) as caught:
        source.generate()

    assert caught.value.diagnostics == "key generation unavailable"
