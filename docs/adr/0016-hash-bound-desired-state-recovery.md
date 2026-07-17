# ADR 0016: Hash-bound desired-state backup recovery

- Status: Accepted
- Date: 2026-07-17

## Context

`JsonFileStateStore` already retained the previous desired-state revision as
`state.json.bak` before every atomic save. That backup was not reachable from
the product. If the primary JSON became truncated or malformed,
`ManagerApp.compose()` loaded it directly and the TUI terminated before an
operator could inspect the backup or choose a recovery action.

Recovery is a state mutation with two distinct hazards. A stale screen must not
replace bytes that changed after review, and an older manager must not classify
a valid future schema as corruption and overwrite it with an older backup.
Replacing the primary must also retain the exact damaged bytes for audit and
manual investigation.

## Decision

Introduce a narrow `StateRecoverySource` system seam. Its inspection returns
typed snapshots for the primary and backup: missing, readable, corrupt,
unsupported schema, or inaccessible. A readable snapshot includes the parsed
`ManagedInstallation`; every observed file includes its SHA-256 when bytes
could be read. Parsing exact byte snapshots reuses the normal JSON state schema.

`StateRecoveryService` owns recovery policy:

- a missing or readable primary starts normally;
- a primary using an unsupported schema is never offered as corruption
  recovery;
- recovery is offered only when the primary is corrupt and the backup is
  readable under the current schema;
- the review shows the backup revision and profile count without exposing
  protocol credentials;
- execution requires explicit confirmation and the shared manager mutation
  lock.

The recovery plan binds both the corrupt primary and readable backup SHA-256.
Inside the lock, the adapter reads both files again and rejects any mismatch.
It also reclassifies the exact bytes before writing, so a now-readable primary
or now-invalid backup cannot be consumed through a stale plan.

Before replacement, the adapter preserves the exact primary bytes at
`state.json.corrupt-<full-primary-sha256>`. The archive is created once with an
atomic same-filesystem link from an fsynced mode-`0600` temporary file. The
reviewed backup bytes are then written to another fsynced temporary file and
atomically replace the primary, followed by a parent-directory fsync. The
existing `.bak` is not rewritten during recovery.

At startup, Textual uses the application report instead of loading corrupt
state through `Manager`. A recoverable failure presents a safe page and a
separate confirmation screen. Unsupported or unrecoverable states present
guidance without a mutation button. One validated interface copy catalog owns
startup classification, exact-fingerprint review, confirmation, guarded
progress, rejection, terminal evidence, and unknown-result policy. SHA-256,
typed diagnostics, and the corrupt archive path remain literal evidence with
markup disabled.

A `StateRecoveryPreconditionError` proves the reviewed plan is stale and is
presented as a terminal rejection without re-enabling confirmation. A broader
`StateRecoverySourceError` cannot prove whether archive or replacement work
started, so it is classified with unhandled confirmed failures as an unknown
mutation result and never as “recovery did not run.” A failed read-only
reinspection is non-disclosing and states that no operation ran.

After a successful restore, Textual presents the restored revision, profile
count, and corrupt archive path. An explicit return action then clears the
stale recovery stack, recomposes the normal dashboard, and resumes configured
host observations.

## Consequences

- A malformed primary no longer prevents the operator from reaching a bounded
  recovery workflow.
- Review and execution refer to exact bytes, not only a revision number or file
  path.
- Future-schema state remains protected from downgrade overwrite.
- The damaged input and the backup used for recovery remain independently
  available after success.
- A stale reviewed plan cannot be retried from the terminal rejection page, and
  an uncertain storage result cannot be mistaken for a safe rejection.
- The operator sees durable success evidence before the recovered dashboard
  replaces the recovery workflow.
- Textual knows recovery availability and summary data but contains no parsing,
  hashing, locking, or file-replacement policy.
- Recovery currently restores only the automatically retained previous
  revision. Selecting arbitrary historical snapshots remains outside this
  slice.

## Rejected alternatives

### Catch every startup exception and silently load `.bak`

Rejected because it hides data loss, bypasses operator consent, and cannot
distinguish corruption from a future schema or a permission problem.

### Call `JsonFileStateStore.save(backup)` during recovery

Rejected because the normal save path would first copy the corrupt primary over
`.bak`, destroying the exact recovery source before commit.

### Bind the plan only to desired-state revision

Rejected because corrupt primary state has no trustworthy revision and two
different byte documents can claim the same revision.

### Delete the corrupt primary after successful recovery

Rejected because the original bytes are useful for audit and diagnosis, and
their full hash provides an unambiguous archive identity.

### Recover an unsupported schema when the backup is readable

Rejected because this may be a normal downgrade attempt. The safe action is to
open it with a compatible manager version, not overwrite it.
