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
    HOST_DIAGNOSTICS_TITLE = "host_diagnostics.title"
    HOST_DIAGNOSTICS_SUMMARY_HEALTHY = "host_diagnostics.summary.healthy"
    HOST_DIAGNOSTICS_SUMMARY_UNHEALTHY = "host_diagnostics.summary.unhealthy"
    HOST_DIAGNOSTICS_DETAILS_UNAVAILABLE = "host_diagnostics.details.unavailable"
    HOST_DIAGNOSTICS_RECOVERY_TITLE = "host_diagnostics.recovery.title"
    HOST_DIAGNOSTICS_RECOVERY_STEP = "host_diagnostics.recovery.step"
    HOST_DIAGNOSTICS_RECOVERY_EMPTY = "host_diagnostics.recovery.empty"
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
    PROFILE_CLONE_FORM_TITLE = "profile_clone.form.title"
    PROFILE_CLONE_FACET_PROTOCOL = "profile_clone.facet.protocol"
    PROFILE_CLONE_FACET_SERVER_ADDRESS = "profile_clone.facet.server_address"
    PROFILE_CLONE_FACET_TLS_STRATEGY = "profile_clone.facet.tls_strategy"
    PROFILE_CLONE_FACET_TRANSPORT = "profile_clone.facet.transport"
    PROFILE_CLONE_FACET_CREDENTIALS = "profile_clone.facet.credentials"
    PROFILE_CLONE_FACET_LISTEN_PORT = "profile_clone.facet.listen_port"
    PROFILE_CLONE_FACET_RUNTIME_STATUS = "profile_clone.facet.runtime_status"
    PROFILE_CLONE_FACET_SEPARATOR = "profile_clone.facet.separator"
    PROFILE_CLONE_FACET_CONJUNCTION = "profile_clone.facet.conjunction"
    PROFILE_CLONE_FORM_SOURCE = "profile_clone.form.source"
    PROFILE_CLONE_FORM_COPIED = "profile_clone.form.copied"
    PROFILE_CLONE_FORM_RESET = "profile_clone.form.reset"
    PROFILE_CLONE_FORM_REVIEW = "profile_clone.form.review"
    PROFILE_CLONE_FORM_EDIT = "profile_clone.form.edit"
    PROFILE_CLONE_FORM_CONFIRM = "profile_clone.form.confirm"
    PROFILE_CLONE_FORM_RETURN_LIST = "profile_clone.form.return_list"
    PROFILE_CLONE_REVIEW_TITLE = "profile_clone.review.title"
    PROFILE_CLONE_REVIEW_SUMMARY = "profile_clone.review.summary"
    PROFILE_CLONE_IN_PROGRESS = "profile_clone.in_progress"
    PROFILE_CLONE_STALE = "profile_clone.stale"
    PROFILE_CLONE_RESULT_TITLE = "profile_clone.result.title"
    PROFILE_CLONE_RESULT_SUMMARY = "profile_clone.result.summary"
    PROFILE_CLONE_PLANNING_TITLE = "profile_clone.planning.title"
    PROFILE_CLONE_PLANNING_DETAILS = "profile_clone.planning.details"
    PROFILE_CLONE_PLANNING_SAFETY = "profile_clone.planning.safety"
    PROFILE_CLONE_OPERATIONAL_TITLE = "profile_clone.operational.title"
    PROFILE_CLONE_OPERATIONAL_DETAILS = "profile_clone.operational.details"
    PROFILE_CLONE_OPERATIONAL_SAFETY = "profile_clone.operational.safety"
    PROFILE_RECOMMENDATION_PURPOSE_TITLE = "profile_recommendation.purpose.title"
    PROFILE_RECOMMENDATION_PURPOSE_GUIDANCE = "profile_recommendation.purpose.guidance"
    PROFILE_RECOMMENDATION_PURPOSE_CHOICE_RECOMMENDED = (
        "profile_recommendation.purpose.choice.recommended"
    )
    PROFILE_RECOMMENDATION_PURPOSE_CHOOSE_DIRECTLY = (
        "profile_recommendation.purpose.choose_directly"
    )
    PROFILE_RECOMMENDATION_PURPOSE_GENERAL = "profile_recommendation.purpose.general"
    PROFILE_RECOMMENDATION_PURPOSE_LOW_LATENCY = "profile_recommendation.purpose.low_latency"
    PROFILE_RECOMMENDATION_PURPOSE_RESTRICTED_NETWORK = (
        "profile_recommendation.purpose.restricted_network"
    )
    PROFILE_RECOMMENDATION_PURPOSE_COMPATIBILITY = "profile_recommendation.purpose.compatibility"
    PROFILE_RECOMMENDATION_VARIANT_VLESS_REALITY = "profile_recommendation.variant.vless_reality"
    PROFILE_RECOMMENDATION_VARIANT_SHADOWSOCKS = "profile_recommendation.variant.shadowsocks"
    PROFILE_RECOMMENDATION_VARIANT_HYSTERIA2 = "profile_recommendation.variant.hysteria2"
    PROFILE_RECOMMENDATION_VARIANT_TROJAN = "profile_recommendation.variant.trojan"
    PROFILE_RECOMMENDATION_VARIANT_ANYTLS = "profile_recommendation.variant.anytls"
    PROFILE_RECOMMENDATION_VARIANT_TUIC = "profile_recommendation.variant.tuic"
    PROFILE_RECOMMENDATION_VARIANT_VLESS_WEBSOCKET = (
        "profile_recommendation.variant.vless_websocket"
    )
    PROFILE_RECOMMENDATION_VARIANT_VLESS_GRPC = "profile_recommendation.variant.vless_grpc"
    PROFILE_RECOMMENDATION_VARIANT_VMESS_WEBSOCKET = (
        "profile_recommendation.variant.vmess_websocket"
    )
    PROFILE_RECOMMENDATION_VARIANT_VMESS_GRPC = "profile_recommendation.variant.vmess_grpc"
    PROFILE_RECOMMENDATION_RANKING_TITLE = "profile_recommendation.ranking.title"
    PROFILE_RECOMMENDATION_RANKING_CAVEAT = "profile_recommendation.ranking.caveat"
    PROFILE_RECOMMENDATION_RANKING_CHOICE_PRIMARY = "profile_recommendation.ranking.choice.primary"
    PROFILE_RECOMMENDATION_RANKING_CHOICE = "profile_recommendation.ranking.choice"
    PROFILE_RECOMMENDATION_RANKING_REASON = "profile_recommendation.ranking.reason"
    PROFILE_RECOMMENDATION_RANKING_TRADEOFF = "profile_recommendation.ranking.tradeoff"
    PROFILE_RECOMMENDATION_RANKING_SELECT = "profile_recommendation.ranking.select"
    PROFILE_RECOMMENDATION_ERROR_TITLE = "profile_recommendation.error.title"
    PROFILE_RECOMMENDATION_ERROR_DETAILS = "profile_recommendation.error.details"
    PROFILE_RECOMMENDATION_ERROR_SAFETY = "profile_recommendation.error.safety"
    PROFILE_RECOMMENDATION_ERROR_CHOOSE_DIRECTLY = "profile_recommendation.error.choose_directly"
    PROFILE_RECOMMENDATION_DIRECT_TITLE = "profile_recommendation.direct.title"
    PROFILE_RECOMMENDATION_DIRECT_GUIDANCE = "profile_recommendation.direct.guidance"
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_REALITY = (
        "profile_recommendation.direct.choice.vless_reality"
    )
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_SHADOWSOCKS = (
        "profile_recommendation.direct.choice.shadowsocks"
    )
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_HYSTERIA2 = (
        "profile_recommendation.direct.choice.hysteria2"
    )
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_TROJAN = "profile_recommendation.direct.choice.trojan"
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_ANYTLS = "profile_recommendation.direct.choice.anytls"
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_TUIC = "profile_recommendation.direct.choice.tuic"
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_WEBSOCKET = (
        "profile_recommendation.direct.choice.vless_websocket"
    )
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_GRPC = (
        "profile_recommendation.direct.choice.vless_grpc"
    )
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_VMESS_WEBSOCKET = (
        "profile_recommendation.direct.choice.vmess_websocket"
    )
    PROFILE_RECOMMENDATION_DIRECT_CHOICE_VMESS_GRPC = (
        "profile_recommendation.direct.choice.vmess_grpc"
    )
    PROFILE_RECOMMENDATION_GENERAL_VLESS_REALITY_REASON = (
        "profile_recommendation.rationale.general_vless_reality.reason"
    )
    PROFILE_RECOMMENDATION_GENERAL_VLESS_REALITY_TRADEOFF = (
        "profile_recommendation.rationale.general_vless_reality.tradeoff"
    )
    PROFILE_RECOMMENDATION_GENERAL_SHADOWSOCKS_REASON = (
        "profile_recommendation.rationale.general_shadowsocks.reason"
    )
    PROFILE_RECOMMENDATION_GENERAL_SHADOWSOCKS_TRADEOFF = (
        "profile_recommendation.rationale.general_shadowsocks.tradeoff"
    )
    PROFILE_RECOMMENDATION_GENERAL_TROJAN_REASON = (
        "profile_recommendation.rationale.general_trojan.reason"
    )
    PROFILE_RECOMMENDATION_GENERAL_TROJAN_TRADEOFF = (
        "profile_recommendation.rationale.general_trojan.tradeoff"
    )
    PROFILE_RECOMMENDATION_LOW_LATENCY_HYSTERIA2_REASON = (
        "profile_recommendation.rationale.low_latency_hysteria2.reason"
    )
    PROFILE_RECOMMENDATION_LOW_LATENCY_HYSTERIA2_TRADEOFF = (
        "profile_recommendation.rationale.low_latency_hysteria2.tradeoff"
    )
    PROFILE_RECOMMENDATION_LOW_LATENCY_TUIC_REASON = (
        "profile_recommendation.rationale.low_latency_tuic.reason"
    )
    PROFILE_RECOMMENDATION_LOW_LATENCY_TUIC_TRADEOFF = (
        "profile_recommendation.rationale.low_latency_tuic.tradeoff"
    )
    PROFILE_RECOMMENDATION_LOW_LATENCY_VLESS_REALITY_REASON = (
        "profile_recommendation.rationale.low_latency_vless_reality.reason"
    )
    PROFILE_RECOMMENDATION_LOW_LATENCY_VLESS_REALITY_TRADEOFF = (
        "profile_recommendation.rationale.low_latency_vless_reality.tradeoff"
    )
    PROFILE_RECOMMENDATION_RESTRICTED_VLESS_REALITY_REASON = (
        "profile_recommendation.rationale.restricted_vless_reality.reason"
    )
    PROFILE_RECOMMENDATION_RESTRICTED_VLESS_REALITY_TRADEOFF = (
        "profile_recommendation.rationale.restricted_vless_reality.tradeoff"
    )
    PROFILE_RECOMMENDATION_RESTRICTED_ANYTLS_REASON = (
        "profile_recommendation.rationale.restricted_anytls.reason"
    )
    PROFILE_RECOMMENDATION_RESTRICTED_ANYTLS_TRADEOFF = (
        "profile_recommendation.rationale.restricted_anytls.tradeoff"
    )
    PROFILE_RECOMMENDATION_RESTRICTED_VLESS_WEBSOCKET_REASON = (
        "profile_recommendation.rationale.restricted_vless_websocket.reason"
    )
    PROFILE_RECOMMENDATION_RESTRICTED_VLESS_WEBSOCKET_TRADEOFF = (
        "profile_recommendation.rationale.restricted_vless_websocket.tradeoff"
    )
    PROFILE_RECOMMENDATION_COMPATIBILITY_TROJAN_REASON = (
        "profile_recommendation.rationale.compatibility_trojan.reason"
    )
    PROFILE_RECOMMENDATION_COMPATIBILITY_TROJAN_TRADEOFF = (
        "profile_recommendation.rationale.compatibility_trojan.tradeoff"
    )
    PROFILE_RECOMMENDATION_COMPATIBILITY_SHADOWSOCKS_REASON = (
        "profile_recommendation.rationale.compatibility_shadowsocks.reason"
    )
    PROFILE_RECOMMENDATION_COMPATIBILITY_SHADOWSOCKS_TRADEOFF = (
        "profile_recommendation.rationale.compatibility_shadowsocks.tradeoff"
    )
    PROFILE_RECOMMENDATION_COMPATIBILITY_VMESS_WEBSOCKET_REASON = (
        "profile_recommendation.rationale.compatibility_vmess_websocket.reason"
    )
    PROFILE_RECOMMENDATION_COMPATIBILITY_VMESS_WEBSOCKET_TRADEOFF = (
        "profile_recommendation.rationale.compatibility_vmess_websocket.tradeoff"
    )
    CORE_UPDATE_FORM_TITLE = "core_update.form.title"
    CORE_UPDATE_OPEN = "core_update.open"
    CORE_UPDATE_FORM_GUIDANCE = "core_update.form.guidance"
    CORE_UPDATE_FORM_VERSION_LABEL = "core_update.form.version_label"
    CORE_UPDATE_FORM_VERSION_PLACEHOLDER = "core_update.form.version_placeholder"
    CORE_UPDATE_FORM_ARCHITECTURE_LABEL = "core_update.form.architecture_label"
    CORE_UPDATE_FORM_ARCHITECTURE_AMD64 = "core_update.form.architecture.amd64"
    CORE_UPDATE_FORM_ARCHITECTURE_ARM64 = "core_update.form.architecture.arm64"
    CORE_UPDATE_FORM_PRERELEASE_CONSENT = "core_update.form.prerelease_consent"
    CORE_UPDATE_FORM_PREVIEW = "core_update.form.preview"
    CORE_UPDATE_FORM_ERROR_INVALID_VERSION = "core_update.form.error.invalid_version"
    CORE_UPDATE_FORM_ERROR_ARCHITECTURE = "core_update.form.error.architecture"
    CORE_UPDATE_FORM_ERROR_PRERELEASE_CONSENT = "core_update.form.error.prerelease_consent"
    CORE_UPDATE_PLAN_TITLE = "core_update.plan.title"
    CORE_UPDATE_PLAN_VERSION = "core_update.plan.version"
    CORE_UPDATE_PLAN_ARCHITECTURE = "core_update.plan.architecture"
    CORE_UPDATE_PLAN_ASSET = "core_update.plan.asset"
    CORE_UPDATE_PLAN_SOURCE = "core_update.plan.source"
    CORE_UPDATE_PLAN_WARNING_PRERELEASE = "core_update.plan.warning.prerelease"
    CORE_UPDATE_PLAN_SAFETY = "core_update.plan.safety"
    CORE_UPDATE_PLAN_CONFIRM = "core_update.plan.confirm"
    CORE_UPDATE_PLAN_PROGRESS = "core_update.plan.progress"
    CORE_UPDATE_RESULT_TITLE = "core_update.result.title"
    CORE_UPDATE_RESULT_VERSION = "core_update.result.version"
    CORE_UPDATE_RESULT_BINARY = "core_update.result.binary"
    CORE_UPDATE_RESULT_TARGET = "core_update.result.target"
    CORE_UPDATE_RESULT_PREVIOUS = "core_update.result.previous"
    CORE_UPDATE_RESULT_PREVIOUS_NONE = "core_update.result.previous.none"
    CORE_UPDATE_PLANNING_ERROR_TITLE = "core_update.planning_error.title"
    CORE_UPDATE_PLANNING_ERROR_DETAILS = "core_update.planning_error.details"
    CORE_UPDATE_PLANNING_ERROR_SAFETY = "core_update.planning_error.safety"
    CORE_UPDATE_ERROR_UNKNOWN_TITLE = "core_update.error.unknown.title"
    CORE_UPDATE_ERROR_ACQUISITION_TITLE = "core_update.error.acquisition.title"
    CORE_UPDATE_ERROR_UNKNOWN_SAFETY = "core_update.error.unknown.safety"
    CORE_UPDATE_ERROR_ACQUISITION_SAFETY = "core_update.error.acquisition.safety"
    CORE_UPDATE_ERROR_UNEXPECTED_DETAILS = "core_update.error.unexpected_details"
    CONFIG_ADOPTION_PLAN_LOADING = "config_adoption.plan.loading"
    CONFIG_ADOPTION_PLAN_TITLE = "config_adoption.plan.title"
    CONFIG_ADOPTION_PLAN_FINGERPRINT = "config_adoption.plan.fingerprint"
    CONFIG_ADOPTION_PLAN_SAFETY = "config_adoption.plan.safety"
    CONFIG_ADOPTION_PLAN_CONFIRM = "config_adoption.plan.confirm"
    CONFIG_ADOPTION_PLAN_PROGRESS = "config_adoption.plan.progress"
    CONFIG_ADOPTION_RESULT_TITLE = "config_adoption.result.title"
    CONFIG_ADOPTION_RESULT_REVISION = "config_adoption.result.revision"
    CONFIG_ADOPTION_RESULT_SAFETY = "config_adoption.result.safety"
    CONFIG_ADOPTION_RESULT_RETURN_DASHBOARD = "config_adoption.result.return_dashboard"
    CONFIG_ADOPTION_PLANNING_ERROR_TITLE = "config_adoption.planning_error.title"
    CONFIG_ADOPTION_PLANNING_ERROR_DETAILS = "config_adoption.planning_error.details"
    CONFIG_ADOPTION_PLANNING_ERROR_SAFETY = "config_adoption.planning_error.safety"
    CONFIG_ADOPTION_UNKNOWN_TITLE = "config_adoption.unknown.title"
    CONFIG_ADOPTION_UNKNOWN_DETAILS = "config_adoption.unknown.details"
    CONFIG_ADOPTION_UNKNOWN_SAFETY = "config_adoption.unknown.safety"
    CONFIG_ADOPTION_ERROR_TITLE = "config_adoption.error.title"
    CONFIG_ADOPTION_ERROR_SAFETY = "config_adoption.error.safety"
    STATE_RECOVERY_AVAILABLE_TITLE = "state_recovery.available.title"
    STATE_RECOVERY_AVAILABLE_BACKUP = "state_recovery.available.backup"
    STATE_RECOVERY_AVAILABLE_GUIDANCE = "state_recovery.available.guidance"
    STATE_RECOVERY_AVAILABLE_REVIEW = "state_recovery.available.review"
    STATE_RECOVERY_CONFIRM_TITLE = "state_recovery.confirm.title"
    STATE_RECOVERY_CONFIRM_BACKUP = "state_recovery.confirm.backup"
    STATE_RECOVERY_CONFIRM_PRIMARY_FINGERPRINT = "state_recovery.confirm.primary_fingerprint"
    STATE_RECOVERY_CONFIRM_BACKUP_FINGERPRINT = "state_recovery.confirm.backup_fingerprint"
    STATE_RECOVERY_CONFIRM_SAFETY = "state_recovery.confirm.safety"
    STATE_RECOVERY_CONFIRM_ACTION = "state_recovery.confirm.action"
    STATE_RECOVERY_CONFIRM_PROGRESS = "state_recovery.confirm.progress"
    STATE_RECOVERY_RESULT_TITLE = "state_recovery.result.title"
    STATE_RECOVERY_RESULT_REVISION = "state_recovery.result.revision"
    STATE_RECOVERY_RESULT_PROFILES = "state_recovery.result.profiles"
    STATE_RECOVERY_RESULT_ARCHIVE = "state_recovery.result.archive"
    STATE_RECOVERY_RESULT_SAFETY = "state_recovery.result.safety"
    STATE_RECOVERY_RESULT_RETURN_DASHBOARD = "state_recovery.result.return_dashboard"
    STATE_RECOVERY_REJECTION_TITLE = "state_recovery.rejection.title"
    STATE_RECOVERY_REJECTION_SAFETY = "state_recovery.rejection.safety"
    STATE_RECOVERY_UNKNOWN_TITLE = "state_recovery.unknown.title"
    STATE_RECOVERY_UNKNOWN_DETAILS = "state_recovery.unknown.details"
    STATE_RECOVERY_UNKNOWN_SAFETY = "state_recovery.unknown.safety"
    STATE_RECOVERY_INSPECTION_ERROR_TITLE = "state_recovery.inspection_error.title"
    STATE_RECOVERY_INSPECTION_ERROR_DETAILS = "state_recovery.inspection_error.details"
    STATE_RECOVERY_INSPECTION_ERROR_SAFETY = "state_recovery.inspection_error.safety"
    STATE_RECOVERY_UNSUPPORTED_TITLE = "state_recovery.unsupported.title"
    STATE_RECOVERY_UNSUPPORTED_GUIDANCE = "state_recovery.unsupported.guidance"
    STATE_RECOVERY_UNAVAILABLE_TITLE = "state_recovery.unavailable.title"
    STATE_RECOVERY_UNAVAILABLE_GUIDANCE = "state_recovery.unavailable.guidance"
    STATE_RECOVERY_PLANNING_ERROR_TITLE = "state_recovery.planning_error.title"
    STATE_RECOVERY_PLANNING_ERROR_DETAILS = "state_recovery.planning_error.details"
    STATE_RECOVERY_PLANNING_ERROR_SAFETY = "state_recovery.planning_error.safety"
    PROFILE_CREATION_VALIDATION_PROFILE_NAME_REQUIRED = (
        "profile_creation.validation.profile_name_required"
    )
    PROFILE_CREATION_VALIDATION_LISTEN_PORT_OUT_OF_RANGE = (
        "profile_creation.validation.listen_port_out_of_range"
    )
    PROFILE_CREATION_VALIDATION_TLS_NOT_SUPPORTED = "profile_creation.validation.tls_not_supported"
    PROFILE_CREATION_VALIDATION_TLS_REQUIRED = "profile_creation.validation.tls_required"
    PROFILE_CREATION_VALIDATION_TLS_SERVER_NAME_REQUIRED = (
        "profile_creation.validation.tls_server_name_required"
    )
    PROFILE_CREATION_VALIDATION_TLS_EMAIL_REQUIRED = (
        "profile_creation.validation.tls_email_required"
    )
    PROFILE_CREATION_VALIDATION_TLS_CERTIFICATE_PATH_UNTRUSTED = (
        "profile_creation.validation.tls_certificate_path_untrusted"
    )
    PROFILE_CREATION_VALIDATION_TLS_KEY_PATH_UNTRUSTED = (
        "profile_creation.validation.tls_key_path_untrusted"
    )
    PROFILE_CREATION_VALIDATION_TRANSPORT_NOT_SUPPORTED = (
        "profile_creation.validation.transport_not_supported"
    )
    PROFILE_CREATION_VALIDATION_TRANSPORT_REQUIRED = (
        "profile_creation.validation.transport_required"
    )
    PROFILE_CREATION_VALIDATION_WEBSOCKET_PATH_INVALID = (
        "profile_creation.validation.websocket_path_invalid"
    )
    PROFILE_CREATION_VALIDATION_GRPC_SERVICE_NAME_REQUIRED = (
        "profile_creation.validation.grpc_service_name_required"
    )
    PROFILE_CREATION_FORM_TITLE_VLESS_REALITY = "profile_creation.form.title.vless_reality"
    PROFILE_CREATION_FORM_GUIDANCE_VLESS_REALITY = "profile_creation.form.guidance.vless_reality"
    PROFILE_CREATION_FORM_TITLE_SHADOWSOCKS = "profile_creation.form.title.shadowsocks"
    PROFILE_CREATION_FORM_GUIDANCE_SHADOWSOCKS = "profile_creation.form.guidance.shadowsocks"
    PROFILE_CREATION_FORM_TITLE_HYSTERIA2 = "profile_creation.form.title.hysteria2"
    PROFILE_CREATION_FORM_GUIDANCE_HYSTERIA2 = "profile_creation.form.guidance.hysteria2"
    PROFILE_CREATION_FORM_TITLE_TROJAN = "profile_creation.form.title.trojan"
    PROFILE_CREATION_FORM_GUIDANCE_TROJAN = "profile_creation.form.guidance.trojan"
    PROFILE_CREATION_FORM_TITLE_ANYTLS = "profile_creation.form.title.anytls"
    PROFILE_CREATION_FORM_GUIDANCE_ANYTLS = "profile_creation.form.guidance.anytls"
    PROFILE_CREATION_FORM_TITLE_TUIC = "profile_creation.form.title.tuic"
    PROFILE_CREATION_FORM_GUIDANCE_TUIC = "profile_creation.form.guidance.tuic"
    PROFILE_CREATION_FORM_TITLE_VLESS_WEBSOCKET = "profile_creation.form.title.vless_websocket"
    PROFILE_CREATION_FORM_GUIDANCE_VLESS_WEBSOCKET = (
        "profile_creation.form.guidance.vless_websocket"
    )
    PROFILE_CREATION_FORM_TITLE_VLESS_GRPC = "profile_creation.form.title.vless_grpc"
    PROFILE_CREATION_FORM_GUIDANCE_VLESS_GRPC = "profile_creation.form.guidance.vless_grpc"
    PROFILE_CREATION_FORM_TITLE_VMESS_WEBSOCKET = "profile_creation.form.title.vmess_websocket"
    PROFILE_CREATION_FORM_GUIDANCE_VMESS_WEBSOCKET = (
        "profile_creation.form.guidance.vmess_websocket"
    )
    PROFILE_CREATION_FORM_TITLE_VMESS_GRPC = "profile_creation.form.title.vmess_grpc"
    PROFILE_CREATION_FORM_GUIDANCE_VMESS_GRPC = "profile_creation.form.guidance.vmess_grpc"
    PROFILE_CREATION_FORM_PROFILE_NAME_LABEL = "profile_creation.form.profile_name_label"
    PROFILE_CREATION_FORM_PROFILE_NAME_PLACEHOLDER = (
        "profile_creation.form.profile_name_placeholder"
    )
    PROFILE_CREATION_FORM_SERVER_ADDRESS_LABEL = "profile_creation.form.server_address_label"
    PROFILE_CREATION_FORM_SERVER_ADDRESS_PLACEHOLDER = (
        "profile_creation.form.server_address_placeholder"
    )
    PROFILE_CREATION_FORM_TLS_SERVER_NAME_LABEL = "profile_creation.form.tls_server_name_label"
    PROFILE_CREATION_FORM_TLS_SERVER_NAME_PLACEHOLDER = (
        "profile_creation.form.tls_server_name_placeholder"
    )
    PROFILE_CREATION_FORM_TLS_STRATEGY_LABEL = "profile_creation.form.tls_strategy_label"
    PROFILE_CREATION_FORM_TLS_STRATEGY_ACME = "profile_creation.form.tls_strategy.acme"
    PROFILE_CREATION_FORM_TLS_STRATEGY_FILES = "profile_creation.form.tls_strategy.files"
    PROFILE_CREATION_FORM_TLS_EMAIL_LABEL = "profile_creation.form.tls_email_label"
    PROFILE_CREATION_FORM_TLS_EMAIL_PLACEHOLDER = "profile_creation.form.tls_email_placeholder"
    PROFILE_CREATION_FORM_TLS_CERTIFICATE_PATH_LABEL = (
        "profile_creation.form.tls_certificate_path_label"
    )
    PROFILE_CREATION_FORM_TLS_CERTIFICATE_PATH_PLACEHOLDER = (
        "profile_creation.form.tls_certificate_path_placeholder"
    )
    PROFILE_CREATION_FORM_TLS_KEY_PATH_LABEL = "profile_creation.form.tls_key_path_label"
    PROFILE_CREATION_FORM_TLS_KEY_PATH_PLACEHOLDER = (
        "profile_creation.form.tls_key_path_placeholder"
    )
    PROFILE_CREATION_FORM_WEBSOCKET_PATH_LABEL = "profile_creation.form.websocket_path_label"
    PROFILE_CREATION_FORM_WEBSOCKET_PATH_PLACEHOLDER = (
        "profile_creation.form.websocket_path_placeholder"
    )
    PROFILE_CREATION_FORM_WEBSOCKET_HOST_LABEL = "profile_creation.form.websocket_host_label"
    PROFILE_CREATION_FORM_WEBSOCKET_HOST_PLACEHOLDER = (
        "profile_creation.form.websocket_host_placeholder"
    )
    PROFILE_CREATION_FORM_GRPC_SERVICE_NAME_LABEL = "profile_creation.form.grpc_service_name_label"
    PROFILE_CREATION_FORM_GRPC_SERVICE_NAME_PLACEHOLDER = (
        "profile_creation.form.grpc_service_name_placeholder"
    )
    PROFILE_CREATION_FORM_LISTEN_PORT_LABEL = "profile_creation.form.listen_port_label"
    PROFILE_CREATION_FORM_LISTEN_PORT_PLACEHOLDER = "profile_creation.form.listen_port_placeholder"
    PROFILE_CREATION_FORM_PREVIEW = "profile_creation.form.preview"
    PROFILE_CREATION_PLANNING_ERROR_TITLE = "profile_creation.planning_error.title"
    PROFILE_CREATION_PLANNING_ERROR_DETAILS = "profile_creation.planning_error.details"
    PROFILE_CREATION_PLANNING_ERROR_SAFETY = "profile_creation.planning_error.safety"
    PROFILE_CREATION_PLAN_TITLE = "profile_creation.plan.title"
    PROFILE_CREATION_PLAN_PROFILE = "profile_creation.plan.profile"
    PROFILE_CREATION_PLAN_PROTOCOL = "profile_creation.plan.protocol"
    PROFILE_CREATION_PLAN_PORT = "profile_creation.plan.port"
    PROFILE_CREATION_PLAN_PORT_AUTOMATIC = "profile_creation.plan.port.automatic"
    PROFILE_CREATION_PLAN_SERVER_ADDRESS = "profile_creation.plan.server_address"
    PROFILE_CREATION_PLAN_TLS_ACME = "profile_creation.plan.tls.acme"
    PROFILE_CREATION_PLAN_TLS_FILES = "profile_creation.plan.tls.files"
    PROFILE_CREATION_PLAN_TLS_KEY = "profile_creation.plan.tls.key"
    PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET = "profile_creation.plan.transport.websocket"
    PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET_HOST = (
        "profile_creation.plan.transport.websocket_host"
    )
    PROFILE_CREATION_PLAN_TRANSPORT_GRPC = "profile_creation.plan.transport.grpc"
    PROFILE_CREATION_PLAN_GENERATED = "profile_creation.plan.generated"
    PROFILE_CREATION_PLAN_GENERATED_SEPARATOR = "profile_creation.plan.generated_separator"
    PROFILE_CREATION_PLAN_GENERATED_UUID = "profile_creation.plan.generated.uuid"
    PROFILE_CREATION_PLAN_GENERATED_REALITY_KEY_PAIR = (
        "profile_creation.plan.generated.reality_key_pair"
    )
    PROFILE_CREATION_PLAN_GENERATED_SERVER_NAME = "profile_creation.plan.generated.server_name"
    PROFILE_CREATION_PLAN_GENERATED_SHADOWSOCKS_KEY = (
        "profile_creation.plan.generated.shadowsocks_key"
    )
    PROFILE_CREATION_PLAN_GENERATED_HYSTERIA2_PASSWORD = (
        "profile_creation.plan.generated.hysteria2_password"
    )
    PROFILE_CREATION_PLAN_GENERATED_TROJAN_PASSWORD = (
        "profile_creation.plan.generated.trojan_password"
    )
    PROFILE_CREATION_PLAN_GENERATED_ANYTLS_PASSWORD = (
        "profile_creation.plan.generated.anytls_password"
    )
    PROFILE_CREATION_PLAN_GENERATED_TUIC_UUID = "profile_creation.plan.generated.tuic_uuid"
    PROFILE_CREATION_PLAN_GENERATED_TUIC_PASSWORD = "profile_creation.plan.generated.tuic_password"
    PROFILE_CREATION_PLAN_GENERATED_VLESS_UUID = "profile_creation.plan.generated.vless_uuid"
    PROFILE_CREATION_PLAN_GENERATED_VMESS_UUID = "profile_creation.plan.generated.vmess_uuid"
    PROFILE_CREATION_PLAN_GENERATED_TLS_CERTIFICATE = (
        "profile_creation.plan.generated.tls_certificate"
    )
    PROFILE_CREATION_PLAN_SAFETY = "profile_creation.plan.safety"
    PROFILE_CREATION_PLAN_SAVE_DRAFT = "profile_creation.plan.save_draft"
    PROFILE_CREATION_DRAFT_TITLE = "profile_creation.draft.title"
    PROFILE_CREATION_DRAFT_STATUS = "profile_creation.draft.status"
    PROFILE_CREATION_DRAFT_SAFETY = "profile_creation.draft.safety"
    PROFILE_CREATION_DRAFT_APPLY = "profile_creation.draft.apply"
    PROFILE_CREATION_DRAFT_RETURN_DASHBOARD = "profile_creation.draft.return_dashboard"
    PROFILE_CREATION_DRAFT_REJECTION_TITLE = "profile_creation.draft.rejection.title"
    PROFILE_CREATION_DRAFT_REJECTION_SAFETY = "profile_creation.draft.rejection.safety"
    PROFILE_CREATION_DRAFT_UNKNOWN_TITLE = "profile_creation.draft.unknown.title"
    PROFILE_CREATION_DRAFT_UNKNOWN_DETAILS = "profile_creation.draft.unknown.details"
    PROFILE_CREATION_DRAFT_UNKNOWN_SAFETY = "profile_creation.draft.unknown.safety"
    PROFILE_CREATION_APPLY_CONFIRM_TITLE = "profile_creation.apply.confirm.title"
    PROFILE_CREATION_APPLY_CONFIRM_PROFILE = "profile_creation.apply.confirm.profile"
    PROFILE_CREATION_APPLY_CONFIRM_WARNING = "profile_creation.apply.confirm.warning"
    PROFILE_CREATION_APPLY_CONFIRM_ACTION = "profile_creation.apply.confirm.action"
    PROFILE_CREATION_APPLY_CONFIRM_PROGRESS = "profile_creation.apply.confirm.progress"
    PROFILE_CREATION_APPLY_RESULT_SUCCESS_TITLE = "profile_creation.apply.result.success.title"
    PROFILE_CREATION_APPLY_RESULT_SUCCESS_REVISION = (
        "profile_creation.apply.result.success.revision"
    )
    PROFILE_CREATION_APPLY_RESULT_SUCCESS_HEALTH = "profile_creation.apply.result.success.health"
    PROFILE_CREATION_APPLY_RESULT_VALIDATION_TITLE = (
        "profile_creation.apply.result.validation.title"
    )
    PROFILE_CREATION_APPLY_RESULT_VALIDATION_SAFETY = (
        "profile_creation.apply.result.validation.safety"
    )
    PROFILE_CREATION_APPLY_RESULT_PRECONDITION_TITLE = (
        "profile_creation.apply.result.precondition.title"
    )
    PROFILE_CREATION_APPLY_RESULT_PRECONDITION_SAFETY = (
        "profile_creation.apply.result.precondition.safety"
    )
    PROFILE_CREATION_APPLY_RESULT_PRECONDITION_DETAILS_FALLBACK = (
        "profile_creation.apply.result.precondition.details_fallback"
    )
    PROFILE_CREATION_APPLY_RESULT_COMMIT_TITLE = "profile_creation.apply.result.commit.title"
    PROFILE_CREATION_APPLY_RESULT_COMMIT_SAFETY = "profile_creation.apply.result.commit.safety"
    PROFILE_CREATION_APPLY_RESULT_COMMIT_DETAILS_FALLBACK = (
        "profile_creation.apply.result.commit.details_fallback"
    )
    PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_TITLE = (
        "profile_creation.apply.result.rolled_back.title"
    )
    PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_SAFETY = (
        "profile_creation.apply.result.rolled_back.safety"
    )
    PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_DETAILS_FALLBACK = (
        "profile_creation.apply.result.rolled_back.details_fallback"
    )
    PROFILE_CREATION_APPLY_RESULT_ROLLBACK_FAILED_TITLE = (
        "profile_creation.apply.result.rollback_failed.title"
    )
    PROFILE_CREATION_APPLY_RESULT_ROLLBACK_FAILED_DETAILS_FALLBACK = (
        "profile_creation.apply.result.rollback_failed.details_fallback"
    )
    PROFILE_CREATION_APPLY_RESULT_RECOVERY_STEP = "profile_creation.apply.result.recovery_step"
    PROFILE_CREATION_APPLY_RESULT_RETURN_DASHBOARD = (
        "profile_creation.apply.result.return_dashboard"
    )
    PROFILE_CREATION_APPLY_OPERATIONAL_TITLE = "profile_creation.apply.operational.title"
    PROFILE_CREATION_APPLY_OPERATIONAL_SAFETY = "profile_creation.apply.operational.safety"
    PROFILE_CREATION_APPLY_UNKNOWN_TITLE = "profile_creation.apply.unknown.title"
    PROFILE_CREATION_APPLY_UNKNOWN_DETAILS = "profile_creation.apply.unknown.details"
    PROFILE_CREATION_APPLY_UNKNOWN_SAFETY = "profile_creation.apply.unknown.safety"
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
        UiText.PROFILE_CLONE_FACET_CONJUNCTION: frozenset({"prefix", "last"}),
        UiText.PROFILE_CLONE_FORM_SOURCE: frozenset({"name"}),
        UiText.PROFILE_CLONE_FORM_COPIED: frozenset({"facets"}),
        UiText.PROFILE_CLONE_FORM_RESET: frozenset({"facets"}),
        UiText.PROFILE_CLONE_REVIEW_SUMMARY: frozenset({"source", "target"}),
        UiText.PROFILE_CLONE_RESULT_SUMMARY: frozenset({"name", "revision"}),
        UiText.PROFILE_RECOMMENDATION_RANKING_TITLE: frozenset({"purpose"}),
        UiText.PROFILE_RECOMMENDATION_PURPOSE_CHOICE_RECOMMENDED: frozenset({"purpose"}),
        UiText.PROFILE_RECOMMENDATION_RANKING_CHOICE_PRIMARY: frozenset({"rank", "label"}),
        UiText.PROFILE_RECOMMENDATION_RANKING_CHOICE: frozenset({"rank", "label"}),
        UiText.PROFILE_RECOMMENDATION_RANKING_REASON: frozenset({"reason"}),
        UiText.PROFILE_RECOMMENDATION_RANKING_TRADEOFF: frozenset({"tradeoff"}),
        UiText.PROFILE_RECOMMENDATION_RANKING_SELECT: frozenset({"label"}),
        UiText.CORE_UPDATE_PLAN_VERSION: frozenset({"version"}),
        UiText.CORE_UPDATE_PLAN_ARCHITECTURE: frozenset({"architecture"}),
        UiText.CORE_UPDATE_PLAN_ASSET: frozenset({"asset"}),
        UiText.CORE_UPDATE_PLAN_SOURCE: frozenset({"source"}),
        UiText.CORE_UPDATE_RESULT_VERSION: frozenset({"version"}),
        UiText.CORE_UPDATE_RESULT_BINARY: frozenset({"path"}),
        UiText.CORE_UPDATE_RESULT_TARGET: frozenset({"target"}),
        UiText.CORE_UPDATE_RESULT_PREVIOUS: frozenset({"target"}),
        UiText.CONFIG_ADOPTION_PLAN_FINGERPRINT: frozenset({"sha256"}),
        UiText.CONFIG_ADOPTION_RESULT_REVISION: frozenset({"revision"}),
        UiText.STATE_RECOVERY_AVAILABLE_BACKUP: frozenset({"revision", "profiles"}),
        UiText.STATE_RECOVERY_CONFIRM_BACKUP: frozenset({"revision", "profiles"}),
        UiText.STATE_RECOVERY_CONFIRM_PRIMARY_FINGERPRINT: frozenset({"sha256"}),
        UiText.STATE_RECOVERY_CONFIRM_BACKUP_FINGERPRINT: frozenset({"sha256"}),
        UiText.STATE_RECOVERY_RESULT_REVISION: frozenset({"revision"}),
        UiText.STATE_RECOVERY_RESULT_PROFILES: frozenset({"profiles"}),
        UiText.STATE_RECOVERY_RESULT_ARCHIVE: frozenset({"path"}),
        UiText.STATE_RECOVERY_UNSUPPORTED_GUIDANCE: frozenset({"schema"}),
        UiText.PROFILE_CREATION_VALIDATION_TLS_CERTIFICATE_PATH_UNTRUSTED: frozenset({"path"}),
        UiText.PROFILE_CREATION_VALIDATION_TLS_KEY_PATH_UNTRUSTED: frozenset({"path"}),
        UiText.PROFILE_CREATION_PLAN_PROFILE: frozenset({"name"}),
        UiText.PROFILE_CREATION_PLAN_PROTOCOL: frozenset({"protocol"}),
        UiText.PROFILE_CREATION_PLAN_PORT: frozenset({"port"}),
        UiText.PROFILE_CREATION_PLAN_SERVER_ADDRESS: frozenset({"address"}),
        UiText.PROFILE_CREATION_PLAN_TLS_ACME: frozenset({"server_name", "email"}),
        UiText.PROFILE_CREATION_PLAN_TLS_FILES: frozenset({"server_name", "certificate_path"}),
        UiText.PROFILE_CREATION_PLAN_TLS_KEY: frozenset({"path"}),
        UiText.PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET: frozenset({"path"}),
        UiText.PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET_HOST: frozenset({"path", "host"}),
        UiText.PROFILE_CREATION_PLAN_TRANSPORT_GRPC: frozenset({"service_name"}),
        UiText.PROFILE_CREATION_PLAN_GENERATED: frozenset({"values"}),
        UiText.PROFILE_CREATION_DRAFT_STATUS: frozenset({"revision"}),
        UiText.PROFILE_CREATION_APPLY_CONFIRM_PROFILE: frozenset({"name"}),
        UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_REVISION: frozenset({"revision"}),
        UiText.PROFILE_CREATION_APPLY_RESULT_RECOVERY_STEP: frozenset({"number", "instruction"}),
        UiText.HOST_DIAGNOSTICS_RECOVERY_STEP: frozenset({"number", "instruction"}),
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
        UiText.HOST_DIAGNOSTICS_TITLE: "主机诊断",
        UiText.HOST_DIAGNOSTICS_SUMMARY_HEALTHY: "sing-box 服务运行正常",
        UiText.HOST_DIAGNOSTICS_SUMMARY_UNHEALTHY: "sing-box 服务未通过健康检查",
        UiText.HOST_DIAGNOSTICS_DETAILS_UNAVAILABLE: "运行时未提供详细信息",
        UiText.HOST_DIAGNOSTICS_RECOVERY_TITLE: "建议的恢复步骤",
        UiText.HOST_DIAGNOSTICS_RECOVERY_STEP: "{number}. {instruction}",
        UiText.HOST_DIAGNOSTICS_RECOVERY_EMPTY: "当前无需恢复操作。",
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
        UiText.PROFILE_CLONE_FORM_TITLE: "以现有配置创建新草案",
        UiText.PROFILE_CLONE_FACET_PROTOCOL: "协议",
        UiText.PROFILE_CLONE_FACET_SERVER_ADDRESS: "服务器地址",
        UiText.PROFILE_CLONE_FACET_TLS_STRATEGY: "TLS 方式",
        UiText.PROFILE_CLONE_FACET_TRANSPORT: "传输方式",
        UiText.PROFILE_CLONE_FACET_CREDENTIALS: "认证凭据",
        UiText.PROFILE_CLONE_FACET_LISTEN_PORT: "监听端口",
        UiText.PROFILE_CLONE_FACET_RUNTIME_STATUS: "运行状态",
        UiText.PROFILE_CLONE_FACET_SEPARATOR: "、",
        UiText.PROFILE_CLONE_FACET_CONJUNCTION: "{prefix}和{last}",
        UiText.PROFILE_CLONE_FORM_SOURCE: "模板：{name}",
        UiText.PROFILE_CLONE_FORM_COPIED: "将复用：{facets}",
        UiText.PROFILE_CLONE_FORM_RESET: "将重置：{facets}，新配置保存为未应用草案。",
        UiText.PROFILE_CLONE_FORM_REVIEW: "审阅草案",
        UiText.PROFILE_CLONE_FORM_EDIT: "修改名称",
        UiText.PROFILE_CLONE_FORM_CONFIRM: "确认创建草案",
        UiText.PROFILE_CLONE_FORM_RETURN_LIST: "返回配置列表",
        UiText.PROFILE_CLONE_REVIEW_TITLE: "确认模板草案",
        UiText.PROFILE_CLONE_REVIEW_SUMMARY: "{source} → {target}",
        UiText.PROFILE_CLONE_IN_PROGRESS: "操作已确认，正在创建新草案。完成前无法返回。",
        UiText.PROFILE_CLONE_STALE: (
            "desired state 已变化。请修改名称后重新审阅，或返回配置详情重新开始。"
        ),
        UiText.PROFILE_CLONE_RESULT_TITLE: "草案已创建",
        UiText.PROFILE_CLONE_RESULT_SUMMARY: ("{name} · desired state revision {revision}"),
        UiText.PROFILE_CLONE_PLANNING_TITLE: "无法准备配置模板",
        UiText.PROFILE_CLONE_PLANNING_DETAILS: (
            "读取配置模板计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_CLONE_PLANNING_SAFETY: (
            "尚未创建草案。请返回配置列表，重新打开详情后再试。"
        ),
        UiText.PROFILE_CLONE_OPERATIONAL_TITLE: "无法确认模板草案结果",
        UiText.PROFILE_CLONE_OPERATIONAL_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_CLONE_OPERATIONAL_SAFETY: (
            "该流程不修改服务器配置或服务。desired state 是否已创建草案未知。"
            "请先返回配置列表检查，再决定是否重试。"
        ),
        UiText.PROFILE_RECOMMENDATION_PURPOSE_TITLE: "你主要想优化什么?",
        UiText.PROFILE_RECOMMENDATION_PURPOSE_GUIDANCE: (
            "先按使用目的缩小选择范围; 推荐会同时说明限制，不会自动应用配置。"
        ),
        UiText.PROFILE_RECOMMENDATION_PURPOSE_CHOICE_RECOMMENDED: ("{purpose} · 推荐"),
        UiText.PROFILE_RECOMMENDATION_PURPOSE_CHOOSE_DIRECTLY: "直接选择协议 · 高级",
        UiText.PROFILE_RECOMMENDATION_PURPOSE_GENERAL: "通用搭建",
        UiText.PROFILE_RECOMMENDATION_PURPOSE_LOW_LATENCY: "移动网络与低延迟",
        UiText.PROFILE_RECOMMENDATION_PURPOSE_RESTRICTED_NETWORK: "受限网络中的连接选择",
        UiText.PROFILE_RECOMMENDATION_PURPOSE_COMPATIBILITY: "兼容既有客户端",
        UiText.PROFILE_RECOMMENDATION_VARIANT_VLESS_REALITY: "VLESS Reality",
        UiText.PROFILE_RECOMMENDATION_VARIANT_SHADOWSOCKS: "Shadowsocks 2022",
        UiText.PROFILE_RECOMMENDATION_VARIANT_HYSTERIA2: "Hysteria2",
        UiText.PROFILE_RECOMMENDATION_VARIANT_TROJAN: "Trojan",
        UiText.PROFILE_RECOMMENDATION_VARIANT_ANYTLS: "AnyTLS",
        UiText.PROFILE_RECOMMENDATION_VARIANT_TUIC: "TUIC",
        UiText.PROFILE_RECOMMENDATION_VARIANT_VLESS_WEBSOCKET: "VLESS TLS · WebSocket",
        UiText.PROFILE_RECOMMENDATION_VARIANT_VLESS_GRPC: "VLESS TLS · gRPC",
        UiText.PROFILE_RECOMMENDATION_VARIANT_VMESS_WEBSOCKET: "VMess TLS · WebSocket",
        UiText.PROFILE_RECOMMENDATION_VARIANT_VMESS_GRPC: "VMess TLS · gRPC",
        UiText.PROFILE_RECOMMENDATION_RANKING_TITLE: "{purpose}的推荐顺序",
        UiText.PROFILE_RECOMMENDATION_RANKING_CAVEAT: (
            "推荐只帮助缩小选择，不承诺连通性或适用于所有网络。"
        ),
        UiText.PROFILE_RECOMMENDATION_RANKING_CHOICE_PRIMARY: ("{rank}. {label} · 首选"),
        UiText.PROFILE_RECOMMENDATION_RANKING_CHOICE: "{rank}. {label}",
        UiText.PROFILE_RECOMMENDATION_RANKING_REASON: "适合原因：{reason}",
        UiText.PROFILE_RECOMMENDATION_RANKING_TRADEOFF: "需要注意：{tradeoff}",
        UiText.PROFILE_RECOMMENDATION_RANKING_SELECT: "使用 {label}",
        UiText.PROFILE_RECOMMENDATION_ERROR_TITLE: "暂时无法生成协议建议",
        UiText.PROFILE_RECOMMENDATION_ERROR_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_RECOMMENDATION_ERROR_SAFETY: (
            "尚未创建或修改任何配置。请返回后重试，或使用“直接选择协议”的高级入口。"
        ),
        UiText.PROFILE_RECOMMENDATION_ERROR_CHOOSE_DIRECTLY: "直接选择协议 · 高级",
        UiText.PROFILE_RECOMMENDATION_DIRECT_TITLE: "直接选择协议",
        UiText.PROFILE_RECOMMENDATION_DIRECT_GUIDANCE: (
            "这里不再排序; 请只选择你确认客户端和网络都支持的协议。"
        ),
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_REALITY: "VLESS Reality",
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_SHADOWSOCKS: ("Shadowsocks 2022 · 简洁稳定"),
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_HYSTERIA2: "Hysteria2 · 移动网络",
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_TROJAN: "Trojan · TLS 兼容",
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_ANYTLS: ("AnyTLS · 抗 TLS 嵌套指纹"),
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_TUIC: "TUIC · QUIC 低延迟",
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_WEBSOCKET: ("VLESS TLS · WebSocket/CDN"),
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VLESS_GRPC: "VLESS TLS · gRPC",
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VMESS_WEBSOCKET: ("VMess TLS · 旧客户端兼容"),
        UiText.PROFILE_RECOMMENDATION_DIRECT_CHOICE_VMESS_GRPC: ("VMess TLS · gRPC 兼容"),
        UiText.PROFILE_RECOMMENDATION_GENERAL_VLESS_REALITY_REASON: (
            "无需管理自有 TLS 证书，向导所需信息最少"
        ),
        UiText.PROFILE_RECOMMENDATION_GENERAL_VLESS_REALITY_TRADEOFF: (
            "客户端必须支持 VLESS Reality"
        ),
        UiText.PROFILE_RECOMMENDATION_GENERAL_SHADOWSOCKS_REASON: (
            "配置字段少，并使用官方推荐的 AEAD 2022 方法"
        ),
        UiText.PROFILE_RECOMMENDATION_GENERAL_SHADOWSOCKS_TRADEOFF: (
            "客户端必须支持 Shadowsocks 2022"
        ),
        UiText.PROFILE_RECOMMENDATION_GENERAL_TROJAN_REASON: (
            "使用标准 TLS 证书路径，适合作为常规 TLS 方案"
        ),
        UiText.PROFILE_RECOMMENDATION_GENERAL_TROJAN_TRADEOFF: ("需要可解析的域名和可用证书"),
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_HYSTERIA2_REASON: (
            "QUIC 与专用拥塞控制适合存在丢包的移动链路"
        ),
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_HYSTERIA2_TRADEOFF: (
            "必须能稳定使用 UDP; UDP 代理流量特征也更明显"
        ),
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_TUIC_REASON: (
            "QUIC 传输支持多路复用和可选拥塞控制策略"
        ),
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_TUIC_TRADEOFF: (
            "需要 UDP、TLS 和支持 TUIC 的客户端"
        ),
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_VLESS_REALITY_REASON: (
            "不依赖 UDP，可作为移动网络中的 TCP 备选"
        ),
        UiText.PROFILE_RECOMMENDATION_LOW_LATENCY_VLESS_REALITY_TRADEOFF: (
            "高丢包链路没有 Hysteria2 的专用拥塞控制"
        ),
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_REALITY_REASON: (
            "Reality 使用 TCP，且不要求管理自有 TLS 证书"
        ),
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_REALITY_TRADEOFF: (
            "不保证适用于所有受限网络; 客户端必须支持 Reality"
        ),
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_ANYTLS_REASON: (
            "TLS、填充和多路复用组合提供另一种 TCP 方案"
        ),
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_ANYTLS_TRADEOFF: (
            "需要域名、证书和支持 AnyTLS 的较新客户端"
        ),
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_WEBSOCKET_REASON: (
            "TLS WebSocket 适合明确需要 HTTP 兼容传输的场景"
        ),
        UiText.PROFILE_RECOMMENDATION_RESTRICTED_VLESS_WEBSOCKET_TRADEOFF: (
            "配置项更多，且同样不保证适用于所有受限网络"
        ),
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_TROJAN_REASON: (
            "密码认证与标准 TLS 组合便于对照既有 TLS 客户端"
        ),
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_TROJAN_TRADEOFF: ("需要可解析的域名和可用证书"),
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_SHADOWSOCKS_REASON: (
            "协议认知广，manager 使用官方推荐的 AEAD 2022 方法"
        ),
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_SHADOWSOCKS_TRADEOFF: (
            "旧客户端可能不支持 Shadowsocks 2022"
        ),
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_VMESS_WEBSOCKET_REASON: (
            "仅在需要兼容既有 VMess 客户端时保留"
        ),
        UiText.PROFILE_RECOMMENDATION_COMPATIBILITY_VMESS_WEBSOCKET_TRADEOFF: (
            "新部署不默认推荐，并需要 TLS 与 WebSocket"
        ),
        UiText.CORE_UPDATE_FORM_TITLE: "安装或升级 sing-box 核心",
        UiText.CORE_UPDATE_OPEN: "安装或升级 sing-box 核心",
        UiText.CORE_UPDATE_FORM_GUIDANCE: "只接受官方 immutable release 的精确版本。",
        UiText.CORE_UPDATE_FORM_VERSION_LABEL: "精确版本",
        UiText.CORE_UPDATE_FORM_VERSION_PLACEHOLDER: "精确版本，例如 1.14.0-alpha.45",
        UiText.CORE_UPDATE_FORM_ARCHITECTURE_LABEL: "服务器架构",
        UiText.CORE_UPDATE_FORM_ARCHITECTURE_AMD64: "x86-64 (amd64)",
        UiText.CORE_UPDATE_FORM_ARCHITECTURE_ARM64: "ARM64 (arm64)",
        UiText.CORE_UPDATE_FORM_PRERELEASE_CONSENT: "我接受预发布版本的兼容性风险",
        UiText.CORE_UPDATE_FORM_PREVIEW: "预览核心更新计划",
        UiText.CORE_UPDATE_FORM_ERROR_INVALID_VERSION: (
            "版本格式无效。请输入完整版本，例如 1.14.0 或 1.14.0-alpha.45。"
        ),
        UiText.CORE_UPDATE_FORM_ERROR_ARCHITECTURE: "请选择服务器架构。",
        UiText.CORE_UPDATE_FORM_ERROR_PRERELEASE_CONSENT: (
            "该版本属于预发布版本。勾选兼容性风险确认后再预览计划。"
        ),
        UiText.CORE_UPDATE_PLAN_TITLE: "确认核心更新计划",
        UiText.CORE_UPDATE_PLAN_VERSION: "版本：{version}",
        UiText.CORE_UPDATE_PLAN_ARCHITECTURE: "架构：{architecture}",
        UiText.CORE_UPDATE_PLAN_ASSET: "发行资产：{asset}",
        UiText.CORE_UPDATE_PLAN_SOURCE: "来源：{source}",
        UiText.CORE_UPDATE_PLAN_WARNING_PRERELEASE: ("这是预发布核心; 仅在接受兼容性风险时继续。"),
        UiText.CORE_UPDATE_PLAN_SAFETY: ("当前仅预览; 尚未下载文件，也不会修改服务器。"),
        UiText.CORE_UPDATE_PLAN_CONFIRM: "确认下载并激活",
        UiText.CORE_UPDATE_PLAN_PROGRESS: ("操作已确认，正在下载、校验并激活。完成前无法返回。"),
        UiText.CORE_UPDATE_RESULT_TITLE: "sing-box 核心已激活",
        UiText.CORE_UPDATE_RESULT_VERSION: "版本：{version}",
        UiText.CORE_UPDATE_RESULT_BINARY: "当前二进制：{path}",
        UiText.CORE_UPDATE_RESULT_TARGET: "激活目标：{target}",
        UiText.CORE_UPDATE_RESULT_PREVIOUS: "上一个激活目标：{target}",
        UiText.CORE_UPDATE_RESULT_PREVIOUS_NONE: "无",
        UiText.CORE_UPDATE_PLANNING_ERROR_TITLE: "无法准备核心更新计划",
        UiText.CORE_UPDATE_PLANNING_ERROR_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.CORE_UPDATE_PLANNING_ERROR_SAFETY: (
            "尚未下载发行资产，也未请求核心激活。请重新打开核心更新页后再试。"
        ),
        UiText.CORE_UPDATE_ERROR_UNKNOWN_TITLE: "无法确认核心激活结果",
        UiText.CORE_UPDATE_ERROR_ACQUISITION_TITLE: "核心下载或校验失败",
        UiText.CORE_UPDATE_ERROR_UNKNOWN_SAFETY: (
            "请检查 current 链接、helper 日志和 sing-box 版本，再决定是否重试。"
        ),
        UiText.CORE_UPDATE_ERROR_ACQUISITION_SAFETY: ("尚未请求特权激活，当前核心保持不变。"),
        UiText.CORE_UPDATE_ERROR_UNEXPECTED_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.CONFIG_ADOPTION_PLAN_LOADING: "正在检查现有配置…",
        UiText.CONFIG_ADOPTION_PLAN_TITLE: "确认现有配置接管计划",
        UiText.CONFIG_ADOPTION_PLAN_FINGERPRINT: "当前配置 SHA-256：{sha256}",
        UiText.CONFIG_ADOPTION_PLAN_SAFETY: (
            "接管不会修改服务器，也不会把现有 JSON 导入为 profile。"
        ),
        UiText.CONFIG_ADOPTION_PLAN_CONFIRM: "确认接管此配置",
        UiText.CONFIG_ADOPTION_PLAN_PROGRESS: (
            "操作已确认，正在重新核对并记录配置指纹。完成前无法返回。"
        ),
        UiText.CONFIG_ADOPTION_RESULT_TITLE: "现有配置已被记录为替换前置条件",
        UiText.CONFIG_ADOPTION_RESULT_REVISION: "desired state revision {revision}",
        UiText.CONFIG_ADOPTION_RESULT_SAFETY: (
            "服务器配置没有改变。下一次应用会先核对已记录指纹。"
        ),
        UiText.CONFIG_ADOPTION_RESULT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.CONFIG_ADOPTION_PLANNING_ERROR_TITLE: "无法检查现有配置",
        UiText.CONFIG_ADOPTION_PLANNING_ERROR_DETAILS: (
            "读取配置接管计划时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.CONFIG_ADOPTION_PLANNING_ERROR_SAFETY: (
            "尚未记录 replacement precondition，也未修改服务器配置。请重新打开诊断或仪表盘后再试。"
        ),
        UiText.CONFIG_ADOPTION_UNKNOWN_TITLE: "无法确认配置接管结果",
        UiText.CONFIG_ADOPTION_UNKNOWN_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.CONFIG_ADOPTION_UNKNOWN_SAFETY: (
            "此流程没有修改服务器配置。desired state 是否已记录 replacement precondition 未知。"
            "请先通过诊断中心重新检查 live configuration identity，再决定是否重试。"
        ),
        UiText.CONFIG_ADOPTION_ERROR_TITLE: "无法接管现有配置",
        UiText.CONFIG_ADOPTION_ERROR_SAFETY: (
            "服务器配置和 desired state 均未改变。请重新检查后再试。"
        ),
        UiText.STATE_RECOVERY_AVAILABLE_TITLE: "desired state 无法读取",
        UiText.STATE_RECOVERY_AVAILABLE_BACKUP: (
            "可恢复备份：revision {revision} · {profiles} 个配置"
        ),
        UiText.STATE_RECOVERY_AVAILABLE_GUIDANCE: (
            "恢复前会再次核对主文件和备份指纹，损坏原文件会被完整保留。"
        ),
        UiText.STATE_RECOVERY_AVAILABLE_REVIEW: "审阅恢复计划",
        UiText.STATE_RECOVERY_CONFIRM_TITLE: "确认恢复 desired state",
        UiText.STATE_RECOVERY_CONFIRM_BACKUP: ("备份：revision {revision} · {profiles} 个配置"),
        UiText.STATE_RECOVERY_CONFIRM_PRIMARY_FINGERPRINT: ("待替换主文件 SHA-256：{sha256}"),
        UiText.STATE_RECOVERY_CONFIRM_BACKUP_FINGERPRINT: ("待恢复备份 SHA-256：{sha256}"),
        UiText.STATE_RECOVERY_CONFIRM_SAFETY: (
            "将用已审阅备份替换损坏主文件，损坏原文件会被完整归档。"
        ),
        UiText.STATE_RECOVERY_CONFIRM_ACTION: "确认并恢复",
        UiText.STATE_RECOVERY_CONFIRM_PROGRESS: (
            "操作已确认，正在恢复 desired state。完成前无法返回。"
        ),
        UiText.STATE_RECOVERY_RESULT_TITLE: "desired state 已恢复",
        UiText.STATE_RECOVERY_RESULT_REVISION: "恢复至 revision {revision}",
        UiText.STATE_RECOVERY_RESULT_PROFILES: "恢复配置数：{profiles}",
        UiText.STATE_RECOVERY_RESULT_ARCHIVE: "损坏主文件归档：{path}",
        UiText.STATE_RECOVERY_RESULT_SAFETY: (
            "已验证的备份现在是 manager desired state，live configuration 未被修改。"
        ),
        UiText.STATE_RECOVERY_RESULT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.STATE_RECOVERY_REJECTION_TITLE: "无法执行 desired state 恢复",
        UiText.STATE_RECOVERY_REJECTION_SAFETY: (
            "未替换 desired state。审阅证据已失效，请返回并重新检查后再决定是否恢复。"
        ),
        UiText.STATE_RECOVERY_UNKNOWN_TITLE: "无法确认 desired state 恢复结果",
        UiText.STATE_RECOVERY_UNKNOWN_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.STATE_RECOVERY_UNKNOWN_SAFETY: (
            "主文件、备份和损坏文件归档的结果均未知。"
            "请先只读检查这些文件的 SHA-256 和 revision，不要直接重试。"
        ),
        UiText.STATE_RECOVERY_INSPECTION_ERROR_TITLE: "无法检查 desired state",
        UiText.STATE_RECOVERY_INSPECTION_ERROR_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.STATE_RECOVERY_INSPECTION_ERROR_SAFETY: (
            "当前会话不会写入 desired state。请修复文件访问问题后重新启动 manager。"
        ),
        UiText.STATE_RECOVERY_UNSUPPORTED_TITLE: "desired state 版本高于当前管理器",
        UiText.STATE_RECOVERY_UNSUPPORTED_GUIDANCE: (
            "检测到 schema {schema}。请使用兼容版本的管理器打开，当前版本不会覆盖该文件。"
        ),
        UiText.STATE_RECOVERY_UNAVAILABLE_TITLE: "desired state 无法读取",
        UiText.STATE_RECOVERY_UNAVAILABLE_GUIDANCE: (
            "没有找到可验证的备份。当前版本不会覆盖主文件，请从外部备份恢复或检查文件权限。"
        ),
        UiText.STATE_RECOVERY_PLANNING_ERROR_TITLE: "无法重新检查恢复计划",
        UiText.STATE_RECOVERY_PLANNING_ERROR_DETAILS: (
            "读取 desired state 恢复证据时发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.STATE_RECOVERY_PLANNING_ERROR_SAFETY: (
            "尚未归档或替换任何 desired state 文件。请修复文件访问问题并重新启动 manager 后再审阅。"
        ),
        UiText.PROFILE_CREATION_VALIDATION_PROFILE_NAME_REQUIRED: "请输入配置名称",
        UiText.PROFILE_CREATION_VALIDATION_LISTEN_PORT_OUT_OF_RANGE: ("端口必须在 1 到 65535 之间"),
        UiText.PROFILE_CREATION_VALIDATION_TLS_NOT_SUPPORTED: ("该协议不使用 TLS 证书选项"),
        UiText.PROFILE_CREATION_VALIDATION_TLS_REQUIRED: "请选择 TLS 证书方式",
        UiText.PROFILE_CREATION_VALIDATION_TLS_SERVER_NAME_REQUIRED: "请输入证书域名",
        UiText.PROFILE_CREATION_VALIDATION_TLS_EMAIL_REQUIRED: "请输入 ACME 联系邮箱",
        UiText.PROFILE_CREATION_VALIDATION_TLS_CERTIFICATE_PATH_UNTRUSTED: (
            "证书文件必须位于 {path}"
        ),
        UiText.PROFILE_CREATION_VALIDATION_TLS_KEY_PATH_UNTRUSTED: ("私钥文件必须位于 {path}"),
        UiText.PROFILE_CREATION_VALIDATION_TRANSPORT_NOT_SUPPORTED: ("该协议不使用传输选项"),
        UiText.PROFILE_CREATION_VALIDATION_TRANSPORT_REQUIRED: "请选择传输方式",
        UiText.PROFILE_CREATION_VALIDATION_WEBSOCKET_PATH_INVALID: ("WebSocket 路径必须以 / 开头"),
        UiText.PROFILE_CREATION_VALIDATION_GRPC_SERVICE_NAME_REQUIRED: ("请输入 gRPC 服务名"),
        UiText.PROFILE_CREATION_FORM_TITLE_VLESS_REALITY: "配置 VLESS Reality",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_VLESS_REALITY: (
            "适合大多数网络环境。UUID、密钥和兼容站点将自动生成。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_SHADOWSOCKS: "配置 Shadowsocks 2022",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_SHADOWSOCKS: (
            "无需 TLS，适合需要简洁配置的场景。安全密钥将自动生成。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_HYSTERIA2: "配置 Hysteria2",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_HYSTERIA2: (
            "适合移动网络。认证密码自动生成，TLS 证书通过 ACME 申请。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_TROJAN: "配置 Trojan",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_TROJAN: (
            "基于 TLS 的兼容协议。认证密码自动生成，证书通过 ACME 申请。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_ANYTLS: "配置 AnyTLS",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_ANYTLS: (
            "用于缓解 TLS 嵌套指纹。认证密码自动生成，证书通过 ACME 申请。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_TUIC: "配置 TUIC",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_TUIC: (
            "基于 QUIC 的低延迟协议。默认关闭可重放的 0-RTT。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_VLESS_WEBSOCKET: ("配置 VLESS TLS WebSocket"),
        UiText.PROFILE_CREATION_FORM_GUIDANCE_VLESS_WEBSOCKET: (
            "适合需要 WebSocket 或 CDN 兼容入口的场景。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_VLESS_GRPC: "配置 VLESS TLS gRPC",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_VLESS_GRPC: ("适合需要标准 gRPC 传输兼容性的场景。"),
        UiText.PROFILE_CREATION_FORM_TITLE_VMESS_WEBSOCKET: ("配置 VMess TLS WebSocket"),
        UiText.PROFILE_CREATION_FORM_GUIDANCE_VMESS_WEBSOCKET: (
            "仅用于旧客户端兼容，使用 alterId 0 和现代 UUID 认证。"
        ),
        UiText.PROFILE_CREATION_FORM_TITLE_VMESS_GRPC: "配置 VMess TLS gRPC",
        UiText.PROFILE_CREATION_FORM_GUIDANCE_VMESS_GRPC: (
            "旧客户端兼容的 VMess，使用标准 gRPC 传输。"
        ),
        UiText.PROFILE_CREATION_FORM_PROFILE_NAME_LABEL: "配置名称",
        UiText.PROFILE_CREATION_FORM_PROFILE_NAME_PLACEHOLDER: "例如：手机",
        UiText.PROFILE_CREATION_FORM_SERVER_ADDRESS_LABEL: "服务器地址",
        UiText.PROFILE_CREATION_FORM_SERVER_ADDRESS_PLACEHOLDER: (
            "例如：vpn.example.com 或 203.0.113.10"
        ),
        UiText.PROFILE_CREATION_FORM_TLS_SERVER_NAME_LABEL: "TLS 证书域名",
        UiText.PROFILE_CREATION_FORM_TLS_SERVER_NAME_PLACEHOLDER: ("例如：vpn.example.com"),
        UiText.PROFILE_CREATION_FORM_TLS_STRATEGY_LABEL: "TLS 证书方式",
        UiText.PROFILE_CREATION_FORM_TLS_STRATEGY_ACME: "自动申请 ACME · 推荐",
        UiText.PROFILE_CREATION_FORM_TLS_STRATEGY_FILES: ("已有 root 管理的证书文件 · 高级"),
        UiText.PROFILE_CREATION_FORM_TLS_EMAIL_LABEL: "ACME 联系邮箱",
        UiText.PROFILE_CREATION_FORM_TLS_EMAIL_PLACEHOLDER: ("例如：operator@example.com"),
        UiText.PROFILE_CREATION_FORM_TLS_CERTIFICATE_PATH_LABEL: "证书文件",
        UiText.PROFILE_CREATION_FORM_TLS_CERTIFICATE_PATH_PLACEHOLDER: (
            "/etc/sing-box-manager/tls/server.crt"
        ),
        UiText.PROFILE_CREATION_FORM_TLS_KEY_PATH_LABEL: "私钥文件",
        UiText.PROFILE_CREATION_FORM_TLS_KEY_PATH_PLACEHOLDER: (
            "/etc/sing-box-manager/tls/server.key"
        ),
        UiText.PROFILE_CREATION_FORM_WEBSOCKET_PATH_LABEL: "WebSocket 路径",
        UiText.PROFILE_CREATION_FORM_WEBSOCKET_PATH_PLACEHOLDER: "例如：/proxy",
        UiText.PROFILE_CREATION_FORM_WEBSOCKET_HOST_LABEL: "WebSocket Host (可选)",
        UiText.PROFILE_CREATION_FORM_WEBSOCKET_HOST_PLACEHOLDER: ("例如：vpn.example.com"),
        UiText.PROFILE_CREATION_FORM_GRPC_SERVICE_NAME_LABEL: "gRPC 服务名",
        UiText.PROFILE_CREATION_FORM_GRPC_SERVICE_NAME_PLACEHOLDER: ("例如：ProxyService"),
        UiText.PROFILE_CREATION_FORM_LISTEN_PORT_LABEL: "监听端口",
        UiText.PROFILE_CREATION_FORM_LISTEN_PORT_PLACEHOLDER: "留空自动选择",
        UiText.PROFILE_CREATION_FORM_PREVIEW: "预览变更计划",
        UiText.PROFILE_CREATION_PLANNING_ERROR_TITLE: "无法准备配置计划",
        UiText.PROFILE_CREATION_PLANNING_ERROR_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_CREATION_PLANNING_ERROR_SAFETY: (
            "尚未创建草案，也未修改服务器。请返回后重新填写，或先检查 desired state 文件访问。"
        ),
        UiText.PROFILE_CREATION_PLAN_TITLE: "确认变更计划",
        UiText.PROFILE_CREATION_PLAN_PROFILE: "配置：{name}",
        UiText.PROFILE_CREATION_PLAN_PROTOCOL: "协议：{protocol}",
        UiText.PROFILE_CREATION_PLAN_PORT: "监听端口：{port}",
        UiText.PROFILE_CREATION_PLAN_PORT_AUTOMATIC: "自动选择可用端口",
        UiText.PROFILE_CREATION_PLAN_SERVER_ADDRESS: "服务器地址：{address}",
        UiText.PROFILE_CREATION_PLAN_TLS_ACME: ("TLS：ACME · {server_name} · {email}"),
        UiText.PROFILE_CREATION_PLAN_TLS_FILES: (
            "TLS：已有证书 · {server_name} · {certificate_path}"
        ),
        UiText.PROFILE_CREATION_PLAN_TLS_KEY: "私钥：{path}",
        UiText.PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET: ("传输：WebSocket · {path}"),
        UiText.PROFILE_CREATION_PLAN_TRANSPORT_WEBSOCKET_HOST: (
            "传输：WebSocket · {path} · Host {host}"
        ),
        UiText.PROFILE_CREATION_PLAN_TRANSPORT_GRPC: ("传输：gRPC · {service_name}"),
        UiText.PROFILE_CREATION_PLAN_GENERATED: "自动生成：{values}",
        UiText.PROFILE_CREATION_PLAN_GENERATED_SEPARATOR: "、",
        UiText.PROFILE_CREATION_PLAN_GENERATED_UUID: "UUID",
        UiText.PROFILE_CREATION_PLAN_GENERATED_REALITY_KEY_PAIR: "Reality 密钥",
        UiText.PROFILE_CREATION_PLAN_GENERATED_SERVER_NAME: "兼容站点",
        UiText.PROFILE_CREATION_PLAN_GENERATED_SHADOWSOCKS_KEY: ("Shadowsocks 2022 安全密钥"),
        UiText.PROFILE_CREATION_PLAN_GENERATED_HYSTERIA2_PASSWORD: ("Hysteria2 认证密码"),
        UiText.PROFILE_CREATION_PLAN_GENERATED_TROJAN_PASSWORD: "Trojan 认证密码",
        UiText.PROFILE_CREATION_PLAN_GENERATED_ANYTLS_PASSWORD: "AnyTLS 认证密码",
        UiText.PROFILE_CREATION_PLAN_GENERATED_TUIC_UUID: "TUIC UUID",
        UiText.PROFILE_CREATION_PLAN_GENERATED_TUIC_PASSWORD: "TUIC 认证密码",
        UiText.PROFILE_CREATION_PLAN_GENERATED_VLESS_UUID: "VLESS UUID",
        UiText.PROFILE_CREATION_PLAN_GENERATED_VMESS_UUID: "VMess UUID",
        UiText.PROFILE_CREATION_PLAN_GENERATED_TLS_CERTIFICATE: "TLS 证书",
        UiText.PROFILE_CREATION_PLAN_SAFETY: "当前仅预览，不会修改服务器。",
        UiText.PROFILE_CREATION_PLAN_SAVE_DRAFT: "保存为草案",
        UiText.PROFILE_CREATION_DRAFT_TITLE: "草案已保存",
        UiText.PROFILE_CREATION_DRAFT_STATUS: "草案 · revision {revision}",
        UiText.PROFILE_CREATION_DRAFT_SAFETY: "尚未修改服务器。",
        UiText.PROFILE_CREATION_DRAFT_APPLY: "应用到服务器",
        UiText.PROFILE_CREATION_DRAFT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.PROFILE_CREATION_DRAFT_REJECTION_TITLE: "无法保存已审阅草案",
        UiText.PROFILE_CREATION_DRAFT_REJECTION_SAFETY: (
            "desired state 未改变。计划 revision 已过期，请返回 Dashboard 后重新开始。"
        ),
        UiText.PROFILE_CREATION_DRAFT_UNKNOWN_TITLE: "无法确认草案保存结果",
        UiText.PROFILE_CREATION_DRAFT_UNKNOWN_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_CREATION_DRAFT_UNKNOWN_SAFETY: (
            "服务器未被修改，但 desired state 是否已写入草案未知。"
            "请返回 Dashboard 并重新读取 Profiles，确认后再决定下一步。"
        ),
        UiText.PROFILE_CREATION_APPLY_CONFIRM_TITLE: "即将修改服务器",
        UiText.PROFILE_CREATION_APPLY_CONFIRM_PROFILE: "配置：{name}",
        UiText.PROFILE_CREATION_APPLY_CONFIRM_WARNING: (
            "将写入 sing-box 配置并刷新服务，失败时自动回滚。"
        ),
        UiText.PROFILE_CREATION_APPLY_CONFIRM_ACTION: "确认并应用",
        UiText.PROFILE_CREATION_APPLY_CONFIRM_PROGRESS: (
            "操作已确认，正在校验、提交并检查服务健康状态。完成前无法返回。"
        ),
        UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_TITLE: "应用成功",
        UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_REVISION: ("已提交 revision {revision}"),
        UiText.PROFILE_CREATION_APPLY_RESULT_SUCCESS_HEALTH: (
            "sing-box 配置已生效，服务运行正常。"
        ),
        UiText.PROFILE_CREATION_APPLY_RESULT_VALIDATION_TITLE: "配置校验失败",
        UiText.PROFILE_CREATION_APPLY_RESULT_VALIDATION_SAFETY: ("原有配置和服务均未改变。"),
        UiText.PROFILE_CREATION_APPLY_RESULT_PRECONDITION_TITLE: "服务器配置已变化",
        UiText.PROFILE_CREATION_APPLY_RESULT_PRECONDITION_SAFETY: (
            "本次尚未写入配置，请重新检查并确认接管状态。"
        ),
        UiText.PROFILE_CREATION_APPLY_RESULT_PRECONDITION_DETAILS_FALLBACK: (
            "服务器配置不再符合已确认的接管前置条件"
        ),
        UiText.PROFILE_CREATION_APPLY_RESULT_COMMIT_TITLE: "无法写入配置",
        UiText.PROFILE_CREATION_APPLY_RESULT_COMMIT_SAFETY: ("尚未刷新服务，原有配置保持不变。"),
        UiText.PROFILE_CREATION_APPLY_RESULT_COMMIT_DETAILS_FALLBACK: "配置提交失败",
        UiText.PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_TITLE: ("应用失败，已自动回滚"),
        UiText.PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_SAFETY: ("原有配置和服务已恢复。"),
        UiText.PROFILE_CREATION_APPLY_RESULT_ROLLED_BACK_DETAILS_FALLBACK: ("旧配置已恢复。"),
        UiText.PROFILE_CREATION_APPLY_RESULT_ROLLBACK_FAILED_TITLE: ("回滚未完成，需要人工恢复"),
        UiText.PROFILE_CREATION_APPLY_RESULT_ROLLBACK_FAILED_DETAILS_FALLBACK: ("回滚状态未知"),
        UiText.PROFILE_CREATION_APPLY_RESULT_RECOVERY_STEP: ("{number}. {instruction}"),
        UiText.PROFILE_CREATION_APPLY_RESULT_RETURN_DASHBOARD: "返回仪表盘",
        UiText.PROFILE_CREATION_APPLY_OPERATIONAL_TITLE: "无法确认服务器变更结果",
        UiText.PROFILE_CREATION_APPLY_OPERATIONAL_SAFETY: (
            "desired state 未提交。请先检查 sing-box 服务和 helper 日志，再决定是否重试。"
        ),
        UiText.PROFILE_CREATION_APPLY_UNKNOWN_TITLE: "无法确认配置应用结果",
        UiText.PROFILE_CREATION_APPLY_UNKNOWN_DETAILS: (
            "发生意外错误。底层错误未显示，以避免泄露敏感信息。"
        ),
        UiText.PROFILE_CREATION_APPLY_UNKNOWN_SAFETY: (
            "服务器配置、服务和 desired state 的结果均未知。"
            "请先检查配置身份、服务状态和应用历史，再决定是否重试。"
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
