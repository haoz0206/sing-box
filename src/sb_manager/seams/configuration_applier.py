"""Public seam for applying a generated configuration transactionally."""

from collections.abc import Mapping
from typing import Protocol

from sb_manager.transactions.apply import ApplyTransactionResult


class ConfigurationApplyError(RuntimeError):
    """The system boundary could not return a trustworthy apply result."""


class ConfigurationApplier(Protocol):
    """Commit one complete sing-box document through the transaction boundary."""

    def apply(self, document: Mapping[str, object]) -> ApplyTransactionResult: ...
