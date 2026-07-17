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

- complete profile-creation traversal through the Textual Pilot seam: catalog
  propagation across form, validation, plan, draft, confirmation, progress, all
  typed apply outcomes, expected operational failure, and non-disclosing unknown
  results; stable application validation identities; literal non-markup dynamic
  evidence; duplicate-confirmation suppression; and terminal button/`Esc`
  navigation to a freshly recomposed dashboard;
- purpose-first recommendation examples for general, low-latency,
  restricted-network, and compatibility outcomes; exact protocol/transport
  variant and rationale identity, catalog-rendered reasons and tradeoffs,
  non-guarantee wording, catalog-rendered advanced direct selection,
  non-disclosing same-page fallback after unexpected advisor failure,
  existing-form handoff, production composition, and regression coverage for
  every supported profile form;
- package build and clean-environment install;
- exact retained-package rollback plan, confirmation, stale-plan, and stable
  launcher behavior;
- profile edit, removal, availability, and template planning through Textual
  controls for non-disclosing unclassified exceptions, explicit no-mutation
  wording, fresh-read retry guidance, and preservation of typed validation,
  stale-selection, and port evidence;
- startup state inspection, profile details, purpose recommendation,
  new-profile planning, adoption planning, and core-update planning for a usable
  non-disclosing TUI, accurate no-mutation wording, and a fresh-read or advanced
  fallback path;
- exact core-update form validation, semantic prerelease warning identity,
  catalog-rendered immutable plan and activation evidence, literal non-markup
  typed diagnostics, and catalog-rendered acquisition/unknown-result recovery;
- confirmed profile-apply, profile-edit, profile-removal,
  profile-availability, profile-clone, config-adoption, state-recovery, and
  core-update workers for
  non-disclosing unclassified exceptions, complete scope-specific unknown-result
  wording, absence of unsafe state inference or automatic retry, and
  preservation of existing typed failure evidence;
- exact-fingerprint adoption catalog propagation through review, confirmation,
  guarded progress, classified rejection, success, unexpected planning failure,
  unknown confirmed result, and explicit fresh-dashboard return;
- profile removal plans for draft and applied scopes, revision conflicts,
  desired-state-only deletion, transactional live projection, failed-host state
  preservation, final-profile zero-inbound validation against the privileged
  allowlist and real sing-box, catalog propagation through planning and
  operational failures, literal non-markup diagnostics, missing-transaction
  uncertainty, precondition and commit failures, rollback success, manual
  recovery instructions, and the complete Textual confirmation/result journey;
- profile template cloning for semantic copied/reset facet presentation,
  editable-name review, revision and source-intent conflicts, desired-state-only
  confirmation, catalog propagation through every form/result/failure state,
  literal non-markup profile values and diagnostics, unknown desired-state
  outcomes, dashboard refresh, and secret-free independent drafts;
- profile edit plans for normalized mutable metadata, no-op and field
  validation, desired-state-only versus live-configuration scope, revision and
  reviewed-content conflicts, transactional failure preservation, every typed
  TUI result, production composition, and real sing-box reprojection;
- credential-bearing connection links through both persisted profile details
  and successful first apply: the complete URI is absent from mounted terminal
  controls before explicit reveal, the risk guidance and action are visible,
  revealed text is read-only and page-local, immediate conceal cannot be
  followed by a second reveal on the same page, and no clipboard side effect is
  introduced;
- listen-port edit plans for fixed/automatic selection, range, duplicate intent,
  host availability, policy-only scope, confirmation-time recheck, automatic
  selection under lock, transactional projection, typed stale-port TUI
  guidance, production composition, and real sing-box reprojection;
- profile availability plans for active/paused/no-op/draft states, explicit
  confirmation, revision and reviewed-content conflicts, fixed-port TOCTOU,
  automatic-port reselection under lock, material preservation, zero-inbound
  pause projection, failed-host state preservation, typed transaction and
  recovery presentation, legacy-state compatibility, production composition,
  and real sing-box pause/resume validation;
- diagnostics-center aggregation for healthy evidence, corrupt or inconsistent
  desired state, duplicate/missing identities, readiness/runtime probe
  isolation, severity prioritization, on-demand TUI loading, refresh after
  recovery, non-disclosing unexpected failure retry, and production composition;
- dashboard background-probe isolation for non-disclosing runtime/readiness
  failure states, conservative next-action guidance, disabled stale details,
  catalog propagation into the host-runtime fallback drill-down, exact
  healthy/unhealthy summaries, missing-detail fallback, literal non-markup
  diagnostics and recovery instructions, no recovery action for healthy state,
  and `Esc` return to the existing dashboard context;
  explicit read-only retry, successful recovery, a persistent no-automatic-
  mutation scope statement, and catalog-backed titles, probe states, counts,
  navigation, and reinspection controls;
- typed dashboard recommendation priority across failed, pending, blocking,
  maintenance, draft, empty, and healthy evidence; stable recommendation and
  action identities, catalog-rendered summaries and labels, capability-aware
  withholding, one visible primary action, and Pilot journeys that execute add,
  draft-review, and failed-probe recovery without producing or parsing
  presentation text in application policy;
- dashboard continuity after successful profile edit, removal, pause/resume,
  template creation, or desired-state recovery: stale observations are cleared,
  current desired state is recomposed, and all configured read-only workers run
  again; managed-certificate maintenance covers healthy, attention,
  action-required, non-disclosing failure, explicit retry, recommendation
  priority, and direct/privileged production composition through the same
  application module used by the diagnostics center;
- desired-state recovery acceptance for catalog propagation across recoverable,
  unsupported-schema, unavailable-backup, and inspection-failure startup
  states; exact primary/backup SHA-256 review; non-returning confirmation
  progress; stale-plan rejection without retry; distinct unknown durability and
  unclassified outcomes; non-disclosure; durable revision/profile/archive
  evidence; and explicit return to a freshly recomposed dashboard;
- live-configuration identity diagnostics for empty, untracked, matching,
  missing, externally changed, and failed-probe observations, including
  single-snapshot desired-state failure isolation and direct/privileged
  production inspector composition;
- generated-configuration diagnostics for valid and semantically rejected
  documents, projection failures, unavailable disposable staging, protocol
  material redaction, missing-core priority, Textual presentation, production
  composition, and the real `sing-box check` release gate;
- public-domain diagnostics for normalization, IDNA/domain syntax, duplicate
  domains and IP endpoints, public and TLS names, successful/partial/failed
  resolution, one bounded worker lifetime, Textual presentation, and production
  composition without external-network test requirements;
- service-log drill-down for 1–500 line bounds, native systemd and OpenRC
  command contracts, command/permission/empty states, persisted and generic
  credential redaction, control-sequence cleaning, non-markup Textual
  presentation, typed-unavailable evidence, non-disclosing unexpected failure,
  refresh, retry, and both production compositions;
- listener ownership diagnostics for protocol-specific TCP/UDP expectations,
  draft/paused exclusion, missing and foreign listeners, incomplete ownership,
  unavailable `/proc`, IPv4/IPv6 inode merging, UDP socket state, owner process
  resolution, PID/descriptor scan limits, control-character cleaning,
  non-markup Textual presentation, and production composition;
- managed certificate diagnostics for applied/enabled filtering, shared-target
  deduplication, healthy/30-day/7-day/expired/not-yet-valid/material-state
  policy, mixed-evidence preservation, operator-file and CertMagic cache
  contracts, trusted-root and symlink containment, exact privileged request and
  response schemas, private-key-field rejection, non-markup Textual
  presentation, and direct/privileged production composition;
- configuration apply history for durable pre-mutation recording, typed final
  outcomes, interrupted/final-write-unknown semantics, strict atomic JSON,
  bounded retention, symlink refusal, credential redaction, diagnostics-center
  classification, non-markup Textual drill-down, non-disclosing unexpected
  failure retry, and shared direct/privileged production composition;
- keyboard-first Textual navigation for discoverable `?` help, dashboard-only
  add/profiles/network/settings/diagnostics/operations/quit actions, child-screen suppression,
  non-mutating navigation, and preservation of normal form input; the
  operations workspace must prove capability-aware available/unavailable
  presentation plus on-demand core, service-log, and apply-history handoff; the
  profiles workspace must prove dashboard/inventory separation, capability-
  aware row actions, exact profile-ID handoff through one typed UI message,
  `Esc` context preservation, dashboard refresh after lifecycle success,
  catalog injection for inventory copy, and an always-visible read-only,
  plan-first, explicit-confirmation scope statement;
- profile-details acceptance for catalog propagation through the nested
  connection-share panel, a visible read-only lifecycle scope, endpoint intent
  when no share URI exists, one-page credential reveal/hide, disclosure-safe
  expected and unexpected read failures, scrollable layout, and unchanged
  edit/availability/clone/removal plan handoff;
- profile-edit acceptance for catalog propagation from details through form,
  normalized plan, desired-state result, read-only planning failure, and
  unknown mutation result; exact desired-only versus live-transaction impact,
  actionable field validation, revision-bound confirmation, typed conflict and
  rollback outcomes, non-disclosing unexpected failures, and non-markup dynamic
  profile/diagnostic evidence;
- profile-availability acceptance for catalog propagation from details through
  pause/resume plan, committed result, expected rejection, unexpected planning
  failure, and unknown mutation result; preserved identity/material, exact
  complete-configuration impact, confirmation-time port policy, typed
  transaction/rollback evidence, and non-markup profile and diagnostic values;
- read-only Network workspace acceptance for empty and populated desired state,
  lifecycle-aware TCP/UDP listener intent, fixed and apply-time automatic ports,
  public addresses, explicit no-probe/no-firewall policy, contextual `n`
  navigation, and preservation of existing listener-diagnostics behavior
  through the shared endpoint projection;
- Settings workspace acceptance for a visible/default-terminal entry,
  application-wide dark/light switching, reopening within one process and
  restoration in a new process, per-user/no-host-effect scope disclosure,
  exact effective preference path, default/loaded/saved/unavailable visible
  states, non-disclosing malformed-storage fallback, preservation of future
  schemas, bounded 64 KiB document reads, strict schema-v1 JSON, mode-`0600`
  atomic writes, symbolic-link refusal, reset visibility only for unavailable
  persistence, review-only
  SHA-256/default/scope presentation, cancellation without writes, explicit
  confirmation, archive-before-replace semantics, mode-`0600` original-byte
  preservation, confirmation-time fingerprint conflict, non-disclosing typed
  and unknown failures, immediate default-theme restoration, cross-process
  reload, complete simplified-Chinese language support plus an explicit
  no-partial-locale policy, catalog-backed Settings/reset copy, effective
  direct/helper and init-system labels, helper-fixed versus direct config
  targeting, transaction paths, manual-exact-version update policy, contextual
  `s` suppression, and production CLI composition;
- confirmed-operation navigation for pre-confirmation cancellation, disabled
  return while a worker is in flight, duplicate-confirmation suppression,
  terminal-result delivery to the originating screen, and guard release before
  subsequent navigation;
- typed diagnostic-action journeys from an untracked configuration to exact
  fingerprint adoption review and from a helper-ready missing core to the
  trusted update form, including withheld actions when prerequisites or
  destination modules are unavailable;
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
