# Session appearance and effective Settings acceptance — 2026-07-17

## Scope

Add the missing Settings destination from the SDD information architecture
without inventing unsafe host-policy editors or pretending a session choice is
already persisted. Deliver one immediate appearance preference and disclose the
effective production startup choices that explain how the manager will act.

## Accepted behavior

- Dashboard exposes a default-terminal-visible `打开设置` action and contextual
  `s` shortcut; `?` documents it and child screens suppress it.
- Settings states that Simplified Chinese is the only current UI language.
- Dark/light selection applies immediately to the complete Textual application,
  survives closing and reopening Settings within the same process, and is
  explicitly limited to the current session.
- Appearance changes do not write desired state, live configuration, helper
  policy, or host settings. No persistence claim or preference file is made.
- Production composition supplies the effective direct/helper access mode,
  systemd/OpenRC runtime, desired-state path, direct live-config path or
  helper-fixed policy, and active transaction directory.
- Core updates remain manual exact-version operations; Settings states that no
  automatic update occurs.
- Additional language choices remain absent until a complete string catalog can
  preserve every safety workflow.

## Test seam and evidence

- Confirmed Seam A: Textual `App.run_test()` and Pilot only for new user
  behavior. Existing installed-command composition tests cover construction of
  the production app with the injected effective settings.
- Focused Settings, keyboard, and CLI composition set: `29 passed`.
- Complete acceptance suite: `137 passed`.
- Complete repository suite: `558 passed, 18 skipped`.
- Ruff check passed; Ruff format reported `254 files already formatted`;
  strict mypy passed for `157 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully, both including
  `sb_manager/ui/screens/settings.py`.
- Wheel SHA-256:
  `4a89152058751d5663d325118f96bd01ecc50bc5329b9496e75c2cb6cdb20459`.

## External release boundary

This slice changes Textual presentation and read-only startup disclosure only.
It adds no privileged mutation and no preference-store adapter. Stable-release
status still requires the supported stable sing-box 1.14 gate and separately
authorized live systemd/OpenRC acceptance on recoverable hosts.
