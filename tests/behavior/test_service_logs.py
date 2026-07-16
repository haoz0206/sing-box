import pytest

from sb_manager.adapters.memory_state import MemoryStateStore
from sb_manager.application.service_logs import (
    MAX_LOG_LINE_LENGTH,
    ServiceLogCondition,
    ServiceLogReport,
    ServiceLogService,
)
from sb_manager.domain.installation import (
    ManagedInstallation,
    ManagedProfile,
    PortSelection,
    ProfileStatus,
    ProtocolKind,
)
from sb_manager.domain.protocol_material import RealityMaterial, TuicMaterial
from sb_manager.seams.runtime_logs import RuntimeLogCapture

REQUESTED_LOG_LIMIT = 7
EXPECTED_REDACTIONS = 6


class FixedRuntimeLogSource:
    def __init__(self, capture: RuntimeLogCapture) -> None:
        self.capture = capture
        self.limits: list[int] = []

    def read_recent(self, *, limit: int) -> RuntimeLogCapture:
        self.limits.append(limit)
        return self.capture


def installation_with_secrets() -> ManagedInstallation:
    return ManagedInstallation(
        schema_version=1,
        revision=2,
        profiles=(
            ManagedProfile(
                profile_id="profile-1",
                profile_name="Reality",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=RealityMaterial(
                    user_uuid="11111111-2222-3333-4444-555555555555",
                    private_key="private-key-from-state",
                    public_key="safe-public-key",
                    short_id="0123456789abcdef",
                    server_name="www.example.com",
                ),
            ),
            ManagedProfile(
                profile_id="profile-2",
                profile_name="TUIC",
                protocol=ProtocolKind.TUIC,
                listen_port=8443,
                port_selection=PortSelection.FIXED,
                status=ProfileStatus.APPLIED,
                protocol_material=TuicMaterial(
                    user_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    password="tuic-password-from-state",
                ),
            ),
        ),
    )


def test_recent_logs_are_bounded_sanitized_and_redact_persisted_and_generic_secrets() -> None:
    source = FixedRuntimeLogSource(
        RuntimeLogCapture(
            available=True,
            source_label="systemd journal",
            lines=(
                "old line that the requested bound removes",
                "accepted uuid=11111111-2222-3333-4444-555555555555",
                "private_key: private-key-from-state",
                'json {"password":"unknown-runtime-secret"}',
                "Authorization: Bearer header-only-secret",
                "uri vless://aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee@vpn.example.com:443",
                "request https://api.example.com/?token=ephemeral-token&mode=test",
                "\x1b[31mfailed\x1b[0m\x00",
            ),
        )
    )
    service = ServiceLogService(
        state_store=MemoryStateStore(installation_with_secrets()),
        log_source=source,
    )

    report = service.read_recent(limit=REQUESTED_LOG_LIMIT)

    assert report.condition is ServiceLogCondition.AVAILABLE
    assert report.source_label == "systemd journal"
    assert report.lines == (
        "accepted uuid=[已脱敏]",
        "private_key: [已脱敏]",
        'json {"password":[已脱敏]}',
        "Authorization: [已脱敏]",
        "uri vless://[已脱敏]@vpn.example.com:443",
        "request https://api.example.com/?token=[已脱敏]&mode=test",
        "failed",
    )
    assert report.redacted_occurrences == EXPECTED_REDACTIONS
    assert report.limit == REQUESTED_LOG_LIMIT
    assert source.limits == [REQUESTED_LOG_LIMIT]
    rendered = "\n".join(report.lines)
    for secret in (
        "11111111-2222-3333-4444-555555555555",
        "private-key-from-state",
        "unknown-runtime-secret",
        "header-only-secret",
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "tuic-password-from-state",
    ):
        assert secret not in rendered
    assert "safe-public-key" not in rendered


def test_empty_and_unavailable_log_sources_remain_distinct_and_diagnostics_are_redacted() -> None:
    empty = ServiceLogService(
        state_store=MemoryStateStore(installation_with_secrets()),
        log_source=FixedRuntimeLogSource(
            RuntimeLogCapture(available=True, source_label="OpenRC syslog", lines=())
        ),
    ).read_recent()
    unavailable = ServiceLogService(
        state_store=MemoryStateStore(installation_with_secrets()),
        log_source=FixedRuntimeLogSource(
            RuntimeLogCapture(
                available=False,
                source_label="OpenRC syslog",
                lines=(),
                diagnostics="token=unknown-diagnostic-secret",
            )
        ),
    ).read_recent()

    assert empty == ServiceLogReport(
        condition=ServiceLogCondition.EMPTY,
        source_label="OpenRC syslog",
        lines=(),
        diagnostics="",
        redacted_occurrences=0,
        limit=200,
    )
    assert unavailable == ServiceLogReport(
        condition=ServiceLogCondition.UNAVAILABLE,
        source_label="OpenRC syslog",
        lines=(),
        diagnostics="token=[已脱敏]",
        redacted_occurrences=1,
        limit=200,
    )


def test_log_line_cap_includes_the_truncation_marker_after_redaction() -> None:
    source = FixedRuntimeLogSource(
        RuntimeLogCapture(
            available=True,
            source_label="test",
            lines=(f"password=line-only-secret {'x' * 5000}",),
        )
    )
    report = ServiceLogService(
        state_store=MemoryStateStore(),
        log_source=source,
    ).read_recent()

    assert len(report.lines[0]) == MAX_LOG_LINE_LENGTH
    assert report.lines[0].endswith("…[已截断]")
    assert "line-only-secret" not in report.lines[0]
    assert report.redacted_occurrences == 1


@pytest.mark.parametrize("limit", [0, -1, 501])
def test_log_limit_rejects_unbounded_or_invalid_requests(limit: int) -> None:
    source = FixedRuntimeLogSource(RuntimeLogCapture(available=True, source_label="test", lines=()))
    service = ServiceLogService(state_store=MemoryStateStore(), log_source=source)

    with pytest.raises(ValueError, match="between 1 and 500"):
        service.read_recent(limit=limit)

    assert source.limits == []
