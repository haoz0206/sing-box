# Sing-box Manager Python Rewrite — Software Design Document

Status: Active implementation  
Version: 0.1  
Primary language: Python 3  
Primary interface: Textual TUI

## 1. Decision

The repository will be rewritten as a Python management application for sing-box.
It is a new product design, not a behavioral port of the Bash scripts.

The existing Bash implementation remains a reference for protocol coverage and
host integration, but does not define the new interaction model or internal
architecture.

## 2. Product intent

The product helps a single server operator safely build and maintain a personal
proxy service over SSH without memorizing protocol syntax or editing JSON by
hand.

The product optimizes for:

- guided operation instead of command memorization;
- safe plans before privileged changes;
- useful defaults with progressive disclosure;
- clear health and diagnostic feedback;
- reliable configuration generation and rollback;
- sustainable addition of protocols and host adapters.

## 3. Non-goals for the first stable release

- Reimplementing the sing-box core.
- Preserving every Bash command and output string.
- A browser-based control panel.
- Multi-server orchestration.
- Traffic accounting, billing, or a user database.
- A third-party plugin marketplace.
- Editing arbitrary sing-box JSON through form fields.

## 4. Product principles

### 4.1 Desired state is authoritative

The manager owns a versioned desired-state document. Generated sing-box and
Caddy files are artifacts, not the source of truth.

Default paths:

```text
/etc/sing-box-manager/state.json       # desired state, manager-owned
/etc/sing-box-manager/backups/         # transaction backups
/etc/sing-box/config.json              # generated global configuration
/etc/sing-box/conf/*.json              # generated inbound configurations
/etc/caddy/233boy/*.conf               # generated edge configuration
```

Existing unmanaged configurations may be discovered and displayed read-only.
Adoption/import is a separate workflow and will never silently rewrite them.

### 4.2 Plan before apply

Every mutation has two phases:

```text
user intent -> validated desired state -> execution plan -> explicit approval
            -> staged artifacts -> external validation -> atomic commit
            -> runtime refresh -> result
```

The plan explains:

- files to create, update, or remove;
- ports to open or close;
- processes to reload or restart;
- packages or artifacts to download;
- credentials that will be generated;
- validation and rollback actions.

Secrets are redacted in plans and logs unless the user explicitly requests a
one-time reveal.

### 4.3 Privilege is required only at apply time

The TUI can start, inspect desired state, build profiles, and preview plans
without root. Privileged checks and changes occur behind the executor seam.

### 4.4 One writer

Only one backend may own manager-controlled artifacts. Bash and Python must
never write the same managed files during migration.

### 4.5 Narrow public seams, deep modules

CLI/TUI screens coordinate user intent. Protocol, configuration transaction,
runtime, TLS, and artifact details remain inside their respective modules.
Splitting one function per file is explicitly avoided.

## 5. TUI information architecture

### 5.1 Global frame

```text
┌ Sing-box Manager ─ host.example ─ core 1.x ─● healthy ────────────────┐
│ Dashboard │ Profiles │ Network │ Operations │ Diagnostics │ Settings │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│                         active screen                                 │
│                                                                       │
├───────────────────────────────────────────────────────────────────────┤
│ ? Help   a Add profile   p Preview plan   Enter Open   q Quit         │
└───────────────────────────────────────────────────────────────────────┘
```

The application is keyboard-first and mouse-capable. A persistent footer shows
only actions valid for the current screen.

### 5.2 Dashboard

The dashboard answers five questions without navigation:

1. Is sing-box healthy?
2. How many profiles are active or unhealthy?
3. Is there an unapplied plan?
4. Are certificates or artifacts approaching maintenance?
5. What is the safest next action?

Initial empty-state primary action: `Create your first profile`.

### 5.3 Profiles

Profiles represent operator intent, not raw inbound JSON.

List columns:

- display name;
- purpose;
- protocol;
- public endpoint;
- health;
- applied revision.

Profile detail shows connection information, share actions, generated artifact
summary, recent apply result, and context-sensitive actions.

### 5.4 Profile wizard

The wizard uses progressive disclosure:

1. Purpose: general use, low latency, restricted network, compatibility.
2. Recommended protocol: ranked choices with plain-language trade-offs.
3. Endpoint: port, domain, or automatic selection.
4. Credentials: generated by default; manual override under advanced options.
5. Transport and TLS: only choices supported by the selected protocol.
6. Review: human-readable plan, warnings, and one explicit apply action.

The first implementation slice supports one guided VLESS Reality profile. The
architecture must not assume Reality is the only protocol.

### 5.5 Network

Owns DNS policy, listening addresses, public address discovery, port inventory,
and firewall intent. Firewall mutation is deferred until an adapter and recovery
design are accepted.

### 5.6 Operations

Owns core/Caddy versions, update plans, backup history, restore, start/stop,
restart/reload, and maintenance state.

### 5.7 Diagnostics

Presents actionable checks rather than raw logs first:

- desired state validity;
- generated configuration validity;
- port conflicts;
- domain resolution;
- certificate condition;
- process condition;
- recent apply failure and rollback result.

Raw logs remain available as a drill-down view with secrets redacted.

### 5.8 Settings

Owns language, color/accessibility preferences, update channel, paths, and
advanced behavior. Chinese is the initial UI language; user-visible strings are
centralized so another locale does not require changing screens.

## 6. Domain model

### 6.1 ManagedInstallation

Describes desired state for one host:

- schema version;
- installation identity;
- global DNS/log/NTP policy;
- profiles;
- TLS resources;
- artifact policy;
- last successfully applied revision.

### 6.2 Profile

A named proxy endpoint managed as one user concept:

- stable identifier;
- display name and purpose;
- enabled state;
- protocol specification;
- endpoint specification;
- credential specification;
- transport/TLS specification;
- optional share metadata.

### 6.3 ProtocolSpec

Protocol-specific validated intent. It owns capabilities, minimum supported
sing-box version, generated inbound fragment, connection information, and
protocol-specific validation.

### 6.4 HostSnapshot

Read-only observed host state used during planning:

- platform and architecture;
- init system;
- installed artifact versions;
- occupied ports;
- process condition;
- relevant path ownership;
- public addresses and DNS observations when requested.

### 6.5 ExecutionPlan

An immutable, human-reviewable sequence of effects with warnings, required
privilege, validation steps, redacted previews, and rollback intent.

### 6.6 ApplyResult

Reports committed revision, validations, runtime refresh, rollback state, and
actionable errors. UI code never parses subprocess text to infer this result.

## 7. Architecture

```text
Textual TUI / machine CLI
          |
          v
Application use cases
          |
          +------ Protocol module
          +------ Planning module
          +------ Configuration transaction module
          |
          v
System seams
  StateStore       ConfigValidator       Runtime       TLS       ArtifactSource
     |                    |                  |           |              |
 filesystem          sing-box check    systemd/OpenRC  Caddy/ACME   GitHub/local
```

### 7.1 UI module

Responsibilities:

- navigation and focus;
- user input and accessible explanations;
- mapping user actions to application requests;
- rendering typed results;
- no subprocesses or direct filesystem mutation.

Textual screens are used for durable navigation and modal screens for explicit
confirmation. UI state is not the desired-state source of truth.

### 7.2 Application module

Responsibilities:

- user-facing use cases;
- orchestration of domain behavior and system seams;
- typed request/result objects;
- authorization of plan/apply transitions;
- no Textual widget knowledge.

### 7.3 Protocol module

Responsibilities:

- protocol capabilities and validation;
- desired-state representation;
- sing-box inbound generation;
- connection/share information;
- version compatibility.

Protocol implementations do not write files or restart processes.

### 7.4 Planning and transaction modules

Planning is pure: desired state plus HostSnapshot produces an ExecutionPlan.

Apply is effectful:

1. obtain an exclusive manager lock;
2. verify plan revision and host preconditions;
3. stage desired state and generated artifacts;
4. validate all staged sing-box/Caddy artifacts;
5. create a recovery backup;
6. atomically replace artifacts;
7. reload or restart required runtimes;
8. run postconditions;
9. commit the new applied revision;
10. roll back on any failure after step 5.

### 7.5 Runtime adapters

The runtime seam owns install/remove definitions, enable/disable, start/stop,
reload/restart, status, and diagnostic execution. systemd and OpenRC are real
adapters. Application code never calls their commands directly.

### 7.6 TLS adapters

The TLS seam supports Caddy-managed certificates, sing-box ACME where supported,
and operator-provided certificates. Self-signed credentials are allowed only for
protocols and workflows that explicitly communicate client verification needs.

### 7.7 Artifact adapters

The artifact seam owns version discovery, acquisition, integrity verification,
staging, replacement, and rollback. GitHub and local files are initial adapters.
The initial network trust and staging policy is fixed by ADR-0003: exact
immutable releases, mandatory SHA-256 verification, safe archive inspection,
and version self-verification occur before the later privileged replacement
seam. The TUI exposes this as an exact-version plan/confirm workflow. Blocking
metadata, download, and helper calls run in a Textual thread worker; UI updates
return to the application thread. Acquisition failures are reported before any
privileged request, while helper failures conservatively report an unknown host
activation result.

### 7.8 Privileged helper

ADR-0004 defines a single-shot, root-only, no-network helper with versioned JSON
requests and fixed root-owned paths. It exposes allowlisted domain operations,
not arbitrary commands or destinations. The interactive manager stays
unprivileged and relies on operator-managed sudo/doas authorization. Blocking
configuration validation, helper execution, runtime refresh, and health checks
run in a Textual thread worker; only progress and screen transitions run on the
UI thread, and duplicate confirmation is disabled while work is active.

## 8. Python project layout

```text
pyproject.toml
src/sb_manager/
  __init__.py
  __main__.py
  cli.py
  ui/
    app.py
    screens/
    messages.py
    theme.tcss
  application/
    manager.py
    requests.py
    results.py
  domain/
    installation.py
    profile.py
    plan.py
    errors.py
  protocols/
    registry.py
    reality.py
  config/
    generator.py
    transaction.py
  seams/
    state_store.py
    validator.py
    runtime.py
    tls.py
    artifacts.py
  adapters/
    filesystem_state.py
    sing_box_validator.py
    systemd_runtime.py
    openrc_runtime.py
    caddy_tls.py
    github_artifacts.py
tests/
  acceptance/
  behavior/
  contracts/
  integration/
  fixtures/
```

The layout may change only when tests show a real locality problem. Empty
directories and speculative modules are not created in advance.

## 9. Technology choices

- Python: typed CPython 3.10 through 3.14; the managed-host matrix and its
  verification levels are defined in `docs/SUPPORT.md`.
- TUI: Textual, selected for screen/widget navigation and headless Pilot tests.
- Tests: pytest, pytest-asyncio, and Textual `run_test()`.
- Static quality: Ruff formatting/linting and mypy strictness introduced
  incrementally at public seams.
- Runtime dependencies: kept minimal and locked.
- Packaging: private virtual environment under `/opt/sing-box-manager` for the
  first production packaging design.

PyInstaller one-file packaging is not the initial target because privileged
Linux deployments, musl/glibc builds, and noexec temporary directories require a
separate design.

## 10. Security and reliability requirements

- No TLS verification bypass for downloads.
- Integrity verification before installing artifacts when a trustworthy digest
  is available; otherwise the plan identifies the weaker trust level.
- Secrets represented by dedicated redacting value objects.
- No secrets in normal logs, exceptions, plans, or snapshots.
- Atomic writes use same-filesystem staging and replacement.
- Manager lock prevents concurrent applies.
- Apply checks that the desired-state revision has not changed since planning.
- External command arguments are arrays, never shell strings.
- No `shell=True`.
- Downloads, DNS, time, randomness, filesystem, and subprocess execution remain
  behind system seams.

## 11. Migration strategy

The new manager installs beside the Bash implementation during development but
uses a separate development state directory. There is no dual writing.

Migration sequence:

1. TUI shell and in-memory desired state.
2. VLESS Reality profile planning without host mutation.
3. Filesystem state adapter and atomic desired-state persistence.
4. Configuration generation plus `sing-box check` staging.
5. Transactional apply to an isolated integration root.
6. systemd runtime adapter and real-host opt-in testing.
7. Additional protocols one vertical slice at a time.
8. TLS, diagnostics, artifacts, import/adoption.
9. Replace the installed entry point after acceptance gates pass.

The Bash entry point is removed only after the Python implementation satisfies
the release acceptance criteria. It is not translated function by function.

## 12. Milestones

### M1 — Navigable product shell

- Empty-state dashboard.
- Profile list.
- Add-profile action opens protocol selection.
- Headless TUI acceptance test.

### M2 — First useful planning slice

- Guided VLESS Reality profile.
- Validated desired-state profile.
- Human-readable plan with no host effects.
- In-memory state seam.

### M3 — Safe local persistence

- Versioned state schema.
- Atomic filesystem store.
- Concurrent revision protection.
- Backup of desired state.

### M4 — Generated sing-box configuration

- Reality inbound generation.
- Staging directory.
- Real `sing-box check` integration seam.
- Semantic fixtures independent of JSON formatting.

### M5 — Transactional host apply

- Apply confirmation.
- Backup, commit, runtime refresh, postcondition, rollback.
- systemd adapter first; OpenRC contract follows.

### M6 — Sustainable protocol expansion

- Hysteria2, TUIC, AnyTLS, Shadowsocks, Trojan, VMess/VLESS transports.
- Each protocol delivered as a complete UI-to-config vertical slice.

Current implementation status (2026-07-16):

- complete vertical slices: VLESS Reality, Shadowsocks 2022, Hysteria2, Trojan,
  AnyTLS, TUIC, VLESS/VMess TLS WebSocket/gRPC;
- shared TLS strategies: the guided TUI supports sing-box 1.14 ACME certificate
  providers and an advanced root-managed certificate-file workflow constrained
  to `/etc/sing-box-manager/tls`;
- release integration: product-generated configurations for every supported
  protocol and the VLESS/VMess WebSocket/gRPC variants pass `sing-box check`
  against official 1.14.0-alpha.45;
- release harness: systemd/OpenRC service refresh and health checks require
  explicit host authorization;
- artifact acquisition: exact immutable official releases require an API
  SHA-256, safe archive staging, and staged core version self-verification;
- artifact activation: isolated-root tests and the real official artifact prove
  versioned distributions, an atomic relative `current` link, retained prior
  versions, and conflict-aware rollback;
- privileged artifact seam: a root-only, no-network, fixed-policy JSON helper
  re-copies and hashes incoming archives before using safe staging and atomic
  activation;
- privileged configuration seam: a SHA-256-only request selects a derived
  incoming filename and fixed config/core/runtime/lock policy; a strict
  manager-generated schema allowlist rejects extra sing-box capabilities and
  untrusted ACME/TLS paths before reusing validation, atomic commit, health, and
  rollback transactions;
- unprivileged client: explicit privileged apply mode stages deterministic
  mode-`0600` JSON, sends a SHA-256-only request through a non-interactive
  runner, strictly restores the typed transaction, and surfaces unknown host
  results without committing desired state;
- privileged installation: a root-only command installs fixed directories and
  exact no-arguments sudo/doas rules after a read-only plan and explicit
  `--confirm`, followed by native syntax validation; pinned Debian 12, Ubuntu
  24.04, and Alpine 3.20 container acceptance passes;
- persisted operator journey: reopening the TUI exposes an apply action for
  each draft and carries its stable profile ID plus current desired-state
  revision into the existing confirmation and background apply flow;
- host diagnostics: the dashboard performs a read-only systemd/OpenRC health
  observation in a Textual worker, reports applied/draft counts and the safest
  next action, and exposes typed diagnostics plus recovery guidance without
  parsing subprocess output in the UI;
- durable profile details: an applied profile can be reopened after restart to
  reconstruct its endpoint and share URI from persisted desired state through
  a read-only application query; stale concurrent selections produce a typed
  error screen instead of terminating the TUI;
- UI module depth: the complete core-update form, plan, confirmation, worker,
  result, and failure workflow now lives behind the single
  `CoreUpdateFormScreen(core_updater)` interface in `ui/screens/core_update.py`;
  `ManagerApp` owns only the navigation entry to that workflow;
- pending privileged work: live systemd/OpenRC execution on approved,
  recoverable target hosts;
- pending: the stable sing-box 1.14 release and execution of that harness on
  every supported host family.

## 13. Release acceptance criteria

- A new operator can create and apply the first profile without reading protocol
  documentation or editing JSON.
- Every destructive action presents a plan and explicit confirmation.
- Configuration validation failure leaves the prior revision running.
- Apply failure either restores the prior revision or reports that rollback
  failed with exact recovery instructions.
- Unit and behavior tests need neither root nor network.
- TUI acceptance tests drive public user actions with Textual Pilot.
- Runtime and artifact adapters pass shared contract suites.
- Supported protocols pass desired-state-to-config and connection-information
  behavior examples.
- No manager-owned file is written outside the transaction module.
- No systemd/OpenRC command exists outside its runtime adapter.
- No download exists outside an artifact adapter.
- The supported OS/core/protocol matrix is documented and tested at its stated
  level.

## 14. Deferred scope

- Caddy edge orchestration is deferred until after the first stable release.
  The first stable release uses sing-box-native ACME or root-managed certificate
  files; adding Caddy later requires its own artifact trust, transactional
  validation, runtime, and rollback design.
