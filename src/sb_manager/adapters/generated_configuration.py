"""Semantic desired-configuration inspection without host mutation."""

from dataclasses import fields

from sb_manager.application.configuration_projection import (
    ConfigurationProjectionError,
    ManagedConfigurationProjector,
)
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.config_validator import ConfigValidator
from sb_manager.seams.generated_configuration import (
    GeneratedConfigurationInspectionError,
    GeneratedConfigurationObservation,
)
from sb_manager.transactions.staging import ConfigurationStager


class ProjectedGeneratedConfigurationInspector:
    """Project one desired-state snapshot and validate it in disposable staging."""

    def __init__(
        self,
        *,
        projector: ManagedConfigurationProjector,
        stager: ConfigurationStager,
        validator: ConfigValidator,
    ) -> None:
        self._projector = projector
        self._stager = stager
        self._validator = validator

    def inspect(self, installation: ManagedInstallation) -> GeneratedConfigurationObservation:
        try:
            document = self._projector.project(installation.profiles)
        except ConfigurationProjectionError as error:
            return GeneratedConfigurationObservation(valid=False, diagnostics=str(error))
        try:
            with self._stager.stage(document) as staged:
                result = self._validator.validate(staged.config_path)
        except OSError as error:
            raise GeneratedConfigurationInspectionError(
                f"Unable to inspect generated configuration: {error}"
            ) from error
        return GeneratedConfigurationObservation(
            valid=result.valid,
            diagnostics=self._redact_protocol_material(
                ("sing-box check completed successfully" if result.valid else result.diagnostics),
                installation=installation,
            ),
        )

    @staticmethod
    def _redact_protocol_material(
        diagnostics: str,
        *,
        installation: ManagedInstallation,
    ) -> str:
        redacted = diagnostics
        for profile in installation.profiles:
            material = profile.protocol_material
            if material is None:
                continue
            for field in fields(material):
                value = getattr(material, field.name)
                if isinstance(value, str) and value:
                    redacted = redacted.replace(value, "[REDACTED]")
        return redacted
