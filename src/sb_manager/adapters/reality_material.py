"""Generate Reality key material with the sing-box executable."""

import subprocess
from pathlib import Path

from sb_manager.domain.protocol_material import RealityMaterial
from sb_manager.seams.random_source import RandomSource
from sb_manager.seams.reality_material import RealityMaterialGenerationError


class SingBoxRealityMaterialSource:
    """Combine secure random values with a sing-box Reality key pair."""

    def __init__(
        self,
        *,
        random_source: RandomSource,
        server_name: str,
        binary: str | Path = "sing-box",
    ) -> None:
        self._binary = str(binary)
        self._random_source = random_source
        self._server_name = server_name

    def generate(self) -> RealityMaterial:
        try:
            completed = subprocess.run(
                [self._binary, "generate", "reality-keypair"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise RealityMaterialGenerationError(str(error)) from error
        if completed.returncode != 0:
            raise RealityMaterialGenerationError((completed.stderr or completed.stdout).strip())
        key_values = dict(
            line.split(":", maxsplit=1) for line in completed.stdout.splitlines() if ":" in line
        )
        return RealityMaterial(
            user_uuid=self._random_source.uuid(),
            private_key=key_values["PrivateKey"].strip(),
            public_key=key_values["PublicKey"].strip(),
            short_id=self._random_source.token_hex(8),
            server_name=self._server_name,
        )
