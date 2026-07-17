# ADR 0009: Prioritized read-only diagnostics center

- Status: Accepted
- Date: 2026-07-17

## Context

The dashboard already observed runtime health and first-run readiness, but its
diagnostics page showed only one runtime result. Operators had to mentally
combine desired-state integrity, configuration ownership, helper readiness,
core availability, and service health. Calling adapters or parsing command
output in the TUI would spread system knowledge across screens and make partial
failures difficult to explain safely.

The product needs actionable checks before it needs a general log viewer. One
failed probe must not erase independent evidence that can still guide recovery.

## Decision

Introduce one deep `DiagnosticsCenter` application interface with a single
read-only operation:

```text
inspect() -> DiagnosticsCenterReport
```

`DiagnosticsCenterService` owns aggregation and translation:

- validates readable desired state, stable and unique profile identities,
  applied profile port/material completeness, and the managed-configuration
  fingerprint invariant;
- reuses the active direct or privileged configuration-target inspector to
  compare its content-free SHA-256 observation with the desired-state
  replacement precondition;
- reuses the typed host-readiness interface for configuration target, minimum
  privilege helper, and core evidence;
- reuses typed runtime diagnostics for process health and recovery guidance;
- maps all checks to `healthy`, `attention`, or `action-required`;
- preserves each independent result when another probe fails;
- selects the first action-required guidance, then attention guidance, as the
  single recommended operator action; a fully healthy report returns no
  recommendation so locale-specific “no action required” policy remains in the
  presentation catalog.

The Textual screen loads only when the operator opens the diagnostics center,
runs inspection in a worker, displays stable check identities and guidance, and
supports an explicit recheck. The dashboard retains its lightweight background
runtime/readiness summary but exposes only one diagnostics action when the
center is available. Page framing, priority summaries, condition markers,
missing-detail fallback, progress/error recovery, and navigation labels come
from the validated interface copy catalog; report evidence is rendered
literally with markup disabled.

The live-configuration identity check has six explicit outcomes: no recorded
identity and no target is healthy; an existing untracked target requires
explicit adoption; an exact match is healthy; a missing recorded target or a
different fingerprint requires recovery; and an unavailable inspector becomes
one isolated action-required item. Desired state is loaded once per report so a
corrupt document cannot fail again while independent host probes continue.

The first slice does not read raw logs, mutate the host, or claim to validate
domain resolution, certificate expiry, generated configuration semantics, port
ownership, or historical apply results. Identity equality is not semantic
configuration validation. Those become later typed checks behind the same
report interface.

## Consequences

- The TUI learns one report interface instead of state, core, helper, and init
  system details.
- Operators receive one prioritized next action without losing lower-priority
  evidence.
- Corrupt desired state and unavailable probes appear as actionable checks
  rather than crashing or emptying the screen.
- Opening and refreshing the center repeats read-only probes, so slow external
  checks remain in a background worker.
- New diagnostics can extend the report without adding subprocess knowledge to
  the screen.

## Rejected alternatives

### Let the TUI call each adapter

Rejected because adapter error handling, priority, and wording would be
duplicated across presentation code.

### Replace first-run readiness with diagnostics

Rejected because readiness is a focused setup workflow with valid setup
actions, while diagnostics is a broader read-only explanation surface.

### Start with raw journal or OpenRC logs

Rejected because raw output can contain secrets, is init-system-specific, and
does not provide a stable recommended action without a separate redaction and
classification design.
