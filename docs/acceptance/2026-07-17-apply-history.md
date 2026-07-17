# Configuration apply history acceptance — 2026-07-17

## Scope

This record covers durable pre-mutation apply evidence, typed completion and
interruption semantics, bounded private JSON persistence, shared disclosure
policy, diagnostics-center classification, Textual drill-down, direct and
privileged production composition, package construction, and supported-
distribution installation policy.

## Evidence

- Full local suite: `498 passed, 18 skipped`.
- Focused history, diagnostics, Textual, persistence, and production-composition
  set: `42 passed`.
- Ruff format and lint: passed.
- mypy strict source check: `Success: no issues found in 146 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Source distribution and wheel build: passed; the wheel contains the history
  seam, atomic JSON and memory adapters, recording/classification application
  module, shared disclosure policy, diagnostics integration, production
  composition, and Textual screen.
- Package release install integration from the exact wheel: `1 passed`.
- Distribution policy acceptance using host networking for the configured
  host-loopback package proxy:
  - Debian 12 / sudo: passed with Python 3.11 and a manylinux wheel;
  - Ubuntu 24.04 / sudo: passed with Python 3.12 and a manylinux wheel;
  - Alpine 3.20 / doas: passed with Python 3.12 and a musllinux wheel.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `c245ace9cfb2465df214ea9e74266dd8204e06f3ab75d44a65d6f2f76af6346d`.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- Every configuration application composed by the CLI—initial apply, live
  edit, pause/resume, and applied-profile removal—passes through one decorator
  around the existing `ConfigurationApplier` seam in both direct and privileged
  modes.
- A strict `in-progress` entry is durably written before the host delegate is
  called. If the begin write fails, the host apply is not executed and the
  operator receives an actionable error.
- Completion preserves the attempt ID, start time, candidate SHA-256, and active
  profile count while adding a timezone-aware completion time, typed transaction
  outcome, and bounded diagnostics.
- A failed final history update does not rewrite the host transaction result.
  The existing `in-progress` entry remains as conservative evidence that the
  final state must be checked. Reported system-boundary exceptions are completed
  as `execution-error` on a best-effort basis and then propagate unchanged;
  unexpected termination leaves `in-progress` evidence.
- Persisted protocol secrets and common credential forms share one conservative
  disclosure boundary with service logs. History diagnostics are capped at 4096
  characters and record the number of redactions.
- The JSON store uses schema version 1, exact fields, duplicate rejection,
  atomic replacement, directory synchronization, file mode `0600`, a one-MiB
  input bound, final-path symlink refusal, and newest-100 retention. Corrupt or
  unsupported history is never silently overwritten before an apply.
- The ledger stores no generated configuration document, desired-state
  snapshot, share URI, credential, certificate, or private key.
- The diagnostics center classifies successful, attention, action-required,
  missing, and unavailable history without parsing diagnostic text. The Textual
  drill-down loads the newest 20 entries in a worker, supports refresh, and
  renders all dynamic values with markup disabled.
- History remains unprivileged and beside desired state; the root helper
  protocol and host allowlist are unchanged.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when
  released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this interaction slice.
