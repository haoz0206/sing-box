"""Transactional orchestration for validated sing-box configuration."""

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tempfile import NamedTemporaryFile

from sb_manager.seams.config_validator import ConfigValidationResult, ConfigValidator
from sb_manager.seams.runtime import Runtime, RuntimePostcondition, RuntimeRefreshResult
from sb_manager.transactions.staging import ConfigurationStager


class ApplyOutcome(str, Enum):
    """Operator-relevant terminal state of an apply transaction."""

    VALIDATION_FAILED = "validation-failed"
    COMMIT_FAILED = "commit-failed"
    APPLIED = "applied"
    ROLLED_BACK = "rolled-back"
    ROLLBACK_FAILED = "rollback-failed"


@dataclass(frozen=True, slots=True)
class RollbackResult:
    """Whether recovery restored the previous configuration and runtime."""

    success: bool
    diagnostics: str
    recovery_instructions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CommitResult:
    """Whether staged configuration reached the manager-owned target path."""

    success: bool
    diagnostics: str


@dataclass(frozen=True, slots=True)
class ApplyTransactionResult:
    """Typed evidence produced by one apply attempt."""

    outcome: ApplyOutcome
    validation: ConfigValidationResult
    runtime_refresh: RuntimeRefreshResult | None
    postcondition: RuntimePostcondition | None
    rollback: RollbackResult | None
    commit: CommitResult | None = None


class ApplyCoordinator:
    """Order staged validation before any change to the running host."""

    def __init__(
        self,
        *,
        config_path: Path,
        stager: ConfigurationStager,
        validator: ConfigValidator,
        runtime: Runtime,
    ) -> None:
        self._config_path = config_path
        self.backup_path = config_path.with_name(f"{config_path.name}.bak")
        self._stager = stager
        self._validator = validator
        self._runtime = runtime

    def apply(self, document: Mapping[str, object]) -> ApplyTransactionResult:
        with self._stager.stage(document) as staged:
            validation = self._validator.validate(staged.config_path)
            if not validation.valid:
                return ApplyTransactionResult(
                    outcome=ApplyOutcome.VALIDATION_FAILED,
                    validation=validation,
                    runtime_refresh=None,
                    postcondition=None,
                    rollback=None,
                )

            try:
                had_previous_configuration = self._backup_current_configuration()
                self._atomic_copy(staged.config_path, self._config_path)
            except OSError as error:
                return ApplyTransactionResult(
                    outcome=ApplyOutcome.COMMIT_FAILED,
                    validation=validation,
                    runtime_refresh=None,
                    postcondition=None,
                    rollback=None,
                    commit=CommitResult(success=False, diagnostics=str(error)),
                )

        commit = CommitResult(success=True, diagnostics="configuration committed")

        runtime_refresh = self._runtime.refresh()
        if not runtime_refresh.success:
            rollback = self._restore_previous_configuration(had_previous_configuration)
            return ApplyTransactionResult(
                outcome=(
                    ApplyOutcome.ROLLED_BACK if rollback.success else ApplyOutcome.ROLLBACK_FAILED
                ),
                validation=validation,
                runtime_refresh=runtime_refresh,
                postcondition=None,
                rollback=rollback,
                commit=commit,
            )
        postcondition = self._runtime.check_health()
        if not postcondition.healthy:
            rollback = self._restore_previous_configuration(had_previous_configuration)
            return ApplyTransactionResult(
                outcome=(
                    ApplyOutcome.ROLLED_BACK if rollback.success else ApplyOutcome.ROLLBACK_FAILED
                ),
                validation=validation,
                runtime_refresh=runtime_refresh,
                postcondition=postcondition,
                rollback=rollback,
                commit=commit,
            )
        return ApplyTransactionResult(
            outcome=ApplyOutcome.APPLIED,
            validation=validation,
            runtime_refresh=runtime_refresh,
            postcondition=postcondition,
            rollback=None,
            commit=commit,
        )

    def _backup_current_configuration(self) -> bool:
        if self._config_path.exists():
            self._atomic_copy(self._config_path, self.backup_path)
            return True
        return False

    def _restore_previous_configuration(self, had_previous: bool) -> RollbackResult:
        try:
            if had_previous:
                self._atomic_copy(self.backup_path, self._config_path)
            else:
                self._config_path.unlink(missing_ok=True)
        except OSError as error:
            return RollbackResult(
                success=False,
                diagnostics=f"failed to restore previous configuration: {error}",
                recovery_instructions=self._recovery_instructions(restored=False),
            )

        refresh = self._runtime.refresh()
        if not refresh.success:
            return RollbackResult(
                success=False,
                diagnostics=refresh.diagnostics,
                recovery_instructions=self._recovery_instructions(restored=True),
            )
        postcondition = self._runtime.check_health()
        return RollbackResult(
            success=postcondition.healthy,
            diagnostics="; ".join(
                item for item in (refresh.diagnostics, postcondition.diagnostics) if item
            ),
            recovery_instructions=(
                () if postcondition.healthy else self._recovery_instructions(restored=True)
            ),
        )

    def _recovery_instructions(self, *, restored: bool) -> tuple[str, ...]:
        file_instruction = (
            f"确认旧配置已恢复到 {self._config_path}，恢复副本位于 {self.backup_path}。"
            if restored
            else f"将 {self.backup_path} 复制到 {self._config_path}。"
        )
        return (file_instruction, *self._runtime.recovery_instructions())

    @staticmethod
    def _atomic_copy(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with (
                source.open("rb") as source_file,
                NamedTemporaryFile(
                    mode="wb",
                    dir=destination.parent,
                    prefix=f".{destination.name}.",
                    delete=False,
                ) as temporary_file,
            ):
                temporary_path = Path(temporary_file.name)
                shutil.copyfileobj(source_file, temporary_file)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary_path.replace(destination)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
