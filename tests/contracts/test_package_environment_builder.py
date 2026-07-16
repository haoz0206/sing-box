import json
from pathlib import Path

from sb_manager.adapters.package_environment import SubprocessPackageEnvironmentBuilder
from sb_manager.seams.package_environment import PackageEnvironmentBuildRequest


def _write_fake_python(path: Path, *, log_path: Path) -> Path:
    path.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import shutil\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"log = Path({str(log_path)!r})\n"
        "with log.open('a', encoding='utf-8') as output:\n"
        "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['-m', 'venv']:\n"
        "    binary = Path(sys.argv[3]) / 'bin/python'\n"
        "    binary.parent.mkdir(parents=True)\n"
        "    shutil.copy2(__file__, binary)\n"
        "    binary.chmod(0o755)\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_environment_builder_uses_only_the_selected_offline_wheelhouse(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "commands.jsonl"
    python_binary = _write_fake_python(tmp_path / "python3", log_path=log_path)
    release_directory = tmp_path / "release"
    release_directory.mkdir()
    wheel = release_directory / "sing_box_manager-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"fixture wheel")
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    builder = SubprocessPackageEnvironmentBuilder(python_binary=python_binary)

    builder.build(
        PackageEnvironmentBuildRequest(
            release_directory=release_directory,
            wheel_path=wheel,
            wheelhouse=wheelhouse,
            allow_index=False,
        )
    )

    commands = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert commands == [
        ["-m", "venv", str(release_directory / "venv")],
        [
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--retries",
            "5",
            "--timeout",
            "60",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            str(wheel),
        ],
    ]
