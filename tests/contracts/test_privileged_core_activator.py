import json
from pathlib import Path

import pytest

from sb_manager.adapters.privileged_core_activator import (
    PrivilegedCoreActivator,
    PrivilegedCoreHelperExecutionError,
    PrivilegedCoreHelperProtocolError,
)
from sb_manager.artifacts.installation import CoreActivation, CoreReleaseIdentity
from sb_manager.seams.artifact_source import ArtifactArchitecture
from sb_manager.seams.core_activator import CoreActivationRequest
from sb_manager.seams.core_switcher import CoreSwitchRequest

VERSION = "1.14.0-alpha.45"


def activation_response(
    *,
    status: str = "activated",
    version: str = VERSION,
    previous_target: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": status,
        "activation": {
            "version": version,
            "distribution_directory": "/opt/sing-box-manager/core/versions/release",
            "binary_path": "/opt/sing-box-manager/core/current/sing-box",
            "activated_target": "versions/release",
            "previous_target": previous_target,
        },
    }


def request() -> CoreActivationRequest:
    return CoreActivationRequest(
        version=VERSION,
        architecture=ArtifactArchitecture.AMD64,
        sha256="a" * 64,
    )


def switch_request() -> CoreSwitchRequest:
    return CoreSwitchRequest(
        target=CoreReleaseIdentity(
            version="1.13.14",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="a" * 64,
        ),
        expected_active=CoreReleaseIdentity(
            version="1.14.0-alpha.46",
            architecture=ArtifactArchitecture.AMD64,
            source_sha256="b" * 64,
        ),
    )


def test_exact_request_is_sent_and_complete_activation_is_restored(tmp_path: Path) -> None:
    log_path = tmp_path / "request.json"
    helper = tmp_path / "privileged-helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        f"Path({str(log_path)!r}).write_text(json.dumps(request), encoding='utf-8')\n"
        f"print({json.dumps(activation_response())!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    activation = PrivilegedCoreActivator(helper_command=(str(helper),)).activate_core(request())

    assert activation == CoreActivation(
        version=VERSION,
        distribution_directory=Path("/opt/sing-box-manager/core/versions/release"),
        binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
        activated_target="versions/release",
        previous_target=None,
    )
    assert json.loads(log_path.read_text()) == {
        "schema_version": 1,
        "operation": "activate-core",
        "version": VERSION,
        "architecture": "amd64",
        "sha256": "a" * 64,
    }


def test_exact_retained_switch_request_restores_complete_activation(tmp_path: Path) -> None:
    log_path = tmp_path / "request.json"
    helper = tmp_path / "privileged-helper"
    response = activation_response(
        status="switched",
        version="1.13.14",
        previous_target="versions/preview",
    )
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        f"Path({str(log_path)!r}).write_text(json.dumps(request), encoding='utf-8')\n"
        f"print({json.dumps(response)!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    activation = PrivilegedCoreActivator(helper_command=(str(helper),)).switch_core(
        switch_request()
    )

    assert activation == CoreActivation(
        version="1.13.14",
        distribution_directory=Path("/opt/sing-box-manager/core/versions/release"),
        binary_path=Path("/opt/sing-box-manager/core/current/sing-box"),
        activated_target="versions/release",
        previous_target="versions/preview",
    )
    assert json.loads(log_path.read_text()) == {
        "schema_version": 1,
        "operation": "switch-core",
        "target": {
            "version": "1.13.14",
            "architecture": "amd64",
            "sha256": "a" * 64,
        },
        "expected_active": {
            "version": "1.14.0-alpha.46",
            "architecture": "amd64",
            "sha256": "b" * 64,
        },
    }


def test_helper_failure_is_an_operational_activation_error(tmp_path: Path) -> None:
    helper = tmp_path / "rejecting-helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('authorization denied', file=sys.stderr)\n"
        "raise SystemExit(77)\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    with pytest.raises(PrivilegedCoreHelperExecutionError, match="authorization denied"):
        PrivilegedCoreActivator(helper_command=(str(helper),)).activate_core(request())


def test_helper_response_requires_exact_fields_and_matching_version(tmp_path: Path) -> None:
    response = activation_response()
    activation = response["activation"]
    assert isinstance(activation, dict)
    activation["version"] = "1.14.0-alpha.44"
    activation["unexpected"] = True
    helper = tmp_path / "malformed-helper"
    helper.write_text(
        f"#!/usr/bin/env python3\nprint({json.dumps(response)!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    with pytest.raises(PrivilegedCoreHelperProtocolError, match="fields must be exactly"):
        PrivilegedCoreActivator(helper_command=(str(helper),)).activate_core(request())


def test_helper_response_version_must_match_request(tmp_path: Path) -> None:
    response = activation_response()
    activation = response["activation"]
    assert isinstance(activation, dict)
    activation["version"] = "1.14.0-alpha.44"
    helper = tmp_path / "wrong-version-helper"
    helper.write_text(
        f"#!/usr/bin/env python3\nprint({json.dumps(response)!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    with pytest.raises(PrivilegedCoreHelperProtocolError, match="does not match request"):
        PrivilegedCoreActivator(helper_command=(str(helper),)).activate_core(request())
