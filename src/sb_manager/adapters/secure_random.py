"""Cryptographically secure random values from the Python standard library."""

import secrets
import uuid


class SecureRandomSource:
    """Production implementation of the random source seam."""

    def uuid(self) -> str:
        return str(uuid.uuid4())

    def token_hex(self, byte_count: int) -> str:
        return secrets.token_hex(byte_count)

    def token_bytes(self, byte_count: int) -> bytes:
        return secrets.token_bytes(byte_count)
