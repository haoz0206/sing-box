"""Run root-owned wheel and authorization acceptance in pinned Linux images."""

import argparse
import subprocess
import textwrap
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

BOOTSTRAP_ROOT = "/tmp/sb-manager-bootstrap"
PACKAGE_ROOT = "/opt/sing-box-manager"
HELPER = f"{PACKAGE_ROOT}/bin/sb-manager-privileged"
POLICY_INSTALLER = f"{PACKAGE_ROOT}/bin/sb-manager-install-policy"
ACCEPTANCE_TIMEOUT_SECONDS = 900


@dataclass(frozen=True, slots=True)
class DistroCase:
    """Pinned distribution and its native authorization commands."""

    name: str
    image: str
    authorization: str
    install_dependencies: str
    create_identity: str
    privilege_runner: str
    run_as_operator: str
    policy_path: str
    policy_mode: str


def _apt_install_dependencies() -> str:
    packages = "python3 python3-venv sudo ca-certificates"
    return (
        "for attempt in 1 2 3 4 5; do\n"
        "  if apt-get -o Acquire::Retries=5 update; then break; fi\n"
        '  test "$attempt" -eq 5 && exit 1\n'
        "  sleep 2\n"
        "done\n"
        "for attempt in 1 2 3 4 5; do\n"
        "  if DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=5 "
        f"install -y --no-install-recommends {packages}; then break; fi\n"
        '  test "$attempt" -eq 5 && exit 1\n'
        "  sleep 2\n"
        "done"
    )


DISTRO_CASES = {
    "debian12": DistroCase(
        name="Debian 12",
        image=(
            "docker.io/library/debian@"
            "sha256:63a496b5d3b99214b39f5ed70eb71a61e590a77979c79cbee4faf991f8c0783e"
        ),
        authorization="sudo",
        install_dependencies=_apt_install_dependencies(),
        create_identity=(
            "groupadd --system sing-box-manager\n"
            "useradd --create-home --gid sing-box-manager operator"
        ),
        privilege_runner="/usr/bin/sudo",
        run_as_operator="runuser -u operator -- {command}",
        policy_path="/etc/sudoers.d/sing-box-manager",
        policy_mode="440",
    ),
    "ubuntu2404": DistroCase(
        name="Ubuntu 24.04",
        image=(
            "docker.io/library/ubuntu@"
            "sha256:52df9b1ee71626e0088f7d400d5c6b5f7bb916f8f0c82b474289a4ece6cf3faf"
        ),
        authorization="sudo",
        install_dependencies=_apt_install_dependencies(),
        create_identity=(
            "groupadd --system sing-box-manager\n"
            "useradd --create-home --gid sing-box-manager operator"
        ),
        privilege_runner="/usr/bin/sudo",
        run_as_operator="runuser -u operator -- {command}",
        policy_path="/etc/sudoers.d/sing-box-manager",
        policy_mode="440",
    ),
    "alpine320": DistroCase(
        name="Alpine 3.20",
        image=(
            "docker.io/library/alpine@"
            "sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e"
        ),
        authorization="doas",
        install_dependencies="apk add --no-cache python3 py3-pip doas ca-certificates",
        create_identity=("addgroup -S sing-box-manager\nadduser -D -G sing-box-manager operator"),
        privilege_runner="/usr/bin/doas",
        run_as_operator='su operator -c "{command}"',
        policy_path="/etc/doas.d/sing-box-manager.conf",
        policy_mode="600",
    ),
}


def build_container_command(
    *,
    engine: str,
    case: DistroCase,
    wheel: Path,
    wheelhouse: Path | None,
    network: str | None,
) -> list[str]:
    """Build a no-host-shell container command for one immutable case."""
    wheel = wheel.resolve()
    command = [engine, "run", "--rm", "--pull=missing"]
    if network is not None:
        command.append(f"--network={network}")
    command.extend(("-v", f"{wheel}:/tmp/{wheel.name}:ro"))
    if wheelhouse is not None:
        command.extend(("-v", f"{wheelhouse.resolve()}:/tmp/wheelhouse:ro"))
    command.extend(
        (
            case.image,
            "/bin/sh",
            "-ceu",
            _container_script(
                case,
                wheel_name=wheel.name,
                use_wheelhouse=wheelhouse is not None,
            ),
        )
    )
    return command


def _container_script(
    case: DistroCase,
    *,
    wheel_name: str,
    use_wheelhouse: bool,
) -> str:
    bootstrap_install = (
        f"{BOOTSTRAP_ROOT}/bin/pip install --retries 5 --timeout 60 "
        "--no-index --find-links /tmp/wheelhouse "
        f"/tmp/{wheel_name}"
        if use_wheelhouse
        else (f"{BOOTSTRAP_ROOT}/bin/pip install --retries 5 --timeout 60 /tmp/{wheel_name}")
    )
    bootstrap_with_retry = (
        "for attempt in 1 2 3 4 5; do\n"
        f"  if {bootstrap_install}; then break; fi\n"
        '  test "$attempt" -eq 5 && exit 1\n'
        "  sleep 2\n"
        "done"
    )
    dependency_arguments = "--wheelhouse /tmp/wheelhouse" if use_wheelhouse else "--allow-index"
    package_install = (
        f"{BOOTSTRAP_ROOT}/bin/sb-manager-install --wheel /tmp/{wheel_name} "
        f"{dependency_arguments} --confirm"
    )
    policy_install = (
        f"{POLICY_INSTALLER} --authorization {case.authorization} "
        "--group sing-box-manager --confirm"
    )
    allowed_command = case.run_as_operator.format(command=f"{case.privilege_runner} -n {HELPER}")
    operator_manager_help = case.run_as_operator.format(
        command=f"{PACKAGE_ROOT}/bin/sb-manager --help"
    )
    denied_argument_command = case.run_as_operator.format(
        command=f"{case.privilege_runner} -n {HELPER} unexpected"
    )
    return textwrap.dedent(
        f"""
        {case.install_dependencies}
        {case.create_identity}
        python3 -m venv {BOOTSTRAP_ROOT}
        {bootstrap_with_retry}
        {package_install}
        test -L {PACKAGE_ROOT}/current
        test -x {PACKAGE_ROOT}/bin/sb-manager
        test -x {HELPER}
        {operator_manager_help} > /dev/null
        stat -c %a {HELPER} | grep -qx 755
        stat -c %U {HELPER} | grep -qx root
        {policy_install}
        printf '%s' '{{"schema_version":1,"operation":"inspect-config"}}' \
          > /tmp/inspection.json
        {allowed_command} < /tmp/inspection.json > /tmp/inspection-output
        grep -q '"status": "observed"' /tmp/inspection-output
        grep -q '"exists": false' /tmp/inspection-output
        printf "{{}}" > /tmp/request.json
        set +e
        {allowed_command} < /tmp/request.json > /tmp/helper-output 2>&1
        status=$?
        set -e
        test "$status" -eq 64
        grep -q invalid-request /tmp/helper-output
        set +e
        {denied_argument_command} < /tmp/request.json > /tmp/argument-output 2>&1
        argument_status=$?
        set -e
        test "$argument_status" -ne 0
        if grep -q "accepts no arguments" /tmp/argument-output; then exit 1; fi
        stat -c %a {case.policy_path} | grep -qx {case.policy_mode}
        stat -c %a /var/lib/sing-box-manager/incoming | grep -qx 770
        stat -c %G /var/lib/sing-box-manager/incoming | grep -qx sing-box-manager
        printf "DISTRO_POLICY_ACCEPTANCE_OK {case.name}\\n"
        """
    ).strip()


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run pinned distro acceptance for root-owned helper authorization"
    )
    parser.add_argument("--wheel", type=Path, required=True)
    dependency_source = parser.add_mutually_exclusive_group(required=True)
    dependency_source.add_argument("--wheelhouse", type=Path)
    dependency_source.add_argument(
        "--allow-index",
        action="store_true",
        help="explicitly allow pip to resolve dependencies from its configured index",
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=tuple(DISTRO_CASES),
        dest="cases",
    )
    parser.add_argument("--engine", default="podman")
    parser.add_argument("--network", help="optional container network, for example host")
    arguments = parser.parse_args(argv)
    if not arguments.wheel.is_file() or arguments.wheel.suffix != ".whl":
        parser.error("--wheel must be an existing wheel file")
    if arguments.wheelhouse is not None and not arguments.wheelhouse.is_dir():
        parser.error("--wheelhouse must be an existing directory")
    selected_cases = arguments.cases or list(DISTRO_CASES)
    for case_name in selected_cases:
        case = DISTRO_CASES[case_name]
        print(f"==> {case.name}: {case.image}", flush=True)
        command = build_container_command(
            engine=arguments.engine,
            case=case,
            wheel=arguments.wheel,
            wheelhouse=arguments.wheelhouse,
            network=arguments.network,
        )
        try:
            subprocess.run(command, check=True, timeout=ACCEPTANCE_TIMEOUT_SECONDS)
        except subprocess.CalledProcessError as error:
            raise SystemExit(error.returncode) from error
        except subprocess.TimeoutExpired as error:
            raise SystemExit(f"Acceptance timed out for {case.name}") from error


if __name__ == "__main__":
    main()
