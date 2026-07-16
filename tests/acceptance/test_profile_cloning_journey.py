from collections.abc import Iterator
from contextlib import contextmanager

from textual.widgets import Button, Input, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.application.profile_cloning import ProfileCloningService
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools

SOURCE_REVISION = 7
CLONED_REVISION = 8


class ImmediateApplyLock:
    @contextmanager
    def acquire(self) -> Iterator[None]:
        yield


class FixedProfileDetailsReader:
    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        assert profile_id == "profile-1"
        return ProfileDetails(
            profile_id=profile_id,
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=ProfileStatus.APPLIED,
            listen_port=443,
            server_address="vpn.example.com",
            connection_info=None,
        )


def source_profile() -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="vpn.example.com",
    )


def create_app() -> tuple[ManagerApp, MemoryStateStore]:
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=SOURCE_REVISION,
            profiles=(source_profile(),),
            expected_config_sha256="a" * 64,
        )
    )
    return (
        ManagerApp(
            manager=Manager(state_store=state_store),
            host_tools=ManagerAppHostTools(
                profile_details_reader=FixedProfileDetailsReader(),
                profile_cloner=ProfileCloningService(
                    state_store=state_store,
                    mutation_lock=ImmediateApplyLock(),
                ),
            ),
        ),
        state_store,
    )


async def test_operator_creates_a_secret_free_draft_from_profile_details() -> None:
    app, state_store = create_app()

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        assert str(app.screen.query_one("#clone-profile", Button).label) == ("以此配置为模板")

        await pilot.click("#clone-profile")

        name_input = app.screen.query_one("#profile-clone-name", Input)
        assert name_input.value == "手机 副本"
        assert app.screen.query_one("#profile-clone-copied", Static).content == (
            "将复用：协议和服务器地址"
        )
        assert app.screen.query_one("#profile-clone-reset", Static).content == (
            "将重置：认证凭据、监听端口和运行状态，新配置保存为未应用草案。"
        )
        assert state_store.load().revision == SOURCE_REVISION

        name_input.value = "平板"
        await pilot.click("#review-profile-clone")

        assert app.screen.query_one("#profile-clone-title", Static).content == ("确认模板草案")
        assert app.screen.query_one("#profile-clone-summary", Static).content == ("手机 → 平板")
        assert state_store.load().revision == SOURCE_REVISION

        await pilot.click("#confirm-profile-clone")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-title", Static).content == "草案已创建"
        assert app.screen.query_one("#profile-clone-result", Static).content == (
            "平板 · desired state revision 8"
        )
        clone = state_store.load().profiles[-1]
        assert clone.profile_name == "平板"
        assert clone.status is ProfileStatus.DRAFT
        assert clone.protocol_material is None
        assert clone.listen_port is None

        await pilot.click("#finish-profile-clone")
        await pilot.pause()

        assert "平板" in str(app.screen.query_one("#profile-1", Static).content)
        assert "草案" in str(app.screen.query_one("#profile-1", Static).content)


async def test_duplicate_clone_name_stays_in_review_without_mutating_state() -> None:
    app, state_store = create_app()

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        app.screen.query_one("#profile-clone-name", Input).value = "手机"

        await pilot.click("#review-profile-clone")

        assert app.screen.query_one("#profile-clone-error", Static).content == (
            "配置名称已存在：手机"
        )
        assert app.screen.query_one("#confirm-profile-clone", Button).has_class("hidden")
        assert state_store.load().revision == SOURCE_REVISION


async def test_stale_clone_confirmation_keeps_actionable_guidance() -> None:
    app, state_store = create_app()

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        await pilot.click("#review-profile-clone")
        state_store.save(
            ManagedInstallation(
                schema_version=1,
                revision=CLONED_REVISION,
                profiles=(source_profile(),),
                expected_config_sha256="a" * 64,
            )
        )

        await pilot.click("#confirm-profile-clone")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-error", Static).content == (
            "desired state 已变化，请返回配置详情后重新审阅模板。"
        )
        assert state_store.load().profiles == (source_profile(),)
