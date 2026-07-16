import json
import subprocess
import sys
from pathlib import Path

EX_NOPERM = 77


def test_installed_privileged_command_refuses_non_root_before_file_access() -> None:
    command = Path(sys.executable).with_name("sb-manager-privileged")
    request = json.dumps(
        {
            "schema_version": 1,
            "operation": "activate-core",
            "version": "1.14.0-alpha.45",
            "architecture": "amd64",
            "sha256": "a" * 64,
        }
    )

    completed = subprocess.run(
        [command],
        input=request,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == EX_NOPERM
    assert completed.stdout == ""
    assert json.loads(completed.stderr) == {
        "schema_version": 1,
        "status": "error",
        "error": "privilege-required",
        "message": "Privileged helper must run as root",
    }
