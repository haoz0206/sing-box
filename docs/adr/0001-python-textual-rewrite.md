# ADR-0001: Rewrite the manager in Python with a Textual TUI

Status: Accepted  
Date: 2026-07-16

## Context

The repository is currently a Bash installer and manager for sing-box. Protocol
knowledge, JSON generation, host mutation, runtime management, TLS, downloads,
and interaction state are coupled through shell functions and shared global
variables.

The intended product is expanding from a fast one-click script into a guided,
safe, and sustainably extensible personal proxy manager. Preserving every Bash
command would constrain the new interaction design without providing enough
long-term value.

## Decision

The manager will be rewritten in typed Python and will use Textual for its
primary terminal user interface.

The rewrite is product-led rather than translational:

- the TUI uses guided screens, progressive disclosure, plans, and explicit
  confirmation;
- manager desired state becomes authoritative;
- sing-box and Caddy configuration are generated artifacts;
- external effects live behind explicit system seams;
- implementation proceeds as test-driven vertical slices;
- existing Bash behavior is reference material, not a compatibility contract.

The initial supported Python baseline is 3.10. Textual 8.x is the initial UI
dependency line. Runtime dependencies are installed in a private virtual
environment for production deployments.

## Consequences

Positive:

- protocol and plan behavior can use typed models rather than global shell
  state;
- configuration transactions and rollback can be represented explicitly;
- Textual user journeys can be tested headlessly;
- systemd and OpenRC can be real adapters behind one runtime seam;
- future non-interactive commands can reuse the same application behavior;
- the project can add richer interaction without teaching operators protocol
  syntax.

Costs:

- Python and a private environment become installation dependencies;
- the project must define packaging and supported Python/OS matrices;
- a parallel migration period is required;
- privileged host integration still needs real-system contract and smoke tests;
- Textual upgrades require deliberate dependency review.

## Rejected alternatives

### Continue large-scale Bash refactoring

Rejected because it improves locality only partially while preserving weak data
modeling, error propagation, and TUI testability.

### Big-bang behavioral port

Rejected because it would reproduce the current interaction limitations and
hide behavior gaps until late integration.

### Rewrite in Go immediately

Rejected for the current single-host scope. A compiled manager may be revisited
if multi-host orchestration, a long-running daemon, or a stable remote interface
becomes a product requirement.

### Use the standard-library curses module

Rejected because the project would own more navigation, layout, interaction,
and headless-testing infrastructure than its product domain warrants.

## Follow-up decisions

- Public testing seams require explicit confirmation in `docs/TDD.md`.
- The supported OS/Python matrix must be accepted before privileged host apply.
- Packaging and update trust policy require a later ADR before M5.

