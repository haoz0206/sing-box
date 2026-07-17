from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from textual.widgets import Button, Input, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager
from sb_manager.application.profile_cloning import (
    PlanProfileCloneRequest,
    ProfileClonePlan,
    ProfileCloner,
    ProfileCloneResult,
    ProfileCloningService,
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

SOURCE_REVISION = 7
CLONED_REVISION = 8
EXPECTED_PROFILE_COUNT_AFTER_CLONE = 2


class ProfileCloneMarkerCatalog:
    """Render markers across the nested profile-clone journey."""

    def text(self, key: UiText, /, **values: object) -> str:
        markers = {
            "profile_clone.form.title": "目录创建模板草案",
            "profile_clone.facet.protocol": "目录协议",
            "profile_clone.facet.server_address": "目录地址",
            "profile_clone.facet.separator": "+",
            "profile_clone.review.title": "目录确认模板草案",
            "profile_clone.result.title": "目录草案创建完成",
            "profile_clone.planning.title": "目录无法准备模板",
            "profile_clone.planning.details": "目录隐藏计划错误",
            "profile_clone.planning.safety": "目录计划恢复指引",
            "profile_clone.operational.title": "目录无法确认草案结果",
            "profile_clone.operational.details": "目录隐藏提交错误",
            "profile_clone.operational.safety": "目录未知结果恢复指引",
        }
        if key.value == "profile_clone.facet.conjunction":
            return f"{values['prefix']}&{values['last']}"
        if key.value == "profile_clone.form.copied":
            return f"目录复用<{values['facets']}>"
        if marker := markers.get(key.value):
            return marker
        return SIMPLIFIED_CHINESE.text(key, **values)


class ImmediateApplyLock:
    @contextmanager
    def acquire(self) -> Iterator[None]:
        yield


class FixedProfileDetailsReader:
    def __init__(self, profile_name: str = "手机") -> None:
        self.profile_name = profile_name

    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        assert profile_id == "profile-1"
        return ProfileDetails(
            profile_id=profile_id,
            profile_name=self.profile_name,
            protocol=ProtocolKind.VLESS_REALITY,
            status=ProfileStatus.APPLIED,
            listen_port=443,
            server_address="vpn.example.com",
            connection_info=None,
        )


class UnexpectedPlanningProfileCloner:
    def plan(self, request: object) -> object:
        raise RuntimeError("token=private-profile-clone-planning-error")

    def clone(self, plan: object, *, confirmed: bool) -> object:
        raise AssertionError("a failed clone plan must not be confirmed")


class UnexpectedReviewProfileCloner:
    def __init__(self, delegate: ProfileCloner) -> None:
        self.delegate = delegate

    def plan(self, request: PlanProfileCloneRequest) -> ProfileClonePlan:
        if request.profile_name is not None:
            raise RuntimeError("token=private-profile-clone-review-error")
        return self.delegate.plan(request)

    def clone(
        self,
        plan: ProfileClonePlan,
        *,
        confirmed: bool,
    ) -> ProfileCloneResult:
        return self.delegate.clone(plan, confirmed=confirmed)


class UnexpectedProfileCloner:
    def __init__(self, delegate: ProfileCloner) -> None:
        self.delegate = delegate

    def plan(self, request: PlanProfileCloneRequest) -> ProfileClonePlan:
        return self.delegate.plan(request)

    def clone(
        self,
        plan: ProfileClonePlan,
        *,
        confirmed: bool,
    ) -> ProfileCloneResult:
        assert confirmed
        raise RuntimeError("token=private-profile-clone-worker-error")


def source_profile(profile_name: str = "手机") -> ManagedProfile:
    return ManagedProfile(
        profile_id="profile-1",
        profile_name=profile_name,
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=443,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        server_address="vpn.example.com",
    )


def create_app(
    *,
    copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    profile_cloner: ProfileCloner | None = None,
    source_name: str = "手机",
) -> tuple[ManagerApp, MemoryStateStore]:
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=SOURCE_REVISION,
            profiles=(source_profile(source_name),),
            expected_config_sha256="a" * 64,
        )
    )
    return (
        ManagerApp(
            manager=Manager(state_store=state_store),
            host_tools=ManagerAppHostTools(
                profile_details_reader=FixedProfileDetailsReader(source_name),
                profile_cloner=profile_cloner
                or ProfileCloningService(
                    state_store=state_store,
                    mutation_lock=ImmediateApplyLock(),
                ),
            ),
            interface_tools=ManagerAppInterfaceTools(copy_catalog=copy_catalog),
        ),
        state_store,
    )


async def test_profile_clone_copy_catalog_flows_from_details_to_form() -> None:
    app, _ = create_app(
        copy_catalog=cast(CopyCatalog, ProfileCloneMarkerCatalog()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")

        assert app.screen.query_one("#profile-clone-title", Static).content == ("目录创建模板草案")
        assert app.screen.query_one("#profile-clone-copied", Static).content == (
            "目录复用<目录协议&目录地址>"
        )


async def test_profile_clone_copy_catalog_flows_through_review_and_result() -> None:
    app, _ = create_app(
        copy_catalog=cast(CopyCatalog, ProfileCloneMarkerCatalog()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        app.screen.query_one("#profile-clone-name", Input).value = "平板"
        await pilot.click("#review-profile-clone")

        assert app.screen.query_one("#profile-clone-title", Static).content == ("目录确认模板草案")

        await pilot.click("#confirm-profile-clone")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-title", Static).content == ("目录草案创建完成")


async def test_profile_clone_copy_catalog_reaches_planning_failure() -> None:
    app, _ = create_app(
        copy_catalog=cast(CopyCatalog, ProfileCloneMarkerCatalog()),
        profile_cloner=cast(ProfileCloner, UnexpectedPlanningProfileCloner()),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")

        assert app.screen.query_one("#profile-clone-planning-error-title", Static).content == (
            "目录无法准备模板"
        )
        assert app.screen.query_one("#profile-clone-planning-error-details", Static).content == (
            "目录隐藏计划错误"
        )
        assert app.screen.query_one("#profile-clone-planning-error-safety", Static).content == (
            "目录计划恢复指引"
        )


async def test_profile_clone_values_and_results_render_as_literal_plain_text() -> None:
    app, _ = create_app(source_name="[bold]手机[/bold]")

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")

        source = app.screen.query_one("#profile-clone-source", Static)
        assert source.content == "模板：[bold]手机[/bold]"
        assert source.render().plain == source.content

        app.screen.query_one("#profile-clone-name", Input).value = "[bold]平板[/bold]"
        await pilot.click("#review-profile-clone")

        summary = app.screen.query_one("#profile-clone-summary", Static)
        assert summary.content == "[bold]手机[/bold] → [bold]平板[/bold]"
        assert summary.render().plain == summary.content

        await pilot.click("#confirm-profile-clone")
        await pilot.pause()

        result = app.screen.query_one("#profile-clone-result", Static)
        assert result.content == "[bold]平板[/bold] · desired state revision 8"
        assert result.render().plain == result.content


async def test_operator_creates_a_secret_free_draft_from_profile_details() -> None:
    app, state_store = create_app()

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
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

        assert app.screen.query_one("#profile-summary", Static).content == (
            "配置：1 在线 · 0 已暂停 · 1 草案"
        )
        await pilot.click("#open-profiles")
        assert "平板" in str(app.screen.query_one("#profile-1", Static).content)
        assert "草案" in str(app.screen.query_one("#profile-1", Static).content)


async def test_duplicate_clone_name_stays_in_review_without_mutating_state() -> None:
    app, state_store = create_app()

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        app.screen.query_one("#profile-clone-name", Input).value = "手机"

        await pilot.click("#review-profile-clone")

        assert app.screen.query_one("#profile-clone-error", Static).content == (
            "配置名称已存在：手机"
        )
        assert app.screen.query_one("#confirm-profile-clone", Button).has_class("hidden")
        assert state_store.load().revision == SOURCE_REVISION


async def test_unexpected_clone_planning_failure_is_safe_and_not_disclosed() -> None:
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=SOURCE_REVISION,
            profiles=(source_profile(),),
            expected_config_sha256="a" * 64,
        )
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=FixedProfileDetailsReader(),
            profile_cloner=UnexpectedPlanningProfileCloner(),
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-planning-error-title", Static).content == (
            "无法准备配置模板"
        )
        assert app.screen.query_one("#profile-clone-planning-error-details", Static).content == (
            "读取配置模板计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-clone-planning-error-safety", Static).content == (
            "尚未创建草案。请返回配置列表，重新打开详情后再试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-clone-planning-error" not in rendered_text
        assert state_store.load().revision == SOURCE_REVISION


async def test_unexpected_clone_review_failure_is_safe_and_not_disclosed() -> None:
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=SOURCE_REVISION,
            profiles=(source_profile(),),
            expected_config_sha256="a" * 64,
        )
    )
    cloner = UnexpectedReviewProfileCloner(
        ProfileCloningService(
            state_store=state_store,
            mutation_lock=ImmediateApplyLock(),
        )
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=FixedProfileDetailsReader(),
            profile_cloner=cloner,
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        app.screen.query_one("#profile-clone-name", Input).value = "平板"
        await pilot.click("#review-profile-clone")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-planning-error-title", Static).content == (
            "无法准备配置模板"
        )
        assert app.screen.query_one("#profile-clone-planning-error-details", Static).content == (
            "读取配置模板计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-clone-review-error" not in rendered_text
        assert state_store.load().revision == SOURCE_REVISION


async def test_unexpected_clone_failure_is_unknown_and_not_disclosed() -> None:
    state_store = MemoryStateStore(
        ManagedInstallation(
            schema_version=1,
            revision=SOURCE_REVISION,
            profiles=(source_profile(),),
            expected_config_sha256="a" * 64,
        )
    )
    cloner = UnexpectedProfileCloner(
        ProfileCloningService(
            state_store=state_store,
            mutation_lock=ImmediateApplyLock(),
        )
    )
    app = ManagerApp(
        manager=Manager(state_store=state_store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=FixedProfileDetailsReader(),
            profile_cloner=cloner,
        ),
        interface_tools=ManagerAppInterfaceTools(
            copy_catalog=cast(CopyCatalog, ProfileCloneMarkerCatalog())
        ),
    )

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
        await pilot.click("#view-profile-0")
        await pilot.click("#clone-profile")
        app.screen.query_one("#profile-clone-name", Input).value = "平板"
        await pilot.click("#review-profile-clone")
        await pilot.click("#confirm-profile-clone")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-error-title", Static).content == (
            "目录无法确认草案结果"
        )
        assert app.screen.query_one("#profile-clone-error-details", Static).content == (
            "目录隐藏提交错误"
        )
        assert app.screen.query_one("#profile-clone-error-safety", Static).content == (
            "目录未知结果恢复指引"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-clone-worker-error" not in rendered_text


async def test_stale_clone_confirmation_keeps_actionable_guidance() -> None:
    app, state_store = create_app()

    async with app.run_test() as pilot:
        await pilot.click("#open-profiles")
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
            "desired state 已变化。请修改名称后重新审阅，或返回配置详情重新开始。"
        )
        assert app.screen.query_one("#confirm-profile-clone", Button).disabled is True
        assert app.screen.query_one("#edit-profile-clone", Button).disabled is False
        assert state_store.load().profiles == (source_profile(),)

        await pilot.click("#edit-profile-clone")
        await pilot.click("#review-profile-clone")

        assert app.screen.query_one("#confirm-profile-clone", Button).disabled is False
        await pilot.click("#confirm-profile-clone")
        await pilot.pause()

        assert app.screen.query_one("#profile-clone-title", Static).content == "草案已创建"
        assert len(state_store.load().profiles) == EXPECTED_PROFILE_COUNT_AFTER_CLONE
