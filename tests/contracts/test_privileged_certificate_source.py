import json
from pathlib import Path

import pytest

from sb_manager.adapters.privileged_certificates import (
    PrivilegedCertificateProtocolError,
    PrivilegedCertificateSource,
)
from sb_manager.seams.certificate_source import (
    CertificateMaterialState,
    CertificateTarget,
    CertificateTargetKind,
)


def test_privileged_source_round_trips_only_public_certificate_evidence(
    tmp_path: Path,
) -> None:
    request_log = tmp_path / "request.json"
    helper = tmp_path / "helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(request_log)!r}).write_text(sys.stdin.read(), encoding='utf-8')\n"
        "print(json.dumps({"
        "'schema_version': 1, 'status': 'observed', 'observations': [{"
        "'target': {'kind': 'operator-file', "
        "'server_name': 'proxy.example.com', "
        "'location': '/etc/sing-box-manager/tls/proxy.crt'}, "
        "'state': 'available', 'source_label': 'operator file', "
        "'diagnostics': 'Leaf public certificate decoded', "
        "'not_valid_before': '2026-07-01T00:00:00+00:00', "
        "'not_valid_after': '2026-10-01T00:00:00+00:00', "
        "'dns_names': ['proxy.example.com']}] }))\n",
        encoding="utf-8",
    )
    helper.chmod(0o755)
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="proxy.example.com",
        location=Path("/etc/sing-box-manager/tls/proxy.crt"),
    )

    inspection = PrivilegedCertificateSource(helper_command=(str(helper),)).inspect((target,))

    assert json.loads(request_log.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "operation": "inspect-certificates",
        "targets": [
            {
                "kind": "operator-file",
                "server_name": "proxy.example.com",
                "location": "/etc/sing-box-manager/tls/proxy.crt",
            }
        ],
    }
    assert len(inspection.observations) == 1
    observation = inspection.observations[0]
    assert observation.target == target
    assert observation.state is CertificateMaterialState.AVAILABLE
    assert observation.not_valid_after is not None
    assert observation.not_valid_after.isoformat() == "2026-10-01T00:00:00+00:00"
    assert observation.dns_names == ("proxy.example.com",)


def test_privileged_source_rejects_response_that_exposes_certificate_content(
    tmp_path: Path,
) -> None:
    helper = tmp_path / "helper"
    helper.write_text(
        "#!/usr/bin/env python3\n"
        'print(\'{"schema_version":1,"status":"observed","observations":[{'
        '"target":{"kind":"operator-file","server_name":"proxy.example.com",'
        '"location":"/etc/sing-box-manager/tls/proxy.crt"},'
        '"state":"available","source_label":"operator file","diagnostics":"",'
        '"not_valid_before":"2026-07-01T00:00:00+00:00",'
        '"not_valid_after":"2026-10-01T00:00:00+00:00",'
        '"dns_names":["proxy.example.com"],"pem":"secret"}]}\')\n',
        encoding="utf-8",
    )
    helper.chmod(0o755)
    target = CertificateTarget(
        kind=CertificateTargetKind.OPERATOR_FILE,
        server_name="proxy.example.com",
        location=Path("/etc/sing-box-manager/tls/proxy.crt"),
    )

    with pytest.raises(PrivilegedCertificateProtocolError, match="fields"):
        PrivilegedCertificateSource(helper_command=(str(helper),)).inspect((target,))
