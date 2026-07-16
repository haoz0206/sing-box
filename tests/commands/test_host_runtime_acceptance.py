import json

import pytest

from sb_manager.release import host_runtime_acceptance
from sb_manager.release.host_runtime_acceptance import (
    HostRuntimeAcceptance,
    HostRuntimeAuthorizationError,
    HostRuntimePostconditionError,
    HostRuntimePreconditionError,
    HostRuntimeRefreshError,
)
from sb_manager.seams.runtime import (
    RuntimeKind,
    RuntimePostcondition,
    RuntimeRefreshResult,
)


class RecordingRuntime:
    def __init__(
        self,
        *,
        health: tuple[RuntimePostcondition, ...],
        refresh: RuntimeRefreshResult | None = None,
    ) -> None:
        self.health = list(health)
        self.refresh_result = refresh or RuntimeRefreshResult(True, "refreshed")
        self.events: list[str] = []

    def refresh(self) -> RuntimeRefreshResult:
        self.events.append("refresh")
        return self.refresh_result

    def check_health(self) -> RuntimePostcondition:
        self.events.append("health")
        return self.health.pop(0)

    def recovery_instructions(self) -> tuple[str, ...]:
        return ("restart sing-box", "inspect sing-box")


def healthy(diagnostics: str) -> RuntimePostcondition:
    return RuntimePostcondition(healthy=True, diagnostics=diagnostics)


def unhealthy(diagnostics: str) -> RuntimePostcondition:
    return RuntimePostcondition(healthy=False, diagnostics=diagnostics)


def acceptance(runtime: RecordingRuntime) -> HostRuntimeAcceptance:
    return HostRuntimeAcceptance(
        runtime=runtime,
        runtime_kind=RuntimeKind.SYSTEMD,
        service_name="sing-box.service",
    )


def test_plan_is_read_only_and_binds_confirmation_to_runtime_and_service() -> None:
    runtime = RecordingRuntime(health=(healthy("active"), healthy("active")))

    plan = acceptance(runtime).plan()

    assert plan.runtime_kind is RuntimeKind.SYSTEMD
    assert plan.service_name == "sing-box.service"
    assert plan.required_confirmation == "refresh:systemd:sing-box.service"
    assert plan.mutates_host is False
    assert plan.recovery_instructions == ("restart sing-box", "inspect sing-box")
    assert runtime.events == []


def test_wrong_confirmation_is_rejected_before_host_observation() -> None:
    runtime = RecordingRuntime(health=(healthy("active"), healthy("active")))

    with pytest.raises(
        HostRuntimeAuthorizationError,
        match=r"refresh:systemd:sing-box\.service",
    ):
        acceptance(runtime).execute(confirmation="refresh")

    assert runtime.events == []


def test_unhealthy_initial_service_is_not_refreshed() -> None:
    runtime = RecordingRuntime(health=(unhealthy("inactive before test"),))

    with pytest.raises(HostRuntimePreconditionError, match="inactive before test"):
        acceptance(runtime).execute(confirmation="refresh:systemd:sing-box.service")

    assert runtime.events == ["health"]


def test_success_requires_healthy_state_before_and_after_refresh() -> None:
    runtime = RecordingRuntime(health=(healthy("active before"), healthy("active after")))

    result = acceptance(runtime).execute(confirmation="refresh:systemd:sing-box.service")

    assert runtime.events == ["health", "refresh", "health"]
    assert result.initial_diagnostics == "active before"
    assert result.refresh_diagnostics == "refreshed"
    assert result.final_diagnostics == "active after"


def test_refresh_failure_reports_recovery_without_claiming_postcondition() -> None:
    runtime = RecordingRuntime(
        health=(healthy("active before"),),
        refresh=RuntimeRefreshResult(False, "restart failed"),
    )

    with pytest.raises(HostRuntimeRefreshError) as error_info:
        acceptance(runtime).execute(confirmation="refresh:systemd:sing-box.service")

    assert runtime.events == ["health", "refresh"]
    assert "restart failed" in str(error_info.value)
    assert "restart sing-box" in str(error_info.value)


def test_unhealthy_postcondition_reports_recovery() -> None:
    runtime = RecordingRuntime(health=(healthy("active before"), unhealthy("failed after")))

    with pytest.raises(HostRuntimePostconditionError) as error_info:
        acceptance(runtime).execute(confirmation="refresh:systemd:sing-box.service")

    assert runtime.events == ["health", "refresh", "health"]
    assert "failed after" in str(error_info.value)
    assert "inspect sing-box" in str(error_info.value)


def test_service_name_cannot_be_an_init_system_option() -> None:
    runtime = RecordingRuntime(health=(healthy("active"), healthy("active")))

    with pytest.raises(ValueError, match="service name"):
        HostRuntimeAcceptance(
            runtime=runtime,
            runtime_kind=RuntimeKind.SYSTEMD,
            service_name="--system",
        )


def test_command_defaults_to_a_json_plan_without_runtime_commands(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RecordingRuntime(health=(healthy("active"), healthy("active")))
    monkeypatch.setattr(host_runtime_acceptance, "create_runtime", lambda **_: runtime)

    host_runtime_acceptance.main(["--runtime", "systemd"])

    assert json.loads(capsys.readouterr().out) == {
        "mutates_host": False,
        "recovery_instructions": ["restart sing-box", "inspect sing-box"],
        "required_confirmation": "refresh:systemd:sing-box.service",
        "runtime": "systemd",
        "service": "sing-box.service",
        "status": "planned",
    }
    assert runtime.events == []


def test_confirmed_command_reports_completed_observations(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = RecordingRuntime(health=(healthy("active before"), healthy("active after")))
    monkeypatch.setattr(host_runtime_acceptance, "create_runtime", lambda **_: runtime)

    host_runtime_acceptance.main(
        [
            "--runtime",
            "systemd",
            "--confirm-service-refresh",
            "refresh:systemd:sing-box.service",
        ]
    )

    assert json.loads(capsys.readouterr().out) == {
        "final_diagnostics": "active after",
        "initial_diagnostics": "active before",
        "refresh_diagnostics": "refreshed",
        "runtime": "systemd",
        "service": "sing-box.service",
        "status": "accepted",
    }
