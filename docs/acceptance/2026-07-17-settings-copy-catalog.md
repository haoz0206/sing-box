# Settings interface copy catalog acceptance — 2026-07-17

## Scope

Start the complete UI-copy migration with one whole safety journey rather than
offering a partially translated application. This slice covers Settings and
all review, progress, conflict, typed-failure, and unknown-result screens for
hash-bound interface preference reset.

## Accepted behavior

- Settings identifies simplified Chinese as the only fully supported language
  and explains that another language remains unavailable until every safety
  journey is represented by the complete catalog.
- The existing appearance, effective-settings, reset review, cancellation,
  confirmation, conflict, recovery, and non-disclosure behavior is unchanged.
- Settings and preference-reset screens render all locale text through semantic
  identities; neither screen module retains Chinese literals.
- A catalog is immutable and cannot be constructed with a missing, extra, or
  placeholder-incompatible entry. Rendering rejects missing or extra values.
- The locale model contains only `zh-CN`; this slice introduces no partial
  second language and changes neither preference schema nor the managed host.

## Test seam

Confirmed Seam A remains the public test surface. Textual Pilot opens Settings,
observes the language scope, and drives the existing preference journeys. The
catalog is an in-process UI module, not a new external seam; construction is
exercised whenever the application imports the production catalog.

## Quality evidence

- Focused Settings acceptance: `8 passed`; combined Settings, preference-store,
  and CLI composition gate: `44 passed`.
- Full acceptance suite: `143 passed`; full repository suite: `577 passed,
  18 skipped`.
- Ruff checks passed, all 259 files were formatted, mypy strict reported no
  issues across 161 source files, and `git diff --check` passed.
- `uv build` produced source and wheel distributions. The wheel contains the
  copy catalog plus both migrated screens; its SHA-256 is
  `be1cbe20b3b91943a7ec967c1ac5f4c430e2e53994680b37a9b8974fb68ec69b`.
- A literal audit found no Chinese text in either migrated screen module.

## Remaining localization boundary

This is the first complete journey, not a claim that the entire TUI is ready
for another locale. Dashboard, Profiles, Network, Operations, Diagnostics,
guided forms, and their application-provided operator messages must migrate
before a language selector or second catalog can be accepted.
