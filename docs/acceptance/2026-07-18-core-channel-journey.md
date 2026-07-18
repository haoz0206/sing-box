# Stable/Preview core-channel journey acceptance — 2026-07-18

## Scope

This record covers the operator-facing Stable/Preview workflow from the
capability-aware Operations workspace through exact release discovery, local
inventory comparison, confirmation, and terminal evidence. It builds on the
previously accepted immutable artifact path and retained-core switch helper.

## Accepted behavior

- Operations exposes a guided Stable/Preview action when the channel manager is
  composed, while retaining the advanced exact-version action.
- The operator chooses architecture and Stable or Preview before discovery.
  Discovery runs outside the Textual application thread and performs no host
  mutation.
- The application rejects release evidence whose channel or prerelease
  classification does not match the requested policy.
- One exact discovered release produces exactly one typed state:
  already current, switch retained, or acquire and activate.
- Already-current evidence displays the exact version and has no confirmation
  action.
- A retained switch displays target and reviewed-current SHA-256 identities,
  requires explicit confirmation, and invokes the no-network switch operation.
- A missing release reuses the immutable exact-version acquisition,
  verification, and activation path. Preview shows explicit prerelease risk and
  preserves the upstream alpha/beta/rc version.
- Confirmed operations lock navigation until a terminal result. An unexpected
  switch or activation failure is non-disclosing, reports an unknown result,
  and does not offer immediate retry.
- Production composition provides both the guided channel manager and the
  advanced exact-version updater.
- `docs/MANUAL.md` documents the available three-state workflow, retained
  catalog limitation, Preview risk, and unknown-result recovery guidance.

## Evidence

- Focused channel, Operations, exact-update, and composition regression set:
  `55 passed in 32.19s`.
- Complete local suite: `675 passed, 18 skipped in 221.70s`.
- Ruff formatting: `268 files left unchanged`.
- Ruff lint: `All checks passed`.
- mypy source check: `Success: no issues found in 167 source files`.
- Git whitespace check: passed.
- Source distribution and wheel build: passed.
- Wheel SHA-256:
  `4d75c2e7df31b4542830c463c129df771f499563f4cd41c5a62da23fc3176130`.

The 18 skipped tests remain explicit opt-in external gates for approved live
hosts, distribution/package installation, a trusted real sing-box binary, and
official artifact download. This local acceptance does not claim those
environments have passed.
