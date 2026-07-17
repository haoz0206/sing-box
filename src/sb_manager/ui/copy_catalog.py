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
