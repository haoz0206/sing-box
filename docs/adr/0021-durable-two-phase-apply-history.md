# ADR 0021: Durable two-phase configuration apply history

- Status: Accepted
- Date: 2026-07-17

## Context

The manager already returns a typed transaction result for one live
configuration apply, but that result disappears when the process exits. Desired
state cannot prove whether the last host transaction validated, committed,
rolled back, failed during rollback, or was interrupted. Runtime logs are also
an unsuitable audit source: they are init-system-specific, may be unavailable,
and do not bind evidence to the exact candidate configuration.

Recording only after a transaction completes leaves the most important failure
window invisible: process termination between the first host mutation and the
final record. Recording full generated documents or plans would unnecessarily
duplicate credentials and private configuration material.

## Decision

Decorate the existing `ConfigurationApplier` deep seam once in the production
composition root. Profile creation, live editing, pause/resume, and removal
already converge on this interface, so lifecycle use cases remain unaware of
storage details and cannot drift into different audit behavior.

Before delegation, atomically write an `in-progress` entry containing an opaque
attempt ID, timezone-aware start time, canonical candidate SHA-256, active
inbound count, and a fixed diagnostic. If this durable begin fails, reject the
operation before the host applier runs. This makes the safety claim explicit:
an unrecorded apply is not attempted.

After the delegate returns, replace that exact entry with its completion time,
typed transaction outcome, and bounded diagnostics assembled from validation,
commit, runtime refresh, postcondition, and rollback evidence. Persisted
protocol material and common credential forms pass through the shared
disclosure policy. If the final update fails, keep the durable `in-progress`
record and return the delegate's exact result; the ledger conservatively says
that its final result is unknown rather than reclassifying a successful host
transaction as failed. Reported system-boundary exceptions are recorded as
`execution-error` on a best-effort basis and then re-raised unchanged;
unexpected process termination leaves the earlier `in-progress` evidence.

Use a strict versioned JSON store beside desired state, with atomic replacement,
file mode `0600`, a one-MiB input bound, duplicate/extra-field rejection,
symlink refusal, immutable begin/complete evidence, and retention of the newest
100 attempts. The file contains no generated document, desired-state snapshot,
connection link, credential, certificate, or private key.

The read interface defaults to the newest 20 entries. The latest successful
entry is healthy; validation, precondition, commit, or completed rollback
failures require attention; rollback failure, execution error, and
`in-progress` require operator action. An unavailable or corrupt ledger is
attention and never a healthy claim. Textual loads the drill-down in a worker
and renders every dynamic field with markup disabled.

## Consequences

- Every live lifecycle operation shares one audit policy without widening the
  privileged helper protocol.
- A crash after durable begin remains visible across restarts as unknown host
  state that requires inspection.
- History availability becomes a precondition for new applies, while a failed
  final write does not erase or falsify the host transaction result.
- The ledger identifies candidate content and outcome but does not identify a
  specific UI action or retain enough data to reconstruct configuration.
- Concurrent mutation safety continues to rely on the existing manager apply
  lock; readers are safe during writes because replacement is atomic.

## Rejected alternatives

### Infer history from desired state or current runtime

Rejected because both are present-state observations and cannot distinguish
validation failure, rollback, interruption, or externally changed state.

### Write one record only after completion

Rejected because termination during the host transaction would leave no durable
evidence that an apply began.

### Store history inside desired state

Rejected because audit retention would inflate revisions, couple unrelated
schemas, and make a damaged desired-state file erase both intent and history.

### Persist generated documents or full plans

Rejected because the candidate SHA-256 is sufficient for identity. Full content
would duplicate secrets and expand backup, permission, and disclosure risks.
