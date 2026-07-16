# Sing-box Manager

一个以安全计划、显式确认和可恢复变更为核心的 sing-box 管理 TUI。

本 fork 正在把原有 Bash 管理脚本重写为 Python 应用。这是新的产品设计，不以复刻旧脚本行为为目标。旧 Bash 文件暂时保留作迁移与功能覆盖参考，不会被 Python 入口调用。

## 当前状态

目前已经具备：

- Textual 引导式 TUI：配置列表、后台服务健康检查、可操作诊断、协议引导、
  首次启动主机准备度、计划预览、二次确认、持久化配置详情/连接链接与类型化结果；
- 核心安装/升级向导：精确版本与架构选择、预发布风险确认、后台下载、可信校验及激活证据；
- 版本化 desired state、原子 JSON 保存、修订冲突保护和上一版备份；
- VLESS Reality、VLESS/VMess TLS WebSocket/gRPC、Shadowsocks 2022、Hysteria2、Trojan、AnyTLS 与 TUIC 的引导、凭据生成、连接 URI 和多 profile 配置；
- sing-box 1.14 共享 ACME certificate provider 与运维证书文件 TLS 策略；
- 独占 manager lock、隔离 staging、恢复备份与原子配置提交；
- `sing-box check -c` 类型化验证适配器；
- systemd/OpenRC runtime、后置健康检查、自动回滚与人工恢复步骤；
- 官方 immutable release 的精确版本获取、SHA-256 校验、安全 staging、版本自证，以及版本目录的原子激活/rollback；
- root-only、无网络、固定路径与版本化 JSON 协议的 core activation/config apply helper；
- root-owned 目录与 sudo/doas 最小授权策略安装命令，落盘前调用原生语法校验器；
- 现有 live configuration 的只读指纹检查、显式接管计划和 apply 前精确
  SHA-256 前置条件，避免静默覆盖或审阅后的竞态修改；
- `sb-manager` 安装命令和可注入的系统边界；
- pytest、Ruff 与 mypy strict 质量门。

最小权限 helper 已支持 core 激活以及固定配置目标的校验、提交、runtime health 和 rollback；unprivileged TUI 的核心向导始终通过非交互 helper 激活，配置应用则可通过显式 privileged apply 模式调用它。引导式 TLS 表单支持推荐的 sing-box ACME，以及固定 trusted 目录下 root 管理证书文件的高级路径。Caddy 边缘编排明确后移到首个稳定版之后。直接模式写入 `/etc/sing-box/config.json` 时，当前进程仍必须拥有目标文件和服务管理权限。真实稳定发行前仍需要受支持发行版上的 live host 冒烟测试，以及上游稳定 sing-box 1.14，因此当前版本仍不应视为完整生产替代品。

## 开发运行

需要 Python 3.10 或更高版本。

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/sb-manager
```

在完成 [权限 helper 部署约束](docs/PRIVILEGED_HELPER.md) 后，主机应用应显式使用最小权限模式：

```bash
.venv/bin/sb-manager --apply-mode privileged
```

该模式以非交互 `-n` 调用默认 `/usr/bin/sudo` 和 root-owned helper。开发隔离根或已有完整权限的进程可继续使用默认 `direct` 模式。

dashboard 会在后台只读检查最小权限 helper、固定配置目标和 sing-box 核心，
把阻塞项与仅影响核心升级的提醒分开，并给出下一步操作。`privileged` 模式默认使用
manager 激活的 `/opt/sing-box-manager/core/current/sing-box`；`direct` 模式默认从
`PATH` 查找。两种模式都可通过 `--sing-box-binary` 显式覆盖。

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
- [最小权限 helper 决策](docs/adr/0004-minimal-privileged-helper.md)
- [权限 helper 部署约束](docs/PRIVILEGED_HELPER.md)
- [支持平台矩阵](docs/SUPPORT.md)
- [2026-07-16 发行版授权验收记录](docs/acceptance/2026-07-16-distro-policy.md)

核心数据流为：

```text
用户意图 -> validated desired state -> execution plan -> 显式确认
        -> staged artifacts -> 外部校验 -> 原子提交 -> 运行时验证/回滚
```

任何协议扩展都应作为完整的 UI-to-config 垂直切片交付，而不是把协议判断继续堆进 UI 或系统脚本。
