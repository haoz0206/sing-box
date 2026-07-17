from typing import cast

from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.ui.app import ManagerApp, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class NetworkMarkerCatalog:
    """Render markers for the read-only Network inventory journey."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "network.title": "目录网络概览",
            "network.safety": "目录只读网络意图",
            "network.empty": "目录暂无网络意图",
            "network.port.automatic": "目录自动端口",
            "network.state.enabled": "目录已启用",
            "network.state.paused": "目录已暂停",
            "network.state.draft": "目录草案",
            "network.public_address.title": "目录公开地址",
            "network.public_address.unset": "目录地址未设置",
        }
        if key.value == "network.listener.summary":
            return f"目录监听<{values['enabled']}|{values['paused']}|{values['draft']}>"
        if key.value == "network.port.fixed":
            return f"目录端口<{values['port']}>"
        if key.value == "network.listener.row":
            return (
                f"目录监听行<{values['name']}|{values['transports']}|"
                f"{values['port']}|{values['state']}>"
            )
        if key.value == "network.public_address.row":
            return f"目录地址行<{values['name']}|{values['address']}>"
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


async def test_operator_opens_a_read_only_empty_network_workspace() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        assert str(app.screen.query_one("#open-network", Button).label) == "查看网络概览"

        await pilot.click("#open-network")

        assert app.screen.query_one("#network-workspace-title", Static).content == "网络概览"
        assert app.screen.query_one("#network-workspace-empty", Static).content == (
            "尚无配置，因此没有监听端口或公开地址意图。"
        )
        assert app.screen.query_one("#network-firewall-policy", Static).content == (
            "只读视图：不会探测网络或修改防火墙。"
        )
        assert list(app.screen.query("#manage-firewall")) == []


async def test_empty_network_workspace_copy_comes_from_catalog() -> None:
    app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, NetworkMarkerCatalog())
        )
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-network")

        assert app.screen.query_one("#network-workspace-title", Static).content == ("目录网络概览")
        assert app.screen.query_one("#network-firewall-policy", Static).content == (
            "目录只读网络意图"
        )
        assert app.screen.query_one("#network-workspace-empty", Static).content == (
            "目录暂无网络意图"
        )


async def test_network_workspace_explains_each_profile_network_intent() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=3,
        profiles=(
            ManagedProfile(
                profile_id="profile-phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                server_address="proxy.example.com",
            ),
            ManagedProfile(
                profile_id="profile-backup",
                profile_name="备用",
                protocol=ProtocolKind.HYSTERIA2,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                enabled=False,
                server_address="edge.example.com",
            ),
            ManagedProfile(
                profile_id="profile-tablet",
                profile_name="平板",
                protocol=ProtocolKind.TUIC,
                listen_port=None,
                port_selection=PortSelection.AUTOMATIC,
                status=ProfileStatus.DRAFT,
                server_address="203.0.113.10",
            ),
        ),
    )
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore(installation)))

    async with app.run_test() as pilot:
        await pilot.press("n")

        assert app.screen.query_one("#network-listener-summary", Static).content == (
            "监听意图：1 启用 · 1 暂停 · 1 草案"
        )
        assert app.screen.query_one("#network-listener-0", Static).content == (
            "手机 · TCP · 端口 443 · 已启用"
        )
        assert app.screen.query_one("#network-listener-1", Static).content == (
            "备用 · UDP · 端口 8443 · 已暂停"
        )
        assert app.screen.query_one("#network-listener-2", Static).content == (
            "平板 · UDP · 应用时自动选择端口 · 草案"
        )
        assert app.screen.query_one("#network-public-address-0", Static).content == (
            "手机 · proxy.example.com"
        )
        assert app.screen.query_one("#network-public-address-1", Static).content == (
            "备用 · edge.example.com"
        )
        assert app.screen.query_one("#network-public-address-2", Static).content == (
            "平板 · 203.0.113.10"
        )


async def test_populated_network_evidence_copy_comes_from_catalog_and_stays_literal() -> None:
    installation = ManagedInstallation(
        schema_version=1,
        revision=4,
        profiles=(
            ManagedProfile(
                profile_id="profile-phone",
                profile_name="[手机]",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                server_address="[proxy.example.com]",
            ),
            ManagedProfile(
                profile_id="profile-backup",
                profile_name="备用",
                protocol=ProtocolKind.HYSTERIA2,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                enabled=False,
            ),
            ManagedProfile(
                profile_id="profile-tablet",
                profile_name="平板",
                protocol=ProtocolKind.TUIC,
                listen_port=None,
                port_selection=PortSelection.AUTOMATIC,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation)),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, NetworkMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.press("n")

        assert app.screen.query_one("#network-listener-summary", Static).content == (
            "目录监听<1|1|1>"
        )
        assert app.screen.query_one("#network-listener-0", Static).content == (
            "目录监听行<[手机]|TCP|目录端口<443>|目录已启用>"
        )
        assert app.screen.query_one("#network-listener-1", Static).content == (
            "目录监听行<备用|UDP|目录端口<8443>|目录已暂停>"
        )
        assert app.screen.query_one("#network-listener-2", Static).content == (
            "目录监听行<平板|UDP|目录自动端口|目录草案>"
        )
        assert app.screen.query_one("#network-public-address-title", Static).content == (
            "目录公开地址"
        )
        assert app.screen.query_one("#network-public-address-0", Static).content == (
            "目录地址行<[手机]|[proxy.example.com]>"
        )
        assert app.screen.query_one("#network-public-address-1", Static).content == (
            "目录地址行<备用|目录地址未设置>"
        )
        assert app.screen.query_one("#network-public-address-2", Static).content == (
            "目录地址行<平板|目录地址未设置>"
        )
