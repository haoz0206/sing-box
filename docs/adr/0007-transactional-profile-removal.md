# ADR-0007: Remove profiles through desired-state planning and full projection

Status: Accepted  
Date: 2026-07-16

## Context

The Python manager could create, persist, reopen, and apply profiles, but an
operator could not retire one without editing desired state or generated JSON.
Deleting an applied profile from desired state before updating the host would
make the manager claim a state that was not live. Treating every removal as a
host change would make discarding an unapplied draft unnecessarily privileged.

Applying and removing profiles also both need to assemble the complete sing-box
document. Duplicating inbound and certificate-provider aggregation would allow
the two lifecycle paths to diverge as protocols are added.

## Decision

Profile removal is a planned, revision-bound application operation:

1. `plan_removal(profile_id)` reads one exact desired-state revision and reports
   profile identity, draft/applied scope, and remaining profile counts without
   acquiring the mutation lock or changing the host.
2. Every removal requires a second explicit confirmation.
3. Confirmed execution acquires the same manager mutation lock as draft save and
   profile apply, recomputes the plan, and rejects a stale revision.
4. Draft removal writes only the next desired-state revision and preserves the
   recorded live-configuration fingerprint.
5. Applied removal projects every remaining applied profile through one
   `ManagedConfigurationProjector`, preserving ProtocolCatalog's idempotent
   material and TLS behavior.
6. The projected document is applied with the recorded live-configuration
   fingerprint precondition through the existing validation, atomic commit,
   runtime health, and rollback transaction.
7. Desired state removes the applied profile and records the successor
   configuration fingerprint only when the transaction outcome is `APPLIED`.
8. Removing the final applied profile projects an empty inbound list with only
   the fixed direct outbound. sing-box 1.14 accepts this quiescent
   configuration, and the privileged allowlist permits zero through 128
   manager-generated inbounds while retaining every other schema restriction.
9. The Textual workflow begins in profile details, uses distinct draft and live
   impact language, runs confirmed work off the UI thread, presents typed
   terminal states, and returns successful operations to a recomposed dashboard.

## Consequences

- Operators no longer edit manager state or sing-box JSON to retire a profile.
- A failed applied removal leaves desired state aligned with the restored or
  unchanged live configuration.
- Draft removal remains rootless and does not refresh the service.
- Apply, removal, and future enable/disable workflows share one complete
  configuration projection rule.
- Profile editing remains a separate lifecycle decision rather than an implicit
  delete-and-recreate shortcut.

## Rejected alternatives

### Delete desired state before applying the remaining configuration

Rejected because validation or runtime failure would leave desired and live
state describing different profile sets.

### Remove an inbound directly from generated JSON

Rejected because generated configuration is an artifact, not authoritative
state, and protocol-level edits would bypass the catalog and transaction.

### Always invoke the privileged transaction

Rejected because an unapplied draft has no live artifact to remove and should
remain a local desired-state operation.
