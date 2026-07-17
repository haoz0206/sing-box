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


class NetworkScreen(Screen[None]):
    """Present network intent without probing or changing the managed host."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, inventory: NetworkInventory) -> None:
        super().__init__()
        self.inventory = inventory

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="network-workspace"):
            yield Static("网络概览", id="network-workspace-title", markup=False)
            yield Static(
                "只读视图：不会探测网络或修改防火墙。",
                id="network-firewall-policy",
                markup=False,
            )
            if not self.inventory.profiles:
                yield Static(
                    "尚无配置，因此没有监听端口或公开地址意图。",
                    id="network-workspace-empty",
                    markup=False,
                )
            else:
                yield Static(
                    (
                        f"监听意图：{self.inventory.enabled_count} 启用 · "
                        f"{self.inventory.paused_count} 暂停 · "
                        f"{self.inventory.draft_count} 草案"
                    ),
                    id="network-listener-summary",
                    markup=False,
                )
                for index, profile in enumerate(self.inventory.profiles):
                    transports = "/".join(
                        transport.value.upper() for transport in profile.transports
                    )
                    port = (
                        "应用时自动选择端口"
                        if profile.listen_port is None
                        else f"端口 {profile.listen_port}"
                    )
                    state = {
                        NetworkProfileState.ENABLED: "已启用",
                        NetworkProfileState.PAUSED: "已暂停",
                        NetworkProfileState.DRAFT: "草案",
                    }[profile.state]
                    yield Static(
                        f"{profile.profile_name} · {transports} · {port} · {state}",
                        id=f"network-listener-{index}",
                        markup=False,
                    )
                yield Static("公开地址", id="network-public-address-title", markup=False)
                for index, profile in enumerate(self.inventory.profiles):
                    yield Static(
                        f"{profile.profile_name} · {profile.public_address or '尚未设置'}",
                        id=f"network-public-address-{index}",
                        markup=False,
                    )
        yield Footer()
