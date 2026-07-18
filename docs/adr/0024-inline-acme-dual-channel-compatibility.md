# ADR-0024: Use inline ACME across the current dual-channel compatibility window

Status: Accepted  
Date: 2026-07-18

Latest Stable `1.13.14` rejects the shared `certificate_provider` shape added in
1.14, while latest Preview `1.14.0-alpha.47` still accepts the older inline
`tls.acme` shape. The manager therefore emits the strictly allowlisted inline
shape as the common configuration denominator for the current Stable/Preview
window. It omits 1.14-only ACME fields and top-level providers. This decision
does not relax ADR-0003 artifact trust: configuration compatibility and whether
an upstream release is acceptable to acquire are separate claims.

## Consequences

- Current Stable and Preview configurations use one projection with real-binary
  coverage instead of protocol-local version branches.
- Inline ACME is deprecated in 1.14 and scheduled for removal in 1.16. Before a
  supported channel reaches 1.16, the TLS seam must select a version capability
  profile and restore shared providers for that release.
- The privileged configuration policy accepts only the exact inline fields,
  requires its domain to match TLS `server_name`, and fixes its data directory.
