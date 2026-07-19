# Contributing to Sing-box Manager

感谢你帮助改进 Sing-box Manager。项目优先考虑可恢复变更、最小权限和明确的兼容性证据，
因此用户可见功能应作为从意图、计划、确认到验证和回滚的完整垂直切片交付。

## 开始之前

- 使用 GitHub Discussions 讨论使用问题和尚未收敛的设计想法。
- 提交可复现缺陷时使用 Bug 模板，并删除凭据、私钥、域名、IP 和主机日志中的敏感信息。
- 安全漏洞不要提交公开 Issue；请遵循 [`SECURITY.md`](SECURITY.md)。
- 较大的功能先开 Issue，说明用户问题、协议或核心版本边界、权限变化与回滚策略。

## 开发环境

项目支持 Python 3.10–3.14：

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

提交前运行：

```bash
.venv/bin/pytest -q
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
```

默认测试必须离线、非 root 且可重复。需要网络、真实 sing-box 二进制、init 系统或主机权限的
验收必须显式 opt-in，并记录版本、平台、信任证据和未覆盖边界。

## 变更要求

- 从测试开始描述行为；修复缺陷时至少增加一个回归测试。
- 保持模块边界清晰，不把协议判断、权限判断或展示文案重新堆入 UI。
- 任何特权操作都必须有只读计划、显式确认、确认时重检、有限输入和可操作失败结果。
- 用户可见或兼容性变更更新 `CHANGELOG.md` 和相关手册、ADR 或验收记录。
- 不提交真实凭据、私钥、状态文件、完整日志或生产主机数据。
- Pull Request 保持单一目的，并完整填写验证与安全检查清单。

提交即表示你同意按仓库的 GPL-3.0-only 许可证分发贡献，并遵守
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)。
