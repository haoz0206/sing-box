"""Opt-in live host acceptance with service-bound mutation authorization."""

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sb_manager.cli import create_runtime
from sb_manager.seams.runtime import Runtime, RuntimeKind

SAFE_SERVICE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.@-]*")
EX_CONFIG = 78


class HostRuntimeAcceptanceError(RuntimeError):
    """A live runtime acceptance could not establish its safety contract."""


class HostRuntimeAuthorizationError(HostRuntimeAcceptanceError):
    """The supplied confirmation does not authorize this exact service refresh."""


class HostRuntimePreconditionError(HostRuntimeAcceptanceError):
    """The configured service was not healthy before the requested mutation."""


class HostRuntimeRefreshError(HostRuntimeAcceptanceError):
    """The init system rejected or failed the service refresh."""


class HostRuntimePostconditionError(HostRuntimeAcceptanceError):
    """The configured service was not healthy after the refresh."""


@dataclass(frozen=True, slots=True)
class HostRuntimeAcceptancePlan:
    """Read-only evidence required before one exact live service refresh."""

    runtime_kind: RuntimeKind
    service_name: str
    required_confirmation: str
    recovery_instructions: tuple[str, ...]
    mutates_host: bool = False


@dataclass(frozen=True, slots=True)
class HostRuntimeAcceptanceResult:
    """Observations proving one live service survived an authorized refresh."""

    runtime_kind: RuntimeKind
    service_name: str
    initial_diagnostics: str
    refresh_diagnostics: str
    final_diagnostics: str


class HostRuntimeAcceptance:
    """Plan and execute the complete live-runtime acceptance protocol."""

    def __init__(
        self,
        *,
        runtime: Runtime,
        runtime_kind: RuntimeKind,
        service_name: str,
    ) -> None:
        if SAFE_SERVICE_NAME.fullmatch(service_name) is None:
            raise ValueError(f"Invalid service name: {service_name!r}")
        self._runtime = runtime
        self._runtime_kind = runtime_kind
        self._service_name = service_name

    def plan(self) -> HostRuntimeAcceptancePlan:
        """Describe the exact mutation and recovery path without observing the host."""
        return HostRuntimeAcceptancePlan(
            runtime_kind=self._runtime_kind,
            service_name=self._service_name,
            required_confirmation=(f"refresh:{self._runtime_kind.value}:{self._service_name}"),
            recovery_instructions=self._runtime.recovery_instructions(),
        )

    def execute(self, *, confirmation: str) -> HostRuntimeAcceptanceResult:
        """Refresh only an initially healthy service under exact authorization."""
        plan = self.plan()
        if confirmation != plan.required_confirmation:
            raise HostRuntimeAuthorizationError(
                f"Exact confirmation required: {plan.required_confirmation}"
            )
        initial = self._runtime.check_health()
        if not initial.healthy:
            raise HostRuntimePreconditionError(
                "Refusing to refresh a service that was not initially healthy: "
                f"{initial.diagnostics}"
            )
        refresh = self._runtime.refresh()
        if not refresh.success:
            raise HostRuntimeRefreshError(
                _failure_message(
                    summary=f"Service refresh failed: {refresh.diagnostics}",
                    recovery=plan.recovery_instructions,
                )
            )
        final = self._runtime.check_health()
        if not final.healthy:
            raise HostRuntimePostconditionError(
                _failure_message(
                    summary=f"Service was unhealthy after refresh: {final.diagnostics}",
                    recovery=plan.recovery_instructions,
                )
            )
        return HostRuntimeAcceptanceResult(
            runtime_kind=self._runtime_kind,
            service_name=self._service_name,
            initial_diagnostics=initial.diagnostics,
            refresh_diagnostics=refresh.diagnostics,
            final_diagnostics=final.diagnostics,
        )


def main(argv: Sequence[str] | None = None) -> None:
    """Preview or execute one service-bound live host acceptance."""
    parser = argparse.ArgumentParser(
        description="Preview or run an explicitly authorized live sing-box service refresh"
    )
    parser.add_argument("--runtime", choices=("systemd", "openrc"), required=True)
    parser.add_argument("--runtime-binary", type=Path)
    parser.add_argument("--service")
    parser.add_argument(
        "--confirm-service-refresh",
        help="exact confirmation printed by the read-only plan",
    )
    arguments = parser.parse_args(argv)
    runtime_kind = RuntimeKind(arguments.runtime)
    service_name = arguments.service or _default_service(runtime_kind)
    try:
        runtime = create_runtime(
            runtime_kind=runtime_kind,
            binary=arguments.runtime_binary,
            service_name=service_name,
        )
        acceptance = HostRuntimeAcceptance(
            runtime=runtime,
            runtime_kind=runtime_kind,
            service_name=service_name,
        )
        if arguments.confirm_service_refresh is None:
            _write_plan(acceptance.plan())
            return
        _write_result(acceptance.execute(confirmation=arguments.confirm_service_refresh))
    except (HostRuntimeAcceptanceError, OSError, ValueError) as error:
        _write_error(str(error))
        raise SystemExit(EX_CONFIG) from error


def _default_service(runtime_kind: RuntimeKind) -> str:
    return "sing-box.service" if runtime_kind is RuntimeKind.SYSTEMD else "sing-box"


def _failure_message(*, summary: str, recovery: tuple[str, ...]) -> str:
    return f"{summary} Recovery: {' '.join(recovery)}"


def _write_plan(plan: HostRuntimeAcceptancePlan) -> None:
    _write_json(
        {
            "status": "planned",
            "runtime": plan.runtime_kind.value,
            "service": plan.service_name,
            "required_confirmation": plan.required_confirmation,
            "recovery_instructions": list(plan.recovery_instructions),
            "mutates_host": plan.mutates_host,
        }
    )


def _write_result(result: HostRuntimeAcceptanceResult) -> None:
    _write_json(
        {
            "status": "accepted",
            "runtime": result.runtime_kind.value,
            "service": result.service_name,
            "initial_diagnostics": result.initial_diagnostics,
            "refresh_diagnostics": result.refresh_diagnostics,
            "final_diagnostics": result.final_diagnostics,
        }
    )


def _write_error(message: str) -> None:
    sys.stderr.write(
        json.dumps(
            {"status": "error", "error": "host-runtime-acceptance-rejected", "message": message},
            sort_keys=True,
        )
        + "\n"
    )


def _write_json(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
