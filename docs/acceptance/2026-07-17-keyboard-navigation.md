# Contextual keyboard navigation acceptance — 2026-07-17

## Scope

This slice adds keyboard-first navigation without widening any host mutation
boundary. The root dashboard exposes contextual shortcuts, `?` opens a focused
help screen, and printable dashboard shortcuts remain ordinary input outside
the dashboard context.

## Accepted behavior

- `?` opens keyboard help and `Escape` returns to the previous screen.
- `a` starts the purpose-first profile journey from the root dashboard.
- `p` opens the complete profiles workspace from the root dashboard.
- `n` opens the read-only network-intent workspace from the root dashboard.
- `d` opens the diagnostics center only when that capability is configured.
- `o` opens the capability-aware operations workspace; core planning remains an
  explicit selection inside it.
- `q` exits only from the root dashboard.
- Dashboard-only bindings are hidden and disabled on child screens through
  `ManagerApp.check_action`; they cannot consume form input or jump between
  workflows.
- Shortcuts only navigate. Existing plan, preview, and explicit-confirmation
  boundaries still govern configuration, removal, and core update mutations.
- Help content disables Textual markup so user-facing key notation is rendered
  literally.

## Verification evidence

- Full test suite: `502 passed, 18 skipped`.
- Focused keyboard, first-profile, diagnostics-center, and core-update journeys:
  `54 passed`.
- New keyboard Pilot journeys: `4 passed`.
- Ruff lint passed; Ruff format reported `239 files already formatted`.
- Strict mypy passed for `147 source files`.
- `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `5f504f1944c377fc25103cd2f7a5e62b1b9256897b6cd5925c653eff77499800`.
- The wheel contains both `sb_manager/ui/screens/keyboard_help.py` and
  `sb_manager/ui/theme.tcss`.

## Release boundary

This is a UI-only slice with no dependency, packaging-policy, authorization,
or host-service changes. The previously accepted real-core, wheel-install, and
Debian 12 / Ubuntu 24.04 / Alpine 3.20 container gates therefore remain
applicable. Stable sing-box 1.14 verification and authorized live systemd/OpenRC
smoke tests remain external release gates.
