import hashlib
import json
import stat
from pathlib import Path

from textual.widgets import Button, Static

from sb_manager.application.host_readiness import HostAccessMode
from sb_manager.application.interface_preferences import (
    InterfacePreferences,
    InterfacePreferenceService,
)
from sb_manager.cli import create_app
from sb_manager.seams.runtime import RuntimeKind
from sb_manager.ui.app import ManagerApp, ManagerAppInterfaceTools
from sb_manager.ui.screens.settings import EffectiveSettings

PRIVATE_FILE_MODE = 0o600


class MemoryPreferenceStore:
    def __init__(self) -> None:
        self.preferences: InterfacePreferences | None = None

    def load(self) -> InterfacePreferences | None:
        return self.preferences

    def save(self, preferences: InterfacePreferences) -> None:
        self.preferences = preferences


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


async def test_operator_saved_appearance_is_restored_in_the_next_app_instance() -> None:
    store = MemoryPreferenceStore()
    first_app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            preference_service=InterfacePreferenceService(store=store)
        ),
    )

    async with first_app.run_test() as pilot:
        await pilot.press("s")
        await pilot.click("#toggle-color-scheme")

        assert first_app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：已保存，下次启动将继续使用浅色"
        )
        assert first_app.screen.query_one("#settings-safety", Static).content == (
            "外观偏好只写入当前用户的本地偏好文件，不会修改主机或 desired state。"
        )

    second_app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            preference_service=InterfacePreferenceService(store=store)
        ),
    )

    async with second_app.run_test() as pilot:
        assert not second_app.current_theme.dark

        await pilot.press("s")

        assert second_app.screen.query_one("#settings-appearance", Static).content == (
            "界面外观：浅色"
        )
        assert second_app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：已从偏好文件载入"
        )


async def test_settings_explain_effective_privileged_runtime_and_paths() -> None:
    app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            effective_settings=EffectiveSettings(
                host_access_mode=HostAccessMode.PRIVILEGED,
                runtime_kind=RuntimeKind.OPENRC,
                state_file=Path("/home/operator/.local/state/sing-box-manager/state.json"),
                config_file=None,
                transaction_directory=Path("/var/lib/sing-box-manager/incoming"),
            )
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


async def test_production_cli_restores_the_saved_appearance_and_discloses_its_path(
    tmp_path: Path,
) -> None:
    preferences_path = tmp_path / "config/sing-box-manager/preferences.json"
    arguments = [
        "--state-file",
        str(tmp_path / "state.json"),
        "--preferences-file",
        str(preferences_path),
    ]
    first_app = create_app(arguments)

    async with first_app.run_test() as pilot:
        await pilot.press("s")

        assert first_app.screen.query_one("#settings-preferences-file", Static).content == (
            f"界面偏好：{preferences_path}"
        )

        await pilot.click("#toggle-color-scheme")

    second_app = create_app(arguments)

    async with second_app.run_test() as pilot:
        assert not second_app.current_theme.dark

        await pilot.press("s")

        assert second_app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：已从偏好文件载入"
        )


async def test_unreadable_preferences_keep_the_tui_usable_without_overwriting_them(
    tmp_path: Path,
) -> None:
    preferences_path = tmp_path / "preferences.json"
    original = (
        b'{"schema_version": 2, "color_scheme": "light", "private_note": "do-not-disclose"}\n'
    )
    preferences_path.write_bytes(original)
    app = create_app(
        [
            "--state-file",
            str(tmp_path / "state.json"),
            "--preferences-file",
            str(preferences_path),
        ]
    )

    async with app.run_test() as pilot:
        assert app.current_theme.dark

        await pilot.press("s")

        assert app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：无法读取偏好文件，本次使用默认深色"
        )

        await pilot.click("#toggle-color-scheme")

        assert not app.current_theme.dark
        assert app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：本次已应用，但未能保存。下次启动可能恢复默认值"
        )
        visible_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "do-not-disclose" not in visible_text

    assert preferences_path.read_bytes() == original


async def test_operator_reviews_and_cancels_an_unreadable_preference_reset(
    tmp_path: Path,
) -> None:
    preferences_path = tmp_path / "preferences.json"
    original = (
        b'{"schema_version": 2, "color_scheme": "light", "private_note": "do-not-disclose"}\n'
    )
    preferences_path.write_bytes(original)
    app = create_app(
        [
            "--state-file",
            str(tmp_path / "state.json"),
            "--preferences-file",
            str(preferences_path),
        ]
    )

    async with app.run_test() as pilot:
        await pilot.press("s")

        assert str(app.screen.query_one("#review-preference-reset", Button).label) == (
            "审查并重置界面偏好"
        )

        await pilot.click("#review-preference-reset")

        assert app.screen.query_one("#preference-reset-title", Static).content == (
            "确认重置界面偏好"
        )
        assert app.screen.query_one("#preference-reset-fingerprint", Static).content == (
            f"待替换文件 SHA-256：{hashlib.sha256(original).hexdigest()}"
        )
        assert app.screen.query_one("#preference-reset-default", Static).content == (
            "重置结果：schema v1 · 深色外观"
        )
        assert app.screen.query_one("#preference-reset-safety", Static).content == (
            "确认后会先归档原字节，再只替换当前用户的界面偏好。"
            "不会修改 desired state、live configuration 或主机。"
        )
        visible_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "do-not-disclose" not in visible_text

        await pilot.press("escape")

        assert app.screen.query_one("#settings-title", Static).content == "设置"

    assert preferences_path.read_bytes() == original


async def test_operator_confirms_reset_and_the_default_is_restored_next_time(
    tmp_path: Path,
) -> None:
    preferences_path = tmp_path / "preferences.json"
    original = b'{"schema_version": 2, "color_scheme": "light"}\n'
    digest = hashlib.sha256(original).hexdigest()
    archive_path = preferences_path.with_name(f"{preferences_path.name}.rejected-{digest}.json")
    preferences_path.write_bytes(original)
    arguments = [
        "--state-file",
        str(tmp_path / "state.json"),
        "--preferences-file",
        str(preferences_path),
    ]
    app = create_app(arguments)

    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.click("#toggle-color-scheme")
        assert not app.current_theme.dark

        await pilot.click("#review-preference-reset")
        await pilot.click("#confirm-preference-reset")

        assert app.screen.query_one("#settings-title", Static).content == "设置"
        assert app.current_theme.dark
        assert app.screen.query_one("#settings-appearance", Static).content == "界面外观：深色"
        assert app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：已重置为深色，原文件已按 SHA-256 归档"
        )

    assert archive_path.read_bytes() == original
    assert stat.S_IMODE(archive_path.stat().st_mode) == PRIVATE_FILE_MODE
    assert json.loads(preferences_path.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "color_scheme": "dark",
    }

    restarted_app = create_app(arguments)

    async with restarted_app.run_test() as pilot:
        assert restarted_app.current_theme.dark
        await pilot.press("s")
        assert restarted_app.screen.query_one("#settings-persistence", Static).content == (
            "外观保存：已从偏好文件载入"
        )


async def test_preference_reset_refuses_bytes_changed_after_review(
    tmp_path: Path,
) -> None:
    preferences_path = tmp_path / "preferences.json"
    reviewed = b'{"schema_version": 2, "color_scheme": "light"}\n'
    changed = b'{"schema_version": 3, "color_scheme": "dark"}\n'
    reviewed_digest = hashlib.sha256(reviewed).hexdigest()
    preferences_path.write_bytes(reviewed)
    app = create_app(
        [
            "--state-file",
            str(tmp_path / "state.json"),
            "--preferences-file",
            str(preferences_path),
        ]
    )

    async with app.run_test() as pilot:
        await pilot.press("s")
        await pilot.click("#review-preference-reset")
        preferences_path.write_bytes(changed)

        await pilot.click("#confirm-preference-reset")
        await pilot.pause()

        assert app.screen.query_one("#preference-reset-error", Static).content == (
            "偏好文件在审阅后已变化，未覆盖任何内容。请返回设置重新审查。"
        )

        await pilot.press("escape")

        assert app.screen.query_one("#settings-title", Static).content == "设置"

    assert preferences_path.read_bytes() == changed
    archive_path = preferences_path.with_name(
        f"{preferences_path.name}.rejected-{reviewed_digest}.json"
    )
    assert not archive_path.exists()
