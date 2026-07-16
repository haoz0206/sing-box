# Sing-box Manager

一个以安全计划、显式确认和可恢复变更为核心的 sing-box 管理 TUI。

本 fork 正在把原有 Bash 管理脚本重写为 Python 应用。这是新的产品设计，不以复刻旧脚本行为为目标。旧 Bash 文件暂时保留作迁移与功能覆盖参考，不会被 Python 入口调用。

## 当前状态

目前已经具备：

- Textual 引导式 TUI：配置列表、协议引导、计划预览、二次确认与类型化结果；
- 版本化 desired state、原子 JSON 保存、修订冲突保护和上一版备份；
- VLESS Reality、VLESS/VMess TLS WebSocket/gRPC、Shadowsocks 2022、Hysteria2、Trojan、AnyTLS 与 TUIC 的引导、凭据生成、连接 URI 和多 profile 配置；
- sing-box 1.14 共享 ACME certificate provider 与运维证书文件 TLS 策略；
- 独占 manager lock、隔离 staging、恢复备份与原子配置提交；
- `sing-box check -c` 类型化验证适配器；
- systemd/OpenRC runtime、后置健康检查、自动回滚与人工恢复步骤；
- 官方 immutable release 的精确版本获取、SHA-256 校验、安全 staging、版本自证，以及版本目录的原子激活/rollback；
- `sb-manager` 安装命令和可注入的系统边界；
- pytest、Ruff 与 mypy strict 质量门。

当前尚未完成权限提升代理、将原子制品激活接入受保护系统目录，以及 Caddy 工作流。引导式 TLS 表单目前只开放 ACME；运维证书文件已经由后端支持，但尚未接入高级表单。直接写入 `/etc/sing-box/config.json` 时，当前进程必须已经拥有目标文件和服务管理权限。真实发行前还需要受支持发行版上的 opt-in 主机冒烟测试，因此当前版本仍不应视为完整生产替代品。

## 开发运行

需要 Python 3.10 或更高版本。

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/sb-manager
```

默认状态文件为 `~/.local/state/sing-box-manager/state.json`。开发或隔离测试时可指定其他位置：

```bash
.venv/bin/sb-manager --state-file /tmp/sb-manager-state.json
```

## 质量门

```bash
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
```

测试以公开边界为主：Textual Pilot 用户行为、Manager 用例、协议语义、系统适配器契约和安装命令。单元及行为测试不需要 root 或网络。

## 设计文档

- [软件设计说明](docs/SDD.md)
- [TDD 执行方法](docs/TDD.md)
- [Python + Textual 重写决策](docs/adr/0001-python-textual-rewrite.md)
- [深协议 catalog 决策](docs/adr/0002-deep-protocol-catalog.md)
- [sing-box 制品信任策略](docs/adr/0003-sing-box-artifact-trust.md)
- [支持平台矩阵](docs/SUPPORT.md)

核心数据流为：

```text
用户意图 -> validated desired state -> execution plan -> 显式确认
        -> staged artifacts -> 外部校验 -> 原子提交 -> 运行时验证/回滚
```

任何协议扩展都应作为完整的 UI-to-config 垂直切片交付，而不是把协议判断继续堆进 UI 或系统脚本。
