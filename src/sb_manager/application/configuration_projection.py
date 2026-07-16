"""Project complete manager desired state into one sing-box document."""

from collections.abc import Iterable

from sb_manager.domain.installation import ManagedProfile, ProfileStatus
from sb_manager.protocols.catalog import ProtocolCatalog
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.tls.catalog import TlsMaterialError


class ConfigurationProjectionError(ConfigurationApplyError):
    """Applied desired state cannot be rebuilt into a complete configuration."""


class ManagedConfigurationProjector:
    """Hide complete-document assembly behind one protocol-neutral operation."""

    def __init__(self, *, protocol_catalog: ProtocolCatalog) -> None:
        self._protocol_catalog = protocol_catalog

    def project(self, profiles: Iterable[ManagedProfile]) -> dict[str, object]:
        """Materialize every applied profile and assemble one complete document."""
        inbounds: list[dict[str, object]] = []
        certificate_providers: list[dict[str, object]] = []
        for profile in profiles:
            if profile.status is not ProfileStatus.APPLIED or not profile.enabled:
                continue
            if profile.listen_port is None:
                raise ConfigurationProjectionError(
                    f"Applied profile has no port: {profile.profile_id}"
                )
            try:
                materialized = self._protocol_catalog.materialize(
                    profile,
                    listen_port=profile.listen_port,
                )
            except (TlsMaterialError, TypeError, ValueError) as error:
                raise ConfigurationProjectionError(str(error)) from error
            inbounds.append(materialized.inbound)
            certificate_providers.extend(materialized.certificate_providers)
        document: dict[str, object] = {
            "inbounds": inbounds,
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
        if certificate_providers:
            document["certificate_providers"] = certificate_providers
        return document
