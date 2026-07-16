"""Root-only command that installs the fixed helper authorization policy."""

import argparse
import grp
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from sb_manager.adapters.authorization_policy_validator import (
    SubprocessAuthorizationPolicyValidator,
)
from sb_manager.installation.privileged_policy import (
    AuthorizationProvider,
    HostOwnershipPolicy,
    HostPolicyInstaller,
    HostPolicyInstallError,
    PosixFileOwnership,
)

EX_NOPERM = 77
EX_CONFIG = 78
ROOT_UID = 0
HOST_ROOT = Path("/")


def main(argv: Sequence[str] | None = None) -> None:
    """Install one native authorization fragment after root and group checks."""
    if os.geteuid() != ROOT_UID:
        _write_error(
            error="privilege-required",
            message="Policy installer must run as root",
        )
        raise SystemExit(EX_NOPERM)
    parser = argparse.ArgumentParser(
        prog="sb-manager-install-policy",
        description="安装 sing-box manager 最小权限 helper 授权策略",
    )
    parser.add_argument(
        "--authorization",
        required=True,
        choices=tuple(provider.value for provider in AuthorizationProvider),
        help="Debian/Ubuntu 使用 sudo，Alpine 使用 doas",
    )
    parser.add_argument(
        "--group",
        default="sing-box-manager",
        help="已经存在且包含获授权运维用户的专用组",
    )
    arguments = parser.parse_args(argv)
    try:
        root_gid = grp.getgrnam("root").gr_gid
        manager_gid = grp.getgrnam(arguments.group).gr_gid
    except KeyError as error:
        _write_error(
            error="unknown-group",
            message=f"Required POSIX group does not exist: {error.args[0]}",
        )
        raise SystemExit(EX_CONFIG) from error
    try:
        result = HostPolicyInstaller(
            root=HOST_ROOT,
            ownership_policy=HostOwnershipPolicy(
                root_uid=ROOT_UID,
                root_gid=root_gid,
                manager_gid=manager_gid,
            ),
            validator=SubprocessAuthorizationPolicyValidator(),
            ownership=PosixFileOwnership(),
        ).install(
            AuthorizationProvider(arguments.authorization),
            group_name=arguments.group,
        )
    except (HostPolicyInstallError, OSError, ValueError) as error:
        _write_error(error="install-rejected", message=str(error))
        raise SystemExit(EX_CONFIG) from error
    sys.stdout.write(
        json.dumps(
            {
                "status": "installed",
                "provider": result.provider.value,
                "authorization_path": str(result.authorization_path),
                "helper_path": str(result.helper_path),
            },
            sort_keys=True,
        )
        + "\n"
    )


def _write_error(*, error: str, message: str) -> None:
    sys.stderr.write(
        json.dumps(
            {
                "status": "error",
                "error": error,
                "message": message,
            },
            sort_keys=True,
        )
        + "\n"
    )
