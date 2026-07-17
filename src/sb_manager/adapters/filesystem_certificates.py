"""Bounded public-certificate inspection inside explicitly trusted roots."""

from collections.abc import Collection
from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID

from sb_manager.seams.certificate_source import (
    CertificateInspection,
    CertificateMaterialState,
    CertificateObservation,
    CertificateTarget,
    CertificateTargetKind,
)

MAX_CERTIFICATE_BYTES = 1024 * 1024
MAX_ACME_ENTRIES = 2048
MAX_ACME_CERTIFICATES = 256


class FilesystemCertificateSource:
    """Decode public PEM leaves without reading adjacent private-key material."""

    def __init__(self, *, trusted_roots: Collection[Path]) -> None:
        roots = tuple(root.resolve() for root in trusted_roots)
        if not roots:
            raise ValueError("At least one trusted certificate root is required")
        self._trusted_roots = roots

    def inspect(self, targets: Collection[CertificateTarget]) -> CertificateInspection:
        observations = []
        for target in targets:
            if target.kind is CertificateTargetKind.OPERATOR_FILE:
                observations.append(self._inspect_operator_file(target))
            else:
                observations.append(self._inspect_certmagic(target))
        return CertificateInspection(observations=tuple(observations))

    def _inspect_operator_file(self, target: CertificateTarget) -> CertificateObservation:
        path = target.location
        if path.is_symlink():
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics="Certificate path must not be a symbolic link",
            )
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            return self._problem(
                target,
                state=CertificateMaterialState.MISSING,
                diagnostics="Certificate file does not exist",
            )
        except OSError as error:
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics=f"Unable to resolve certificate path: {error}",
            )
        if not self._is_trusted(resolved, allow_root=False):
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics="Certificate path is outside trusted roots",
            )
        if not resolved.is_file():
            return self._problem(
                target,
                state=CertificateMaterialState.INVALID,
                diagnostics="Certificate path is not a regular file",
            )
        return self._decode_path(resolved, target=target, source_label="operator file")

    def _inspect_certmagic(  # noqa: PLR0911 - each return preserves a distinct evidence state
        self, target: CertificateTarget
    ) -> CertificateObservation:
        data_directory = target.location
        if data_directory.is_symlink():
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics="ACME data directory must not be a symbolic link",
                source_label="CertMagic ACME cache",
            )
        try:
            resolved = data_directory.resolve(strict=True)
        except FileNotFoundError:
            return self._problem(
                target,
                state=CertificateMaterialState.MISSING,
                diagnostics="ACME data directory does not exist",
                source_label="CertMagic ACME cache",
            )
        except OSError as error:
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics=f"Unable to resolve ACME data directory: {error}",
                source_label="CertMagic ACME cache",
            )
        if not self._is_trusted(resolved, allow_root=True):
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics="ACME data directory is outside trusted roots",
                source_label="CertMagic ACME cache",
            )
        certificates_root = resolved / "certificates"
        if not certificates_root.is_dir():
            return self._problem(
                target,
                state=CertificateMaterialState.MISSING,
                diagnostics="CertMagic certificate cache does not exist",
                source_label="CertMagic ACME cache",
            )
        try:
            candidates = _bounded_certificate_files(certificates_root)
        except OSError as error:
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics=f"Unable to scan CertMagic certificate cache: {error}",
                source_label="CertMagic ACME cache",
            )
        except _CertificateScanLimitError as error:
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics=str(error),
                source_label="CertMagic ACME cache",
            )
        matching = []
        invalid_diagnostics = []
        for candidate in candidates:
            observation = self._decode_path(
                candidate,
                target=target,
                source_label="CertMagic ACME cache",
            )
            if observation.state is CertificateMaterialState.AVAILABLE:
                matching.append(observation)
            elif observation.state is CertificateMaterialState.INVALID:
                invalid_diagnostics.append(observation.diagnostics)
        if matching:
            return max(matching, key=_expiration)
        if candidates:
            return self._problem(
                target,
                state=CertificateMaterialState.INVALID,
                diagnostics=(
                    invalid_diagnostics[0]
                    if invalid_diagnostics
                    else "No cached certificate covers the declared server name"
                ),
                source_label="CertMagic ACME cache",
            )
        return self._problem(
            target,
            state=CertificateMaterialState.MISSING,
            diagnostics="CertMagic cache contains no public certificates",
            source_label="CertMagic ACME cache",
        )

    def _decode_path(
        self,
        path: Path,
        *,
        target: CertificateTarget,
        source_label: str,
    ) -> CertificateObservation:
        try:
            with path.open("rb") as certificate_file:
                content = certificate_file.read(MAX_CERTIFICATE_BYTES + 1)
        except OSError as error:
            return self._problem(
                target,
                state=CertificateMaterialState.UNAVAILABLE,
                diagnostics=f"Unable to read public certificate: {error}",
                source_label=source_label,
            )
        if len(content) > MAX_CERTIFICATE_BYTES:
            return self._problem(
                target,
                state=CertificateMaterialState.INVALID,
                diagnostics=f"Public certificate exceeds {MAX_CERTIFICATE_BYTES} bytes",
                source_label=source_label,
            )
        try:
            certificates = x509.load_pem_x509_certificates(content)
        except ValueError as error:
            return self._problem(
                target,
                state=CertificateMaterialState.INVALID,
                diagnostics=f"Certificate PEM is invalid: {error}",
                source_label=source_label,
            )
        if not certificates:
            return self._problem(
                target,
                state=CertificateMaterialState.INVALID,
                diagnostics="Certificate PEM contains no certificates",
                source_label=source_label,
            )
        leaf = certificates[0]
        dns_names = _dns_names(leaf)
        if not any(_matches_server_name(name, target.server_name) for name in dns_names):
            return self._problem(
                target,
                state=CertificateMaterialState.INVALID,
                diagnostics="Leaf certificate does not cover the declared server name",
                source_label=source_label,
            )
        return CertificateObservation(
            target=target,
            state=CertificateMaterialState.AVAILABLE,
            source_label=source_label,
            diagnostics="Leaf public certificate decoded",
            not_valid_before=leaf.not_valid_before_utc,
            not_valid_after=leaf.not_valid_after_utc,
            dns_names=dns_names,
        )

    def _is_trusted(self, path: Path, *, allow_root: bool) -> bool:
        return any(
            path.is_relative_to(root) and (allow_root or path != root)
            for root in self._trusted_roots
        )

    @staticmethod
    def _problem(
        target: CertificateTarget,
        *,
        state: CertificateMaterialState,
        diagnostics: str,
        source_label: str = "operator file",
    ) -> CertificateObservation:
        return CertificateObservation(
            target=target,
            state=state,
            source_label=source_label,
            diagnostics=diagnostics,
        )


def _dns_names(certificate: x509.Certificate) -> tuple[str, ...]:
    try:
        names = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        names = [
            value
            for attribute in certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            if isinstance((value := attribute.value), str)
        ]
    return tuple(dict.fromkeys(_normalize_name(name) for name in names))


def _matches_server_name(certificate_name: str, server_name: str) -> bool:
    certificate_name = _normalize_name(certificate_name)
    server_name = _normalize_name(server_name)
    if certificate_name == server_name:
        return True
    if not certificate_name.startswith("*."):
        return False
    suffix = certificate_name[1:]
    return server_name.endswith(suffix) and server_name.count(".") == certificate_name.count(".")


def _normalize_name(name: str) -> str:
    return name.rstrip(".").encode("idna").decode("ascii").lower()


def _expiration(observation: CertificateObservation) -> datetime:
    if observation.not_valid_after is None:
        raise AssertionError("Available certificate observation is missing expiration")
    return observation.not_valid_after


class _CertificateScanLimitError(RuntimeError):
    pass


def _bounded_certificate_files(root: Path) -> tuple[Path, ...]:
    stack = [root]
    entries_seen = 0
    certificates: list[Path] = []
    while stack:
        directory = stack.pop()
        for entry in directory.iterdir():
            entries_seen += 1
            if entries_seen > MAX_ACME_ENTRIES:
                raise _CertificateScanLimitError(
                    f"CertMagic cache exceeds {MAX_ACME_ENTRIES} entries"
                )
            if entry.is_symlink():
                continue
            if entry.is_dir():
                stack.append(entry)
            elif entry.is_file() and entry.suffix.lower() == ".crt":
                certificates.append(entry)
                if len(certificates) > MAX_ACME_CERTIFICATES:
                    raise _CertificateScanLimitError(
                        f"CertMagic cache exceeds {MAX_ACME_CERTIFICATES} certificates"
                    )
    return tuple(certificates)
