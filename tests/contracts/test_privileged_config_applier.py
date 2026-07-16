import json
from pathlib import Path

import pytest

from sb_manager.adapters.privileged_config_applier import (
    PrivilegedConfigurationApplier,
    PrivilegedHelperExecutionError,
    PrivilegedHelperProtocolError,
)
from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyOutcome,
    ApplyTransactionResult,
    CommitResult,
    ConfigTargetPrecondition,
)

SHA256_HEX_LENGTH = 64


def helper_response() -> dict[str, object]:
    return {
        "schema_version": 1,
        "status": "applied",
        "transaction": {
            "outcome": "applied",
            "validation": {"valid": True, "diagnostics": "configuration valid"},
            "commit": {"success": True, "diagnostics": "configuration committed"},
            "runtime_refresh": {"success": True, "diagnostics": "service refreshed"},
            "postcondition": {"healthy": True, "diagnostics": "service active"},
            "rollback": None,
        },
    }


def recording_helper(tmp_path: Path, incoming_directory: Path) -> tuple[Path, Path]:
    log_path = tmp_path / "helper-log.json"
    helper = tmp_path / "privileged-helper"
    response_json = json.dumps(helper_response())
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        "request = json.load(sys.stdin)\n"
        f"incoming = Path({str(incoming_directory)!r})\n"
        "config = incoming / f\"config-{request['sha256']}.json\"\n"
        "record = {'request': request, 'document': json.loads(config.read_text())}\n"
        f"Path({str(log_path)!r}).write_text(json.dumps(record), encoding='utf-8')\n"
        f"print({response_json!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    return helper, log_path


def test_config_is_staged_for_helper_and_typed_transaction_is_restored(tmp_path: Path) -> None:
    incoming_directory = tmp_path / "incoming"
    helper, log_path = recording_helper(tmp_path, incoming_directory)
    document: dict[str, object] = {
        "inbounds": [{"type": "shadowsocks", "tag": "managed"}],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }

    result = PrivilegedConfigurationApplier(
        incoming_directory=incoming_directory,
        helper_command=(str(helper),),
    ).apply(document, precondition=ConfigTargetPrecondition.absent())

    assert result == ApplyTransactionResult(
        outcome=ApplyOutcome.APPLIED,
        validation=ConfigValidationResult(valid=True, diagnostics="configuration valid"),
        commit=CommitResult(success=True, diagnostics="configuration committed"),
        runtime_refresh=RuntimeRefreshResult(success=True, diagnostics="service refreshed"),
        postcondition=RuntimePostcondition(healthy=True, diagnostics="service active"),
        rollback=None,
    )
    helper_log = json.loads(log_path.read_text())
    assert helper_log["document"] == document
    assert helper_log["request"] == {
        "schema_version": 1,
        "operation": "apply-config",
        "sha256": helper_log["request"]["sha256"],
        "expected_config_sha256": None,
    }
    assert len(helper_log["request"]["sha256"]) == SHA256_HEX_LENGTH
    assert list(incoming_directory.iterdir()) == []


def test_helper_failure_is_actionable_and_incoming_config_is_removed(tmp_path: Path) -> None:
    incoming_directory = tmp_path / "incoming"
    helper = tmp_path / "rejecting-helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "print('authorization denied', file=sys.stderr)\n"
        "raise SystemExit(77)\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    applier = PrivilegedConfigurationApplier(
        incoming_directory=incoming_directory,
        helper_command=(str(helper),),
    )

    with pytest.raises(PrivilegedHelperExecutionError, match="authorization denied"):
        applier.apply(
            {"inbounds": []},
            precondition=ConfigTargetPrecondition.absent(),
        )

    assert list(incoming_directory.iterdir()) == []


def test_helper_response_requires_exact_boolean_types(tmp_path: Path) -> None:
    incoming_directory = tmp_path / "incoming"
    response = helper_response()
    transaction = response["transaction"]
    assert isinstance(transaction, dict)
    validation = transaction["validation"]
    assert isinstance(validation, dict)
    validation["valid"] = 1
    helper = tmp_path / "malformed-helper"
    helper.write_text(
        f"#!/usr/bin/env python3\nprint({json.dumps(response)!r})\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)

    with pytest.raises(PrivilegedHelperProtocolError, match="must be a boolean"):
        PrivilegedConfigurationApplier(
            incoming_directory=incoming_directory,
            helper_command=(str(helper),),
        ).apply(
            {"inbounds": []},
            precondition=ConfigTargetPrecondition.absent(),
        )

    assert list(incoming_directory.iterdir()) == []


def test_incoming_path_failure_is_reported_as_operational_error(tmp_path: Path) -> None:
    incoming_path = tmp_path / "incoming"
    incoming_path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(PrivilegedHelperExecutionError, match="Unable to stage helper request"):
        PrivilegedConfigurationApplier(
            incoming_directory=incoming_path,
            helper_command=("unused-helper",),
        ).apply(
            {"inbounds": []},
            precondition=ConfigTargetPrecondition.absent(),
        )
