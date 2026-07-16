import json
from pathlib import Path

import pytest

from sb_manager.adapters.generated_configuration import ProjectedGeneratedConfigurationInspector
from sb_manager.application.configuration_projection import ManagedConfigurationProjector
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import ShadowsocksMaterial
from sb_manager.protocols.catalog import ProtocolCatalog
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.generated_configuration import GeneratedConfigurationInspectionError
from sb_manager.transactions.staging import ConfigurationStager


class KnownDocumentValidator:
    def validate(self, config_path: Path) -> ConfigValidationResult:
        document = json.loads(config_path.read_text(encoding="utf-8"))
        if document == {
            "inbounds": [],
            "outbounds": [{"tag": "direct", "type": "direct"}],
        }:
            return ConfigValidationResult(
                valid=True,
                diagnostics="sing-box check completed successfully",
            )
        return ConfigValidationResult(valid=False, diagnostics="unexpected generated document")


class LeakingValidator:
    def validate(self, config_path: Path) -> ConfigValidationResult:
        return ConfigValidationResult(
            valid=False,
            diagnostics="invalid password super-secret-password in inbound",
        )


class SilentSuccessValidator:
    def validate(self, config_path: Path) -> ConfigValidationResult:
        return ConfigValidationResult(valid=True, diagnostics="")


def test_projected_configuration_is_checked_through_the_validator_seam(tmp_path: Path) -> None:
    inspector = ProjectedGeneratedConfigurationInspector(
        projector=ManagedConfigurationProjector(protocol_catalog=ProtocolCatalog(())),
        stager=ConfigurationStager(parent=tmp_path),
        validator=KnownDocumentValidator(),
    )

    observation = inspector.inspect(ManagedInstallation(schema_version=1, revision=4, profiles=()))

    assert observation.valid is True
    assert observation.diagnostics == "sing-box check completed successfully"


def test_unprojectable_applied_profile_is_reported_as_invalid_configuration(
    tmp_path: Path,
) -> None:
    inspector = ProjectedGeneratedConfigurationInspector(
        projector=ManagedConfigurationProjector(protocol_catalog=ProtocolCatalog(())),
        stager=ConfigurationStager(parent=tmp_path),
        validator=KnownDocumentValidator(),
    )
    incomplete = ManagedProfile(
        profile_id="profile-1",
        profile_name="损坏的配置",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        status=ProfileStatus.APPLIED,
    )

    observation = inspector.inspect(
        ManagedInstallation(schema_version=1, revision=9, profiles=(incomplete,))
    )

    assert observation.valid is False
    assert observation.diagnostics == "Applied profile has no port: profile-1"


def test_unavailable_staging_is_reported_as_an_unknown_check_result(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("occupied", encoding="utf-8")
    inspector = ProjectedGeneratedConfigurationInspector(
        projector=ManagedConfigurationProjector(protocol_catalog=ProtocolCatalog(())),
        stager=ConfigurationStager(parent=blocked_parent),
        validator=KnownDocumentValidator(),
    )

    with pytest.raises(
        GeneratedConfigurationInspectionError,
        match="Unable to inspect generated configuration",
    ):
        inspector.inspect(ManagedInstallation(schema_version=1, revision=4, profiles=()))


def test_validator_diagnostics_redact_persisted_protocol_material(tmp_path: Path) -> None:
    inspector = ProjectedGeneratedConfigurationInspector(
        projector=ManagedConfigurationProjector(protocol_catalog=ProtocolCatalog(())),
        stager=ConfigurationStager(parent=tmp_path),
        validator=LeakingValidator(),
    )
    draft = ManagedProfile(
        profile_id="profile-1",
        profile_name="临时配置",
        protocol=ProtocolKind.SHADOWSOCKS,
        listen_port=8388,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        protocol_material=ShadowsocksMaterial(password="super-secret-password"),
    )

    observation = inspector.inspect(
        ManagedInstallation(schema_version=1, revision=2, profiles=(draft,))
    )

    assert observation.valid is False
    assert observation.diagnostics == "invalid password [REDACTED] in inbound"


def test_silent_success_returns_positive_validation_evidence(tmp_path: Path) -> None:
    inspector = ProjectedGeneratedConfigurationInspector(
        projector=ManagedConfigurationProjector(protocol_catalog=ProtocolCatalog(())),
        stager=ConfigurationStager(parent=tmp_path),
        validator=SilentSuccessValidator(),
    )

    observation = inspector.inspect(ManagedInstallation(schema_version=1, revision=4, profiles=()))

    assert observation.valid is True
    assert observation.diagnostics == "sing-box check completed successfully"
