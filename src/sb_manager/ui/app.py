from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.apply_history import ApplyHistoryReader
from sb_manager.application.config_adoption import ConfigAdopter
from sb_manager.application.core_update import CoreUpdater
from sb_manager.application.diagnostics_center import DiagnosticsCenter
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnostics,
    HostDiagnosticsReport,
)
from sb_manager.application.host_readiness import HostReadiness, HostReadinessReport
from sb_manager.application.manager import (
    AcmeTlsRequest,
    GeneratedValue,
    GrpcTransportRequest,
    Manager,
    OperatorFileTlsRequest,
    PlanProfileRequest,
    PlanValidationError,
    ProfilePlan,
    TlsRequest,
    TransportRequest,
    WebSocketTransportRequest,
)
from sb_manager.application.profile_apply import (
    ApplyProfileRequest,
    ApplyProfileResult,
    ProfileApplier,
)
from sb_manager.application.profile_availability import (
    PlanProfileAvailabilityRequest,
    ProfileAvailability,
    ProfileAvailabilityDraftError,
    ProfileAvailabilityManager,
    ProfileAvailabilityNoChangeError,
    ProfileAvailabilityNotFoundError,
    ProfileResumePortUnavailableError,
)
from sb_manager.application.profile_cloning import (
    ProfileCloneError,
    ProfileCloner,
    ProfileCloneResult,
)
from sb_manager.application.profile_details import (
    ProfileDetails,
    ProfileDetailsError,
    ProfileDetailsReader,
)
from sb_manager.application.profile_editing import ProfileEditor
from sb_manager.application.profile_recommendation import (
    ProfileRecommendationAdvisor,
    ProfileRecommendationService,
    ProtocolVariant,
)
from sb_manager.application.profile_removal import (
    ProfileRemovalNotFoundError,
    ProfileRemover,
)
from sb_manager.application.service_logs import ServiceLogReader
from sb_manager.application.state_recovery import (
    RecoveryAvailability,
    StateRecoveryManager,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.transports.catalog import GrpcTransportIntent, WebSocketTransportIntent
from sb_manager.ui.screens.config_adoption import ConfigAdoptionScreen
from sb_manager.ui.screens.core_update import CoreUpdateFormScreen
from sb_manager.ui.screens.diagnostics_center import DiagnosticsCenterScreen
from sb_manager.ui.screens.host_readiness import HostReadinessScreen
from sb_manager.ui.screens.keyboard_help import KeyboardHelpScreen
from sb_manager.ui.screens.profile_availability import (
    ProfileAvailabilityErrorScreen,
    ProfileAvailabilityPlanningErrorScreen,
    ProfileAvailabilityPlanScreen,
)
from sb_manager.ui.screens.profile_cloning import (
    ProfileClonePlanningErrorScreen,
    ProfileCloneScreen,
)
from sb_manager.ui.screens.profile_editing import ProfileEditFormScreen
from sb_manager.ui.screens.profile_recommendation import ProfilePurposeScreen
from sb_manager.ui.screens.profile_removal import (
    ProfileRemovalPlanningErrorScreen,
    ProfileRemovalScreen,
)
from sb_manager.ui.screens.state_recovery import (
    StateRecoveryConfirmationScreen,
    StateRecoveryPanel,
)


@dataclass(frozen=True, slots=True)
class GuidedProfileDefinition:
    """Protocol-specific copy and identity for the shared profile form."""

    protocol: ProtocolKind
    form_id: str
    title_id: str
    guidance_id: str
    title: str
    guidance: str
    uses_tls: bool = False
    uses_websocket: bool = False
    uses_grpc: bool = False


REALITY_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_REALITY,
    form_id="reality-form",
    title_id="reality-form-title",
    guidance_id="reality-guidance",
    title="配置 VLESS Reality",
    guidance="适合大多数网络环境。UUID、密钥和兼容站点将自动生成。",
)
SHADOWSOCKS_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.SHADOWSOCKS,
    form_id="shadowsocks-form",
    title_id="shadowsocks-form-title",
    guidance_id="protocol-guidance",
    title="配置 Shadowsocks 2022",
    guidance="无需 TLS，适合需要简洁配置的场景。安全密钥将自动生成。",
)
HYSTERIA2_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.HYSTERIA2,
    form_id="hysteria2-form",
    title_id="hysteria2-form-title",
    guidance_id="hysteria2-guidance",
    title="配置 Hysteria2",
    guidance="适合移动网络。认证密码自动生成，TLS 证书通过 ACME 申请。",
    uses_tls=True,
)
TROJAN_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.TROJAN,
    form_id="trojan-form",
    title_id="trojan-form-title",
    guidance_id="trojan-guidance",
    title="配置 Trojan",
    guidance="基于 TLS 的兼容协议。认证密码自动生成，证书通过 ACME 申请。",
    uses_tls=True,
)
ANYTLS_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.ANYTLS,
    form_id="anytls-form",
    title_id="anytls-form-title",
    guidance_id="anytls-guidance",
    title="配置 AnyTLS",
    guidance="用于缓解 TLS 嵌套指纹。认证密码自动生成，证书通过 ACME 申请。",
    uses_tls=True,
)
TUIC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.TUIC,
    form_id="tuic-form",
    title_id="tuic-form-title",
    guidance_id="tuic-guidance",
    title="配置 TUIC",
    guidance="基于 QUIC 的低延迟协议。默认关闭可重放的 0-RTT。",
    uses_tls=True,
)
VLESS_WEBSOCKET_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_TLS,
    form_id="vless-websocket-form",
    title_id="vless-websocket-form-title",
    guidance_id="vless-websocket-guidance",
    title="配置 VLESS TLS WebSocket",
    guidance="适合需要 WebSocket 或 CDN 兼容入口的场景。",
    uses_tls=True,
    uses_websocket=True,
)
VLESS_GRPC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_TLS,
    form_id="vless-grpc-form",
    title_id="vless-grpc-form-title",
    guidance_id="vless-grpc-guidance",
    title="配置 VLESS TLS gRPC",
    guidance="适合需要标准 gRPC 传输兼容性的场景。",
    uses_tls=True,
    uses_grpc=True,
)
VMESS_WEBSOCKET_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VMESS_TLS,
    form_id="vmess-websocket-form",
    title_id="vmess-websocket-form-title",
    guidance_id="vmess-websocket-guidance",
    title="配置 VMess TLS WebSocket",
    guidance="仅用于旧客户端兼容，使用 alterId 0 和现代 UUID 认证。",
    uses_tls=True,
    uses_websocket=True,
)
VMESS_GRPC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VMESS_TLS,
    form_id="vmess-grpc-form",
    title_id="vmess-grpc-form-title",
    guidance_id="vmess-grpc-guidance",
    title="配置 VMess TLS gRPC",
    guidance="旧客户端兼容的 VMess，使用标准 gRPC 传输。",
    uses_tls=True,
    uses_grpc=True,
)
GUIDED_PROFILES_BY_VARIANT: dict[ProtocolVariant, GuidedProfileDefinition] = {
    ProtocolVariant.VLESS_REALITY: REALITY_PROFILE,
    ProtocolVariant.SHADOWSOCKS: SHADOWSOCKS_PROFILE,
    ProtocolVariant.HYSTERIA2: HYSTERIA2_PROFILE,
    ProtocolVariant.TROJAN: TROJAN_PROFILE,
    ProtocolVariant.ANYTLS: ANYTLS_PROFILE,
    ProtocolVariant.TUIC: TUIC_PROFILE,
    ProtocolVariant.VLESS_WEBSOCKET: VLESS_WEBSOCKET_PROFILE,
    ProtocolVariant.VLESS_GRPC: VLESS_GRPC_PROFILE,
    ProtocolVariant.VMESS_WEBSOCKET: VMESS_WEBSOCKET_PROFILE,
    ProtocolVariant.VMESS_GRPC: VMESS_GRPC_PROFILE,
}
PROTOCOL_LABELS: dict[ProtocolKind, str] = {
    ProtocolKind.VLESS_REALITY: "VLESS Reality",
    ProtocolKind.SHADOWSOCKS: "Shadowsocks 2022",
    ProtocolKind.HYSTERIA2: "Hysteria2",
    ProtocolKind.TROJAN: "Trojan",
    ProtocolKind.ANYTLS: "AnyTLS",
    ProtocolKind.TUIC: "TUIC",
    ProtocolKind.VLESS_TLS: "VLESS TLS",
    ProtocolKind.VMESS_TLS: "VMess TLS",
}


class HostDiagnosticsScreen(Screen[None]):
    """Present one typed host observation with operator recovery guidance."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, report: HostDiagnosticsReport) -> None:
        super().__init__()
        self.report = report

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="host-diagnostics"):
            yield Static("主机诊断", id="diagnostics-title")
            yield Static(self.report.summary, id="diagnostics-summary")
            yield Static(
                self.report.diagnostics or "运行时未提供详细信息", id="diagnostics-details"
            )
            if self.report.recovery_instructions:
                yield Static("建议的恢复步骤", id="diagnostics-recovery-title")
                for index, instruction in enumerate(self.report.recovery_instructions):
                    yield Static(
                        f"{index + 1}. {instruction}",
                        id=f"diagnostics-recovery-{index}",
                    )
            else:
                yield Static("当前无需恢复操作。", id="diagnostics-recovery-empty")
        yield Footer()


class ProfileDetailsScreen(Screen[None]):
    """Present durable profile identity and reusable client information."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        details: ProfileDetails,
        *,
        profile_editor: ProfileEditor | None = None,
        profile_remover: ProfileRemover | None = None,
        profile_availability_manager: ProfileAvailabilityManager | None = None,
        profile_cloner: ProfileCloner | None = None,
    ) -> None:
        super().__init__()
        self.details = details
        self.profile_editor = profile_editor
        self.profile_remover = profile_remover
        self.profile_availability_manager = profile_availability_manager
        self.profile_cloner = profile_cloner

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-details"):
            yield Static("配置详情", id="profile-details-title")
            yield Static(f"名称：{self.details.profile_name}", id="profile-details-name")
            yield Static(
                f"协议：{PROTOCOL_LABELS[self.details.protocol]}",
                id="profile-details-protocol",
            )
            status = (
                ("已应用 · 在线" if self.details.enabled else "已应用 · 已暂停")
                if self.details.status is ProfileStatus.APPLIED
                else "草案"
            )
            yield Static(f"状态：{status}", id="profile-details-status")
            if connection_info := self.details.connection_info:
                yield Static(
                    f"服务器：{connection_info.server_address}:{connection_info.server_port}",
                    id="profile-details-endpoint",
                )
                yield Label("连接链接")
                yield Input(
                    value=connection_info.share_uri,
                    id="profile-details-share-uri",
                )
            else:
                yield Static(
                    "该配置尚无可用连接信息。应用草案并设置服务器地址后生成。",
                    id="profile-details-no-connection",
                )
            if self.profile_editor is not None:
                yield Button("编辑配置", id="edit-profile", variant="primary")
            if self.profile_cloner is not None:
                yield Button("以此配置为模板", id="clone-profile")
            if (
                self.profile_availability_manager is not None
                and self.details.status is ProfileStatus.APPLIED
            ):
                yield Button(
                    "暂停配置" if self.details.enabled else "恢复配置",
                    id="change-profile-availability",
                    variant="warning",
                )
            if self.profile_remover is not None:
                yield Button("移除此配置", id="remove-profile", variant="error")
        yield Footer()

    @on(Button.Pressed, "#edit-profile")
    def open_profile_editing(self) -> None:
        if self.profile_editor is not None:
            self.app.push_screen(ProfileEditFormScreen(self.profile_editor, details=self.details))

    @on(Button.Pressed, "#remove-profile")
    def open_profile_removal(self) -> None:
        if self.profile_remover is None:
            return
        try:
            screen = ProfileRemovalScreen(
                self.profile_remover,
                profile_id=self.details.profile_id,
            )
        except ProfileRemovalNotFoundError:
            self.app.push_screen(ProfileDetailsErrorScreen())
            return
        except Exception:
            self.app.push_screen(ProfileRemovalPlanningErrorScreen())
            return
        self.app.push_screen(screen)

    @on(Button.Pressed, "#clone-profile")
    def open_profile_clone(self) -> None:
        if self.profile_cloner is None:
            return
        try:
            screen = ProfileCloneScreen(
                self.profile_cloner,
                source_profile_id=self.details.profile_id,
            )
        except ProfileCloneError:
            self.app.push_screen(ProfileDetailsErrorScreen())
            return
        except Exception:
            self.app.push_screen(ProfileClonePlanningErrorScreen())
            return
        self.app.push_screen(screen, self.finish_profile_clone)

    async def finish_profile_clone(self, result: ProfileCloneResult | None) -> None:
        if result is None:
            return
        self.dismiss()
        await self.app.recompose()

    @on(Button.Pressed, "#change-profile-availability")
    def open_profile_availability(self) -> None:
        if self.profile_availability_manager is None:
            return
        target = ProfileAvailability.PAUSED if self.details.enabled else ProfileAvailability.ACTIVE
        try:
            plan = self.profile_availability_manager.plan_change(
                PlanProfileAvailabilityRequest(
                    profile_id=self.details.profile_id,
                    target=target,
                )
            )
        except (
            ProfileAvailabilityDraftError,
            ProfileAvailabilityNoChangeError,
            ProfileAvailabilityNotFoundError,
            ProfileResumePortUnavailableError,
        ) as error:
            self.app.push_screen(ProfileAvailabilityErrorScreen(str(error)))
            return
        except Exception:
            self.app.push_screen(ProfileAvailabilityPlanningErrorScreen())
            return
        self.app.push_screen(
            ProfileAvailabilityPlanScreen(
                self.profile_availability_manager,
                plan=plan,
            )
        )


class ProfileDetailsErrorScreen(Screen[None]):
    """Keep stale or incomplete desired state from terminating the TUI."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-details-error"):
            yield Static("无法打开配置详情", id="profile-details-error-title")
            yield Static(
                "配置可能已被另一个会话修改，请返回后重新打开列表。",
                id="profile-details-error-message",
            )
        yield Footer()


class ApplyResultScreen(Screen[None]):
    """Present the typed terminal state of an apply attempt."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, result: ApplyProfileResult) -> None:
        super().__init__()
        self.result = result

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-result"):
            if self.result.transaction.outcome is ApplyOutcome.APPLIED:
                yield Static("应用成功", id="apply-result-title")
                yield Static(
                    f"已提交 revision {self.result.committed_revision}",
                    id="apply-result-revision",
                )
                yield Static(
                    "sing-box 配置已生效，服务运行正常。",
                    id="apply-result-health",
                )
                if connection_info := self.result.connection_info:
                    yield Static(
                        f"服务器：{connection_info.server_address}:{connection_info.server_port}",
                        id="apply-result-endpoint",
                    )
                    yield Label("连接链接")
                    yield Input(
                        value=connection_info.share_uri,
                        id="apply-result-share-uri",
                    )
            elif self.result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED:
                yield Static("配置校验失败", id="apply-result-title")
                yield Static(
                    self.result.transaction.validation.diagnostics,
                    id="apply-result-details",
                )
                yield Static("原有配置和服务均未改变。", id="apply-result-safety")
            elif self.result.transaction.outcome is ApplyOutcome.PRECONDITION_FAILED:
                yield Static("服务器配置已变化", id="apply-result-title")
                commit = self.result.transaction.commit
                yield Static(
                    (
                        commit.diagnostics
                        if commit is not None
                        else "服务器配置不再符合已确认的接管前置条件"
                    ),
                    id="apply-result-details",
                )
                yield Static(
                    "本次尚未写入配置，请重新检查并确认接管状态。",
                    id="apply-result-safety",
                )
            elif self.result.transaction.outcome is ApplyOutcome.COMMIT_FAILED:
                yield Static("无法写入配置", id="apply-result-title")
                commit = self.result.transaction.commit
                yield Static(
                    commit.diagnostics if commit is not None else "配置提交失败",
                    id="apply-result-details",
                )
                yield Static(
                    "尚未刷新服务，原有配置保持不变。",
                    id="apply-result-safety",
                )
            elif self.result.transaction.outcome is ApplyOutcome.ROLLED_BACK:
                yield Static("应用失败，已自动回滚", id="apply-result-title")
                rollback = self.result.transaction.rollback
                yield Static(
                    rollback.diagnostics if rollback is not None else "旧配置已恢复。",
                    id="apply-result-details",
                )
                yield Static("原有配置和服务已恢复。", id="apply-result-safety")
            else:
                yield Static("回滚未完成，需要人工恢复", id="apply-result-title")
                rollback = self.result.transaction.rollback
                yield Static(
                    rollback.diagnostics if rollback is not None else "回滚状态未知",
                    id="apply-result-details",
                )
                if rollback is not None:
                    for index, instruction in enumerate(rollback.recovery_instructions):
                        yield Static(
                            f"{index + 1}. {instruction}",
                            id=f"recovery-step-{index}",
                        )
        yield Footer()


class ApplyOperationalErrorScreen(Screen[None]):
    """Explain an unknown host result without claiming that no mutation occurred."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(self, diagnostics: str) -> None:
        super().__init__()
        self.diagnostics = diagnostics

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-operational-error"):
            yield Static("无法确认服务器变更结果", id="apply-error-title")
            yield Static(self.diagnostics, id="apply-error-details")
            yield Static(
                "desired state 未提交。请先检查 sing-box 服务和 helper 日志，再决定是否重试。",
                id="apply-error-safety",
            )
        yield Footer()


class ApplyUnexpectedErrorScreen(Screen[None]):
    """Treat an unexpected confirmed apply failure as an entirely unknown result."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-operational-error"):
            yield Static("无法确认配置应用结果", id="apply-unexpected-error-title")
            yield Static(
                "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="apply-unexpected-error-details",
            )
            yield Static(
                "服务器配置、服务和 desired state 的结果均未知。"
                "请先检查配置身份、服务状态和应用历史，再决定是否重试。",
                id="apply-unexpected-error-safety",
            )
        yield Footer()


class ApplyConfirmationScreen(Screen[None]):
    """Require a second explicit action before host mutation."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(
        self,
        installation: ManagedInstallation,
        profile_applier: ProfileApplier,
        *,
        profile_id: str,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.profile_applier = profile_applier
        try:
            self.profile = next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
            )
        except StopIteration as error:
            raise ValueError(f"Unknown profile in apply confirmation: {profile_id}") from error

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-confirmation"):
            yield Static("即将修改服务器", id="apply-confirm-title")
            yield Static(f"配置：{self.profile.profile_name}", id="apply-confirm-profile")
            yield Static(
                "将写入 sing-box 配置并刷新服务，失败时自动回滚。",
                id="apply-confirm-warning",
            )
            yield Static("", id="apply-progress")
            yield Button("确认并应用", id="confirm-apply", variant="error")
        yield Footer()

    @on(Button.Pressed, "#confirm-apply")
    def confirm_apply(self) -> None:
        self.query_one("#confirm-apply", Button).disabled = True
        self.query_one("#apply-progress", Static).update(
            "正在校验、提交并检查服务健康状态; 请勿关闭程序。"
        )
        self.execute_apply(
            ApplyProfileRequest(
                profile_id=self.profile.profile_id,
                expected_revision=self.installation.revision,
                confirmed=True,
            )
        )

    @work(thread=True, exclusive=True)
    def execute_apply(self, request: ApplyProfileRequest) -> None:
        try:
            result = self.profile_applier.apply_profile(request)
        except ConfigurationApplyError as error:
            self.app.call_from_thread(
                self.app.push_screen,
                ApplyOperationalErrorScreen(str(error)),
            )
            return
        except Exception:
            self.app.call_from_thread(self.app.push_screen, ApplyUnexpectedErrorScreen())
            return
        self.app.call_from_thread(self.app.push_screen, ApplyResultScreen(result))


class DraftSavedScreen(Screen[None]):
    """Confirm that desired state was saved without applying host changes."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        installation: ManagedInstallation,
        *,
        profile_id: str,
        profile_applier: ProfileApplier | None = None,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.profile_applier = profile_applier
        try:
            self.profile = next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
            )
        except StopIteration as error:
            raise ValueError(f"Unknown saved draft profile: {profile_id}") from error

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="draft-saved"):
            yield Static("草案已保存", id="draft-saved-title")
            yield Static(self.profile.profile_name, id="saved-profile")
            yield Static(
                f"草案 · revision {self.installation.revision}",
                id="saved-status",
            )
            yield Static("尚未修改服务器。", id="saved-safety")
            if self.profile_applier is not None:
                yield Button("应用到服务器", id="apply-draft", variant="warning")
        yield Footer()

    @on(Button.Pressed, "#apply-draft")
    def open_apply_confirmation(self) -> None:
        if self.profile_applier is not None:
            self.app.push_screen(
                ApplyConfirmationScreen(
                    self.installation,
                    self.profile_applier,
                    profile_id=self.profile.profile_id,
                )
            )


class PlanPreviewScreen(Screen[None]):
    """Present a side-effect-free plan in operator language."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回修改")]

    GENERATED_LABELS: ClassVar[dict[GeneratedValue, str]] = {
        GeneratedValue.UUID: "UUID",
        GeneratedValue.REALITY_KEY_PAIR: "Reality 密钥",
        GeneratedValue.SERVER_NAME: "兼容站点",
        GeneratedValue.SHADOWSOCKS_KEY: "Shadowsocks 2022 安全密钥",
        GeneratedValue.HYSTERIA2_PASSWORD: "Hysteria2 认证密码",
        GeneratedValue.TROJAN_PASSWORD: "Trojan 认证密码",
        GeneratedValue.ANYTLS_PASSWORD: "AnyTLS 认证密码",
        GeneratedValue.TUIC_UUID: "TUIC UUID",
        GeneratedValue.TUIC_PASSWORD: "TUIC 认证密码",
        GeneratedValue.VLESS_UUID: "VLESS UUID",
        GeneratedValue.VMESS_UUID: "VMess UUID",
        GeneratedValue.TLS_CERTIFICATE: "TLS 证书",
    }

    def __init__(
        self,
        manager: Manager,
        plan: ProfilePlan,
        profile_applier: ProfileApplier | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.plan = plan
        self.profile_applier = profile_applier

    def compose(self) -> ComposeResult:
        generated = "、".join(self.GENERATED_LABELS[value] for value in self.plan.generated_values)
        port_summary = (
            "自动选择可用端口"
            if self.plan.port_selection is PortSelection.AUTOMATIC
            else str(self.plan.listen_port)
        )
        yield Header()
        with Vertical(id="plan-preview"):
            yield Static("确认变更计划", id="plan-title")
            yield Static(f"配置：{self.plan.profile_name}", id="plan-profile")
            yield Static(
                f"协议：{PROTOCOL_LABELS[self.plan.protocol]}",
                id="plan-protocol",
            )
            yield Static(f"监听端口：{port_summary}", id="plan-port")
            if self.plan.server_address is not None:
                yield Static(
                    f"服务器地址：{self.plan.server_address}",
                    id="plan-server-address",
                )
            if isinstance(self.plan.tls_intent, AcmeTlsIntent):
                yield Static(
                    "TLS：ACME · "
                    f"{self.plan.tls_intent.server_name} · {self.plan.tls_intent.email}",
                    id="plan-tls",
                )
            if isinstance(self.plan.tls_intent, OperatorFileTlsIntent):
                yield Static(
                    "TLS：已有证书 · "
                    f"{self.plan.tls_intent.server_name} · "
                    f"{self.plan.tls_intent.certificate_path}",
                    id="plan-tls",
                )
                yield Static(
                    f"私钥：{self.plan.tls_intent.key_path}",
                    id="plan-tls-key",
                )
            if isinstance(self.plan.transport_intent, WebSocketTransportIntent):
                transport_summary = f"传输：WebSocket · {self.plan.transport_intent.path}"
                if self.plan.transport_intent.host is not None:
                    transport_summary += f" · Host {self.plan.transport_intent.host}"
                yield Static(transport_summary, id="plan-transport")
            if isinstance(self.plan.transport_intent, GrpcTransportIntent):
                yield Static(
                    f"传输：gRPC · {self.plan.transport_intent.service_name}",
                    id="plan-transport",
                )
            yield Static(f"自动生成：{generated}", id="plan-generated")
            yield Static("当前仅预览，不会修改服务器。", id="plan-safety")
            yield Button("保存为草案", id="save-draft", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#save-draft")
    def save_draft(self) -> None:
        self.manager.save_profile_draft(self.plan)
        installation = self.manager.get_installation()
        saved_profile = installation.profiles[-1]
        self.app.push_screen(
            DraftSavedScreen(
                installation,
                profile_id=saved_profile.profile_id,
                profile_applier=self.profile_applier,
            )
        )


class GuidedProfileScreen(Screen[None]):
    """Collect common intent using protocol-specific operator guidance."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]
    ERROR_SELECTORS: ClassVar[dict[str, str]] = {
        "profile_name": "#profile-name-error",
        "listen_port": "#listen-port-error",
        "tls_server_name": "#tls-server-name-error",
        "tls_email": "#tls-email-error",
        "tls_certificate_path": "#tls-certificate-path-error",
        "tls_key_path": "#tls-key-path-error",
        "websocket_path": "#websocket-path-error",
        "grpc_service_name": "#grpc-service-name-error",
    }

    def __init__(
        self,
        manager: Manager,
        definition: GuidedProfileDefinition,
        profile_applier: ProfileApplier | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.definition = definition
        self.profile_applier = profile_applier

    def compose(self) -> ComposeResult:
        yield Header()
        form = (
            VerticalScroll(id=self.definition.form_id)
            if self.definition.uses_tls
            else Vertical(id=self.definition.form_id)
        )
        with form:
            yield Static(self.definition.title, id=self.definition.title_id)
            yield Static(self.definition.guidance, id=self.definition.guidance_id)
            yield Label("配置名称", classes="field-label")
            yield Input(placeholder="例如：手机", id="profile-name")
            yield Static("", id="profile-name-error", classes="field-error")
            yield Label("服务器地址", classes="field-label")
            yield Input(
                placeholder="例如：vpn.example.com 或 203.0.113.10",
                id="server-address",
            )
            if self.definition.uses_tls:
                yield Label("TLS 证书域名", classes="field-label")
                yield Input(placeholder="例如：vpn.example.com", id="tls-server-name")
                yield Static("", id="tls-server-name-error", classes="field-error")
                yield Label("TLS 证书方式", classes="field-label")
                yield Select(
                    (
                        ("自动申请 ACME · 推荐", "acme"),
                        ("已有 root 管理的证书文件 · 高级", "operator-files"),
                    ),
                    value="acme",
                    allow_blank=False,
                    id="tls-strategy",
                )
                with Vertical(id="tls-acme-fields"):
                    yield Label("ACME 联系邮箱", classes="field-label")
                    yield Input(placeholder="例如：operator@example.com", id="tls-email")
                    yield Static("", id="tls-email-error", classes="field-error")
                with Vertical(id="tls-file-fields", classes="hidden"):
                    yield Label("证书文件", classes="field-label")
                    yield Input(
                        placeholder="/etc/sing-box-manager/tls/server.crt",
                        id="tls-certificate-path",
                    )
                    yield Static(
                        "",
                        id="tls-certificate-path-error",
                        classes="field-error",
                    )
                    yield Label("私钥文件", classes="field-label")
                    yield Input(
                        placeholder="/etc/sing-box-manager/tls/server.key",
                        id="tls-key-path",
                    )
                    yield Static("", id="tls-key-path-error", classes="field-error")
            if self.definition.uses_websocket:
                yield Label("WebSocket 路径", classes="field-label")
                yield Input(placeholder="例如：/proxy", id="websocket-path")
                yield Static("", id="websocket-path-error", classes="field-error")
                yield Label("WebSocket Host (可选)", classes="field-label")
                yield Input(placeholder="例如：vpn.example.com", id="websocket-host")
            if self.definition.uses_grpc:
                yield Label("gRPC 服务名", classes="field-label")
                yield Input(placeholder="例如：ProxyService", id="grpc-service-name")
                yield Static("", id="grpc-service-name-error", classes="field-error")
            yield Label("监听端口", classes="field-label")
            yield Input(placeholder="留空自动选择", id="listen-port", type="integer")
            yield Static("", id="listen-port-error", classes="field-error")
            yield Button("预览变更计划", id="preview-plan", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#preview-plan")
    def preview_plan(self) -> None:
        profile_name = self.query_one("#profile-name", Input).value
        server_address = self.query_one("#server-address", Input).value
        tls: TlsRequest | None = None
        tls_strategy: object = None
        if self.definition.uses_tls:
            tls_strategy = self.query_one("#tls-strategy", Select).value
            if tls_strategy == "operator-files":
                tls = OperatorFileTlsRequest(
                    server_name=self.query_one("#tls-server-name", Input).value,
                    certificate_path=Path(self.query_one("#tls-certificate-path", Input).value),
                    key_path=Path(self.query_one("#tls-key-path", Input).value),
                )
            else:
                tls = AcmeTlsRequest(
                    server_name=self.query_one("#tls-server-name", Input).value,
                    email=self.query_one("#tls-email", Input).value,
                )
        transport: TransportRequest | None = None
        if self.definition.uses_websocket:
            transport = WebSocketTransportRequest(
                path=self.query_one("#websocket-path", Input).value,
                host=self.query_one("#websocket-host", Input).value,
            )
        if self.definition.uses_grpc:
            transport = GrpcTransportRequest(
                service_name=self.query_one("#grpc-service-name", Input).value,
            )
        port_text = self.query_one("#listen-port", Input).value
        listen_port = int(port_text) if port_text else None
        visible_error_fields = ["profile_name", "listen_port"]
        if self.definition.uses_tls:
            visible_error_fields.append("tls_server_name")
            visible_error_fields.extend(
                ("tls_certificate_path", "tls_key_path")
                if tls_strategy == "operator-files"
                else ("tls_email",)
            )
        if self.definition.uses_websocket:
            visible_error_fields.append("websocket_path")
        if self.definition.uses_grpc:
            visible_error_fields.append("grpc_service_name")
        for error_field in visible_error_fields:
            self.query_one(self.ERROR_SELECTORS[error_field], Static).update("")
        try:
            plan = self.manager.plan_profile(
                PlanProfileRequest(
                    profile_name=profile_name,
                    protocol=self.definition.protocol,
                    listen_port=listen_port,
                    server_address=server_address,
                    tls=tls,
                    transport=transport,
                )
            )
        except PlanValidationError as error:
            for issue in error.issues:
                if error_selector := self.ERROR_SELECTORS.get(issue.field):
                    self.query_one(error_selector, Static).update(issue.message)
            return
        self.app.push_screen(PlanPreviewScreen(self.manager, plan, self.profile_applier))

    @on(Select.Changed, "#tls-strategy")
    def switch_tls_strategy(self, event: Select.Changed) -> None:
        use_operator_files = event.value == "operator-files"
        self.query_one("#tls-acme-fields").display = not use_operator_files
        self.query_one("#tls-file-fields").display = use_operator_files


@dataclass(frozen=True, slots=True)
class ManagerAppHostTools:
    """Host observation and profile lifecycle capabilities available to the TUI."""

    host_diagnostics: HostDiagnostics | None = None
    diagnostics_center: DiagnosticsCenter | None = None
    host_readiness: HostReadiness | None = None
    profile_details_reader: ProfileDetailsReader | None = None
    profile_editor: ProfileEditor | None = None
    profile_remover: ProfileRemover | None = None
    profile_availability_manager: ProfileAvailabilityManager | None = None
    profile_cloner: ProfileCloner | None = None
    profile_recommendation_advisor: ProfileRecommendationAdvisor = field(
        default_factory=ProfileRecommendationService
    )
    config_adopter: ConfigAdopter | None = None
    state_recovery_manager: StateRecoveryManager | None = None
    service_log_reader: ServiceLogReader | None = None
    apply_history_reader: ApplyHistoryReader | None = None


class ManagerApp(App[None]):
    """Guided terminal manager for sing-box."""

    TITLE = "Sing-box Manager"
    SUB_TITLE = "安全地搭建和维护你的代理服务"

    CSS_PATH = "theme.tcss"
    BINDINGS: ClassVar[list[BindingType]] = [
        ("?", "show_keyboard_help", "帮助"),
        ("a", "add_profile", "添加配置"),
        ("d", "open_diagnostics", "诊断"),
        ("c", "manage_core", "核心"),
        ("q", "quit", "退出"),
    ]

    def __init__(
        self,
        manager: Manager | None = None,
        profile_applier: ProfileApplier | None = None,
        core_updater: CoreUpdater | None = None,
        host_tools: ManagerAppHostTools | None = None,
    ) -> None:
        super().__init__()
        tools = host_tools or ManagerAppHostTools()
        self.manager = manager or Manager(state_store=MemoryStateStore())
        self.profile_applier = profile_applier
        self.core_updater = core_updater
        self.host_diagnostics = tools.host_diagnostics
        self.diagnostics_center = tools.diagnostics_center
        self.host_diagnostics_report: HostDiagnosticsReport | None = None
        self.host_readiness = tools.host_readiness
        self.host_readiness_report: HostReadinessReport | None = None
        self.profile_details_reader = tools.profile_details_reader
        self.profile_editor = tools.profile_editor
        self.profile_remover = tools.profile_remover
        self.profile_availability_manager = tools.profile_availability_manager
        self.profile_cloner = tools.profile_cloner
        self.profile_recommendation_advisor = tools.profile_recommendation_advisor
        self.config_adopter = tools.config_adopter
        self.state_recovery_manager = tools.state_recovery_manager
        self.service_log_reader = tools.service_log_reader
        self.apply_history_reader = tools.apply_history_reader
        self._dashboard_ready = False
        self._host_diagnostics_failed = False
        self._host_readiness_failed = False

    def compose(self) -> ComposeResult:
        yield Header()
        recovery_report = (
            self.state_recovery_manager.inspect()
            if self.state_recovery_manager is not None
            else None
        )
        if (
            recovery_report is not None
            and recovery_report.availability is not RecoveryAvailability.HEALTHY
        ):
            self._dashboard_ready = False
            yield StateRecoveryPanel(recovery_report)
            yield Footer()
            return
        installation = (
            recovery_report.installation
            if recovery_report is not None and recovery_report.installation is not None
            else self.manager.get_installation()
        )
        self._dashboard_ready = True
        active_profiles = sum(
            profile.status is ProfileStatus.APPLIED and profile.enabled
            for profile in installation.profiles
        )
        paused_profiles = sum(
            profile.status is ProfileStatus.APPLIED and not profile.enabled
            for profile in installation.profiles
        )
        draft_profiles = sum(
            profile.status is ProfileStatus.DRAFT for profile in installation.profiles
        )
        runtime_status = (
            "服务状态：正在检查…"
            if self.host_diagnostics is not None
            else "服务状态：未启用主机检查"
        )
        readiness_status = (
            "主机准备度：正在检查…" if self.host_readiness is not None else "主机准备度：未启用检查"
        )
        next_action = self._dashboard_next_action(installation)
        if installation.profiles:
            with Vertical(id="dashboard-profiles"):
                yield Static("代理配置", id="profile-list-title")
                yield Static(runtime_status, id="runtime-status")
                yield Static(readiness_status, id="host-readiness-status")
                yield Static(
                    f"配置：{active_profiles} 在线 · {paused_profiles} 已暂停 · "
                    f"{draft_profiles} 草案",
                    id="profile-summary",
                )
                yield Static(next_action, id="dashboard-next-action")
                yield from self._host_action_buttons(installation)
                for index, profile in enumerate(installation.profiles):
                    port = (
                        "自动选择端口"
                        if profile.listen_port is None
                        else f"端口 {profile.listen_port}"
                    )
                    yield Static(
                        " · ".join(
                            (
                                profile.profile_name,
                                PROTOCOL_LABELS[profile.protocol],
                                (
                                    ("在线" if profile.enabled else "已暂停")
                                    if profile.status is ProfileStatus.APPLIED
                                    else "草案"
                                ),
                                port,
                            )
                        ),
                        id=f"profile-{index}",
                    )
                    if self.profile_details_reader is not None:
                        yield Button(
                            "查看详情",
                            name=profile.profile_id,
                            id=f"view-profile-{index}",
                            classes="view-profile-action",
                        )
                    if profile.status is ProfileStatus.DRAFT and self.profile_applier is not None:
                        yield Button(
                            "应用草案",
                            name=profile.profile_id,
                            id=f"apply-profile-{index}",
                            classes="apply-profile-action",
                            variant="warning",
                        )
                yield Button(
                    "添加配置",
                    id="add-profile",
                    classes="add-profile-action",
                    variant="primary",
                )
                if self.core_updater is not None:
                    yield Button("安装或升级 sing-box 核心", id="manage-core")
        else:
            with Vertical(id="dashboard-empty"):
                yield Static("尚未创建代理配置", id="empty-state-title")
                yield Static(runtime_status, id="runtime-status")
                yield Static(readiness_status, id="host-readiness-status")
                yield Static("配置：0 在线 · 0 已暂停 · 0 草案", id="profile-summary")
                yield Static(next_action, id="dashboard-next-action")
                yield from self._host_action_buttons(installation)
                yield Static("从一个引导式配置开始。应用前你会看到完整变更计划。")
                yield Button(
                    "创建第一个配置",
                    id="create-first-profile",
                    classes="add-profile-action",
                    variant="primary",
                )
                if self.core_updater is not None:
                    yield Button("安装或升级 sing-box 核心", id="manage-core")
        yield Footer()

    def action_show_keyboard_help(self) -> None:
        self.push_screen(KeyboardHelpScreen())

    def action_add_profile(self) -> None:
        if self._dashboard_action_available():
            self.open_protocol_selection()

    def action_open_diagnostics(self) -> None:
        if self._dashboard_action_available() and self.diagnostics_center is not None:
            self.open_diagnostics_center()

    def action_manage_core(self) -> None:
        if self._dashboard_action_available() and self.core_updater is not None:
            self.open_core_update()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "add_profile":
            return self._dashboard_action_available()
        if action == "open_diagnostics":
            return self._dashboard_action_available() and self.diagnostics_center is not None
        if action == "manage_core":
            return self._dashboard_action_available() and self.core_updater is not None
        if action == "quit":
            return self._dashboard_action_available()
        return super().check_action(action, parameters)

    def _dashboard_action_available(self) -> bool:
        return self._dashboard_ready and len(self.screen_stack) == 1

    def _host_action_buttons(self, installation: ManagedInstallation) -> Iterator[Button]:
        if self.diagnostics_center is not None:
            yield Button("打开诊断中心", id="open-diagnostics-center")
        elif self.host_diagnostics is not None:
            yield Button("查看诊断", id="view-diagnostics", disabled=True)
        if self.host_diagnostics is not None:
            yield Button("重新检查服务状态", id="refresh-runtime-status", disabled=True)
        if self.host_readiness is not None:
            yield Button("查看准备度", id="view-readiness", disabled=True)
            yield Button("重新检查", id="refresh-readiness", disabled=True)
        if self.config_adopter is not None and installation.expected_config_sha256 is None:
            yield Button("检查并接管现有配置", id="adopt-existing-config")

    def on_mount(self) -> None:
        if self._dashboard_ready:
            self._start_host_inspections()

    def _start_host_inspections(self) -> None:
        if self.host_diagnostics is not None:
            self.load_host_diagnostics()
        if self.host_readiness is not None:
            self.load_host_readiness()

    @on(Button.Pressed, "#review-state-recovery")
    async def open_state_recovery(self) -> None:
        if self.state_recovery_manager is None:
            return
        report = self.state_recovery_manager.inspect()
        if report.plan is None:
            await self.recompose()
            return
        self.push_screen(
            StateRecoveryConfirmationScreen(self.state_recovery_manager, report.plan),
            self.finish_state_recovery,
        )

    async def finish_state_recovery(self, result: object | None) -> None:
        if result is None:
            return
        await self.recompose()
        self.call_after_refresh(self._start_host_inspections)

    @work(thread=True, exclusive=True)
    def load_host_diagnostics(self) -> None:
        if self.host_diagnostics is None:
            return
        try:
            report = self.host_diagnostics.inspect()
        except Exception:
            self.call_from_thread(self.show_host_diagnostics_failure)
            return
        self.call_from_thread(self.show_host_diagnostics, report)

    def show_host_diagnostics(self, report: HostDiagnosticsReport) -> None:
        self._host_diagnostics_failed = False
        self.host_diagnostics_report = report
        status = (
            "服务状态：运行正常"
            if report.condition is HostCondition.HEALTHY
            else "服务状态：需要检查"
        )
        self.query_one("#runtime-status", Static).update(status)
        if self.diagnostics_center is None:
            self.query_one("#view-diagnostics", Button).disabled = False
        self.query_one("#refresh-runtime-status", Button).disabled = False
        self._update_dashboard_next_action()

    def show_host_diagnostics_failure(self) -> None:
        self._host_diagnostics_failed = True
        self.host_diagnostics_report = None
        self.query_one("#runtime-status", Static).update("服务状态：无法检查")
        if self.diagnostics_center is None:
            self.query_one("#view-diagnostics", Button).disabled = True
        self.query_one("#refresh-runtime-status", Button).disabled = False
        self._update_dashboard_next_action()

    @work(thread=True, exclusive=True)
    def load_host_readiness(self) -> None:
        if self.host_readiness is None:
            return
        try:
            report = self.host_readiness.inspect()
        except Exception:
            self.call_from_thread(self.show_host_readiness_failure)
            return
        self.call_from_thread(self.show_host_readiness, report)

    def show_host_readiness(self, report: HostReadinessReport) -> None:
        self._host_readiness_failed = False
        self.host_readiness_report = report
        status = (
            "主机准备度：可以应用配置"
            if report.ready_for_apply
            else f"主机准备度：需要完成 {report.action_required_count} 项"
        )
        self.query_one("#host-readiness-status", Static).update(status)
        self.query_one("#view-readiness", Button).disabled = False
        self.query_one("#refresh-readiness", Button).disabled = False
        self._update_dashboard_next_action()

    def show_host_readiness_failure(self) -> None:
        self._host_readiness_failed = True
        self.host_readiness_report = None
        self.query_one("#host-readiness-status", Static).update("主机准备度：无法检查")
        self.query_one("#view-readiness", Button).disabled = True
        self.query_one("#refresh-readiness", Button).disabled = False
        self._update_dashboard_next_action()

    def _dashboard_next_action(self, installation: ManagedInstallation) -> str:
        if self._host_readiness_failed or self._host_diagnostics_failed:
            return (
                "建议：先重新检查主机准备度"
                if self._host_readiness_failed
                else "建议：先重新检查服务状态"
            )
        if (
            self.host_readiness_report is not None
            and not self.host_readiness_report.ready_for_apply
        ):
            return f"建议：{self.host_readiness_report.recommended_action}"
        if (
            self.host_diagnostics_report is not None
            and self.host_diagnostics_report.condition is HostCondition.UNHEALTHY
        ):
            return "建议：先检查 sing-box 服务，再进行配置变更"
        draft_profiles = sum(
            profile.status is ProfileStatus.DRAFT for profile in installation.profiles
        )
        if draft_profiles:
            return f"建议：先审阅并应用 {draft_profiles} 个草案"
        if not installation.profiles:
            return "建议：创建第一个配置"
        return "建议：配置已应用，确认服务状态"

    def _update_dashboard_next_action(self) -> None:
        self.query_one("#dashboard-next-action", Static).update(
            self._dashboard_next_action(self.manager.get_installation())
        )

    @on(Button.Pressed, "#view-diagnostics")
    def open_host_diagnostics(self) -> None:
        if self.host_diagnostics_report is not None:
            self.push_screen(HostDiagnosticsScreen(self.host_diagnostics_report))

    @on(Button.Pressed, "#refresh-runtime-status")
    def refresh_host_diagnostics(self) -> None:
        if self.host_diagnostics is None:
            return
        self.host_diagnostics_report = None
        self.query_one("#runtime-status", Static).update("服务状态：正在检查…")
        if self.diagnostics_center is None:
            self.query_one("#view-diagnostics", Button).disabled = True
        self.query_one("#refresh-runtime-status", Button).disabled = True
        self.load_host_diagnostics()

    @on(Button.Pressed, "#open-diagnostics-center")
    def open_diagnostics_center(self) -> None:
        if self.diagnostics_center is not None:
            self.push_screen(
                DiagnosticsCenterScreen(
                    self.diagnostics_center,
                    config_adopter=self.config_adopter,
                    core_updater=self.core_updater,
                    service_log_reader=self.service_log_reader,
                    apply_history_reader=self.apply_history_reader,
                )
            )

    @on(Button.Pressed, "#view-readiness")
    def open_host_readiness(self) -> None:
        if self.host_readiness_report is not None:
            self.push_screen(
                HostReadinessScreen(
                    self.host_readiness_report,
                    core_updater=self.core_updater,
                )
            )

    @on(Button.Pressed, "#refresh-readiness")
    def refresh_host_readiness(self) -> None:
        if self.host_readiness is None:
            return
        self.query_one("#host-readiness-status", Static).update("主机准备度：正在检查…")
        self.query_one("#view-readiness", Button).disabled = True
        self.query_one("#refresh-readiness", Button).disabled = True
        self.load_host_readiness()

    @on(Button.Pressed, ".add-profile-action")
    def open_protocol_selection(self) -> None:
        self.push_screen(
            ProfilePurposeScreen(self.profile_recommendation_advisor),
            self.open_guided_profile_variant,
        )

    def open_guided_profile_variant(self, variant: ProtocolVariant | None) -> None:
        if variant is not None:
            self.push_screen(
                GuidedProfileScreen(
                    self.manager,
                    GUIDED_PROFILES_BY_VARIANT[variant],
                    self.profile_applier,
                )
            )

    @on(Button.Pressed, ".apply-profile-action")
    def open_saved_draft_apply(self, event: Button.Pressed) -> None:
        if self.profile_applier is None or event.button.name is None:
            return
        installation = self.manager.get_installation()
        try:
            profile = next(
                profile
                for profile in installation.profiles
                if profile.profile_id == event.button.name
            )
        except StopIteration:
            return
        if profile.status is not ProfileStatus.DRAFT:
            return
        self.push_screen(
            ApplyConfirmationScreen(
                installation,
                self.profile_applier,
                profile_id=profile.profile_id,
            )
        )

    @on(Button.Pressed, ".view-profile-action")
    def open_profile_details(self, event: Button.Pressed) -> None:
        if self.profile_details_reader is None or event.button.name is None:
            return
        try:
            details = self.profile_details_reader.get_profile_details(event.button.name)
        except ProfileDetailsError:
            self.push_screen(ProfileDetailsErrorScreen())
            return
        self.push_screen(
            ProfileDetailsScreen(
                details,
                profile_editor=self.profile_editor,
                profile_remover=self.profile_remover,
                profile_availability_manager=self.profile_availability_manager,
                profile_cloner=self.profile_cloner,
            )
        )

    @on(Button.Pressed, "#manage-core")
    def open_core_update(self) -> None:
        if self.core_updater is not None:
            self.push_screen(CoreUpdateFormScreen(self.core_updater))

    @on(Button.Pressed, "#adopt-existing-config")
    def open_config_adoption(self) -> None:
        if self.config_adopter is not None:
            self.push_screen(ConfigAdoptionScreen(self.config_adopter))
