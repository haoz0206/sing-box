# ADR 0012: Generated configuration diagnostics

- Status: Accepted
- Date: 2026-07-17

## Context

Desired-state consistency and live-configuration identity answer different
questions from whether the current intent can still produce a configuration
accepted by the configured sing-box core. Before this decision, semantic
validation happened only inside an apply transaction or release integration
test. An operator could therefore discover a projection or schema problem only
after entering a mutation workflow.

The diagnostics center must not copy protocol assembly, expose generated JSON,
or weaken apply-time validation. It also must not treat a missing core as proof
that the generated document itself is invalid, and validator output must not
leak persisted credentials into the TUI.

## Decision

Add one read-only `GeneratedConfigurationInspector` seam. Its production adapter
accepts a complete `ManagedInstallation`, reuses `ManagedConfigurationProjector`,
stages the canonical document in a disposable `ConfigurationStager`, and calls
the existing `ConfigValidator`. It returns only typed validity and redacted
diagnostics; it never returns the document or changes the live target.

Projection failures are invalid configuration evidence. Filesystem or probe
failures raise a typed inspection error so the diagnostics center presents an
unknown result rather than an invalid document. Validator diagnostics replace
every persisted protocol-material value before crossing into the application
and UI modules.

The production composition root always installs this inspector. The diagnostics
center places host-readiness findings before the generated-configuration item.
When the configured core is unavailable, it reports the check as not performed
and preserves the existing core-install action as the highest-priority next
step. Otherwise valid, rejected, and unavailable checks become independent
diagnostic items and do not erase live-identity or runtime evidence.

## Consequences

- Operators see semantic configuration failures before approving an apply.
- Apply and diagnostics use the same complete projector and validator seam,
  preventing a second configuration model from forming in the UI.
- Temporary files stay inside the existing staging module and are removed after
  each check.
- A diagnostics refresh may execute one bounded `sing-box check`, but cannot
  write manager-owned or live configuration.
- New protocol support automatically participates once its catalog handler can
  re-materialize persisted applied intent.

## Rejected alternatives

### Validate the live configuration instead

Rejected because live identity and desired-state projection answer different
questions. A valid live file does not prove the next desired document is valid.

### Rebuild protocol fragments inside diagnostics

Rejected because it would create a shallow parallel generator that can drift
from apply behavior.

### Display validator output without redaction

Rejected because schema errors may echo credentials or key material and normal
diagnostic presentation is not a secret-reveal workflow.

### Treat a missing core as invalid configuration

Rejected because it gives the operator the wrong recovery action and conflates
an unavailable validator with semantic rejection.
