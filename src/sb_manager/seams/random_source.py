"""Public seam for security-sensitive random values."""

from typing import Protocol


class RandomSource(Protocol):
    """Generate values that tests must be able to make deterministic."""

    def uuid(self) -> str: ...

    def token_hex(self, byte_count: int) -> str: ...

    def token_bytes(self, byte_count: int) -> bytes: ...
