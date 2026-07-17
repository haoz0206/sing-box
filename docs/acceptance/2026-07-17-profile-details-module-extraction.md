# Profile details deep-module extraction acceptance — 2026-07-17

## Scope

This record covers the behavior-preserving extraction of profile details from
the Textual composition root into one deep presentation module. No product
behavior, application interface, system effect, or persistence schema changes.

## Accepted architecture

- The root application loads one `ProfileDetails` report, constructs one
  immutable `ProfileDetailsCapabilities` bundle, and selects expected versus
  unexpected read-error presentation.
- The details module owns scrollable evidence composition, connection-share
  disclosure, capability-aware edit/remove/pause-resume/clone routing, lifecycle
  planning-error classification, and successful clone refresh.
- Its external interface contains the capabilities bundle, details screen, and
  two read-error screens, declared explicitly through module `__all__`.
  Lifecycle workflow screens remain implementation dependencies rather than new
  root-application responsibilities.
- Existing application seams for details reading, editing, removal,
  availability, and cloning are unchanged; no extraction-only port or adapter
  was introduced.
- Existing Textual Pilot journeys remain the only behavior seam. No tests refer
  to the new module path, private methods, or internal screen fields.

## Equivalence evidence

- Before extraction: the profile workspace, details, editing, removal,
  availability, and cloning journey gate reported `67 passed`.
- After extraction: the identical command reported `67 passed` in `72.03s`.
- Full test suite: `621 passed, 18 skipped` in `183.37s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `262 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 164 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `67e1db4efe1e4520d53cabcdcd314b14017e1a5718b58f687970299a66df5cb6`.
- The root application and profile-details module contain no locale-authored Han
  text.
