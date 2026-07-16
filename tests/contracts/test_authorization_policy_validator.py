import json
from pathlib import Path

import pytest

from sb_manager.adapters.authorization_policy_validator import (
    AuthorizationPolicyValidationError,
    SubprocessAuthorizationPolicyValidator,
)
from sb_manager.installation.privileged_policy import AuthorizationProvider


def write_validator(tmp_path: Path, *, exit_code: int = 0) -> tuple[Path, Path]:
    binary = tmp_path / f"validator-{exit_code}"
    log_path = tmp_path / f"validator-{exit_code}.json"
    binary.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n"
        f"Path({str(log_path)!r}).write_text(json.dumps(sys.argv[1:]), encoding='utf-8')\n"
        + (
            "print('policy syntax rejected', file=sys.stderr)\nraise SystemExit(1)\n"
            if exit_code
            else "raise SystemExit(0)\n"
        ),
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary, log_path


@pytest.mark.parametrize(
    ("provider", "expected_arguments"),
    (
        (AuthorizationProvider.SUDO, ["-cf"]),
        (AuthorizationProvider.DOAS, ["-C"]),
    ),
)
def test_provider_policy_is_checked_with_the_native_parser(
    tmp_path: Path,
    provider: AuthorizationProvider,
    expected_arguments: list[str],
) -> None:
    validator_binary, log_path = write_validator(tmp_path)
    policy_path = tmp_path / "policy.conf"
    policy_path.write_text("fixed policy\n", encoding="utf-8")
    validator = SubprocessAuthorizationPolicyValidator(
        sudo_validator=validator_binary,
        doas_validator=validator_binary,
    )

    validator.validate(provider, policy_path)

    assert json.loads(log_path.read_text()) == [*expected_arguments, str(policy_path)]


def test_native_parser_rejection_preserves_diagnostics(tmp_path: Path) -> None:
    validator_binary, _ = write_validator(tmp_path, exit_code=1)
    policy_path = tmp_path / "policy.conf"
    policy_path.write_text("broken policy\n", encoding="utf-8")

    with pytest.raises(AuthorizationPolicyValidationError, match="policy syntax rejected"):
        SubprocessAuthorizationPolicyValidator(
            sudo_validator=validator_binary,
            doas_validator=validator_binary,
        ).validate(AuthorizationProvider.SUDO, policy_path)
