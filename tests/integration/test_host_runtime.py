import os
from pathlib import Path

import pytest

from sb_manager.cli import create_runtime
from sb_manager.seams.runtime import Runtime, RuntimeKind


@pytest.fixture(scope="session")
def host_runtime() -> Runtime:
    if os.environ.get("SB_MANAGER_HOST_SMOKE") != "refresh":
        pytest.skip("set SB_MANAGER_HOST_SMOKE=refresh to authorize a service refresh")
    configured_kind = os.environ.get("SB_MANAGER_HOST_RUNTIME")
    if configured_kind is None:
        pytest.fail("SB_MANAGER_HOST_RUNTIME must be systemd or openrc")
    try:
        runtime_kind = RuntimeKind(configured_kind)
    except ValueError:
        pytest.fail("SB_MANAGER_HOST_RUNTIME must be systemd or openrc")
    configured_binary = os.environ.get("SB_MANAGER_HOST_RUNTIME_BINARY")
    configured_service = os.environ.get("SB_MANAGER_HOST_SERVICE")
    return create_runtime(
        runtime_kind=runtime_kind,
        binary=Path(configured_binary) if configured_binary is not None else None,
        service_name=configured_service,
    )


@pytest.mark.host
def test_configured_host_runtime_refreshes_and_returns_healthy(host_runtime: Runtime) -> None:
    refresh = host_runtime.refresh()
    assert refresh.success, refresh.diagnostics

    postcondition = host_runtime.check_health()
    assert postcondition.healthy, postcondition.diagnostics
