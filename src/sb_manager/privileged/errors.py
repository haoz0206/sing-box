"""Errors shared by fixed-policy privileged operations."""


class PrivilegedInputError(RuntimeError):
    """An unprivileged request or incoming file violates fixed policy."""
