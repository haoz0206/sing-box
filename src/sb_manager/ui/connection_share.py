"""Explicit, one-page disclosure of credential-bearing connection links."""

from textual import on
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Label, Static, TextArea

from sb_manager.protocols.catalog import ProfileConnectionInfo


class ConnectionSharePanel(Widget):
    """Keep one complete connection URI hidden until the operator reveals it."""

    def __init__(self, connection_info: ProfileConnectionInfo) -> None:
        super().__init__(id="connection-share")
        self._connection_info = connection_info
        self._revealed = False

    def compose(self) -> ComposeResult:
        yield Static(
            f"服务器：{self._connection_info.server_address}:{self._connection_info.server_port}",
            id="connection-share-endpoint",
        )
        yield Static(
            "连接链接包含完整访问凭据，默认隐藏。仅在私密终端中显示。",
            id="connection-share-warning",
        )
        yield Button("显示一次连接链接", id="reveal-connection-share")

    @on(Button.Pressed, "#reveal-connection-share")
    async def reveal_share_uri(self, event: Button.Pressed) -> None:
        if self._revealed:
            return
        self._revealed = True
        self.query_one("#connection-share-warning", Static).update(
            "连接链接仅在本次页面中可见，离开后将重新隐藏。"
        )
        await event.button.remove()
        share_uri = TextArea(
            self._connection_info.share_uri,
            id="connection-share-uri",
            read_only=True,
            soft_wrap=True,
        )
        hide = Button("立即隐藏连接链接", id="hide-connection-share")
        await self.mount(
            Label("连接链接 - 本次页面可见", id="connection-share-label"),
            share_uri,
            hide,
        )
        share_uri.focus()

    @on(Button.Pressed, "#hide-connection-share")
    async def hide_share_uri(self, event: Button.Pressed) -> None:
        await self.query_one("#connection-share-label").remove()
        await self.query_one("#connection-share-uri").remove()
        await event.button.remove()
        self.query_one("#connection-share-warning", Static).update(
            "连接链接已重新隐藏，本页面不会再次显示。返回详情后可重新选择显示。"
        )
