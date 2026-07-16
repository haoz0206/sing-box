from dataclasses import dataclass
from typing import ClassVar

from textual import on
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Static

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.manager import (
    AcmeTlsRequest,
    GeneratedValue,
    Manager,
    PlanProfileRequest,
    PlanValidationError,
    ProfilePlan,
    WebSocketTransportRequest,
)
from sb_manager.application.profile_apply import (
    ApplyProfileRequest,
    ApplyProfileResult,
    ProfileApplier,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.tls.catalog import AcmeTlsIntent
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.transports.catalog import WebSocketTransportIntent


@dataclass(frozen=True, slots=True)
class GuidedProfileDefinition:
    """Protocol-specific copy and identity for the shared profile form."""

    protocol: ProtocolKind
    form_id: str
    title_id: str
    guidance_id: str
    title: str
    guidance: str
    uses_acme: bool = False
    uses_websocket: bool = False


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
    uses_acme=True,
)
TROJAN_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.TROJAN,
    form_id="trojan-form",
    title_id="trojan-form-title",
    guidance_id="trojan-guidance",
    title="配置 Trojan",
    guidance="基于 TLS 的兼容协议。认证密码自动生成，证书通过 ACME 申请。",
    uses_acme=True,
)
ANYTLS_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.ANYTLS,
    form_id="anytls-form",
    title_id="anytls-form-title",
    guidance_id="anytls-guidance",
    title="配置 AnyTLS",
    guidance="用于缓解 TLS 嵌套指纹。认证密码自动生成，证书通过 ACME 申请。",
    uses_acme=True,
)
TUIC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.TUIC,
    form_id="tuic-form",
    title_id="tuic-form-title",
    guidance_id="tuic-guidance",
    title="配置 TUIC",
    guidance="基于 QUIC 的低延迟协议。默认关闭可重放的 0-RTT。",
    uses_acme=True,
)
VLESS_WEBSOCKET_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_TLS,
    form_id="vless-websocket-form",
    title_id="vless-websocket-form-title",
    guidance_id="vless-websocket-guidance",
    title="配置 VLESS TLS WebSocket",
    guidance="适合需要 WebSocket 或 CDN 兼容入口的场景。",
    uses_acme=True,
    uses_websocket=True,
)


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


class ApplyConfirmationScreen(Screen[None]):
    """Require a second explicit action before host mutation."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "取消")]

    def __init__(
        self,
        installation: ManagedInstallation,
        profile_applier: ProfileApplier,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.profile_applier = profile_applier

    def compose(self) -> ComposeResult:
        profile = self.installation.profiles[-1]
        yield Header()
        with Vertical(id="apply-confirmation"):
            yield Static("即将修改服务器", id="apply-confirm-title")
            yield Static(f"配置：{profile.profile_name}", id="apply-confirm-profile")
            yield Static(
                "将写入 sing-box 配置并刷新服务，失败时自动回滚。",
                id="apply-confirm-warning",
            )
            yield Button("确认并应用", id="confirm-apply", variant="error")
        yield Footer()

    @on(Button.Pressed, "#confirm-apply")
    def confirm_apply(self) -> None:
        profile = self.installation.profiles[-1]
        result = self.profile_applier.apply_profile(
            ApplyProfileRequest(
                profile_id=profile.profile_id,
                expected_revision=self.installation.revision,
                confirmed=True,
            )
        )
        self.app.push_screen(ApplyResultScreen(result))


class DraftSavedScreen(Screen[None]):
    """Confirm that desired state was saved without applying host changes."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        installation: ManagedInstallation,
        profile_applier: ProfileApplier | None = None,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.profile_applier = profile_applier

    def compose(self) -> ComposeResult:
        profile = self.installation.profiles[-1]
        yield Header()
        with Vertical(id="draft-saved"):
            yield Static("草案已保存", id="draft-saved-title")
            yield Static(profile.profile_name, id="saved-profile")
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
            self.app.push_screen(ApplyConfirmationScreen(self.installation, self.profile_applier))


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
        GeneratedValue.TLS_CERTIFICATE: "TLS 证书",
    }
    PROTOCOL_LABELS: ClassVar[dict[ProtocolKind, str]] = {
        ProtocolKind.VLESS_REALITY: "VLESS Reality",
        ProtocolKind.SHADOWSOCKS: "Shadowsocks 2022",
        ProtocolKind.HYSTERIA2: "Hysteria2",
        ProtocolKind.TROJAN: "Trojan",
        ProtocolKind.ANYTLS: "AnyTLS",
        ProtocolKind.TUIC: "TUIC",
        ProtocolKind.VLESS_TLS: "VLESS TLS",
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
                f"协议：{self.PROTOCOL_LABELS[self.plan.protocol]}",
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
            if isinstance(self.plan.transport_intent, WebSocketTransportIntent):
                transport_summary = f"传输：WebSocket · {self.plan.transport_intent.path}"
                if self.plan.transport_intent.host is not None:
                    transport_summary += f" · Host {self.plan.transport_intent.host}"
                yield Static(transport_summary, id="plan-transport")
            yield Static(f"自动生成：{generated}", id="plan-generated")
            yield Static("当前仅预览，不会修改服务器。", id="plan-safety")
            yield Button("保存为草案", id="save-draft", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#save-draft")
    def save_draft(self) -> None:
        self.manager.save_profile_draft(self.plan)
        self.app.push_screen(
            DraftSavedScreen(self.manager.get_installation(), self.profile_applier)
        )


class GuidedProfileScreen(Screen[None]):
    """Collect common intent using protocol-specific operator guidance."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]
    ERROR_SELECTORS: ClassVar[dict[str, str]] = {
        "profile_name": "#profile-name-error",
        "listen_port": "#listen-port-error",
        "tls_server_name": "#tls-server-name-error",
        "tls_email": "#tls-email-error",
        "websocket_path": "#websocket-path-error",
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
            if self.definition.uses_acme
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
            if self.definition.uses_acme:
                yield Label("TLS 证书域名", classes="field-label")
                yield Input(placeholder="例如：vpn.example.com", id="tls-server-name")
                yield Static("", id="tls-server-name-error", classes="field-error")
                yield Label("ACME 联系邮箱", classes="field-label")
                yield Input(placeholder="例如：operator@example.com", id="tls-email")
                yield Static("", id="tls-email-error", classes="field-error")
            if self.definition.uses_websocket:
                yield Label("WebSocket 路径", classes="field-label")
                yield Input(placeholder="例如：/proxy", id="websocket-path")
                yield Static("", id="websocket-path-error", classes="field-error")
                yield Label("WebSocket Host (可选)", classes="field-label")
                yield Input(placeholder="例如：vpn.example.com", id="websocket-host")
            yield Label("监听端口", classes="field-label")
            yield Input(placeholder="留空自动选择", id="listen-port", type="integer")
            yield Static("", id="listen-port-error", classes="field-error")
            yield Button("预览变更计划", id="preview-plan", variant="primary")
        yield Footer()

    @on(Button.Pressed, "#preview-plan")
    def preview_plan(self) -> None:
        profile_name = self.query_one("#profile-name", Input).value
        server_address = self.query_one("#server-address", Input).value
        tls = None
        if self.definition.uses_acme:
            tls = AcmeTlsRequest(
                server_name=self.query_one("#tls-server-name", Input).value,
                email=self.query_one("#tls-email", Input).value,
            )
        transport = None
        if self.definition.uses_websocket:
            transport = WebSocketTransportRequest(
                path=self.query_one("#websocket-path", Input).value,
                host=self.query_one("#websocket-host", Input).value,
            )
        port_text = self.query_one("#listen-port", Input).value
        listen_port = int(port_text) if port_text else None
        visible_error_fields = ["profile_name", "listen_port"]
        if self.definition.uses_acme:
            visible_error_fields.extend(("tls_server_name", "tls_email"))
        if self.definition.uses_websocket:
            visible_error_fields.append("websocket_path")
        for field in visible_error_fields:
            self.query_one(self.ERROR_SELECTORS[field], Static).update("")
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


class ProtocolSelectionScreen(Screen[None]):
    """Help an operator choose a protocol without requiring protocol syntax."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "app.pop_screen", "返回")]

    def __init__(
        self,
        manager: Manager,
        profile_applier: ProfileApplier | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.profile_applier = profile_applier

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="protocol-selection"):
            yield Static("选择适合你的协议", id="protocol-selection-title")
            yield Static("从推荐选项开始。高级协议会在后续版本逐步开放。")
            yield Button(
                "VLESS Reality · 推荐",
                id="protocol-vless-reality",
                variant="primary",
            )
            yield Button(
                "Shadowsocks 2022 · 简洁稳定",
                id="protocol-shadowsocks",
            )
            yield Button(
                "Hysteria2 · 移动网络",
                id="protocol-hysteria2",
            )
            yield Button(
                "Trojan · TLS 兼容",
                id="protocol-trojan",
            )
            yield Button(
                "AnyTLS · 抗 TLS 嵌套指纹",
                id="protocol-anytls",
            )
            yield Button("TUIC · QUIC 低延迟", id="protocol-tuic")
            yield Button(
                "VLESS TLS · WebSocket/CDN",
                id="protocol-vless-websocket",
            )
        yield Footer()

    @on(Button.Pressed, "#protocol-vless-reality")
    def open_reality_form(self) -> None:
        self.app.push_screen(
            GuidedProfileScreen(self.manager, REALITY_PROFILE, self.profile_applier)
        )

    @on(Button.Pressed, "#protocol-shadowsocks")
    def open_shadowsocks_form(self) -> None:
        self.app.push_screen(
            GuidedProfileScreen(self.manager, SHADOWSOCKS_PROFILE, self.profile_applier)
        )

    @on(Button.Pressed, "#protocol-hysteria2")
    def open_hysteria2_form(self) -> None:
        self.app.push_screen(
            GuidedProfileScreen(self.manager, HYSTERIA2_PROFILE, self.profile_applier)
        )

    @on(Button.Pressed, "#protocol-trojan")
    def open_trojan_form(self) -> None:
        self.app.push_screen(
            GuidedProfileScreen(self.manager, TROJAN_PROFILE, self.profile_applier)
        )

    @on(Button.Pressed, "#protocol-anytls")
    def open_anytls_form(self) -> None:
        self.app.push_screen(
            GuidedProfileScreen(self.manager, ANYTLS_PROFILE, self.profile_applier)
        )

    @on(Button.Pressed, "#protocol-tuic")
    def open_tuic_form(self) -> None:
        self.app.push_screen(GuidedProfileScreen(self.manager, TUIC_PROFILE, self.profile_applier))

    @on(Button.Pressed, "#protocol-vless-websocket")
    def open_vless_websocket_form(self) -> None:
        self.app.push_screen(
            GuidedProfileScreen(self.manager, VLESS_WEBSOCKET_PROFILE, self.profile_applier)
        )


class ManagerApp(App[None]):
    """Guided terminal manager for sing-box."""

    TITLE = "Sing-box Manager"
    SUB_TITLE = "安全地搭建和维护你的代理服务"

    PROTOCOL_LABELS: ClassVar[dict[ProtocolKind, str]] = {
        ProtocolKind.VLESS_REALITY: "VLESS Reality",
        ProtocolKind.SHADOWSOCKS: "Shadowsocks 2022",
        ProtocolKind.HYSTERIA2: "Hysteria2",
        ProtocolKind.TROJAN: "Trojan",
        ProtocolKind.ANYTLS: "AnyTLS",
        ProtocolKind.TUIC: "TUIC",
        ProtocolKind.VLESS_TLS: "VLESS TLS",
    }
    STATUS_LABELS: ClassVar[dict[ProfileStatus, str]] = {
        ProfileStatus.DRAFT: "草案",
        ProfileStatus.APPLIED: "已应用",
    }

    CSS = """
    Screen {
        align: center middle;
    }

    Header, Footer {
        dock: top;
    }

    Footer {
        dock: bottom;
    }

    #dashboard-empty, #dashboard-profiles, #protocol-selection, #reality-form,
    #shadowsocks-form,
    #hysteria2-form,
    #trojan-form,
    #anytls-form,
    #tuic-form,
    #vless-websocket-form,
    #plan-preview, #draft-saved, #apply-confirmation, #apply-result {
        width: 72;
        max-width: 90%;
        height: auto;
        padding: 2 4;
        border: round $primary;
        background: $surface;
    }

    #empty-state-title, #protocol-selection-title, #reality-form-title,
    #shadowsocks-form-title, #plan-title,
    #hysteria2-form-title,
    #trojan-form-title,
    #anytls-form-title,
    #tuic-form-title,
    #vless-websocket-form-title,
    #draft-saved-title {
        margin-bottom: 1;
        text-style: bold;
    }

    .field-label {
        margin-top: 0;
    }

    .field-error {
        color: $error;
    }

    Button {
        margin-top: 1;
        width: 100%;
    }

    #protocol-selection, #hysteria2-form, #trojan-form, #anytls-form, #tuic-form,
    #vless-websocket-form {
        max-height: 90%;
    }
    """

    def __init__(
        self,
        manager: Manager | None = None,
        profile_applier: ProfileApplier | None = None,
    ) -> None:
        super().__init__()
        self.manager = manager or Manager(state_store=MemoryStateStore())
        self.profile_applier = profile_applier

    def compose(self) -> ComposeResult:
        yield Header()
        installation = self.manager.get_installation()
        if installation.profiles:
            with Vertical(id="dashboard-profiles"):
                yield Static("代理配置", id="profile-list-title")
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
                                self.PROTOCOL_LABELS[profile.protocol],
                                self.STATUS_LABELS[profile.status],
                                port,
                            )
                        ),
                        id=f"profile-{index}",
                    )
                yield Button(
                    "添加配置",
                    id="add-profile",
                    classes="add-profile-action",
                    variant="primary",
                )
        else:
            with Vertical(id="dashboard-empty"):
                yield Static("尚未创建代理配置", id="empty-state-title")
                yield Static("从一个引导式配置开始。应用前你会看到完整变更计划。")
                yield Button(
                    "创建第一个配置",
                    id="create-first-profile",
                    classes="add-profile-action",
                    variant="primary",
                )
        yield Footer()

    @on(Button.Pressed, ".add-profile-action")
    def open_protocol_selection(self) -> None:
        self.push_screen(ProtocolSelectionScreen(self.manager, self.profile_applier))
