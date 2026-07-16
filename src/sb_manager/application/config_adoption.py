"""Plan and confirm ownership adoption of one exact live configuration."""

from dataclasses import dataclass
from typing import Protocol

from sb_manager.application.manager import StateRevisionConflictError
from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.apply_lock import ApplyLock
from sb_manager.seams.config_target import ConfigurationTargetInspector
from sb_manager.seams.state_store import StateStore


class ConfigAdoptionError(RuntimeError):
    """Base error for a rejected configuration adoption workflow."""


class NoLiveConfigurationError(ConfigAdoptionError):
    """There is no existing live configuration to adopt."""


class ConfigurationAlreadyTrackedError(ConfigAdoptionError):
    """Desired state already carries a replacement precondition."""


class AdoptionConfirmationRequiredError(ConfigAdoptionError):
    """Adoption requires a second explicit operator action."""


class LiveConfigChangedError(ConfigAdoptionError):
    """The live configuration changed after the operator reviewed the plan."""


@dataclass(frozen=True, slots=True)
class ConfigAdoptionPlan:
    """Reviewable adoption intent with no host mutation."""

    base_revision: int
    config_sha256: str
    mutates_host: bool = False
    imports_profiles: bool = False


@dataclass(frozen=True, slots=True)
class ConfigAdoptionResult:
    """Desired-state evidence committed after a successful recheck."""

    committed_revision: int
    config_sha256: str


class ConfigAdopter(Protocol):
    """TUI-facing interface for the complete adoption use case."""

    def plan(self) -> ConfigAdoptionPlan: ...

    def adopt(
        self,
        plan: ConfigAdoptionPlan,
        *,
        confirmed: bool,
    ) -> ConfigAdoptionResult: ...


class ConfigAdoptionService:
    """Record exact replacement consent without parsing or changing live config."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        config_inspector: ConfigurationTargetInspector,
        mutation_lock: ApplyLock,
    ) -> None:
        self._state_store = state_store
        self._config_inspector = config_inspector
        self._mutation_lock = mutation_lock

    def plan(self) -> ConfigAdoptionPlan:
        installation = self._state_store.load()
        if installation.expected_config_sha256 is not None:
            raise ConfigurationAlreadyTrackedError(
                "Desired state already tracks the live configuration"
            )
        observation = self._config_inspector.inspect()
        if not observation.exists or observation.sha256 is None:
            raise NoLiveConfigurationError("No existing live configuration was found")
        return ConfigAdoptionPlan(
            base_revision=installation.revision,
            config_sha256=observation.sha256,
        )

    def adopt(
        self,
        plan: ConfigAdoptionPlan,
        *,
        confirmed: bool,
    ) -> ConfigAdoptionResult:
        if not confirmed:
            raise AdoptionConfirmationRequiredError(
                "Configuration adoption requires explicit confirmation"
            )
        with self._mutation_lock.acquire():
            installation = self._state_store.load()
            if installation.revision != plan.base_revision:
                raise StateRevisionConflictError(
                    expected=plan.base_revision,
                    actual=installation.revision,
                )
            if installation.expected_config_sha256 is not None:
                raise ConfigurationAlreadyTrackedError(
                    "Desired state already tracks the live configuration"
                )
            observation = self._config_inspector.inspect()
            if observation.sha256 != plan.config_sha256:
                raise LiveConfigChangedError(
                    "Live configuration changed after the adoption plan was reviewed"
                )
            committed_revision = installation.revision + 1
            self._state_store.save(
                ManagedInstallation(
                    schema_version=installation.schema_version,
                    revision=committed_revision,
                    profiles=installation.profiles,
                    expected_config_sha256=plan.config_sha256,
                )
            )
        return ConfigAdoptionResult(
            committed_revision=committed_revision,
            config_sha256=plan.config_sha256,
        )
