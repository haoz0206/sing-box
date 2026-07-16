"""Installed command and production composition root."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from sb_manager.adapters.anytls_material import SecureAnyTlsMaterialSource
from sb_manager.adapters.file_apply_lock import FileApplyLock
from sb_manager.adapters.hysteria2_material import SecureHysteria2MaterialSource
from sb_manager.adapters.json_file_state import JsonFileStateStore
from sb_manager.adapters.openrc_runtime import OpenRCRuntime
from sb_manager.adapters.reality_material import SingBoxRealityMaterialSource
from sb_manager.adapters.secure_random import SecureRandomSource
from sb_manager.adapters.shadowsocks_material import SecureShadowsocksMaterialSource
from sb_manager.adapters.sing_box_validator import SingBoxConfigValidator
from sb_manager.adapters.socket_ports import SocketPortSource
from sb_manager.adapters.systemd_runtime import SystemdRuntime
from sb_manager.adapters.trojan_material import SecureTrojanMaterialSource
from sb_manager.adapters.tuic_material import SecureTuicMaterialSource
from sb_manager.adapters.vless_material import SecureVlessMaterialSource
from sb_manager.adapters.vmess_material import SecureVmessMaterialSource
from sb_manager.application.manager import Manager
from sb_manager.application.profile_apply import ProfileApplyService
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
from sb_manager.seams.runtime import Runtime
from sb_manager.tls.catalog import AcmeTlsHandler, OperatorFileTlsHandler, TlsCatalog
from sb_manager.transactions.apply import ApplyCoordinator
from sb_manager.transactions.staging import ConfigurationStager
from sb_manager.transports.catalog import TransportCatalog
from sb_manager.ui.app import ManagerApp


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
        default=Path("sing-box"),
        help="sing-box 可执行文件",
    )
    parser.add_argument(
        "--runtime",
        choices=("systemd", "openrc"),
        default="systemd",
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
    state_store = JsonFileStateStore(arguments.state_file)
    mutation_lock = FileApplyLock(
        arguments.state_file.with_name(f"{arguments.state_file.name}.apply.lock")
    )
    manager = Manager(state_store=state_store, mutation_lock=mutation_lock)
    runtime: Runtime
    if arguments.runtime == "systemd":
        runtime = SystemdRuntime(
            binary=arguments.runtime_binary or "systemctl",
            service_name=arguments.service_name or "sing-box.service",
        )
    else:
        runtime = OpenRCRuntime(
            binary=arguments.runtime_binary or "rc-service",
            service_name=arguments.service_name or "sing-box",
        )
    applier = ApplyCoordinator(
        config_path=arguments.config_file,
        stager=ConfigurationStager(parent=arguments.staging_dir),
        validator=SingBoxConfigValidator(binary=arguments.sing_box_binary),
        runtime=runtime,
    )
    profile_applier = ProfileApplyService(
        state_store=state_store,
        protocol_catalog=ProtocolCatalog(
            (
                RealityHandler(
                    material_source=SingBoxRealityMaterialSource(
                        binary=arguments.sing_box_binary,
                        random_source=SecureRandomSource(),
                        server_name=arguments.reality_server_name,
                    )
                ),
                ShadowsocksHandler(
                    material_source=SecureShadowsocksMaterialSource(
                        random_source=SecureRandomSource()
                    )
                ),
                Hysteria2Handler(
                    material_source=SecureHysteria2MaterialSource(
                        random_source=SecureRandomSource()
                    ),
                    tls_catalog=TlsCatalog(
                        (
                            AcmeTlsHandler(),
                            OperatorFileTlsHandler(),
                        )
                    ),
                ),
                TrojanHandler(
                    material_source=SecureTrojanMaterialSource(random_source=SecureRandomSource()),
                    tls_catalog=TlsCatalog(
                        (
                            AcmeTlsHandler(),
                            OperatorFileTlsHandler(),
                        )
                    ),
                ),
                AnyTlsHandler(
                    material_source=SecureAnyTlsMaterialSource(random_source=SecureRandomSource()),
                    tls_catalog=TlsCatalog(
                        (
                            AcmeTlsHandler(),
                            OperatorFileTlsHandler(),
                        )
                    ),
                ),
                TuicHandler(
                    material_source=SecureTuicMaterialSource(random_source=SecureRandomSource()),
                    tls_catalog=TlsCatalog(
                        (
                            AcmeTlsHandler(),
                            OperatorFileTlsHandler(),
                        )
                    ),
                ),
                VlessTlsHandler(
                    material_source=SecureVlessMaterialSource(random_source=SecureRandomSource()),
                    tls_catalog=TlsCatalog(
                        (
                            AcmeTlsHandler(),
                            OperatorFileTlsHandler(),
                        )
                    ),
                    transport_catalog=TransportCatalog(),
                ),
                VmessTlsHandler(
                    material_source=SecureVmessMaterialSource(random_source=SecureRandomSource()),
                    tls_catalog=TlsCatalog(
                        (
                            AcmeTlsHandler(),
                            OperatorFileTlsHandler(),
                        )
                    ),
                    transport_catalog=TransportCatalog(),
                ),
            )
        ),
        port_source=SocketPortSource(),
        applier=applier,
        apply_lock=mutation_lock,
    )
    return ManagerApp(manager=manager, profile_applier=profile_applier)


def main() -> None:
    """Launch the installed terminal application."""
    create_app().run()
