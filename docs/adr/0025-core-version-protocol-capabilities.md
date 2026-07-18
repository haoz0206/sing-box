# ADR-0025: Bind protocol capabilities to exact core versions

Status: Accepted
Date: 2026-07-18

Core release channels are discovery intent, not compatibility evidence. The
manager therefore uses the exact active version observed during planning, and
the exact target version frozen in a core plan, as protocol-capability truth.
Every projected mutation rechecks the observed version and desired-state
revision before changing desired state, generated configuration, runtime, or
the active core. Unknown core evidence fails closed only for protocols with an
explicit version gate; ungated protocols retain their existing behavior.

Snell is the first gated protocol. The manager supports only Snell v6 on
sing-box `1.14.0-alpha.38` or newer, with fixed default mode and one generated
top-level PSK. It deliberately excludes Snell v5, multi-user `users` or
`userkey` shapes, unsafe modes, TLS, transport, multiplex, QUIC proxy, and a
custom `snell://` format. Its typed client artifact is the official Surge
policy shape `Name = snell, host, port, psk=..., version=6`; the operator may
rename `Name` in Surge. The credential-bearing payload stays hidden until an
explicit reveal.

Stable sing-box 1.13.x cannot plan, apply, or resume a Snell profile. An
unknown active core also cannot plan Snell; the recovery is to install and
activate a capable Preview release and plan again. A compatible Preview label
alone is insufficient: the binary must report an exact version at or above the
minimum. Planning and confirmation bind that observation so even a change
between two compatible Preview versions requires replanning.

Applied and enabled Snell profiles block a core target that cannot represent
them. Draft and paused Snell profiles do not block core activation because they
project no live inbound. Pausing an applied Snell profile, or removing the last
active Snell profile, remains the recovery path to Stable. Core update and
channel plans bind the desired-state revision so a profile-state change after
review invalidates the plan before acquisition or switching.

The privileged configuration policy independently validates the exact
allowlisted Snell v6/default/single-PSK shape. It never discovers or infers a
core version; capability selection remains an unprivileged application concern
that is rechecked at every projection boundary.

## Consequences

- Protocol compatibility is a typed, fail-closed planning precondition rather
  than a channel-name convention.
- A core plan reports blocking profile display names without exposing profile
  IDs, credentials, or generated inbound material.
- Deterministic contract, behavior, acceptance, and privileged-policy tests
  cover the compatibility and no-mutation rules. Real official-core checks are
  separate, explicit opt-in integration evidence because they depend on
  external artifacts.
- The protocol boundaries follow the official [sing-box Snell inbound](https://sing-box.sagernet.org/configuration/inbound/snell/),
  [sing-box Snell outbound](https://sing-box.sagernet.org/configuration/outbound/snell/),
  [sing-box changelog](https://sing-box.sagernet.org/changelog/), and
  [Surge proxy-policy](https://manual.nssurge.com/policy/proxy.html)
  documentation.
