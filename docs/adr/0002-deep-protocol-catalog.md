# ADR 0002: Deep protocol catalog

- Status: Accepted
- Date: 2026-07-16

## Context

`ProfileApplyService` currently knows how Reality credentials are generated,
how a Reality inbound is assembled, and how its typed client artifact is
constructed. Adding a second protocol by extending those conditionals would
spread protocol knowledge across application, persistence, and UI modules.

The desired-state model also has a protocol-specific `reality_material` field.
Repeating that shape for every protocol would make schema evolution and every
caller depend on the complete protocol matrix.

## Decision

Introduce one deep protocol module with this external interface:

```python
ProtocolCatalog.materialize(profile, listen_port) -> MaterializedProfile
```

`MaterializedProfile` contains:

- the profile with generated protocol material attached;
- the complete sing-box inbound;
- an optional typed client artifact, such as a share URI or Surge policy.

The catalog selects an internal handler by `ProtocolKind`. Each handler owns
protocol validation, idempotent material generation, inbound construction, and
typed client-artifact generation. Application orchestration does not branch on
protocol kind or assume that every client payload is a URI.

`ManagedProfile` stores one `ProtocolMaterial` tagged union rather than one
field per protocol. JSON persistence owns the tagged representation and reads
the previous Reality-only representation as a compatibility migration.

## Interface invariants

- Materialization is idempotent for an already materialized profile.
- A draft may generate secrets; rebuilding an applied profile reuses persisted
  secrets.
- The returned profile and inbound describe the same port and credentials.
- Private server-only material never appears in a client artifact. Credential-
  bearing client artifacts remain hidden until an explicit one-page reveal.
- Unsupported kinds and mismatched material fail before configuration apply.
- Adding a protocol requires a handler and its serializer branch, not edits to
  application orchestration.

## Rejected alternatives

### Protocol conditionals in `ProfileApplyService`

Rejected because deleting the protocol module would not remove complexity; it
would reappear in application callers and tests.

### One optional material field per protocol

Rejected because every protocol addition would widen the shared profile
interface and persistence schema.

### Exposing separate generate/build/share methods

Rejected as a shallow interface. Callers would need to understand ordering and
keep three outputs consistent. `materialize` hides those invariants behind one
operation.

## Consequences

- Reality, Shadowsocks, and Snell are independent handlers, making the seam
  real. Snell returns a typed Surge-policy artifact rather than inventing a
  custom URI.
- Protocol-specific pure behavior tests remain useful schema fixtures.
- Application behavior tests move to the catalog interface and stop asserting
  protocol implementation steps.
- TLS-dependent protocols can be added after the TLS seam is available without
  widening `ProfileApplyService`.
