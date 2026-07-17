"""Classify certificate validity for enabled, applied managed profiles."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from sb_manager.domain.installation import ManagedInstallation, ProfileStatus
from sb_manager.seams.certificate_source import (
    CertificateInspectionError,
    CertificateMaterialState,
    CertificateObservation,
    CertificateSource,
    CertificateTarget,
    CertificateTargetKind,
)
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent, TlsIntent

_ATTENTION_DAYS = 30
_URGENT_DAYS = 7


class CertificateDiagnosticCondition(str, Enum):
    """Operator significance of managed certificate evidence."""

    HEALTHY = "healthy"
    ATTENTION = "attention"
    ACTION_REQUIRED = "action-required"


@dataclass(frozen=True, slots=True)
class CertificateDiagnosticsReport:
    """One compact explanation of every relevant managed certificate."""

    condition: CertificateDiagnosticCondition
    summary: str
    diagnostics: str
    guidance: str


class CertificateDiagnostics(Protocol):
    """Application-facing certificate diagnostic interface."""

    def inspect(self, installation: ManagedInstallation) -> CertificateDiagnosticsReport: ...


class CertificateDiagnosticsService:
    """Keep certificate discovery and expiry policy behind one small interface."""

    def __init__(
        self,
        *,
        source: CertificateSource,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._source = source
        self._now = now or _utc_now

    def inspect(  # noqa: PLR0911 - explicit operator-priority policy reads top to bottom
        self, installation: ManagedInstallation
    ) -> CertificateDiagnosticsReport:
        profiles_by_target: dict[CertificateTarget, list[str]] = {}
        for profile in installation.profiles:
            if (
                profile.status is not ProfileStatus.APPLIED
                or not profile.enabled
                or profile.tls_intent is None
            ):
                continue
            target = _target_for_intent(profile.tls_intent)
            profiles_by_target.setdefault(target, []).append(profile.profile_name)
        if not profiles_by_target:
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.HEALTHY,
                summary="当前没有需要检查的托管 X.509 证书",
                diagnostics="未请求证书材料观察",
                guidance="",
            )

        targets = tuple(profiles_by_target)
        try:
            inspection = self._source.inspect(targets)
        except CertificateInspectionError as error:
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ATTENTION,
                summary="无法检查托管证书有效期",
                diagnostics=str(error),
                guidance=(
                    "确认只读证书权限或 privileged helper 后重新检查; 状态未知不代表证书有效。"
                ),
            )
        observations = {observation.target: observation for observation in inspection.observations}
        now = self._now()
        invalid = tuple(
            observation
            for target in targets
            if (observation := observations.get(target)) is not None
            and observation.state is CertificateMaterialState.INVALID
        )
        missing = tuple(
            observation
            for target in targets
            if (observation := observations.get(target)) is not None
            and observation.state is CertificateMaterialState.MISSING
        )
        if invalid or missing:
            affected = invalid or missing
            state_label = "无效" if invalid else "缺失"
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ACTION_REQUIRED,
                summary=f"{len(affected)} 个托管证书材料{state_label}",
                diagnostics=_describe_all(
                    targets,
                    observations=observations,
                    profiles_by_target=profiles_by_target,
                    now=now,
                ),
                guidance="修复或重新签发证书材料，确认 sing-box 成功加载后再复检。",
            )
        not_yet_valid = tuple(
            observation
            for target in targets
            if (observation := observations.get(target)) is not None
            and observation.state is CertificateMaterialState.AVAILABLE
            and observation.not_valid_before is not None
            and observation.not_valid_before > now
        )
        if not_yet_valid:
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ACTION_REQUIRED,
                summary=f"{len(not_yet_valid)} 个托管证书尚未生效",
                diagnostics=_describe_all(
                    targets,
                    observations=observations,
                    profiles_by_target=profiles_by_target,
                    now=now,
                ),
                guidance="检查证书来源和主机时钟; 证书生效前不要分享连接。",
            )
        expired = tuple(
            observation
            for target in targets
            if (observation := observations.get(target)) is not None
            and observation.state is CertificateMaterialState.AVAILABLE
            and observation.not_valid_after is not None
            and observation.not_valid_after <= now
        )
        if expired:
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ACTION_REQUIRED,
                summary=f"{len(expired)} 个托管证书已过期",
                diagnostics=_describe_all(
                    targets,
                    observations=observations,
                    profiles_by_target=profiles_by_target,
                    now=now,
                ),
                guidance="立即更新或恢复受影响证书，确认 sing-box 重新加载后再分享连接。",
            )
        expiring = tuple(
            observation
            for target in targets
            if (observation := observations.get(target)) is not None
            and observation.state is CertificateMaterialState.AVAILABLE
            and observation.not_valid_after is not None
            and now < observation.not_valid_after
            and (observation.not_valid_after - now).days <= _ATTENTION_DAYS
        )
        if expiring:
            urgent = tuple(
                observation
                for observation in expiring
                if observation.not_valid_after is not None
                and (observation.not_valid_after - now).days <= _URGENT_DAYS
            )
            threshold = _URGENT_DAYS if urgent else _ATTENTION_DAYS
            affected = urgent or expiring
            return CertificateDiagnosticsReport(
                condition=(
                    CertificateDiagnosticCondition.ACTION_REQUIRED
                    if urgent
                    else CertificateDiagnosticCondition.ATTENTION
                ),
                summary=f"{len(affected)} 个托管证书将在 {threshold} 天内过期",
                diagnostics=_describe_all(
                    targets,
                    observations=observations,
                    profiles_by_target=profiles_by_target,
                    now=now,
                ),
                guidance=(
                    "立即检查自动续期或更新 operator 文件证书，重新加载后再复检。"
                    if urgent
                    else "检查 ACME 自动续期或安排 operator 文件证书更新，并在 7 天阈值前复检。"
                ),
            )
        unavailable = tuple(
            observations.get(target)
            for target in targets
            if observations.get(target) is None
            or observations[target].state is CertificateMaterialState.UNAVAILABLE
        )
        if unavailable:
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.ATTENTION,
                summary=f"{len(unavailable)} 个托管证书状态无法确认",
                diagnostics=_describe_all(
                    targets,
                    observations=observations,
                    profiles_by_target=profiles_by_target,
                    now=now,
                ),
                guidance=(
                    "确认只读证书权限或 privileged helper 后重新检查; 状态未知不代表证书有效。"
                ),
            )
        if all(
            (observation := observations.get(target)) is not None
            and _is_healthy(observation, now=now)
            for target in targets
        ):
            return CertificateDiagnosticsReport(
                condition=CertificateDiagnosticCondition.HEALTHY,
                summary=f"{len(targets)} 个托管证书有效期均正常",
                diagnostics=_describe_all(
                    targets,
                    observations=observations,
                    profiles_by_target=profiles_by_target,
                    now=now,
                ),
                guidance="",
            )
        raise NotImplementedError


def _target_for_intent(intent: TlsIntent) -> CertificateTarget:
    if isinstance(intent, OperatorFileTlsIntent):
        return CertificateTarget(
            kind=CertificateTargetKind.OPERATOR_FILE,
            server_name=intent.server_name,
            location=intent.certificate_path,
        )
    if isinstance(intent, AcmeTlsIntent):
        return CertificateTarget(
            kind=CertificateTargetKind.CERTMAGIC_ACME,
            server_name=intent.server_name,
            location=intent.data_directory,
        )
    raise TypeError(f"Unsupported TLS intent: {type(intent).__name__}")


def _is_healthy(observation: CertificateObservation, *, now: datetime) -> bool:
    return (
        observation.state is CertificateMaterialState.AVAILABLE
        and observation.not_valid_before is not None
        and observation.not_valid_after is not None
        and observation.not_valid_before <= now
        and (observation.not_valid_after - now).days > _ATTENTION_DAYS
    )


def _describe_available(
    observation: CertificateObservation,
    *,
    profile_names: list[str],
    now: datetime,
) -> str:
    not_valid_after = observation.not_valid_after
    if not_valid_after is None:
        raise AssertionError("Available certificate is missing its expiration")
    remaining_days = (not_valid_after - now).days
    return (
        f"{'、'.join(profile_names)}：{observation.target.server_name}，"
        f"有效至 {not_valid_after.date().isoformat()} (剩余 {remaining_days} 天)"
    )


def _describe_expired(
    observation: CertificateObservation,
    *,
    profile_names: list[str],
    now: datetime,
) -> str:
    not_valid_after = observation.not_valid_after
    if not_valid_after is None:
        raise AssertionError("Expired certificate is missing its expiration")
    expired_days = max(1, (now - not_valid_after).days)
    return (
        f"{'、'.join(profile_names)}：{observation.target.server_name}，"
        f"已过期 {expired_days} 天 ({not_valid_after.date().isoformat()})"
    )


def _describe_material_problem(
    observation: CertificateObservation,
    *,
    profile_names: list[str],
) -> str:
    state_label = {
        CertificateMaterialState.MISSING: "材料缺失",
        CertificateMaterialState.INVALID: "材料无效",
        CertificateMaterialState.UNAVAILABLE: "状态不可用",
    }.get(observation.state, observation.state.value)
    diagnostics = f" ({observation.diagnostics})" if observation.diagnostics else ""
    return (
        f"{'、'.join(profile_names)}：{observation.target.server_name}，{state_label}{diagnostics}"
    )


def _describe_all(
    targets: tuple[CertificateTarget, ...],
    *,
    observations: dict[CertificateTarget, CertificateObservation],
    profiles_by_target: dict[CertificateTarget, list[str]],
    now: datetime,
) -> str:
    details = []
    for target in targets:
        observation = observations.get(target)
        if observation is None:
            details.append(
                f"{'、'.join(profiles_by_target[target])}：{target.server_name}，证书源未返回观察"
            )
        elif observation.state is not CertificateMaterialState.AVAILABLE:
            details.append(
                _describe_material_problem(
                    observation,
                    profile_names=profiles_by_target[target],
                )
            )
        elif observation.not_valid_before is not None and observation.not_valid_before > now:
            details.append(
                f"{'、'.join(profiles_by_target[target])}：{target.server_name}，"
                f"生效时间 {observation.not_valid_before.date().isoformat()}"
            )
        elif observation.not_valid_after is not None and observation.not_valid_after <= now:
            details.append(
                _describe_expired(
                    observation,
                    profile_names=profiles_by_target[target],
                    now=now,
                )
            )
        else:
            details.append(
                _describe_available(
                    observation,
                    profile_names=profiles_by_target[target],
                    now=now,
                )
            )
    return "; ".join(details)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
