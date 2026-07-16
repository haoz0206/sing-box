"""Bounded system DNS inspection for manager-owned public endpoints."""

import json
import subprocess
import sys
from ipaddress import ip_address
from pathlib import Path

from sb_manager.domain.installation import ManagedInstallation
from sb_manager.seams.domain_resolution import (
    DomainResolutionInspectionError,
    DomainResolutionObservation,
    DomainResolutionResult,
)

_RESOLVER_PROGRAM = """
import json
import socket
import sys

results = []
for domain in sys.argv[1:]:
    try:
        records = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        results.append({"domain": domain, "addresses": [], "error": str(error)})
    else:
        addresses = sorted({record[4][0] for record in records})
        results.append({"domain": domain, "addresses": addresses, "error": None})
print(json.dumps(results, ensure_ascii=True, separators=(",", ":")))
"""
MAX_DOMAIN_LENGTH = 253
MAX_LABEL_LENGTH = 63


class BoundedSocketDomainResolutionInspector:
    """Resolve all desired public domains in one disposable, time-bounded worker."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        python_binary: str | Path = sys.executable,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._python_binary = str(python_binary)

    def inspect(self, installation: ManagedInstallation) -> DomainResolutionObservation:
        ordered_domains, invalid_domains, skipped_ip_addresses = self._collect_targets(installation)
        if not ordered_domains:
            return DomainResolutionObservation(
                results=tuple(
                    DomainResolutionResult(
                        domain=domain,
                        addresses=(),
                        error="invalid domain syntax",
                    )
                    for domain in invalid_domains
                ),
                skipped_ip_addresses=skipped_ip_addresses,
            )
        try:
            completed = subprocess.run(
                [
                    self._python_binary,
                    "-I",
                    "-c",
                    _RESOLVER_PROGRAM,
                    *ordered_domains,
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise DomainResolutionInspectionError(
                f"Unable to resolve public domains: {error}"
            ) from error
        if completed.returncode != 0:
            diagnostics = (completed.stderr or completed.stdout).strip()
            raise DomainResolutionInspectionError(
                diagnostics or f"DNS worker exited with status {completed.returncode}"
            )
        try:
            payload = json.loads(completed.stdout)
            resolved_results = tuple(
                DomainResolutionResult(
                    domain=item["domain"],
                    addresses=tuple(item["addresses"]),
                    error=item["error"],
                )
                for item in payload
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise DomainResolutionInspectionError(
                f"DNS worker returned invalid evidence: {error}"
            ) from error
        return DomainResolutionObservation(
            results=tuple(
                sorted(
                    (
                        *resolved_results,
                        *(
                            DomainResolutionResult(
                                domain=domain,
                                addresses=(),
                                error="invalid domain syntax",
                            )
                            for domain in invalid_domains
                        ),
                    ),
                    key=lambda result: result.domain,
                )
            ),
            skipped_ip_addresses=skipped_ip_addresses,
        )

    @staticmethod
    def _collect_targets(
        installation: ManagedInstallation,
    ) -> tuple[tuple[str, ...], tuple[str, ...], int]:
        domains: set[str] = set()
        invalid_domains: set[str] = set()
        ip_addresses: set[str] = set()
        for profile in installation.profiles:
            for address in (
                profile.server_address,
                profile.tls_intent.server_name if profile.tls_intent is not None else None,
            ):
                if address is None:
                    continue
                normalized = address.strip().rstrip(".")
                try:
                    ip_address(normalized)
                except ValueError:
                    try:
                        domain = normalized.encode("idna").decode("ascii").lower()
                    except UnicodeError:
                        invalid_domains.add(normalized)
                    else:
                        if BoundedSocketDomainResolutionInspector._valid_domain(domain):
                            domains.add(domain)
                        else:
                            invalid_domains.add(domain)
                else:
                    ip_addresses.add(normalized)
        return (
            tuple(sorted(domains)),
            tuple(sorted(invalid_domains)),
            len(ip_addresses),
        )

    @staticmethod
    def _valid_domain(domain: str) -> bool:
        if not domain or len(domain) > MAX_DOMAIN_LENGTH:
            return False
        labels = domain.split(".")
        return all(
            1 <= len(label) <= MAX_LABEL_LENGTH
            and label[0].isalnum()
            and label[-1].isalnum()
            and all(character.isalnum() or character == "-" for character in label)
            for label in labels
        )
