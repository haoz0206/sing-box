# Typed diagnostic actions acceptance — 2026-07-17

Audited implementation: the repository state identified by the exact wheel
SHA-256 recorded below.

## Capability verdict

The diagnostics center now turns its single highest-priority recommendation
into typed navigation when an existing safe destination is available. An
untracked live configuration can open the exact-fingerprint adoption review. A
missing core can open the trusted update form only when the minimum-privilege
helper is already ready.

Opening either action is non-mutating. The adoption workflow still requires an
explicit confirmation, and the core workflow still requires version and
architecture input, pre-release consent where applicable, plan review, and
explicit activation confirmation. The diagnostics center never parses guidance
text to choose navigation.

## Repository-local evidence

- The complete pytest suite passes without root or network authorization: 330
  passed and 16 opt-in integration cases skipped.
- The diagnostics-center application behavior file covers action selection,
  report priority, helper readiness, and withholding an unsafe core action.
- Six Textual diagnostics journeys cover on-demand loading, refresh, failure
  retry, the single dashboard entry, exact-fingerprint adoption navigation, and
  trusted core-update navigation.
- The navigation tests prove that merely opening a destination neither confirms
  adoption nor plans/downloads/activates a core.
- Ruff formatting and lint checks pass for all 183 files.
- mypy passes for all 113 source files.
- `git diff --check` passes.
- The complete generated-protocol integration suite passes the real
  `sing-box 1.14.0-alpha.45 check`: 13 passed.
- The wheel and source distribution build successfully.
- The exact wheel SHA-256 is
  `7b0ebd748da048f602f1bb648ba0137999d3cd09b7a7c7f57b9b6ecee8637124`.
  That wheel passes the isolated package-release install test and the pinned
  Debian 12, Ubuntu 24.04, and Alpine 3.20 package/authorization acceptance.

## Remaining release gates

1. Run the opt-in systemd smoke on approved, recoverable Debian 12 and Ubuntu
   24.04 hosts.
2. Run the opt-in OpenRC smoke on an approved, recoverable Alpine 3.20 host.
3. Repeat the real configuration and artifact suites after upstream publishes
   stable sing-box 1.14. The currently validated 1.14 artifact remains
   [1.14.0-alpha.45](https://github.com/SagerNet/sing-box/releases/tag/v1.14.0-alpha.45).
