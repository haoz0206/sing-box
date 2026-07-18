# Sing-box Manager

一个以安全计划、显式确认和可恢复变更为核心的 sing-box 管理 TUI。

本 fork 正在把原有 Bash 管理脚本重写为 Python 应用。这是新的产品设计，不以复刻旧脚本行为为目标。旧 Bash 文件暂时保留作迁移与功能覆盖参考，不会被 Python 入口调用。

## 当前状态

目前已经具备：

- Textual 引导式 TUI：Dashboard 只保留服务状态、配置计数与唯一安全建议，完整配置
  清单和生命周期入口集中在独立 Profiles 工作区，可通过 `p` 或可见按钮进入；
  Profiles 清单的标题、只读安全声明、状态、端口、行模板和能力动作均由校验目录
  渲染，清单按钮只发出 typed navigation request，不直接执行配置变更；
  配置详情使用可滚动只读视图展示身份、状态、服务器地址和端口意图，敏感分享链接
  默认隐藏且仅能显式显示一次；详情与分享错误文案统一由目录渲染，生命周期按钮只
  打开既有计划或确认步骤；详情展示、披露和四类生命周期路由集中在独立深模块，
  根应用只负责读取报告与顶层导航；
  Dashboard 始终说明当前检查只读、任何变更仍需审阅计划和明确确认，其状态标题、
  探测结果、计数、唯一建议、动作标签、导航和重试文案统一由校验目录渲染；
  应用层只选择稳定的推荐与动作身份，不携带或解析展示型中文；
  独立 Network 工作区通过 `n` 展示 desired state 中的 TCP/UDP、固定/自动端口、
  启用/暂停/草案和公开地址意图，并明确不执行网络探测或防火墙变更；
  Settings 工作区通过 `s` 切换深/浅外观，并以当前用户独立的 schema v1 JSON
  原子保存到 XDG 配置目录；新进程会恢复选择，损坏、符号链接或未来 schema
  会保留原文件并降级为可用且不披露异常的会话状态；普通文件可经 SHA-256
  绑定的审查与二次确认先私密归档原字节、再重置为默认深色，审阅后变化会拒绝；
  Settings 与偏好重置旅程的全部可见文案已进入严格校验的简体中文目录，并明确说明
  完整安全流程迁移完成前不开放其他语言，避免部分翻译造成误判；
  页面只读展示实际生效的
  direct/helper、systemd/OpenRC、更新策略和路径，不把主机策略伪装成可编辑设置；
  另有后台服务健康检查、可操作诊断、协议引导、上下文键盘快捷键与 `?` 操作帮助，
  完整诊断中心不可用时仍可进入独立的只读运行时诊断页；健康/异常说明、无详情回退、
  恢复区标签和步骤编号来自校验目录，底层诊断与恢复命令保持非 markup 字面证据；
  以及能力感知的运维中心（集中进入核心计划、
  服务日志与配置应用历史，缺失能力显示原因而非无效按钮）、
  基于 desired state、运行时、准备度和证书证据生成的类型化唯一主操作、
  后台检查失败时的保守状态与原位重试、
  首页独立显示托管证书正常/关注/需处理/无法检查状态及安全重试、
  首次启动主机准备度、计划预览、二次确认、持久化配置详情/连接链接与类型化结果；
- 用途优先的配置向导：先选择通用、移动/低延迟、受限网络或既有客户端兼容，
  再查看三项带原因和明确代价的协议/传输变体排序；推荐不自动应用，也不承诺
  特定网络连通性，高级入口仍可直接选择全部支持变体；选择后由独立的首次配置
  深模块完成表单、稳定验证身份、计划、草案保存、首次应用和全部终态，未知结果
  不提供直接重试，所有终态按钮和 `Esc` 都清除旧流程并刷新 Dashboard；
- 按需加载的诊断中心：统一检查 desired state 一致性、实时配置 SHA-256 身份、
  完整生成配置的 `sing-box check` 语义、配置目标、最小权限 helper、核心与 runtime，
  并在有界 worker 中检查公开地址和 TLS 域名解析；可识别未接管、缺失、外部漂移、
  不可应用的 desired state 和部分 DNS 故障，验证诊断会脱敏协议凭据，
  还会按协议核对启用且已应用的 TCP/UDP 监听端点，并只在 `/proc` 证据完整时确认
  sing-box 进程归属；未监听、外部占用和权限导致的归属未知保持不同严重度，
  同时检查运维文件与 CertMagic ACME 缓存中的公开叶证书：30 天内到期提示关注、
  7 天内到期或已过期要求处理，缺失/无效/权限未知保持不同证据且绝不读取私钥；
  按“需处理/注意/正常”排序并给出唯一推荐动作；对未接管配置和 helper 已就绪
  时的核心缺失提供安全上下文按钮，只进入审查/计划页而不直接执行变更；还可钻取
  最近 200 行 systemd/OpenRC 服务日志，统一限量、清理控制字符并脱敏后显示；配置
  应用则在主机变更前留下持久化开始记录，并保留最近 100 次有界结果，诊断页可查看
  最近 20 次状态、候选 SHA-256、生效配置数和脱敏证据，不保存配置正文或私钥；
  诊断中心、服务日志和应用历史若在生成类型化报告前意外失败，只显示非披露的重试
  指引，不会把底层异常原文带入终端；
- desired-state 启动检查、配置详情、用途推荐、新配置计划、配置接管计划和核心更新
  计划若发生未分类读取失败，也会保留可用 TUI，隐藏异常原文并说明尚未执行的范围；
- 配置详情中的生命周期移除：草案只提交 desired state；已应用配置先预览影响，
  再生成完整剩余配置并复用校验、原子提交、服务健康检查和自动回滚；
- 配置详情中的引导式编辑：可修正名称、公开服务器地址和监听端口；端口支持固定值
  或确认时自动选择，预览会区分仅 desired state 的策略/元数据变更与需要端口复检、
  完整校验、刷新、健康检查和回滚的 live configuration 变更；表单、计划、确认进度、
  全部事务结果与错误引导统一由校验文案目录渲染，动态配置值和诊断证据禁用 markup；
- 配置详情中的暂停/恢复：已应用配置可临时退出完整 live configuration，同时保留
  稳定 ID、端口和凭据；恢复时复检固定端口或在锁内重选自动端口，并复用完整事务、
  健康检查、回滚和人工恢复证据；计划、确认进度、全部事务结果和错误引导统一由
  校验文案目录渲染，动态配置值、诊断与恢复命令禁用 markup；
- 配置详情中的安全模板：复用协议、公开地址、TLS 和传输意图，明确重置认证材料、
  监听端口与运行状态，经名称审阅和显式确认后只创建草案，适合为新设备快速搭建
  独立凭据的相似配置；
- 配置详情中的编辑、移除、暂停/恢复和模板入口若在只读计划阶段发生未分类异常，
  会隐藏底层错误、明确说明尚未执行操作，并引导返回列表后重新读取；
- 编辑、移除、暂停/恢复、模板创建或 desired-state 恢复成功返回首页时，会统一清除
  旧观察并重新启动 runtime、准备度和证书维护检查，避免重建后的 dashboard 永久
  停留在“正在检查”或短暂沿用变更前结论；
- 包含完整访问凭据的连接链接在持久化配置详情和首次应用成功页均默认隐藏；页面只
  展示公开端点与风险说明，必须由操作者在私密终端中显式选择“显示一次连接链接”才
  会挂载只读文本；操作者可立即重新隐藏且本页不能二次显示，离开页面后也会自动
  恢复隐藏，整个过程不会自动写入剪贴板；
- 核心安装/升级向导：精确版本与架构选择、语义化预发布风险确认、后台下载、可信校验
  及激活证据；表单验证、计划、进度、结果与恢复策略统一由校验文案目录渲染，
  类型化下载/helper 诊断保持原始非 markup 证据；
- 配置应用、编辑、移除、暂停/恢复、模板创建、配置接管、desired-state 恢复或
  核心激活在确认后若发生未分类异常，
  会显示
  非披露的“结果未知”指导，
  不猜测服务器或 desired state 是否变化，也不会引导用户直接重试；
- 版本化 desired state、原子 JSON 保存、修订冲突保护和上一版备份；主文件损坏时
  TUI 可通过统一文案目录预览备份 revision/配置数量和主文件/备份的完整 SHA-256，
  经二次确认和不可返回进度后原子恢复，同时保留损坏原字节；指纹变化会终止旧计划，
  持久化结果不确定时不会误报“未执行”，成功页展示 revision、配置数和归档路径后再
  显式刷新 Dashboard；未来 schema 不会被降级覆盖；
- VLESS Reality、VLESS/VMess TLS WebSocket/gRPC、Shadowsocks 2022、Hysteria2、Trojan、AnyTLS 与 TUIC 的引导、凭据生成、连接 URI 和多 profile 配置；
- sing-box 1.14 共享 ACME certificate provider 与运维证书文件 TLS 策略；
- 独占 manager lock、隔离 staging、恢复备份与原子配置提交；
- `sing-box check -c` 类型化验证适配器；
- systemd/OpenRC runtime、后置健康检查、自动回滚与人工恢复步骤；
- 官方 release 的精确版本获取：优先使用 immutable release；仅对已发布、非草稿、非预发布的 Stable release，在精确官方 URL 与 API SHA-256 绑定下允许 digest-pinned fallback；Preview 始终只接受 immutable release；随后执行 SHA-256 校验、安全 staging、版本自证，以及版本目录的原子激活/rollback；
- root-only、无网络、固定路径与版本化 JSON 协议的 core activation/config apply helper；
- root-owned 目录与 sudo/doas 最小授权策略安装命令，落盘前调用原生语法校验器；
- 现有 live configuration 的只读指纹检查、显式接管计划和 apply 前精确
  SHA-256 前置条件，避免静默覆盖或审阅后的竞态修改；加载、审阅、确认进度、结果
  与恢复策略统一由校验文案目录渲染，成功后显式清除陈旧计划并刷新 Dashboard；
- `sb-manager` 安装命令和可注入的系统边界；
- 精确 retained release 的只读回退计划、显式 root 确认和原子 package
  activation，不需要手工修改 `/opt` 下的链接；
- pytest、Ruff 与 mypy strict 质量门。

最小权限 helper 已支持 core 激活以及固定配置目标的校验、提交、runtime health 和 rollback；unprivileged TUI 的核心向导始终通过非交互 helper 激活，配置应用则可通过显式 privileged apply 模式调用它。引导式 TLS 表单支持推荐的 sing-box ACME，以及固定 trusted 目录下 root 管理证书文件的高级路径。Caddy 边缘编排明确后移到首个稳定版之后。直接模式写入 `/etc/sing-box/config.json` 时，当前进程仍必须拥有目标文件和服务管理权限。真实稳定发行前仍需要受支持发行版上的 live host 冒烟测试，以及上游稳定 sing-box 1.14，因此当前版本仍不应视为完整生产替代品。

## 版本化安装（预发布）

构建或取得经过审核的 wheel 后，先预览版本、SHA-256、依赖来源和全部目标路径：

```bash
.venv/bin/sb-manager-install \
  --wheel dist/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse
```

确认内容后以 root 执行同一计划，并安装最小权限策略：

```bash
sudo .venv/bin/sb-manager-install \
  --wheel dist/sing_box_manager-0.1.0-py3-none-any.whl \
  --wheelhouse /path/to/reviewed-wheelhouse \
  --confirm
sudo /opt/sing-box-manager/bin/sb-manager-install-policy \
  --authorization sudo --group sing-box-manager
sudo /opt/sing-box-manager/bin/sb-manager-install-policy \
  --authorization sudo --group sing-box-manager --confirm
```

正式 package release 位于版本 + wheel SHA-256 命名的只读目录。四个稳定 launcher
通过一个原子 `current` 链接同步切换，不会原地升级正在使用的 venv。Alpine 将
`sudo` 和 `--authorization sudo` 分别替换为 `doas` 与 `--authorization doas`。

若新 package release 出现回归，先从 `/opt/sing-box-manager/releases` 选择完整的
`<version>-<wheel-sha256>` 名称并预览回退；命令不会猜测“上一个版本”：

```bash
/opt/sing-box-manager/bin/sb-manager-install \
  --rollback-to 0.1.0-<完整的-64-位-wheel-sha256>
sudo /opt/sing-box-manager/bin/sb-manager-install \
  --rollback-to 0.1.0-<完整的-64-位-wheel-sha256> \
  --confirm
```

确认阶段会在安装锁内重新检查当前目标、retained release 身份、所有权、写权限和
稳定命令，然后只原子切换 `current`；现用 release 仍会保留，可用同一机制切回。

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

默认状态文件为 `~/.local/state/sing-box-manager/state.json`，应用历史以权限 `0600`
保存在同目录的 `state.json.apply-history.json`。开发或隔离测试时可指定其他位置：

```bash
.venv/bin/sb-manager --state-file /tmp/sb-manager-state.json
```

界面偏好默认保存在绝对的 `$XDG_CONFIG_HOME/sing-box-manager/preferences.json`，
未设置或为相对路径时回退到 `~/.config/sing-box-manager/preferences.json`；隔离测试可用
`--preferences-file` 指定其他位置。该文件不属于 desired state，也不会交给 root helper。

## 质量门

```bash
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
```

测试以公开边界为主：Textual Pilot 用户行为、Manager 用例、协议语义、系统适配器契约和安装命令。单元及行为测试不需要 root 或网络。

## 设计文档

- [软件使用手册](docs/MANUAL.md)
- [软件设计说明](docs/SDD.md)
- [TDD 执行方法](docs/TDD.md)
- [Python + Textual 重写决策](docs/adr/0001-python-textual-rewrite.md)
- [深协议 catalog 决策](docs/adr/0002-deep-protocol-catalog.md)
- [sing-box 制品信任策略](docs/adr/0003-sing-box-artifact-trust.md)
- [Stable/Preview 核心通道决策](docs/adr/0023-dual-core-release-channels.md)
- [最小权限 helper 决策](docs/adr/0004-minimal-privileged-helper.md)
- [版本化 Python package 安装决策](docs/adr/0006-versioned-python-package-installation.md)
- [事务化配置移除决策](docs/adr/0007-transactional-profile-removal.md)
- [修订绑定的配置元数据编辑决策](docs/adr/0008-revision-bound-profile-metadata-editing.md)
- [优先级诊断中心决策](docs/adr/0009-prioritized-read-only-diagnostics-center.md)
- [类型化诊断动作决策](docs/adr/0010-typed-diagnostic-actions.md)
- [事务化监听端口编辑决策](docs/adr/0011-transactional-listen-port-editing.md)
- [生成配置语义诊断决策](docs/adr/0012-generated-configuration-diagnostics.md)
- [公开域名解析诊断决策](docs/adr/0013-public-domain-resolution-diagnostics.md)
- [事务化配置暂停/恢复决策](docs/adr/0014-transactional-profile-pause-resume.md)
- [用途优先的协议推荐决策](docs/adr/0015-purpose-first-protocol-recommendations.md)
- [desired state 哈希绑定备份恢复决策](docs/adr/0016-hash-bound-desired-state-recovery.md)
- [无敏感材料的配置模板克隆决策](docs/adr/0017-secret-free-profile-template-cloning.md)
- [有界脱敏服务日志决策](docs/adr/0018-bounded-redacted-service-log-drill-down.md)
- [保守的 Linux 监听归属诊断决策](docs/adr/0019-conservative-linux-listener-ownership-diagnostics.md)
- [有界最小披露的托管证书诊断决策](docs/adr/0020-bounded-managed-certificate-diagnostics.md)
- [持久化两阶段配置应用历史决策](docs/adr/0021-durable-two-phase-apply-history.md)
- [目录化首次配置创建决策](docs/adr/0022-catalogued-first-profile-creation.md)
- [权限 helper 部署约束](docs/PRIVILEGED_HELPER.md)
- [支持平台矩阵](docs/SUPPORT.md)
- [2026-07-16 发行版授权验收记录](docs/acceptance/2026-07-16-distro-policy.md)
- [2026-07-17 发布就绪审计](docs/acceptance/2026-07-17-release-audit.md)
- [2026-07-17 配置应用历史验收](docs/acceptance/2026-07-17-apply-history.md)
- [2026-07-17 配置应用历史交互文案验收](docs/acceptance/2026-07-17-apply-history-copy.md)
- [2026-07-17 服务日志交互文案验收](docs/acceptance/2026-07-17-service-logs-copy.md)
- [2026-07-17 上下文键盘导航验收](docs/acceptance/2026-07-17-keyboard-navigation.md)
- [2026-07-17 仪表盘检查失败验收](docs/acceptance/2026-07-17-dashboard-probe-failures.md)
- [2026-07-17 意外读取失败披露验收](docs/acceptance/2026-07-17-unexpected-read-failure-disclosure.md)
- [2026-07-17 主机变更结果未知验收](docs/acceptance/2026-07-17-unknown-mutation-results.md)
- [2026-07-17 配置生命周期结果未知验收](docs/acceptance/2026-07-17-profile-lifecycle-unknown-results.md)
- [2026-07-17 配置操作边界失败验收](docs/acceptance/2026-07-17-profile-action-boundary-failures.md)
- [2026-07-17 TUI 失败边界验收](docs/acceptance/2026-07-17-tui-failure-boundaries.md)
- [2026-07-17 显式连接链接揭示验收](docs/acceptance/2026-07-17-explicit-connection-share-disclosure.md)
- [2026-07-17 Dashboard 维护与刷新验收](docs/acceptance/2026-07-17-dashboard-maintenance-refresh.md)
- [2026-07-17 可执行 Dashboard 建议验收](docs/acceptance/2026-07-17-actionable-dashboard-recommendation.md)
- [2026-07-17 能力感知运维中心验收](docs/acceptance/2026-07-17-capability-aware-operations-workspace.md)
- [2026-07-17 Dashboard / Profiles 信息架构验收](docs/acceptance/2026-07-17-profiles-workspace-information-architecture.md)
- [2026-07-17 只读 Network 工作区验收](docs/acceptance/2026-07-17-read-only-network-workspace.md)
- [2026-07-17 会话外观与有效 Settings 验收](docs/acceptance/2026-07-17-session-settings-workspace.md)
- [2026-07-17 哈希绑定界面偏好重置验收](docs/acceptance/2026-07-17-hash-bound-preference-reset.md)
- [2026-07-17 Settings 文案目录验收](docs/acceptance/2026-07-17-settings-copy-catalog.md)
- [2026-07-17 Dashboard 只读状态外壳验收](docs/acceptance/2026-07-17-dashboard-read-only-copy-shell.md)
- [2026-07-17 Dashboard 语义推荐文案验收](docs/acceptance/2026-07-17-dashboard-semantic-recommendation-copy.md)
- [2026-07-17 Profiles 工作区文案与安全边界验收](docs/acceptance/2026-07-17-profiles-workspace-copy.md)
- [2026-07-17 配置详情与敏感分享边界验收](docs/acceptance/2026-07-17-profile-details-copy.md)
- [2026-07-17 配置编辑文案与事务边界验收](docs/acceptance/2026-07-17-profile-edit-copy.md)
- [2026-07-17 配置暂停恢复文案与事务边界验收](docs/acceptance/2026-07-17-profile-availability-copy.md)
- [2026-07-17 配置移除文案与事务边界验收](docs/acceptance/2026-07-17-profile-removal-copy.md)
- [2026-07-17 无敏感材料配置模板文案验收](docs/acceptance/2026-07-17-profile-clone-copy.md)
- [2026-07-17 用途优先协议推荐与恢复验收](docs/acceptance/2026-07-17-profile-recommendation.md)
- [2026-07-17 核心更新文案与结果边界验收](docs/acceptance/2026-07-17-core-update-copy.md)
- [2026-07-17 精确指纹配置接管文案验收](docs/acceptance/2026-07-17-config-adoption-copy.md)
- [2026-07-17 desired state 恢复文案与结果边界验收](docs/acceptance/2026-07-17-state-recovery-copy.md)
- [2026-07-17 首次配置创建文案与终态导航验收](docs/acceptance/2026-07-17-first-profile-creation-copy.md)
- [2026-07-17 主机运行时诊断回退页验收](docs/acceptance/2026-07-17-host-runtime-diagnostics-copy.md)
- [2026-07-17 诊断中心交互文案验收](docs/acceptance/2026-07-17-diagnostics-center-copy.md)
- [2026-07-17 配置详情深模块提取验收](docs/acceptance/2026-07-17-profile-details-module-extraction.md)

核心数据流为：

```text
用户意图 -> validated desired state -> execution plan -> 显式确认
        -> staged artifacts -> 外部校验 -> 原子提交 -> 运行时验证/回滚
```

任何协议扩展都应作为完整的 UI-to-config 垂直切片交付，而不是把协议判断继续堆进 UI 或系统脚本。创建、应用、暂停/恢复和移除使用同一个完整配置投影规则，避免不同生命周期操作生成不一致的 sing-box 文档。
