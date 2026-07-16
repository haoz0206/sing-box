# ADR 0010: Typed diagnostic actions

- Status: Accepted
- Date: 2026-07-17

## Context

The diagnostics center already selected one highest-priority guidance string.
Operators still had to leave the report and rediscover an existing workflow on
the dashboard. Turning guidance strings into buttons by matching Chinese text
would couple navigation to presentation wording. Running commands directly
from a diagnostic would bypass the product's plan and confirmation model.

The useful interaction is narrower: when a finding has an existing safe review
or planning workflow, the report can identify that destination without owning
or executing it.

## Decision

`DiagnosticItem` may carry one optional `DiagnosticAction`. The report exposes
the action only from the same highest-priority item used for its recommended
guidance. The Textual diagnostics screen maps that stable action to an existing
screen only when the required application module is present.

The initial action set is:

- `review-config-adoption`: opens the existing exact-fingerprint adoption
  review for an untracked live configuration;
- `manage-core`: opens the trusted exact-version core-update form when the core
  is missing and the minimum-privilege helper is already ready.

Opening either destination is non-mutating. Adoption still requires review and
explicit confirmation. Core update still requires version/architecture input,
pre-release consent where applicable, plan review, and explicit activation
confirmation.

The diagnostics center remains read-only. It reports typed navigation but does
not acquire artifacts, call privileged helpers, write desired state, or execute
runtime commands.

## Consequences

- Recommended text and the visible button always refer to the same prioritized
  finding.
- Translation and wording changes cannot alter navigation behavior.
- Missing application modules or unmet prerequisites remove the button while
  preserving diagnostic evidence and guidance.
- New actions require a deliberate typed value, a safe existing destination,
  and a Textual user-journey test.

## Rejected alternatives

### Match guidance text in the TUI

Rejected because localization or copy editing could silently change behavior.

### Put shell commands in diagnostic buttons

Rejected because this would bypass typed system adapters, planning, privilege
isolation, and explicit confirmation.

### Let every finding expose a button

Rejected because competing actions would undermine prioritization and could
route the operator around a more urgent prerequisite.
