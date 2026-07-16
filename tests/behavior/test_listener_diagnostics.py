import pytest

from sb_manager.application.listener_diagnostics import (
    ListenerDiagnosticCondition,
    ListenerDiagnosticsService,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.seams.listener_source import (
    ListenerEndpoint,
    ListenerInspection,
    ListenerInspectionError,
    ListenerObservation,
    ListenerOwner,
    ListenerTransport,
)


class RecordingListenerSource:
    def __init__(self, observations: tuple[ListenerObservation, ...] = ()) -> None:
        self.observations = observations
        self.requested: tuple[ListenerEndpoint, ...] | None = None

    def inspect(self, endpoints: tuple[ListenerEndpoint, ...]) -> ListenerInspection:
        self.requested = endpoints
        return ListenerInspection(observations=self.observations)


class FailingListenerSource:
    def inspect(self, endpoints: tuple[ListenerEndpoint, ...]) -> ListenerInspection:
        raise ListenerInspectionError("/proc/net/tcp is unavailable")


def applied_profile(
    *,
    profile_id: str,
    protocol: ProtocolKind,
    port: int,
    enabled: bool = True,
) -> ManagedProfile:
    return ManagedProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        protocol=protocol,
        listen_port=port,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.APPLIED,
        enabled=enabled,
    )


def installation(*profiles: ManagedProfile) -> ManagedInstallation:
    return ManagedInstallation(schema_version=1, revision=1, profiles=profiles)


def observation(
    endpoint: ListenerEndpoint,
    *,
    process_name: str = "sing-box",
    ownership_complete: bool = True,
) -> ListenerObservation:
    return ListenerObservation(
        endpoint=endpoint,
        owners=(ListenerOwner(pid=42, process_name=process_name),),
        ownership_complete=ownership_complete,
    )


def test_no_enabled_applied_profiles_skips_host_observation() -> None:
    source = RecordingListenerSource()
    service = ListenerDiagnosticsService(source=source)
    draft = ManagedProfile(
        profile_id="draft",
        profile_name="draft",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        status=ProfileStatus.DRAFT,
    )

    report = service.inspect(
        installation(
            draft,
            applied_profile(
                profile_id="paused",
                protocol=ProtocolKind.HYSTERIA2,
                port=8443,
                enabled=False,
            ),
        )
    )

    assert report.condition is ListenerDiagnosticCondition.HEALTHY
    assert report.summary == "当前没有启用且已应用的监听端口"
    assert source.requested is None


def test_protocols_request_their_actual_tcp_and_udp_listener_shapes() -> None:
    endpoints = (
        ListenerEndpoint(port=4433, transport=ListenerTransport.TCP),
        ListenerEndpoint(port=8388, transport=ListenerTransport.TCP),
        ListenerEndpoint(port=8443, transport=ListenerTransport.UDP),
    )
    source = RecordingListenerSource(tuple(observation(endpoint) for endpoint in endpoints))
    service = ListenerDiagnosticsService(source=source)

    report = service.inspect(
        installation(
            applied_profile(
                profile_id="vless",
                protocol=ProtocolKind.VLESS_REALITY,
                port=4433,
            ),
            applied_profile(
                profile_id="ss",
                protocol=ProtocolKind.SHADOWSOCKS,
                port=8388,
            ),
            applied_profile(
                profile_id="hy2",
                protocol=ProtocolKind.HYSTERIA2,
                port=8443,
            ),
        )
    )

    assert source.requested == endpoints
    assert report.condition is ListenerDiagnosticCondition.HEALTHY
    assert report.summary == "3 个预期监听端点均由 sing-box 持有"


def test_missing_expected_listener_requires_action() -> None:
    endpoint = ListenerEndpoint(port=4433, transport=ListenerTransport.TCP)
    report = ListenerDiagnosticsService(source=RecordingListenerSource()).inspect(
        installation(
            applied_profile(
                profile_id="vless",
                protocol=ProtocolKind.VLESS_REALITY,
                port=endpoint.port,
            )
        )
    )

    assert report.condition is ListenerDiagnosticCondition.ACTION_REQUIRED
    assert report.summary == "1 个预期监听端点未监听"
    assert "TCP 4433：未监听" in report.diagnostics


def test_confirmed_foreign_owner_requires_action() -> None:
    endpoint = ListenerEndpoint(port=4433, transport=ListenerTransport.TCP)
    source = RecordingListenerSource(
        (observation(endpoint, process_name="caddy", ownership_complete=True),)
    )

    report = ListenerDiagnosticsService(source=source).inspect(
        installation(
            applied_profile(
                profile_id="vless",
                protocol=ProtocolKind.VLESS_REALITY,
                port=endpoint.port,
            )
        )
    )

    assert report.condition is ListenerDiagnosticCondition.ACTION_REQUIRED
    assert report.summary == "1 个预期监听端点由其他进程持有"
    assert "caddy (PID 42)" in report.diagnostics


@pytest.mark.parametrize(
    "observation_value",
    [
        ListenerObservation(
            endpoint=ListenerEndpoint(port=4433, transport=ListenerTransport.TCP),
            owners=(),
            ownership_complete=False,
        ),
        observation(
            ListenerEndpoint(port=4433, transport=ListenerTransport.TCP),
            ownership_complete=False,
        ),
    ],
)
def test_incomplete_process_evidence_is_attention_not_claimed_ownership(
    observation_value: ListenerObservation,
) -> None:
    report = ListenerDiagnosticsService(
        source=RecordingListenerSource((observation_value,))
    ).inspect(
        installation(
            applied_profile(
                profile_id="vless",
                protocol=ProtocolKind.VLESS_REALITY,
                port=4433,
            )
        )
    )

    assert report.condition is ListenerDiagnosticCondition.ATTENTION
    assert report.summary == "1 个监听端点的进程归属无法确认"
    assert "归属未知" in report.diagnostics


def test_unavailable_proc_evidence_is_attention() -> None:
    report = ListenerDiagnosticsService(source=FailingListenerSource()).inspect(
        installation(
            applied_profile(
                profile_id="vless",
                protocol=ProtocolKind.VLESS_REALITY,
                port=4433,
            )
        )
    )

    assert report.condition is ListenerDiagnosticCondition.ATTENTION
    assert report.summary == "无法检查监听端口与进程归属"
    assert report.diagnostics == "/proc/net/tcp is unavailable"
