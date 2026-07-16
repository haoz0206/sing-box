from pathlib import Path

from sb_manager.release.distro_policy_acceptance import DISTRO_CASES, build_container_command


def test_acceptance_images_are_immutable_and_cover_target_families() -> None:
    assert set(DISTRO_CASES) == {"debian12", "ubuntu2404", "alpine320"}
    assert all("@sha256:" in case.image for case in DISTRO_CASES.values())
    assert DISTRO_CASES["debian12"].authorization == "sudo"
    assert DISTRO_CASES["ubuntu2404"].authorization == "sudo"
    assert DISTRO_CASES["alpine320"].authorization == "doas"


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
    assert "pip install /tmp/sing_box_manager-0.1.0-py3-none-any.whl" in command[-1]
    assert (
        "sb-manager-install-policy --authorization sudo --group sing-box-manager --confirm"
    ) in command[-1]


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
        "pip install --no-index --find-links /tmp/wheelhouse "
        "/tmp/sing_box_manager-0.1.0-py3-none-any.whl"
    ) in command[-1]
