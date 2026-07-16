import json
import os
from pathlib import Path

import pytest

from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.domain.installation import (
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import Hysteria2Material
from sb_manager.protocols.catalog import Hysteria2Handler
from sb_manager.tls.catalog import AcmeTlsHandler, AcmeTlsIntent, TlsCatalog


class FixedHysteria2MaterialSource:
    def generate(self) -> Hysteria2Material:
        return Hysteria2Material(password="release-fixture-password")


@pytest.fixture(scope="session")
def real_sing_box_binary() -> Path:
    configured = os.environ.get("SB_MANAGER_REAL_SING_BOX")
    if configured is None:
        pytest.skip("set SB_MANAGER_REAL_SING_BOX to run real sing-box integration checks")
    binary = Path(configured)
    if not binary.is_file():
        pytest.fail(f"SB_MANAGER_REAL_SING_BOX is not a file: {binary}")
    return binary


@pytest.mark.integration
def test_real_sing_box_accepts_generated_hysteria2_configuration(
    real_sing_box_binary: Path,
    tmp_path: Path,
) -> None:
    materialized = Hysteria2Handler(
        material_source=FixedHysteria2MaterialSource(),
        tls_catalog=TlsCatalog((AcmeTlsHandler(),)),
    ).materialize(
        ManagedProfile(
            profile_name="release-fixture",
            protocol=ProtocolKind.HYSTERIA2,
            listen_port=18443,
            port_selection=PortSelection.FIXED,
            status=ProfileStatus.DRAFT,
            profile_id="release-fixture",
            tls_intent=AcmeTlsIntent(
                server_name="proxy.example.com",
                email="operator@example.com",
                data_directory=tmp_path / "acme",
            ),
        ),
        listen_port=18443,
    )
    document: dict[str, object] = {
        "inbounds": [materialized.inbound],
        "outbounds": [{"type": "direct", "tag": "direct"}],
        "certificate_providers": list(materialized.certificate_providers),
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")

    result = SingBoxConfigValidator(binary=real_sing_box_binary).validate(config_path)

    assert result.valid, result.diagnostics
