# First-profile creation copy and terminal-navigation acceptance — 2026-07-17

## Scope

This record covers the guided protocol form, stable field validation, plan
preview, revision-bound draft persistence, optional first apply, every typed
transaction outcome, expected operational failure, unknown mutation results,
and terminal return behavior.

## Accepted behavior

- One injected interface copy catalog flows through form labels and guidance,
  validation, plan, draft result, confirmation progress, all typed apply
  outcomes, operational failure, and non-disclosing unknown results.
- Application validation carries stable identities and optional structured
  context instead of presentation-ready Chinese messages.
- Profile names, endpoints, TLS paths, transaction diagnostics, and recovery
  instructions render literally with markup disabled.
- A stale draft plan terminates without direct retry. An unexpected draft write
  exposes no exception and makes no claim about the desired-state result.
- Confirmed apply runs in a worker, disables duplicate confirmation and return,
  and exposes no intermediate retry path.
- Validation, precondition, commit, successful rollback, failed rollback,
  operational error, unexpected error, and success each have a catalogued
  terminal presentation.
- Every persistence/apply terminal page provides an explicit dashboard action;
  `Esc` performs the same refresh and never reveals a consumed plan or
  confirmation.
- The root application imports only the variant catalog, guided form, and apply
  confirmation from the deep profile-creation module. That module contains no
  locale-authored Han text.

## Evidence

- Focused application and Textual Pilot tests: `62 passed` in `57.82s`.
- Full test suite: `620 passed, 18 skipped` in `183.87s`; the skips are the
  existing external-environment acceptance cases.
- Ruff formatting check: `260 files already formatted`.
- Ruff lint: `All checks passed!`.
- mypy strict source check: `Success: no issues found in 162 source files`.
- Git whitespace/error check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `3058466b562825e420b8007c4a9b56c14e8969f3f90c7ec8b29fb0c3b05d5bcd`.
- The profile-creation screen module contains no locale-authored Han text.
