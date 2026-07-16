"""Installed single-shot root helper with a fixed allowlisted policy."""

import json
import os
import sys
from pathlib import Path

from sb_manager.adapters.file_config_target import FileConfigurationTargetInspector
from sb_manager.artifacts.installation import CoreInstallError
from sb_manager.privileged.config_apply import (
    ApplyConfigRequest,
    PrivilegedConfigApplyPolicy,
    PrivilegedConfigApplyService,
)
from sb_manager.privileged.core_install import (
    PrivilegedCoreInstallPolicy,
    PrivilegedCoreInstallService,
)
from sb_manager.privileged.errors import PrivilegedInputError
from sb_manager.privileged.protocol import (
    MAX_REQUEST_BYTES,
    REQUEST_SCHEMA_VERSION,
    PrivilegedProtocolError,
    execute_privileged_request,
)
from sb_manager.privileged.runtime_policy import HostRuntimePolicyError, create_host_runtime
from sb_manager.seams.apply_lock import ApplyLockUnavailableError
from sb_manager.seams.artifact_source import (
    ArtifactArchiveError,
    ArtifactIntegrityError,
    ArtifactVersionError,
)
from sb_manager.transactions.apply import ApplyTransactionResult

EX_NOPERM = 77
EX_USAGE = 64
EX_SOFTWARE = 70

HOST_POLICY = PrivilegedCoreInstallPolicy(
    incoming_directory=Path("/var/lib/sing-box-manager/incoming"),
    working_directory=Path("/var/lib/sing-box-manager/work"),
    installation_root=Path("/opt/sing-box-manager/core"),
    lock_path=Path("/run/lock/sing-box-manager-core.lock"),
)
HOST_CONFIG_POLICY = PrivilegedConfigApplyPolicy(
    incoming_directory=Path("/var/lib/sing-box-manager/incoming"),
    working_directory=Path("/var/lib/sing-box-manager/work"),
    config_path=Path("/etc/sing-box/config.json"),
    core_binary=Path("/opt/sing-box-manager/core/current/sing-box"),
    lock_path=Path("/run/lock/sing-box-manager-apply.lock"),
)


class HostConfigApplier:
    """Delay fixed init-system detection until an apply request needs it."""

    def apply_config(self, request: ApplyConfigRequest) -> ApplyTransactionResult:
        return PrivilegedConfigApplyService(
            policy=HOST_CONFIG_POLICY,
            runtime=create_host_runtime(),
        ).apply_config(request)


def main() -> None:
    """Execute one root-only request using the compiled host policy."""
    if os.geteuid() != 0:
        _write_error(
            error="privilege-required",
            message="Privileged helper must run as root",
        )
        raise SystemExit(EX_NOPERM)
    if len(sys.argv) != 1:
        _write_error(error="invalid-request", message="Privileged helper accepts no arguments")
        raise SystemExit(EX_USAGE)

    request_text = sys.stdin.read(MAX_REQUEST_BYTES + 1)
    try:
        result = execute_privileged_request(
            request_text,
            effective_user_id=os.geteuid(),
            core_activator=PrivilegedCoreInstallService(policy=HOST_POLICY),
            config_applier=HostConfigApplier(),
            config_inspector=FileConfigurationTargetInspector(
                config_path=HOST_CONFIG_POLICY.config_path
            ),
        )
    except PrivilegedProtocolError as error:
        _write_error(error="invalid-request", message=str(error))
        raise SystemExit(EX_USAGE) from error
    except (
        ApplyLockUnavailableError,
        ArtifactArchiveError,
        ArtifactIntegrityError,
        ArtifactVersionError,
        CoreInstallError,
        HostRuntimePolicyError,
        PrivilegedInputError,
    ) as error:
        _write_error(error="operation-rejected", message=str(error))
        raise SystemExit(1) from error
    except Exception as error:
        _write_error(error="internal-error", message="Privileged operation failed")
        raise SystemExit(EX_SOFTWARE) from error

    sys.stdout.write(f"{result}\n")


def _write_error(*, error: str, message: str) -> None:
    sys.stderr.write(
        json.dumps(
            {
                "schema_version": REQUEST_SCHEMA_VERSION,
                "status": "error",
                "error": error,
                "message": message,
            },
            sort_keys=True,
        )
        + "\n"
    )
