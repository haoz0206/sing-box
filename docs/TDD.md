# Sing-box Manager Python Rewrite — TDD Execution Method

Status: Active — seams confirmed  
Applies to: every implementation slice in the Python rewrite

## 1. Purpose

Tests are executable product specifications. They verify behavior through public
seams and must survive internal rewrites. The process is strict red → green, one
vertical slice at a time.

No production implementation is written before its first failing behavior test.
No test is written against an unconfirmed public seam.

## 2. Proposed public test seams — confirmation required

### Seam A — TUI user seam

Public interface: Textual application operated through visible controls,
keybindings, screen content, and modal results.

Test mechanism: `App.run_test()` and Textual Pilot.

Behaviors covered:

- navigation;
- guided input;
- visible validation;
- plan review and confirmation;
- success/failure presentation;
- keyboard accessibility.

Tests do not call screen event handlers or inspect private widget state.

### Seam B — Manager application seam

Public interface: typed user-facing requests and results for query, plan, and
apply use cases.

Behaviors covered:

- desired-state transitions;
- profile validation;
- planning decisions;
- revision conflicts;
- apply and rollback outcomes;
- error classification and redaction.

Tests do not call protocol/configuration helper functions directly when the
behavior is observable through this seam.

### Seam C — Protocol behavior seam

Public interface: validated protocol intent producing a sing-box fragment and
connection information.

Behaviors covered:

- supported choices and constraints;
- minimum core version behavior;
- known-good configuration examples;
- known-good share/connection information;
- secret redaction.

Expected values are fixed examples from the SDD and sing-box schema, never
recomputed with the same algorithm as production code.

### Seam D — System adapter contracts

Public interfaces: state store, configuration validator, runtime, TLS, artifact
source, clock/random source where needed.

Behaviors covered:

- shared contract for every real adapter;
- path and result semantics;
- failure classification;
- cancellation/timeout behavior where relevant.

Application behavior tests use small fakes only at these external system seams.
They do not mock the manager's own modules.

### Seam E — Installed command seam

Public interface: packaged `sb-manager` command exit code, standard streams, and
machine-readable subcommands introduced by the SDD.

Behaviors covered:

- process startup;
- environment/path discovery;
- non-interactive status/plan output;
- packaging and installation smoke tests.

This seam begins after M2; it is not needed for the first TUI tracer bullet.

## 3. Test portfolio

```text
few      installed command + real-host opt-in tests
some     headless TUI acceptance tests
many     manager application behavior tests
many     protocol behavior examples
focused  adapter contract and integration tests
```

Test count is not a target. Each test must protect a user-visible behavior,
domain rule, or system contract.

## 4. Red → green execution

For each vertical slice:

1. Write one worked example in plain language.
2. Identify exactly one confirmed seam that observes it.
3. Add one test with one logical outcome.
4. Run only that test and capture the expected failure.
5. Add the minimum implementation that can satisfy the example.
6. Run the focused test until green.
7. Run the existing suite to detect regression.
8. Stop the TDD loop.
9. Review naming, locality, duplication, security, and accessibility separately.
10. Start the next slice with a new failing test.

Refactoring is not smuggled into the green step. A review may schedule a separate
behavior-preserving refactor after the suite is green.

## 5. Vertical slicing rule

Slices follow user capability, never technical layers.

Good slice:

```text
operator opens an empty manager -> sees the recommended next action
-> opens protocol selection -> sees VLESS Reality explained as recommended
```

Bad slice:

```text
create all domain dataclasses -> create all adapters -> create all screens
-> add tests after implementation
```

No speculative empty modules are created for later milestones.

## 6. First tracer bullet after seam confirmation

Specification:

> Given a fresh manager state, when the operator opens the TUI, the dashboard
> clearly says that no proxy profile exists and presents `创建第一个配置` as the
> primary action. When the operator activates that action, the app opens protocol
> selection and marks VLESS Reality as the recommended starting choice.

Primary seam: Seam A — TUI user seam.

Expected first red:

- `sb_manager.ui.app.ManagerApp` does not exist.

Minimum green:

- one application;
- one empty dashboard screen;
- one protocol selection screen;
- one user action connecting them;
- no persistence, subprocess, networking, or host mutation.

The second tracer bullet will be chosen only after learning from the first.

## 7. Test data rules

- UUIDs, domains, ports, keys, timestamps, and versions in tests are fixed known
  examples.
- Randomness and time enter through system seams.
- Secrets use obviously synthetic values and are asserted absent from normal
  presentation.
- JSON assertions compare parsed semantic structures, not whitespace or key
  order.
- Golden files are accepted only for independently reviewed protocol examples or
  full-screen rendering where semantic assertions are insufficient.
- A golden update is reviewed as a product behavior change, never performed
  automatically to make CI pass.

## 8. Mocking policy

Allowed fakes/mocks:

- subprocess execution;
- network/DNS;
- filesystem only when a real temporary directory cannot express the case;
- clock and randomness;
- init systems;
- artifact sources.

Preferred over mocks:

- real domain objects;
- real manager application module;
- real temporary directories;
- real JSON serialization;
- Textual headless application;
- a real sing-box binary in opt-in integration tests.

Forbidden:

- mocking protocol/application internals;
- asserting internal call counts;
- calling private screen methods;
- inspecting files to verify behavior that has a public query interface;
- duplicating the implementation algorithm in expected values.

## 9. Failure evidence

Every cycle records red and green through command output. A test that passes on
its first run is not accepted as the starting test; it must be corrected until it
demonstrates the missing behavior.

Expected failure types:

- missing public object/interface for the first slice;
- assertion failure for later behavior;
- deliberately unsupported system capability for an adapter contract.

Unexpected collection/configuration failures are fixed before implementation;
they do not count as a valid red.

## 10. Suite layout

```text
tests/
  acceptance/        # Seam A and later Seam E
  behavior/          # Seam B
  protocols/         # Seam C
  contracts/         # Seam D shared adapter contracts
  integration/       # real filesystem/binary/host opt-in cases
  fixtures/          # independently reviewed examples
```

Tests are named as capabilities, for example:

```text
test_operator_can_start_first_profile_from_empty_dashboard
test_plan_rejects_a_port_occupied_after_snapshot
test_failed_validation_preserves_applied_revision
test_reality_profile_produces_known_good_inbound
```

Names describing implementation calls are rejected.

## 11. Quality gates

Focused development gate:

```text
pytest path/to/current_test.py
```

Local suite gate:

```text
pytest
ruff format --check .
ruff check .
mypy src
```

Release gate adds:

- package build and clean-environment install;
- exact retained-package rollback plan, confirmation, stale-plan, and stable
  launcher behavior;
- profile removal plans for draft and applied scopes, revision conflicts,
  desired-state-only deletion, transactional live projection, failed-host state
  preservation, final-profile zero-inbound validation against the privileged
  allowlist and real sing-box, and the complete Textual confirmation/result journey;
- profile edit plans for normalized mutable metadata, no-op and field
  validation, desired-state-only versus live-configuration scope, revision and
  reviewed-content conflicts, transactional failure preservation, every typed
  TUI result, production composition, and real sing-box reprojection;
- headless TUI acceptance suite;
- supported Python matrix;
- semantic configuration fixtures;
- real `sing-box check` integration suite;
- adapter contract suites;
- isolated-root transactional apply/rollback suite;
- explicitly opted-in systemd/OpenRC host smoke tests whose authorization is
  bound to the exact runtime and service, with healthy pre- and postconditions.

## 12. Definition of done for a slice

- The test failed for the intended missing behavior before implementation.
- The behavior is observable through one confirmed public seam.
- The focused test and existing suite pass.
- No new unapproved seam was introduced.
- External effects remain behind system seams.
- User-visible errors are actionable and redact secrets.
- The SDD is updated if the slice changes product behavior or domain language.
- No speculative implementation for a later slice was added.

## 13. Confirmation record

Implementation may begin only after the user confirms or changes Seams A–E.
Record the accepted seams and date here before writing the first test.

```text
Status: confirmed
Accepted seams: A, B, C, D, E
Date: 2026-07-16
Notes: User confirmed the complete proposed seam set without changes.
```
