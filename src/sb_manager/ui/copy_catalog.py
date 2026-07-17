"""Validated operator-facing copy for one complete migration slice."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from string import Formatter
from types import MappingProxyType


class UiLocale(str, Enum):
    """Locales whose catalog is safe to present as complete."""

    SIMPLIFIED_CHINESE = "zh-CN"


class UiText(str, Enum):
    """Stable semantic identities for catalogued operator-facing copy."""

    COMMON_RETURN = "common.return"
    APP_SUBTITLE = "app.subtitle"
    APP_BINDING_HELP = "app.binding.help"
    APP_BINDING_ADD_PROFILE = "app.binding.add_profile"
    APP_BINDING_PROFILES = "app.binding.profiles"
    APP_BINDING_NETWORK = "app.binding.network"
    APP_BINDING_DIAGNOSTICS = "app.binding.diagnostics"
    APP_BINDING_OPERATIONS = "app.binding.operations"
    APP_BINDING_QUIT = "app.binding.quit"
    DASHBOARD_TITLE = "dashboard.title"
    DASHBOARD_EMPTY_TITLE = "dashboard.empty.title"
    DASHBOARD_SAFETY = "dashboard.safety"
    DASHBOARD_RUNTIME_CHECKING = "dashboard.runtime.checking"
    DASHBOARD_RUNTIME_NOT_CONFIGURED = "dashboard.runtime.not_configured"
    DASHBOARD_RUNTIME_HEALTHY = "dashboard.runtime.healthy"
    DASHBOARD_RUNTIME_UNHEALTHY = "dashboard.runtime.unhealthy"
    DASHBOARD_RUNTIME_FAILED = "dashboard.runtime.failed"
    DASHBOARD_READINESS_CHECKING = "dashboard.readiness.checking"
    DASHBOARD_READINESS_NOT_CONFIGURED = "dashboard.readiness.not_configured"
    DASHBOARD_READINESS_READY = "dashboard.readiness.ready"
    DASHBOARD_READINESS_ACTION_REQUIRED = "dashboard.readiness.action_required"
    DASHBOARD_READINESS_FAILED = "dashboard.readiness.failed"
    DASHBOARD_CERTIFICATE_CHECKING = "dashboard.certificate.checking"
    DASHBOARD_CERTIFICATE_NOT_CONFIGURED = "dashboard.certificate.not_configured"
    DASHBOARD_CERTIFICATE_ACTION_REQUIRED = "dashboard.certificate.action_required"
    DASHBOARD_CERTIFICATE_ATTENTION = "dashboard.certificate.attention"
    DASHBOARD_CERTIFICATE_HEALTHY = "dashboard.certificate.healthy"
    DASHBOARD_CERTIFICATE_FAILED = "dashboard.certificate.failed"
    DASHBOARD_PROFILE_SUMMARY = "dashboard.profile_summary"
    DASHBOARD_RECOMMENDATION = "dashboard.recommendation"
    DASHBOARD_RECOMMENDATION_RECHECK_READINESS = "dashboard.recommendation.recheck_readiness"
    DASHBOARD_RECOMMENDATION_RECHECK_RUNTIME = "dashboard.recommendation.recheck_runtime"
    DASHBOARD_RECOMMENDATION_RECHECK_CERTIFICATES = "dashboard.recommendation.recheck_certificates"
    DASHBOARD_RECOMMENDATION_RESOLVE_READINESS = "dashboard.recommendation.resolve_readiness"
    DASHBOARD_RECOMMENDATION_INSPECT_RUNTIME = "dashboard.recommendation.inspect_runtime"
    DASHBOARD_RECOMMENDATION_RESOLVE_CERTIFICATES = "dashboard.recommendation.resolve_certificates"
    DASHBOARD_RECOMMENDATION_ADD_PROFILE = "dashboard.recommendation.add_profile"
    DASHBOARD_RECOMMENDATION_WAIT_FOR_INSPECTIONS = "dashboard.recommendation.wait_for_inspections"
    DASHBOARD_RECOMMENDATION_REVIEW_DRAFTS = "dashboard.recommendation.review_drafts"
    DASHBOARD_RECOMMENDATION_REVIEW_CERTIFICATES = "dashboard.recommendation.review_certificates"
    DASHBOARD_RECOMMENDATION_VERIFY_RUNTIME = "dashboard.recommendation.verify_runtime"
    DASHBOARD_ACTION_RECHECK_READINESS = "dashboard.action.recheck_readiness"
    DASHBOARD_ACTION_RECHECK_RUNTIME = "dashboard.action.recheck_runtime"
    DASHBOARD_ACTION_RECHECK_CERTIFICATES = "dashboard.action.recheck_certificates"
    DASHBOARD_ACTION_OPEN_READINESS = "dashboard.action.open_readiness"
    DASHBOARD_ACTION_OPEN_RUNTIME_DIAGNOSTICS = "dashboard.action.open_runtime_diagnostics"
    DASHBOARD_ACTION_OPEN_DIAGNOSTICS = "dashboard.action.open_diagnostics"
    DASHBOARD_ACTION_APPLY_DRAFT = "dashboard.action.apply_draft"
    DASHBOARD_ACTION_ADD_PROFILE = "dashboard.action.add_profile"
    DASHBOARD_NO_ACTION = "dashboard.no_action"
    DASHBOARD_NAV_PROFILES = "dashboard.navigation.profiles"
    DASHBOARD_NAV_NETWORK = "dashboard.navigation.network"
    DASHBOARD_NAV_OPERATIONS = "dashboard.navigation.operations"
    DASHBOARD_OPEN_DIAGNOSTICS = "dashboard.open_diagnostics"
    DASHBOARD_VIEW_DIAGNOSTICS = "dashboard.view_diagnostics"
    DASHBOARD_REFRESH_RUNTIME = "dashboard.refresh_runtime"
    DASHBOARD_VIEW_READINESS = "dashboard.view_readiness"
    DASHBOARD_REFRESH_READINESS = "dashboard.refresh_readiness"
    DASHBOARD_REFRESH_CERTIFICATES = "dashboard.refresh_certificates"
    DASHBOARD_ADOPT_CONFIGURATION = "dashboard.adopt_configuration"
    DASHBOARD_EMPTY_GUIDANCE = "dashboard.empty.guidance"
    PROFILES_TITLE = "profiles.title"
    PROFILES_SUMMARY = "profiles.summary"
    PROFILES_SAFETY = "profiles.safety"
    PROFILES_EMPTY = "profiles.empty"
    PROFILES_PORT_AUTOMATIC = "profiles.port.automatic"
    PROFILES_PORT_FIXED = "profiles.port.fixed"
    PROFILES_STATUS_ACTIVE = "profiles.status.active"
    PROFILES_STATUS_PAUSED = "profiles.status.paused"
    PROFILES_STATUS_DRAFT = "profiles.status.draft"
    PROFILES_ROW = "profiles.row"
    PROFILES_VIEW_DETAILS = "profiles.view_details"
    PROFILES_APPLY_DRAFT = "profiles.apply_draft"
    PROFILES_ADD = "profiles.add"
    PROFILE_DETAILS_TITLE = "profile_details.title"
    PROFILE_DETAILS_SAFETY = "profile_details.safety"
    PROFILE_DETAILS_NAME = "profile_details.name"
    PROFILE_DETAILS_PROTOCOL = "profile_details.protocol"
    PROFILE_DETAILS_STATUS = "profile_details.status"
    PROFILE_DETAILS_STATUS_ACTIVE = "profile_details.status.active"
    PROFILE_DETAILS_STATUS_PAUSED = "profile_details.status.paused"
    PROFILE_DETAILS_STATUS_DRAFT = "profile_details.status.draft"
    PROFILE_DETAILS_SERVER_ADDRESS = "profile_details.server_address"
    PROFILE_DETAILS_SERVER_ADDRESS_UNSET = "profile_details.server_address.unset"
    PROFILE_DETAILS_LISTEN_PORT = "profile_details.listen_port"
    PROFILE_DETAILS_LISTEN_PORT_AUTOMATIC = "profile_details.listen_port.automatic"
    PROFILE_DETAILS_NO_CONNECTION = "profile_details.no_connection"
    PROFILE_DETAILS_EDIT = "profile_details.edit"
    PROFILE_DETAILS_CLONE = "profile_details.clone"
    PROFILE_DETAILS_PAUSE = "profile_details.pause"
    PROFILE_DETAILS_RESUME = "profile_details.resume"
    PROFILE_DETAILS_REMOVE = "profile_details.remove"
    PROFILE_DETAILS_ERROR_TITLE = "profile_details.error.title"
    PROFILE_DETAILS_ERROR_MESSAGE = "profile_details.error.message"
    PROFILE_DETAILS_UNEXPECTED_TITLE = "profile_details.unexpected.title"
    PROFILE_DETAILS_UNEXPECTED_DETAILS = "profile_details.unexpected.details"
    PROFILE_DETAILS_UNEXPECTED_SAFETY = "profile_details.unexpected.safety"
    PROFILE_EDIT_TITLE = "profile_edit.title"
    PROFILE_EDIT_CANCEL = "profile_edit.cancel"
    PROFILE_EDIT_GUIDANCE = "profile_edit.guidance"
    PROFILE_EDIT_NAME_LABEL = "profile_edit.name.label"
    PROFILE_EDIT_SERVER_ADDRESS_LABEL = "profile_edit.server_address.label"
    PROFILE_EDIT_LISTEN_PORT_LABEL = "profile_edit.listen_port.label"
    PROFILE_EDIT_LISTEN_PORT_PLACEHOLDER = "profile_edit.listen_port.placeholder"
    PROFILE_EDIT_PORT_GUIDANCE = "profile_edit.listen_port.guidance"
    PROFILE_EDIT_PREVIEW = "profile_edit.preview"
    PROFILE_EDIT_PORT_INVALID = "profile_edit.port.invalid"
    PROFILE_EDIT_NO_CHANGES = "profile_edit.no_changes"
    PROFILE_EDIT_NOT_FOUND = "profile_edit.not_found"
    PROFILE_EDIT_PLANNING_TITLE = "profile_edit.planning.title"
    PROFILE_EDIT_PLANNING_DETAILS = "profile_edit.planning.details"
    PROFILE_EDIT_PLANNING_SAFETY = "profile_edit.planning.safety"
    PROFILE_EDIT_PLAN_TITLE = "profile_edit.plan.title"
    PROFILE_EDIT_PLAN_CHANGE_NAME = "profile_edit.plan.change.name"
    PROFILE_EDIT_PLAN_CHANGE_SERVER_ADDRESS = "profile_edit.plan.change.server_address"
    PROFILE_EDIT_PLAN_CHANGE_LISTEN_PORT = "profile_edit.plan.change.listen_port"
    PROFILE_EDIT_PLAN_CHANGE_PORT_SELECTION = "profile_edit.plan.change.port_selection"
    PROFILE_EDIT_PLAN_VALUE_UNSET = "profile_edit.plan.value.unset"
    PROFILE_EDIT_PLAN_VALUE_AUTOMATIC = "profile_edit.plan.value.automatic"
    PROFILE_EDIT_PLAN_VALUE_AUTOMATIC_AT_CONFIRMATION = (
        "profile_edit.plan.value.automatic_at_confirmation"
    )
    PROFILE_EDIT_PLAN_VALUE_FIXED = "profile_edit.plan.value.fixed"
    PROFILE_EDIT_PLAN_IMPACT_DESIRED = "profile_edit.plan.impact.desired"
    PROFILE_EDIT_PLAN_IMPACT_LIVE = "profile_edit.plan.impact.live"
    PROFILE_EDIT_PLAN_SAFETY_PREVIEW = "profile_edit.plan.safety.preview"
    PROFILE_EDIT_PLAN_CONFIRM_DESIRED = "profile_edit.plan.confirm.desired"
    PROFILE_EDIT_PLAN_CONFIRM_LIVE = "profile_edit.plan.confirm.live"
    PROFILE_EDIT_PLAN_IN_PROGRESS = "profile_edit.plan.in_progress"
    PROFILE_EDIT_RESULT_DESIRED_TITLE = "profile_edit.result.desired.title"
    PROFILE_EDIT_RESULT_REVISION = "profile_edit.result.revision"
    PROFILE_EDIT_RESULT_DESIRED_SAFETY = "profile_edit.result.desired.safety"
    PROFILE_EDIT_RESULT_APPLIED_TITLE = "profile_edit.result.applied.title"
    PROFILE_EDIT_RESULT_APPLIED_SAFETY = "profile_edit.result.applied.safety"
    PROFILE_EDIT_RESULT_VALIDATION_FAILED_TITLE = "profile_edit.result.validation_failed.title"
    PROFILE_EDIT_RESULT_VALIDATION_FAILED_SAFETY = "profile_edit.result.validation_failed.safety"
    PROFILE_EDIT_RESULT_PRECONDITION_FAILED_TITLE = "profile_edit.result.precondition_failed.title"
    PROFILE_EDIT_RESULT_PRECONDITION_FALLBACK = "profile_edit.result.precondition_failed.fallback"
    PROFILE_EDIT_RESULT_PRECONDITION_SAFETY = "profile_edit.result.precondition_failed.safety"
    PROFILE_EDIT_RESULT_COMMIT_FAILED_TITLE = "profile_edit.result.commit_failed.title"
    PROFILE_EDIT_RESULT_COMMIT_FALLBACK = "profile_edit.result.commit_failed.fallback"
    PROFILE_EDIT_RESULT_COMMIT_SAFETY = "profile_edit.result.commit_failed.safety"
    PROFILE_EDIT_RESULT_ROLLED_BACK_TITLE = "profile_edit.result.rolled_back.title"
    PROFILE_EDIT_RESULT_ROLLED_BACK_FALLBACK = "profile_edit.result.rolled_back.fallback"
    PROFILE_EDIT_RESULT_ROLLED_BACK_SAFETY = "profile_edit.result.rolled_back.safety"
    PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_TITLE = "profile_edit.result.rollback_unknown.title"
    PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_FALLBACK = "profile_edit.result.rollback_unknown.fallback"
    PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_SAFETY = "profile_edit.result.rollback_unknown.safety"
    PROFILE_EDIT_RESULT_RECOVERY_STEP = "profile_edit.result.recovery_step"
    PROFILE_EDIT_RESULT_LISTEN_PORT = "profile_edit.result.listen_port"
    PROFILE_EDIT_RESULT_RETURN_DASHBOARD = "profile_edit.result.return_dashboard"
    PROFILE_EDIT_OPERATIONAL_TITLE = "profile_edit.operational.title"
    PROFILE_EDIT_OPERATIONAL_UNEXPECTED_DETAILS = "profile_edit.operational.unexpected.details"
    PROFILE_EDIT_OPERATIONAL_KNOWN_SAFETY = "profile_edit.operational.known.safety"
    PROFILE_EDIT_OPERATIONAL_UNKNOWN_SAFETY = "profile_edit.operational.unknown.safety"
    PROFILE_EDIT_PORT_CONFLICT_TITLE = "profile_edit.port_conflict.title"
    PROFILE_EDIT_PORT_CONFLICT_SAFETY = "profile_edit.port_conflict.safety"
    PROFILE_EDIT_CONFLICT_TITLE = "profile_edit.conflict.title"
    PROFILE_EDIT_CONFLICT_SAFETY = "profile_edit.conflict.safety"
    PROFILE_AVAILABILITY_PLAN_RESUME_TITLE = "profile_availability.plan.resume.title"
    PROFILE_AVAILABILITY_PLAN_PAUSE_TITLE = "profile_availability.plan.pause.title"
    PROFILE_AVAILABILITY_PLAN_PROFILE = "profile_availability.plan.profile"
    PROFILE_AVAILABILITY_PLAN_PAUSE_IMPACT = "profile_availability.plan.pause.impact"
    PROFILE_AVAILABILITY_PLAN_RESUME_IMPACT = "profile_availability.plan.resume.impact"
    PROFILE_AVAILABILITY_PLAN_ACTIVE_COUNT = "profile_availability.plan.active_count"
    PROFILE_AVAILABILITY_PLAN_SAFETY_PREVIEW = "profile_availability.plan.safety.preview"
    PROFILE_AVAILABILITY_PLAN_CONFIRM_PAUSE = "profile_availability.plan.confirm.pause"
    PROFILE_AVAILABILITY_PLAN_CONFIRM_RESUME = "profile_availability.plan.confirm.resume"
    PROFILE_AVAILABILITY_PLAN_IN_PROGRESS = "profile_availability.plan.in_progress"
    PROFILE_AVAILABILITY_OPERATIONAL_TITLE = "profile_availability.operational.title"
    PROFILE_AVAILABILITY_OPERATIONAL_UNEXPECTED_DETAILS = (
        "profile_availability.operational.unexpected.details"
    )
    PROFILE_AVAILABILITY_OPERATIONAL_KNOWN_SAFETY = "profile_availability.operational.known.safety"
    PROFILE_AVAILABILITY_OPERATIONAL_UNKNOWN_SAFETY = (
        "profile_availability.operational.unknown.safety"
    )
    PROFILE_AVAILABILITY_PLANNING_TITLE = "profile_availability.planning.title"
    PROFILE_AVAILABILITY_PLANNING_DETAILS = "profile_availability.planning.details"
    PROFILE_AVAILABILITY_PLANNING_SAFETY = "profile_availability.planning.safety"
    PROFILE_AVAILABILITY_RESULT_PAUSED_TITLE = "profile_availability.result.paused.title"
    PROFILE_AVAILABILITY_RESULT_RESUMED_TITLE = "profile_availability.result.resumed.title"
    PROFILE_AVAILABILITY_RESULT_REVISION = "profile_availability.result.revision"
    PROFILE_AVAILABILITY_RESULT_SUCCESS_SAFETY = "profile_availability.result.success.safety"
    PROFILE_AVAILABILITY_RESULT_RETURN_DASHBOARD = "profile_availability.result.return_dashboard"
    PROFILE_AVAILABILITY_RESULT_VALIDATION_FAILED_TITLE = (
        "profile_availability.result.validation_failed.title"
    )
    PROFILE_AVAILABILITY_RESULT_VALIDATION_FAILED_SAFETY = (
        "profile_availability.result.validation_failed.safety"
    )
    PROFILE_AVAILABILITY_RESULT_PRECONDITION_FAILED_TITLE = (
        "profile_availability.result.precondition_failed.title"
    )
    PROFILE_AVAILABILITY_RESULT_PRECONDITION_FALLBACK = (
        "profile_availability.result.precondition_failed.fallback"
    )
    PROFILE_AVAILABILITY_RESULT_PRECONDITION_SAFETY = (
        "profile_availability.result.precondition_failed.safety"
    )
    PROFILE_AVAILABILITY_RESULT_COMMIT_FAILED_TITLE = (
        "profile_availability.result.commit_failed.title"
    )
    PROFILE_AVAILABILITY_RESULT_COMMIT_FALLBACK = (
        "profile_availability.result.commit_failed.fallback"
    )
    PROFILE_AVAILABILITY_RESULT_COMMIT_SAFETY = "profile_availability.result.commit_failed.safety"
    PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_TITLE = "profile_availability.result.rolled_back.title"
    PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_FALLBACK = (
        "profile_availability.result.rolled_back.fallback"
    )
    PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_SAFETY = (
        "profile_availability.result.rolled_back.safety"
    )
    PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_TITLE = (
        "profile_availability.result.rollback_unknown.title"
    )
    PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_FALLBACK = (
        "profile_availability.result.rollback_unknown.fallback"
    )
    PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_SAFETY = (
        "profile_availability.result.rollback_unknown.safety"
    )
    PROFILE_AVAILABILITY_RESULT_RECOVERY_STEP = "profile_availability.result.recovery_step"
    PROFILE_REMOVAL_PLAN_TITLE = "profile_removal.plan.title"
    PROFILE_REMOVAL_PLAN_PROFILE = "profile_removal.plan.profile"
    PROFILE_REMOVAL_PLAN_DRAFT_IMPACT = "profile_removal.plan.draft.impact"
    PROFILE_REMOVAL_PLAN_LIVE_IMPACT = "profile_removal.plan.live.impact"
    PROFILE_REMOVAL_PLAN_REMAINING = "profile_removal.plan.remaining"
    PROFILE_REMOVAL_PLAN_SAFETY_PREVIEW = "profile_removal.plan.safety.preview"
    PROFILE_REMOVAL_PLAN_CONFIRM_DRAFT = "profile_removal.plan.confirm.draft"
    PROFILE_REMOVAL_PLAN_CONFIRM_LIVE = "profile_removal.plan.confirm.live"
    PROFILE_REMOVAL_PLAN_IN_PROGRESS = "profile_removal.plan.in_progress"
    PROFILE_REMOVAL_RESULT_DRAFT_TITLE = "profile_removal.result.draft.title"
    PROFILE_REMOVAL_RESULT_APPLIED_TITLE = "profile_removal.result.applied.title"
    PROFILE_REMOVAL_RESULT_REVISION = "profile_removal.result.revision"
    PROFILE_REMOVAL_RESULT_DRAFT_SAFETY = "profile_removal.result.draft.safety"
    PROFILE_REMOVAL_RESULT_RETURN_DASHBOARD = "profile_removal.result.return_dashboard"
    PROFILE_REMOVAL_RESULT_UNTRUSTED_TITLE = "profile_removal.result.untrusted.title"
    PROFILE_REMOVAL_RESULT_UNTRUSTED_DETAILS = "profile_removal.result.untrusted.details"
    PROFILE_REMOVAL_RESULT_UNTRUSTED_SAFETY = "profile_removal.result.untrusted.safety"
    PROFILE_REMOVAL_RESULT_APPLIED_SAFETY = "profile_removal.result.applied.safety"
    PROFILE_REMOVAL_RESULT_VALIDATION_FAILED_TITLE = (
        "profile_removal.result.validation_failed.title"
    )
    PROFILE_REMOVAL_RESULT_VALIDATION_FAILED_SAFETY = (
        "profile_removal.result.validation_failed.safety"
    )
    PROFILE_REMOVAL_RESULT_PRECONDITION_FAILED_TITLE = (
        "profile_removal.result.precondition_failed.title"
    )
    PROFILE_REMOVAL_RESULT_PRECONDITION_FALLBACK = (
        "profile_removal.result.precondition_failed.fallback"
    )
    PROFILE_REMOVAL_RESULT_PRECONDITION_SAFETY = "profile_removal.result.precondition_failed.safety"
    PROFILE_REMOVAL_RESULT_COMMIT_FAILED_TITLE = "profile_removal.result.commit_failed.title"
    PROFILE_REMOVAL_RESULT_COMMIT_FALLBACK = "profile_removal.result.commit_failed.fallback"
    PROFILE_REMOVAL_RESULT_COMMIT_SAFETY = "profile_removal.result.commit_failed.safety"
    PROFILE_REMOVAL_RESULT_ROLLED_BACK_TITLE = "profile_removal.result.rolled_back.title"
    PROFILE_REMOVAL_RESULT_ROLLED_BACK_FALLBACK = "profile_removal.result.rolled_back.fallback"
    PROFILE_REMOVAL_RESULT_ROLLED_BACK_SAFETY = "profile_removal.result.rolled_back.safety"
    PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_TITLE = "profile_removal.result.rollback_unknown.title"
    PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_FALLBACK = (
        "profile_removal.result.rollback_unknown.fallback"
    )
    PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_SAFETY = (
        "profile_removal.result.rollback_unknown.safety"
    )
    PROFILE_REMOVAL_RESULT_RECOVERY_STEP = "profile_removal.result.recovery_step"
    PROFILE_REMOVAL_OPERATIONAL_TITLE = "profile_removal.operational.title"
    PROFILE_REMOVAL_OPERATIONAL_UNEXPECTED_DETAILS = (
        "profile_removal.operational.unexpected.details"
    )
    PROFILE_REMOVAL_OPERATIONAL_KNOWN_SAFETY = "profile_removal.operational.known.safety"
    PROFILE_REMOVAL_OPERATIONAL_UNKNOWN_SAFETY = "profile_removal.operational.unknown.safety"
    PROFILE_REMOVAL_PLANNING_TITLE = "profile_removal.planning.title"
    PROFILE_REMOVAL_PLANNING_DETAILS = "profile_removal.planning.details"
    PROFILE_REMOVAL_PLANNING_SAFETY = "profile_removal.planning.safety"
    CONNECTION_SHARE_ENDPOINT = "connection_share.endpoint"
    CONNECTION_SHARE_WARNING_HIDDEN = "connection_share.warning.hidden"
    CONNECTION_SHARE_REVEAL = "connection_share.reveal"
    CONNECTION_SHARE_WARNING_REVEALED = "connection_share.warning.revealed"
    CONNECTION_SHARE_HIDE = "connection_share.hide"
    CONNECTION_SHARE_LABEL = "connection_share.label"
    CONNECTION_SHARE_WARNING_HIDDEN_AFTER = "connection_share.warning.hidden_after"
    SETTINGS_TITLE = "settings.title"
    SETTINGS_BINDING = "settings.binding"
    SETTINGS_OPEN = "settings.open"
    SETTINGS_LANGUAGE = "settings.language"
    SETTINGS_LANGUAGE_POLICY = "settings.language_policy"
    SETTINGS_COLOR_DARK = "settings.color.dark"
    SETTINGS_COLOR_LIGHT = "settings.color.light"
    SETTINGS_APPEARANCE = "settings.appearance"
    SETTINGS_TOGGLE_APPEARANCE = "settings.toggle_appearance"
    SETTINGS_REVIEW_RESET = "settings.review_reset"
    SETTINGS_UPDATE_POLICY = "settings.update_policy"
    SETTINGS_PERSISTENCE_SAVED = "settings.persistence.saved"
    SETTINGS_PERSISTENCE_LOADED = "settings.persistence.loaded"
    SETTINGS_PERSISTENCE_LOAD_FAILED = "settings.persistence.load_failed"
    SETTINGS_PERSISTENCE_SAVE_FAILED = "settings.persistence.save_failed"
    SETTINGS_PERSISTENCE_RESET = "settings.persistence.reset"
    SETTINGS_PERSISTENCE_READY = "settings.persistence.ready"
    SETTINGS_PERSISTENCE_SESSION_ONLY = "settings.persistence.session_only"
    SETTINGS_SAFETY_SESSION = "settings.safety.session"
    SETTINGS_SAFETY_PERSISTED = "settings.safety.persisted"
    SETTINGS_HOST_ACCESS_PRIVILEGED = "settings.host_access.privileged"
    SETTINGS_HOST_ACCESS_DIRECT = "settings.host_access.direct"
    SETTINGS_HOST_ACCESS_UNAVAILABLE = "settings.host_access.unavailable"
    SETTINGS_RUNTIME_SYSTEMD = "settings.runtime.systemd"
    SETTINGS_RUNTIME_OPENRC = "settings.runtime.openrc"
    SETTINGS_RUNTIME_UNAVAILABLE = "settings.runtime.unavailable"
    SETTINGS_CONFIG_PRIVILEGED = "settings.config.privileged"
    SETTINGS_PATH = "settings.path"
    SETTINGS_PATH_UNAVAILABLE = "settings.path.unavailable"
    SETTINGS_ROLE_STATE = "settings.role.state"
    SETTINGS_ROLE_PREFERENCES = "settings.role.preferences"
    SETTINGS_ROLE_CONFIG = "settings.role.config"
    SETTINGS_ROLE_TRANSACTION = "settings.role.transaction"
    PREFERENCE_RESET_TITLE = "preference_reset.title"
    PREFERENCE_RESET_FINGERPRINT = "preference_reset.fingerprint"
    PREFERENCE_RESET_DEFAULT = "preference_reset.default"
    PREFERENCE_RESET_SAFETY = "preference_reset.safety"
    PREFERENCE_RESET_CONFIRM = "preference_reset.confirm"
    PREFERENCE_RESET_IN_PROGRESS = "preference_reset.in_progress"
    PREFERENCE_RESET_CONFLICT = "preference_reset.conflict"
    PREFERENCE_RESET_ERROR = "preference_reset.error"
    PREFERENCE_RESET_PLANNING_TITLE = "preference_reset.planning.title"
    PREFERENCE_RESET_PLANNING_DETAILS = "preference_reset.planning.details"
    PREFERENCE_RESET_PLANNING_SAFETY = "preference_reset.planning.safety"
    PREFERENCE_RESET_OPERATIONAL_TITLE = "preference_reset.operational.title"
    PREFERENCE_RESET_OPERATIONAL_DETAILS = "preference_reset.operational.details"
    PREFERENCE_RESET_OPERATIONAL_SAFETY = "preference_reset.operational.safety"


_EXPECTED_FIELDS: dict[UiText, frozenset[str]] = {key: frozenset() for key in UiText}
_EXPECTED_FIELDS.update(
    {
        UiText.DASHBOARD_READINESS_ACTION_REQUIRED: frozenset({"count"}),
        UiText.DASHBOARD_PROFILE_SUMMARY: frozenset({"active", "paused", "drafts"}),
        UiText.DASHBOARD_RECOMMENDATION: frozenset({"summary"}),
        UiText.DASHBOARD_RECOMMENDATION_REVIEW_DRAFTS: frozenset({"count"}),
        UiText.PROFILES_PORT_FIXED: frozenset({"port"}),
        UiText.PROFILES_ROW: frozenset({"name", "protocol", "status", "port"}),
        UiText.PROFILE_DETAILS_NAME: frozenset({"name"}),
        UiText.PROFILE_DETAILS_PROTOCOL: frozenset({"protocol"}),
        UiText.PROFILE_DETAILS_STATUS: frozenset({"status"}),
        UiText.PROFILE_DETAILS_SERVER_ADDRESS: frozenset({"address"}),
        UiText.PROFILE_DETAILS_LISTEN_PORT: frozenset({"port"}),
        UiText.PROFILE_EDIT_PLAN_CHANGE_NAME: frozenset({"previous", "current"}),
        UiText.PROFILE_EDIT_PLAN_CHANGE_SERVER_ADDRESS: frozenset({"previous", "current"}),
        UiText.PROFILE_EDIT_PLAN_CHANGE_LISTEN_PORT: frozenset({"previous", "current"}),
        UiText.PROFILE_EDIT_PLAN_CHANGE_PORT_SELECTION: frozenset({"previous", "current"}),
        UiText.PROFILE_EDIT_RESULT_REVISION: frozenset({"revision"}),
        UiText.PROFILE_EDIT_RESULT_RECOVERY_STEP: frozenset({"number", "instruction"}),
        UiText.PROFILE_EDIT_RESULT_LISTEN_PORT: frozenset({"port"}),
        UiText.PROFILE_AVAILABILITY_PLAN_PROFILE: frozenset({"name"}),
        UiText.PROFILE_AVAILABILITY_PLAN_ACTIVE_COUNT: frozenset({"count"}),
        UiText.PROFILE_AVAILABILITY_RESULT_REVISION: frozenset({"revision"}),
        UiText.PROFILE_AVAILABILITY_RESULT_RECOVERY_STEP: frozenset({"number", "instruction"}),
        UiText.PROFILE_REMOVAL_PLAN_PROFILE: frozenset({"name"}),
        UiText.PROFILE_REMOVAL_PLAN_REMAINING: frozenset({"profiles", "applied"}),
        UiText.PROFILE_REMOVAL_RESULT_REVISION: frozenset({"revision"}),
        UiText.PROFILE_REMOVAL_RESULT_RECOVERY_STEP: frozenset({"number", "instruction"}),
        UiText.CONNECTION_SHARE_ENDPOINT: frozenset({"address", "port"}),
        UiText.SETTINGS_APPEARANCE: frozenset({"label"}),
        UiText.SETTINGS_TOGGLE_APPEARANCE: frozenset({"target"}),
        UiText.SETTINGS_PERSISTENCE_SAVED: frozenset({"label"}),
        UiText.SETTINGS_PATH: frozenset({"role", "path"}),
        UiText.PREFERENCE_RESET_FINGERPRINT: frozenset({"sha256"}),
    }
)


class CopyCatalogError(ValueError):
    """One catalog is incomplete or cannot render a declared message."""


@dataclass(frozen=True, slots=True)
class CopyCatalog:
    """Render a validated locale catalog behind one small interface."""

    locale: UiLocale
    _templates: Mapping[UiText, str]

    def __init__(self, locale: UiLocale, templates: Mapping[UiText, str]) -> None:
        normalized = dict(templates)
        missing = set(UiText).difference(normalized)
        unexpected = set(normalized).difference(UiText)
        if missing or unexpected:
            raise CopyCatalogError("UI copy catalog keys do not match the declared text set")
        formatter = Formatter()
        for key, template in normalized.items():
            fields = frozenset(
                field_name
                for _, field_name, _, _ in formatter.parse(template)
                if field_name is not None
            )
            if fields != _EXPECTED_FIELDS[key]:
                raise CopyCatalogError(f"UI copy fields do not match {key.value}")
        object.__setattr__(self, "locale", locale)
        object.__setattr__(self, "_templates", MappingProxyType(normalized))

    def text(self, key: UiText, /, **values: object) -> str:
        """Render one semantic message without exposing the catalog mapping."""

        if set(values) != _EXPECTED_FIELDS[key]:
            raise CopyCatalogError(f"UI copy values do not match {key.value}")
        try:
            return self._templates[key].format_map(values)
        except (KeyError, ValueError) as error:
            raise CopyCatalogError(f"UI copy could not render {key.value}") from error


SIMPLIFIED_CHINESE = CopyCatalog(
    UiLocale.SIMPLIFIED_CHINESE,
    {
        UiText.COMMON_RETURN: "返回",
        UiText.APP_SUBTITLE: "安全地搭建和维护你的代理服务",
        UiText.APP_BINDING_HELP: "帮助",
        UiText.APP_BINDING_ADD_PROFILE: "添加配置",
        UiText.APP_BINDING_PROFILES: "配置",
        UiText.APP_BINDING_NETWORK: "网络",
        UiText.APP_BINDING_DIAGNOSTICS: "诊断",
        UiText.APP_BINDING_OPERATIONS: "运维",
        UiText.APP_BINDING_QUIT: "退出",
        UiText.DASHBOARD_TITLE: "服务总览",
        UiText.DASHBOARD_EMPTY_TITLE: "尚未创建代理配置",
        UiText.DASHBOARD_SAFETY: (
            "当前页面只读：检查不会修改主机。任何变更都必须先审阅计划并明确确认。"
        ),
        UiText.DASHBOARD_RUNTIME_CHECKING: "服务状态：正在检查…",
        UiText.DASHBOARD_RUNTIME_NOT_CONFIGURED: "服务状态：未启用主机检查",
        UiText.DASHBOARD_RUNTIME_HEALTHY: "服务状态：运行正常",
        UiText.DASHBOARD_RUNTIME_UNHEALTHY: "服务状态：需要检查",
        UiText.DASHBOARD_RUNTIME_FAILED: "服务状态：无法检查",
        UiText.DASHBOARD_READINESS_CHECKING: "主机准备度：正在检查…",
        UiText.DASHBOARD_READINESS_NOT_CONFIGURED: "主机准备度：未启用检查",
        UiText.DASHBOARD_READINESS_READY: "主机准备度：可以应用配置",
        UiText.DASHBOARD_READINESS_ACTION_REQUIRED: "主机准备度：需要完成 {count} 项",
        UiText.DASHBOARD_READINESS_FAILED: "主机准备度：无法检查",
        UiText.DASHBOARD_CERTIFICATE_CHECKING: "证书维护：正在检查…",
        UiText.DASHBOARD_CERTIFICATE_NOT_CONFIGURED: "证书维护：未启用检查",
        UiText.DASHBOARD_CERTIFICATE_ACTION_REQUIRED: "证书维护：需要处理",
        UiText.DASHBOARD_CERTIFICATE_ATTENTION: "证书维护：建议关注",
        UiText.DASHBOARD_CERTIFICATE_HEALTHY: "证书维护：状态正常",
        UiText.DASHBOARD_CERTIFICATE_FAILED: "证书维护：无法检查",
        UiText.DASHBOARD_PROFILE_SUMMARY: ("配置：{active} 在线 · {paused} 已暂停 · {drafts} 草案"),
        UiText.DASHBOARD_RECOMMENDATION: "建议：{summary}",
        UiText.DASHBOARD_RECOMMENDATION_RECHECK_READINESS: "先重新检查主机准备度",
        UiText.DASHBOARD_RECOMMENDATION_RECHECK_RUNTIME: "先重新检查服务状态",
        UiText.DASHBOARD_RECOMMENDATION_RECHECK_CERTIFICATES: "先重新检查证书维护状态",
        UiText.DASHBOARD_RECOMMENDATION_RESOLVE_READINESS: "先完成主机准备项，再应用配置",
        UiText.DASHBOARD_RECOMMENDATION_INSPECT_RUNTIME: ("先检查 sing-box 服务，再进行配置变更"),
        UiText.DASHBOARD_RECOMMENDATION_RESOLVE_CERTIFICATES: ("先处理证书维护项，再进行配置变更"),
        UiText.DASHBOARD_RECOMMENDATION_ADD_PROFILE: "创建第一个配置",
        UiText.DASHBOARD_RECOMMENDATION_WAIT_FOR_INSPECTIONS: "正在检查主机状态",
        UiText.DASHBOARD_RECOMMENDATION_REVIEW_DRAFTS: "先审阅并应用 {count} 个草案",
        UiText.DASHBOARD_RECOMMENDATION_REVIEW_CERTIFICATES: "查看需要关注的证书维护项",
        UiText.DASHBOARD_RECOMMENDATION_VERIFY_RUNTIME: "配置已应用，确认服务状态",
        UiText.DASHBOARD_ACTION_RECHECK_READINESS: "立即重新检查主机准备度",
        UiText.DASHBOARD_ACTION_RECHECK_RUNTIME: "立即重新检查服务状态",
        UiText.DASHBOARD_ACTION_RECHECK_CERTIFICATES: "立即重新检查证书",
        UiText.DASHBOARD_ACTION_OPEN_READINESS: "查看主机准备度",
        UiText.DASHBOARD_ACTION_OPEN_RUNTIME_DIAGNOSTICS: "查看服务诊断",
        UiText.DASHBOARD_ACTION_OPEN_DIAGNOSTICS: "打开诊断中心",
        UiText.DASHBOARD_ACTION_APPLY_DRAFT: "审阅并应用草案",
        UiText.DASHBOARD_ACTION_ADD_PROFILE: "创建第一个配置",
        UiText.DASHBOARD_NO_ACTION: "暂无可执行建议",
        UiText.DASHBOARD_NAV_PROFILES: "管理配置",
        UiText.DASHBOARD_NAV_NETWORK: "查看网络概览",
        UiText.DASHBOARD_NAV_OPERATIONS: "打开运维中心",
        UiText.DASHBOARD_OPEN_DIAGNOSTICS: "打开诊断中心",
        UiText.DASHBOARD_VIEW_DIAGNOSTICS: "查看诊断",
        UiText.DASHBOARD_REFRESH_RUNTIME: "重新检查服务状态",
        UiText.DASHBOARD_VIEW_READINESS: "查看准备度",
        UiText.DASHBOARD_REFRESH_READINESS: "重新检查",
        UiText.DASHBOARD_REFRESH_CERTIFICATES: "重新检查证书",
        UiText.DASHBOARD_ADOPT_CONFIGURATION: "检查并接管现有配置",
        UiText.DASHBOARD_EMPTY_GUIDANCE: ("从一个引导式配置开始。应用前你会看到完整变更计划。"),
        UiText.PROFILES_TITLE: "配置工作区",
        UiText.PROFILES_SUMMARY: "浏览 desired state 中的完整配置，并从这里开始生命周期操作。",
        UiText.PROFILES_SAFETY: (
            "当前清单只读。任何配置变更都会先显示计划，并在执行前要求明确确认。"
        ),
        UiText.PROFILES_EMPTY: "尚未创建代理配置。先说明使用目的，再选择合适的协议。",
        UiText.PROFILES_PORT_AUTOMATIC: "自动选择端口",
        UiText.PROFILES_PORT_FIXED: "端口 {port}",
        UiText.PROFILES_STATUS_ACTIVE: "在线",
        UiText.PROFILES_STATUS_PAUSED: "已暂停",
        UiText.PROFILES_STATUS_DRAFT: "草案",
        UiText.PROFILES_ROW: "{name} · {protocol} · {status} · {port}",
        UiText.PROFILES_VIEW_DETAILS: "查看详情",
        UiText.PROFILES_APPLY_DRAFT: "应用草案",
        UiText.PROFILES_ADD: "添加配置",
        UiText.PROFILE_DETAILS_TITLE: "配置详情",
        UiText.PROFILE_DETAILS_SAFETY: (
            "当前页面只读。生命周期按钮只会打开计划或确认步骤，不会在本页直接变更配置。"
        ),
        UiText.PROFILE_DETAILS_NAME: "名称：{name}",
        UiText.PROFILE_DETAILS_PROTOCOL: "协议：{protocol}",
        UiText.PROFILE_DETAILS_STATUS: "状态：{status}",
        UiText.PROFILE_DETAILS_STATUS_ACTIVE: "已应用 · 在线",
        UiText.PROFILE_DETAILS_STATUS_PAUSED: "已应用 · 已暂停",
        UiText.PROFILE_DETAILS_STATUS_DRAFT: "草案",
        UiText.PROFILE_DETAILS_SERVER_ADDRESS: "服务器地址：{address}",
        UiText.PROFILE_DETAILS_SERVER_ADDRESS_UNSET: "服务器地址：未设置",
        UiText.PROFILE_DETAILS_LISTEN_PORT: "监听端口：{port}",
        UiText.PROFILE_DETAILS_LISTEN_PORT_AUTOMATIC: "监听端口：应用时自动选择",
        UiText.PROFILE_DETAILS_NO_CONNECTION: (
            "该配置尚无可用连接信息。应用草案并设置服务器地址后生成。"
        ),
        UiText.PROFILE_DETAILS_EDIT: "编辑配置",
        UiText.PROFILE_DETAILS_CLONE: "以此配置为模板",
        UiText.PROFILE_DETAILS_PAUSE: "暂停配置",
        UiText.PROFILE_DETAILS_RESUME: "恢复配置",
        UiText.PROFILE_DETAILS_REMOVE: "移除此配置",
        UiText.PROFILE_DETAILS_ERROR_TITLE: "无法打开配置详情",
        UiText.PROFILE_DETAILS_ERROR_MESSAGE: (
            "配置可能已被另一个会话修改，请返回后重新打开列表。"
        ),
        UiText.PROFILE_DETAILS_UNEXPECTED_TITLE: "无法读取配置详情",
        UiText.PROFILE_DETAILS_UNEXPECTED_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_DETAILS_UNEXPECTED_SAFETY: "尚未修改任何配置。请返回列表后重新读取。",
        UiText.PROFILE_EDIT_TITLE: "编辑配置",
        UiText.PROFILE_EDIT_CANCEL: "取消",
        UiText.PROFILE_EDIT_GUIDANCE: "稳定 ID、协议和凭据保持不变。提交前会显示影响计划。",
        UiText.PROFILE_EDIT_NAME_LABEL: "配置名称",
        UiText.PROFILE_EDIT_SERVER_ADDRESS_LABEL: "公开服务器地址 (可留空)",
        UiText.PROFILE_EDIT_LISTEN_PORT_LABEL: "监听端口 (可留空)",
        UiText.PROFILE_EDIT_LISTEN_PORT_PLACEHOLDER: "留空自动选择",
        UiText.PROFILE_EDIT_PORT_GUIDANCE: (
            "留空表示自动选择。已应用配置会在确认后选择端口并执行完整事务。"
        ),
        UiText.PROFILE_EDIT_PREVIEW: "预览变更",
        UiText.PROFILE_EDIT_PORT_INVALID: ("端口必须是 1 到 65535 之间的整数，或留空自动选择"),
        UiText.PROFILE_EDIT_NO_CHANGES: "没有可保存的变更",
        UiText.PROFILE_EDIT_NOT_FOUND: "配置可能已被另一个会话移除，请返回后重新打开列表。",
        UiText.PROFILE_EDIT_PLANNING_TITLE: "无法准备配置编辑",
        UiText.PROFILE_EDIT_PLANNING_DETAILS: (
            "读取配置编辑计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_EDIT_PLANNING_SAFETY: (
            "尚未执行任何操作。请返回配置列表，重新打开详情后再试。"
        ),
        UiText.PROFILE_EDIT_PLAN_TITLE: "确认配置变更",
        UiText.PROFILE_EDIT_PLAN_CHANGE_NAME: "名称：{previous} → {current}",
        UiText.PROFILE_EDIT_PLAN_CHANGE_SERVER_ADDRESS: "公开地址：{previous} → {current}",
        UiText.PROFILE_EDIT_PLAN_CHANGE_LISTEN_PORT: "监听端口：{previous} → {current}",
        UiText.PROFILE_EDIT_PLAN_CHANGE_PORT_SELECTION: "端口策略：{previous} → {current}",
        UiText.PROFILE_EDIT_PLAN_VALUE_UNSET: "未设置",
        UiText.PROFILE_EDIT_PLAN_VALUE_AUTOMATIC: "自动选择",
        UiText.PROFILE_EDIT_PLAN_VALUE_AUTOMATIC_AT_CONFIRMATION: "自动选择 - 确认时",
        UiText.PROFILE_EDIT_PLAN_VALUE_FIXED: "固定",
        UiText.PROFILE_EDIT_PLAN_IMPACT_DESIRED: (
            "只更新 manager desired state，不会写入 sing-box 配置或刷新服务。"
        ),
        UiText.PROFILE_EDIT_PLAN_IMPACT_LIVE: (
            "将生成完整 sing-box 配置，校验并刷新服务，失败时自动回滚。"
        ),
        UiText.PROFILE_EDIT_PLAN_SAFETY_PREVIEW: "当前仅预览，尚未修改任何内容。",
        UiText.PROFILE_EDIT_PLAN_CONFIRM_DESIRED: "确认保存",
        UiText.PROFILE_EDIT_PLAN_CONFIRM_LIVE: "确认修改并应用",
        UiText.PROFILE_EDIT_PLAN_IN_PROGRESS: ("操作已确认，正在执行配置变更。完成前无法返回。"),
        UiText.PROFILE_EDIT_RESULT_DESIRED_TITLE: "配置已更新",
        UiText.PROFILE_EDIT_RESULT_REVISION: "desired state 已提交 revision {revision}。",
        UiText.PROFILE_EDIT_RESULT_DESIRED_SAFETY: "未写入 sing-box 配置，也未刷新服务。",
        UiText.PROFILE_EDIT_RESULT_APPLIED_TITLE: "配置已应用并更新",
        UiText.PROFILE_EDIT_RESULT_APPLIED_SAFETY: ("新配置已通过校验，服务刷新和健康检查已完成。"),
        UiText.PROFILE_EDIT_RESULT_VALIDATION_FAILED_TITLE: "配置校验失败，未更新",
        UiText.PROFILE_EDIT_RESULT_VALIDATION_FAILED_SAFETY: (
            "原有配置、服务和 desired state 均未改变。"
        ),
        UiText.PROFILE_EDIT_RESULT_PRECONDITION_FAILED_TITLE: "服务器配置已变化，未更新",
        UiText.PROFILE_EDIT_RESULT_PRECONDITION_FALLBACK: (
            "live configuration 不再匹配已确认的版本"
        ),
        UiText.PROFILE_EDIT_RESULT_PRECONDITION_SAFETY: ("本次尚未写入配置，请重新检查后再确认。"),
        UiText.PROFILE_EDIT_RESULT_COMMIT_FAILED_TITLE: "无法写入编辑后的配置",
        UiText.PROFILE_EDIT_RESULT_COMMIT_FALLBACK: "配置提交失败",
        UiText.PROFILE_EDIT_RESULT_COMMIT_SAFETY: (
            "尚未刷新服务，原有配置和 desired state 保持不变。"
        ),
        UiText.PROFILE_EDIT_RESULT_ROLLED_BACK_TITLE: "编辑失败，已自动回滚",
        UiText.PROFILE_EDIT_RESULT_ROLLED_BACK_FALLBACK: "旧配置已恢复。",
        UiText.PROFILE_EDIT_RESULT_ROLLED_BACK_SAFETY: ("原有配置、服务和 desired state 已保留。"),
        UiText.PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_TITLE: "回滚未完成，需要人工恢复",
        UiText.PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_FALLBACK: "回滚状态未知",
        UiText.PROFILE_EDIT_RESULT_ROLLBACK_UNKNOWN_SAFETY: (
            "desired state 未提交。完成恢复前不要再次修改配置。"
        ),
        UiText.PROFILE_EDIT_RESULT_RECOVERY_STEP: "{number}. {instruction}",
        UiText.PROFILE_EDIT_RESULT_LISTEN_PORT: "当前监听端口：{port}",
        UiText.PROFILE_EDIT_RESULT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.PROFILE_EDIT_OPERATIONAL_TITLE: "无法确认配置编辑结果",
        UiText.PROFILE_EDIT_OPERATIONAL_UNEXPECTED_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_EDIT_OPERATIONAL_KNOWN_SAFETY: (
            "desired state 未提交。请检查 sing-box 服务和 helper 日志后再决定是否重试。"
        ),
        UiText.PROFILE_EDIT_OPERATIONAL_UNKNOWN_SAFETY: (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        ),
        UiText.PROFILE_EDIT_PORT_CONFLICT_TITLE: "监听端口已不可用",
        UiText.PROFILE_EDIT_PORT_CONFLICT_SAFETY: (
            "尚未调用配置 applier，实时配置、服务和 desired state 均未改变。"
        ),
        UiText.PROFILE_EDIT_CONFLICT_TITLE: "配置已被其他会话修改",
        UiText.PROFILE_EDIT_CONFLICT_SAFETY: (
            "本次变更未执行。请返回列表，重新打开详情并预览最新计划。"
        ),
        UiText.PROFILE_AVAILABILITY_PLAN_RESUME_TITLE: "确认恢复配置",
        UiText.PROFILE_AVAILABILITY_PLAN_PAUSE_TITLE: "确认暂停配置",
        UiText.PROFILE_AVAILABILITY_PLAN_PROFILE: "配置：{name}",
        UiText.PROFILE_AVAILABILITY_PLAN_PAUSE_IMPACT: (
            "将从完整 sing-box 配置中移除此 inbound，保留 profile、端口和凭据。"
        ),
        UiText.PROFILE_AVAILABILITY_PLAN_RESUME_IMPACT: (
            "将把此 inbound 恢复到完整 sing-box 配置，校验并刷新服务。"
        ),
        UiText.PROFILE_AVAILABILITY_PLAN_ACTIVE_COUNT: "完成后在线配置数：{count}",
        UiText.PROFILE_AVAILABILITY_PLAN_SAFETY_PREVIEW: "当前仅预览，尚未修改任何内容。",
        UiText.PROFILE_AVAILABILITY_PLAN_CONFIRM_PAUSE: "确认暂停",
        UiText.PROFILE_AVAILABILITY_PLAN_CONFIRM_RESUME: "确认恢复",
        UiText.PROFILE_AVAILABILITY_PLAN_IN_PROGRESS: (
            "操作已确认，正在执行完整配置事务。完成前无法返回。"
        ),
        UiText.PROFILE_AVAILABILITY_OPERATIONAL_TITLE: "无法确认配置状态变更",
        UiText.PROFILE_AVAILABILITY_OPERATIONAL_UNEXPECTED_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_AVAILABILITY_OPERATIONAL_KNOWN_SAFETY: (
            "desired state 未提交。请重新打开配置详情并检查当前服务状态。"
        ),
        UiText.PROFILE_AVAILABILITY_OPERATIONAL_UNKNOWN_SAFETY: (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        ),
        UiText.PROFILE_AVAILABILITY_PLANNING_TITLE: "无法准备配置状态变更",
        UiText.PROFILE_AVAILABILITY_PLANNING_DETAILS: (
            "读取暂停/恢复计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_AVAILABILITY_PLANNING_SAFETY: (
            "尚未执行任何操作。请返回配置列表，重新打开详情后再试。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_PAUSED_TITLE: "配置已暂停",
        UiText.PROFILE_AVAILABILITY_RESULT_RESUMED_TITLE: "配置已恢复",
        UiText.PROFILE_AVAILABILITY_RESULT_REVISION: "desired state 已提交 revision {revision}。",
        UiText.PROFILE_AVAILABILITY_RESULT_SUCCESS_SAFETY: (
            "完整配置已通过校验，服务刷新和健康检查已完成。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.PROFILE_AVAILABILITY_RESULT_VALIDATION_FAILED_TITLE: ("配置校验失败，状态未改变"),
        UiText.PROFILE_AVAILABILITY_RESULT_VALIDATION_FAILED_SAFETY: (
            "原有配置、服务和 desired state 均未改变。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_PRECONDITION_FAILED_TITLE: (
            "服务器配置已变化，状态未改变"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_PRECONDITION_FALLBACK: (
            "live configuration 不再匹配已确认的版本"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_PRECONDITION_SAFETY: (
            "本次尚未写入配置，请重新检查后再确认。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_COMMIT_FAILED_TITLE: "无法写入状态变更后的配置",
        UiText.PROFILE_AVAILABILITY_RESULT_COMMIT_FALLBACK: "配置提交失败",
        UiText.PROFILE_AVAILABILITY_RESULT_COMMIT_SAFETY: (
            "尚未刷新服务，原有配置和 desired state 保持不变。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_TITLE: "状态变更失败，已自动回滚",
        UiText.PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_FALLBACK: "旧配置已恢复。",
        UiText.PROFILE_AVAILABILITY_RESULT_ROLLED_BACK_SAFETY: (
            "原有配置、服务和 desired state 已保留。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_TITLE: ("回滚未完成，需要人工恢复"),
        UiText.PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_FALLBACK: "回滚状态未知",
        UiText.PROFILE_AVAILABILITY_RESULT_ROLLBACK_UNKNOWN_SAFETY: (
            "desired state 未提交。完成恢复前不要再次修改配置。"
        ),
        UiText.PROFILE_AVAILABILITY_RESULT_RECOVERY_STEP: "{number}. {instruction}",
        UiText.PROFILE_REMOVAL_PLAN_TITLE: "确认移除配置",
        UiText.PROFILE_REMOVAL_PLAN_PROFILE: "配置：{name}",
        UiText.PROFILE_REMOVAL_PLAN_DRAFT_IMPACT: (
            "只删除 manager 中的草案，不会修改 sing-box 配置或刷新服务。"
        ),
        UiText.PROFILE_REMOVAL_PLAN_LIVE_IMPACT: (
            "将生成不含此配置的完整 sing-box 配置，校验并刷新服务。失败时自动回滚。"
        ),
        UiText.PROFILE_REMOVAL_PLAN_REMAINING: (
            "移除后保留 {profiles} 个配置，其中 {applied} 个已应用。"
        ),
        UiText.PROFILE_REMOVAL_PLAN_SAFETY_PREVIEW: "当前仅预览，尚未删除任何内容。",
        UiText.PROFILE_REMOVAL_PLAN_CONFIRM_DRAFT: "确认移除草案",
        UiText.PROFILE_REMOVAL_PLAN_CONFIRM_LIVE: "确认下线并移除",
        UiText.PROFILE_REMOVAL_PLAN_IN_PROGRESS: "操作已确认，正在执行移除计划。完成前无法返回。",
        UiText.PROFILE_REMOVAL_RESULT_DRAFT_TITLE: "草案已移除",
        UiText.PROFILE_REMOVAL_RESULT_APPLIED_TITLE: "配置已下线并移除",
        UiText.PROFILE_REMOVAL_RESULT_REVISION: "desired state 已提交 revision {revision}。",
        UiText.PROFILE_REMOVAL_RESULT_DRAFT_SAFETY: "未修改 sing-box 配置，也未刷新服务。",
        UiText.PROFILE_REMOVAL_RESULT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.PROFILE_REMOVAL_RESULT_UNTRUSTED_TITLE: "无法确认移除结果",
        UiText.PROFILE_REMOVAL_RESULT_UNTRUSTED_DETAILS: "未收到可信的 host transaction。",
        UiText.PROFILE_REMOVAL_RESULT_UNTRUSTED_SAFETY: (
            "desired state 未提交，host transaction 结果未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_APPLIED_SAFETY: (
            "新配置已通过校验，服务刷新和健康检查已完成。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_VALIDATION_FAILED_TITLE: "配置校验失败，未移除",
        UiText.PROFILE_REMOVAL_RESULT_VALIDATION_FAILED_SAFETY: (
            "原有配置、服务和 desired state 均未改变。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_PRECONDITION_FAILED_TITLE: "服务器配置已变化，未移除",
        UiText.PROFILE_REMOVAL_RESULT_PRECONDITION_FALLBACK: (
            "live configuration 不再匹配已确认的版本"
        ),
        UiText.PROFILE_REMOVAL_RESULT_PRECONDITION_SAFETY: (
            "本次尚未写入配置，请重新检查后再确认。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_COMMIT_FAILED_TITLE: "无法写入移除后的配置",
        UiText.PROFILE_REMOVAL_RESULT_COMMIT_FALLBACK: "配置提交失败",
        UiText.PROFILE_REMOVAL_RESULT_COMMIT_SAFETY: (
            "尚未刷新服务，原有配置和 desired state 保持不变。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_ROLLED_BACK_TITLE: "移除失败，已自动回滚",
        UiText.PROFILE_REMOVAL_RESULT_ROLLED_BACK_FALLBACK: "旧配置已恢复。",
        UiText.PROFILE_REMOVAL_RESULT_ROLLED_BACK_SAFETY: (
            "原有配置、服务和 desired state 已保留。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_TITLE: "回滚未完成，需要人工恢复",
        UiText.PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_FALLBACK: "回滚状态未知",
        UiText.PROFILE_REMOVAL_RESULT_ROLLBACK_UNKNOWN_SAFETY: (
            "desired state 未提交。完成恢复前不要再次修改配置。"
        ),
        UiText.PROFILE_REMOVAL_RESULT_RECOVERY_STEP: "{number}. {instruction}",
        UiText.PROFILE_REMOVAL_OPERATIONAL_TITLE: "无法确认配置移除结果",
        UiText.PROFILE_REMOVAL_OPERATIONAL_UNEXPECTED_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_REMOVAL_OPERATIONAL_KNOWN_SAFETY: (
            "desired state 未提交。请检查 sing-box 服务和 helper 日志后再决定是否重试。"
        ),
        UiText.PROFILE_REMOVAL_OPERATIONAL_UNKNOWN_SAFETY: (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
        ),
        UiText.PROFILE_REMOVAL_PLANNING_TITLE: "无法准备配置移除",
        UiText.PROFILE_REMOVAL_PLANNING_DETAILS: (
            "读取配置移除计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_REMOVAL_PLANNING_SAFETY: (
            "尚未执行任何操作。请返回配置列表，重新打开详情后再试。"
        ),
        UiText.CONNECTION_SHARE_ENDPOINT: "服务器：{address}:{port}",
        UiText.CONNECTION_SHARE_WARNING_HIDDEN: (
            "连接链接包含完整访问凭据，默认隐藏。仅在私密终端中显示。"
        ),
        UiText.CONNECTION_SHARE_REVEAL: "显示一次连接链接",
        UiText.CONNECTION_SHARE_WARNING_REVEALED: (
            "连接链接仅在本次页面中可见，离开后将重新隐藏。"
        ),
        UiText.CONNECTION_SHARE_HIDE: "立即隐藏连接链接",
        UiText.CONNECTION_SHARE_LABEL: "连接链接 - 本次页面可见",
        UiText.CONNECTION_SHARE_WARNING_HIDDEN_AFTER: (
            "连接链接已重新隐藏，本页面不会再次显示。返回详情后可重新选择显示。"
        ),
        UiText.SETTINGS_TITLE: "设置",
        UiText.SETTINGS_BINDING: "设置",
        UiText.SETTINGS_OPEN: "打开设置",
        UiText.SETTINGS_LANGUAGE: "界面语言：简体中文 · 当前版本完整支持",
        UiText.SETTINGS_LANGUAGE_POLICY: (
            "语言范围：完整文案目录覆盖所有安全流程前，不开放其他语言。"
        ),
        UiText.SETTINGS_COLOR_DARK: "深色",
        UiText.SETTINGS_COLOR_LIGHT: "浅色",
        UiText.SETTINGS_APPEARANCE: "界面外观：{label}",
        UiText.SETTINGS_TOGGLE_APPEARANCE: "切换为{target}",
        UiText.SETTINGS_REVIEW_RESET: "审查并重置界面偏好",
        UiText.SETTINGS_UPDATE_POLICY: "核心更新：手动指定确切版本 · 不自动更新",
        UiText.SETTINGS_PERSISTENCE_SAVED: "外观保存：已保存，下次启动将继续使用{label}",
        UiText.SETTINGS_PERSISTENCE_LOADED: "外观保存：已从偏好文件载入",
        UiText.SETTINGS_PERSISTENCE_LOAD_FAILED: ("外观保存：无法读取偏好文件，本次使用默认深色"),
        UiText.SETTINGS_PERSISTENCE_SAVE_FAILED: (
            "外观保存：本次已应用，但未能保存。下次启动可能恢复默认值"
        ),
        UiText.SETTINGS_PERSISTENCE_RESET: ("外观保存：已重置为深色，原文件已按 SHA-256 归档"),
        UiText.SETTINGS_PERSISTENCE_READY: "外观保存：已启用，切换后会保留到下次启动",
        UiText.SETTINGS_PERSISTENCE_SESSION_ONLY: "外观保存：仅本次会话",
        UiText.SETTINGS_SAFETY_SESSION: (
            "外观变更仅影响本次 TUI 会话，不会修改主机或 desired state。"
        ),
        UiText.SETTINGS_SAFETY_PERSISTED: (
            "外观偏好只写入当前用户的本地偏好文件，不会修改主机或 desired state。"
        ),
        UiText.SETTINGS_HOST_ACCESS_PRIVILEGED: "主机变更：最小权限 helper",
        UiText.SETTINGS_HOST_ACCESS_DIRECT: "主机变更：直接模式",
        UiText.SETTINGS_HOST_ACCESS_UNAVAILABLE: "主机变更：当前启动方式未提供",
        UiText.SETTINGS_RUNTIME_SYSTEMD: "服务管理：systemd",
        UiText.SETTINGS_RUNTIME_OPENRC: "服务管理：OpenRC",
        UiText.SETTINGS_RUNTIME_UNAVAILABLE: "服务管理：当前启动方式未提供",
        UiText.SETTINGS_CONFIG_PRIVILEGED: ("live configuration：由最小权限 helper 的固定策略管理"),
        UiText.SETTINGS_PATH: "{role}：{path}",
        UiText.SETTINGS_PATH_UNAVAILABLE: "当前启动方式未提供",
        UiText.SETTINGS_ROLE_STATE: "desired state",
        UiText.SETTINGS_ROLE_PREFERENCES: "界面偏好",
        UiText.SETTINGS_ROLE_CONFIG: "live configuration",
        UiText.SETTINGS_ROLE_TRANSACTION: "事务提交目录",
        UiText.PREFERENCE_RESET_TITLE: "确认重置界面偏好",
        UiText.PREFERENCE_RESET_FINGERPRINT: "待替换文件 SHA-256：{sha256}",
        UiText.PREFERENCE_RESET_DEFAULT: "重置结果：schema v1 · 深色外观",
        UiText.PREFERENCE_RESET_SAFETY: (
            "确认后会先归档原字节，再只替换当前用户的界面偏好。"
            "不会修改 desired state、live configuration 或主机。"
        ),
        UiText.PREFERENCE_RESET_CONFIRM: "确认并重置",
        UiText.PREFERENCE_RESET_IN_PROGRESS: (
            "操作已确认，正在归档并重置界面偏好。完成前无法返回。"
        ),
        UiText.PREFERENCE_RESET_CONFLICT: (
            "偏好文件在审阅后已变化，未覆盖任何内容。请返回设置重新审查。"
        ),
        UiText.PREFERENCE_RESET_ERROR: ("无法安全归档或写入偏好文件。请检查路径和权限后重新审查。"),
        UiText.PREFERENCE_RESET_PLANNING_TITLE: "无法准备界面偏好重置",
        UiText.PREFERENCE_RESET_PLANNING_DETAILS: (
            "偏好文件无法安全读取或不是普通文件，底层错误和文件内容均未显示。"
        ),
        UiText.PREFERENCE_RESET_PLANNING_SAFETY: (
            "尚未替换或删除任何内容。请检查偏好路径、权限或符号链接后重新打开设置。"
        ),
        UiText.PREFERENCE_RESET_OPERATIONAL_TITLE: "无法确认界面偏好重置结果",
        UiText.PREFERENCE_RESET_OPERATIONAL_DETAILS: (
            "发生意外错误，底层错误和偏好文件内容均未显示。"
        ),
        UiText.PREFERENCE_RESET_OPERATIONAL_SAFETY: (
            "当前偏好文件或归档可能已经写入。请重新启动 manager 只读检查后再决定是否重试。"
        ),
    },
)
