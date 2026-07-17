# Contextual keyboard navigation acceptance — 2026-07-17

## Scope

This slice adds keyboard-first navigation without widening any host mutation
boundary. The root dashboard exposes contextual shortcuts, non-printable `F1`
opens focused help from ordinary screens, `?` remains a compatible non-input
entry, and printable shortcuts remain ordinary form input outside the dashboard
context.

## Accepted behavior

- `F1` opens keyboard help even while a form input is focused; `Escape` returns
  to the same screen with the entered value and focus preserved.
- `?` opens the same help outside input focus and remains ordinary text inside
  an input.
- Repeating `F1` or `?` on the help page does not stack another help screen.
- After a mutation is explicitly confirmed, F1 cannot hide its non-returning
  progress screen; the shared confirmation guard releases auxiliary navigation
  only after a typed terminal result.
- `a` starts the purpose-first profile journey from the root dashboard.
- `p` opens the complete profiles workspace from the root dashboard.
- `n` opens the read-only network-intent workspace from the root dashboard.
- `s` opens Settings from the root dashboard and remains ordinary input on
  child screens.
- `d` opens the diagnostics center only when that capability is configured.
- `o` opens the capability-aware operations workspace; core planning remains an
  explicit selection inside it.
- `q` exits only from the root dashboard.
- Dashboard-only bindings are hidden and disabled on child screens through
  `ManagerApp.check_action`; they cannot consume form input or jump between
  workflows.
- Shortcuts only navigate. Existing plan, preview, and explicit-confirmation
  boundaries still govern configuration, removal, and core update mutations.
- One injected interface copy catalog owns the help title, navigation and
  dashboard sections, key guides, context explanation, and safety statement.
  The Screen contains no locale-authored Han text and disables Textual markup so
  key notation is rendered literally.

## Verification evidence

- Red evidence: an injected marker catalog initially left the hard-coded
  `键盘操作帮助` visible.
- Red evidence: `F1` on a focused core-version input initially left the operator
  on the form with no help screen.
- Red evidence: pressing `F1`, then `?`, then `Escape` initially returned to a
  duplicate help page instead of the original Dashboard.
- Red evidence: F1 initially opened help over a blocked, confirmed Core Update
  worker and hid its required progress screen.
- Keyboard Pilot journeys: `8 passed` in `5.35s`.
- Affected Keyboard/Core Update/Operations/Network acceptance set: `31 passed`
  in `29.22s`.
- Complete repository suite: `653 passed, 18 skipped` in `206.07s`.
- Ruff check passed; Ruff format reported `263 files already formatted`;
  strict mypy passed for `164 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `9f97aa48f227be93441fea7587400483673a0c4bf10ce954a1b1bd4026b5e302`.
- The wheel contains the updated `sb_manager/ui/app.py`,
  `sb_manager/ui/confirmed_operation.py`, `sb_manager/ui/copy_catalog.py`, and
  `sb_manager/ui/screens/keyboard_help.py`.
- The wheel contains both `sb_manager/ui/screens/keyboard_help.py` and
  `sb_manager/ui/theme.tcss`.

## Release boundary

This is a UI-only slice with no dependency, packaging-policy, authorization,
or host-service changes. The previously accepted real-core, wheel-install, and
Debian 12 / Ubuntu 24.04 / Alpine 3.20 container gates therefore remain
applicable. Stable sing-box 1.14 verification and authorized live systemd/OpenRC
smoke tests remain external release gates.
