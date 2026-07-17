"""Shared fixed host locations allowed for managed public-certificate inspection."""

from pathlib import Path

MANAGED_CERTIFICATE_ROOTS = (
    Path("/etc/sing-box-manager/tls"),
    Path("/var/lib/sing-box-manager/acme"),
)
