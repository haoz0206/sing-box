# Desired-state backup recovery acceptance — 2026-07-17

## Scope

This record covers startup classification of the manager-owned primary and
backup state files, review and confirmation policy, stale-plan protection,
crash-safe restoration, corrupt-byte preservation, Textual recovery journeys,
production composition, package construction, and supported-distribution
installation policy.

## Evidence

- Full local suite: `419 passed, 18 skipped`.
- Focused recovery/application/adapter/TUI/composition tests: `10 passed`.
- Ruff formatting: `204 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 125 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Source distribution and wheel build: passed.
- Package release install integration from the exact wheel: `1 passed`.
- Distribution policy acceptance using host networking for the configured
  host-loopback package proxy:
  - Debian 12 / sudo: passed;
  - Ubuntu 24.04 / sudo: passed;
  - Alpine 3.20 / doas: passed.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `2b93bd91a8117ec44c0d9ac072f0b6ed164b57df47a891a581aec29247b1f788`.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- A missing or readable primary state starts the normal dashboard.
- A malformed primary is classified separately from an unsupported future
  schema and an inaccessible file.
- Recovery is offered only when the primary is corrupt and `.bak` parses under
  the current state schema.
- The startup page exposes only the backup revision and profile count; it does
  not display persisted credentials.
- An unsupported future schema never receives a recovery button and is not
  overwritten by an older backup.
- The recovery plan binds the exact primary and backup SHA-256 values and does
  not mutate the host.
- Confirmation is required before acquiring the shared manager mutation lock.
- Execution re-reads, re-hashes, and reclassifies both files inside the lock;
  changed primary or backup bytes reject the stale plan.
- The exact corrupt primary bytes are retained at a full-hash archive path and
  durably linked before primary replacement.
- The reviewed backup bytes atomically replace the primary; `.bak` remains
  unchanged and readable after success.
- Storage or `fsync` failure is returned as a typed unconfirmed-durability
  error instead of escaping the Textual worker.
- A successful confirmation dismisses the recovery screen, recomposes the
  normal dashboard, and resumes host observations.
- Production composition uses `JsonStateRecoverySource` and the same
  `FileApplyLock` as all other desired-state mutations.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when
  released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this recovery slice.
