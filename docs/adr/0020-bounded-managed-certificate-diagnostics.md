# ADR 0020: Bounded managed certificate diagnostics with minimum disclosure

- Status: Accepted
- Date: 2026-07-17

## Context

The manager can generate TLS configuration from an operator certificate pair or
sing-box's shared ACME certificate provider, but a valid desired state does not
prove that the public leaf is present, covers the declared server name, is
currently valid, or has enough time remaining for safe operator action.
Runtime health and DNS resolution answer different questions. Waiting for a TLS
failure would make renewal risk visible too late.

Certificate files and CertMagic storage may be root-readable on a production
host. Broadening Textual's privileges or returning PEM through the existing
helper would create an unnecessary disclosure boundary, especially because the
diagnostic needs no private-key material.

sing-box 1.14 delegates ACME certificate storage to CertMagic and exposes a
fixed `data_directory`. CertMagic's filesystem storage places public
certificates below a `certificates` tree. The Python `cryptography` X.509 API
provides timezone-aware validity timestamps and typed SAN access without an
OpenSSL subprocess.

## Decision

Add a small `CertificateDiagnostics.inspect(installation)` application
interface and a separate `CertificateSource` system seam. The application
derives targets only from enabled profiles in `APPLIED` state and deduplicates
profiles that share the same certificate intent.

The filesystem adapter accepts only explicitly configured trusted roots. An
operator target must be a non-symlink regular public-certificate file below
`/etc/sing-box-manager/tls`. An ACME target must be the fixed
`/var/lib/sing-box-manager/acme` data directory; discovery is restricted to its
`certificates` subtree and hard-capped by entries, candidate certificates, and
certificate bytes. Symlinks are never followed. The adapter parses public PEM,
requires the leaf to cover the declared server name using SAN or legacy CN,
and selects the matching CertMagic leaf with the latest expiry. It never opens
an adjacent key file.

Direct mode uses this adapter locally. Privileged mode uses a new exact
`inspect-certificates` helper operation. Requests contain at most 64 ordered,
unique `{kind, server_name, location}` targets with absolute paths. Unknown
fields, relative paths, and private-key fields fail before source invocation.
Responses preserve the same target order and contain only typed material state,
source label, diagnostics, public DNS names, and ISO 8601 validity timestamps.
The unprivileged adapter rejects duplicate fields, extra fields, mismatched
targets, malformed times, or impossible observation states.

The application treats expired, not-yet-valid, invalid, and missing material as
action-required. Expiry within seven days is also action-required; expiry
within thirty days is attention. Unavailable evidence is attention and never a
healthy claim. All target details remain visible even when a higher-priority
finding determines the report summary. Textual reuses the diagnostics-center
severity and guidance presentation with markup disabled.

## Consequences

- Operators see renewal risk before an outage without adding a network probe or
  mutating ACME state.
- Direct and privileged installations share one classification policy and one
  fixed path allowlist.
- The package gains a bounded `cryptography>=42,<50` runtime dependency; release
  builds and supported-distribution installation tests must cover its wheels.
- The check proves only the locally selected public leaf's identity and
  validity window. It does not prove ACME renewal success, TLS reachability,
  private-key correspondence, or that a remote client receives the leaf.
- A future key-pair or live TLS diagnostic requires a new explicitly reviewed
  seam; this interface will not silently broaden its disclosure.

## Rejected alternatives

### Invoke `openssl x509`

Rejected because human-oriented output and executable discovery add a
subprocess contract for typed data available through a maintained Python API.

### Read private keys to verify the pair

Rejected because expiry and declared-name coverage require only the public
leaf. Reading key bytes would materially expand privilege and disclosure.

### Probe the public TLS endpoint

Rejected because DNS, routing, load balancers, and externally terminated TLS
would turn a local managed-material check into a different product claim.

### Report only the highest-priority certificate

Rejected because an expired target must not hide an adjacent permission failure
or upcoming renewal. Independent evidence is a diagnostics-center invariant.

## References

- [sing-box ACME certificate provider](https://sing-box.sagernet.org/configuration/shared/certificate-provider/acme/)
- [CertMagic storage model](https://github.com/caddyserver/certmagic)
- [PyCA cryptography X.509 reference](https://cryptography.io/en/latest/x509/reference/)
