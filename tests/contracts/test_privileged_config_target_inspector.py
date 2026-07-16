import json
from pathlib import Path

import pytest

from sb_manager.adapters.privileged_config_target import (
    PrivilegedConfigInspectionProtocolError,
    PrivilegedConfigurationTargetInspector,
)
from sb_manager.seams.config_target import LiveConfigObservation


def test_privileged_inspector_requests_only_redacted_config_identity(tmp_path: Path) -> None:
    request_log = tmp_path / "request.json"
    helper = tmp_path / "helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(request_log)!r}).write_text(sys.stdin.read(), encoding='utf-8')\n"
        "print(json.dumps({'schema_version': 1, 'status': 'observed', "
        "'config': {'exists': True, 'sha256': 'a' * 64}}))\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    observation = PrivilegedConfigurationTargetInspector(helper_command=(str(helper),)).inspect()

    assert observation == LiveConfigObservation(exists=True, sha256="a" * 64)
    assert json.loads(request_log.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "operation": "inspect-config",
    }


def test_privileged_inspector_rejects_extra_response_fields(tmp_path: Path) -> None:
    helper = tmp_path / "helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        'print(\'{"schema_version":1,"status":"observed",'
        '"config":{"exists":false,"sha256":null,"content":"secret"}}\')\n',
        encoding="utf-8",
    )
    helper.chmod(0o755)

    with pytest.raises(PrivilegedConfigInspectionProtocolError, match="fields"):
        PrivilegedConfigurationTargetInspector(helper_command=(str(helper),)).inspect()
