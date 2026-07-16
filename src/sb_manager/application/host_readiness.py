"""Deep first-run readiness module for safe host operations."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.seams.config_target import (
    ConfigTargetInspectionError,
    ConfigurationTargetInspector,
    LiveConfigObservation,
)
from sb_manager.seams.core_status import CoreStatusInspector


class HostAccessMode(str, Enum):
    """How generated configuration is expected to reach the host."""

    DIRECT = "direct"
    PRIVILEGED = "privileged"


class ReadinessState(str, Enum):
    """Operator relevance of one read-only readiness check."""

    READY = "ready"
    ATTENTION = "attention"
    ACTION_REQUIRED = "action-required"


class HostReadinessItemCode(str, Enum):
    """Stable identities for readiness checks presented by the TUI."""

    CONFIG_TARGET = "config-target"
    PRIVILEGED_HELPER = "privileged-helper"
    CORE = "core"


@dataclass(frozen=True, slots=True)
class HostReadinessItem:
    """One actionable host prerequisite without raw system parsing in the TUI."""

    code: HostReadinessItemCode
    state: ReadinessState
    title: str
    summary: str
    diagnostics: str
    guidance: str


@dataclass(frozen=True, slots=True)
class HostReadinessReport:
    """Complete first-run evidence behind one small TUI-facing interface."""

    items: tuple[HostReadinessItem, ...]

    @property
    def ready_for_apply(self) -> bool:
        return not any(item.state is ReadinessState.ACTION_REQUIRED for item in self.items)

    @property
    def action_required_count(self) -> int:
        return sum(item.state is ReadinessState.ACTION_REQUIRED for item in self.items)

    @property
    def recommended_action(self) -> str:
        for item in self.items:
            if item.state is ReadinessState.ACTION_REQUIRED:
                return _recommended_action(item)
        for item in self.items:
            if item.state is ReadinessState.ATTENTION:
                return _recommended_action(item)
        return "开始创建或应用配置"


class HostReadiness(Protocol):
    """Public application seam consumed by the dashboard."""

    def inspect(self) -> HostReadinessReport: ...


class HostReadinessService:
    """Translate core, target, and helper probes into ordered operator guidance."""

    def __init__(
        self,
        *,
        access_mode: HostAccessMode,
        config_inspector: ConfigurationTargetInspector,
        privileged_inspector: ConfigurationTargetInspector,
        core_inspector: CoreStatusInspector,
    ) -> None:
        self._access_mode = access_mode
        self._config_inspector = config_inspector
        self._privileged_inspector = privileged_inspector
        self._core_inspector = core_inspector

    def inspect(self) -> HostReadinessReport:
        items: list[HostReadinessItem] = []
        if self._access_mode is HostAccessMode.DIRECT:
            items.append(self._inspect_direct_target())
        items.append(self._inspect_privileged_helper())
        items.append(self._inspect_core())
        return HostReadinessReport(items=tuple(items))

    def _inspect_direct_target(self) -> HostReadinessItem:
        try:
            observation = self._config_inspector.inspect()
        except ConfigTargetInspectionError as error:
            return HostReadinessItem(
                code=HostReadinessItemCode.CONFIG_TARGET,
                state=ReadinessState.ACTION_REQUIRED,
                title="直接配置目标",
                summary="当前进程无法安全检查配置目标",
                diagnostics=str(error),
                guidance=(
                    "确认当前用户拥有目标读写权限，或改用 --apply-mode privileged "
                    "和最小权限 helper。"
                ),
            )
        return HostReadinessItem(
            code=HostReadinessItemCode.CONFIG_TARGET,
            state=ReadinessState.READY,
            title="直接配置目标",
            summary="当前进程可以安全检查配置目标",
            diagnostics=_observation_diagnostics(observation),
            guidance="",
        )

    def _inspect_privileged_helper(self) -> HostReadinessItem:
        try:
            observation = self._privileged_inspector.inspect()
        except ConfigTargetInspectionError as error:
            state = (
                ReadinessState.ACTION_REQUIRED
                if self._access_mode is HostAccessMode.PRIVILEGED
                else ReadinessState.ATTENTION
            )
            return HostReadinessItem(
                code=HostReadinessItemCode.PRIVILEGED_HELPER,
                state=state,
                title="最小权限 helper",
                summary="最小权限 helper 或固定配置目标尚不可用",
                diagnostics=str(error),
                guidance=(
                    "以 root 身份运行 sb-manager-install-policy --confirm，然后返回 TUI 重新检查。"
                ),
            )
        return HostReadinessItem(
            code=HostReadinessItemCode.PRIVILEGED_HELPER,
            state=ReadinessState.READY,
            title="最小权限 helper",
            summary="最小权限 helper 与固定配置目标可用",
            diagnostics=_observation_diagnostics(observation),
            guidance="",
        )

    def _inspect_core(self) -> HostReadinessItem:
        observation = self._core_inspector.inspect()
        if observation.available:
            return HostReadinessItem(
                code=HostReadinessItemCode.CORE,
                state=ReadinessState.READY,
                title="sing-box 核心",
                summary=f"sing-box {observation.version} 已可用",
                diagnostics=observation.diagnostics,
                guidance="",
            )
        return HostReadinessItem(
            code=HostReadinessItemCode.CORE,
            state=ReadinessState.ACTION_REQUIRED,
            title="sing-box 核心",
            summary="sing-box 核心尚不可用",
            diagnostics=observation.diagnostics,
            guidance="选择“安装或升级 sing-box 核心”，完成可信安装后重新检查。",
        )


def _observation_diagnostics(observation: LiveConfigObservation) -> str:
    return "配置目标已存在并完成只读识别" if observation.exists else "配置目标尚不存在"


def _recommended_action(item: HostReadinessItem) -> str:
    if item.code is HostReadinessItemCode.CONFIG_TARGET:
        return "修复配置目标权限或改用最小权限模式"
    if item.code is HostReadinessItemCode.PRIVILEGED_HELPER:
        return (
            "安装最小权限策略"
            if item.state is ReadinessState.ACTION_REQUIRED
            else "安装最小权限策略以启用核心升级"
        )
    return "安装 sing-box 核心"
