from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.apply_history import ApplyHistoryReader
from sb_manager.application.certificate_diagnostics import (
    CertificateDiagnosticCondition,
    CertificateDiagnostics,
    CertificateDiagnosticsReport,
)
from sb_manager.application.config_adoption import ConfigAdopter
from sb_manager.application.core_update import CoreUpdater
from sb_manager.application.dashboard import (
    DashboardActionKind,
    DashboardEvidence,
    DashboardProbeState,
    DashboardRecommendation,
    DashboardRecommendationKind,
    recommend_dashboard_action,
)
from sb_manager.application.diagnostics_center import DiagnosticsCenter
from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnostics,
    HostDiagnosticsReport,
)
from sb_manager.application.host_readiness import HostReadiness, HostReadinessReport
from sb_manager.application.interface_preferences import (
    ColorScheme,
    InterfacePreferences,
    InterfacePreferenceService,
    InterfacePreferenceSnapshot,
    PreferencePersistence,
    PreferenceResetResult,
)
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
from sb_manager.application.network_inventory import build_network_inventory
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
    StateRecoveryReport,
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
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.connection_share import ConnectionSharePanel
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.labels import PROTOCOL_LABELS
from sb_manager.ui.messages import DashboardRefreshRequested
from sb_manager.ui.screens.config_adoption import ConfigAdoptionScreen
from sb_manager.ui.screens.diagnostics_center import (
    DiagnosticsCenterScreen,
    DiagnosticsCenterTools,
)
from sb_manager.ui.screens.host_readiness import HostReadinessScreen
from sb_manager.ui.screens.keyboard_help import KeyboardHelpScreen
from sb_manager.ui.screens.network import NetworkScreen
from sb_manager.ui.screens.operations import OperationsScreen
from sb_manager.ui.screens.preference_reset import (
    PreferenceResetConfirmationScreen,
    PreferenceResetPlanningErrorScreen,
)
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
from sb_manager.ui.screens.profiles import (
    ProfilesScreen,
    ProfileWorkspaceActionKind,
    ProfileWorkspaceActionRequested,
)
from sb_manager.ui.screens.settings import (
    ColorSchemeChangeRequested,
    EffectiveSettings,
    PreferenceResetReviewRequested,
    SettingsScreen,
)
from sb_manager.ui.screens.state_recovery import (
    StateRecoveryConfirmationScreen,
    StateRecoveryInspectionErrorPanel,
    StateRecoveryPanel,
    StateRecoveryPlanningErrorScreen,
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


@dataclass(frozen=True, slots=True)
class ProfileDetailsCapabilities:
    """Lifecycle entries available from one profile-details snapshot."""

    editor: ProfileEditor | None = None
    remover: ProfileRemover | None = None
    availability_manager: ProfileAvailabilityManager | None = None
    cloner: ProfileCloner | None = None


class ProfileDetailsScreen(Screen[None]):
    """Present durable profile identity and reusable client information."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        details: ProfileDetails,
        *,
        capabilities: ProfileDetailsCapabilities | None = None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.details = details
        self.capabilities = capabilities or ProfileDetailsCapabilities()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="profile-details"):
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_TITLE),
                id="profile-details-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_SAFETY),
                id="profile-details-safety",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_NAME, name=self.details.profile_name),
                id="profile-details-name",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_DETAILS_PROTOCOL,
                    protocol=PROTOCOL_LABELS[self.details.protocol],
                ),
                id="profile-details-protocol",
                markup=False,
            )
            status = (
                (
                    self.copy.text(UiText.PROFILE_DETAILS_STATUS_ACTIVE)
                    if self.details.enabled
                    else self.copy.text(UiText.PROFILE_DETAILS_STATUS_PAUSED)
                )
                if self.details.status is ProfileStatus.APPLIED
                else self.copy.text(UiText.PROFILE_DETAILS_STATUS_DRAFT)
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_STATUS, status=status),
                id="profile-details-status",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_DETAILS_SERVER_ADDRESS,
                    address=self.details.server_address,
                )
                if self.details.server_address is not None
                else self.copy.text(UiText.PROFILE_DETAILS_SERVER_ADDRESS_UNSET),
                id="profile-details-server-address",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_DETAILS_LISTEN_PORT,
                    port=self.details.listen_port,
                )
                if self.details.listen_port is not None
                else self.copy.text(UiText.PROFILE_DETAILS_LISTEN_PORT_AUTOMATIC),
                id="profile-details-listen-port",
                markup=False,
            )
            if connection_info := self.details.connection_info:
                yield ConnectionSharePanel(connection_info, self.copy)
            else:
                yield Static(
                    self.copy.text(UiText.PROFILE_DETAILS_NO_CONNECTION),
                    id="profile-details-no-connection",
                    markup=False,
                )
            if self.capabilities.editor is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_DETAILS_EDIT),
                    id="edit-profile",
                    variant="primary",
                )
            if self.capabilities.cloner is not None:
                yield Button(self.copy.text(UiText.PROFILE_DETAILS_CLONE), id="clone-profile")
            if (
                self.capabilities.availability_manager is not None
                and self.details.status is ProfileStatus.APPLIED
            ):
                yield Button(
                    self.copy.text(
                        UiText.PROFILE_DETAILS_PAUSE
                        if self.details.enabled
                        else UiText.PROFILE_DETAILS_RESUME
                    ),
                    id="change-profile-availability",
                    variant="warning",
                )
            if self.capabilities.remover is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_DETAILS_REMOVE),
                    id="remove-profile",
                    variant="error",
                )
        yield Footer()

    @on(Button.Pressed, "#edit-profile")
    def open_profile_editing(self) -> None:
        if self.capabilities.editor is not None:
            self.app.push_screen(
                ProfileEditFormScreen(
                    self.capabilities.editor,
                    details=self.details,
                    copy_catalog=self.copy,
                )
            )

    @on(Button.Pressed, "#remove-profile")
    def open_profile_removal(self) -> None:
        if self.capabilities.remover is None:
            return
        try:
            screen = ProfileRemovalScreen(
                self.capabilities.remover,
                profile_id=self.details.profile_id,
                copy_catalog=self.copy,
            )
        except ProfileRemovalNotFoundError:
            self.app.push_screen(ProfileDetailsErrorScreen(self.copy))
            return
        except Exception:
            self.app.push_screen(ProfileRemovalPlanningErrorScreen(self.copy))
            return
        self.app.push_screen(screen)

    @on(Button.Pressed, "#clone-profile")
    def open_profile_clone(self) -> None:
        if self.capabilities.cloner is None:
            return
        try:
            screen = ProfileCloneScreen(
                self.capabilities.cloner,
                source_profile_id=self.details.profile_id,
                copy_catalog=self.copy,
            )
        except ProfileCloneError:
            self.app.push_screen(ProfileDetailsErrorScreen(self.copy))
            return
        except Exception:
            self.app.push_screen(ProfileClonePlanningErrorScreen(self.copy))
            return
        self.app.push_screen(screen, self.finish_profile_clone)

    def finish_profile_clone(self, result: ProfileCloneResult | None) -> None:
        if result is None:
            return
        self.dismiss()
        self.app.post_message(DashboardRefreshRequested())

    @on(Button.Pressed, "#change-profile-availability")
    def open_profile_availability(self) -> None:
        if self.capabilities.availability_manager is None:
            return
        target = ProfileAvailability.PAUSED if self.details.enabled else ProfileAvailability.ACTIVE
        try:
            plan = self.capabilities.availability_manager.plan_change(
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
            self.app.push_screen(ProfileAvailabilityErrorScreen(str(error), copy_catalog=self.copy))
            return
        except Exception:
            self.app.push_screen(ProfileAvailabilityPlanningErrorScreen(self.copy))
            return
        self.app.push_screen(
            ProfileAvailabilityPlanScreen(
                self.capabilities.availability_manager,
                plan=plan,
                copy_catalog=self.copy,
            )
        )


class ProfileDetailsErrorScreen(Screen[None]):
    """Keep stale or incomplete desired state from terminating the TUI."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-details-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_ERROR_TITLE),
                id="profile-details-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_ERROR_MESSAGE),
                id="profile-details-error-message",
                markup=False,
            )
        yield Footer()


class ProfileDetailsUnexpectedErrorScreen(Screen[None]):
    """Report an unexpected profile-detail read without disclosing its cause."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-details-unexpected-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_UNEXPECTED_TITLE),
                id="profile-details-unexpected-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_UNEXPECTED_DETAILS),
                id="profile-details-unexpected-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_DETAILS_UNEXPECTED_SAFETY),
                id="profile-details-unexpected-safety",
                markup=False,
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
                    yield ConnectionSharePanel(connection_info)
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


class ApplyConfirmationScreen(ConfirmedOperationScreen[None]):
    """Require a second explicit action before host mutation."""

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
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-apply", Button).disabled = True
        self.query_one("#apply-progress", Static).update(
            "操作已确认，正在校验、提交并检查服务健康状态。完成前无法返回。"
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
                self.push_terminal_screen,
                ApplyOperationalErrorScreen(str(error)),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ApplyUnexpectedErrorScreen(),
            )
            return
        self.app.call_from_thread(self.push_terminal_screen, ApplyResultScreen(result))


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


class ProfilePlanningUnexpectedErrorScreen(Screen[None]):
    """Report an unexpected read-only profile-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-planning-error"):
            yield Static("无法准备配置计划", id="profile-planning-error-title")
            yield Static(
                "发生意外错误。底层错误未显示，以避免泄露敏感信息。",
                id="profile-planning-error-details",
            )
            yield Static(
                "尚未创建草案，也未修改服务器。请返回后重新填写，或先检查 desired state 文件访问。",
                id="profile-planning-error-safety",
            )
        yield Footer()


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
        request = PlanProfileRequest(
            profile_name=profile_name,
            protocol=self.definition.protocol,
            listen_port=listen_port,
            server_address=server_address,
            tls=tls,
            transport=transport,
        )
        plan = self._plan_profile(request)
        if plan is None:
            return
        self.app.push_screen(PlanPreviewScreen(self.manager, plan, self.profile_applier))

    def _plan_profile(self, request: PlanProfileRequest) -> ProfilePlan | None:
        try:
            return self.manager.plan_profile(request)
        except PlanValidationError as error:
            for issue in error.issues:
                if error_selector := self.ERROR_SELECTORS.get(issue.field):
                    self.query_one(error_selector, Static).update(issue.message)
            return None
        except Exception:
            self.app.push_screen(ProfilePlanningUnexpectedErrorScreen())
            return None

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
    certificate_diagnostics: CertificateDiagnostics | None = None
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


@dataclass(frozen=True, slots=True)
class ManagerAppInterfaceTools:
    """Effective interface settings and per-user preference capability."""

    effective_settings: EffectiveSettings = field(default_factory=EffectiveSettings)
    preference_service: InterfacePreferenceService | None = None
    copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE


class ManagerApp(App[None]):
    """Guided terminal manager for sing-box."""

    TITLE = "Sing-box Manager"
    SUB_TITLE = SIMPLIFIED_CHINESE.text(UiText.APP_SUBTITLE)

    CSS_PATH = "theme.tcss"
    BINDINGS: ClassVar[list[BindingType]] = [
        ("?", "show_keyboard_help", SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_HELP)),
        (
            "a",
            "add_profile",
            SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_ADD_PROFILE),
        ),
        ("p", "open_profiles", SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_PROFILES)),
        ("n", "open_network", SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_NETWORK)),
        ("s", "open_settings", SIMPLIFIED_CHINESE.text(UiText.SETTINGS_BINDING)),
        (
            "d",
            "open_diagnostics",
            SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_DIAGNOSTICS),
        ),
        ("o", "open_operations", SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_OPERATIONS)),
        ("q", "quit", SIMPLIFIED_CHINESE.text(UiText.APP_BINDING_QUIT)),
    ]
    _DASHBOARD_RECOMMENDATION_COPY: ClassVar[dict[DashboardRecommendationKind, UiText]] = {
        DashboardRecommendationKind.RECHECK_READINESS: (
            UiText.DASHBOARD_RECOMMENDATION_RECHECK_READINESS
        ),
        DashboardRecommendationKind.RECHECK_RUNTIME: (
            UiText.DASHBOARD_RECOMMENDATION_RECHECK_RUNTIME
        ),
        DashboardRecommendationKind.RECHECK_CERTIFICATES: (
            UiText.DASHBOARD_RECOMMENDATION_RECHECK_CERTIFICATES
        ),
        DashboardRecommendationKind.RESOLVE_READINESS: (
            UiText.DASHBOARD_RECOMMENDATION_RESOLVE_READINESS
        ),
        DashboardRecommendationKind.INSPECT_RUNTIME: (
            UiText.DASHBOARD_RECOMMENDATION_INSPECT_RUNTIME
        ),
        DashboardRecommendationKind.RESOLVE_CERTIFICATES: (
            UiText.DASHBOARD_RECOMMENDATION_RESOLVE_CERTIFICATES
        ),
        DashboardRecommendationKind.ADD_PROFILE: UiText.DASHBOARD_RECOMMENDATION_ADD_PROFILE,
        DashboardRecommendationKind.WAIT_FOR_INSPECTIONS: (
            UiText.DASHBOARD_RECOMMENDATION_WAIT_FOR_INSPECTIONS
        ),
        DashboardRecommendationKind.REVIEW_DRAFTS: (UiText.DASHBOARD_RECOMMENDATION_REVIEW_DRAFTS),
        DashboardRecommendationKind.REVIEW_CERTIFICATES: (
            UiText.DASHBOARD_RECOMMENDATION_REVIEW_CERTIFICATES
        ),
        DashboardRecommendationKind.VERIFY_RUNTIME: (
            UiText.DASHBOARD_RECOMMENDATION_VERIFY_RUNTIME
        ),
    }
    _DASHBOARD_ACTION_COPY: ClassVar[dict[DashboardActionKind, UiText]] = {
        DashboardActionKind.RECHECK_READINESS: UiText.DASHBOARD_ACTION_RECHECK_READINESS,
        DashboardActionKind.RECHECK_RUNTIME: UiText.DASHBOARD_ACTION_RECHECK_RUNTIME,
        DashboardActionKind.RECHECK_CERTIFICATES: (UiText.DASHBOARD_ACTION_RECHECK_CERTIFICATES),
        DashboardActionKind.OPEN_READINESS: UiText.DASHBOARD_ACTION_OPEN_READINESS,
        DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS: (
            UiText.DASHBOARD_ACTION_OPEN_RUNTIME_DIAGNOSTICS
        ),
        DashboardActionKind.OPEN_DIAGNOSTICS: UiText.DASHBOARD_ACTION_OPEN_DIAGNOSTICS,
        DashboardActionKind.APPLY_DRAFT: UiText.DASHBOARD_ACTION_APPLY_DRAFT,
        DashboardActionKind.ADD_PROFILE: UiText.DASHBOARD_ACTION_ADD_PROFILE,
    }

    def __init__(
        self,
        manager: Manager | None = None,
        profile_applier: ProfileApplier | None = None,
        core_updater: CoreUpdater | None = None,
        host_tools: ManagerAppHostTools | None = None,
        interface_tools: ManagerAppInterfaceTools | None = None,
    ) -> None:
        super().__init__()
        tools = host_tools or ManagerAppHostTools()
        interface = interface_tools or ManagerAppInterfaceTools()
        self.manager = manager or Manager(state_store=MemoryStateStore())
        self.profile_applier = profile_applier
        self.core_updater = core_updater
        self.host_diagnostics = tools.host_diagnostics
        self.diagnostics_center = tools.diagnostics_center
        self.host_diagnostics_report: HostDiagnosticsReport | None = None
        self.host_readiness = tools.host_readiness
        self.host_readiness_report: HostReadinessReport | None = None
        self.certificate_diagnostics = tools.certificate_diagnostics
        self.certificate_diagnostics_report: CertificateDiagnosticsReport | None = None
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
        self.effective_settings = interface.effective_settings
        self.preference_service = interface.preference_service
        self.copy_catalog = interface.copy_catalog
        preference_snapshot = (
            interface.preference_service.load()
            if interface.preference_service is not None
            else InterfacePreferenceSnapshot(
                preferences=InterfacePreferences(),
                persistence=PreferencePersistence.SESSION_ONLY,
            )
        )
        self._preference_persistence = preference_snapshot.persistence
        self.theme = self._textual_theme(preference_snapshot.preferences.color_scheme)
        self._current_dashboard_recommendation: DashboardRecommendation | None = None
        self._dashboard_ready = False
        self._host_diagnostics_failed = False
        self._host_readiness_failed = False
        self._certificate_diagnostics_failed = False

    def _inspect_state_recovery(
        self,
    ) -> StateRecoveryReport | StateRecoveryInspectionErrorPanel | None:
        if self.state_recovery_manager is not None:
            try:
                return self.state_recovery_manager.inspect()
            except Exception:
                return StateRecoveryInspectionErrorPanel(self.copy_catalog)
        return None

    def _initial_dashboard_statuses(self) -> tuple[str, str, str]:
        runtime = (
            self.copy_catalog.text(UiText.DASHBOARD_RUNTIME_CHECKING)
            if self.host_diagnostics is not None
            else self.copy_catalog.text(UiText.DASHBOARD_RUNTIME_NOT_CONFIGURED)
        )
        readiness = (
            self.copy_catalog.text(UiText.DASHBOARD_READINESS_CHECKING)
            if self.host_readiness is not None
            else self.copy_catalog.text(UiText.DASHBOARD_READINESS_NOT_CONFIGURED)
        )
        certificate = (
            self.copy_catalog.text(UiText.DASHBOARD_CERTIFICATE_CHECKING)
            if self.certificate_diagnostics is not None
            else self.copy_catalog.text(UiText.DASHBOARD_CERTIFICATE_NOT_CONFIGURED)
        )
        return runtime, readiness, certificate

    @staticmethod
    def _profile_counts(installation: ManagedInstallation) -> tuple[int, int, int]:
        active = sum(
            profile.status is ProfileStatus.APPLIED and profile.enabled
            for profile in installation.profiles
        )
        paused = sum(
            profile.status is ProfileStatus.APPLIED and not profile.enabled
            for profile in installation.profiles
        )
        drafts = sum(profile.status is ProfileStatus.DRAFT for profile in installation.profiles)
        return active, paused, drafts

    def _dashboard_recommendation_widgets(
        self,
        recommendation: DashboardRecommendation,
    ) -> Iterator[Static | Button]:
        yield Static(
            self._dashboard_recommendation_text(recommendation),
            id="dashboard-next-action",
        )
        yield self._dashboard_primary_action(recommendation)

    def _dashboard_recommendation_text(
        self,
        recommendation: DashboardRecommendation,
    ) -> str:
        key = self._DASHBOARD_RECOMMENDATION_COPY[recommendation.kind]
        summary = (
            self.copy_catalog.text(key, count=recommendation.draft_count)
            if recommendation.kind is DashboardRecommendationKind.REVIEW_DRAFTS
            else self.copy_catalog.text(key)
        )
        return self.copy_catalog.text(UiText.DASHBOARD_RECOMMENDATION, summary=summary)

    def _dashboard_action_text(self, kind: DashboardActionKind) -> str:
        return self.copy_catalog.text(self._DASHBOARD_ACTION_COPY[kind])

    def _workspace_navigation(self) -> Horizontal:
        return Horizontal(
            Button(self.copy_catalog.text(UiText.DASHBOARD_NAV_PROFILES), id="open-profiles"),
            Button(self.copy_catalog.text(UiText.DASHBOARD_NAV_NETWORK), id="open-network"),
            Button(
                self.copy_catalog.text(UiText.DASHBOARD_NAV_OPERATIONS),
                id="open-operations",
            ),
            Button(self.copy_catalog.text(UiText.SETTINGS_OPEN), id="open-settings"),
            id="dashboard-workspace-navigation",
        )

    def compose(self) -> ComposeResult:
        yield Header()
        recovery_state = self._inspect_state_recovery()
        if isinstance(recovery_state, StateRecoveryInspectionErrorPanel):
            self._dashboard_ready = False
            yield recovery_state
            yield Footer()
            return
        recovery_report = recovery_state
        if (
            recovery_report is not None
            and recovery_report.availability is not RecoveryAvailability.HEALTHY
        ):
            self._dashboard_ready = False
            yield StateRecoveryPanel(recovery_report, self.copy_catalog)
            yield Footer()
            return
        installation = (
            recovery_report.installation
            if recovery_report is not None and recovery_report.installation is not None
            else self.manager.get_installation()
        )
        self._dashboard_ready = True
        active_profiles, paused_profiles, draft_profiles = self._profile_counts(installation)
        runtime_status, readiness_status, certificate_status = self._initial_dashboard_statuses()
        recommendation = self._dashboard_recommendation(installation)
        self._current_dashboard_recommendation = recommendation
        if installation.profiles:
            with Vertical(id="dashboard-profiles"):
                yield Static(self.copy_catalog.text(UiText.DASHBOARD_TITLE), id="dashboard-title")
                yield Static(
                    self.copy_catalog.text(UiText.DASHBOARD_SAFETY),
                    id="dashboard-safety",
                    markup=False,
                )
                yield Static(runtime_status, id="runtime-status")
                yield Static(readiness_status, id="host-readiness-status")
                yield Static(certificate_status, id="certificate-maintenance-status")
                yield Static(
                    self.copy_catalog.text(
                        UiText.DASHBOARD_PROFILE_SUMMARY,
                        active=active_profiles,
                        paused=paused_profiles,
                        drafts=draft_profiles,
                    ),
                    id="profile-summary",
                )
                yield from self._dashboard_recommendation_widgets(recommendation)
                yield from self._host_action_buttons(installation)
                yield self._workspace_navigation()
        else:
            with Vertical(id="dashboard-empty"):
                yield Static(
                    self.copy_catalog.text(UiText.DASHBOARD_EMPTY_TITLE),
                    id="empty-state-title",
                )
                yield Static(
                    self.copy_catalog.text(UiText.DASHBOARD_SAFETY),
                    id="dashboard-safety",
                    markup=False,
                )
                yield Static(runtime_status, id="runtime-status")
                yield Static(readiness_status, id="host-readiness-status")
                yield Static(certificate_status, id="certificate-maintenance-status")
                yield Static(
                    self.copy_catalog.text(
                        UiText.DASHBOARD_PROFILE_SUMMARY,
                        active=0,
                        paused=0,
                        drafts=0,
                    ),
                    id="profile-summary",
                )
                yield from self._dashboard_recommendation_widgets(recommendation)
                yield from self._host_action_buttons(installation)
                yield Static(self.copy_catalog.text(UiText.DASHBOARD_EMPTY_GUIDANCE))
                yield self._workspace_navigation()
        yield Footer()

    def action_show_keyboard_help(self) -> None:
        self.push_screen(KeyboardHelpScreen())

    def action_add_profile(self) -> None:
        if self._dashboard_action_available():
            self.open_protocol_selection()

    def action_open_profiles(self) -> None:
        if self._dashboard_action_available():
            self.open_profiles_workspace()

    def action_open_network(self) -> None:
        if self._dashboard_action_available():
            self.open_network_workspace()

    def action_open_settings(self) -> None:
        if self._dashboard_action_available():
            self.open_settings_workspace()

    def action_open_diagnostics(self) -> None:
        if self._dashboard_action_available() and self.diagnostics_center is not None:
            self.open_diagnostics_center()

    def action_open_operations(self) -> None:
        if self._dashboard_action_available():
            self.open_operations_center()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {
            "add_profile",
            "open_profiles",
            "open_network",
            "open_settings",
            "open_operations",
            "quit",
        }:
            return self._dashboard_action_available()
        if action == "open_diagnostics":
            return self._dashboard_action_available() and self.diagnostics_center is not None
        return super().check_action(action, parameters)

    def _dashboard_action_available(self) -> bool:
        return self._dashboard_ready and len(self.screen_stack) == 1

    def _host_action_buttons(self, installation: ManagedInstallation) -> Iterator[Button]:
        if self.diagnostics_center is not None:
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_OPEN_DIAGNOSTICS),
                id="open-diagnostics-center",
            )
        elif self.host_diagnostics is not None:
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_VIEW_DIAGNOSTICS),
                id="view-diagnostics",
                disabled=True,
            )
        if self.host_diagnostics is not None:
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_REFRESH_RUNTIME),
                id="refresh-runtime-status",
                disabled=True,
            )
        if self.host_readiness is not None:
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_VIEW_READINESS),
                id="view-readiness",
                disabled=True,
            )
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_REFRESH_READINESS),
                id="refresh-readiness",
                disabled=True,
            )
        if self.certificate_diagnostics is not None:
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_REFRESH_CERTIFICATES),
                id="refresh-certificate-maintenance",
                disabled=True,
            )
        if self.config_adopter is not None and installation.expected_config_sha256 is None:
            yield Button(
                self.copy_catalog.text(UiText.DASHBOARD_ADOPT_CONFIGURATION),
                id="adopt-existing-config",
            )

    def on_mount(self) -> None:
        if self._dashboard_ready:
            self._start_dashboard_inspections()

    def _start_dashboard_inspections(self) -> None:
        if self.host_diagnostics is not None:
            self.load_host_diagnostics()
        if self.host_readiness is not None:
            self.load_host_readiness()
        if self.certificate_diagnostics is not None:
            self.load_certificate_diagnostics()

    @on(DashboardRefreshRequested)
    async def refresh_dashboard(self) -> None:
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.host_diagnostics_report = None
        self.host_readiness_report = None
        self.certificate_diagnostics_report = None
        self._host_diagnostics_failed = False
        self._host_readiness_failed = False
        self._certificate_diagnostics_failed = False
        await self.recompose()
        self.call_after_refresh(self._start_dashboard_inspections)

    @work(thread=True, exclusive=True)
    def load_certificate_diagnostics(self) -> None:
        if self.certificate_diagnostics is None:
            return
        try:
            report = self.certificate_diagnostics.inspect(self.manager.get_installation())
        except Exception:
            self.call_from_thread(self.show_certificate_diagnostics_failure)
            return
        self.call_from_thread(self.show_certificate_diagnostics, report)

    def show_certificate_diagnostics(self, report: CertificateDiagnosticsReport) -> None:
        self._certificate_diagnostics_failed = False
        self.certificate_diagnostics_report = report
        if report.condition is CertificateDiagnosticCondition.ACTION_REQUIRED:
            key = UiText.DASHBOARD_CERTIFICATE_ACTION_REQUIRED
        elif report.condition is CertificateDiagnosticCondition.ATTENTION:
            key = UiText.DASHBOARD_CERTIFICATE_ATTENTION
        else:
            key = UiText.DASHBOARD_CERTIFICATE_HEALTHY
        self.query_one("#certificate-maintenance-status", Static).update(
            self.copy_catalog.text(key)
        )
        self.query_one("#refresh-certificate-maintenance", Button).disabled = False
        self._update_dashboard_next_action()

    def show_certificate_diagnostics_failure(self) -> None:
        self._certificate_diagnostics_failed = True
        self.certificate_diagnostics_report = None
        self.query_one("#certificate-maintenance-status", Static).update(
            self.copy_catalog.text(UiText.DASHBOARD_CERTIFICATE_FAILED)
        )
        self.query_one("#refresh-certificate-maintenance", Button).disabled = False
        self._update_dashboard_next_action()

    @on(Button.Pressed, "#review-state-recovery")
    def open_state_recovery(self) -> None:
        if self.state_recovery_manager is None:
            return
        try:
            report = self.state_recovery_manager.inspect()
        except Exception:
            self.push_screen(StateRecoveryPlanningErrorScreen(self.copy_catalog))
            return
        if report.plan is None:
            self.post_message(DashboardRefreshRequested())
            return
        self.push_screen(
            StateRecoveryConfirmationScreen(
                self.state_recovery_manager,
                report.plan,
                self.copy_catalog,
            )
        )

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
        key = (
            UiText.DASHBOARD_RUNTIME_HEALTHY
            if report.condition is HostCondition.HEALTHY
            else UiText.DASHBOARD_RUNTIME_UNHEALTHY
        )
        self.query_one("#runtime-status", Static).update(self.copy_catalog.text(key))
        if self.diagnostics_center is None:
            self.query_one("#view-diagnostics", Button).disabled = False
        self.query_one("#refresh-runtime-status", Button).disabled = False
        self._update_dashboard_next_action()

    def show_host_diagnostics_failure(self) -> None:
        self._host_diagnostics_failed = True
        self.host_diagnostics_report = None
        self.query_one("#runtime-status", Static).update(
            self.copy_catalog.text(UiText.DASHBOARD_RUNTIME_FAILED)
        )
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
            self.copy_catalog.text(UiText.DASHBOARD_READINESS_READY)
            if report.ready_for_apply
            else self.copy_catalog.text(
                UiText.DASHBOARD_READINESS_ACTION_REQUIRED,
                count=report.action_required_count,
            )
        )
        self.query_one("#host-readiness-status", Static).update(status)
        self.query_one("#view-readiness", Button).disabled = False
        self.query_one("#refresh-readiness", Button).disabled = False
        self._update_dashboard_next_action()

    def show_host_readiness_failure(self) -> None:
        self._host_readiness_failed = True
        self.host_readiness_report = None
        self.query_one("#host-readiness-status", Static).update(
            self.copy_catalog.text(UiText.DASHBOARD_READINESS_FAILED)
        )
        self.query_one("#view-readiness", Button).disabled = True
        self.query_one("#refresh-readiness", Button).disabled = False
        self._update_dashboard_next_action()

    def _dashboard_recommendation(
        self,
        installation: ManagedInstallation,
    ) -> DashboardRecommendation:
        runtime: DashboardProbeState | HostDiagnosticsReport
        if self._host_diagnostics_failed:
            runtime = DashboardProbeState.FAILED
        elif self.host_diagnostics_report is not None:
            runtime = self.host_diagnostics_report
        elif self.host_diagnostics is not None:
            runtime = DashboardProbeState.PENDING
        else:
            runtime = DashboardProbeState.NOT_CONFIGURED

        readiness: DashboardProbeState | HostReadinessReport
        if self._host_readiness_failed:
            readiness = DashboardProbeState.FAILED
        elif self.host_readiness_report is not None:
            readiness = self.host_readiness_report
        elif self.host_readiness is not None:
            readiness = DashboardProbeState.PENDING
        else:
            readiness = DashboardProbeState.NOT_CONFIGURED

        certificates: DashboardProbeState | CertificateDiagnosticsReport
        if self._certificate_diagnostics_failed:
            certificates = DashboardProbeState.FAILED
        elif self.certificate_diagnostics_report is not None:
            certificates = self.certificate_diagnostics_report
        elif self.certificate_diagnostics is not None:
            certificates = DashboardProbeState.PENDING
        else:
            certificates = DashboardProbeState.NOT_CONFIGURED

        return recommend_dashboard_action(
            DashboardEvidence(
                installation=installation,
                runtime=runtime,
                readiness=readiness,
                certificates=certificates,
                diagnostics_available=self.diagnostics_center is not None,
                profile_apply_available=self.profile_applier is not None,
            )
        )

    def _dashboard_primary_action(
        self,
        recommendation: DashboardRecommendation,
    ) -> Button:
        action = recommendation.action
        return Button(
            self._dashboard_action_text(action.kind)
            if action is not None
            else self.copy_catalog.text(UiText.DASHBOARD_NO_ACTION),
            id="dashboard-primary-action",
            classes="" if action is not None else "hidden",
            disabled=action is None,
            variant="primary",
        )

    def _update_dashboard_next_action(self) -> None:
        recommendation = self._dashboard_recommendation(self.manager.get_installation())
        self._current_dashboard_recommendation = recommendation
        self.query_one("#dashboard-next-action", Static).update(
            self._dashboard_recommendation_text(recommendation)
        )
        button = self.query_one("#dashboard-primary-action", Button)
        if recommendation.action is None:
            button.disabled = True
            button.add_class("hidden")
            return
        button.label = self._dashboard_action_text(recommendation.action.kind)
        button.disabled = False
        button.remove_class("hidden")

    @on(Button.Pressed, "#dashboard-primary-action")
    def execute_dashboard_primary_action(self) -> None:
        recommendation = self._current_dashboard_recommendation
        if recommendation is None or recommendation.action is None:
            return
        action = recommendation.action
        if action.kind is DashboardActionKind.RECHECK_READINESS:
            self.refresh_host_readiness()
        elif action.kind is DashboardActionKind.RECHECK_RUNTIME:
            self.refresh_host_diagnostics()
        elif action.kind is DashboardActionKind.RECHECK_CERTIFICATES:
            self.refresh_certificate_diagnostics()
        elif action.kind is DashboardActionKind.OPEN_READINESS:
            self.open_host_readiness()
        elif action.kind is DashboardActionKind.OPEN_RUNTIME_DIAGNOSTICS:
            self.open_host_diagnostics()
        elif action.kind is DashboardActionKind.OPEN_DIAGNOSTICS:
            self.open_diagnostics_center()
        elif action.kind is DashboardActionKind.APPLY_DRAFT:
            if action.profile_id is not None:
                self._open_saved_draft_apply(action.profile_id)
        elif action.kind is DashboardActionKind.ADD_PROFILE:
            self.open_protocol_selection()

    @on(Button.Pressed, "#view-diagnostics")
    def open_host_diagnostics(self) -> None:
        if self.host_diagnostics_report is not None:
            self.push_screen(HostDiagnosticsScreen(self.host_diagnostics_report))

    @on(Button.Pressed, "#refresh-runtime-status")
    def refresh_host_diagnostics(self) -> None:
        if self.host_diagnostics is None:
            return
        self._host_diagnostics_failed = False
        self.host_diagnostics_report = None
        self.query_one("#runtime-status", Static).update(
            self.copy_catalog.text(UiText.DASHBOARD_RUNTIME_CHECKING)
        )
        if self.diagnostics_center is None:
            self.query_one("#view-diagnostics", Button).disabled = True
        self.query_one("#refresh-runtime-status", Button).disabled = True
        self._update_dashboard_next_action()
        self.load_host_diagnostics()

    @on(Button.Pressed, "#open-diagnostics-center")
    def open_diagnostics_center(self) -> None:
        if self.diagnostics_center is not None:
            self.push_screen(
                DiagnosticsCenterScreen(
                    self.diagnostics_center,
                    tools=DiagnosticsCenterTools(
                        config_adopter=self.config_adopter,
                        core_updater=self.core_updater,
                        service_log_reader=self.service_log_reader,
                        apply_history_reader=self.apply_history_reader,
                    ),
                    copy_catalog=self.copy_catalog,
                )
            )

    @on(Button.Pressed, "#open-operations")
    def open_operations_center(self) -> None:
        self.push_screen(
            OperationsScreen(
                core_updater=self.core_updater,
                service_log_reader=self.service_log_reader,
                apply_history_reader=self.apply_history_reader,
                copy_catalog=self.copy_catalog,
            )
        )

    @on(Button.Pressed, "#open-profiles")
    def open_profiles_workspace(self) -> None:
        self.push_screen(
            ProfilesScreen(
                self.manager.get_installation(),
                details_available=self.profile_details_reader is not None,
                apply_available=self.profile_applier is not None,
                copy_catalog=self.copy_catalog,
            )
        )

    @on(Button.Pressed, "#open-network")
    def open_network_workspace(self) -> None:
        self.push_screen(NetworkScreen(build_network_inventory(self.manager.get_installation())))

    @on(Button.Pressed, "#open-settings")
    def open_settings_workspace(self) -> None:
        color_scheme = ColorScheme.DARK if self.current_theme.dark else ColorScheme.LIGHT
        self.push_screen(
            SettingsScreen(
                color_scheme,
                self.effective_settings,
                self._preference_persistence,
                self.copy_catalog,
            )
        )

    @on(ColorSchemeChangeRequested)
    def change_color_scheme(self, event: ColorSchemeChangeRequested) -> None:
        self.theme = self._textual_theme(event.color_scheme)
        if self.preference_service is not None:
            snapshot = self.preference_service.save_color_scheme(event.color_scheme)
            self._preference_persistence = snapshot.persistence
            if isinstance(self.screen, SettingsScreen):
                self.screen.show_preference_persistence(snapshot.persistence)

    @on(PreferenceResetReviewRequested)
    def open_preference_reset(self) -> None:
        if self.preference_service is None:
            return
        try:
            plan = self.preference_service.plan_reset()
        except Exception:
            self.push_screen(PreferenceResetPlanningErrorScreen(self.copy_catalog))
            return
        self.push_screen(
            PreferenceResetConfirmationScreen(
                self.preference_service,
                plan,
                self.copy_catalog,
            ),
            self.finish_preference_reset,
        )

    def finish_preference_reset(self, result: PreferenceResetResult | None) -> None:
        if result is None:
            return
        self._preference_persistence = result.snapshot.persistence
        self.theme = self._textual_theme(result.snapshot.preferences.color_scheme)
        if isinstance(self.screen, SettingsScreen):
            self.screen.show_preference_reset()

    @staticmethod
    def _textual_theme(color_scheme: ColorScheme) -> str:
        return "textual-light" if color_scheme is ColorScheme.LIGHT else "textual-dark"

    @on(ProfileWorkspaceActionRequested)
    def handle_profile_workspace_action(
        self,
        event: ProfileWorkspaceActionRequested,
    ) -> None:
        if event.kind is ProfileWorkspaceActionKind.ADD_PROFILE:
            self.open_protocol_selection()
        elif event.kind is ProfileWorkspaceActionKind.VIEW_DETAILS and event.profile_id is not None:
            self._open_profile_details(event.profile_id)
        elif event.kind is ProfileWorkspaceActionKind.APPLY_DRAFT and event.profile_id is not None:
            self._open_saved_draft_apply(event.profile_id)

    @on(Button.Pressed, "#view-readiness")
    def open_host_readiness(self) -> None:
        if self.host_readiness_report is not None:
            self.push_screen(
                HostReadinessScreen(
                    self.host_readiness_report,
                    core_updater=self.core_updater,
                    copy_catalog=self.copy_catalog,
                )
            )

    @on(Button.Pressed, "#refresh-readiness")
    def refresh_host_readiness(self) -> None:
        if self.host_readiness is None:
            return
        self._host_readiness_failed = False
        self.host_readiness_report = None
        self.query_one("#host-readiness-status", Static).update(
            self.copy_catalog.text(UiText.DASHBOARD_READINESS_CHECKING)
        )
        self.query_one("#view-readiness", Button).disabled = True
        self.query_one("#refresh-readiness", Button).disabled = True
        self._update_dashboard_next_action()
        self.load_host_readiness()

    @on(Button.Pressed, "#refresh-certificate-maintenance")
    def refresh_certificate_diagnostics(self) -> None:
        if self.certificate_diagnostics is None:
            return
        self._certificate_diagnostics_failed = False
        self.certificate_diagnostics_report = None
        self.query_one("#certificate-maintenance-status", Static).update(
            self.copy_catalog.text(UiText.DASHBOARD_CERTIFICATE_CHECKING)
        )
        self.query_one("#refresh-certificate-maintenance", Button).disabled = True
        self._update_dashboard_next_action()
        self.load_certificate_diagnostics()

    def open_protocol_selection(self) -> None:
        self.push_screen(
            ProfilePurposeScreen(
                self.profile_recommendation_advisor,
                self.copy_catalog,
            ),
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

    def _open_saved_draft_apply(self, profile_id: str) -> None:
        if self.profile_applier is None:
            return
        installation = self.manager.get_installation()
        try:
            profile = next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
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

    def _open_profile_details(self, profile_id: str) -> None:
        if self.profile_details_reader is None:
            return
        try:
            details = self.profile_details_reader.get_profile_details(profile_id)
        except ProfileDetailsError:
            self.push_screen(ProfileDetailsErrorScreen(self.copy_catalog))
            return
        except Exception:
            self.push_screen(ProfileDetailsUnexpectedErrorScreen(self.copy_catalog))
            return
        self.push_screen(
            ProfileDetailsScreen(
                details,
                capabilities=ProfileDetailsCapabilities(
                    editor=self.profile_editor,
                    remover=self.profile_remover,
                    availability_manager=self.profile_availability_manager,
                    cloner=self.profile_cloner,
                ),
                copy_catalog=self.copy_catalog,
            )
        )

    @on(Button.Pressed, "#adopt-existing-config")
    def open_config_adoption(self) -> None:
        if self.config_adopter is not None:
            self.push_screen(ConfigAdoptionScreen(self.config_adopter, self.copy_catalog))
