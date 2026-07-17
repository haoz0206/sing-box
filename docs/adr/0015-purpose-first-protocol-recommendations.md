# ADR 0015: Purpose-first protocol recommendations

- Status: Accepted
- Date: 2026-07-17

## Context

The guided profile journey originally opened with ten protocol and transport
names. That required a new operator to understand the implementation choice
before stating the outcome they cared about. It contradicted the product goal
of guided operation and the SDD's purpose-first wizard.

Protocol recommendations are also safety-sensitive product policy. The UI must
not hide requirements such as UDP availability, TLS certificates, or client
support, and it must not imply that one protocol guarantees connectivity in a
restricted network.

The persisted `ProtocolKind` is intentionally coarser than a selectable form:
VLESS TLS and VMess TLS each support both WebSocket and gRPC. Returning only a
`ProtocolKind` would force the UI to guess the transport after recommendation.

## Decision

Start every add-profile journey by asking for one `ProfilePurpose`:

- general setup;
- mobile network and low latency;
- connection choices for a restricted network;
- compatibility with an existing client.

`ProfileRecommendationAdvisor.recommend(purpose)` is the small application
interface. It returns exactly three ordered `ProtocolRecommendation` values.
Every choice includes an exact `ProtocolVariant` and a stable
`RecommendationRationale`. Recommendation policy stays in the application
module; the Textual presentation adapter resolves purpose, ranking, rationale,
tradeoff, error, and advanced-choice copy through the validated interface copy
catalog and returns the selected variant.

Introduce `ProtocolVariant` as the identity of one exact guided form, including
WebSocket or gRPC when needed. It is navigation state, not persisted desired
state. Once the existing form produces a plan, the established `ProtocolKind`,
TLS intent, and transport intent remain authoritative.

The first recommendation is visually marked as the starting point, not an
automatic choice. Selecting it only opens the existing profile form. The form
still requires operator input, plan review, draft persistence, and explicit
apply confirmation. Advanced operators retain a direct list of every supported
variant without a recommendation rank.

Recommendations are static, reviewable product policy. They do not probe the
network, infer censorship conditions, inspect clients, or mutate the host. The
screen explicitly says that ranking does not guarantee connectivity or fitness
for every network.

The initial wording is grounded in the upstream sing-box documentation:

- the [Hysteria2 manual](https://sing-box.sagernet.org/manual/proxy-protocol/hysteria2/)
  describes QUIC/Brutal behavior under packet loss and warns that UDP proxy
  traffic has more obvious characteristics;
- the [Shadowsocks manual](https://sing-box.sagernet.org/manual/proxy-protocol/shadowsocks/)
  recommends AEAD 2022 over TCP with multiplexing;
- the [TUIC inbound reference](https://sing-box.sagernet.org/configuration/inbound/tuic/)
  requires TLS and exposes QUIC congestion control;
- the [AnyTLS inbound reference](https://sing-box.sagernet.org/configuration/inbound/anytls/)
  records its version floor, TLS requirement, and padding behavior;
- the [shared TLS reference](https://sing-box.sagernet.org/configuration/shared/tls/)
  defines Reality key material and certificate requirements.

## Consequences

- New operators start from intent and see costs before protocol vocabulary.
- Recommendation policy is testable without Textual and changes in one module.
- The UI receives exact form and rationale identities, contains no ranking
  rules, and owns no locale-authored recommendation copy.
- An unexpected advisor failure remains non-disclosing and exposes direct
  protocol selection without requiring the operator to navigate backward.
- Existing protocol planning, persistence, generation, and apply modules remain
  unchanged.
- Purpose is deliberately ephemeral; choosing a different purpose never changes
  desired state.
- Recommendation copy must be reviewed when supported variants or upstream
  protocol guidance changes.

## Rejected alternatives

### Keep a flat protocol list as the primary journey

Rejected because it makes protocol knowledge a prerequisite for a guided
product. The flat list remains available only as an explicit advanced route.

### Automatically select and apply the top recommendation

Rejected because a recommendation cannot know client support or current network
conditions and must not bypass the existing form, plan, and confirmation.

### Return only `ProtocolKind`

Rejected because it loses the WebSocket/gRPC distinction and pushes transport
guessing back into Textual.

### Persist the selected purpose

Rejected for this slice because purpose affects only navigation and ranking; it
does not yet change generated configuration or ongoing lifecycle behavior.

### Probe the network to claim the best protocol

Rejected because a bounded local probe cannot prove future reachability or
censorship resistance and would turn a pure pre-plan interaction into an
external-effect workflow.
