import hashlib
import json
from pathlib import Path

from sb_manager.seams.config_validator import ConfigValidationResult
from sb_manager.seams.runtime import RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.apply import (
    ApplyCoordinator,
    ApplyOutcome,
    ConfigTargetPrecondition,
)
from sb_manager.transactions.staging import ConfigurationStager


class RejectingValidator:
    def validate(self, config_path: Path) -> ConfigValidationResult:
        assert config_path.read_text(encoding="utf-8")
        return ConfigValidationResult(valid=False, diagnostics="invalid inbound")


class RuntimeThatMustNotBeCalled:
    def refresh(self) -> None:
        raise AssertionError("runtime refresh must not run after validation failure")

    def check_health(self) -> None:
        raise AssertionError("runtime health must not run after validation failure")


class AcceptingValidator:
    def validate(self, config_path: Path) -> ConfigValidationResult:
        assert json.loads(config_path.read_text(encoding="utf-8"))
        return ConfigValidationResult(valid=True, diagnostics="configuration is valid")


class HealthyRuntime:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def refresh(self) -> RuntimeRefreshResult:
        self.calls.append("refresh")
        return RuntimeRefreshResult(success=True, diagnostics="service reloaded")

    def check_health(self) -> RuntimePostcondition:
        self.calls.append("health")
        return RuntimePostcondition(healthy=True, diagnostics="service is active")


class RuntimeRejectingCandidate:
    def __init__(self) -> None:
        self.refresh_count = 0
        self.calls: list[str] = []

    def refresh(self) -> RuntimeRefreshResult:
        self.refresh_count += 1
        if self.refresh_count == 1:
            self.calls.append("refresh-candidate")
            return RuntimeRefreshResult(success=False, diagnostics="candidate reload failed")
        self.calls.append("refresh-previous")
        return RuntimeRefreshResult(success=True, diagnostics="previous config reloaded")

    def check_health(self) -> RuntimePostcondition:
        self.calls.append("health-previous")
        return RuntimePostcondition(
            healthy=True,
            diagnostics="previous service is active",
        )


class RuntimeWithUnhealthyCandidate:
    def __init__(self) -> None:
        self.health_count = 0
        self.calls: list[str] = []

    def refresh(self) -> RuntimeRefreshResult:
        self.calls.append("refresh")
        return RuntimeRefreshResult(success=True, diagnostics="service reloaded")

    def check_health(self) -> RuntimePostcondition:
        self.health_count += 1
        if self.health_count == 1:
            self.calls.append("health-candidate")
            return RuntimePostcondition(healthy=False, diagnostics="service exited")
        self.calls.append("health-previous")
        return RuntimePostcondition(healthy=True, diagnostics="previous service is active")


class RuntimeWhoseRollbackRefreshFails:
    def refresh(self) -> RuntimeRefreshResult:
        return RuntimeRefreshResult(success=False, diagnostics="service would not restart")

    def check_health(self) -> RuntimePostcondition:
        raise AssertionError("health must not run after failed rollback refresh")

    def recovery_instructions(self) -> tuple[str, ...]:
        return (
            "运行 systemctl restart sing-box。",
            "运行 systemctl status sing-box --no-pager。",
        )


def test_absent_precondition_refuses_to_replace_an_unmanaged_configuration(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    unmanaged_bytes = b'{"inbounds": [{"tag": "unmanaged"}]}\n'
    config_path.write_bytes(unmanaged_bytes)
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=RuntimeThatMustNotBeCalled(),
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        },
        precondition=ConfigTargetPrecondition.absent(),
    )

    assert result.outcome is ApplyOutcome.PRECONDITION_FAILED
    assert result.commit is not None and not result.commit.success
    assert result.commit.diagnostics == "Live configuration exists but absence was required"
    assert result.runtime_refresh is None
    assert result.rollback is None
    assert config_path.read_bytes() == unmanaged_bytes
    assert not coordinator.backup_path.exists()


def test_absent_precondition_refuses_to_replace_a_dangling_symlink(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    symlink_target = tmp_path / "missing.json"
    config_path.symlink_to(symlink_target)
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=RuntimeThatMustNotBeCalled(),
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        },
        precondition=ConfigTargetPrecondition.absent(),
    )

    assert result.outcome is ApplyOutcome.PRECONDITION_FAILED
    assert result.commit is not None and not result.commit.success
    assert result.commit.diagnostics == "Live configuration exists but absence was required"
    assert config_path.is_symlink()
    assert config_path.readlink() == symlink_target
    assert not coordinator.backup_path.exists()


def test_matching_fingerprint_allows_an_adopted_configuration_to_be_replaced(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    adopted_bytes = b'{"inbounds": [{"tag": "adopted"}]}\n'
    config_path.write_bytes(adopted_bytes)
    runtime = HealthyRuntime()
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=runtime,
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        },
        precondition=ConfigTargetPrecondition.matching_sha256(
            hashlib.sha256(adopted_bytes).hexdigest()
        ),
    )

    assert result.outcome is ApplyOutcome.APPLIED
    assert coordinator.backup_path.read_bytes() == adopted_bytes
    assert runtime.calls == ["refresh", "health"]


def test_changed_adopted_configuration_fails_the_fingerprint_precondition(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    reviewed_bytes = b'{"inbounds": [{"tag": "reviewed"}]}\n'
    changed_bytes = b'{"inbounds": [{"tag": "changed-after-review"}]}\n'
    config_path.write_bytes(changed_bytes)
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=RuntimeThatMustNotBeCalled(),
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        },
        precondition=ConfigTargetPrecondition.matching_sha256(
            hashlib.sha256(reviewed_bytes).hexdigest()
        ),
    )

    assert result.outcome is ApplyOutcome.PRECONDITION_FAILED
    assert result.commit is not None and not result.commit.success
    assert result.commit.diagnostics == "Live configuration fingerprint changed after review"
    assert config_path.read_bytes() == changed_bytes


def test_failed_validation_preserves_the_running_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    previous_bytes = b'{"inbounds": [{"tag": "previous"}]}\n'
    config_path.write_bytes(previous_bytes)
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=RejectingValidator(),
        runtime=RuntimeThatMustNotBeCalled(),
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
    )

    assert result.outcome is ApplyOutcome.VALIDATION_FAILED
    assert result.validation == ConfigValidationResult(
        valid=False,
        diagnostics="invalid inbound",
    )
    assert result.runtime_refresh is None
    assert result.postcondition is None
    assert result.rollback is None
    assert config_path.read_bytes() == previous_bytes


def test_valid_configuration_is_committed_before_runtime_refresh(tmp_path: Path) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    previous_bytes = b'{"inbounds": [{"tag": "previous"}]}\n'
    config_path.write_bytes(previous_bytes)
    runtime = HealthyRuntime()
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=runtime,
    )
    document = {
        "inbounds": [{"type": "vless", "tag": "candidate"}],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }

    result = coordinator.apply(document)

    assert result.outcome is ApplyOutcome.APPLIED
    assert result.validation.valid
    assert result.runtime_refresh == RuntimeRefreshResult(
        success=True,
        diagnostics="service reloaded",
    )
    assert result.postcondition == RuntimePostcondition(
        healthy=True,
        diagnostics="service is active",
    )
    assert result.rollback is None
    assert json.loads(config_path.read_text(encoding="utf-8")) == document
    assert coordinator.backup_path.read_bytes() == previous_bytes
    assert runtime.calls == ["refresh", "health"]


def test_failed_runtime_refresh_restores_the_previous_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    previous_bytes = b'{"inbounds": [{"tag": "previous"}]}\n'
    config_path.write_bytes(previous_bytes)
    runtime = RuntimeRejectingCandidate()
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=runtime,
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
    )

    assert result.outcome is ApplyOutcome.ROLLED_BACK
    assert result.runtime_refresh == RuntimeRefreshResult(
        success=False,
        diagnostics="candidate reload failed",
    )
    assert result.postcondition is None
    assert result.rollback is not None
    assert result.rollback.success
    assert result.rollback.diagnostics == ("previous config reloaded; previous service is active")
    assert config_path.read_bytes() == previous_bytes
    assert runtime.calls == [
        "refresh-candidate",
        "refresh-previous",
        "health-previous",
    ]


def test_failed_postcondition_restores_the_previous_configuration(tmp_path: Path) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    previous_bytes = b'{"inbounds": [{"tag": "previous"}]}\n'
    config_path.write_bytes(previous_bytes)
    runtime = RuntimeWithUnhealthyCandidate()
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=runtime,
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
    )

    assert result.outcome is ApplyOutcome.ROLLED_BACK
    assert result.runtime_refresh == RuntimeRefreshResult(
        success=True,
        diagnostics="service reloaded",
    )
    assert result.postcondition == RuntimePostcondition(
        healthy=False,
        diagnostics="service exited",
    )
    assert result.rollback is not None and result.rollback.success
    assert config_path.read_bytes() == previous_bytes
    assert runtime.calls == [
        "refresh",
        "health-candidate",
        "refresh",
        "health-previous",
    ]


def test_failed_rollback_reports_exact_recovery_instructions(tmp_path: Path) -> None:
    config_path = tmp_path / "etc/sing-box/config.json"
    config_path.parent.mkdir(parents=True)
    previous_bytes = b'{"inbounds": [{"tag": "previous"}]}\n'
    config_path.write_bytes(previous_bytes)
    coordinator = ApplyCoordinator(
        config_path=config_path,
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=RuntimeWhoseRollbackRefreshFails(),
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "vless", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
    )

    assert result.outcome is ApplyOutcome.ROLLBACK_FAILED
    assert result.rollback is not None and not result.rollback.success
    assert config_path.read_bytes() == previous_bytes
    assert result.rollback.recovery_instructions == (
        f"确认旧配置已恢复到 {config_path}，恢复副本位于 {coordinator.backup_path}。",
        "运行 systemctl restart sing-box。",
        "运行 systemctl status sing-box --no-pager。",
    )


def test_commit_filesystem_failure_is_typed_before_runtime_refresh(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("blocks config directory creation", encoding="utf-8")
    coordinator = ApplyCoordinator(
        config_path=blocked_parent / "config.json",
        stager=ConfigurationStager(parent=tmp_path / "staging"),
        validator=AcceptingValidator(),
        runtime=RuntimeThatMustNotBeCalled(),
    )

    result = coordinator.apply(
        {
            "inbounds": [{"type": "shadowsocks", "tag": "candidate"}],
            "outbounds": [{"type": "direct", "tag": "direct"}],
        }
    )

    assert result.outcome is ApplyOutcome.COMMIT_FAILED
    assert result.commit is not None and not result.commit.success
    assert "not-a-directory" in result.commit.diagnostics
    assert result.runtime_refresh is None
    assert result.postcondition is None
    assert result.rollback is None
