# ADR 0017: Secret-free profile template cloning

- Status: Accepted
- Date: 2026-07-17

## Context

An operator adding a second device or a similar listener previously had to
repeat the complete protocol form. Repeating public address, TLS strategy, and
transport settings is tedious and error-prone, but copying an applied
`ManagedProfile` wholesale would duplicate authentication material, listening
ports, and runtime state. That would create shared credentials and port
conflicts while making two profiles appear independently manageable.

The product needs a purpose-oriented “use this as a template” journey rather
than a low-level JSON copy command. It must make the copied and reset fields
visible before desired state changes.

## Decision

Add `ProfileCloner` as a small application interface with a read-only `plan`
operation and an explicitly confirmed `clone` operation. The plan is bound to
the source profile ID and desired-state revision. It exposes typed copied and
reset facets so Textual renders policy rather than inventing it.

Planning suggests a unique display name based on `<source> 副本`, adding a
numeric suffix when needed. Operators may edit the name before review. Explicit
names are trimmed, must not be blank, and must not duplicate an existing
profile name.

The new draft copies only reusable intent:

- protocol kind;
- public server address when present;
- TLS strategy and its non-secret configuration;
- transport strategy and its path, host, or service name.

The new draft always resets:

- `protocol_material` to `None`, causing the existing protocol catalog to
  generate independent UUIDs, passwords, keys, and short IDs at apply time;
- `listen_port` to `None` and `port_selection` to `AUTOMATIC`, avoiding a
  conflict with the source listener;
- status to `DRAFT` and availability to enabled, without changing the live
  configuration or service.

Confirmation acquires the shared manager mutation lock, rechecks the exact
desired-state revision, compares the reviewed non-secret source intent even if
an external edit incorrectly retained that revision, verifies that the source
and name are still valid, and appends one new stable profile ID. It preserves
the current live-configuration SHA-256 precondition because cloning does not
touch the host.

The Textual journey lives behind `ProfileCloneScreen`. Profile details expose
one “以此配置为模板” action. The screen provides an editable suggested name,
an explicit copied/reset summary, a second confirmation step, typed stale-state
guidance, and a success state. Returning from success dismisses stale details
and recomposes the dashboard so the new draft is immediately visible.

## Consequences

- Similar device profiles can be created without re-entering non-secret
  protocol configuration.
- Each applied clone receives independent authentication material and a newly
  selected port through the existing apply workflow.
- Cloning is desired-state-only; it never invokes a configuration applier,
  runtime, privileged helper, or material source.
- Name policy and copy/reset semantics are testable without Textual.
- Changes to clone policy require updating the facet report and corresponding
  operator wording.
- The slice does not bulk-create profiles or automatically apply the new draft.

## Rejected alternatives

### Copy the entire `ManagedProfile`

Rejected because it would reuse credentials, private keys, listen ports, and
applied/paused state.

### Reopen the generic protocol form with prefilled fields

Rejected because the current form request types do not represent persisted
material safely, and the operator would still have to understand which values
must change. A dedicated template plan makes reset policy explicit.

### Clone and immediately apply

Rejected because it would combine a desired-state convenience action with host
mutation, port allocation, credential generation, validation, service refresh,
and rollback. The existing draft apply journey already owns those effects.

### Preserve a fixed source port

Rejected because the source may still be listening on it. Automatic selection
at apply time provides the established confirmation-time availability check.

### Reuse authentication material for the same operator

Rejected because profile lifecycle operations are independent. Shared secrets
would make revocation and device-specific removal unsafe and surprising.
