"""Session-scoped interface preferences and effective manager settings."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from textual import on
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sb_manager.application.host_readiness import HostAccessMode
from sb_manager.application.interface_preferences import (
    ColorScheme,
    PreferencePersistence,
)
from sb_manager.seams.runtime import RuntimeKind
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


@dataclass(frozen=True, slots=True)
class EffectiveSettings:
    """Startup-selected settings safe to disclose in the TUI."""

    host_access_mode: HostAccessMode | None = None
    runtime_kind: RuntimeKind | None = None
    state_file: Path | None = None
    preferences_file: Path | None = None
    config_file: Path | None = None
    transaction_directory: Path | None = None


@dataclass
class ColorSchemeChangeRequested(Message):
    """Request one valid application-wide appearance for the current session."""

    color_scheme: ColorScheme


class PreferenceResetReviewRequested(Message):
    """Request a review-only plan for replacing unreadable preferences."""


class SettingsScreen(Screen[None]):
    """Present safe interface settings without changing host configuration."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        color_scheme: ColorScheme,
        effective_settings: EffectiveSettings,
        preference_persistence: PreferencePersistence,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.color_scheme = color_scheme
        self.effective_settings = effective_settings
        self.preference_persistence = preference_persistence
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="settings-workspace"):
            yield Static(self.copy.text(UiText.SETTINGS_TITLE), id="settings-title", markup=False)
            yield Static(
                self.copy.text(UiText.SETTINGS_LANGUAGE),
                id="settings-language",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.SETTINGS_LANGUAGE_POLICY),
                id="settings-language-policy",
                markup=False,
            )
            yield Static(
                self._appearance_label(),
                id="settings-appearance",
                markup=False,
            )
            yield Button(self._toggle_label(), id="toggle-color-scheme")
            yield Static(
                self._persistence_label(),
                id="settings-persistence",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.SETTINGS_REVIEW_RESET),
                id="review-preference-reset",
                classes=(
                    ""
                    if self.preference_persistence
                    in {PreferencePersistence.LOAD_FAILED, PreferencePersistence.SAVE_FAILED}
                    else "hidden"
                ),
                variant="warning",
            )
            yield Static(
                self._safety_label(),
                id="settings-safety",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.SETTINGS_UPDATE_POLICY),
                id="settings-update-policy",
                markup=False,
            )
            yield Static(
                self._host_access_label(),
                id="settings-host-access",
                markup=False,
            )
            yield Static(
                self._runtime_label(),
                id="settings-runtime",
                markup=False,
            )
            yield Static(
                self._path_label(
                    self.copy.text(UiText.SETTINGS_ROLE_STATE),
                    self.effective_settings.state_file,
                ),
                id="settings-state-file",
                markup=False,
            )
            yield Static(
                self._path_label(
                    self.copy.text(UiText.SETTINGS_ROLE_PREFERENCES),
                    self.effective_settings.preferences_file,
                ),
                id="settings-preferences-file",
                markup=False,
            )
            yield Static(
                self._config_file_label(),
                id="settings-config-file",
                markup=False,
            )
            yield Static(
                self._path_label(
                    self.copy.text(UiText.SETTINGS_ROLE_TRANSACTION),
                    self.effective_settings.transaction_directory,
                ),
                id="settings-transaction-directory",
                markup=False,
            )
        yield Footer()

    @on(Button.Pressed, "#toggle-color-scheme")
    def toggle_color_scheme(self, event: Button.Pressed) -> None:
        event.stop()
        self.color_scheme = (
            ColorScheme.LIGHT if self.color_scheme is ColorScheme.DARK else ColorScheme.DARK
        )
        self.query_one("#settings-appearance", Static).update(self._appearance_label())
        event.button.label = self._toggle_label()
        self.post_message(ColorSchemeChangeRequested(self.color_scheme))

    @on(Button.Pressed, "#review-preference-reset")
    def review_preference_reset(self, event: Button.Pressed) -> None:
        event.stop()
        self.post_message(PreferenceResetReviewRequested())

    def show_preference_persistence(self, persistence: PreferencePersistence) -> None:
        """Present the latest disclosure-safe persistence result."""

        self.preference_persistence = persistence
        self.query_one("#settings-persistence", Static).update(self._persistence_label())
        reset = self.query_one("#review-preference-reset", Button)
        if persistence in {
            PreferencePersistence.LOAD_FAILED,
            PreferencePersistence.SAVE_FAILED,
        }:
            reset.remove_class("hidden")
        else:
            reset.add_class("hidden")

    def show_preference_reset(self) -> None:
        """Apply the restored defaults after one confirmed reset."""

        self.color_scheme = ColorScheme.DARK
        self.query_one("#settings-appearance", Static).update(self._appearance_label())
        self.query_one("#toggle-color-scheme", Button).label = self._toggle_label()
        self.show_preference_persistence(PreferencePersistence.RESET)

    def _appearance_label(self) -> str:
        return self.copy.text(UiText.SETTINGS_APPEARANCE, label=self._color_label())

    def _toggle_label(self) -> str:
        target = (
            self.copy.text(UiText.SETTINGS_COLOR_LIGHT)
            if self.color_scheme is ColorScheme.DARK
            else self.copy.text(UiText.SETTINGS_COLOR_DARK)
        )
        return self.copy.text(UiText.SETTINGS_TOGGLE_APPEARANCE, target=target)

    def _color_label(self) -> str:
        key = (
            UiText.SETTINGS_COLOR_DARK
            if self.color_scheme is ColorScheme.DARK
            else UiText.SETTINGS_COLOR_LIGHT
        )
        return self.copy.text(key)

    def _persistence_label(self) -> str:
        if self.preference_persistence is PreferencePersistence.SAVED:
            return self.copy.text(
                UiText.SETTINGS_PERSISTENCE_SAVED,
                label=self._color_label(),
            )
        keys = {
            PreferencePersistence.LOADED: UiText.SETTINGS_PERSISTENCE_LOADED,
            PreferencePersistence.LOAD_FAILED: UiText.SETTINGS_PERSISTENCE_LOAD_FAILED,
            PreferencePersistence.SAVE_FAILED: UiText.SETTINGS_PERSISTENCE_SAVE_FAILED,
            PreferencePersistence.RESET: UiText.SETTINGS_PERSISTENCE_RESET,
            PreferencePersistence.READY: UiText.SETTINGS_PERSISTENCE_READY,
            PreferencePersistence.SESSION_ONLY: UiText.SETTINGS_PERSISTENCE_SESSION_ONLY,
        }
        return self.copy.text(keys[self.preference_persistence])

    def _safety_label(self) -> str:
        if self.preference_persistence is PreferencePersistence.SESSION_ONLY:
            return self.copy.text(UiText.SETTINGS_SAFETY_SESSION)
        return self.copy.text(UiText.SETTINGS_SAFETY_PERSISTED)

    def _host_access_label(self) -> str:
        mode = self.effective_settings.host_access_mode
        keys: dict[HostAccessMode | None, UiText] = {
            HostAccessMode.PRIVILEGED: UiText.SETTINGS_HOST_ACCESS_PRIVILEGED,
            HostAccessMode.DIRECT: UiText.SETTINGS_HOST_ACCESS_DIRECT,
            None: UiText.SETTINGS_HOST_ACCESS_UNAVAILABLE,
        }
        return self.copy.text(keys[mode])

    def _runtime_label(self) -> str:
        runtime = self.effective_settings.runtime_kind
        keys: dict[RuntimeKind | None, UiText] = {
            RuntimeKind.SYSTEMD: UiText.SETTINGS_RUNTIME_SYSTEMD,
            RuntimeKind.OPENRC: UiText.SETTINGS_RUNTIME_OPENRC,
            None: UiText.SETTINGS_RUNTIME_UNAVAILABLE,
        }
        return self.copy.text(keys[runtime])

    def _config_file_label(self) -> str:
        if self.effective_settings.host_access_mode is HostAccessMode.PRIVILEGED:
            return self.copy.text(UiText.SETTINGS_CONFIG_PRIVILEGED)
        return self._path_label(
            self.copy.text(UiText.SETTINGS_ROLE_CONFIG),
            self.effective_settings.config_file,
        )

    def _path_label(self, role: str, path: Path | None) -> str:
        rendered_path = (
            str(path) if path is not None else self.copy.text(UiText.SETTINGS_PATH_UNAVAILABLE)
        )
        return self.copy.text(UiText.SETTINGS_PATH, role=role, path=rendered_path)
