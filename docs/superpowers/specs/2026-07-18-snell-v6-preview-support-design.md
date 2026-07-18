# Snell v6 Preview-Core Support Design

**Status:** Approved direction, awaiting written-spec review

**Date:** 2026-07-18

**Scope:** Python TUI profile lifecycle, managed sing-box configuration, and client handoff for Snell v6

## Decision

Add Snell v6 as a first-class protocol in the existing protocol catalog. The
manager supports only protocol version 6, with one generated top-level PSK and
the sing-box `default` mode. It does not expose Snell v5, multi-user `userkey`
authentication, QUIC proxy mode, or unsafe raw mode.

Snell is a core-version-gated capability. A Snell profile may be applied or
resumed only when the active sing-box binary reports a version that includes
Snell support. Switching to a core that lacks the capability is rejected while
an applied Snell profile exists. Stable 1.13.x therefore remains usable for all
existing protocols but cannot activate Snell; the current Preview 1.14 line can
activate it once the observed version satisfies the capability threshold.

Snell has no official interoperable share-URI scheme. Instead of inventing
`snell://`, the manager returns a typed connection payload and renders Snell as
an official Surge policy line. Existing protocols continue to return URI
payloads with unchanged content.

## Problem

The manager currently treats every catalogued protocol as compatible with every
supported sing-box core. That assumption no longer holds: Stable is currently
on 1.13.x, while Snell first appears in the 1.14 prerelease line. Merely adding a
serializer would allow users to produce a desired state that the active core
cannot parse, and relying on a late `sing-box check` failure would provide poor
guidance and leave core downgrade behavior undefined.

The existing connection handoff is also named `share_uri`. Snell's documented
client representation is a Surge policy entry, not a URI. Putting a policy line
into a field and UI labelled as a URI would weaken the protocol catalog's
abstraction and encourage consumers to make false assumptions.

## Goals

- Support only Snell protocol version 6 through the normal profile lifecycle.
- Generate and persist one strong PSK per profile without exposing server
  secrets in logs or non-reveal UI.
- Emit the exact minimal sing-box inbound accepted by a Snell-capable core.
- Fail before host mutation when the active or target core lacks Snell support.
- Keep Stable 1.13.x behavior unchanged for every existing protocol.
- Prevent a downgrade or channel switch from stranding an applied Snell config
  behind an incompatible core.
- Provide an official, copyable Surge policy line without inventing a URI.
- Preserve the protocol catalog as the deep module that owns protocol-specific
  generation, validation, serialization, and client handoff.
- Cover deterministic unit, application, persistence, privileged-policy, TUI,
  and opt-in real-core acceptance behavior.

## Non-goals

- Snell v5.
- Multi-user Snell v6 configuration through `users` and `userkey`.
- User-selectable Snell modes, including `unshaped` or `unsafe-raw`.
- QUIC proxy mode.
- A custom `snell://` URI or compatibility with undocumented URI schemes.
- Automatically downloading or switching to Preview when Snell is selected.
- Automatically deleting, pausing, or rewriting Snell profiles during a core
  change.
- General feature negotiation for arbitrary third-party sing-box forks.

## Alternatives Considered

### 1. Catalog slice plus typed core capability and client payload (selected)

Add Snell through the same vertical slice as existing protocols, introduce one
central compatibility policy derived from observed core versions, and deepen
connection handoff from a URI-only field to a typed payload. This costs more
than a serializer-only patch, but it gives early errors, safe downgrade
behavior, truthful UI labels, and one reusable seam for future version-gated
features.

### 2. Serializer-only protocol handler

Add `ProtocolKind.SNELL_V6`, generate an inbound, and let `sing-box check` reject
Stable. This is smaller but fails late, cannot explain the Preview requirement
before planning, and does not protect core switching. It also forces a Surge
policy line into a URI-shaped interface. Rejected because it makes an invalid
host plan representable.

### 3. Separate Preview-only Snell workflow

Build a dedicated Snell screen that checks Preview before creating a profile.
This makes the dependency visible, but duplicates the profile lifecycle and
still leaves edits, resume, desired-state rebuilds, and core switching to solve
elsewhere. Rejected because protocol compatibility belongs in application
policy, not one UI entry point.

## Domain Model and Interfaces

### Protocol identity and material

Add `ProtocolKind.SNELL_V6` and a tagged material value:

```python
@dataclass(frozen=True)
class SnellV6Material:
    psk: str
```

The PSK source is a small secure-generation seam with a production adapter
backed by the operating system CSPRNG. Production generates 32 random bytes and
encodes them as unpadded URL-safe Base64, yielding a 43-character ASCII value.
This is comfortably inside sing-box's 12-to-255-byte Snell v6 PSK constraint
and contains no commas or whitespace that would make a Surge policy ambiguous.

Material generation is idempotent: planning a new draft may create the PSK;
materializing a persisted profile reuses it. Persistence adds one new tagged
material variant and rejects malformed, missing, or mismatched Snell material.
Existing serialized profiles require no migration.

### Core capability policy

Introduce one pure, typed policy instead of scattering version comparisons:

```python
@dataclass(frozen=True)
class CoreProtocolCapabilities:
    version: CoreVersion
    supported_protocols: frozenset[ProtocolKind]


class ProtocolCompatibilityPolicy(Protocol):
    def require_supported(
        self,
        protocol: ProtocolKind,
        core_version: CoreVersion,
    ) -> None: ...
```

The official capability threshold is `1.14.0-alpha.38`, the release where
sing-box added Snell. SemVer ordering therefore accepts alpha.38 and later
alphas, betas, release candidates, 1.14.0 final, and later releases. It rejects
1.14.0 prereleases older than alpha.38 even though their minor version is 1.14.
An absent, unparseable, or failed core observation does not prove support and
fails closed for Snell.

All existing protocols retain their current compatibility behavior. The policy
does not infer Snell support from the selected channel name: the active or
planned exact binary version is authoritative.

### Typed client payload

Replace the protocol-neutral `share_uri` assumption with:

```python
class ConnectionPayloadKind(str, Enum):
    URI = "uri"
    SURGE_POLICY = "surge-policy"


@dataclass(frozen=True)
class ConnectionPayload:
    kind: ConnectionPayloadKind
    content: str


@dataclass(frozen=True)
class ProfileConnectionInfo:
    server_address: str
    server_port: int
    payload: ConnectionPayload
```

Existing handlers return `URI` and preserve their exact current string. Snell
returns `SURGE_POLICY` with this shape:

```text
Snell-<stable-id> = snell, <server-address>, <port>, psk=<psk>, version=6
```

`stable-id` is the first 12 lowercase hexadecimal characters of a SHA-256 over
the manager-owned profile identifier. It is deterministic, collision-resistant
for this local naming purpose, and cannot inject Surge delimiters even when the
operator's display name contains punctuation. The generated PSK alphabet also
prevents delimiter injection. The payload is revealed only through the existing
explicit reveal control; its UI label and copy explain that it is a Surge policy
entry rather than a generic URI. The operator may rename the policy after
copying it into Surge.

## Protocol Catalog Behavior

The Snell handler owns four invariants behind
`ProtocolCatalog.materialize(profile, listen_port)`:

1. The profile kind is exactly `SNELL_V6`.
2. Material is either absent and securely generated, or present as valid
   `SnellV6Material`.
3. The inbound and client payload use the same port and PSK.
4. The handler always emits protocol version 6 and mode `default`.

The minimal managed inbound is:

```json
{
  "type": "snell",
  "tag": "<managed-tag>",
  "listen": "::",
  "listen_port": 443,
  "version": 6,
  "psk": "<generated-psk>",
  "mode": "default"
}
```

The manager does not emit `users`, `userkey`, TLS, transport, multiplex, or
unknown protocol fields. Snell is modelled as a TCP listener in port-conflict
and host-diagnostic policy.

## Compatibility Enforcement and Data Flow

Compatibility is enforced at application mutation boundaries, not only in the
TUI:

```text
inspect active exact core version
  -> derive typed protocol capabilities
  -> select and preview Snell v6
  -> reject unsupported/unknown core before draft materialization or mutation
  -> generate or reuse PSK
  -> persist the draft
  -> confirmation rechecks desired-state revision and active core capability
  -> materialize the inbound
  -> privileged config validation
  -> sing-box check, atomic apply, and service reconciliation
  -> reveal typed Surge policy only after successful apply
```

The profile creation UI always lists `Snell v6` and marks it as requiring
Preview/core 1.14 support. Selecting it on an unsupported or unknown active core
keeps the workflow read-only and explains that the operator must install and
activate a compatible Preview core, then plan again. The manager never switches
channels implicitly.

Existing persisted Snell profiles remain visible when the active core is
incompatible. Read-only details, copy that does not reveal secrets, pause, and
removal remain available. Apply and resume are rejected before configuration
or service mutation. No profile is silently deleted or rewritten.

Core activation planning evaluates all profiles that will be present in the
projected active configuration. A target Stable or older exact version is
rejected when any applied Snell profile exists, with guidance to pause or remove
those profiles first. Draft and paused Snell profiles do not block a downgrade
because they are not projected into the active sing-box configuration.

Every confirmed profile operation re-observes the active binary rather than
trusting a version captured when a screen opened. Every confirmed core switch
rechecks the desired-state revision. A version or state race therefore cancels
the stale plan instead of applying against different capabilities.

## Error Model and Recovery

Add stable typed errors rather than matching exception text:

- `ProtocolUnsupportedByCore`: exact protocol, observed version when available,
  minimum supported version, and recovery action;
- `CoreVersionUnknown`: Snell capability cannot be proven;
- `CoreTargetIncompatibleWithDesiredState`: target version and blocking profile
  identities;
- existing material-validation errors extended with the Snell material tag.

Compatibility failures occur before host mutation and are safe to resolve by
activating Preview or pausing/removing blocking Snell profiles, then creating a
new plan. A later `sing-box check` failure remains authoritative defense in
depth and must not be described as a compatibility success.

Logs may contain protocol identity, profile identifier, core version, and
capability threshold. They must not contain the PSK or complete Surge policy.
User-visible error copy must not echo the PSK.

## Privileged Boundary

The privileged helper accepts a Snell inbound only when all of these are true:

- `type` is exactly `snell`;
- `version` is the integer `6`;
- `mode` is exactly `default`;
- `psk` is an ASCII string whose encoded length is 12 through 255 bytes;
- `tag`, `listen`, and `listen_port` satisfy existing managed-inbound policy;
- no `users`, `userkey`, unknown, TLS, or transport fields are present.

The helper does not inspect release channels or fetch core metadata. The
unprivileged application owns version compatibility; the helper owns the shape
of the privileged config it is asked to install. The configured binary's
existing pre-activation `sing-box check` remains the final schema authority.

## TUI Behavior

- Protocol recommendations and the full protocol picker include `Snell v6` with
  a concise `Preview / sing-box 1.14+` requirement.
- Stable, unsupported prerelease, missing binary, and unreadable version states
  show an actionable incompatibility message before any generated-value review.
- The review identifies `Snell v6`, TCP, the chosen port, and generated PSK as a
  secret without displaying its value.
- A successful apply uses the shared reveal-once panel. For Snell, the panel
  says `Surge policy` and copies the official policy line; other protocols keep
  the existing URI wording and content.
- Profile details render the same payload kind consistently after restart.
- Core-channel review rejects an incompatible target and lists blocking applied
  Snell profiles without revealing credentials.

No separate Snell wizard is introduced.

## TDD Strategy

Tests are written before each implementation slice and assert public behavior.

### Domain and protocol tests

- `SNELL_V6` round-trips through desired-state JSON.
- Secure material generation produces valid, independent 43-character PSKs and
  reuses persisted material.
- Invalid length, alphabet, missing material, and cross-protocol material fail.
- Exact inbound serialization contains only the approved fields, version 6, and
  mode `default`.
- The Surge policy contains the same host, port, and PSK as the inbound.
- The Surge policy name is stable for a profile and cannot contain operator
  input or policy delimiters.
- Existing protocols keep byte-for-byte equivalent URI payloads.

### Capability and application tests

- Stable 1.13.x, 1.14.0-alpha.37, missing versions, and malformed versions
  reject Snell before mutation.
- 1.14.0-alpha.38, the current Preview, 1.14.0 final, and later releases accept
  Snell.
- A stale profile plan is rejected if the active core changes before confirm.
- Apply and resume reject an incompatible active core; read-only inspection,
  pause, and removal remain available.
- Core switching rejects an incompatible target only for applied Snell
  profiles; draft and paused Snell profiles do not block it.
- Existing protocols remain unaffected on Stable.

### Privileged-policy tests

- The exact managed Snell v6 inbound is accepted.
- v5, missing/wrong version, non-default modes, invalid PSKs, `users`, `userkey`,
  and every unknown field are rejected.
- Rejection occurs before config replacement or service action.

### TUI Pilot tests

- Snell is visible with the Preview requirement.
- Stable and unknown-core planning show recovery guidance and do not create a
  draft or reveal a secret.
- Compatible Preview planning, confirmation, and apply follow the existing
  profile workflow.
- Successful Snell apply and persisted profile details label and reveal a Surge
  policy; existing protocols still label and reveal a URI.
- Incompatible core-switch review lists blockers and performs no activation.

### Real-core acceptance

An opt-in test uses the repository's existing `SB_MANAGER_REAL_SING_BOX` seam.
With an official compatible Preview binary, it materializes Snell v6 and proves
that `sing-box check` accepts the generated managed config. A Stable 1.13 binary
proves the application capability policy rejects the plan before invoking host
mutation. External binary acquisition remains outside the deterministic suite.

## Documentation and Architecture Records

The implementation updates:

- a new ADR for exact-core protocol capability gating and safe downgrade;
- ADR-0002 for typed connection payloads and the Snell catalog slice;
- `docs/SDD.md` for material, capability, error, and privileged boundaries;
- `docs/MANUAL.md` for Preview activation, Snell creation, Surge handoff, and
  downgrade recovery;
- `docs/SUPPORT.md` for Snell v6's exact core requirement and exclusions;
- protocol lists and acceptance evidence wherever they are user-visible.

The version threshold and official client shape are linked to primary sources
so future maintainers can revalidate them:

- sing-box Snell inbound: <https://sing-box.sagernet.org/configuration/inbound/snell/>
- sing-box Snell outbound: <https://sing-box.sagernet.org/configuration/outbound/snell/>
- sing-box changelog: <https://sing-box.sagernet.org/changelog/>
- Surge proxy policy reference: <https://manual.nssurge.com/policy/proxy.html>

## Implementation Slices

1. Add failing domain, persistence, and Snell protocol tests; implement Snell v6
   material and pure serialization.
2. Add failing typed-payload compatibility tests; deepen connection handoff and
   preserve all existing URI outputs.
3. Add failing version-capability and profile-lifecycle tests; implement the
   centralized policy and active-core rechecks.
4. Add failing core-switch compatibility tests; reject incompatible targets
   against projected applied profiles.
5. Add failing privileged-policy tests; allow only the exact Snell v6 schema.
6. Add failing TUI Pilot tests; integrate selection, guidance, review, apply,
   details, and typed payload reveal.
7. Run opt-in official Preview/Stable core acceptance and capture evidence.
8. Update ADRs, SDD, manual, support matrix, and acceptance documentation.
9. Run formatting, lint, type checking, deterministic tests, real-core checks,
   and package build before final implementation review.

Each coherent slice receives a focused conventional commit after its focused
tests pass. The implementation follows the previously approved subagent-driven
development policy: narrowly scoped mechanical work may use medium or lower
capacity, while capability architecture, privileged validation, and final
cross-slice review use the highest appropriate reasoning tier. Shared-worktree
production edits remain serial; independent read-only reviews may run in
parallel.

## Acceptance Criteria

- The protocol picker exposes Snell v6 and no Snell v5 option.
- A Snell profile always persists one valid generated PSK and reuses it.
- Generated inbound configuration is exactly Snell version 6 with mode
  `default` and contains no multi-user or unsafe fields.
- Stable 1.13.x and prereleases before 1.14.0-alpha.38 cannot plan, apply, or
  resume Snell, and no host mutation occurs.
- 1.14.0-alpha.38 and newer official versions can plan and apply Snell.
- A target core lacking Snell cannot be activated while an applied Snell profile
  exists; pausing or removing the blockers makes the switch possible.
- Unknown or changed core versions fail closed at confirmation.
- Existing protocols continue to work on Stable and retain their exact URI
  payload content.
- Snell reveals a correctly labelled official Surge policy line, never a
  fabricated `snell://` URI.
- The privileged helper accepts only the bounded Snell v6 schema and rejects v5,
  multi-user, unsafe, and unknown fields before mutation.
- Deterministic domain, persistence, application, privileged-policy, and TUI
  suites pass.
- The opt-in official Preview binary accepts the generated config through
  `sing-box check`; Stable rejection is verified at the application boundary.
- User and developer documentation describe the same compatibility and recovery
  behavior as production code.

## Security and Maintenance Rationale

The PSK is generated from operating-system entropy, stored only in the existing
secret-bearing desired state, redacted from logs, and revealed through the same
explicit user action as other protocol credentials. Restricting the privileged
schema to one version and one safe mode keeps the new attack surface bounded.

The exact active binary, rather than a mutable channel label, is the source of
capability truth. Applying the same pure policy to profile mutations and core
switches prevents both forward incompatibility and unsafe downgrade. The typed
connection payload removes an incidental URI assumption from the protocol
catalog, allowing future non-URI client artifacts without branching in
application services or lying in the UI.
