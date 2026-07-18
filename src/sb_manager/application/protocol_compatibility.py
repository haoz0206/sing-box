"""Exact core-version compatibility for manager-owned protocols."""

import re
from collections.abc import Iterable

from sb_manager.domain.installation import ManagedProfile, ProfileStatus, ProtocolKind
from sb_manager.seams.core_status import CoreStatusInspector

SNELL_V6_INTRODUCTION = "1.14.0-alpha.38"
_SNELL_V6_INTRODUCTION_RELEASE = (1, 14, 0)
_SNELL_V6_INTRODUCTION_ALPHA = 38
_CORE_VERSION = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?"
    r"(?:\+[0-9A-Za-z.-]+)?$"
)


class ProtocolCompatibilityError(RuntimeError):
    """A requested protocol is incompatible with observed core evidence."""


class CoreVersionUnknown(ProtocolCompatibilityError):  # noqa: N818 - public API name
    """The active core version required for a protocol is unavailable."""

    def __init__(self, *, protocol: ProtocolKind) -> None:
        super().__init__(f"Core version is unavailable for {protocol.value}")
        self.protocol = protocol
        self.observed_version: str | None = None
        self.minimum_version = SNELL_V6_INTRODUCTION


class ProtocolUnsupportedByCore(  # noqa: N818 - public API name
    ProtocolCompatibilityError
):
    """The observed core predates a protocol's compatibility window."""

    def __init__(
        self,
        *,
        protocol: ProtocolKind,
        observed_version: str,
        minimum_version: str,
    ) -> None:
        super().__init__(
            f"{protocol.value} requires {minimum_version}; observed {observed_version}"
        )
        self.protocol = protocol
        self.observed_version = observed_version
        self.minimum_version = minimum_version


class CoreVersionChanged(ProtocolCompatibilityError):  # noqa: N818 - public API name
    """The active core no longer matches the version previously inspected."""

    def __init__(self, *, expected_version: str, observed_version: str) -> None:
        super().__init__(f"Core version changed from {expected_version} to {observed_version}")
        self.expected_version = expected_version
        self.observed_version = observed_version


class CoreTargetIncompatibleWithDesiredState(  # noqa: N818 - public API name
    ProtocolCompatibilityError
):
    """A proposed core target cannot serve all active applied profiles."""

    def __init__(
        self,
        *,
        target_version: str,
        blocking_profile_ids: tuple[str, ...],
        blocking_profile_names: tuple[str, ...],
    ) -> None:
        super().__init__(f"Core {target_version} is incompatible with applied profiles")
        self.target_version = target_version
        self.blocking_profile_ids = blocking_profile_ids
        self.blocking_profile_names = blocking_profile_names


def _supports_snell_v6(version: str) -> bool:
    match = _CORE_VERSION.fullmatch(version)
    if match is None:
        return False
    release = tuple(int(part) for part in match.group(1, 2, 3))
    if release != _SNELL_V6_INTRODUCTION_RELEASE:
        return release > _SNELL_V6_INTRODUCTION_RELEASE
    stage = match.group(4)
    if stage is None or stage in {"beta", "rc"}:
        return True
    return int(match.group(5)) >= _SNELL_V6_INTRODUCTION_ALPHA


class ProtocolCompatibilityPolicy:
    """Pure compatibility decisions for protocol and core-version pairs."""

    def supports(self, protocol: ProtocolKind, version: str) -> bool:
        if protocol is not ProtocolKind.SNELL_V6:
            return True
        return _supports_snell_v6(version)

    def require_supported(self, protocol: ProtocolKind, version: str) -> None:
        if not self.supports(protocol, version):
            raise ProtocolUnsupportedByCore(
                protocol=protocol,
                observed_version=version,
                minimum_version=SNELL_V6_INTRODUCTION,
            )

    def blocking_profiles(
        self,
        profiles: Iterable[ManagedProfile],
        *,
        target_version: str,
    ) -> tuple[ManagedProfile, ...]:
        return tuple(
            profile
            for profile in profiles
            if profile.status is ProfileStatus.APPLIED
            and profile.enabled
            and not self.supports(profile.protocol, target_version)
        )

    def require_profiles_supported(
        self,
        profiles: Iterable[ManagedProfile],
        *,
        target_version: str,
    ) -> None:
        blocking = self.blocking_profiles(profiles, target_version=target_version)
        if blocking:
            raise CoreTargetIncompatibleWithDesiredState(
                target_version=target_version,
                blocking_profile_ids=tuple(profile.profile_id for profile in blocking),
                blocking_profile_names=tuple(profile.profile_name for profile in blocking),
            )


class ActiveCoreProtocolCompatibility:
    """Fail closed against one read-only observation of the active core."""

    def __init__(
        self,
        *,
        inspector: CoreStatusInspector | None = None,
        policy: ProtocolCompatibilityPolicy | None = None,
    ) -> None:
        self._inspector = inspector
        self._policy = policy or ProtocolCompatibilityPolicy()

    def require_protocol(
        self,
        protocol: ProtocolKind,
        *,
        expected_version: str | None = None,
    ) -> str | None:
        if protocol is not ProtocolKind.SNELL_V6:
            return None
        if self._inspector is None:
            raise CoreVersionUnknown(protocol=protocol)
        observation = self._inspector.inspect()
        if not observation.available or observation.version is None:
            raise CoreVersionUnknown(protocol=protocol)
        observed_version = observation.version
        self._policy.require_supported(protocol, observed_version)
        if expected_version is not None and observed_version != expected_version:
            raise CoreVersionChanged(
                expected_version=expected_version,
                observed_version=observed_version,
            )
        return observed_version

    def require_profiles(
        self,
        profiles: Iterable[ManagedProfile],
        *,
        expected_version: str | None = None,
    ) -> str | None:
        active_snell_profiles = tuple(
            profile
            for profile in profiles
            if profile.status is ProfileStatus.APPLIED
            and profile.enabled
            and profile.protocol is ProtocolKind.SNELL_V6
        )
        if not active_snell_profiles:
            return None
        return self.require_protocol(
            ProtocolKind.SNELL_V6,
            expected_version=expected_version,
        )
