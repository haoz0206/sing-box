"""Shared navigation guard for explicitly confirmed background operations."""

from dataclasses import replace
from typing import ClassVar, Generic, TypeVar

from textual.binding import ActiveBinding, BindingType
from textual.screen import Screen

from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

ScreenResult = TypeVar("ScreenResult")


class ConfirmedOperationScreen(Screen[ScreenResult], Generic[ScreenResult]):
    """Keep a confirmed operation visible until it reaches a terminal state."""

    BINDINGS: ClassVar[list[BindingType]] = [
        (
            "escape",
            "return_from_confirmation",
            SIMPLIFIED_CHINESE.text(UiText.COMMON_CANCEL),
        )
    ]

    _confirmed_operation_running = False

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    @property
    def active_bindings(self) -> dict[str, ActiveBinding]:
        """Render the shared cancellation action through this screen's catalog."""

        bindings = super().active_bindings
        active_escape = bindings.get("escape")
        if active_escape is not None and active_escape.binding.action == "return_from_confirmation":
            bindings["escape"] = ActiveBinding(
                active_escape.node,
                replace(
                    active_escape.binding,
                    description=self.copy.text(UiText.COMMON_CANCEL),
                ),
                active_escape.enabled,
                active_escape.tooltip,
            )
        return bindings

    @property
    def navigation_locked(self) -> bool:
        """Whether auxiliary navigation must keep this progress screen visible."""

        return self._confirmed_operation_running

    def begin_confirmed_operation(self) -> bool:
        """Acquire the one-shot navigation guard before starting background work."""
        if self._confirmed_operation_running:
            return False
        self._confirmed_operation_running = True
        return True

    def finish_confirmed_operation(self) -> None:
        """Release the navigation guard after a typed terminal outcome is known."""
        self._confirmed_operation_running = False

    def push_terminal_screen(self, screen: Screen[None]) -> None:
        """Release the guard and present a terminal result on the UI thread."""
        self.finish_confirmed_operation()
        self.app.push_screen(screen)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Keep the return binding visible but disabled while work is in flight."""
        if action == "return_from_confirmation" and self._confirmed_operation_running:
            return None
        return super().check_action(action, parameters)

    def action_return_from_confirmation(self) -> None:
        """Allow cancellation only while no confirmed operation is running."""
        if not self._confirmed_operation_running:
            self.app.pop_screen()
