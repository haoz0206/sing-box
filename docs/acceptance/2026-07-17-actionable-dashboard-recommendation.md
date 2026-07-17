# Actionable dashboard recommendation acceptance — 2026-07-17

## Scope

This slice replaces presentation-owned dashboard priority logic with one typed
application recommendation module and makes the selected recommendation an
executable primary action. Existing planning, confirmation, diagnostics, and
host-effect workflows remain the only destinations; the dashboard does not
perform mutations directly.

## Accepted behavior

- Runtime, readiness, and managed-certificate probes are represented as typed
  reports or explicit not-configured, pending, and failed states.
- Failed readiness, runtime, and certificate probes produce direct reinspection
  actions in that safety order.
- Blocking readiness, unhealthy runtime, and urgent certificate evidence outrank
  draft and maintenance guidance and open their existing evidence workflows.
- A reviewable draft outranks certificate attention and carries the exact stable
  profile identity into the existing apply-confirmation screen.
- Empty desired state keeps profile planning available while read-only host
  checks are pending; applied desired state with pending evidence withholds the
  primary action rather than guessing health.
- Certificate attention and healthy runtime evidence remain actionable when the
  corresponding destination capability exists. Missing optional capabilities
  preserve the explanation but withhold the button.
- Textual maps stable action identities to navigation. It never parses Chinese
  wording, and every effectful destination retains its own explicit confirmation.

## Verification evidence

- Red evidence was recorded independently for each application priority rule,
  the no-host-tools fallback, and the first missing Textual primary action.
- Focused application policy: `13 passed`.
- Complete first-profile Textual journey file: `45 passed`; empty-state add,
  exact-draft review, and failed-readiness recovery all execute through the new
  primary action.
- Full test suite: `542 passed, 18 skipped`.
- Static gates: Ruff lint passed, all `244` files are formatted, mypy passed for
  `151` source files, and `git diff --check` passed.
- Release build produced both sdist and wheel successfully. Wheel SHA-256:
  `a8fbc9bbdf239ddb9e36a81f8268fc3afb049d5406e95e112badf5bbf1a1ed48`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Stable sing-box 1.14 and
authorized live systemd/OpenRC smoke tests remain external release gates.
