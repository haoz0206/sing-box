"""Read-only profile detail queries for durable TUI navigation."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.domain.installation import ProfileStatus, ProtocolKind
from sb_manager.protocols.catalog import ProfileConnectionInfo, ProtocolCatalog
from sb_manager.seams.state_store import StateStore


class ProfileDetailsError(RuntimeError):
    """A profile detail query cannot produce safe presentation data."""


class ProfileDetailsNotFoundError(ProfileDetailsError):
    """The requested stable profile identifier is not in desired state."""


class ProfileDetailsUnavailableError(ProfileDetailsError):
    """Persisted profile data cannot currently rebuild client information."""


@dataclass(frozen=True, slots=True)
class ProfileDetails:
    """Protocol-neutral profile information suitable for durable presentation."""

    profile_id: str
    profile_name: str
    protocol: ProtocolKind
    status: ProfileStatus
    listen_port: int | None
    server_address: str | None
    connection_info: ProfileConnectionInfo | None


class ProfileDetailsReader(Protocol):
    """Public query seam consumed by the profile list."""

    def get_profile_details(self, profile_id: str) -> ProfileDetails: ...


class ProfileDetailsService:
    """Rebuild client information from persisted applied profile material."""

    def __init__(self, *, state_store: StateStore, protocol_catalog: ProtocolCatalog) -> None:
        self._state_store = state_store
        self._protocol_catalog = protocol_catalog

    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        installation = self._state_store.load()
        try:
            profile = next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
            )
        except StopIteration as error:
            raise ProfileDetailsNotFoundError(profile_id) from error
        connection_info = None
        if profile.status is ProfileStatus.APPLIED and profile.listen_port is not None:
            try:
                connection_info = self._protocol_catalog.materialize(
                    profile,
                    listen_port=profile.listen_port,
                ).connection_info
            except (TypeError, ValueError) as error:
                raise ProfileDetailsUnavailableError(str(error)) from error
        return ProfileDetails(
            profile_id=profile.profile_id,
            profile_name=profile.profile_name,
            protocol=profile.protocol,
            status=profile.status,
            listen_port=profile.listen_port,
            server_address=profile.server_address,
            connection_info=connection_info,
        )
