# Hash-bound interface preference reset acceptance — 2026-07-17

## Scope

Turn an unavailable persisted-appearance state into an actionable recovery
journey without silently repairing, deleting, or downgrading unknown local
preferences. The workflow remains isolated from desired state, live
configuration, helper policy, and the managed host.

## Accepted behavior

- Settings exposes `审查并重置界面偏好` only when persistence is unavailable.
- Opening the workflow performs no write and shows only the complete SHA-256,
  schema-v1 dark default, and exact no-host-effect scope. Preference content and
  parser errors remain absent.
- `Esc` cancellation returns to Settings and leaves the original bytes intact.
- Confirmation is a guarded background operation. It rechecks the complete
  reviewed SHA-256 before creating any archive or replacement.
- Changed bytes produce an actionable stale-plan result, remain untouched, and
  do not create an archive for the obsolete fingerprint.
- Candidate inspection and confirmation-time revalidation reject documents
  larger than 64 KiB without reading or mutating them as reset candidates.
- A matching unreadable regular file is preserved byte-for-byte in a
  hash-named mode-`0600` archive before the main path is atomically replaced by
  strict schema-v1 dark preferences.
- Archive publication is atomic and exclusive: a file created at the archive
  path by another process is never overwritten and is accepted only when its
  bytes exactly match the reviewed document.
- Success returns to Settings, immediately applies dark appearance, hides the
  recovery action, and is loaded normally by a new application instance.
- Symbolic links and unsafe targets remain non-mutating manual-recovery cases;
  unexpected post-confirmation exceptions never disclose content or claim a
  known local-file result.

## Test seams and evidence

- Confirmed Seam A: Textual Pilot covers review, cancellation, confirmation,
  visible scope, stale-plan guidance, immediate theme restoration, and a new
  application instance.
- Confirmed Seam D: the JSON adapter contract covers exact candidate identity,
  bounded document reads, conflict-before-archive behavior, private archival,
  and atomic schema-v1 replacement.
- Focused Settings, JSON-store, and CLI gate: `44 passed`.
- Full acceptance gate: `143 passed`.
- Full repository gate: `577 passed, 18 skipped`.
- Static analysis: Ruff checks passed, all 258 files were formatted, mypy strict
  reported no issues across 160 source files, and `git diff --check` passed.
- `uv build` produced both source and wheel distributions. The wheel contains
  the preference application module, JSON adapter, and reset screen; its
  SHA-256 is
  `06390b0ad19ca6ac122b14d3c59ed5fbedc99d054d146fab5da4ebe08602b4bf`.

## External release boundary

This slice mutates only one explicitly configured current-user preference file
and its same-directory private archive. It adds no privileged or host mutation;
the repository's independent stable-core and authorized live-host gates remain.
