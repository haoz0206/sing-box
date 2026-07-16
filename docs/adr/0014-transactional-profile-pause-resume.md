# ADR 0014: Transactional profile pause and resume

- Status: Accepted
- Date: 2026-07-17

## Context

Operators sometimes need to take one applied inbound offline temporarily while
retaining its stable identity, credentials, public endpoint, and listen-port
intent. Removing and later recreating a profile is unsafe for this purpose: it
loses lifecycle continuity, may rotate client material, and makes a reversible
operational action look destructive.

An applied profile previously expressed both historical lifecycle and current
participation in the live configuration through one `APPLIED` status. Those are
different facts. A paused profile is still manager-owned applied intent, but it
must not appear in the generated sing-box inbounds.

## Decision

Keep `ProfileStatus.APPLIED` as the durable lifecycle fact and add the boolean
`ManagedProfile.enabled` as current live-participation intent. Existing state
files default a missing `enabled` field to `true`.

The complete managed configuration projector includes only profiles that are
both applied and enabled. Pausing and resuming use one `ProfileAvailability`
application seam with a pure, revision-bound plan followed by explicit
confirmation.

Confirmation acquires the shared mutation lock, rechecks the desired-state
revision and reviewed profile fields, projects the complete configuration, and
reuses the existing fingerprint precondition, external validation, atomic
commit, runtime refresh, health check, and rollback transaction. Desired state
advances only when the host transaction reports `APPLIED`.

Pausing preserves the profile ID, protocol material, server address, listen
port, and port-selection policy. Resuming a fixed-port profile probes its
recorded port during planning and again under the lock. An automatic profile
reuses its recorded port when available; otherwise it chooses a new port under
the lock while excluding every port declared by another profile.

Edits and removals of paused profiles are desired-state-only because the
profile is absent from the live projection. Draft profiles continue to use the
existing first-apply workflow and cannot be paused or resumed.

## Consequences

- Temporary service withdrawal no longer destroys identity or client material.
- Dashboard, details, persistence, diagnostics, editing, and removal all share
  the same explicit online/paused distinction.
- A final active profile can be paused through the real zero-inbound document.
- Fixed-port resume remains advisory at preview and authoritative under lock.
- Every failed transaction leaves desired state unchanged; rollback failure
  exposes exact recovery instructions.
- The state schema remains backward-compatible, but new writers persist the
  explicit `enabled` field.

## Rejected alternatives

### Remove and recreate the profile

Rejected because a temporary operational state must not rotate or discard
stable profile identity and credentials.

### Add a separate paused lifecycle status

Rejected because it conflates two independent dimensions: whether intent has
ever been applied and whether it currently participates in live configuration.

### Stop sing-box or patch one inbound directly

Rejected because stopping the whole service affects unrelated profiles, while
partial JSON mutation bypasses complete projection, fingerprint preconditions,
validation, health checks, and rollback.

### Reserve the resumed port during preview

Rejected because a read-only plan cannot hold a host resource until the user
confirms; availability must be rechecked inside the mutation lock.
