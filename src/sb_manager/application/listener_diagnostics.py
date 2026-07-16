"""Classify expected sing-box listeners without claiming unavailable evidence."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sb_manager.domain.installation import (
    ManagedInstallation,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.listener_source import (
    ListenerEndpoint,
    ListenerInspectionError,
    ListenerObservation,
    ListenerOwner,
    ListenerSource,
    ListenerTransport,
)


class ListenerDiagnosticCondition(str, Enum):
    """Operator significance of declared listener evidence."""

    HEALTHY = "healthy"
    ATTENTION = "attention"
    ACTION_REQUIRED = "action-required"


@dataclass(frozen=True, slots=True)
class ListenerDiagnosticsReport:
    """One compact explanation of all enabled, applied listener endpoints."""

    condition: ListenerDiagnosticCondition
    summary: str
    diagnostics: str
    guidance: str


class ListenerDiagnostics(Protocol):
    """Application-facing listener diagnostic interface."""

    def inspect(self, installation: ManagedInstallation) -> ListenerDiagnosticsReport: ...


_TCP_PROTOCOLS = frozenset(
    {
        ProtocolKind.VLESS_REALITY,
        ProtocolKind.SHADOWSOCKS,
        ProtocolKind.TROJAN,
        ProtocolKind.ANYTLS,
        ProtocolKind.VLESS_TLS,
        ProtocolKind.VMESS_TLS,
    }
)
_UDP_PROTOCOLS = frozenset(
    {
        ProtocolKind.HYSTERIA2,
        ProtocolKind.TUIC,
    }
)


class ListenerDiagnosticsService:
    """Compare desired listener shape with conservative Linux process evidence."""

    def __init__(self, *, source: ListenerSource) -> None:
        self._source = source

    def inspect(self, installation: ManagedInstallation) -> ListenerDiagnosticsReport:
        endpoints = _expected_endpoints(installation)
        if not endpoints:
            return ListenerDiagnosticsReport(
                condition=ListenerDiagnosticCondition.HEALTHY,
                summary="当前没有启用且已应用的监听端口",
                diagnostics="未请求主机端口观察",
                guidance="",
            )
        try:
            inspection = self._source.inspect(endpoints)
        except ListenerInspectionError as error:
            return ListenerDiagnosticsReport(
                condition=ListenerDiagnosticCondition.ATTENTION,
                summary="无法检查监听端口与进程归属",
                diagnostics=str(error),
                guidance="确认 /proc 可读权限后重新检查; 证据未知时不要假定端口由 sing-box 持有。",
            )

        observed = {item.endpoint: item for item in inspection.observations}
        missing = tuple(endpoint for endpoint in endpoints if endpoint not in observed)
        foreign = tuple(
            observation
            for endpoint in endpoints
            if (observation := observed.get(endpoint)) is not None
            and _has_confirmed_foreign_owner(observation)
        )
        unknown = tuple(
            observation
            for endpoint in endpoints
            if (observation := observed.get(endpoint)) is not None
            and not _has_confirmed_foreign_owner(observation)
            and not _has_confirmed_sing_box_ownership(observation)
        )
        details = tuple(_describe(endpoint, observed.get(endpoint)) for endpoint in endpoints)
        diagnostics = "; ".join(details)
        if inspection.diagnostics:
            diagnostics = f"{diagnostics}; {inspection.diagnostics}"

        if missing:
            return ListenerDiagnosticsReport(
                condition=ListenerDiagnosticCondition.ACTION_REQUIRED,
                summary=_count_summary(len(missing), len(endpoints), "预期监听端点未监听"),
                diagnostics=diagnostics,
                guidance="先检查 sing-box 服务和配置加载结果; 不要在端口状态异常时分享连接。",
            )
        if foreign:
            return ListenerDiagnosticsReport(
                condition=ListenerDiagnosticCondition.ACTION_REQUIRED,
                summary=f"{len(foreign)} 个预期监听端点由其他进程持有",
                diagnostics=diagnostics,
                guidance="确认占用进程来源并解决端口冲突，然后重启 sing-box 并重新检查。",
            )
        if unknown:
            return ListenerDiagnosticsReport(
                condition=ListenerDiagnosticCondition.ATTENTION,
                summary=f"{len(unknown)} 个监听端点的进程归属无法确认",
                diagnostics=diagnostics,
                guidance=(
                    "以能读取相关 /proc 进程描述符的权限重新检查; 不要把仅监听误当成所有权证明。"
                ),
            )
        return ListenerDiagnosticsReport(
            condition=ListenerDiagnosticCondition.HEALTHY,
            summary=f"{len(endpoints)} 个预期监听端点均由 sing-box 持有",
            diagnostics=diagnostics,
            guidance="",
        )


def _expected_endpoints(installation: ManagedInstallation) -> tuple[ListenerEndpoint, ...]:
    endpoints: set[ListenerEndpoint] = set()
    for profile in installation.profiles:
        if (
            profile.status is not ProfileStatus.APPLIED
            or not profile.enabled
            or profile.listen_port is None
        ):
            continue
        if profile.protocol in _TCP_PROTOCOLS:
            endpoints.add(
                ListenerEndpoint(port=profile.listen_port, transport=ListenerTransport.TCP)
            )
        if profile.protocol in _UDP_PROTOCOLS:
            endpoints.add(
                ListenerEndpoint(port=profile.listen_port, transport=ListenerTransport.UDP)
            )
    return tuple(sorted(endpoints, key=lambda item: (item.port, item.transport.value)))


def _has_confirmed_foreign_owner(observation: ListenerObservation) -> bool:
    return (
        observation.ownership_complete
        and bool(observation.owners)
        and any(owner.process_name != "sing-box" for owner in observation.owners)
    )


def _has_confirmed_sing_box_ownership(observation: ListenerObservation) -> bool:
    return (
        observation.ownership_complete
        and bool(observation.owners)
        and all(owner.process_name == "sing-box" for owner in observation.owners)
    )


def _describe(
    endpoint: ListenerEndpoint,
    observation: ListenerObservation | None,
) -> str:
    label = f"{endpoint.transport.value.upper()} {endpoint.port}"
    if observation is None:
        return f"{label}：未监听"
    owners = ", ".join(_describe_owner(owner) for owner in observation.owners)
    if _has_confirmed_sing_box_ownership(observation):
        return f"{label}：{owners}"
    if _has_confirmed_foreign_owner(observation):
        return f"{label}：其他进程 {owners}"
    return f"{label}：归属未知{f' (可见：{owners})' if owners else ''}"


def _describe_owner(owner: ListenerOwner) -> str:
    return f"{owner.process_name or '未知进程'} (PID {owner.pid})"


def _count_summary(count: int, total: int, message: str) -> str:
    prefix = f"{count}/{total}" if total > count else str(count)
    return f"{prefix} 个{message}"
