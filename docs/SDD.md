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
│ ? Help   a Add profile   p Profiles   d Diagnostics   o Operations   q Quit │
└───────────────────────────────────────────────────────────────────────┘
```

The application is keyboard-first and mouse-capable. A persistent footer shows
only actions valid for the current screen.

The root dashboard exposes `?` for help, `a` for the purpose-first add journey,
`p` for the profiles workspace, `d` for the diagnostics center, `o` for the
operations workspace, and `q` for exit. Core lifecycle is not a direct root
shortcut: the operations workspace
first explains available capabilities and safety, then opens the existing plan
workflow only after an explicit selection. `check_action()` hides dashboard-only
bindings whenever a child screen is active, so printable letters remain form
input and no shortcut bypasses an existing plan or confirmation. `?` opens one
read-only help screen; `Esc`, `Tab`, `Shift+Tab`, and `Enter` retain their normal
screen and focus semantics.

### 5.2 Dashboard

The dashboard answers five questions without navigation:

1. Is sing-box healthy?
2. How many profiles are active or unhealthy?
3. Is there an unapplied plan?
4. Are certificates or artifacts approaching maintenance?
5. What is the safest next action?

It shows aggregate profile counts, not the complete profile inventory or a row
of lifecycle buttons per profile. One visible `Manage profiles` action and the
contextual `p` shortcut open the dedicated profiles workspace. The empty state
keeps exactly one primary creation action; navigation to the empty workspace is
secondary and does not duplicate that call to action.

One application-level recommendation module owns that fifth answer. It consumes
the desired-state snapshot plus typed runtime, readiness, and certificate
evidence, including pending, unavailable, and failed probes. It returns one
explanation and at most one stable action identity. Textual renders the wording
and maps that identity to an existing add, review, diagnostics, or reinspection
workflow; it never parses guidance text or bypasses the destination's planning
and confirmation. While evidence needed for an applied profile is pending, the
primary action is withheld rather than guessed. Empty-state profile planning
remains available because it has no host effect.

Initial empty-state primary action: `Create your first profile`.

Runtime-health and host-readiness observations run independently in background
workers. An unexpected probe exception becomes a visible `无法检查` state rather
than a worker crash or a healthy inference. The dashboard never renders the raw
exception, keeps the affected detail action disabled, enables one read-only
reinspection action, and continues to recommend reinspection until a fresh
report succeeds. A failed retry remains in the same conservative state.

Managed-certificate maintenance is a third independent, read-only dashboard
observation. It reuses the same certificate-diagnostics module as the detailed
diagnostics center and presents only `正常`, `建议关注`, `需要处理`, or `无法检查`
plus an explicit recheck. Urgent certificate guidance outranks unapplied drafts;
attention guidance follows drafts. No certificate diagnostics, paths, DNS names,
or exception text are rendered on the dashboard.

Successful edit, removal, pause/resume, template creation, and desired-state
recovery return through one dashboard-refresh message. The root application
owns clearing stale reports, recomposing current desired state, and restarting
every configured observation. Lifecycle screens therefore do not know which
runtime, readiness, or maintenance inspectors exist, and a recomposed dashboard
cannot remain indefinitely at `正在检查` or reuse a pre-mutation conclusion.

### 5.3 Profiles

Profiles represent operator intent, not raw inbound JSON.

The profiles workspace owns the complete desired-state inventory and the entry
points for add, details, and draft apply. It receives one immutable snapshot and
only renders actions whose application capabilities were injected. Row buttons
are translated locally into one typed message carrying a stable action kind and,
when required, a stable profile ID; the root application never listens to child
screen CSS selectors. `Esc` from details returns to the workspace, while a
successful lifecycle mutation uses the shared refresh message to discard stale
child snapshots and return to a freshly recomposed dashboard.

List columns:

- display name;
- purpose;
- protocol;
- public endpoint;
- health;
- applied revision.

Profile detail shows connection information, share actions, generated artifact
summary, recent apply result, and context-sensitive actions. Removal is always
planned and confirmed: a draft removal changes desired state only, while an
applied removal transactionally projects and applies all remaining profiles
before desired state is committed.

A connection share URI is a credential, not ordinary profile metadata. Profile
details and successful first apply show the public endpoint and a disclosure
warning, but do not mount the URI in a terminal control by default. The operator
must explicitly reveal it for the current page; it appears in a read-only,
selectable text area with an immediate conceal action. Concealing removes the
URI and prevents another reveal on that page. No automatic clipboard write
occurs, and leaving the page discards the revealed presentation state.
Reopening either workflow starts hidden again.

Profile metadata editing starts with display name and public server address.
The stable identifier, protocol, credentials, TLS, and transport remain
unchanged. Every edit is normalized, revision-bound, previewed, and confirmed.
Draft edits and public-address-only edits update desired state without host
effects. Renaming an applied profile transactionally projects and applies the
complete configuration because the display name is present in generated
sing-box user records. Desired state advances only after host success.

Listening-port editing accepts a validated fixed port or an empty automatic
selection. Plans reject ranges outside 1–65535, ports declared by another
profile, and newly selected fixed ports unavailable on the host. Confirmation
rechecks fixed-port availability under the shared mutation lock; an automatic
applied edit chooses its actual port only inside that lock. Draft port changes
remain desired-state-only. An applied actual-port change reprojects and applies
the complete configuration, while changing only automatic/fixed policy for the
same actual port updates desired state without refreshing sing-box. Firewall
mutation remains outside this workflow. Automatic selection excludes ports
already declared by other profiles, and a successful result presents the
actual selected port to the operator.

Applied-profile availability is independent from its applied lifecycle status.
An online profile contributes one inbound to the complete managed projection;
a paused profile retains stable identity, credentials, endpoint, listen port,
and selection policy but contributes no inbound. Pause/resume plans are pure,
revision-bound, previewed, and explicitly confirmed. Confirmation rechecks the
reviewed profile under the shared mutation lock and reuses complete projection,
fingerprint preconditions, validation, atomic commit, runtime health checks,
and rollback. Fixed-port resume checks availability during preview and again
under the lock; automatic resume may choose a new actual port only under that
lock. Drafts use first apply, while paused edits and removals are desired-state
only.

### 5.4 Profile wizard

The wizard uses progressive disclosure:

1. Purpose: general use, low latency, restricted network, compatibility.
2. Recommended protocol: ranked choices with plain-language trade-offs.
3. Endpoint: port, domain, or automatic selection.
4. Credentials: generated by default; manual override under advanced options.
5. Transport and TLS: only choices supported by the selected protocol.
6. Review: human-readable plan, warnings, and one explicit apply action.

The implemented entry journey asks for general setup, mobile/low-latency,
restricted-network connection choices, or existing-client compatibility before
showing protocol terminology. A pure application advisor returns three ordered
exact protocol variants with one reason and one tradeoff each. Textual renders
that evidence without recomputing policy, labels the first choice as a starting
point rather than an automatic decision, and states that no recommendation
guarantees connectivity. Selection opens the existing form and retains all
normal plan and confirmation steps. An explicit advanced action exposes every
supported protocol/transport variant without ranking.

Wizard purpose remains ephemeral navigation intent. `ProtocolVariant` identifies
the exact form, including WebSocket/gRPC distinctions, but persisted profiles
continue to store protocol, TLS intent, and transport intent as the source of
truth.

### 5.5 Network

Owns DNS policy, listening addresses, public address discovery, port inventory,
and firewall intent. Firewall mutation is deferred until an adapter and recovery
design are accepted.

### 5.6 Operations

Owns core/Caddy versions, update plans, backup history, restore, start/stop,
restart/reload, and maintenance state.

The first operations-workspace slice is a capability-aware navigation module.
The dashboard and `o` shortcut open one non-mutating page rather than jumping
directly into a core update form. The page groups trusted core lifecycle from
read-only runtime evidence, and reuses the existing core-update, bounded service
log, and configuration-apply-history workflows. Merely opening the workspace
does not plan, probe, download, activate, or read logs/history. Each dependency
is invoked only after the operator selects its task. A capability absent from
the current startup mode is represented by an explanation and no clickable
control, so the page never advertises an action that cannot work.

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

The first diagnostics-center slice aggregates desired-state consistency, host
readiness, core/helper/config-target evidence, and runtime health behind one
read-only `inspect()` interface. It assigns one stable severity model, keeps
independent evidence when a probe fails, and chooses the highest-priority
operator action. The next slice reuses the active direct or privileged
configuration-target inspector to compare only its SHA-256 with the desired
state replacement precondition. It distinguishes an empty target, an untracked
existing target, a matching identity, a missing recorded target, external
drift, and an unavailable probe without reading configuration content. The
generated-configuration slice reprojects the same complete document used by
apply into disposable staging and runs the configured `sing-box check` adapter
without mutating the host. Projection failures, semantic rejection, and an
unavailable check remain distinct evidence; persisted protocol material is
redacted from validator diagnostics. Core readiness precedes this check in
recommendation priority so a missing core is never misreported as invalid
configuration. The public-domain slice extracts normalized, deduplicated server
addresses and TLS server names from the same desired-state snapshot. It skips
literal IP endpoints, resolves all domains inside one disposable worker with a
bounded total runtime, retains successful addresses beside per-domain failures,
and treats unresolved or unavailable DNS as attention rather than host mutation
failure. The service-log drill-down uses a separate read-only runtime-log seam
for bounded systemd journal or OpenRC syslog capture. One application disclosure
boundary reapplies the line bound, removes control sequences, caps line length,
redacts persisted protocol material plus common credential forms, and returns
typed available, empty, or unavailable results. Textual loads and refreshes the
default 200-line view in a worker with markup disabled; it never parses commands,
follows logs, escalates privileges, or changes the service. The apply-history
slice decorates the single configuration-apply seam used by create, edit,
pause/resume, and removal. Before delegating any host mutation it atomically
persists an `in-progress` record containing only an attempt ID, timestamps,
candidate SHA-256, active-profile count, and bounded diagnostics. A failed begin
blocks the apply; a failed final update preserves the durable `in-progress`
evidence without changing an already returned host result. The newest 100
records are retained in a private, strict-schema JSON file. Diagnostics classify
the latest typed outcome, while Textual presents the newest 20 with markup
disabled and without configuration documents or private material. If the
diagnostics center, service-log reader, or apply-history reader fails before it
can return a typed disclosure-safe report, Textual catches the top-level worker
exception, discards its text, shows generic retry guidance, and keeps the
read-only retry enabled. Typed unavailable reports still present their bounded,
already-sanitized evidence. The
listener-ownership slice
derives transport-specific expectations only from enabled, applied profiles,
then reads Linux TCP/UDP socket tables and visible process descriptors through
a dedicated read-only seam. Missing listeners and fully observed foreign owners
require action; inaccessible tables, descriptor permissions, process races, or
scan limits remain attention. A listener is attributed to sing-box only when
every observed inode has complete ownership evidence. Draft and paused profiles
do not imply runtime listeners, and Textual renders all dynamic diagnostic
content with markup disabled.

The managed-certificate slice derives deduplicated public-certificate targets
only from enabled, applied profiles. Operator-file targets stay below
`/etc/sing-box-manager/tls`; CertMagic ACME discovery stays below
`/var/lib/sing-box-manager/acme/certificates` and selects the latest matching
public leaf. Direct mode reads those fixed roots locally, while privileged mode
uses an exact helper request that cannot include a private-key path. Both paths
return only validity timestamps, DNS names, typed material state, and bounded
diagnostics. Expired, not-yet-valid, invalid, missing, or seven-day expiry
evidence requires action; thirty-day expiry and unavailable evidence require
attention. Independent targets remain visible even when one determines the
overall priority.

Actionable findings may carry one typed navigation action. The report exposes
only the action belonging to its highest-priority finding, and the Textual
screen renders it only when the destination application module and its safety
prerequisites are available. Initial actions open the existing configuration
adoption review and trusted core-update form. Opening an action never adopts,
downloads, activates, or otherwise mutates the host; the destination workflow
retains its own plan and explicit confirmation.

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

### 6.7 ApplyHistory

A durable, newest-bounded ledger of complete configuration-apply attempts. Each
entry records the candidate identity, active-profile count, start/completion
times, typed transaction outcome, and bounded redacted diagnostics. It never
stores the generated configuration, connection links, credentials, or private
keys. `IN_PROGRESS` is evidence that the final result is unknown, not a success
or failure inferred from desired state.

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

Every explicitly confirmed background operation uses one shared navigation
guard. Before confirmation, Escape returns without executing the plan. From
confirmation until a typed terminal result or classified error reaches the UI
thread, the originating screen remains mounted, its return binding is visibly
disabled, and progress text states that the operation cannot be left. Releasing
the guard is part of presenting every terminal path, including retryable
errors, unknown-result screens, same-screen success, and dismissed typed
results. Escape never implies cancellation of host or desired-state work.

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

If a confirmed mutation worker fails before returning one of these typed
terminal outcomes, Textual treats the complete effect as an unknown mutation
result. It discards the exception text, does not claim that live configuration,
runtime, artifacts, rollback, or desired state are unchanged, and directs the
operator to read-only identity, health, and history evidence before deciding
whether to retry. No automatic retry is offered.

Read-only startup inspection, recommendation, details, and action planning must
leave a usable TUI when no typed result exists. This includes new-profile,
edit, removal, pause/resume, template, adoption, and core-update planning.
Textual discards unclassified exception text, states which operation was not
executed, and directs the operator through an appropriate fresh read or
advanced fallback before retrying. Typed validation, stale-selection, and
port-unavailable evidence retains its existing actionable presentation.

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
activation result. An unclassified exception after core-update confirmation is
also non-disclosing and is conservatively presented as an unknown activation
result, because it may have occurred before or after the atomic switch.

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

Current implementation status (2026-07-17):

- keyboard-first contextual navigation: the Footer exposes help and only the
  dashboard actions currently safe to open; `a`, `p`, `d`, `o`, and `q` are gated by
  screen context and injected capability, while `?` opens a non-mutating help
  page that explains focus, activation, return, and confirmation safety;
- secret-free profile templates: profile details can plan a uniquely named
  draft from an existing applied, paused, or draft profile; protocol, public
  address, TLS strategy, and transport intent are reviewably reused while
  authentication material, listen port, and runtime status are always reset;
  explicit confirmation rechecks the desired-state revision under the shared
  mutation lock, commits desired state only, and returns to a recomposed
  dashboard without invoking host or material adapters; unclassified initial
  or review-plan failures are non-disclosing and safe to retry from a fresh
  detail read, while an unclassified confirmed worker failure reports the
  desired-state result as unknown without implying host effects;
- desired-state startup recovery: exact primary/backup byte snapshots are
  classified behind a storage seam; only a corrupt primary plus a
  current-schema readable backup produces a reviewable plan, explicit
  confirmation rechecks both SHA-256 values under the shared mutation lock,
  preserves the corrupt bytes under their full hash, atomically restores the
  backup without rewriting `.bak`, and recomposes the normal dashboard;
  unsupported future schemas and inaccessible or invalid backups remain
  non-mutating guidance states; an unclassified startup inspection still
  renders a read-only TUI with every mutation entry disabled, while an
  unclassified confirmed restore reports primary, backup, and corrupt-archive
  results as unknown and forbids direct retry;
- purpose-first profile recommendation: adding a profile starts from four
  operator outcomes, returns three reasoned and caveated protocol variants from
  one pure application module, opens the existing guided form after selection,
  and retains an unranked advanced list of all ten supported variants; an
  unavailable advisor is non-disclosing and keeps the advanced path reachable;
- complete vertical slices: VLESS Reality, Shadowsocks 2022, Hysteria2, Trojan,
  AnyTLS, TUIC, VLESS/VMess TLS WebSocket/gRPC;
- shared TLS strategies: the guided TUI supports sing-box 1.14 ACME certificate
  providers and an advanced root-managed certificate-file workflow constrained
  to `/etc/sing-box-manager/tls`;
- release integration: product-generated configurations for every supported
  protocol and the VLESS/VMess WebSocket/gRPC variants pass `sing-box check`
  against official 1.14.0-alpha.45;
- release harness: a read-only systemd/OpenRC acceptance plan prints recovery
  actions and an authorization value bound to the exact runtime and service;
  execution refuses an unhealthy precondition, refreshes once, and requires a
  healthy postcondition;
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
  results without committing desired state; the Textual apply, edit, removal,
  pause/resume, template-clone, and core-update workers also convert unclassified
  post-confirmation exceptions into non-disclosing unknown-result guidance
  rather than crashing or implying a rollback;
- privileged installation: a root-only command installs fixed directories and
  exact no-arguments sudo/doas rules after a read-only plan and explicit
  `--confirm`, followed by native syntax validation; pinned Debian 12, Ubuntu
  24.04, and Alpine 3.20 container acceptance passes;
- persisted operator journey: reopening the TUI exposes an apply action for
  each draft in a dedicated profiles workspace and carries its stable profile
  ID plus current desired-state revision into the existing confirmation and
  background apply flow; the dashboard retains counts and one safest next
  action instead of duplicating the full inventory;
- host diagnostics: the dashboard performs a read-only systemd/OpenRC health
  observation in a Textual worker, reports applied/draft counts and the safest
  next action, exposes typed diagnostics plus recovery guidance without parsing
  subprocess output in the UI, and converts unexpected runtime/readiness probe
  exceptions into non-disclosing, conservative states with explicit read-only
  retry actions;
- dashboard observation continuity: lifecycle success and desired-state
  recovery use one UI refresh request that clears prior evidence, recomposes the
  latest desired state, and restarts runtime, readiness, and managed-certificate
  workers; certificate status reuses the diagnostics-center application module,
  prioritizes urgent and attention guidance correctly, hides detailed evidence,
  and converts an unexpected probe failure into non-disclosing in-place retry;
- diagnostics center: an on-demand Textual workflow aggregates desired-state
  identity/material/fingerprint consistency, configuration target, minimum
  privilege helper, configured core, and runtime health through one deep
  read-only application interface; it isolates failed probes, prioritizes
  action-required over attention checks, presents one recommended action, and
  supports background rechecks without duplicating dashboard actions; a failure
  before any typed report exists is non-disclosing and retryable;
- live configuration identity: the diagnostics center reuses the access-mode
  selected configuration inspector to compare the target's read-only SHA-256
  with the single desired-state replacement precondition; empty, untracked,
  matching, missing, changed, and failed-probe states produce distinct typed
  results while corrupt desired state still leaves readiness/runtime evidence
  available;
- typed diagnostic actions: an untracked live configuration can open the exact
  fingerprint adoption review, while a missing core can open the trusted update
  form only after the privileged helper is ready; actions follow report
  priority, disappear when their destination is unavailable, and never bypass
  the destination workflow's plan or confirmation;
- generated configuration inspection: every production diagnostics run uses
  the complete managed projector, disposable staging, and the configured
  `sing-box check` validator; valid, invalid, unavailable, and unprojectable
  outcomes remain typed, protocol material is redacted from diagnostics, and a
  missing core retains priority as the operator's actual prerequisite;
- public domain resolution: one bounded read-only worker normalizes and
  deduplicates public server addresses plus TLS server names, skips literal IP
  endpoints, preserves mixed success/failure evidence, and reports invalid,
  unresolved, or unavailable DNS as attention without obscuring higher-priority
  configuration, core, or runtime actions;
- bounded service-log drill-down: the diagnostics center can open and refresh
  the latest 200 systemd journal or OpenRC syslog lines through an init-neutral
  read-only seam; adapter timeouts, command failure, missing access, and empty
  logs remain typed, while one application policy removes terminal controls,
  caps lines, and redacts both persisted and pattern-recognized credentials
  before Textual renders non-markup content; unexpected reader exceptions are
  discarded in favor of generic retry guidance;
- managed certificate diagnostics: enabled, applied TLS profiles produce
  deduplicated operator-file or CertMagic ACME public-certificate targets;
  direct and fixed-helper adapters expose only DNS names and timezone-aware
  validity metadata, enforce trusted roots and bounded reads, classify
  missing/invalid/expired/not-yet-valid/seven-day expiry as action-required,
  thirty-day expiry or unavailable evidence as attention, and preserve every
  target's evidence without reading private keys;
- listener ownership diagnostics: enabled, applied profiles produce exact TCP
  and UDP endpoint expectations; a dependency-free Linux `/proc` adapter joins
  IPv4/IPv6 socket inodes to visible process descriptors under hard scan limits,
  while missing, confirmed foreign, confirmed sing-box, and incomplete evidence
  remain distinct action-required, healthy, or attention outcomes;
- listening-port editing: profile details prefill the current port and accept a
  fixed value or an empty automatic selection; plans separate actual-port and
  selection-policy changes, reject desired-state/host conflicts, recheck under
  the shared lock, and transactionally reproject applied profiles while draft
  or policy-only changes remain desired-state-only; the TUI preserves exact
  validation, stale-port, transaction, rollback, and unknown-result guidance;
- profile pause/resume: profile details expose the current online/paused state
  and a revision-bound transition preview; confirmation preserves profile
  identity and material, transactionally reprojects the complete configuration,
  rechecks fixed ports or selects an automatic port under the shared lock, and
  commits desired state only after host success; transaction failures retain
  typed validation, precondition, commit, rollback, and recovery evidence,
  while unclassified worker failures discard exception text and present the
  complete live configuration, service, and desired-state result as unknown;
- durable profile details: an applied profile can be reopened after restart to
  reconstruct its endpoint and share URI from persisted desired state through
  a read-only application query; stale concurrent selections produce a typed
  error screen instead of terminating the TUI;
- explicit connection-link disclosure: persisted profile details and successful
  first apply show only the public endpoint plus credential-risk guidance by
  default; one shared Textual module mounts the complete URI as read-only text
  only after an explicit one-page reveal, permits immediate conceal without a
  second reveal on that page, performs no clipboard write, and naturally returns
  to hidden state when the page closes;
- UI module depth: the complete core-update form, plan, confirmation, worker,
  result, and failure workflow now lives behind the single
  `CoreUpdateFormScreen(core_updater)` interface in `ui/screens/core_update.py`;
  `ManagerApp` owns only the navigation entry to that workflow;
- UI presentation: the Textual stylesheet is isolated in `ui/theme.tcss` and
  included as package data, so layout changes do not require editing screen
  behavior and installed wheels retain the same rendering contract;
- existing-configuration adoption: an unmanaged live configuration is never
  parsed or silently replaced; the TUI reviews and confirms its exact
  fingerprint, desired state records that replacement precondition without host
  mutation, and direct/privileged apply rechecks it immediately before commit;
  unclassified planning failures state that no adoption occurred, while an
  unclassified confirmed result preserves the no-host-mutation guarantee but
  treats the desired-state replacement precondition as unknown;
- first-run readiness: one read-only application module classifies the
  configuration target, minimum-privilege helper, and configured core as ready,
  attention, or action-required; the dashboard prioritizes blocking setup work,
  exposes detailed guidance, supports an explicit recheck, and routes to core
  installation only after the helper is ready;
- managed core continuity: privileged mode uses
  `/opt/sing-box-manager/core/current/sing-box` by default for local material
  generation and readiness checks, matching the core activated by the root
  helper; direct development mode keeps the `PATH` default and both remain
  explicitly overridable;
- versioned Python deployment: `sb-manager-install` plans an exact local wheel
  identity and explicit dependency source, builds only from a private verified
  copy under an exclusive lock, and activates an immutable package release
  through one atomic `current` link; stable real launchers keep the TUI and
  privileged helper on the same selected release and give sudo/doas a fixed
  non-symlink command path; an explicit retained-release rollback plan rechecks
  current state and immutable tree trust under the same lock before atomically
  reactivating exactly the operator-selected release;
- profile lifecycle removal: profile details open a read-only, revision-bound
  removal plan; draft removal commits desired state under the shared mutation
  lock without host effects, while applied removal uses one shared complete
  configuration projector, the existing fingerprint precondition, validation,
  atomic commit, runtime health check, and rollback transaction before removing
  the profile from desired state; the TUI presents typed success, failure,
  rollback, and unknown-result states and recomposes the dashboard after success;
  removing the final applied profile produces a real-sing-box-validated quiescent
  document with zero inbounds and the fixed direct outbound;
- profile metadata editing: profile details expose a prefilled form for the
  display name and public server address without planning on navigation; the
  normalized plan identifies changed fields and separates desired-state-only
  address/draft changes from applied-name live transactions; confirmation runs
  under the shared mutation lock, rechecks the revision and reviewed content,
  reuses complete configuration projection and fingerprint preconditions, and
  presents typed validation, commit, rollback, recovery, and unknown-result
  states before recomposing the dashboard;
- pending privileged work: live systemd/OpenRC execution on approved,
  recoverable target hosts;
- pending: the stable sing-box 1.14 release and execution of that harness on
  every supported host family.

## 13. Release acceptance criteria

- An operator can discover keyboard navigation from `?`; dashboard shortcuts
  open only existing safe workflows, disappear outside their valid context, and
  never bypass preview or confirmation. Operations navigation groups core
  planning and read-only evidence without reading or mutating the host eagerly,
  and explains capabilities missing from the current startup mode.
- The dashboard contains profile counts and one recommendation, while the
  profiles workspace contains the complete inventory and capability-aware
  lifecycle entries. Cross-screen navigation uses typed action identity rather
  than selectors or translated labels; cancellation preserves context and
  lifecycle success refreshes the desired-state snapshot.
- An operator can use an existing profile as a template while the review makes
  copied intent and reset credentials/port/runtime state explicit; confirmation
  creates only a revision-bound draft and never changes the host.
- Corrupt desired state starts a bounded recovery page instead of terminating
  the TUI; restoration requires a valid current-schema backup, explicit
  confirmation, exact primary/backup hash rechecks, and preservation of the
  corrupt bytes.
- A new operator can create and apply the first profile without reading protocol
  documentation or editing JSON.
- Every destructive action presents a plan and explicit confirmation.
- Configuration validation failure leaves the prior revision running.
- Apply failure either restores the prior revision or reports that rollback
  failed with exact recovery instructions.
- Unit and behavior tests need neither root nor network.
- TUI acceptance tests drive public user actions with Textual Pilot.
- Recent service logs are bounded, control-cleaned, and credential-redacted
  before the TUI receives them; unavailable log access never changes the host.
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
