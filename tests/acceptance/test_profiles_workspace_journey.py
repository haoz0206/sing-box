from typing import cast

from textual.widgets import Button, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.application.profile_apply import (
    ApplyProfileRequest,
    ApplyProfileResult,
)
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools, ManagerAppInterfaceTools
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText


class ProfilesMarkerCatalog:
    """Render markers for Profiles copy while delegating every established key."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "profiles.title": "目录配置工作区",
            "profiles.add": "目录添加配置",
        }
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


def installation_with_two_profiles() -> ManagedInstallation:
    return ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-phone",
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
            ),
            ManagedProfile(
                profile_id="profile-tablet",
                profile_name="平板",
                protocol=ProtocolKind.SHADOWSOCKS,
                listen_port=None,
                port_selection=PortSelection.AUTOMATIC,
                status=ProfileStatus.DRAFT,
            ),
        ),
    )


class FixedProfileDetailsReader:
    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        assert profile_id == "profile-phone"
        return ProfileDetails(
            profile_id=profile_id,
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=ProfileStatus.APPLIED,
            listen_port=4433,
            server_address="proxy.example.com",
            connection_info=None,
        )


class NeverCalledProfileApplier:
    def apply_profile(self, request: ApplyProfileRequest) -> ApplyProfileResult:
        raise AssertionError("opening draft confirmation must not apply a profile")


async def test_dashboard_summary_opens_the_complete_profiles_workspace() -> None:
    app = ManagerApp(
        manager=Manager(
            state_store=MemoryStateStore(installation_with_two_profiles()),
        )
    )

    async with app.run_test() as pilot:
        assert app.screen.query_one("#profile-summary", Static).content == (
            "配置：1 在线 · 0 已暂停 · 1 草案"
        )
        assert list(app.screen.query("#profile-0")) == []
        assert str(app.screen.query_one("#open-profiles", Button).label) == "管理配置"

        await pilot.click("#open-profiles")

        assert app.screen.query_one("#profiles-workspace-title", Static).content == "配置工作区"
        assert app.screen.query_one("#profile-0", Static).content == (
            "手机 · VLESS Reality · 在线 · 端口 4433"
        )
        assert app.screen.query_one("#profile-1", Static).content == (
            "平板 · Shadowsocks 2022 · 草案 · 自动选择端口"
        )
        assert str(app.screen.query_one("#add-profile", Button).label) == "添加配置"


async def test_profiles_workspace_copy_comes_from_the_interface_catalog() -> None:
    app = ManagerApp(
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, ProfilesMarkerCatalog())
        )
    )

    async with app.run_test() as pilot:
        await pilot.press("p")

        assert app.screen.query_one("#profiles-workspace-title", Static).content == (
            "目录配置工作区"
        )
        assert str(app.screen.query_one("#add-profile", Button).label) == "目录添加配置"


async def test_profiles_workspace_explains_its_effect_boundary() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.press("p")

        assert app.screen.query_one("#profiles-workspace-safety", Static).content == (
            "当前清单只读。任何配置变更都会先显示计划，并在执行前要求明确确认。"
        )


async def test_empty_profiles_workspace_starts_the_guided_add_journey() -> None:
    app = ManagerApp()

    async with app.run_test() as pilot:
        await pilot.press("p")

        assert app.screen.query_one("#profiles-workspace-empty", Static).content == (
            "尚未创建代理配置。先说明使用目的，再选择合适的协议。"
        )

        await pilot.click("#add-profile")

        assert app.screen.query_one("#profile-purpose-title", Static).content == "你主要想优化什么?"


async def test_empty_dashboard_has_one_primary_creation_action() -> None:
    app = ManagerApp()

    async with app.run_test():
        assert str(app.screen.query_one("#dashboard-primary-action", Button).label) == (
            "创建第一个配置"
        )
        assert list(app.screen.query("#create-first-profile")) == []
        assert str(app.screen.query_one("#open-profiles", Button).label) == "管理配置"


async def test_operator_opens_profile_details_and_returns_to_the_workspace() -> None:
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation_with_two_profiles())),
        host_tools=ManagerAppHostTools(
            profile_details_reader=FixedProfileDetailsReader(),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")

        assert app.screen.query_one("#profile-details-title", Static).content == "配置详情"
        assert app.screen.query_one("#profile-details-name", Static).content == "名称：手机"

        await pilot.press("escape")

        assert app.screen.query_one("#profiles-workspace-title", Static).content == "配置工作区"


async def test_operator_reviews_one_exact_draft_from_the_profiles_workspace() -> None:
    app = ManagerApp(
        manager=Manager(state_store=MemoryStateStore(installation_with_two_profiles())),
        profile_applier=NeverCalledProfileApplier(),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")

        assert list(app.screen.query("#apply-profile-0")) == []
        assert str(app.screen.query_one("#apply-profile-1", Button).label) == "应用草案"

        await pilot.click("#apply-profile-1")

        assert app.screen.query_one("#apply-confirm-profile", Static).content == "配置：平板"

        await pilot.press("escape")

        assert app.screen.query_one("#profiles-workspace-title", Static).content == "配置工作区"
