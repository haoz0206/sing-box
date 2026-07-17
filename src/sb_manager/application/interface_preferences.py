"""Application policy for loading and saving operator interface preferences."""

from dataclasses import dataclass
from enum import Enum
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


@dataclass(frozen=True, slots=True)
class InterfacePreferenceSnapshot:
    """Preferences plus evidence about their persistence state."""

    preferences: InterfacePreferences
    persistence: PreferencePersistence


class PreferenceStoreError(RuntimeError):
    """The preference store could not safely load or save its document."""


class PreferenceStore(Protocol):
    """Persist the complete interface preference document."""

    def load(self) -> InterfacePreferences | None: ...

    def save(self, preferences: InterfacePreferences) -> None: ...


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
