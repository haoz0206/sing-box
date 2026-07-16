from pathlib import Path

from sb_manager.release.distro_policy_acceptance import DISTRO_CASES, build_container_command

APT_PHASE_COUNT = 2
TOTAL_RETRYING_PHASE_COUNT = 3


def test_acceptance_images_are_immutable_and_cover_target_families() -> None:
    assert set(DISTRO_CASES) == {"debian12", "ubuntu2404", "alpine320"}
    assert all("@sha256:" in case.image for case in DISTRO_CASES.values())
    assert DISTRO_CASES["debian12"].authorization == "sudo"
    assert DISTRO_CASES["ubuntu2404"].authorization == "sudo"
    assert DISTRO_CASES["alpine320"].authorization == "doas"


def test_apt_based_acceptance_retries_transient_package_proxy_failures() -> None:
    for case_name in ("debian12", "ubuntu2404"):
        commands = DISTRO_CASES[case_name].install_dependencies
        assert "apt-get -o Acquire::Retries=5 update" in commands
        assert "apt-get -o Acquire::Retries=5 install" in commands
        assert commands.count("for attempt in 1 2 3 4 5; do") == APT_PHASE_COUNT
        assert commands.count('test "$attempt" -eq 5 && exit 1') == APT_PHASE_COUNT
        assert commands.count("sleep 2") == APT_PHASE_COUNT


def test_container_command_preserves_wheel_name_and_explicit_network(tmp_path: Path) -> None:
    wheel = tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")

    command = build_container_command(
        engine="podman",
        case=DISTRO_CASES["debian12"],
        wheel=wheel,
        wheelhouse=None,
        network="host",
    )

    assert command[:4] == ["podman", "run", "--rm", "--pull=missing"]
    assert "--network=host" in command
    assert f"{wheel.resolve()}:/tmp/sing_box_manager-0.1.0-py3-none-any.whl:ro" in command
    assert command[-3:-1] == ["/bin/sh", "-ceu"]
    assert (
        "/tmp/sb-manager-bootstrap/bin/pip install --retries 5 --timeout 60 "
        "/tmp/sing_box_manager-0.1.0-py3-none-any.whl"
    ) in command[-1]
    assert command[-1].count("for attempt in 1 2 3 4 5; do") == TOTAL_RETRYING_PHASE_COUNT
    assert (
        "/tmp/sb-manager-bootstrap/bin/sb-manager-install --wheel "
        "/tmp/sing_box_manager-0.1.0-py3-none-any.whl --allow-index --confirm"
    ) in command[-1]
    assert (
        "/opt/sing-box-manager/bin/sb-manager-install-policy --authorization sudo "
        "--group sing-box-manager --confirm"
    ) in command[-1]
    assert "test -L /opt/sing-box-manager/current" in command[-1]
    assert "runuser -u operator -- /opt/sing-box-manager/bin/sb-manager --help" in command[-1]
    assert "stat -c %U /opt/sing-box-manager/bin/sb-manager-privileged" in command[-1]
    assert '"operation":"inspect-config"' in command[-1]
    assert "inspection-output" in command[-1]
    assert '"status": "observed"' in command[-1]


def test_reviewed_wheelhouse_disables_package_index(tmp_path: Path) -> None:
    wheel = tmp_path / "sing_box_manager-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()

    command = build_container_command(
        engine="podman",
        case=DISTRO_CASES["alpine320"],
        wheel=wheel,
        wheelhouse=wheelhouse,
        network=None,
    )

    assert "--network=host" not in command
    assert f"{wheelhouse.resolve()}:/tmp/wheelhouse:ro" in command
    assert (
        "/tmp/sb-manager-bootstrap/bin/pip install --retries 5 --timeout 60 "
        "--no-index --find-links /tmp/wheelhouse "
        "/tmp/sing_box_manager-0.1.0-py3-none-any.whl"
    ) in command[-1]
    assert (
        "/tmp/sb-manager-bootstrap/bin/sb-manager-install --wheel "
        "/tmp/sing_box_manager-0.1.0-py3-none-any.whl "
        "--wheelhouse /tmp/wheelhouse --confirm"
    ) in command[-1]
