"""Aggregate read-only manager and host evidence into actionable diagnostics."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnostics,
)
from sb_manager.application.host_readiness import (
    HostReadiness,
    HostReadinessItemCode,
    ReadinessState,
)
from sb_manager.domain.installation import ManagedInstallation, ProfileStatus
from sb_manager.seams.config_target import (
    ConfigTargetInspectionError,
    ConfigurationTargetInspector,
)
from sb_manager.seams.state_store import StateStore


class DiagnosticCondition(str, Enum):
    """Operator priority shared by every diagnostics-center check."""

    HEALTHY = "healthy"
    ATTENTION = "attention"
    ACTION_REQUIRED = "action-required"


class DiagnosticAction(str, Enum):
    """Typed navigation that can safely follow one diagnostic recommendation."""

    REVIEW_CONFIG_ADOPTION = "review-config-adoption"
    MANAGE_CORE = "manage-core"


class DiagnosticCode(str, Enum):
    """Stable identities for checks presented by the diagnostics center."""

    DESIRED_STATE = "desired-state"
    LIVE_CONFIGURATION = "live-configuration"
    CONFIG_TARGET = "config-target"
    PRIVILEGED_HELPER = "privileged-helper"
    CORE = "core"
    HOST_READINESS = "host-readiness"
    RUNTIME = "runtime"


@dataclass(frozen=True, slots=True)
class DiagnosticItem:
    """One typed observation with enough guidance for the operator's next step."""

    code: DiagnosticCode
    condition: DiagnosticCondition
    title: str
    summary: str
    diagnostics: str
    guidance: str
    action: DiagnosticAction | None = None


@dataclass(frozen=True, slots=True)
class DiagnosticsCenterReport:
    """Complete read-only diagnostics evidence behind one small interface."""

    items: tuple[DiagnosticItem, ...]

    @property
    def condition(self) -> DiagnosticCondition:
        if any(item.condition is DiagnosticCondition.ACTION_REQUIRED for item in self.items):
            return DiagnosticCondition.ACTION_REQUIRED
        if any(item.condition is DiagnosticCondition.ATTENTION for item in self.items):
            return DiagnosticCondition.ATTENTION
        return DiagnosticCondition.HEALTHY

    @property
    def action_required_count(self) -> int:
        return sum(item.condition is DiagnosticCondition.ACTION_REQUIRED for item in self.items)

    @property
    def attention_count(self) -> int:
        return sum(item.condition is DiagnosticCondition.ATTENTION for item in self.items)

    @property
    def recommended_action(self) -> str:
        item = self._recommended_item()
        return (
            item.guidance or item.summary if item is not None else "当前无需处理，可以安全继续操作"
        )

    @property
    def recommended_action_kind(self) -> DiagnosticAction | None:
        item = self._recommended_item()
        return item.action if item is not None else None

    def _recommended_item(self) -> DiagnosticItem | None:
        for condition in (
            DiagnosticCondition.ACTION_REQUIRED,
            DiagnosticCondition.ATTENTION,
        ):
            for item in self.items:
                if item.condition is condition:
                    return item
        return None


class DiagnosticsCenter(Protocol):
    """Public application seam consumed by the diagnostics-center TUI."""

    def inspect(self) -> DiagnosticsCenterReport: ...


class DiagnosticsCenterService:
    """Translate desired-state, readiness, and runtime evidence into one report."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        config_inspector: ConfigurationTargetInspector,
        host_readiness: HostReadiness,
        host_diagnostics: HostDiagnostics,
    ) -> None:
        self._state_store = state_store
        self._config_inspector = config_inspector
        self._host_readiness = host_readiness
        self._host_diagnostics = host_diagnostics

    def inspect(self) -> DiagnosticsCenterReport:
        desired_state, installation = self._inspect_desired_state()
        items = [desired_state]
        if installation is not None:
            items.append(self._inspect_live_configuration(installation))
        try:
            readiness = self._host_readiness.inspect()
        except (OSError, RuntimeError, ValueError) as error:
            items.append(
                DiagnosticItem(
                    code=DiagnosticCode.HOST_READINESS,
                    condition=DiagnosticCondition.ACTION_REQUIRED,
                    title="主机准备度检查",
                    summary="无法完成主机准备度检查",
                    diagnostics=str(error),
                    guidance=("重新运行检查，若持续失败，确认 helper、core 与配置目标权限。"),
                )
            )
        else:
            helper_ready = any(
                item.code is HostReadinessItemCode.PRIVILEGED_HELPER
                and item.state is ReadinessState.READY
                for item in readiness.items
            )
            items.extend(
                DiagnosticItem(
                    code=DiagnosticCode(item.code.value),
                    condition=(
                        DiagnosticCondition.HEALTHY
                        if item.state is ReadinessState.READY
                        else (
                            DiagnosticCondition.ATTENTION
                            if item.state is ReadinessState.ATTENTION
                            else DiagnosticCondition.ACTION_REQUIRED
                        )
                    ),
                    title=item.title,
                    summary=item.summary,
                    diagnostics=item.diagnostics,
                    guidance=item.guidance,
                    action=(
                        DiagnosticAction.MANAGE_CORE
                        if item.code is HostReadinessItemCode.CORE
                        and item.state is ReadinessState.ACTION_REQUIRED
                        and helper_ready
                        else None
                    ),
                )
                for item in readiness.items
            )
        try:
            runtime = self._host_diagnostics.inspect()
        except (OSError, RuntimeError, ValueError) as error:
            items.append(
                DiagnosticItem(
                    code=DiagnosticCode.RUNTIME,
                    condition=DiagnosticCondition.ACTION_REQUIRED,
                    title="sing-box 运行状态",
                    summary="无法完成 sing-box 运行状态检查",
                    diagnostics=str(error),
                    guidance=(
                        "确认 init system 和 sing-box 服务名称后重新检查，"
                        "不要在状态未知时应用配置。"
                    ),
                )
            )
        else:
            items.append(
                DiagnosticItem(
                    code=DiagnosticCode.RUNTIME,
                    condition=(
                        DiagnosticCondition.HEALTHY
                        if runtime.condition is HostCondition.HEALTHY
                        else DiagnosticCondition.ACTION_REQUIRED
                    ),
                    title="sing-box 运行状态",
                    summary=runtime.summary,
                    diagnostics=runtime.diagnostics,
                    guidance=" ".join(runtime.recovery_instructions),
                )
            )
        return DiagnosticsCenterReport(items=tuple(items))

    def _inspect_live_configuration(self, installation: ManagedInstallation) -> DiagnosticItem:
        try:
            observation = self._config_inspector.inspect()
        except ConfigTargetInspectionError as error:
            return DiagnosticItem(
                code=DiagnosticCode.LIVE_CONFIGURATION,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="实时配置身份",
                summary="无法核对实时配置身份",
                diagnostics=str(error),
                guidance=(
                    "确认配置目标读取权限或最小权限 helper 后重新检查。在身份未知时不要应用配置。"
                ),
            )
        if installation.expected_config_sha256 is None and not observation.exists:
            return DiagnosticItem(
                code=DiagnosticCode.LIVE_CONFIGURATION,
                condition=DiagnosticCondition.HEALTHY,
                title="实时配置身份",
                summary="配置目标不存在，desired state 也未记录实时配置",
                diagnostics="没有待核对的实时配置身份",
                guidance="",
            )
        if installation.expected_config_sha256 is None and observation.exists:
            return DiagnosticItem(
                code=DiagnosticCode.LIVE_CONFIGURATION,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="实时配置身份",
                summary="发现尚未由 manager 接管的现有配置",
                diagnostics=f"当前配置 SHA-256：{observation.sha256}",
                guidance=(
                    "打开现有配置接管流程，先审查并确认这个精确指纹。接管不会导入或改写配置。"
                ),
                action=DiagnosticAction.REVIEW_CONFIG_ADOPTION,
            )
        if installation.expected_config_sha256 is not None and not observation.exists:
            return DiagnosticItem(
                code=DiagnosticCode.LIVE_CONFIGURATION,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="实时配置身份",
                summary="desired state 记录的实时配置不存在",
                diagnostics=(
                    f"记录的 SHA-256：{installation.expected_config_sha256}，配置目标不存在"
                ),
                guidance=(
                    "不要创建空文件或直接应用。先确认配置目标路径和挂载状态，再从已知正常版本恢复。"
                ),
            )
        if observation.sha256 != installation.expected_config_sha256:
            return DiagnosticItem(
                code=DiagnosticCode.LIVE_CONFIGURATION,
                condition=DiagnosticCondition.ACTION_REQUIRED,
                title="实时配置身份",
                summary="实时配置已在 manager 记录后发生变化",
                diagnostics=(
                    f"记录的 SHA-256：{installation.expected_config_sha256}，"
                    f"当前 SHA-256：{observation.sha256}"
                ),
                guidance=(
                    "不要直接应用。先备份当前配置并确认外部修改来源。"
                    "若改动非预期，恢复记录版本后重新检查。"
                ),
            )
        return DiagnosticItem(
            code=DiagnosticCode.LIVE_CONFIGURATION,
            condition=DiagnosticCondition.HEALTHY,
            title="实时配置身份",
            summary="实时配置身份与 desired state 记录一致",
            diagnostics=f"当前配置 SHA-256：{observation.sha256}",
            guidance="",
        )

    def _inspect_desired_state(self) -> tuple[DiagnosticItem, ManagedInstallation | None]:
        try:
            installation = self._state_store.load()
        except (OSError, KeyError, TypeError, ValueError) as error:
            return (
                DiagnosticItem(
                    code=DiagnosticCode.DESIRED_STATE,
                    condition=DiagnosticCondition.ACTION_REQUIRED,
                    title="manager desired state",
                    summary="无法读取 manager desired state",
                    diagnostics=str(error),
                    guidance=(
                        "不要覆盖现有文件。检查 state.json.bak，"
                        "确认内容后恢复兼容的 desired state。"
                    ),
                ),
                None,
            )
        applied_profiles = tuple(
            profile for profile in installation.profiles if profile.status is ProfileStatus.APPLIED
        )
        applied_count = len(applied_profiles)
        draft_count = sum(
            profile.status is ProfileStatus.DRAFT for profile in installation.profiles
        )
        issues: list[str] = []
        issues.extend(
            f"配置缺少稳定 profile ID: {profile.profile_name}"
            for profile in installation.profiles
            if not profile.profile_id
        )
        seen_profile_ids: set[str] = set()
        duplicate_profile_ids: set[str] = set()
        for profile in installation.profiles:
            if profile.profile_id in seen_profile_ids:
                duplicate_profile_ids.add(profile.profile_id)
            seen_profile_ids.add(profile.profile_id)
        issues.extend(
            f"重复的 profile ID: {profile_id}" for profile_id in sorted(duplicate_profile_ids)
        )
        for profile in applied_profiles:
            if profile.listen_port is None:
                issues.append(f"{profile.profile_id}: 已应用配置缺少监听端口")
            if profile.protocol_material is None:
                issues.append(f"{profile.profile_id}: 已应用配置缺少协议凭据")
        if applied_profiles and installation.expected_config_sha256 is None:
            issues.append("已应用配置存在，但缺少 managed configuration fingerprint")
        if issues:
            return (
                DiagnosticItem(
                    code=DiagnosticCode.DESIRED_STATE,
                    condition=DiagnosticCondition.ACTION_REQUIRED,
                    title="manager desired state",
                    summary=f"desired state 存在 {len(issues)} 个一致性问题",
                    diagnostics="; ".join(issues),
                    guidance=(
                        "不要直接编辑 JSON。先恢复 desired-state 备份，或移除并重新创建受影响配置。"
                    ),
                ),
                installation,
            )
        return (
            DiagnosticItem(
                code=DiagnosticCode.DESIRED_STATE,
                condition=DiagnosticCondition.HEALTHY,
                title="manager desired state",
                summary=(
                    f"desired state revision {installation.revision} 可读取，"
                    f"{applied_count} 个已应用配置，{draft_count} 个草案"
                ),
                diagnostics="desired state 可读取",
                guidance="",
            ),
            installation,
        )
