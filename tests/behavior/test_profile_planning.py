from pathlib import Path

import pytest

from sb_manager.application.manager import (
    AcmeTlsRequest,
    GeneratedValue,
    Manager,
    OperatorFileTlsRequest,
    PlanProfileRequest,
    PlanValidationError,
    ProfilePlan,
    ValidationIssue,
)
from sb_manager.domain.installation import PortSelection, ProtocolKind
from sb_manager.tls.catalog import AcmeTlsIntent, OperatorFileTlsIntent


def test_operator_can_plan_a_reality_profile_without_host_changes() -> None:
    manager = Manager()

    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=4433,
        )
    )

    assert plan == ProfilePlan(
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=4433,
        port_selection=PortSelection.FIXED,
        base_revision=0,
        generated_values=(
            GeneratedValue.UUID,
            GeneratedValue.REALITY_KEY_PAIR,
            GeneratedValue.SERVER_NAME,
        ),
        mutates_host=False,
    )


def test_operator_is_told_when_a_profile_name_is_missing() -> None:
    manager = Manager()

    with pytest.raises(PlanValidationError) as caught:
        manager.plan_profile(
            PlanProfileRequest(
                profile_name=" ",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=4433,
            )
        )

    assert caught.value.issues == (ValidationIssue(field="profile_name", message="请输入配置名称"),)


def test_operator_can_defer_port_selection_to_apply_time() -> None:
    manager = Manager()

    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="手机",
            protocol=ProtocolKind.VLESS_REALITY,
            listen_port=None,
        )
    )

    assert plan == ProfilePlan(
        profile_name="手机",
        protocol=ProtocolKind.VLESS_REALITY,
        listen_port=None,
        port_selection=PortSelection.AUTOMATIC,
        base_revision=0,
        generated_values=(
            GeneratedValue.UUID,
            GeneratedValue.REALITY_KEY_PAIR,
            GeneratedValue.SERVER_NAME,
        ),
        mutates_host=False,
    )


def test_operator_is_told_when_a_fixed_port_is_out_of_range() -> None:
    manager = Manager()

    with pytest.raises(PlanValidationError) as caught:
        manager.plan_profile(
            PlanProfileRequest(
                profile_name="手机",
                protocol=ProtocolKind.VLESS_REALITY,
                listen_port=65_536,
            )
        )

    assert caught.value.issues == (
        ValidationIssue(field="listen_port", message="端口必须在 1 到 65535 之间"),
    )


def test_operator_can_plan_hysteria2_with_acme_without_internal_path_input(
    tmp_path: Path,
) -> None:
    manager = Manager(acme_data_directory=tmp_path / "acme")

    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="移动网络",
            protocol=ProtocolKind.HYSTERIA2,
            listen_port=8443,
            server_address="vpn.example.com",
            tls=AcmeTlsRequest(
                server_name="vpn.example.com",
                email="operator@example.com",
            ),
        )
    )

    assert plan == ProfilePlan(
        profile_name="移动网络",
        protocol=ProtocolKind.HYSTERIA2,
        listen_port=8443,
        port_selection=PortSelection.FIXED,
        base_revision=0,
        generated_values=(
            GeneratedValue.HYSTERIA2_PASSWORD,
            GeneratedValue.TLS_CERTIFICATE,
        ),
        mutates_host=False,
        server_address="vpn.example.com",
        tls_intent=AcmeTlsIntent(
            server_name="vpn.example.com",
            email="operator@example.com",
            data_directory=tmp_path / "acme",
        ),
    )


def test_operator_is_told_which_hysteria2_acme_fields_are_missing() -> None:
    manager = Manager()

    with pytest.raises(PlanValidationError) as caught:
        manager.plan_profile(
            PlanProfileRequest(
                profile_name="移动网络",
                protocol=ProtocolKind.HYSTERIA2,
                listen_port=8443,
                tls=AcmeTlsRequest(server_name=" ", email=" "),
            )
        )

    assert caught.value.issues == (
        ValidationIssue(field="tls_server_name", message="请输入证书域名"),
        ValidationIssue(field="tls_email", message="请输入 ACME 联系邮箱"),
    )


def test_operator_can_plan_trusted_existing_tls_files_without_generating_a_certificate(
    tmp_path: Path,
) -> None:
    tls_directory = tmp_path / "tls"
    manager = Manager(trusted_tls_directory=tls_directory)

    plan = manager.plan_profile(
        PlanProfileRequest(
            profile_name="已有证书",
            protocol=ProtocolKind.TROJAN,
            listen_port=443,
            tls=OperatorFileTlsRequest(
                server_name="vpn.example.com",
                certificate_path=tls_directory / "server.crt",
                key_path=tls_directory / "server.key",
            ),
        )
    )

    assert plan.tls_intent == OperatorFileTlsIntent(
        server_name="vpn.example.com",
        certificate_path=tls_directory / "server.crt",
        key_path=tls_directory / "server.key",
    )
    assert plan.generated_values == (GeneratedValue.TROJAN_PASSWORD,)


def test_operator_tls_files_cannot_escape_the_trusted_directory(tmp_path: Path) -> None:
    tls_directory = tmp_path / "tls"
    manager = Manager(trusted_tls_directory=tls_directory)

    with pytest.raises(PlanValidationError) as caught:
        manager.plan_profile(
            PlanProfileRequest(
                profile_name="越界证书",
                protocol=ProtocolKind.TROJAN,
                listen_port=443,
                tls=OperatorFileTlsRequest(
                    server_name="vpn.example.com",
                    certificate_path=tmp_path / "outside.crt",
                    key_path=tls_directory / "../outside.key",
                ),
            )
        )

    assert caught.value.issues == (
        ValidationIssue(
            field="tls_certificate_path",
            message=f"证书文件必须位于 {tls_directory}",
        ),
        ValidationIssue(
            field="tls_key_path",
            message=f"私钥文件必须位于 {tls_directory}",
        ),
    )
