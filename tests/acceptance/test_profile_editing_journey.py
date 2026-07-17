from textual.widgets import Button, Input, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import Manager, StateRevisionConflictError
from sb_manager.application.profile_details import ProfileDetails
from sb_manager.application.profile_editing import (
    PlanProfileEditRequest,
    ProfileEditPlan,
    ProfileEditPortUnavailableError,
    ProfileEditResult,
    ProfileEditScope,
    ProfileEditValidationError,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    RollbackResult,
)
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools

LISTEN_PORT = 4433
EDITED_PORT = 8443


class FixedProfileDetailsReader:
    def __init__(self, status: ProfileStatus) -> None:
        self.status = status

    def get_profile_details(self, profile_id: str) -> ProfileDetails:
        assert profile_id == "profile-1"
        return ProfileDetails(
            profile_id=profile_id,
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            status=self.status,
            listen_port=4433,
            server_address="old.example.com",
            connection_info=None,
        )


class RecordingProfileEditor:
    def __init__(self, *, status: ProfileStatus = ProfileStatus.DRAFT) -> None:
        self.status = status
        self.requests: list[PlanProfileEditRequest] = []
        self.edits: list[tuple[ProfileEditPlan, bool]] = []

    def plan_edit(self, request: PlanProfileEditRequest) -> ProfileEditPlan:
        self.requests.append(request)
        profile_name = request.profile_name.strip()
        server_address = (request.server_address or "").strip() or None
        port_selection = (
            PortSelection.AUTOMATIC if request.listen_port is None else PortSelection.FIXED
        )
        changed_fields = tuple(
            field
            for field, changed in (
                ("profile_name", profile_name != "手机"),
                ("server_address", server_address != "old.example.com"),
                ("listen_port", request.listen_port != LISTEN_PORT),
                ("port_selection", port_selection is not PortSelection.FIXED),
            )
            if changed
        )
        return ProfileEditPlan(
            profile_id=request.profile_id,
            previous_profile_name="手机",
            profile_name=profile_name,
            previous_server_address="old.example.com",
            server_address=server_address,
            previous_listen_port=LISTEN_PORT,
            listen_port=request.listen_port,
            previous_port_selection=PortSelection.FIXED,
            port_selection=port_selection,
            status=self.status,
            expected_revision=2,
            scope=(
                ProfileEditScope.LIVE_CONFIGURATION
                if self.status is ProfileStatus.APPLIED
                and {"profile_name", "listen_port"}.intersection(changed_fields)
                else ProfileEditScope.DESIRED_STATE_ONLY
            ),
            changed_fields=changed_fields,
        )

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        self.edits.append((plan, confirmed))
        transaction = (
            ApplyTransactionResult(
                outcome=ApplyOutcome.APPLIED,
                validation=ConfigValidationResult(valid=True, diagnostics="valid"),
                runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="reloaded"),
                postcondition=RuntimePostcondition(healthy=True, diagnostics="active"),
                rollback=None,
            )
            if plan.scope is ProfileEditScope.LIVE_CONFIGURATION
            else None
        )
        return ProfileEditResult(
            scope=plan.scope,
            committed_revision=3,
            transaction=transaction,
            listen_port=(
                9443
                if plan.scope is ProfileEditScope.LIVE_CONFIGURATION
                and plan.port_selection is PortSelection.AUTOMATIC
                else plan.listen_port
            ),
        )


class ValidationFailingProfileEditor(RecordingProfileEditor):
    def plan_edit(self, request: PlanProfileEditRequest) -> ProfileEditPlan:
        self.requests.append(request)
        raise ProfileEditValidationError(
            field="profile_name",
            message="请输入配置名称",
        )


class LiveValidationFailingProfileEditor(RecordingProfileEditor):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        self.edits.append((plan, confirmed))
        return ProfileEditResult(
            scope=ProfileEditScope.LIVE_CONFIGURATION,
            committed_revision=None,
            transaction=ApplyTransactionResult(
                outcome=ApplyOutcome.VALIDATION_FAILED,
                validation=ConfigValidationResult(
                    valid=False,
                    diagnostics="edited candidate is invalid",
                ),
                runtime_refresh=None,
                postcondition=None,
                rollback=None,
            ),
        )


class UnavailableProfileEditor(RecordingProfileEditor):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        raise ConfigurationApplyError("sudo authorization denied")


class UnexpectedProfileEditor(RecordingProfileEditor):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        assert confirmed
        raise RuntimeError("token=private-profile-edit-worker-error")


class UnexpectedPlanningProfileEditor(RecordingProfileEditor):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def plan_edit(self, request: PlanProfileEditRequest) -> ProfileEditPlan:
        raise RuntimeError("token=private-profile-edit-planning-error")


class StaleProfileEditor(RecordingProfileEditor):
    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        raise StateRevisionConflictError(expected=2, actual=3)


class PortUnavailableProfileEditor(RecordingProfileEditor):
    def __init__(self) -> None:
        super().__init__(status=ProfileStatus.APPLIED)

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        raise ProfileEditPortUnavailableError(8443)


class FixedLiveResultProfileEditor(RecordingProfileEditor):
    def __init__(self, transaction: ApplyTransactionResult) -> None:
        super().__init__(status=ProfileStatus.APPLIED)
        self.transaction = transaction

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        return ProfileEditResult(
            scope=ProfileEditScope.LIVE_CONFIGURATION,
            committed_revision=None,
            transaction=self.transaction,
        )


class StateMutatingProfileEditor(RecordingProfileEditor):
    def __init__(self, state_store: MemoryStateStore) -> None:
        super().__init__()
        self.state_store = state_store

    def apply_edit(
        self,
        plan: ProfileEditPlan,
        *,
        confirmed: bool,
    ) -> ProfileEditResult:
        result = super().apply_edit(plan, confirmed=confirmed)
        current = self.state_store.load()
        existing = current.profiles[0]
        self.state_store.save(
            ManagedInstallation(
                schema_version=current.schema_version,
                revision=3,
                profiles=(
                    ManagedProfile(
                        profile_id=existing.profile_id,
                        profile_name=plan.profile_name,
                        protocol=existing.protocol,
                        listen_port=plan.listen_port,
                        port_selection=plan.port_selection,
                        status=existing.status,
                        protocol_material=existing.protocol_material,
                        server_address=plan.server_address,
                        tls_intent=existing.tls_intent,
                        transport_intent=existing.transport_intent,
                    ),
                ),
                expected_config_sha256=current.expected_config_sha256,
            )
        )
        return result


def app_for(
    editor: RecordingProfileEditor,
    *,
    state_store: MemoryStateStore | None = None,
) -> ManagerApp:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=editor.status,
        server_address="old.example.com",
    )
    store = state_store or MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=2, profiles=(profile,))
    )
    return ManagerApp(
        manager=Manager(state_store=store),
        host_tools=ManagerAppHostTools(
            profile_details_reader=FixedProfileDetailsReader(editor.status),
            profile_editor=editor,
        ),
    )


async def test_operator_opens_prefilled_profile_edit_form_without_creating_a_plan() -> None:
    editor = RecordingProfileEditor()
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        assert str(app.screen.query_one("#edit-profile", Button).label) == "编辑配置"

        await pilot.click("#edit-profile")

        assert app.screen.query_one("#profile-edit-title", Static).content == "编辑配置"
        assert app.screen.query_one("#profile-edit-name", Input).value == "手机"
        assert (
            app.screen.query_one("#profile-edit-server-address", Input).value == "old.example.com"
        )
        assert app.screen.query_one("#profile-edit-listen-port", Input).value == str(LISTEN_PORT)
        assert app.screen.query_one("#profile-edit-port-guidance", Static).content == (
            "留空表示自动选择。已应用配置会在确认后选择端口并执行完整事务。"
        )
        assert editor.requests == []
        assert editor.edits == []


async def test_operator_previews_normalized_draft_metadata_changes_before_confirmation() -> None:
    editor = RecordingProfileEditor()
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        app.screen.query_one("#profile-edit-server-address", Input).value = "new.example.com"
        await pilot.click("#preview-profile-edit")

        assert editor.requests == [
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="平板",
                server_address="new.example.com",
                listen_port=4433,
            )
        ]
        assert app.screen.query_one("#profile-edit-plan-title", Static).content == ("确认配置变更")
        assert app.screen.query_one("#profile-edit-plan-changes", Static).content == (
            "名称：手机 → 平板\n公开地址：old.example.com → new.example.com"
        )
        assert app.screen.query_one("#profile-edit-plan-impact", Static).content == (
            "只更新 manager desired state，不会写入 sing-box 配置或刷新服务。"
        )
        assert editor.edits == []


async def test_operator_previews_applied_listen_port_change_before_confirmation() -> None:
    editor = RecordingProfileEditor(status=ProfileStatus.APPLIED)
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-listen-port", Input).value = "8443"

        await pilot.click("#preview-profile-edit")

        assert editor.requests == [
            PlanProfileEditRequest(
                profile_id="profile-1",
                profile_name="手机",
                server_address="old.example.com",
                listen_port=8443,
            )
        ]
        assert app.screen.query_one("#profile-edit-plan-changes", Static).content == (
            "监听端口：4433 → 8443"
        )
        assert app.screen.query_one("#profile-edit-plan-impact", Static).content == (
            "将生成完整 sing-box 配置，校验并刷新服务，失败时自动回滚。"
        )
        assert str(app.screen.query_one("#confirm-profile-edit", Button).label) == (
            "确认修改并应用"
        )
        assert editor.edits == []


async def test_port_conflict_after_review_returns_operator_to_a_fresh_preview() -> None:
    app = app_for(PortUnavailableProfileEditor())

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-listen-port", Input).value = "8443"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-port-conflict-title", Static).content == (
            "监听端口已不可用"
        )
        assert app.screen.query_one("#profile-edit-port-conflict-details", Static).content == (
            "端口 8443 在确认后已不可用，请重新预览"
        )
        assert app.screen.query_one("#profile-edit-port-conflict-safety", Static).content == (
            "尚未调用配置 applier，实时配置、服务和 desired state 均未改变。"
        )


async def test_automatic_port_edit_reports_the_selected_live_port() -> None:
    editor = RecordingProfileEditor(status=ProfileStatus.APPLIED)
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-listen-port", Input).value = ""
        await pilot.click("#preview-profile-edit")

        assert app.screen.query_one("#profile-edit-plan-changes", Static).content == (
            "监听端口：4433 → 自动选择 - 确认时\n端口策略：固定 → 自动选择"
        )

        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "配置已应用并更新"
        )
        assert app.screen.query_one("#profile-edit-result-listen-port", Static).content == (
            "当前监听端口：9443"
        )


async def test_profile_edit_form_keeps_field_validation_actionable() -> None:
    editor = ValidationFailingProfileEditor()
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = ""
        await pilot.click("#preview-profile-edit")

        assert app.screen.query_one("#profile-edit-error", Static).content == ("请输入配置名称")
        assert app.screen.query_one("#profile-edit-name", Input).has_focus


async def test_operator_confirms_desired_state_only_edit_and_sees_revision() -> None:
    editor = RecordingProfileEditor()
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        app.screen.query_one("#profile-edit-server-address", Input).value = "new.example.com"
        await pilot.click("#preview-profile-edit")
        assert str(app.screen.query_one("#confirm-profile-edit", Button).label) == ("确认保存")

        await pilot.click("#confirm-profile-edit")

        assert len(editor.edits) == 1
        plan, confirmed = editor.edits[0]
        assert plan.profile_id == "profile-1"
        assert confirmed is True
        assert app.screen.query_one("#profile-edit-result-title", Static).content == ("配置已更新")
        assert app.screen.query_one("#profile-edit-result-details", Static).content == (
            "desired state 已提交 revision 3。"
        )
        assert app.screen.query_one("#profile-edit-result-safety", Static).content == (
            "未写入 sing-box 配置，也未刷新服务。"
        )


async def test_successful_profile_edit_returns_to_recomposed_dashboard() -> None:
    profile = ManagedProfile(
        profile_id="profile-1",
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
        server_address="old.example.com",
    )
    state_store = MemoryStateStore(
        ManagedInstallation(schema_version=1, revision=2, profiles=(profile,))
    )
    editor = StateMutatingProfileEditor(state_store)
    app = app_for(editor, state_store=state_store)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert str(app.screen.query_one("#profile-edit-return-dashboard", Button).label) == (
            "返回仪表盘"
        )
        await pilot.click("#profile-edit-return-dashboard")

        assert "平板" in str(app.screen.query_one("#profile-0", Static).content)


async def test_applied_name_edit_requires_live_apply_and_reports_healthy_result() -> None:
    editor = RecordingProfileEditor(status=ProfileStatus.APPLIED)
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")

        assert app.screen.query_one("#profile-edit-plan-impact", Static).content == (
            "将生成完整 sing-box 配置，校验并刷新服务，失败时自动回滚。"
        )
        assert str(app.screen.query_one("#confirm-profile-edit", Button).label) == (
            "确认修改并应用"
        )
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "配置已应用并更新"
        )
        assert app.screen.query_one("#profile-edit-result-safety", Static).content == (
            "新配置已通过校验，服务刷新和健康检查已完成。"
        )


async def test_failed_live_profile_edit_does_not_claim_success() -> None:
    app = app_for(LiveValidationFailingProfileEditor())

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "配置校验失败，未更新"
        )
        assert app.screen.query_one("#profile-edit-result-details", Static).content == (
            "edited candidate is invalid"
        )
        assert app.screen.query_one("#profile-edit-result-safety", Static).content == (
            "原有配置、服务和 desired state 均未改变。"
        )


async def test_unknown_profile_edit_host_result_requires_operator_diagnostics() -> None:
    app = app_for(UnavailableProfileEditor())

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-error-title", Static).content == (
            "无法确认配置编辑结果"
        )
        assert app.screen.query_one("#profile-edit-error-details", Static).content == (
            "sudo authorization denied"
        )
        assert app.screen.query_one("#profile-edit-error-safety", Static).content == (
            "desired state 未提交。请检查 sing-box 服务和 helper 日志后再决定是否重试。"
        )


async def test_unexpected_profile_edit_planning_failure_is_safe_and_not_disclosed() -> None:
    app = app_for(UnexpectedPlanningProfileEditor())

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.pause()

        assert app.screen.query_one("#profile-edit-planning-error-title", Static).content == (
            "无法准备配置编辑"
        )
        assert app.screen.query_one("#profile-edit-planning-error-details", Static).content == (
            "读取配置编辑计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-edit-planning-error-safety", Static).content == (
            "尚未执行任何操作。请返回配置列表，重新打开详情后再试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-edit-planning-error" not in rendered_text


async def test_unexpected_profile_edit_failure_is_unknown_and_not_disclosed() -> None:
    app = app_for(UnexpectedProfileEditor())

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")
        await pilot.pause()

        assert app.screen.query_one("#profile-edit-error-title", Static).content == (
            "无法确认配置编辑结果"
        )
        assert app.screen.query_one("#profile-edit-error-details", Static).content == (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        )
        assert app.screen.query_one("#profile-edit-error-safety", Static).content == (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        )
        rendered_text = "\n".join(str(widget.content) for widget in app.screen.query(Static))
        assert "private-profile-edit-worker-error" not in rendered_text


async def test_stale_profile_edit_plan_routes_operator_back_to_fresh_details() -> None:
    app = app_for(StaleProfileEditor())

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-conflict-title", Static).content == (
            "配置已被其他会话修改"
        )
        assert app.screen.query_one("#profile-edit-conflict-details", Static).content == (
            "State revision changed from 2 to 3"
        )
        assert app.screen.query_one("#profile-edit-conflict-safety", Static).content == (
            "本次变更未执行。请返回列表，重新打开详情并预览最新计划。"
        )


async def test_profile_edit_precondition_failure_explains_that_nothing_was_written() -> None:
    editor = FixedLiveResultProfileEditor(
        ApplyTransactionResult(
            outcome=ApplyOutcome.PRECONDITION_FAILED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
            commit=CommitResult(
                success=False,
                diagnostics="Live configuration fingerprint changed after review",
            ),
        )
    )
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "服务器配置已变化，未更新"
        )
        assert app.screen.query_one("#profile-edit-result-details", Static).content == (
            "Live configuration fingerprint changed after review"
        )
        assert app.screen.query_one("#profile-edit-result-safety", Static).content == (
            "本次尚未写入配置，请重新检查后再确认。"
        )


async def test_profile_edit_commit_failure_preserves_the_running_service() -> None:
    editor = FixedLiveResultProfileEditor(
        ApplyTransactionResult(
            outcome=ApplyOutcome.COMMIT_FAILED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=None,
            postcondition=None,
            rollback=None,
            commit=CommitResult(success=False, diagnostics="permission denied"),
        )
    )
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "无法写入编辑后的配置"
        )
        assert app.screen.query_one("#profile-edit-result-details", Static).content == (
            "permission denied"
        )
        assert app.screen.query_one("#profile-edit-result-safety", Static).content == (
            "尚未刷新服务，原有配置和 desired state 保持不变。"
        )


async def test_failed_profile_edit_reports_successful_automatic_rollback() -> None:
    editor = FixedLiveResultProfileEditor(
        ApplyTransactionResult(
            outcome=ApplyOutcome.ROLLED_BACK,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(
                success=False,
                diagnostics="service failed",
            ),
            postcondition=None,
            rollback=RollbackResult(
                success=True,
                diagnostics="old configuration restored",
                recovery_instructions=(),
            ),
            commit=CommitResult(success=True, diagnostics="committed"),
        )
    )
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "编辑失败，已自动回滚"
        )
        assert app.screen.query_one("#profile-edit-result-details", Static).content == (
            "old configuration restored"
        )
        assert app.screen.query_one("#profile-edit-result-safety", Static).content == (
            "原有配置、服务和 desired state 已保留。"
        )


async def test_failed_profile_edit_exposes_manual_recovery_steps() -> None:
    editor = FixedLiveResultProfileEditor(
        ApplyTransactionResult(
            outcome=ApplyOutcome.ROLLBACK_FAILED,
            validation=ConfigValidationResult(valid=True, diagnostics="valid"),
            runtime_refresh=RuntimeRefreshResult(
                success=False,
                diagnostics="service failed",
            ),
            postcondition=None,
            rollback=RollbackResult(
                success=False,
                diagnostics="old service did not recover",
                recovery_instructions=(
                    "restore /etc/sing-box/config.json.bak",
                    "restart sing-box.service",
                ),
            ),
            commit=CommitResult(success=True, diagnostics="committed"),
        )
    )
    app = app_for(editor)

    async with app.run_test() as pilot:
        await pilot.click("#view-profile-0")
        await pilot.click("#edit-profile")
        app.screen.query_one("#profile-edit-name", Input).value = "平板"
        await pilot.click("#preview-profile-edit")
        await pilot.click("#confirm-profile-edit")

        assert app.screen.query_one("#profile-edit-result-title", Static).content == (
            "回滚未完成，需要人工恢复"
        )
        assert app.screen.query_one("#profile-edit-result-details", Static).content == (
            "old service did not recover"
        )
        assert app.screen.query_one("#profile-edit-recovery-step-0", Static).content == (
            "1. restore /etc/sing-box/config.json.bak"
        )
        assert app.screen.query_one("#profile-edit-recovery-step-1", Static).content == (
            "2. restart sing-box.service"
        )
