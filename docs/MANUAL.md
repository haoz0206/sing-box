# Sing-box Manager 软件使用手册

本手册面向通过终端管理一台 sing-box 主机的操作者。它只描述当前构建中已经可用的
行为；开发中的功能会明确标注，不应作为生产操作依据。

## 安全模型

- Dashboard 和所有检查页面默认只读。
- 配置应用、配置移除、状态恢复和核心激活都会先显示计划，再要求明确确认。
- 确认后的操作在得到终态前不能离开；意外中断会按“结果未知”处理，不会建议直接重试。
- 动态配置值、诊断信息和恢复命令按字面证据显示，不会被解释成快捷键或策略。

## 启动与导航

开发环境中运行：

```bash
.venv/bin/sb-manager
```

常用入口：

- `F1`：打开键盘帮助；
- `p`：配置工作区；
- `n`：网络意图概览；
- `s`：界面设置；
- `d`：诊断中心（启动模式提供该能力时）；
- `o`：运维中心；
- `Esc`：返回当前安全的父页面。

在 60×18 或更大的受支持终端中，Dashboard 的状态证据可以滚动，而上下文动作和
四个工作区入口保持可见。

## 管理 sing-box 核心

从 Dashboard 打开“运维中心”，再选择“安装或升级 sing-box 核心”。当前已发布的
界面要求输入一个精确版本、选择架构，并在预发布版本时单独确认兼容性风险。只读规划
会显示制品名称、由 64 个十六进制字符组成的完整 SHA-256 和信任模式：
`immutable-release` 表示上游锁定了 release 与资产；`digest-pinned-stable` 表示 Stable
release 尚可变，但计划已绑定官方精确
下载地址与 GitHub API 发布的 SHA-256。后一种模式会额外显示警告，必须在确认前审阅。
Preview 预发布版本只接受 `immutable-release`。

下载发生在非特权进程中。确认执行时，manager 会先重新读取 release 元数据；版本、
资产、地址、SHA-256、immutable/prerelease 标志或信任模式只要有一项与计划不同，就会
拒绝下载并要求重新规划。非特权 manager 下载制品并校验其 SHA-256，但不会解包或运行
制品。随后 root-only、无网络的最小权限 helper 会重新复制并再次哈希传入的归档，在
helper 内安全解包、执行版本自证并原子激活。

### Stable 与 Preview（Beta/测试）通道

从 Dashboard 打开“运维中心”，选择“管理 Stable / Preview 通道”，再选择服务器架构
和一个通道。查询过程只读，会同时解析官方精确版本并检查本机由 manager 记录的可信
安装：

- `stable` 动态解析官方最新非预发布 release，优先使用 `immutable-release`；上游 release
  尚可变时，仅在官方精确地址和 API SHA-256 都可信时使用带警告的
  `digest-pinned-stable`；
- `preview` 是 beta/测试通道，解析官方最新 prerelease；实际版本可能是 alpha、beta
  或 rc，计划会显示真实版本，不会把 alpha 错称为 beta，并且始终要求 immutable；
- 截至 2026-07-18 的官方证据是 stable `1.13.14`、preview
  `1.14.0-alpha.47`，生产代码不会硬编码这两个值；
- “latest” 每次查询都会动态解析；通道解析完成后仍会生成绑定精确版本和制品证据的
  计划，不会把会移动的 `latest` 直接交给 root helper。

进入通道页面并生成计划需要访问 GitHub。already-current 或 retained-switch 计划一旦
生成，后续审阅与执行只使用本机 manifest，不再下载制品或访问上游；当前版本没有绕过
通道发现步骤的纯离线切换入口。

查询后会出现三种结果：

- **已是当前版本**：页面明确显示精确版本，不提供确认按钮，也不会修改主机；
- **切换到已安装版本**：计划显示目标与当前制品 SHA-256；确认后只重新验证本机
  retained release 并原子切换，不下载文件；
- **下载并激活**：目标尚未可信安装；计划会显示完整 SHA-256、信任模式和相关警告，
  确认后才重新检查元数据、下载、校验并原子激活精确版本。

Preview 计划会显示预发布兼容性警告；digest-pinned Stable 计划会显示可变 release
警告。元数据在确认后发生变化时，本次操作会在下载和激活前停止，当前 active 核心
保持不变，需要返回并生成新计划。下载或 manager 侧 SHA-256 校验在进入激活边界前
失败时同样不会改变 active 核心。请求进入激活边界后，切换或激活完成前不能离开确认
页；若出现“结果未知”，按下一节检查后再决定是否重试。

2026-07-18 的实际验收中，Stable `1.13.14` 通过 `digest-pinned-stable` 流程，Preview
`1.14.0-alpha.47` 通过 `immutable-release` 流程。它们是当日证据，不是写入生产代码的
版本常量；之后查询“latest”可能得到其他精确版本。

较早版本安装的、没有 manager manifest 的核心可以继续作为当前运行目标，但不会被
静默列为 retained-switch 候选。通过可信精确版本流程重新获取后，它才会进入 retained
catalog。
“安装或升级 sing-box 核心”入口仍保留，供需要手工指定精确版本的高级操作使用。

## 配置 Snell v6

Snell 是版本受限协议。规划时以当前 active 核心实际报告的精确版本为准，不能只看
“Stable”或“Preview”通道名称。manager 只支持 sing-box `1.14.0-alpha.38` 或更新版本
上的 Snell v6，并固定生成 default mode 和一个顶层 PSK；不提供 v5、多用户
`users`/`userkey`、其他 mode、TLS、transport、multiplex、QUIC proxy 或自定义
`snell://` 链接。

Stable 1.13.x 不能规划、应用或恢复 Snell。若核心版本未知，只有 Snell 这类明确受版本
限制的协议会保守停止；先从运维中心安装并激活能够报告所需版本的 Preview 核心，再
返回配置页重新生成计划。旧计划不会因通道名称相同而继续使用：active 核心的精确
版本变化后必须重新规划。

应用并启用的 Snell 配置会阻止切换到不兼容的 Stable 核心；草案和已暂停配置不会。
需要回到 Stable 时，先暂停 Snell，或移除最后一个正在应用且启用的 Snell 配置，再
生成新的核心计划。核心计划绑定 desired-state revision；审阅后配置状态发生变化会在
下载或切换前终止旧计划。

Snell 的客户端结果是 Surge 策略，不是 URI：

```text
Name = snell, host, port, psk=<已隐藏>, version=6
```

在 Surge 中可以自行修改策略名称 `Name`。完整策略包含 PSK，默认不会挂载到界面；
只能在私密终端中通过“显示一次”显式揭示，并可立即隐藏。文档、日志和错误引导都不
应记录真实 PSK。

## 遇到“结果未知”

不要立即重复执行。这表示请求已经进入激活边界，但界面没有可信终态；helper 可能因
启动错误而根本没有运行，也可能已经修改主机。先从诊断中心检查当前核心/配置身份、
服务状态和配置应用历史，再根据页面给出的恢复证据决定下一步。核心激活还应核对
manager 的 `current` 链接和实际 `sing-box version` 输出；确认真实状态后才重新规划，
而不是直接重试旧计划。

## 当前发布边界

本项目仍处于 Python 重写和主机验收阶段。真实生产部署还需要目标发行版上的
systemd/OpenRC 冒烟测试、最小权限策略安装和所选 sing-box 通道的兼容性验证。
