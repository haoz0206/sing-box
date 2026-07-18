import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label, TextArea

from sb_manager.protocols.catalog import (
    ConnectionPayload,
    ConnectionPayloadKind,
    ProfileConnectionInfo,
)
from sb_manager.ui.connection_share import ConnectionSharePanel


class ConnectionShareApp(App[None]):
    def __init__(self, connection_info: ProfileConnectionInfo) -> None:
        super().__init__()
        self.connection_info = connection_info

    def compose(self) -> ComposeResult:
        yield ConnectionSharePanel(self.connection_info)


@pytest.mark.parametrize(
    ("payload_kind", "label", "content"),
    (
        (ConnectionPayloadKind.URI, "连接 URI", "vless://credential-bearing-uri"),
        (
            ConnectionPayloadKind.SURGE_POLICY,
            "Surge 策略",
            "snell = snell, vpn.example.com, 443, psk=credential-bearing-policy",
        ),
    ),
)
async def test_connection_payload_requires_explicit_reveal_and_can_be_hidden_again(
    payload_kind: ConnectionPayloadKind,
    label: str,
    content: str,
) -> None:
    connection_info = ProfileConnectionInfo(
        server_address="vpn.example.com",
        server_port=443,
        payload=ConnectionPayload(
            kind=payload_kind,
            content=content,
        ),
    )
    app = ConnectionShareApp(connection_info)

    async with app.run_test() as pilot:
        assert len(app.screen.query("#connection-share-payload")) == 0
        assert len(app.screen.query("#connection-share-label")) == 0

        await pilot.click("#reveal-connection-share")

        assert app.screen.query_one("#connection-share-label", Label).content == label
        payload = app.screen.query_one("#connection-share-payload", TextArea)
        assert payload.text == content
        assert payload.read_only is True

        await pilot.click("#hide-connection-share")

        assert len(app.screen.query("#connection-share-payload")) == 0
        assert len(app.screen.query("#connection-share-label")) == 0
        assert len(app.screen.query("#reveal-connection-share")) == 0
        assert len(app.screen.query("#hide-connection-share")) == 0
