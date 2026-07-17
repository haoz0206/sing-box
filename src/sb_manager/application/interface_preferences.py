"""Application policy for loading and saving operator interface preferences."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class ColorScheme(str, Enum):
    """Supported application-wide color schemes."""

    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True, slots=True)
class InterfacePreferences:
    """The complete persisted interface preference document."""

    color_scheme: ColorScheme = ColorScheme.DARK


class PreferencePersistence(str, Enum):
    """Disclosure-safe state of the local preference store."""

    SESSION_ONLY = "session-only"
    READY = "ready"
    LOADED = "loaded"
    LOAD_FAILED = "load-failed"
    SAVED = "saved"
    SAVE_FAILED = "save-failed"
    RESET = "reset"


@dataclass(frozen=True, slots=True)
class InterfacePreferenceSnapshot:
    """Preferences plus evidence about their persistence state."""

    preferences: InterfacePreferences
    persistence: PreferencePersistence


@dataclass(frozen=True, slots=True)
class PreferenceResetCandidate:
    """Disclosure-safe identity of one unreadable preference document."""

    expected_sha256: str
    archive_path: Path


@dataclass(frozen=True, slots=True)
class PreferenceResetPlan:
    """One review-bound replacement of unreadable preferences with defaults."""

    expected_sha256: str
    archive_path: Path
    replacement: InterfacePreferences


@dataclass(frozen=True, slots=True)
class PreferenceResetResult:
    """Typed evidence that defaults replaced one exact reviewed document."""

    snapshot: InterfacePreferenceSnapshot
    archive_path: Path


class PreferenceStoreError(RuntimeError):
    """The preference store could not safely load or save its document."""


class PreferenceResetConflictError(PreferenceStoreError):
    """The unreadable preference document changed after reset review."""


class PreferenceResetConfirmationError(RuntimeError):
    """Preference reset was requested without explicit confirmation."""


class PreferenceStore(Protocol):
    """Persist the complete interface preference document."""

    def load(self) -> InterfacePreferences | None: ...

    def save(self, preferences: InterfacePreferences) -> None: ...

    def inspect_reset_candidate(self) -> PreferenceResetCandidate: ...

    def reset_candidate(
        self,
        *,
        expected_sha256: str,
        preferences: InterfacePreferences,
    ) -> Path: ...


class InterfacePreferenceService:
    """Keep storage failures out of the TUI while preserving session usability."""

    def __init__(self, *, store: PreferenceStore) -> None:
        self._store = store

    def load(self) -> InterfacePreferenceSnapshot:
        try:
            preferences = self._store.load()
        except Exception:
            return InterfacePreferenceSnapshot(
                preferences=InterfacePreferences(),
                persistence=PreferencePersistence.LOAD_FAILED,
            )
        if preferences is None:
            return InterfacePreferenceSnapshot(
                preferences=InterfacePreferences(),
                persistence=PreferencePersistence.READY,
            )
        return InterfacePreferenceSnapshot(
            preferences=preferences,
            persistence=PreferencePersistence.LOADED,
        )

    def save_color_scheme(self, color_scheme: ColorScheme) -> InterfacePreferenceSnapshot:
        preferences = InterfacePreferences(color_scheme=color_scheme)
        try:
            self._store.save(preferences)
        except Exception:
            return InterfacePreferenceSnapshot(
                preferences=preferences,
                persistence=PreferencePersistence.SAVE_FAILED,
            )
        return InterfacePreferenceSnapshot(
            preferences=preferences,
            persistence=PreferencePersistence.SAVED,
        )

    def plan_reset(self) -> PreferenceResetPlan:
        candidate = self._store.inspect_reset_candidate()
        return PreferenceResetPlan(
            expected_sha256=candidate.expected_sha256,
            archive_path=candidate.archive_path,
            replacement=InterfacePreferences(),
        )

    def reset(
        self,
        plan: PreferenceResetPlan,
        *,
        confirmed: bool,
    ) -> PreferenceResetResult:
        if not confirmed:
            raise PreferenceResetConfirmationError(
                "interface preference reset requires explicit confirmation"
            )
        archive_path = self._store.reset_candidate(
            expected_sha256=plan.expected_sha256,
            preferences=plan.replacement,
        )
        return PreferenceResetResult(
            snapshot=InterfacePreferenceSnapshot(
                preferences=plan.replacement,
                persistence=PreferencePersistence.RESET,
            ),
            archive_path=archive_path,
        )
