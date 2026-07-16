import pytest
from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.ui.app import ManagerApp


async def test_add_profile_starts_with_operator_purpose_instead_of_protocol_terms() -> None:
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")

        assert app.screen.query_one("#profile-purpose-title", Static).content == (
            "你主要想优化什么?"
        )
        assert str(app.screen.query_one("#purpose-general", Button).label) == "通用搭建 · 推荐"
        assert str(app.screen.query_one("#purpose-low-latency", Button).label) == (
            "移动网络与低延迟"
        )
        assert str(app.screen.query_one("#purpose-restricted-network", Button).label) == (
            "受限网络中的连接选择"
        )
        assert str(app.screen.query_one("#purpose-compatibility", Button).label) == (
            "兼容既有客户端"
        )
        assert str(app.screen.query_one("#choose-protocol-directly", Button).label) == (
            "直接选择协议 · 高级"
        )


async def test_general_purpose_shows_ranked_reasons_and_tradeoffs() -> None:
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#purpose-general")

        assert app.screen.query_one("#profile-recommendation-title", Static).content == (
            "通用搭建的推荐顺序"
        )
        assert app.screen.query_one("#recommendation-0-name", Static).content == (
            "1. VLESS Reality · 首选"
        )
        assert app.screen.query_one("#recommendation-0-reason", Static).content == (
            "适合原因：无需管理自有 TLS 证书，向导所需信息最少"
        )
        assert app.screen.query_one("#recommendation-0-tradeoff", Static).content == (
            "需要注意：客户端必须支持 VLESS Reality"
        )
        assert str(app.screen.query_one("#select-recommendation-0", Button).label) == (
            "使用 VLESS Reality"
        )
        assert app.screen.query_one("#profile-recommendation-caveat", Static).content == (
            "推荐只帮助缩小选择，不承诺连通性或适用于所有网络。"
        )


@pytest.mark.parametrize(
    ("purpose_selector", "expected_title", "expected_first_choice"),
    (
        ("#purpose-low-latency", "移动网络与低延迟的推荐顺序", "1. Hysteria2 · 首选"),
        (
            "#purpose-restricted-network",
            "受限网络中的连接选择的推荐顺序",
            "1. VLESS Reality · 首选",
        ),
        ("#purpose-compatibility", "兼容既有客户端的推荐顺序", "1. Trojan · 首选"),
    ),
)
async def test_each_non_default_purpose_opens_its_own_ranking(
    purpose_selector: str,
    expected_title: str,
    expected_first_choice: str,
) -> None:
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        app.screen.query_one(purpose_selector, Button).press()
        await pilot.pause()

        assert app.screen.query_one("#profile-recommendation-title", Static).content == (
            expected_title
        )
        assert app.screen.query_one("#recommendation-0-name", Static).content == (
            expected_first_choice
        )


async def test_recommended_variant_opens_the_existing_guided_profile_form() -> None:
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test() as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#purpose-general")
        await pilot.click("#select-recommendation-0")
        await pilot.pause()

        assert app.screen.query_one("#reality-form-title", Static).content == ("配置 VLESS Reality")
        assert app.screen.query_one("#reality-guidance", Static).content == (
            "适合大多数网络环境。UUID、密钥和兼容站点将自动生成。"
        )


async def test_advanced_operator_can_still_choose_an_exact_protocol_variant() -> None:
    app = ManagerApp(manager=Manager(state_store=MemoryStateStore()))

    async with app.run_test(size=(100, 60)) as pilot:
        await pilot.click("#create-first-profile")
        await pilot.click("#choose-protocol-directly")

        assert app.screen.query_one("#protocol-selection-title", Static).content == ("直接选择协议")
        assert app.screen.query_one("#protocol-selection-guidance", Static).content == (
            "这里不再排序; 请只选择你确认客户端和网络都支持的协议。"
        )
        assert str(app.screen.query_one("#protocol-vmess-grpc", Button).label) == (
            "VMess TLS · gRPC 兼容"
        )

        await pilot.click("#protocol-vmess-grpc")
        await pilot.pause()

        assert app.screen.query_one("#vmess-grpc-form-title", Static).content == (
            "配置 VMess TLS gRPC"
        )
