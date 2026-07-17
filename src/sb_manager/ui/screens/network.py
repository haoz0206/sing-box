"""Read-only workspace for network intent in one desired-state snapshot."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from sb_manager.application.network_inventory import (
    NetworkInventory,
    NetworkProfileState,
)
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText

NETWORK_STATE_TEXT = {
    NetworkProfileState.ENABLED: UiText.NETWORK_STATE_ENABLED,
    NetworkProfileState.PAUSED: UiText.NETWORK_STATE_PAUSED,
    NetworkProfileState.DRAFT: UiText.NETWORK_STATE_DRAFT,
}


class NetworkScreen(Screen[None]):
    """Present network intent without probing or changing the managed host."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        inventory: NetworkInventory,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.inventory = inventory
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="network-workspace"):
            yield Static(
                self.copy.text(UiText.NETWORK_TITLE),
                id="network-workspace-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.NETWORK_SAFETY),
                id="network-firewall-policy",
                markup=False,
            )
            if not self.inventory.profiles:
                yield Static(
                    self.copy.text(UiText.NETWORK_EMPTY),
                    id="network-workspace-empty",
                    markup=False,
                )
            else:
                yield Static(
                    self.copy.text(
                        UiText.NETWORK_LISTENER_SUMMARY,
                        enabled=self.inventory.enabled_count,
                        paused=self.inventory.paused_count,
                        draft=self.inventory.draft_count,
                    ),
                    id="network-listener-summary",
                    markup=False,
                )
                for index, profile in enumerate(self.inventory.profiles):
                    transports = "/".join(
                        transport.value.upper() for transport in profile.transports
                    )
                    port = (
                        self.copy.text(UiText.NETWORK_PORT_AUTOMATIC)
                        if profile.listen_port is None
                        else self.copy.text(
                            UiText.NETWORK_PORT_FIXED,
                            port=profile.listen_port,
                        )
                    )
                    state = self.copy.text(NETWORK_STATE_TEXT[profile.state])
                    yield Static(
                        self.copy.text(
                            UiText.NETWORK_LISTENER_ROW,
                            name=profile.profile_name,
                            transports=transports,
                            port=port,
                            state=state,
                        ),
                        id=f"network-listener-{index}",
                        markup=False,
                    )
                yield Static(
                    self.copy.text(UiText.NETWORK_PUBLIC_ADDRESS_TITLE),
                    id="network-public-address-title",
                    markup=False,
                )
                for index, profile in enumerate(self.inventory.profiles):
                    yield Static(
                        self.copy.text(
                            UiText.NETWORK_PUBLIC_ADDRESS_ROW,
                            name=profile.profile_name,
                            address=profile.public_address
                            or self.copy.text(UiText.NETWORK_PUBLIC_ADDRESS_UNSET),
                        ),
                        id=f"network-public-address-{index}",
                        markup=False,
                    )
        yield Footer()
