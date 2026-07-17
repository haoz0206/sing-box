# Persisted appearance and effective Settings acceptance — 2026-07-17

## Scope

Extend the Settings destination with one honest per-user appearance preference
without inventing unsafe host-policy editors. Persist only the complete color
scheme document and continue to disclose the effective production startup
choices that explain how the manager will act.

## Accepted behavior

- Dashboard exposes a default-terminal-visible `打开设置` action and contextual
  `s` shortcut; `?` documents it and child screens suppress it.
- Settings states that Simplified Chinese is the only current UI language.
- Dark/light selection applies immediately to the complete Textual application,
  survives reopening Settings, and is restored by a new application instance.
- The default preference path follows an absolute `XDG_CONFIG_HOME` or
  `~/.config`, and `--preferences-file` supports explicit isolation. Settings
  discloses the exact effective path.
- Schema v1 JSON is written with same-directory atomic replacement and mode
  `0600`. Symbolic links, invalid documents, unknown fields, and future schemas
  are rejected without overwriting their bytes.
- A failed load defaults to a usable dark session and never renders the raw
  document or exception. A requested color change still applies to the current
  process, while Settings accurately reports that it could not be saved.
- Appearance changes do not write desired state, live configuration, helper
  policy, or host settings. The preference file belongs only to the current
  Unix operator.
- Production composition supplies the effective direct/helper access mode,
  systemd/OpenRC runtime, desired-state path, direct live-config path or
  helper-fixed policy, and active transaction directory.
- Core updates remain manual exact-version operations; Settings states that no
  automatic update occurs.
- Additional language choices remain absent until a complete string catalog can
  preserve every safety workflow.

## Test seam and evidence

- Confirmed Seam A: Textual `App.run_test()` and Pilot for cross-instance user
  behavior and non-disclosing fallback.
- Confirmed Seam D: strict JSON store contract with a test memory adapter and
  the production atomic filesystem adapter.
- Confirmed Seam E: `create_app()` option/default resolution and complete
  production composition.
- Focused Settings, JSON contract, and CLI composition set: `38 passed`.
- Complete Textual acceptance suite: `140 passed`.
- Complete repository suite: `571 passed, 18 skipped`; skipped cases remain
  explicitly opted-in external integration and live-host gates.
- Ruff check passed; Ruff format reported `257 files already formatted`;
  strict mypy passed for `159 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully. The wheel contains the
  application preference module, JSON adapter, and Settings screen.
- Wheel SHA-256:
  `1d6c867a95c82a70bb232baed60d72ea7f10862d5d1bbd12b1f1532eaca3fb8f`.

## External release boundary

This slice adds one unprivileged per-user local file and no privileged mutation.
Stable-release status still requires the supported stable sing-box 1.14 gate
and separately authorized live systemd/OpenRC acceptance on recoverable hosts.
