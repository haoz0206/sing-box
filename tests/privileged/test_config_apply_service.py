import hashlib
import json
from pathlib import Path

from sb_manager.privileged.config_apply import (
    ApplyConfigRequest,
    PrivilegedConfigApplyPolicy,
    PrivilegedConfigApplyService,
)
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import ApplyOutcome

ROLLBACK_REFRESH_COUNT = 2


class HealthyRuntime:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def refresh(self) -> RuntimeRefreshResult:
        self.calls.append("refresh")
        return RuntimeRefreshResult(success=True, diagnostics="service refreshed")

    def check_health(self) -> RuntimePostcondition:
        self.calls.append("health")
        return RuntimePostcondition(healthy=True, diagnostics="service active")

    def recovery_instructions(self) -> tuple[str, ...]:
        return ("recover service",)


class RuntimeThatMustNotBeCalled:
    def refresh(self) -> RuntimeRefreshResult:
        raise AssertionError("runtime must not refresh after validation failure")

    def check_health(self) -> RuntimePostcondition:
        raise AssertionError("runtime health must not run after validation failure")

    def recovery_instructions(self) -> tuple[str, ...]:
        return ()


class RuntimeThatRecoversPreviousConfig:
    def __init__(self) -> None:
        self.refresh_count = 0

    def refresh(self) -> RuntimeRefreshResult:
        self.refresh_count += 1
        if self.refresh_count == 1:
            return RuntimeRefreshResult(success=False, diagnostics="candidate rejected")
        return RuntimeRefreshResult(success=True, diagnostics="previous config refreshed")

    def check_health(self) -> RuntimePostcondition:
        return RuntimePostcondition(healthy=True, diagnostics="previous config active")

    def recovery_instructions(self) -> tuple[str, ...]:
        return ("recover service",)


def validator_binary(tmp_path: Path, *, valid: bool) -> Path:
    binary = tmp_path / ("valid-sing-box" if valid else "invalid-sing-box")
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        + (
            "print('configuration valid')\n"
            if valid
            else "print('configuration invalid', file=sys.stderr)\nraise SystemExit(23)\n"
        ),
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def policy(tmp_path: Path, *, core_binary: Path) -> PrivilegedConfigApplyPolicy:
    return PrivilegedConfigApplyPolicy(
        incoming_directory=tmp_path / "incoming",
        working_directory=tmp_path / "work",
        config_path=tmp_path / "etc/sing-box/config.json",
        core_binary=core_binary,
        lock_path=tmp_path / "apply.lock",
    )


def write_incoming_config(
    install_policy: PrivilegedConfigApplyPolicy,
    document: dict[str, object],
) -> str:
    content = json.dumps(document, sort_keys=True).encode()
    sha256 = hashlib.sha256(content).hexdigest()
    install_policy.incoming_directory.mkdir(exist_ok=True)
    (install_policy.incoming_directory / f"config-{sha256}.json").write_bytes(content)
    return sha256


def test_verified_incoming_config_is_validated_committed_and_refreshed(tmp_path: Path) -> None:
    runtime = HealthyRuntime()
    install_policy = policy(tmp_path, core_binary=validator_binary(tmp_path, valid=True))
    document: dict[str, object] = {
        "inbounds": [{"type": "shadowsocks", "tag": "managed"}],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    sha256 = write_incoming_config(install_policy, document)

    result = PrivilegedConfigApplyService(
        policy=install_policy,
        runtime=runtime,
    ).apply_config(ApplyConfigRequest(sha256=sha256))

    assert result.outcome is ApplyOutcome.APPLIED
    assert json.loads(install_policy.config_path.read_text()) == document
    assert runtime.calls == ["refresh", "health"]


def test_validation_failure_preserves_previous_config_and_skips_runtime(tmp_path: Path) -> None:
    install_policy = policy(tmp_path, core_binary=validator_binary(tmp_path, valid=False))
    install_policy.config_path.parent.mkdir(parents=True)
    previous = b'{"inbounds":[{"tag":"previous"}]}\n'
    install_policy.config_path.write_bytes(previous)
    sha256 = write_incoming_config(
        install_policy,
        {"inbounds": [{"type": "shadowsocks", "tag": "candidate"}]},
    )

    result = PrivilegedConfigApplyService(
        policy=install_policy,
        runtime=RuntimeThatMustNotBeCalled(),
    ).apply_config(ApplyConfigRequest(sha256=sha256))

    assert result.outcome is ApplyOutcome.VALIDATION_FAILED
    assert install_policy.config_path.read_bytes() == previous
    assert result.validation.diagnostics == "configuration invalid"


def test_runtime_rejection_restores_previous_config(tmp_path: Path) -> None:
    install_policy = policy(tmp_path, core_binary=validator_binary(tmp_path, valid=True))
    install_policy.config_path.parent.mkdir(parents=True)
    previous = b'{"inbounds":[{"tag":"previous"}]}\n'
    install_policy.config_path.write_bytes(previous)
    sha256 = write_incoming_config(
        install_policy,
        {"inbounds": [{"type": "shadowsocks", "tag": "candidate"}]},
    )
    runtime = RuntimeThatRecoversPreviousConfig()

    result = PrivilegedConfigApplyService(
        policy=install_policy,
        runtime=runtime,
    ).apply_config(ApplyConfigRequest(sha256=sha256))

    assert result.outcome is ApplyOutcome.ROLLED_BACK
    assert install_policy.config_path.read_bytes() == previous
    assert result.rollback is not None
    assert result.rollback.success is True
    assert runtime.refresh_count == ROLLBACK_REFRESH_COUNT
