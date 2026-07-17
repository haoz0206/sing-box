"""Keyboard-first interaction guidance behind one navigation interface."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static


class KeyboardHelpScreen(Screen[None]):
    """Explain stable navigation keys without exposing workflow internals."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="keyboard-help"):
            yield Static("键盘操作帮助", id="keyboard-help-title", markup=False)
            yield Static(
                "通用导航",
                id="keyboard-help-navigation-title",
                markup=False,
            )
            yield Static(
                "?  打开本帮助\n"
                "Tab / Shift+Tab  移动焦点\n"
                "Enter  激活当前按钮\n"
                "Esc  返回或取消当前页面",
                id="keyboard-help-navigation",
                markup=False,
            )
            yield Static(
                "仪表盘快捷键",
                id="keyboard-help-dashboard-title",
                markup=False,
            )
            yield Static(
                "a  添加配置\np  管理配置\nn  查看网络概览\n"
                "d  打开诊断中心\no  打开运维中心\nq  退出",
                id="keyboard-help-dashboard",
                markup=False,
            )
            yield Static(
                "仪表盘快捷键仅在对应功能可用时生效。表单中的字母仍会正常输入。",
                id="keyboard-help-context",
                markup=False,
            )
            yield Static(
                "快捷键只负责导航。应用配置、移除和升级仍需预览与明确确认。",
                id="keyboard-help-safety",
                markup=False,
            )
        yield Footer()
