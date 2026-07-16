# ADR 0013: Public domain resolution diagnostics

- Status: Accepted
- Date: 2026-07-17

## Context

The manager can persist public server addresses and TLS server names, but an
operator previously learned about misspelling, missing DNS records, or a broken
local resolver only through certificate or client failures. Resolving arbitrary
text directly in the Textual module would couple networking, normalization, and
failure parsing to presentation. Calling the process resolver without a bound
could also leave one diagnostics worker waiting for the operating system's full
resolver retry policy.

Resolution alone cannot prove that an A or AAAA record points at the managed
host. The product therefore needs useful DNS evidence without presenting it as
public-address ownership or connectivity proof.

## Decision

Add one read-only `DomainResolutionInspector` seam. It accepts the complete
`ManagedInstallation` snapshot and returns a `DomainResolutionObservation` with
one typed result per normalized domain plus the count of distinct literal IP
endpoints that do not require DNS.

The production `BoundedSocketDomainResolutionInspector` extracts both public
server addresses and TLS server names. It strips a terminal dot, applies IDNA,
normalizes case, validates DNS label syntax, deduplicates domains and IPs, and
sorts results for stable presentation. Malformed host text becomes per-domain
failure evidence rather than a subprocess argument or an unexpected TUI error.

All valid domains are passed as separate arguments, never shell text, to one
isolated Python standard-library resolver worker. The manager enforces one total
timeout for the batch, validates the worker's JSON response, and maps launch,
timeout, protocol, and process failures to one typed inspection error. The
worker performs no writes and receives no credentials or generated
configuration.

The diagnostics center reports complete success as healthy. Invalid or
unresolved domains and an unavailable resolver are attention findings, because
they affect certificate issuance or client reachability but do not themselves
prove unsafe host mutation. Successful addresses remain visible when other
domains fail. Existing action-required findings retain recommendation priority.

## Consequences

- Draft and applied profiles receive the same early DNS feedback.
- Repeated profiles do not multiply resolver traffic.
- A local resolver stall cannot hold the diagnostics worker indefinitely.
- Literal IP endpoints are distinguished from missing public-address intent.
- The result deliberately does not claim that DNS points to this host; adding
  ownership comparison requires a separately accepted public-address seam.
- The implementation adds no runtime Python dependency and remains testable
  through `localhost`, fake typed observations, and zero-timeout behavior.

## Rejected alternatives

### Call `socket.getaddrinfo` directly in the Textual worker

Rejected because the operating system resolver call has no portable per-call
timeout and could leave a refresh waiting through lengthy retry policy.

### Depend on a platform `getent` command

Rejected because command availability and output differ across supported host
families, while the installed Python runtime is already part of the product.

### Treat unresolved DNS as proof that apply is unsafe

Rejected because DNS propagation and external records are independent of a
transactionally valid local sing-box configuration. The finding remains visible
as attention while higher-priority host failures keep their action.

### Claim that a resolved address belongs to the host

Rejected because resolution provides addresses only. Ownership needs a trusted
public-address observation and comparison policy that this slice does not have.
