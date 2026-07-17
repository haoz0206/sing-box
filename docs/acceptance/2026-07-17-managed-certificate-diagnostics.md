# Managed certificate diagnostics acceptance — 2026-07-17

## Scope

This record covers managed-certificate target derivation, expiry policy,
operator-file and CertMagic filesystem inspection, minimum-disclosure
privileged protocol, diagnostics-center and Textual presentation, direct and
privileged production composition, package construction, and supported-
distribution installation policy.

## Evidence

- Full local suite: `487 passed, 18 skipped`.
- Focused certificate application, adapter, helper, diagnostics, Textual, and
  production-composition set: `27 passed`.
- Ruff format and lint: passed.
- mypy strict source check: `Success: no issues found in 140 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Source distribution and wheel build: passed; the wheel contains the
  certificate seam, both adapters, application policy, helper operation,
  production composition, and Textual integration.
- Package release install integration from the exact wheel: `1 passed`.
- Distribution policy acceptance using host networking for the configured
  host-loopback package proxy:
  - Debian 12 / sudo: passed with Python 3.11 and a manylinux cryptography wheel;
  - Ubuntu 24.04 / sudo: passed with Python 3.12 and a manylinux wheel;
  - Alpine 3.20 / doas: passed with Python 3.12 and a musllinux wheel.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `382218926ab1c96967536158f82a5cfbe39ca396d84cb68de26d14d6bb60f30a`.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- Only enabled profiles in `APPLIED` state request certificate evidence. Draft
  and paused profiles are excluded, and profiles sharing one TLS intent produce
  one target while retaining every profile name in diagnostics.
- Operator-file targets inspect only a public certificate below
  `/etc/sing-box-manager/tls`. CertMagic targets scan only the bounded public
  `certificates` subtree below `/var/lib/sing-box-manager/acme` and select the
  latest leaf that covers the declared server name.
- Certificate files, cache entries, traversal counts, and helper targets are
  bounded. Symlinks and paths outside trusted roots are not followed.
- Public PEM is decoded with the typed X.509 API. The diagnostic returns DNS
  names and timezone-aware validity timestamps; adjacent key files are never
  opened or returned.
- Healthy validity is more than 30 days. Expiry within 30 days is attention;
  expiry within 7 days is action-required. Expired, not-yet-valid, missing, and
  invalid material are action-required. Unavailable evidence is attention and
  never a false healthy claim.
- Higher-priority findings determine the report condition without hiding
  independent evidence from another target.
- Privileged requests contain only ordered `{kind, server_name, location}`
  targets. Relative paths, duplicate targets, unknown fields, and private-key
  fields fail before source invocation.
- Helper responses contain only typed public evidence and must exactly match
  the requested target order. The client rejects malformed or extra fields,
  duplicate JSON keys, impossible state/validity combinations, and mismatches.
- Textual presents the typed condition and recovery guidance with markup
  disabled, preserving bracketed profile text literally.
- Diagnostics remain read-only. The slice does not issue or renew a certificate,
  read a private key, perform a public TLS probe, write desired state, reload
  sing-box, or mutate CertMagic storage.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when
  released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this read-only interaction slice.
