# ADR 0008: Revision-bound profile metadata editing

- Status: Accepted
- Date: 2026-07-16
- Extended by: ADR 0011 for transactional listen-port editing

## Context

Operators could create, reopen, apply, and remove profiles, but correcting a
display name or public server address required removing and recreating the
profile. Editing generated JSON or the desired-state file directly would bypass
validation, stable identity, revision protection, configuration fingerprints,
and rollback.

The two initial editable fields have different host impact. A public server
address is client-facing metadata and is not emitted into sing-box server
configuration. A profile name is emitted into generated inbound user records,
so renaming an applied profile changes the live configuration.

## Decision

Introduce one deep `ProfileEditor` application interface with two operations:

1. `plan_edit(request)` normalizes input, validates the name, rejects a no-op,
   identifies exact changed fields, binds the plan to the current desired-state
   revision, and classifies its scope without locking or mutating anything.
2. `apply_edit(plan, confirmed=True)` acquires the shared mutation lock, checks
   the revision and reviewed content again, then commits either desired state or
   one complete transactional live-configuration projection.

The initial interface edits only display name and public server address. Stable
profile ID, protocol, port, credentials, TLS, and transport are preserved.

- Draft edits are desired-state-only.
- Public-address-only edits are desired-state-only, including for applied
  profiles.
- Renaming an applied profile uses the shared configuration projector,
  fingerprint precondition, validation, atomic commit, runtime refresh, health
  check, and rollback transaction.
- Desired state advances only for a desired-state-only edit or an `APPLIED`
  host transaction.
- The TUI opens a prefilled form without planning, presents normalized changes
  and host impact, requires explicit confirmation, executes in a worker, and
  preserves every typed transaction result and recovery instruction.

## Consequences

- Operators can correct common metadata without credential rotation or profile
  recreation.
- The plan truthfully distinguishes a client-only address change from a server
  configuration change.
- Concurrent or tampered desired state cannot silently consume a stale plan.
- Protocol, port, TLS, transport, and credential editing remain separate future
  decisions because each has different validation, regeneration, and rollback
  semantics.

## Rejected alternatives

### Treat every applied edit as a host mutation

Rejected because changing only the public address does not alter server
configuration. Refreshing sing-box would add risk without changing the host.

### Commit desired state before applying a renamed profile

Rejected because a failed validation or runtime refresh would make desired
state claim a name the running configuration does not use.

### General-purpose patch dictionaries

Rejected because callers would need to understand field mutability and host
impact, creating a shallow interface and making unsafe fields easy to expose.
