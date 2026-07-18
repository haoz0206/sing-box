# Snell v6 exact-core compatibility acceptance — 2026-07-18

Status: **PASS.** The deterministic product tests are separate from the opt-in
real-binary executions below. The default integration run skipped without an
explicit executable, Stable proved typed pre-generation rejection, and Preview
proved that the bounded generated Snell configuration passes real
`sing-box check` without disclosing its PSK.

## Accepted support contract

- Snell support is v6 only, with fixed default mode and one generated top-level
  PSK. The manager excludes v5, multi-user `users`/`userkey`, unsafe modes, TLS,
  transport, multiplex, QUIC proxy, and custom `snell://` payloads.
- The exact version reported by the active core during planning is capability
  truth. A channel label is not. Snell requires `1.14.0-alpha.38` or newer;
  Stable 1.13.x and unknown observations fail closed before mutation.
- Every later projection rechecks exact compatibility. Core targets bind the
  desired-state revision; applied and enabled Snell blocks an incompatible
  target, while draft or paused Snell does not. Pausing or removing the final
  active Snell profile is the recovery path to Stable.
- The privileged policy validates the exact projected shape but never discovers
  a core version.
- The client artifact is an official Surge policy, not a URI:
  `Name = snell, host, port, psk=REDACTED, version=6`. The operator may rename
  `Name` in Surge. The real payload remains hidden until explicit reveal. No
  real PSK is included in this evidence record.

These boundaries follow the official [sing-box Snell inbound](https://sing-box.sagernet.org/configuration/inbound/snell/),
[sing-box Snell outbound](https://sing-box.sagernet.org/configuration/outbound/snell/),
[sing-box changelog](https://sing-box.sagernet.org/changelog/), and
[Surge proxy-policy](https://manual.nssurge.com/policy/proxy.html)
documentation.

## Official artifact evidence

The artifacts and digests below are dated acceptance inputs, not permanent
production constants:

| Channel observation | Official Linux amd64 artifact | SHA-256 |
|---|---|---|
| Stable `1.13.14` | `sing-box-1.13.14-linux-amd64.tar.gz` | `f48703461a15476951ac4967cdad339d986f4b8096b4eb3ff0829a500502d697` |
| Preview `1.14.0-alpha.47` | `sing-box-1.14.0-alpha.47-linux-amd64.tar.gz` | `39387ea20a1b44fc123c106fb4b2cf961b98f5550e55a516f446498a163336e1` |

Their official discovery, trust mode, download, digest verification, version
self-verification, isolated activation, and rollback provenance is recorded in
[Official Stable digest fallback and Preview acceptance — 2026-07-18](2026-07-18-stable-digest-fallback.md).
That record explains why Stable used the digest-pinned fallback and Preview
required immutable prerelease evidence. Neither record promises that a later
channel discovery will resolve the same version or digest.

The table contains source archive/artifact digests. Extracted executable
digests are separate byte identities and are reported with the real-core runs
below; they must not be compared as though archive and executable were the same
file.

## Deterministic and opt-in boundaries

The normal contract, behavior, acceptance, privileged-policy, and TUI suites
use fakes or generated documents and require neither root, network, nor an
external core. They prove version comparison, exact plan binding, fail-closed
errors, no-mutation boundaries, desired-state revision checks, allowlisted
Snell shape, typed Surge payloads, and secret-safe disclosure.

`tests/integration/test_real_sing_box.py` is different: it invokes the trusted
executable named by `SB_MANAGER_REAL_SING_BOX`. Without that explicit opt-in,
the integration cases skip before invoking sing-box:

```console
rtk .venv/bin/pytest tests/integration/test_real_sing_box.py -q -rs
```

Observed result: `17 skipped in 0.34s`. No external executable was invoked.

For reproduction, first follow the official acquisition commands and trust
evidence in [the Stable digest fallback and Preview acceptance](2026-07-18-stable-digest-fallback.md).
Verify the archive/source digest against the dated table above, extract it to a
trusted location, and point `SB_MANAGER_REAL_SING_BOX` at the extracted binary.
The placeholders below must therefore name independently verified official
binaries that report the expected exact versions.

Run the Stable case with:

```console
rtk env SB_MANAGER_REAL_SING_BOX=/absolute/path/to/sing-box-1.13 .venv/bin/pytest tests/integration/test_real_sing_box.py -q -rs -k legacy_real_sing_box_rejects_snell_v6_before_configuration
```

Observed result: `1 passed in 0.34s`. The executable reported `1.13.14`; the
test raised the structured incompatibility before creating a configuration and
the temporary test directory remained empty. The extracted binary SHA-256 was
`68aeab83cc4ab2659a5b92232261a20746ccdafc3b3d1e19b2d63247eec3bbf7`.

Run the capable Preview case separately:

```console
rtk env SB_MANAGER_REAL_SING_BOX=/absolute/path/to/sing-box-1.14-preview .venv/bin/pytest tests/integration/test_real_sing_box.py -q -rs -k capable_real_sing_box_accepts_generated_snell_v6_configuration
```

Observed result: `1 passed in 0.37s`. The executable reported
`1.14.0-alpha.47`; the test proved the exact v6/default/single-top-level-PSK
inbound, fixed direct outbound, privileged-policy acceptance, successful real
`sing-box check`, and absence of the generated PSK from diagnostics. The
installed binary SHA-256 was
`ed43be663338e70fef2fd644299343e00638fb8b65a59849bf8bdbdb9f39a97e`.
The source digest is the archive digest and is therefore not expected to equal
the extracted executable digest. This run verified the source digest recorded
in the manager manifest; no local Preview archive remained for a second
independent archive rehash.

## External nondeterminism boundary

Acquiring official artifacts depends on upstream metadata, CDN availability,
DNS, TLS, rate limits, and bandwidth. The real-core test itself depends on the
operator selecting the intended verified executable. Those external facts are
release evidence only; they do not replace deterministic compatibility and
transaction tests, and their dated versions and hashes must not become
hardcoded production capability policy.
