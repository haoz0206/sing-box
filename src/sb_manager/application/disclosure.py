"""Shared conservative redaction for operator-visible and durable diagnostics."""

import re
from collections.abc import Mapping
from dataclasses import replace

from sb_manager.domain.installation import ManagedInstallation
from sb_manager.domain.protocol_material import (
    AnyTlsMaterial,
    Hysteria2Material,
    RealityMaterial,
    ShadowsocksMaterial,
    SnellV6Material,
    TrojanMaterial,
    TuicMaterial,
    VlessMaterial,
    VmessMaterial,
)
from sb_manager.transactions.apply import ApplyTransactionResult

MIN_EXACT_SECRET_LENGTH = 8
MIN_PRINTABLE_CODE_POINT = 32
REDACTION_MARKER = "[已脱敏]"

SENSITIVE_CONFIGURATION_KEYS = frozenset(
    {
        "api_key",
        "auth",
        "authentication",
        "authorization",
        "credential",
        "password",
        "passwd",
        "private_key",
        "psk",
        "refresh_token",
        "secret",
        "short_id",
        "token",
        "access_token",
        "uuid",
    }
)

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[@-_])")
_URI_USERINFO = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)([^@\s/]+)@")
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)([\"']?\b(?:password|passwd|psk|secret|token|(?:access|refresh)[_ -]?token|"
    r"auth(?:entication|orization)?|credential|api[_ -]?key|private[_ -]?key|uuid|"
    r"short[_ -]?id)\b[\"']?\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|(?:(?:Bearer|Basic)\s+)?[^\s,;&}]+)"
)


def redact_text(text: str, secrets: tuple[str, ...]) -> tuple[str, int]:
    """Remove controls and replace common or exact credential disclosures."""
    sanitized = sanitize_controls(text)
    replacements = 0

    def redact_uri(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return f"{match.group(1)}{REDACTION_MARKER}@"

    sanitized = _URI_USERINFO.sub(redact_uri, sanitized)

    def redact_assignment(match: re.Match[str]) -> str:
        nonlocal replacements
        replacements += 1
        return f"{match.group(1)}{REDACTION_MARKER}"

    sanitized = _SENSITIVE_ASSIGNMENT.sub(redact_assignment, sanitized)
    for secret in secrets:
        occurrences = sanitized.count(secret)
        if occurrences:
            sanitized = sanitized.replace(secret, REDACTION_MARKER)
            replacements += occurrences
    return sanitized, replacements


def sanitize_controls(text: str) -> str:
    """Strip terminal escapes and non-printing controls from untrusted text."""
    without_ansi = _ANSI_ESCAPE.sub("", text)
    return "".join(
        character
        for character in without_ansi
        if character in "\n\t" or ord(character) >= MIN_PRINTABLE_CODE_POINT
    )


def persisted_secrets(installation: ManagedInstallation) -> tuple[str, ...]:
    """Return long persisted credentials, ordered longest-first for redaction."""
    values: set[str] = set()
    for profile in installation.profiles:
        material = profile.protocol_material
        candidates: tuple[str, ...]
        if isinstance(material, RealityMaterial):
            candidates = (material.user_uuid, material.private_key, material.short_id)
        elif isinstance(
            material,
            (ShadowsocksMaterial, Hysteria2Material, TrojanMaterial, AnyTlsMaterial),
        ):
            candidates = (material.password,)
        elif isinstance(material, SnellV6Material):
            candidates = (material.psk,)
        elif isinstance(material, TuicMaterial):
            candidates = (material.user_uuid, material.password)
        elif isinstance(material, (VlessMaterial, VmessMaterial)):
            candidates = (material.user_uuid,)
        else:
            candidates = ()
        values.update(value for value in candidates if len(value) >= MIN_EXACT_SECRET_LENGTH)
    return tuple(sorted(values, key=len, reverse=True))


def disclosure_secrets(
    installation: ManagedInstallation,
    document: Mapping[str, object],
) -> tuple[str, ...]:
    """Return exact persisted and candidate credentials needed at an apply boundary."""
    values = set(persisted_secrets(installation))

    def collect(value: object, *, sensitive: bool = False) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                normalized_key = str(key).lower().replace("-", "_").replace(" ", "_")
                collect(
                    child,
                    sensitive=sensitive or normalized_key in SENSITIVE_CONFIGURATION_KEYS,
                )
        elif isinstance(value, (list, tuple)):
            for child in value:
                collect(child, sensitive=sensitive)
        elif sensitive and isinstance(value, str) and len(value) >= MIN_EXACT_SECRET_LENGTH:
            values.add(value)

    collect(document)
    return tuple(sorted(values, key=len, reverse=True))


def redact_transaction_result(
    result: ApplyTransactionResult,
    secrets: tuple[str, ...],
) -> tuple[ApplyTransactionResult, int]:
    """Redact every operator-visible diagnostic while preserving clean result identity."""
    replacements = 0
    changed = False

    def sanitized(text: str) -> str:
        nonlocal replacements, changed
        value, count = redact_text(text, secrets)
        replacements += count
        changed = changed or value != text
        return value

    validation = replace(
        result.validation,
        diagnostics=sanitized(result.validation.diagnostics),
    )
    runtime_refresh = (
        replace(
            result.runtime_refresh,
            diagnostics=sanitized(result.runtime_refresh.diagnostics),
        )
        if result.runtime_refresh is not None
        else None
    )
    postcondition = (
        replace(
            result.postcondition,
            diagnostics=sanitized(result.postcondition.diagnostics),
        )
        if result.postcondition is not None
        else None
    )
    commit = (
        replace(result.commit, diagnostics=sanitized(result.commit.diagnostics))
        if result.commit is not None
        else None
    )
    rollback = None
    if result.rollback is not None:
        rollback = replace(
            result.rollback,
            diagnostics=sanitized(result.rollback.diagnostics),
            recovery_instructions=tuple(
                sanitized(instruction) for instruction in result.rollback.recovery_instructions
            ),
        )
    if not changed:
        return result, replacements
    return (
        replace(
            result,
            validation=validation,
            runtime_refresh=runtime_refresh,
            postcondition=postcondition,
            commit=commit,
            rollback=rollback,
        ),
        replacements,
    )
