"""Installed command and production composition root."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from sb_manager.adapters.anytls_material import SecureAnyTlsMaterialSource
from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.adapters.file_config_target import FileConfigurationTargetInspector
from sb_manager.adapters.github_artifacts import GitHubArtifactSource
from sb_manager.adapters.hysteria2_material import SecureHysteria2MaterialSource
from sb_manager.adapters.json_file_state import JsonFileStateStore
from sb_manager.adapters.openrc_runtime import OpenRCRuntime
from sb_manager.adapters.privileged_config_applier import PrivilegedConfigurationApplier
from sb_manager.adapters.privileged_config_target import (
    PrivilegedConfigurationTargetInspector,
)
from sb_manager.adapters.privileged_core_activator import PrivilegedCoreActivator
from sb_manager.adapters.reality_material import SingBoxRealityMaterialSource
from sb_manager.adapters.secure_random import SecureRandomSource
from sb_manager.adapters.shadowsocks_material import SecureShadowsocksMaterialSource
from sb_manager.adapters.sing_box_core_status import SingBoxCoreStatusInspector
from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.adapters.socket_ports import SocketPortSource
from sb_manager.adapters.systemd_runtime import SystemdRuntime
from sb_manager.adapters.trojan_material import SecureTrojanMaterialSource
from sb_manager.adapters.tuic_material import SecureTuicMaterialSource
from sb_manager.adapters.urllib_http import UrllibHttpClient
from sb_manager.adapters.vless_material import SecureVlessMaterialSource
from sb_manager.adapters.vmess_material import SecureVmessMaterialSource
from sb_manager.application.config_adoption import ConfigAdoptionService
from sb_manager.application.core_update import CoreUpdateService
from sb_manager.application.diagnostics_center import DiagnosticsCenterService
from sb_manager.application.host_diagnostics import RuntimeHostDiagnostics
from sb_manager.application.host_readiness import (
    HostAccessMode,
    HostReadinessService,
)
from sb_manager.application.manager import Manager
from sb_manager.application.profile_apply import ProfileApplyService
from sb_manager.application.profile_details import ProfileDetailsService
from sb_manager.application.profile_editing import ProfileEditingService
from sb_manager.application.profile_removal import ProfileRemovalService
from sb_manager.protocols.catalog import (
    AnyTlsHandler,
    Hysteria2Handler,
    ProtocolCatalog,
    RealityHandler,
    ShadowsocksHandler,
    TrojanHandler,
    TuicHandler,
    VlessTlsHandler,
    VmessTlsHandler,
)
from sb_manager.seams.config_target import ConfigurationTargetInspector
from sb_manager.seams.configuration_applier import ConfigurationApplier
from sb_manager.seams.runtime import Runtime, RuntimeKind
from sb_manager.tls.catalog import AcmeTlsHandler, OperatorFileTlsHandler, TlsCatalog
from sb_manager.transactions.apply import ApplyCoordinator
from sb_manager.transactions.staging import ConfigurationStager
from sb_manager.transports.catalog import TransportCatalog
from sb_manager.ui.app import ManagerApp, ManagerAppHostTools

MANAGED_CORE_BINARY = Path("/opt/sing-box-manager/core/current/sing-box")


def create_runtime(
    *,
    runtime_kind: RuntimeKind,
    binary: str | Path | None = None,
    service_name: str | None = None,
) -> Runtime:
    """Select one production runtime with init-system-specific defaults."""
    if runtime_kind is RuntimeKind.SYSTEMD:
        return SystemdRuntime(
            binary=binary or "systemctl",
            service_name=service_name or "sing-box.service",
        )
    return OpenRCRuntime(
        binary=binary or "rc-service",
        service_name=service_name or "sing-box",
    )


def create_protocol_catalog(
    *,
    sing_box_binary: str | Path,
    reality_server_name: str,
) -> ProtocolCatalog:
    """Build the complete production protocol catalog behind one composition seam."""
    random_source = SecureRandomSource()
    tls_catalog = TlsCatalog((AcmeTlsHandler(), OperatorFileTlsHandler()))
    return ProtocolCatalog(
        (
            RealityHandler(
                material_source=SingBoxRealityMaterialSource(
                    binary=sing_box_binary,
                    random_source=random_source,
                    server_name=reality_server_name,
                )
            ),
            ShadowsocksHandler(
                material_source=SecureShadowsocksMaterialSource(random_source=random_source)
            ),
            Hysteria2Handler(
                material_source=SecureHysteria2MaterialSource(random_source=random_source),
                tls_catalog=tls_catalog,
            ),
            TrojanHandler(
                material_source=SecureTrojanMaterialSource(random_source=random_source),
                tls_catalog=tls_catalog,
            ),
            AnyTlsHandler(
                material_source=SecureAnyTlsMaterialSource(random_source=random_source),
                tls_catalog=tls_catalog,
            ),
            TuicHandler(
                material_source=SecureTuicMaterialSource(random_source=random_source),
                tls_catalog=tls_catalog,
            ),
            VlessTlsHandler(
                material_source=SecureVlessMaterialSource(random_source=random_source),
                tls_catalog=tls_catalog,
                transport_catalog=TransportCatalog(),
            ),
            VmessTlsHandler(
                material_source=SecureVmessMaterialSource(random_source=random_source),
                tls_catalog=tls_catalog,
                transport_catalog=TransportCatalog(),
            ),
        )
    )


def create_app(argv: Sequence[str] | None = None) -> ManagerApp:
    """Build the TUI with production adapters selected from command arguments."""
    parser = argparse.ArgumentParser(
        prog="sb-manager",
        description="通过引导式 TUI 搭建和维护 sing-box 代理服务",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=Path.home() / ".local/state/sing-box-manager/state.json",
        help="desired state 文件路径",
    )
    parser.add_argument(
        "--config-file",
        type=Path,
        default=Path("/etc/sing-box/config.json"),
        help="生成的 sing-box 配置路径",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=Path.home() / ".cache/sing-box-manager/staging",
        help="事务 staging 目录",
    )
    parser.add_argument(
        "--sing-box-binary",
        type=Path,
        help=(
            "sing-box 可执行文件，privileged 模式默认使用 manager 激活的核心，"
            "direct 模式默认从 PATH 查找"
        ),
    )
    parser.add_argument(
        "--apply-mode",
        choices=("direct", "privileged"),
        default="direct",
        help="直接应用或通过最小权限 helper 应用",
    )
    parser.add_argument(
        "--privilege-runner",
        type=Path,
        default=Path("/usr/bin/sudo"),
        help="调用 root helper 的 sudo 或 doas 绝对路径",
    )
    parser.add_argument(
        "--privileged-helper-binary",
        type=Path,
        default=Path("/opt/sing-box-manager/bin/sb-manager-privileged"),
        help="root-owned privileged helper 绝对路径",
    )
    parser.add_argument(
        "--privileged-incoming-dir",
        type=Path,
        default=Path("/var/lib/sing-box-manager/incoming"),
        help="与 privileged helper 共享的 incoming 目录",
    )
    parser.add_argument(
        "--runtime",
        choices=tuple(kind.value for kind in RuntimeKind),
        default=RuntimeKind.SYSTEMD.value,
        help="服务管理器",
    )
    parser.add_argument(
        "--runtime-binary",
        type=Path,
        help="systemctl 或 rc-service 可执行文件",
    )
    parser.add_argument(
        "--service-name",
        help="服务单元名称",
    )
    parser.add_argument(
        "--reality-server-name",
        default="www.cloudflare.com",
        help="Reality 默认伪装站点",
    )
    arguments = parser.parse_args(argv)
    access_mode = HostAccessMode(arguments.apply_mode)
    sing_box_binary = arguments.sing_box_binary or (
        MANAGED_CORE_BINARY if access_mode is HostAccessMode.PRIVILEGED else Path("sing-box")
    )
    privileged_helper_command = (
        str(arguments.privilege_runner),
        "-n",
        str(arguments.privileged_helper_binary),
    )
    state_store = JsonFileStateStore(arguments.state_file)
    mutation_lock = FileApplyLock(
        arguments.state_file.with_name(f"{arguments.state_file.name}.apply.lock")
    )
    manager = Manager(state_store=state_store, mutation_lock=mutation_lock)
    runtime = create_runtime(
        runtime_kind=RuntimeKind(arguments.runtime),
        binary=arguments.runtime_binary,
        service_name=arguments.service_name,
    )
    applier: ConfigurationApplier
    config_inspector: ConfigurationTargetInspector
    privileged_config_inspector = PrivilegedConfigurationTargetInspector(
        helper_command=privileged_helper_command
    )
    if access_mode is HostAccessMode.PRIVILEGED:
        config_inspector = privileged_config_inspector
        applier = PrivilegedConfigurationApplier(
            incoming_directory=arguments.privileged_incoming_dir,
            helper_command=privileged_helper_command,
        )
    else:
        config_inspector = FileConfigurationTargetInspector(config_path=arguments.config_file)
        applier = ApplyCoordinator(
            config_path=arguments.config_file,
            stager=ConfigurationStager(parent=arguments.staging_dir),
            validator=SingBoxConfigValidator(binary=sing_box_binary),
            runtime=runtime,
        )
    protocol_catalog = create_protocol_catalog(
        sing_box_binary=sing_box_binary,
        reality_server_name=arguments.reality_server_name,
    )
    profile_applier = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=protocol_catalog,
        port_source=SocketPortSource(),
        applier=applier,
        apply_lock=mutation_lock,
    )
    core_updater = CoreUpdateService(
        artifact_source=GitHubArtifactSource(http_client=UrllibHttpClient()),
        core_activator=PrivilegedCoreActivator(helper_command=privileged_helper_command),
        incoming_directory=arguments.privileged_incoming_dir,
    )
    host_diagnostics = RuntimeHostDiagnostics(runtime=runtime)
    host_readiness = HostReadinessService(
        access_mode=access_mode,
        config_inspector=config_inspector,
        privileged_inspector=privileged_config_inspector,
        core_inspector=SingBoxCoreStatusInspector(binary=sing_box_binary),
    )
    return ManagerApp(
        manager=manager,
        profile_applier=profile_applier,
        core_updater=core_updater,
        host_tools=ManagerAppHostTools(
            host_diagnostics=host_diagnostics,
            diagnostics_center=DiagnosticsCenterService(
                state_store=state_store,
                config_inspector=config_inspector,
                host_readiness=host_readiness,
                host_diagnostics=host_diagnostics,
            ),
            host_readiness=host_readiness,
            profile_details_reader=ProfileDetailsService(
                state_store=state_store,
                protocol_catalog=protocol_catalog,
            ),
            profile_editor=ProfileEditingService(
                state_store=state_store,
                protocol_catalog=protocol_catalog,
                applier=applier,
                apply_lock=mutation_lock,
            ),
            profile_remover=ProfileRemovalService(
                state_store=state_store,
                protocol_catalog=protocol_catalog,
                applier=applier,
                apply_lock=mutation_lock,
            ),
            config_adopter=ConfigAdoptionService(
                state_store=state_store,
                config_inspector=config_inspector,
                mutation_lock=mutation_lock,
            ),
        ),
    )


def main() -> None:
    """Launch the installed terminal application."""
    create_app().run()
