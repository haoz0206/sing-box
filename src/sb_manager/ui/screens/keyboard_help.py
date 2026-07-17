"""Keyboard-first interaction guidance behind one navigation interface."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class KeyboardHelpScreen(Screen[None]):
    """Explain stable navigation keys without exposing workflow internals."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="keyboard-help"):
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_TITLE),
                id="keyboard-help-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_NAVIGATION_TITLE),
                id="keyboard-help-navigation-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_NAVIGATION),
                id="keyboard-help-navigation",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_DASHBOARD_TITLE),
                id="keyboard-help-dashboard-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_DASHBOARD),
                id="keyboard-help-dashboard",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_CONTEXT),
                id="keyboard-help-context",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.KEYBOARD_HELP_SAFETY),
                id="keyboard-help-safety",
                markup=False,
            )
        yield Footer()
