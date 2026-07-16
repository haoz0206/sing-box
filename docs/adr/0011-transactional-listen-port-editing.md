# ADR 0011: Transactional listen-port editing

- Status: Accepted
- Date: 2026-07-17

## Context

Profile editing initially covered only display name and public server address.
Changing a listen port still required removing and recreating a profile, even
though the existing configuration transaction already provided validation,
fingerprint preconditions, runtime health checks, and rollback.

A listen port is not ordinary metadata. It changes generated server
configuration and client connection information, may conflict with another
profile or process, and can become unavailable between preview and
confirmation. Automatic selection also cannot choose a durable value during a
read-only preview.

## Decision

Extend the existing deep `ProfileEditor` interface instead of creating a
parallel port-edit module.

`PlanProfileEditRequest` carries either a fixed integer or `None` for automatic
selection. `ProfileEditPlan` records the previous and requested actual port,
the previous and requested selection policy, changed fields, revision, and
desired/live scope.

Planning remains non-mutating and:

- rejects fixed ports outside 1–65535;
- rejects a port already declared by another profile;
- probes a newly selected fixed port through `PortSource`;
- does not probe an unchanged active port;
- does not choose an automatic port.

Confirmation acquires the shared mutation lock, rechecks revision and reviewed
content, and repeats fixed-port availability validation. If the port became
unavailable, a typed error is returned before the configuration applier runs.
For an automatic applied edit, the actual port is chosen inside the lock.
`PortSource` receives every port declared by another profile as an exclusion,
so an inactive draft cannot be assigned the same port accidentally.

Draft port changes update desired state only. Changing only automatic/fixed
policy while retaining the same actual applied port also updates desired state
only. Changing the actual port of an applied profile reprojects the complete
managed configuration and reuses fingerprint preconditions, external
validation, atomic commit, runtime refresh, health checks, and rollback. Desired
state records the actual selected port only after host success.
The typed result returns that actual port so the TUI can present it immediately.

Firewall mutation is explicitly not part of the port-edit transaction.

## Consequences

- Operators can correct or automatically reselect a port without rotating
  credentials or recreating a profile.
- The preview distinguishes policy changes from service-impacting port changes.
- Port availability is advisory at preview and authoritative when repeated
  under the mutation lock.
- A confirmation-time conflict has a precise TUI result and never claims an
  unknown host outcome.
- `SocketPortSource` is shared by first apply and profile editing in production.

## Rejected alternatives

### Recreate the profile

Rejected because it rotates unrelated identity/material and obscures the actual
port-only intent.

### Choose an automatic port during preview

Rejected because a read-only plan could not reserve that port until
confirmation and would present a misleading exact effect.

### Patch only one generated inbound

Rejected because generated JSON is not authoritative and partial writes bypass
global validation, fingerprint preconditions, and rollback.

### Open the firewall automatically

Rejected because firewall ownership and recovery require a separate accepted
adapter and transaction design.
