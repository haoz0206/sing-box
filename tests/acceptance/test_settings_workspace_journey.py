from pathlib import Path

from textual.widgets import Button, Static

from sb_manager.application.host_readiness import HostAccessMode
from sb_manager.seams.runtime import RuntimeKind
from sb_manager.ui.app import ManagerApp
from sb_manager.ui.screens.settings import EffectiveSettings


async def test_operator_changes_appearance_for_the_current_session() -> None:
    app = ManagerApp()
    app.theme = "textual-dark"

    async with app.run_test() as pilot:
        assert str(app.screen.query_one("#open-settings", Button).label) == "打开设置"

        await pilot.click("#open-settings")

        assert app.screen.query_one("#settings-title", Static).content == "设置"
        assert app.screen.query_one("#settings-language", Static).content == "界面语言：简体中文"
        assert app.screen.query_one("#settings-appearance", Static).content == "界面外观：深色"
        assert app.screen.query_one("#settings-safety", Static).content == (
            "外观变更仅影响本次 TUI 会话，不会修改主机或 desired state。"
        )

        await pilot.click("#toggle-color-scheme")

        assert app.screen.query_one("#settings-appearance", Static).content == "界面外观：浅色"
        assert not app.current_theme.dark
        assert str(app.screen.query_one("#toggle-color-scheme", Button).label) == "切换为深色"

        await pilot.press("escape")
        await pilot.press("s")

        assert app.screen.query_one("#settings-appearance", Static).content == "界面外观：浅色"


async def test_settings_explain_effective_privileged_runtime_and_paths() -> None:
    app = ManagerApp(
        effective_settings=EffectiveSettings(
            host_access_mode=HostAccessMode.PRIVILEGED,
            runtime_kind=RuntimeKind.OPENRC,
            state_file=Path("/home/operator/.local/state/sing-box-manager/state.json"),
            config_file=None,
            transaction_directory=Path("/var/lib/sing-box-manager/incoming"),
        )
    )

    async with app.run_test() as pilot:
        await pilot.press("s")

        assert app.screen.query_one("#settings-update-policy", Static).content == (
            "核心更新：手动指定确切版本 · 不自动更新"
        )
        assert app.screen.query_one("#settings-host-access", Static).content == (
            "主机变更：最小权限 helper"
        )
        assert app.screen.query_one("#settings-runtime", Static).content == ("服务管理：OpenRC")
        assert app.screen.query_one("#settings-state-file", Static).content == (
            "desired state：/home/operator/.local/state/sing-box-manager/state.json"
        )
        assert app.screen.query_one("#settings-config-file", Static).content == (
            "live configuration：由最小权限 helper 的固定策略管理"
        )
        assert app.screen.query_one("#settings-transaction-directory", Static).content == (
            "事务提交目录：/var/lib/sing-box-manager/incoming"
        )
