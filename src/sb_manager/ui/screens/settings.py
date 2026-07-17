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


class SettingsScreen(Screen[None]):
    """Present safe interface settings without changing host configuration."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        color_scheme: ColorScheme,
        effective_settings: EffectiveSettings,
        preference_persistence: PreferencePersistence,
    ) -> None:
        super().__init__()
        self.color_scheme = color_scheme
        self.effective_settings = effective_settings
        self.preference_persistence = preference_persistence

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="settings-workspace"):
            yield Static("设置", id="settings-title", markup=False)
            yield Static("界面语言：简体中文", id="settings-language", markup=False)
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
            yield Static(
                self._safety_label(),
                id="settings-safety",
                markup=False,
            )
            yield Static(
                "核心更新：手动指定确切版本 · 不自动更新",
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
                self._path_label("desired state", self.effective_settings.state_file),
                id="settings-state-file",
                markup=False,
            )
            yield Static(
                self._path_label("界面偏好", self.effective_settings.preferences_file),
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
                    "事务提交目录",
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

    def show_preference_persistence(self, persistence: PreferencePersistence) -> None:
        """Present the latest disclosure-safe persistence result."""

        self.preference_persistence = persistence
        self.query_one("#settings-persistence", Static).update(self._persistence_label())

    def _appearance_label(self) -> str:
        label = "深色" if self.color_scheme is ColorScheme.DARK else "浅色"
        return f"界面外观：{label}"

    def _toggle_label(self) -> str:
        target = "浅色" if self.color_scheme is ColorScheme.DARK else "深色"
        return f"切换为{target}"

    def _persistence_label(self) -> str:
        if self.preference_persistence is PreferencePersistence.LOADED:
            return "外观保存：已从偏好文件载入"
        if self.preference_persistence is PreferencePersistence.SAVED:
            label = "浅色" if self.color_scheme is ColorScheme.LIGHT else "深色"
            return f"外观保存：已保存，下次启动将继续使用{label}"
        if self.preference_persistence is PreferencePersistence.LOAD_FAILED:
            return "外观保存：无法读取偏好文件，本次使用默认深色"
        if self.preference_persistence is PreferencePersistence.SAVE_FAILED:
            return "外观保存：本次已应用，但未能保存。下次启动可能恢复默认值"
        if self.preference_persistence is PreferencePersistence.READY:
            return "外观保存：已启用，切换后会保留到下次启动"
        return "外观保存：仅本次会话"

    def _safety_label(self) -> str:
        if self.preference_persistence is PreferencePersistence.SESSION_ONLY:
            return "外观变更仅影响本次 TUI 会话，不会修改主机或 desired state。"
        return "外观偏好只写入当前用户的本地偏好文件，不会修改主机或 desired state。"

    def _host_access_label(self) -> str:
        mode = self.effective_settings.host_access_mode
        if mode is HostAccessMode.PRIVILEGED:
            return "主机变更：最小权限 helper"
        if mode is HostAccessMode.DIRECT:
            return "主机变更：直接模式"
        return "主机变更：当前启动方式未提供"

    def _runtime_label(self) -> str:
        runtime = self.effective_settings.runtime_kind
        if runtime is RuntimeKind.SYSTEMD:
            return "服务管理：systemd"
        if runtime is RuntimeKind.OPENRC:
            return "服务管理：OpenRC"
        return "服务管理：当前启动方式未提供"

    def _config_file_label(self) -> str:
        if self.effective_settings.host_access_mode is HostAccessMode.PRIVILEGED:
            return "live configuration：由最小权限 helper 的固定策略管理"
        return self._path_label("live configuration", self.effective_settings.config_file)

    @staticmethod
    def _path_label(role: str, path: Path | None) -> str:
        return f"{role}：{path if path is not None else '当前启动方式未提供'}"
