import os
from pathlib import Path

import pytest

from sb_manager.cli import create_runtime
from sb_manager.release.host_runtime_acceptance import HostRuntimeAcceptance
from sb_manager.seams.runtime import RuntimeKind


@pytest.fixture(scope="session")
def host_runtime_acceptance() -> tuple[HostRuntimeAcceptance, str]:
    supplied_confirmation = os.environ.get("SB_MANAGER_HOST_SMOKE")
    if supplied_confirmation is None:
        pytest.skip("set SB_MANAGER_HOST_SMOKE to the exact confirmation from the read-only plan")
    configured_kind = os.environ.get("SB_MANAGER_HOST_RUNTIME")
    if configured_kind is None:
        pytest.fail("SB_MANAGER_HOST_RUNTIME must be systemd or openrc")
    try:
        runtime_kind = RuntimeKind(configured_kind)
    except ValueError:
        pytest.fail("SB_MANAGER_HOST_RUNTIME must be systemd or openrc")
    configured_binary = os.environ.get("SB_MANAGER_HOST_RUNTIME_BINARY")
    configured_service = os.environ.get("SB_MANAGER_HOST_SERVICE") or (
        "sing-box.service" if runtime_kind is RuntimeKind.SYSTEMD else "sing-box"
    )
    required_confirmation = f"refresh:{runtime_kind.value}:{configured_service}"
    if supplied_confirmation != required_confirmation:
        pytest.fail(f"SB_MANAGER_HOST_SMOKE must equal {required_confirmation}")
    runtime = create_runtime(
        runtime_kind=runtime_kind,
        binary=Path(configured_binary) if configured_binary is not None else None,
        service_name=configured_service,
    )
    return (
        HostRuntimeAcceptance(
            runtime=runtime,
            runtime_kind=runtime_kind,
            service_name=configured_service,
        ),
        supplied_confirmation,
    )


@pytest.mark.host
def test_configured_host_runtime_survives_authorized_refresh(
    host_runtime_acceptance: tuple[HostRuntimeAcceptance, str],
) -> None:
    acceptance, confirmation = host_runtime_acceptance

    result = acceptance.execute(confirmation=confirmation)

    assert result.final_diagnostics
