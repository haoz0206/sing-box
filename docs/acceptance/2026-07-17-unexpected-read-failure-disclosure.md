# Unexpected read-failure disclosure acceptance — 2026-07-17

## Scope

This slice closes top-level exception disclosure paths in three read-only
Textual workflows: the diagnostics center, bounded service-log drill-down, and
configuration apply-history drill-down. It changes no application/system seam
and no host behavior.

## Accepted behavior

- A typed diagnostics, service-log, or apply-history report still renders its
  bounded, already-sanitized evidence.
- An exception raised before a typed report exists is caught at the Textual
  worker edge.
- The raw exception is neither retained by the screen nor rendered to Static
  widgets.
- The user sees operation-specific generic guidance explaining that details
  were hidden to avoid sensitive disclosure.
- The relevant read-only retry remains enabled.
- Refresh does not mutate desired state, configuration, artifacts, or runtime.

## Verification evidence

- Red evidence: diagnostics-center `token=private-diagnostics-value` was rendered
  verbatim before the implementation.
- Red evidence: service-log `password=private-log-reader-error` was rendered
  verbatim before the implementation.
- Red evidence: apply-history `token=private-history-reader-error` was rendered
  verbatim before the implementation.
- Focused non-disclosure journeys: `3 passed`.
- Complete diagnostics-center acceptance file: `15 passed`.
- Full test suite: `506 passed, 18 skipped`.
- Ruff format reported `239 files already formatted`; Ruff lint passed.
- Strict mypy passed for `147 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `de90052d003aca1e166276edfd148112e9a07db728f1d55a9403828e66008067`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, or runtime adapter changed. Previously accepted real-core,
wheel-install, and Debian 12 / Ubuntu 24.04 / Alpine 3.20 container evidence
therefore remains applicable. Stable sing-box 1.14 verification and authorized
live systemd/OpenRC smoke tests remain external release gates.
