"""Explicit, one-page disclosure of credential-bearing connection links."""

from textual import on
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Button, Label, Static, TextArea

from sb_manager.protocols.catalog import ProfileConnectionInfo
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class ConnectionSharePanel(Widget):
    """Keep one complete connection URI hidden until the operator reveals it."""

    def __init__(
        self,
        connection_info: ProfileConnectionInfo,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(id="connection-share")
        self._connection_info = connection_info
        self._revealed = False
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Static(
            self.copy.text(
                UiText.CONNECTION_SHARE_ENDPOINT,
                address=self._connection_info.server_address,
                port=self._connection_info.server_port,
            ),
            id="connection-share-endpoint",
            markup=False,
        )
        yield Static(
            self.copy.text(UiText.CONNECTION_SHARE_WARNING_HIDDEN),
            id="connection-share-warning",
            markup=False,
        )
        yield Button(
            self.copy.text(UiText.CONNECTION_SHARE_REVEAL),
            id="reveal-connection-share",
        )

    @on(Button.Pressed, "#reveal-connection-share")
    async def reveal_share_uri(self, event: Button.Pressed) -> None:
        if self._revealed:
            return
        self._revealed = True
        self.query_one("#connection-share-warning", Static).update(
            self.copy.text(UiText.CONNECTION_SHARE_WARNING_REVEALED)
        )
        await event.button.remove()
        share_uri = TextArea(
            self._connection_info.share_uri,
            id="connection-share-uri",
            read_only=True,
            soft_wrap=True,
        )
        hide = Button(
            self.copy.text(UiText.CONNECTION_SHARE_HIDE),
            id="hide-connection-share",
        )
        await self.mount(
            Label(
                self.copy.text(UiText.CONNECTION_SHARE_LABEL),
                id="connection-share-label",
            ),
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
            self.copy.text(UiText.CONNECTION_SHARE_WARNING_HIDDEN_AFTER)
        )
