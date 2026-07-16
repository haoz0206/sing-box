from sb_manager.application.host_diagnostics import (
    HostCondition,
    HostDiagnosticsReport,
    RuntimeHostDiagnostics,
)
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult


class StubRuntime:
    def __init__(self, postcondition: RuntimePostcondition) -> None:
        self.postcondition = postcondition
        self.health_checks = 0

    def refresh(self) -> RuntimeRefreshResult:
        raise AssertionError("diagnostics must not mutate the runtime")

    def check_health(self) -> RuntimePostcondition:
        self.health_checks += 1
        return self.postcondition

    def recovery_instructions(self) -> tuple[str, ...]:
        return (
            "运行 systemctl restart sing-box.service。",
            "运行 systemctl status sing-box.service --no-pager。",
        )


def test_runtime_diagnostics_reports_a_healthy_service_without_recovery_actions() -> None:
    runtime = StubRuntime(RuntimePostcondition(healthy=True, diagnostics="active"))

    report = RuntimeHostDiagnostics(runtime=runtime).inspect()

    assert report == HostDiagnosticsReport(
        condition=HostCondition.HEALTHY,
        summary="sing-box 服务运行正常",
        diagnostics="active",
        recovery_instructions=(),
    )
    assert runtime.health_checks == 1


def test_runtime_diagnostics_turns_an_unhealthy_result_into_actionable_guidance() -> None:
    runtime = StubRuntime(
        RuntimePostcondition(
            healthy=False,
            diagnostics="sing-box.service is inactive",
        )
    )

    report = RuntimeHostDiagnostics(runtime=runtime).inspect()

    assert report == HostDiagnosticsReport(
        condition=HostCondition.UNHEALTHY,
        summary="sing-box 服务未通过健康检查",
        diagnostics="sing-box.service is inactive",
        recovery_instructions=(
            "运行 systemctl restart sing-box.service。",
            "运行 systemctl status sing-box.service --no-pager。",
        ),
    )
