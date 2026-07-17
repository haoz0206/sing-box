from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from textual import on, work
from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from sb_manager.application.manager import (
    AcmeTlsRequest,
    GeneratedValue,
    GrpcTransportRequest,
    Manager,
    OperatorFileTlsRequest,
    PlanProfileRequest,
    PlanValidationError,
    ProfilePlan,
    StateRevisionConflictError,
    TlsRequest,
    TransportRequest,
    ValidationIssue,
    ValidationIssueCode,
    WebSocketTransportRequest,
)
from sb_manager.application.profile_apply import (
    ApplyProfileRequest,
    ApplyProfileResult,
    ProfileApplier,
)
from sb_manager.application.profile_recommendation import ProtocolVariant
from sb_manager.domain.installation import ManagedInstallation, PortSelection, ProtocolKind
from sb_manager.seams.configuration_applier import ConfigurationApplyError
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent
from sb_manager.transactions.apply import ApplyOutcome
from sb_manager.transports.catalog import GrpcTransportIntent, WebSocketTransportIntent
from sb_manager.ui.confirmed_operation import ConfirmedOperationScreen
from sb_manager.ui.connection_share import ConnectionSharePanel
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.labels import PROTOCOL_LABELS
from sb_manager.ui.messages import DashboardRefreshRequested


@dataclass(frozen=True, slots=True)
class GuidedProfileDefinition:
    """Protocol-specific semantic copy identities for the shared form."""

    protocol: ProtocolKind
    form_id: str
    title_id: str
    guidance_id: str
    title_key: UiText
    guidance_key: UiText
    uses_tls: bool = False
    uses_websocket: bool = False
    uses_grpc: bool = False


REALITY_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_REALITY,
    form_id="reality-form",
    title_id="reality-form-title",
    guidance_id="reality-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_VLESS_REALITY,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_VLESS_REALITY,
)
SHADOWSOCKS_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.SHADOWSOCKS,
    form_id="shadowsocks-form",
    title_id="shadowsocks-form-title",
    guidance_id="protocol-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_SHADOWSOCKS,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_SHADOWSOCKS,
)
HYSTERIA2_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.HYSTERIA2,
    form_id="hysteria2-form",
    title_id="hysteria2-form-title",
    guidance_id="hysteria2-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_HYSTERIA2,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_HYSTERIA2,
    uses_tls=True,
)
TROJAN_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.TROJAN,
    form_id="trojan-form",
    title_id="trojan-form-title",
    guidance_id="trojan-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_TROJAN,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_TROJAN,
    uses_tls=True,
)
ANYTLS_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.ANYTLS,
    form_id="anytls-form",
    title_id="anytls-form-title",
    guidance_id="anytls-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_ANYTLS,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_ANYTLS,
    uses_tls=True,
)
TUIC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.TUIC,
    form_id="tuic-form",
    title_id="tuic-form-title",
    guidance_id="tuic-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_TUIC,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_TUIC,
    uses_tls=True,
)
VLESS_WEBSOCKET_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_TLS,
    form_id="vless-websocket-form",
    title_id="vless-websocket-form-title",
    guidance_id="vless-websocket-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_VLESS_WEBSOCKET,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_VLESS_WEBSOCKET,
    uses_tls=True,
    uses_websocket=True,
)
VLESS_GRPC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VLESS_TLS,
    form_id="vless-grpc-form",
    title_id="vless-grpc-form-title",
    guidance_id="vless-grpc-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_VLESS_GRPC,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_VLESS_GRPC,
    uses_tls=True,
    uses_grpc=True,
)
VMESS_WEBSOCKET_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VMESS_TLS,
    form_id="vmess-websocket-form",
    title_id="vmess-websocket-form-title",
    guidance_id="vmess-websocket-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_VMESS_WEBSOCKET,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_VMESS_WEBSOCKET,
    uses_tls=True,
    uses_websocket=True,
)
VMESS_GRPC_PROFILE = GuidedProfileDefinition(
    protocol=ProtocolKind.VMESS_TLS,
    form_id="vmess-grpc-form",
    title_id="vmess-grpc-form-title",
    guidance_id="vmess-grpc-guidance",
    title_key=UiText.PROFILE_CREATION_FORM_TITLE_VMESS_GRPC,
    guidance_key=UiText.PROFILE_CREATION_FORM_GUIDANCE_VMESS_GRPC,
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


class ApplyResultScreen(Screen[None]):
    """Present the typed terminal state of an apply attempt."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "return_to_dashboard", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        result: ApplyProfileResult,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.result = result
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-result"):
            if self.result.transaction.outcome is ApplyOutcome.APPLIED:
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_TITLE),
                    id="apply-result-title",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_REVISION,
                        revision=self.result.committed_revision,
                    ),
                    id="apply-result-revision",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_HEALTH),
                    id="apply-result-health",
                    markup=False,
                )
                if connection_info := self.result.connection_info:
                    yield ConnectionSharePanel(connection_info, self.copy)
            elif self.result.transaction.outcome is ApplyOutcome.VALIDATION_FAILED:
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_VALIDATION_TITLE),
                    id="apply-result-title",
                    markup=False,
                )
                yield Static(
                    self.result.transaction.validation.diagnostics,
                    id="apply-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_VALIDATION_SAFETY),
                    id="apply-result-safety",
                    markup=False,
                )
            elif self.result.transaction.outcome is ApplyOutcome.PRECONDITION_FAILED:
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_PRECONDITION_TITLE),
                    id="apply-result-title",
                    markup=False,
                )
                commit = self.result.transaction.commit
                yield Static(
                    (
                        commit.diagnostics
                        if commit is not None
                        else self.copy.text(
                            UiText.PROFILE_CREATION_APPLY_RESULT_PRECONDITION_DETAILS_FALLBACK
                        )
                    ),
                    id="apply-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_PRECONDITION_SAFETY),
                    id="apply-result-safety",
                    markup=False,
                )
            elif self.result.transaction.outcome is ApplyOutcome.COMMIT_FAILED:
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_COMMIT_TITLE),
                    id="apply-result-title",
                    markup=False,
                )
                commit = self.result.transaction.commit
                yield Static(
                    (
                        commit.diagnostics
                        if commit is not None
                        else self.copy.text(
                            UiText.PROFILE_CREATION_APPLY_RESULT_COMMIT_DETAILS_FALLBACK
                        )
                    ),
                    id="apply-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_COMMIT_SAFETY),
                    id="apply-result-safety",
                    markup=False,
                )
            elif self.result.transaction.outcome is ApplyOutcome.ROLLED_BACK:
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_TITLE),
                    id="apply-result-title",
                    markup=False,
                )
                rollback = self.result.transaction.rollback
                yield Static(
                    (
                        rollback.diagnostics
                        if rollback is not None
                        else self.copy.text(
                            UiText.PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_DETAILS_FALLBACK
                        )
                    ),
                    id="apply-result-details",
                    markup=False,
                )
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_SAFETY),
                    id="apply-result-safety",
                    markup=False,
                )
            else:
                yield Static(
                    self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_ROLLBACK_FAILED_TITLE),
                    id="apply-result-title",
                    markup=False,
                )
                rollback = self.result.transaction.rollback
                yield Static(
                    (
                        rollback.diagnostics
                        if rollback is not None
                        else self.copy.text(
                            UiText.PROFILE_CREATION_APPLY_RESULT_ROLLBACK_FAILED_DETAILS_FALLBACK
                        )
                    ),
                    id="apply-result-details",
                    markup=False,
                )
                if rollback is not None:
                    for index, instruction in enumerate(rollback.recovery_instructions):
                        yield Static(
                            self.copy.text(
                                UiText.PROFILE_CREATION_APPLY_RESULT_RECOVERY_STEP,
                                number=index + 1,
                                instruction=instruction,
                            ),
                            id=f"recovery-step-{index}",
                            markup=False,
                        )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_RETURN_DASHBOARD),
                id="apply-return-dashboard",
                variant="primary"
                if self.result.transaction.outcome is ApplyOutcome.APPLIED
                else "default",
            )
        yield Footer()

    @on(Button.Pressed, "#apply-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.action_return_to_dashboard()

    def action_return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class ApplyOperationalErrorScreen(Screen[None]):
    """Explain an unknown host result without claiming that no mutation occurred."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "return_to_dashboard", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-operational-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_OPERATIONAL_TITLE),
                id="apply-error-title",
                markup=False,
            )
            yield Static(self.diagnostics, id="apply-error-details", markup=False)
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_OPERATIONAL_SAFETY),
                id="apply-error-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_RETURN_DASHBOARD),
                id="apply-error-return-dashboard",
            )
        yield Footer()

    @on(Button.Pressed, "#apply-error-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.action_return_to_dashboard()

    def action_return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class ApplyUnexpectedErrorScreen(Screen[None]):
    """Treat an unexpected confirmed apply failure as an entirely unknown result."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "return_to_dashboard", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="apply-operational-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_UNKNOWN_TITLE),
                id="apply-unexpected-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_UNKNOWN_DETAILS),
                id="apply-unexpected-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_UNKNOWN_SAFETY),
                id="apply-unexpected-error-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_RESULT_RETURN_DASHBOARD),
                id="apply-unknown-return-dashboard",
            )
        yield Footer()

    @on(Button.Pressed, "#apply-unknown-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.action_return_to_dashboard()

    def action_return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class ApplyConfirmationScreen(ConfirmedOperationScreen[None]):
    """Require a second explicit action before host mutation."""

    def __init__(
        self,
        installation: ManagedInstallation,
        profile_applier: ProfileApplier,
        *,
        profile_id: str,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__(copy_catalog)
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
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_CONFIRM_TITLE),
                id="apply-confirm-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CREATION_APPLY_CONFIRM_PROFILE,
                    name=self.profile.profile_name,
                ),
                id="apply-confirm-profile",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_CONFIRM_WARNING),
                id="apply-confirm-warning",
                markup=False,
            )
            yield Static("", id="apply-progress", markup=False)
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_APPLY_CONFIRM_ACTION),
                id="confirm-apply",
                variant="error",
            )
        yield Footer()

    @on(Button.Pressed, "#confirm-apply")
    def confirm_apply(self) -> None:
        if not self.begin_confirmed_operation():
            return
        self.query_one("#confirm-apply", Button).disabled = True
        self.query_one("#apply-progress", Static).update(
            self.copy.text(UiText.PROFILE_CREATION_APPLY_CONFIRM_PROGRESS)
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
                ApplyOperationalErrorScreen(str(error), self.copy),
            )
            return
        except Exception:
            self.app.call_from_thread(
                self.push_terminal_screen,
                ApplyUnexpectedErrorScreen(self.copy),
            )
            return
        self.app.call_from_thread(
            self.push_terminal_screen,
            ApplyResultScreen(result, self.copy),
        )


class DraftSavedScreen(Screen[None]):
    """Confirm that desired state was saved without applying host changes."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "return_to_dashboard", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        installation: ManagedInstallation,
        *,
        profile_id: str,
        profile_applier: ProfileApplier | None = None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.installation = installation
        self.profile_applier = profile_applier
        self.copy = copy_catalog
        try:
            self.profile = next(
                profile for profile in installation.profiles if profile.profile_id == profile_id
            )
        except StopIteration as error:
            raise ValueError(f"Unknown saved draft profile: {profile_id}") from error

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="draft-saved"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_TITLE),
                id="draft-saved-title",
                markup=False,
            )
            yield Static(self.profile.profile_name, id="saved-profile", markup=False)
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CREATION_DRAFT_STATUS,
                    revision=self.installation.revision,
                ),
                id="saved-status",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_SAFETY),
                id="saved-safety",
                markup=False,
            )
            if self.profile_applier is not None:
                yield Button(
                    self.copy.text(UiText.PROFILE_CREATION_DRAFT_APPLY),
                    id="apply-draft",
                    variant="warning",
                )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_RETURN_DASHBOARD),
                id="draft-return-dashboard",
            )
        yield Footer()

    @on(Button.Pressed, "#apply-draft")
    def open_apply_confirmation(self) -> None:
        if self.profile_applier is not None:
            self.app.push_screen(
                ApplyConfirmationScreen(
                    self.installation,
                    self.profile_applier,
                    profile_id=self.profile.profile_id,
                    copy_catalog=self.copy,
                )
            )

    @on(Button.Pressed, "#draft-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.action_return_to_dashboard()

    def action_return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class PlanPreviewScreen(Screen[None]):
    """Present a side-effect-free plan in operator language."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    GENERATED_COPY: ClassVar[dict[GeneratedValue, UiText]] = {
        GeneratedValue.UUID: UiText.PROFILE_CREATION_PLAN_GENERATED_UUID,
        GeneratedValue.REALITY_KEY_PAIR: (UiText.PROFILE_CREATION_PLAN_GENERATED_REALITY_KEY_PAIR),
        GeneratedValue.SERVER_NAME: UiText.PROFILE_CREATION_PLAN_GENERATED_SERVER_NAME,
        GeneratedValue.SHADOWSOCKS_KEY: (UiText.PROFILE_CREATION_PLAN_GENERATED_SHADOWSOCKS_KEY),
        GeneratedValue.HYSTERIA2_PASSWORD: (
            UiText.PROFILE_CREATION_PLAN_GENERATED_HYSTERIA2_PASSWORD
        ),
        GeneratedValue.TROJAN_PASSWORD: (UiText.PROFILE_CREATION_PLAN_GENERATED_TROJAN_PASSWORD),
        GeneratedValue.ANYTLS_PASSWORD: (UiText.PROFILE_CREATION_PLAN_GENERATED_ANYTLS_PASSWORD),
        GeneratedValue.TUIC_UUID: UiText.PROFILE_CREATION_PLAN_GENERATED_TUIC_UUID,
        GeneratedValue.TUIC_PASSWORD: (UiText.PROFILE_CREATION_PLAN_GENERATED_TUIC_PASSWORD),
        GeneratedValue.VLESS_UUID: UiText.PROFILE_CREATION_PLAN_GENERATED_VLESS_UUID,
        GeneratedValue.VMESS_UUID: UiText.PROFILE_CREATION_PLAN_GENERATED_VMESS_UUID,
        GeneratedValue.TLS_CERTIFICATE: (UiText.PROFILE_CREATION_PLAN_GENERATED_TLS_CERTIFICATE),
    }

    def __init__(
        self,
        manager: Manager,
        plan: ProfilePlan,
        profile_applier: ProfileApplier | None = None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.plan = plan
        self.profile_applier = profile_applier
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        generated = self.copy.text(UiText.PROFILE_CREATION_PLAN_GENERATED_SEPARATOR).join(
            self.copy.text(self.GENERATED_COPY[value]) for value in self.plan.generated_values
        )
        port_summary = (
            self.copy.text(UiText.PROFILE_CREATION_PLAN_PORT_AUTOMATIC)
            if self.plan.port_selection is PortSelection.AUTOMATIC
            else str(self.plan.listen_port)
        )
        yield Header()
        with Vertical(id="plan-preview"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLAN_TITLE),
                id="plan-title",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CREATION_PLAN_PROFILE,
                    name=self.plan.profile_name,
                ),
                id="plan-profile",
                markup=False,
            )
            yield Static(
                self.copy.text(
                    UiText.PROFILE_CREATION_PLAN_PROTOCOL,
                    protocol=PROTOCOL_LABELS[self.plan.protocol],
                ),
                id="plan-protocol",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLAN_PORT, port=port_summary),
                id="plan-port",
                markup=False,
            )
            if self.plan.server_address is not None:
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_SERVER_ADDRESS,
                        address=self.plan.server_address,
                    ),
                    id="plan-server-address",
                    markup=False,
                )
            if isinstance(self.plan.tls_intent, AcmeTlsIntent):
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_TLS_ACME,
                        server_name=self.plan.tls_intent.server_name,
                        email=self.plan.tls_intent.email,
                    ),
                    id="plan-tls",
                    markup=False,
                )
            if isinstance(self.plan.tls_intent, OperatorFileTlsIntent):
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_TLS_FILES,
                        server_name=self.plan.tls_intent.server_name,
                        certificate_path=self.plan.tls_intent.certificate_path,
                    ),
                    id="plan-tls",
                    markup=False,
                )
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_TLS_KEY,
                        path=self.plan.tls_intent.key_path,
                    ),
                    id="plan-tls-key",
                    markup=False,
                )
            if isinstance(self.plan.transport_intent, WebSocketTransportIntent):
                transport_summary = (
                    self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET_HOST,
                        path=self.plan.transport_intent.path,
                        host=self.plan.transport_intent.host,
                    )
                    if self.plan.transport_intent.host is not None
                    else self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET,
                        path=self.plan.transport_intent.path,
                    )
                )
                yield Static(transport_summary, id="plan-transport", markup=False)
            if isinstance(self.plan.transport_intent, GrpcTransportIntent):
                yield Static(
                    self.copy.text(
                        UiText.PROFILE_CREATION_PLAN_TRANSPORT_GRPC,
                        service_name=self.plan.transport_intent.service_name,
                    ),
                    id="plan-transport",
                    markup=False,
                )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLAN_GENERATED, values=generated),
                id="plan-generated",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLAN_SAFETY),
                id="plan-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_PLAN_SAVE_DRAFT),
                id="save-draft",
                variant="primary",
            )
        yield Footer()

    @on(Button.Pressed, "#save-draft")
    def save_draft(self) -> None:
        try:
            self.manager.save_profile_draft(self.plan)
            installation = self.manager.get_installation()
        except StateRevisionConflictError as error:
            self.app.push_screen(DraftSaveRejectionScreen(str(error), self.copy))
            return
        except Exception:
            self.app.push_screen(DraftSaveUnknownScreen(self.copy))
            return
        saved_profile = installation.profiles[-1]
        self.app.push_screen(
            DraftSavedScreen(
                installation,
                profile_id=saved_profile.profile_id,
                profile_applier=self.profile_applier,
                copy_catalog=self.copy,
            )
        )


class DraftSaveRejectionScreen(Screen[None]):
    """Terminate a stale draft plan without offering direct retry."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "return_to_dashboard", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(
        self,
        diagnostics: str,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.diagnostics = diagnostics
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="draft-save-rejection"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_REJECTION_TITLE),
                id="draft-save-rejection-title",
                markup=False,
            )
            yield Static(
                self.diagnostics,
                id="draft-save-rejection-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_REJECTION_SAFETY),
                id="draft-save-rejection-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_RETURN_DASHBOARD),
                id="draft-rejection-return-dashboard",
            )
        yield Footer()

    @on(Button.Pressed, "#draft-rejection-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.action_return_to_dashboard()

    def action_return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class DraftSaveUnknownScreen(Screen[None]):
    """Report an uncertain desired-state draft write without disclosure."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "return_to_dashboard", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="draft-save-unknown"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_UNKNOWN_TITLE),
                id="draft-save-unknown-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_UNKNOWN_DETAILS),
                id="draft-save-unknown-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_UNKNOWN_SAFETY),
                id="draft-save-unknown-safety",
                markup=False,
            )
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_DRAFT_RETURN_DASHBOARD),
                id="draft-unknown-return-dashboard",
            )
        yield Footer()

    @on(Button.Pressed, "#draft-unknown-return-dashboard")
    def return_to_dashboard(self) -> None:
        self.action_return_to_dashboard()

    def action_return_to_dashboard(self) -> None:
        self.post_message(DashboardRefreshRequested())


class ProfilePlanningUnexpectedErrorScreen(Screen[None]):
    """Report an unexpected read-only profile-planning failure safely."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]

    def __init__(self, copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE) -> None:
        super().__init__()
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="profile-planning-error"):
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLANNING_ERROR_TITLE),
                id="profile-planning-error-title",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLANNING_ERROR_DETAILS),
                id="profile-planning-error-details",
                markup=False,
            )
            yield Static(
                self.copy.text(UiText.PROFILE_CREATION_PLANNING_ERROR_SAFETY),
                id="profile-planning-error-safety",
                markup=False,
            )
        yield Footer()


class GuidedProfileScreen(Screen[None]):
    """Collect common intent using protocol-specific operator guidance."""

    BINDINGS: ClassVar[list[BindingType]] = [
        ("escape", "app.pop_screen", SIMPLIFIED_CHINESE.text(UiText.COMMON_RETURN))
    ]
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
    VALIDATION_COPY: ClassVar[dict[ValidationIssueCode, UiText]] = {
        ValidationIssueCode.PROFILE_NAME_REQUIRED: (
            UiText.PROFILE_CREATION_VALIDATION_PROFILE_NAME_REQUIRED
        ),
        ValidationIssueCode.LISTEN_PORT_OUT_OF_RANGE: (
            UiText.PROFILE_CREATION_VALIDATION_LISTEN_PORT_OUT_OF_RANGE
        ),
        ValidationIssueCode.TLS_NOT_SUPPORTED: (
            UiText.PROFILE_CREATION_VALIDATION_TLS_NOT_SUPPORTED
        ),
        ValidationIssueCode.TLS_REQUIRED: UiText.PROFILE_CREATION_VALIDATION_TLS_REQUIRED,
        ValidationIssueCode.TLS_SERVER_NAME_REQUIRED: (
            UiText.PROFILE_CREATION_VALIDATION_TLS_SERVER_NAME_REQUIRED
        ),
        ValidationIssueCode.TLS_EMAIL_REQUIRED: (
            UiText.PROFILE_CREATION_VALIDATION_TLS_EMAIL_REQUIRED
        ),
        ValidationIssueCode.TLS_CERTIFICATE_PATH_UNTRUSTED: (
            UiText.PROFILE_CREATION_VALIDATION_TLS_CERTIFICATE_PATH_UNTRUSTED
        ),
        ValidationIssueCode.TLS_KEY_PATH_UNTRUSTED: (
            UiText.PROFILE_CREATION_VALIDATION_TLS_KEY_PATH_UNTRUSTED
        ),
        ValidationIssueCode.TRANSPORT_NOT_SUPPORTED: (
            UiText.PROFILE_CREATION_VALIDATION_TRANSPORT_NOT_SUPPORTED
        ),
        ValidationIssueCode.TRANSPORT_REQUIRED: (
            UiText.PROFILE_CREATION_VALIDATION_TRANSPORT_REQUIRED
        ),
        ValidationIssueCode.WEBSOCKET_PATH_INVALID: (
            UiText.PROFILE_CREATION_VALIDATION_WEBSOCKET_PATH_INVALID
        ),
        ValidationIssueCode.GRPC_SERVICE_NAME_REQUIRED: (
            UiText.PROFILE_CREATION_VALIDATION_GRPC_SERVICE_NAME_REQUIRED
        ),
    }

    def __init__(
        self,
        manager: Manager,
        definition: GuidedProfileDefinition,
        profile_applier: ProfileApplier | None = None,
        copy_catalog: CopyCatalog = SIMPLIFIED_CHINESE,
    ) -> None:
        super().__init__()
        self.manager = manager
        self.definition = definition
        self.profile_applier = profile_applier
        self.copy = copy_catalog

    def compose(self) -> ComposeResult:
        yield Header()
        form = (
            VerticalScroll(id=self.definition.form_id)
            if self.definition.uses_tls
            else Vertical(id=self.definition.form_id)
        )
        with form:
            yield Static(
                self.copy.text(self.definition.title_key),
                id=self.definition.title_id,
                markup=False,
            )
            yield Static(
                self.copy.text(self.definition.guidance_key),
                id=self.definition.guidance_id,
                markup=False,
            )
            yield Label(
                self.copy.text(UiText.PROFILE_CREATION_FORM_PROFILE_NAME_LABEL),
                classes="field-label",
                markup=False,
            )
            yield Input(
                placeholder=self.copy.text(UiText.PROFILE_CREATION_FORM_PROFILE_NAME_PLACEHOLDER),
                id="profile-name",
            )
            yield Static("", id="profile-name-error", classes="field-error", markup=False)
            yield Label(
                self.copy.text(UiText.PROFILE_CREATION_FORM_SERVER_ADDRESS_LABEL),
                classes="field-label",
                markup=False,
            )
            yield Input(
                placeholder=self.copy.text(UiText.PROFILE_CREATION_FORM_SERVER_ADDRESS_PLACEHOLDER),
                id="server-address",
            )
            if self.definition.uses_tls:
                yield Label(
                    self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_SERVER_NAME_LABEL),
                    classes="field-label",
                    markup=False,
                )
                yield Input(
                    placeholder=self.copy.text(
                        UiText.PROFILE_CREATION_FORM_TLS_SERVER_NAME_PLACEHOLDER
                    ),
                    id="tls-server-name",
                )
                yield Static(
                    "",
                    id="tls-server-name-error",
                    classes="field-error",
                    markup=False,
                )
                yield Label(
                    self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_STRATEGY_LABEL),
                    classes="field-label",
                    markup=False,
                )
                yield Select(
                    (
                        (
                            self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_STRATEGY_ACME),
                            "acme",
                        ),
                        (
                            self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_STRATEGY_FILES),
                            "operator-files",
                        ),
                    ),
                    value="acme",
                    allow_blank=False,
                    id="tls-strategy",
                )
                with Vertical(id="tls-acme-fields"):
                    yield Label(
                        self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_EMAIL_LABEL),
                        classes="field-label",
                        markup=False,
                    )
                    yield Input(
                        placeholder=self.copy.text(
                            UiText.PROFILE_CREATION_FORM_TLS_EMAIL_PLACEHOLDER
                        ),
                        id="tls-email",
                    )
                    yield Static(
                        "",
                        id="tls-email-error",
                        classes="field-error",
                        markup=False,
                    )
                with Vertical(id="tls-file-fields", classes="hidden"):
                    yield Label(
                        self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_CERTIFICATE_PATH_LABEL),
                        classes="field-label",
                        markup=False,
                    )
                    yield Input(
                        placeholder=self.copy.text(
                            UiText.PROFILE_CREATION_FORM_TLS_CERTIFICATE_PATH_PLACEHOLDER
                        ),
                        id="tls-certificate-path",
                    )
                    yield Static(
                        "",
                        id="tls-certificate-path-error",
                        classes="field-error",
                        markup=False,
                    )
                    yield Label(
                        self.copy.text(UiText.PROFILE_CREATION_FORM_TLS_KEY_PATH_LABEL),
                        classes="field-label",
                        markup=False,
                    )
                    yield Input(
                        placeholder=self.copy.text(
                            UiText.PROFILE_CREATION_FORM_TLS_KEY_PATH_PLACEHOLDER
                        ),
                        id="tls-key-path",
                    )
                    yield Static(
                        "",
                        id="tls-key-path-error",
                        classes="field-error",
                        markup=False,
                    )
            if self.definition.uses_websocket:
                yield Label(
                    self.copy.text(UiText.PROFILE_CREATION_FORM_WEBSOCKET_PATH_LABEL),
                    classes="field-label",
                    markup=False,
                )
                yield Input(
                    placeholder=self.copy.text(
                        UiText.PROFILE_CREATION_FORM_WEBSOCKET_PATH_PLACEHOLDER
                    ),
                    id="websocket-path",
                )
                yield Static(
                    "",
                    id="websocket-path-error",
                    classes="field-error",
                    markup=False,
                )
                yield Label(
                    self.copy.text(UiText.PROFILE_CREATION_FORM_WEBSOCKET_HOST_LABEL),
                    classes="field-label",
                    markup=False,
                )
                yield Input(
                    placeholder=self.copy.text(
                        UiText.PROFILE_CREATION_FORM_WEBSOCKET_HOST_PLACEHOLDER
                    ),
                    id="websocket-host",
                )
            if self.definition.uses_grpc:
                yield Label(
                    self.copy.text(UiText.PROFILE_CREATION_FORM_GRPC_SERVICE_NAME_LABEL),
                    classes="field-label",
                    markup=False,
                )
                yield Input(
                    placeholder=self.copy.text(
                        UiText.PROFILE_CREATION_FORM_GRPC_SERVICE_NAME_PLACEHOLDER
                    ),
                    id="grpc-service-name",
                )
                yield Static(
                    "",
                    id="grpc-service-name-error",
                    classes="field-error",
                    markup=False,
                )
            yield Label(
                self.copy.text(UiText.PROFILE_CREATION_FORM_LISTEN_PORT_LABEL),
                classes="field-label",
                markup=False,
            )
            yield Input(
                placeholder=self.copy.text(UiText.PROFILE_CREATION_FORM_LISTEN_PORT_PLACEHOLDER),
                id="listen-port",
                type="integer",
            )
            yield Static("", id="listen-port-error", classes="field-error", markup=False)
            yield Button(
                self.copy.text(UiText.PROFILE_CREATION_FORM_PREVIEW),
                id="preview-plan",
                variant="primary",
            )
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
        self.app.push_screen(
            PlanPreviewScreen(
                self.manager,
                plan,
                self.profile_applier,
                self.copy,
            )
        )

    def _plan_profile(self, request: PlanProfileRequest) -> ProfilePlan | None:
        try:
            return self.manager.plan_profile(request)
        except PlanValidationError as error:
            for issue in error.issues:
                if error_selector := self.ERROR_SELECTORS.get(issue.field):
                    self.query_one(error_selector, Static).update(
                        self._validation_issue_text(issue)
                    )
            return None
        except Exception:
            self.app.push_screen(ProfilePlanningUnexpectedErrorScreen(self.copy))
            return None

    def _validation_issue_text(self, issue: ValidationIssue) -> str:
        key = self.VALIDATION_COPY[issue.code]
        if issue.code in {
            ValidationIssueCode.TLS_CERTIFICATE_PATH_UNTRUSTED,
            ValidationIssueCode.TLS_KEY_PATH_UNTRUSTED,
        }:
            return self.copy.text(key, path=issue.context or "")
        return self.copy.text(key)

    @on(Select.Changed, "#tls-strategy")
    def switch_tls_strategy(self, event: Select.Changed) -> None:
        use_operator_files = event.value == "operator-files"
        self.query_one("#tls-acme-fields").display = not use_operator_files
        self.query_one("#tls-file-fields").display = use_operator_files
