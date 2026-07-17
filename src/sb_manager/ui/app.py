from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

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
    Manager,
)
from sb_manager.application.network_inventory import build_network_inventory
from sb_manager.application.profile_apply import (
    ProfileApplier,
)
from sb_manager.application.profile_availability import (
    ProfileAvailabilityManager,
)
from sb_manager.application.profile_cloning import (
    ProfileCloner,
)
from sb_manager.application.profile_details import (
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
    ProfileStatus,
)
from sb_manager.ui.copy_catalog import SIMPLIFIED_CHINESE, CopyCatalog, UiText
from sb_manager.ui.messages import DashboardRefreshRequested
from sb_manager.ui.screens.config_adoption import ConfigAdoptionScreen
from sb_manager.ui.screens.diagnostics_center import (
    DiagnosticsCenterScreen,
    DiagnosticsCenterTools,
)
from sb_manager.ui.screens.host_diagnostics import HostDiagnosticsScreen
from sb_manager.ui.screens.host_readiness import HostReadinessScreen
from sb_manager.ui.screens.keyboard_help import KeyboardHelpScreen
from sb_manager.ui.screens.network import NetworkScreen
from sb_manager.ui.screens.operations import OperationsScreen
from sb_manager.ui.screens.preference_reset import (
    PreferenceResetConfirmationScreen,
    PreferenceResetPlanningErrorScreen,
)
from sb_manager.ui.screens.profile_creation import (
    GUIDED_PROFILES_BY_VARIANT,
    ApplyConfirmationScreen,
    GuidedProfileScreen,
)
from sb_manager.ui.screens.profile_details import (
    ProfileDetailsCapabilities,
    ProfileDetailsErrorScreen,
    ProfileDetailsScreen,
    ProfileDetailsUnexpectedErrorScreen,
)
from sb_manager.ui.screens.profile_recommendation import ProfilePurposeScreen
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
            self.push_screen(HostDiagnosticsScreen(self.host_diagnostics_report, self.copy_catalog))

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
        self.push_screen(
            NetworkScreen(
                build_network_inventory(self.manager.get_installation()),
                self.copy_catalog,
            )
        )

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
                    self.copy_catalog,
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
                copy_catalog=self.copy_catalog,
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
