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
│ F1 Help  a Add  p Profiles  n Network  s Settings  d Diagnostics  o Operations  q Quit │
└───────────────────────────────────────────────────────────────────────┘
```

The application is keyboard-first and mouse-capable. A persistent footer shows
only actions valid for the current screen.

The application exposes non-printable `F1` for help from every ordinary screen;
`?` remains a compatible help shortcut whenever no input control consumes it.
An explicitly confirmed operation keeps its non-returning progress screen
visible until a typed terminal result releases the shared navigation lock.
The root dashboard exposes `a` for the purpose-first add journey, `p` for the
profiles workspace, `n` for the read-only network workspace, `s` for Settings,
`d` for the diagnostics center, `o` for the operations workspace, and `q` for
exit.
Core lifecycle is not a direct root shortcut: the operations workspace
first explains available capabilities and safety, then opens the existing plan
workflow only after an explicit selection. `check_action()` hides dashboard-only
bindings whenever a child screen is active, so printable keys remain form input
and no shortcut bypasses an existing plan or confirmation. The help action is
idempotent, so `F1` or `?` cannot stack duplicate help screens. Returning with
`Esc` restores the previous screen, focused control, and entered value; `Tab`,
`Shift+Tab`, and `Enter` retain their normal focus and activation semantics. One
validated interface copy catalog owns the help hierarchy, key guide, context
explanation, and navigation-safety statement.

Worked example — unavailable operational capabilities:

> The operator opens Operations in a startup mode with no trusted core updater,
> service-log reader, or apply-history reader. The catalog supplies the title,
> task summary, host-effect boundary, section labels, and three explicit
> startup-mode explanations; no dead action is rendered. Opening the workspace
> plans nothing, reads nothing, and mutates nothing. When a capability is
> configured, its catalog action replaces only that explanation and opens the
> existing destination workflow after explicit selection.

Worked example — one mixed Network inventory:

> The operator presses `n` and sees a read-only desired-state projection with
> one enabled TCP profile on a fixed port, one paused UDP profile, and one draft
> UDP profile whose port will be selected only during apply. Catalog templates
> frame the page, counts, lifecycle labels, port policy, rows, public-address
> heading, and missing-address fallback. Profile names, transport identifiers,
> fixed ports, and declared public addresses remain literal non-markup evidence.
> Opening the workspace performs no DNS, socket, reachability, ownership, or
> firewall observation and offers no mutation control.

### 5.2 Dashboard

The dashboard answers five questions without navigation:

1. Is sing-box healthy?
2. How many profiles are active or unhealthy?
3. Is there an unapplied plan?
4. Are certificates or artifacts approaching maintenance?
5. What is the safest next action?

The dashboard always presents one stable scope statement before its evidence:
background checks are read-only and every mutation still requires a reviewed
plan plus explicit confirmation. The title, initial and terminal probe states,
profile counts, navigation, and reinspection controls render through the
validated interface copy catalog. Application recommendations remain a
separate typed decision module that returns only a stable recommendation
identity, optional structured values, and an optional stable action identity.
The Textual presentation adapter renders the recommendation summary and action
label through the same catalog; detailed readiness and certificate guidance
remains on its evidence screen instead of becoming unbounded Dashboard copy.

The dashboard layout has three stable zones: independently scrollable evidence,
a fixed contextual-action row, and a fixed workspace-navigation row. At the
supported compact size of 60 columns by 18 rows, both action rows remain visible
and directly clickable while longer status evidence scrolls without moving the
primary navigation off-screen. Empty and populated dashboards share this one
layout contract.

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
screen CSS selectors. The inventory states that it is read-only and that every
configuration change first presents a plan and requires explicit confirmation.
Its title, task summary, safety statement, empty guidance, lifecycle/port
labels, row template, and capability-aware actions render through the validated
interface copy catalog; protocol names remain stable product identifiers.
`Esc` from details returns to the workspace, while a
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
summary, recent apply result, and context-sensitive actions. The current
implementation presents it as a scrollable read-only view with an explicit
effect statement, stable profile identity and lifecycle status, server-address
and listen-port intent even when no share URI exists, and capability-aware
buttons that only open existing plan or confirmation workflows. Detail,
connection-disclosure, stale-read, and unexpected-read copy renders through the
validated interface copy catalog. Removal is always planned and confirmed: a
draft removal changes desired state only, while an applied removal
transactionally projects and applies all remaining profiles before desired
state is committed. The details catalog instance flows through the scope-aware
plan, confirmation progress, every typed terminal transaction outcome,
planning failure, and known or unknown operational failure. A missing host
transaction is treated as an unknown result rather than success and requires
configuration identity, service status, and apply-history inspection before
retry. Profile names, transaction diagnostics, and recovery instructions render
with markup disabled.

The complete details presentation is one deep module. Its external interface is
the immutable `ProfileDetailsCapabilities` dependency bundle, the details
screen, and the expected/unexpected read-error screens used by the composition
root. Connection disclosure, capability-aware lifecycle routing, planning-error
classification, and successful clone refresh remain local implementation
details. The root application owns report loading and top-level routing only;
it does not duplicate lifecycle policy or screen composition.

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
The details view passes one validated interface copy catalog through the edit
form, normalized plan, confirmation worker, terminal result, planning failure,
confirmation conflict, and unknown-result guidance. Authored interface copy is
selected only by semantic identity; profile values and typed diagnostic
evidence are rendered with markup disabled. The plan gives desired-state-only
updates a warning confirmation and live configuration transactions an error
confirmation, while both state explicitly that the preview has no effect.
Unexpected post-confirmation failure remains an unknown mutation result and
requires identity, service, and apply-history inspection before retry.

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
The profile-details catalog instance flows into expected planning rejection,
unexpected planning failure, the pause/resume plan, confirmation progress,
every terminal transaction outcome, and known or unknown operational failure.
Authored copy uses semantic identities; profile names, transaction diagnostics,
and recovery commands render with markup disabled. An unexpected planning
failure states that no operation ran, while an unexpected confirmed failure
claims no host or desired-state result and requires identity, service, and
apply-history inspection before retry.

Profile template cloning is desired-state-only and never applies or refreshes
sing-box. Its pure plan names the exact source revision, reusable non-secret
protocol/address/TLS/transport facets, and intentionally reset credentials,
listen port, and runtime status. The operator may edit only the proposed name,
then reviews the normalized source-to-target summary before explicit
confirmation. Confirmation rechecks the revision and source intent under the
shared mutation lock and appends one independent draft.
The profile-details catalog instance flows through the form, localized facet
list construction, review/edit loop, confirmation progress, stale-state
guidance, committed result, planning failure, and unknown desired-state result.
Profile names and typed application diagnostics render with markup disabled.
Revision conflict invalidates the reviewed confirmation; only returning to edit
and producing a fresh plan re-enables confirmation.
An unexpected planning failure states that no draft was created; an unexpected
confirmed failure states that the host was never modified while requiring the
operator to inspect Profiles before retrying the uncertain desired-state write.

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
exact protocol variants with stable rationale identities. Textual resolves each
rationale into its reason and tradeoff through the validated interface copy
catalog without recomputing policy, labels the first choice as a starting point
rather than an automatic decision, and states that no recommendation guarantees
connectivity. Selection opens the existing form and retains all normal plan and
confirmation steps. An explicit advanced action exposes every supported
protocol/transport variant without ranking. If the advisor fails unexpectedly,
the recovery page hides the exception and offers direct selection immediately;
the chosen variant still hands off to the existing guided form.

Wizard purpose remains ephemeral navigation intent. `ProtocolVariant` identifies
the exact form, including WebSocket/gRPC distinctions, but persisted profiles
continue to store protocol, TLS intent, and transport intent as the source of
truth.

The selected variant enters one deep profile-creation module. Its small external
interface consists of the variant-to-form catalog, the guided-form screen, and
the saved-draft apply-confirmation screen; form composition, application
validation rendering, plan preview, draft persistence boundaries, confirmed
apply, and terminal result policy remain local implementation details.

Application validation returns stable `ValidationIssueCode` identities plus
optional structured context instead of locale-authored messages. The injected
interface copy catalog renders every visible form, plan, persistence, progress,
typed result, and unknown-result message. Profile names, paths, transaction
diagnostics, and recovery instructions render literally with markup disabled.
Draft revision conflict terminates the stale plan; an unclassified draft-write
failure is an unknown desired-state result. After apply confirmation, duplicate
submission and return are disabled until one typed or unknown terminal result is
available. Success, rejection, rollback, operational failure, and unknown result
all provide one explicit dashboard action; `Esc` performs the same refresh and
never returns to a consumed plan or confirmation screen.

### 5.5 Network

Owns DNS policy, listening addresses, public address discovery, port inventory,
and firewall intent. Firewall mutation is deferred until an adapter and recovery
design are accepted.

The first network-workspace slice is a desired-state view, not a network probe.
The dashboard and contextual `n` shortcut open one snapshot showing each
profile's TCP/UDP listener transport, fixed or apply-time automatic port,
lifecycle state, and public address intent. One application-level network
inventory module owns protocol-to-transport mapping and also supplies the
deduplicated active endpoints consumed by listener diagnostics. This prevents
the UI and runtime diagnostics from drifting when protocols are added. Draft
and paused profiles remain visible as intent but never become expected active
listeners. Empty state and missing public addresses are explicit.

Opening the workspace performs no DNS lookup, socket inspection, reachability
test, public-IP discovery, or firewall read/write. The page contains no firewall
mutation control and states that limitation directly. Runtime evidence remains
in Diagnostics so desired state is never presented as proof of host state.

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

Worked example — bounded log evidence and an empty refresh:

> The operator opens Recent service logs from Diagnostics Center and sees the
> exact read-only bound, source identity, redaction count, and already-sanitized
> lines. The operator explicitly refreshes after recovery and receives a typed
> empty state rather than a blank page. Page framing, source/count templates,
> empty/unavailable fallbacks, loading/reloading states, and generic failure
> recovery come from the same injected interface copy catalog. Source labels,
> redacted lines, and typed diagnostics remain literal with markup disabled;
> refreshing never follows the journal or mutates the service.

Worked example — one failed apply record:

> The operator opens Apply History and sees the newest bounded record with its
> UTC start time, typed outcome, active-profile count, exact candidate SHA-256,
> bounded redacted diagnostics, and redaction count. The report conclusion and
> record evidence remain literal with markup disabled, while page framing,
> status labels, entry templates, unknown-result warning, empty/unavailable
> states, loading/reloading states, and generic failure recovery come from the
> same injected interface copy catalog through every navigation entry. Opening
> or refreshing history never retries an apply or infers success from desired
> state.

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

Worked example — catalogued healthy report:

> The operator opens Diagnostics after all checks have succeeded. The screen
> presents one healthy overall summary, one explicit “no action required”
> recommendation, stable condition markers for every check, and only the
> read-only drill-downs supported by the current application capabilities.
> Page framing, condition policy, recommendation templates, missing-evidence
> fallback, refresh/error guidance, and action labels come from the injected
> interface copy catalog. Report diagnostics remain literal, non-markup
> evidence. Rechecking never duplicates the prior report or exposes an
> exception raised before a typed report exists.

### 5.8 Settings

Owns language, color/accessibility preferences, update channel, paths, and
advanced behavior.

Settings exposes one safe per-user interface preference and one read-only
effective-settings snapshot. The dashboard and contextual `s` shortcut open the
workspace. Dark/light appearance changes use Textual's built-in themes and
apply immediately to the complete running application. A typed screen message
carries the selected scheme to the root application, which owns global theme
state and asks one application module to persist the complete preference
document. The preference file is separate from desired state, live
configuration, helper policy, and every host-managed path.

The JSON adapter writes schema v1 in the current user's XDG configuration
directory (`$XDG_CONFIG_HOME` when absolute, otherwise `~/.config`) or an
explicit `--preferences-file`. It uses same-directory atomic replacement,
mode `0600`, a 64 KiB read bound, and strict whole-document validation. Missing
storage means the default dark appearance and remains writable. Invalid JSON,
oversized documents, unsafe targets, unknown fields, and future schemas produce
a non-disclosing default-dark session; a manual color change still applies
immediately but must not overwrite the unreadable bytes. Settings shows whether
persistence is ready, loaded, saved, session-only, or unavailable without
rendering the underlying error.

For an unreadable regular file, Settings offers an explicit recovery path
instead of leaving the operator at a dead end. Opening it is read-only and
shows only the reviewed SHA-256, schema-v1 dark default, and effect scope.
Cancellation changes nothing. Confirmation runs off the UI thread, rechecks the
complete file identity, preserves the original bytes in a mode-`0600`,
hash-named archive, and only then atomically writes defaults. A changed file,
symbolic link, unsafe target, archive conflict, or I/O failure is never
overwritten. Unexpected post-confirmation failure is reported as an unknown
local preference result without exposing content or implying host impact.

The same page displays the startup choices actually used by production
composition: direct versus minimum-privilege helper access, systemd versus
OpenRC, desired-state path, direct live-config path or helper-fixed policy, the
active transaction directory, and the interface-preference path. It also states
that core versions are chosen manually and automatic updates are disabled.
These values are evidence, not editable copies of command arguments;
unsupported mutation controls are absent.

Chinese is the only offered UI language. The immutable interface copy catalog
uses semantic text identities, validates complete key coverage and exact
template placeholders at construction, and exposes only one rendering method
to screens. Complete migration units now cover Settings and every
preference-reset outcome, the Dashboard read-only shell and semantic
recommendation, Profiles inventory, profile details and credential disclosure,
the complete profile-edit journey, and profile pause/resume. Those migrated
screen ranges also include the complete profile-removal and profile-template-
clone journeys plus the purpose-first recommendation, recommendation-failure,
advanced direct-selection journey, and the complete trusted core-update
journey plus exact-fingerprint configuration adoption, and contain no
locale-authored text.
Settings states that
Chinese is fully supported and explains why other languages are withheld.
Additional locale choices must not appear until every remaining user-visible
string has moved into the catalog, so an operator never receives a partially
translated safety workflow. Additional accessibility preferences require their
own accepted behavior before extending the complete preference document.

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
results. The shared confirmation screen receives the journey's validated copy
catalog and renders the visible pre-confirmation Escape label through the
`common.cancel` identity, so all confirmed workflows expose one localized
navigation contract. Escape never implies cancellation of host or desired-state
work.

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
result, because it may have occurred before or after the atomic switch. The
application plan returns stable warning identities; the presentation adapter
renders form validation, warnings, immutable plan values, progress, terminal
evidence, and recovery policy through the validated interface copy catalog.
Typed diagnostics stay literal and use non-markup widgets.

### 7.8 Privileged helper

ADR-0004 defines a single-shot, root-only, no-network helper with versioned JSON
requests and fixed root-owned paths. It exposes allowlisted domain operations,
not arbitrary commands or destinations. The interactive manager stays
unprivileged and relies on operator-managed sudo/doas authorization. Blocking
configuration validation, helper execution, runtime refresh, and health checks
run in a Textual thread worker; only progress and screen transitions run on the
UI thread, and duplicate confirmation is disabled while work is active.

### 7.9 Interface preference adapter

The application preference module owns defaults, valid values, and
non-disclosing load/save outcomes behind one small interface. The production
JSON adapter and acceptance-test memory adapter make the storage seam real.
Textual knows only the typed snapshot and never parses JSON or filesystem
exceptions. The same interface owns hash-bound reset planning and explicit
confirmation, while the adapter owns byte identity, private archival, and
atomic replacement. Candidate inspection and confirmation-time revalidation
share the same 64 KiB document bound. Preference failure cannot disable host
inspection or management.

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
  dashboard actions currently safe to open; `a`, `p`, `n`, `s`, `d`, `o`, and
  `q` are gated by screen context and injected capability, while non-printable
  `F1` opens one non-mutating help page from focused forms and `?` remains a
  compatible non-input shortcut; catalog-backed help explains focus, activation,
  return, context, and confirmation safety without recursive screen stacking or
  hiding an in-flight confirmed-operation progress screen;
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
  backup without rewriting `.bak`, and presents revision, profile-count, and
  corrupt-archive evidence before an explicit return to a recomposed dashboard;
  startup classification, both exact fingerprints, confirmation, guarded
  progress, terminal outcomes, and recovery policy render through one validated
  interface copy catalog, while typed diagnostics and archive paths remain
  literal non-markup evidence;
  unsupported future schemas and inaccessible or invalid backups remain
  non-mutating guidance states; an unclassified startup inspection still
  renders a read-only TUI with every mutation entry disabled, while an
  unclassified review reinspection states that no operation ran; a typed
  precondition mismatch terminates the stale plan without offering direct
  retry, while a broader storage failure or unclassified confirmed failure
  reports primary, backup, and corrupt-archive results as unknown and forbids
  direct retry;
- purpose-first profile recommendation: adding a profile starts from four
  operator outcomes, returns three protocol variants with stable rationale
  identities from one pure application module, renders every reason, caveat,
  recovery action, and direct-choice label through the validated interface copy
  catalog, opens the existing guided form after selection, and retains an
  unranked advanced list of all ten supported variants; an unavailable advisor
  is non-disclosing and exposes the advanced path on the same recovery page;
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
  retry actions; when the full diagnostics center is unavailable, its dedicated
  drill-down module maps typed healthy/unhealthy state, missing-detail fallback,
  recovery labels, and step numbering through the validated copy catalog while
  rendering runtime diagnostics and adapter instructions literally with markup
  disabled;
- read-only network inventory: the dashboard and `n` open a dedicated workspace
  that distinguishes enabled, paused, and draft listener intent, explains
  TCP/UDP plus fixed/automatic ports and public addresses, performs no probe or
  firewall mutation, and shares one protocol-to-endpoint projection with
  listener diagnostics. Page framing, empty state, counts, lifecycle labels,
  port policy, row templates, public-address heading, and missing-address
  fallback come from the validated interface copy catalog while profile and
  address values remain literal non-markup evidence;
- persisted interface Settings: the dashboard and `s` open a dedicated
  workspace where dark/light appearance changes apply application-wide and are
  restored from one strict per-user schema-v1 JSON document; missing storage
  uses a writable default, while malformed, symbolic-link, and future-schema
  targets remain untouched and degrade to a non-disclosing session result;
  an explicit reset review shows only the exact fingerprint and defaults,
  rechecks bytes after confirmation, archives the original privately, rejects
  stale plans, and returns the running application to persisted dark mode;
  effective direct/helper, init-system, update-policy, preference, and host
  paths are disclosed from production composition without becoming editable
  host or desired-state controls;
- validated interface copy: Settings and the complete hash-bound preference
  reset journey render through one immutable simplified-Chinese catalog whose
  construction rejects missing, extra, or placeholder-incompatible entries;
  the Dashboard status shell now uses the same catalog for its application
  subtitle, contextual bindings, read-only scope, probe states, counts,
  semantic recommendation summaries, stable action labels, navigation, and
  retry controls; the application recommendation module no longer owns
  presentation-ready strings; the Profiles inventory workspace now renders its
  task hierarchy, read-only safety boundary, rows, and capability-aware actions
  through the catalog as well; profile details, endpoint intent, credential
  disclosure, and safe read failures now use the catalog too; the UI discloses
  that no additional locale is available until all remaining safety journeys
  have migrated;
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
  `CoreUpdateFormScreen(core_updater, copy_catalog)` interface in
  `ui/screens/core_update.py`; `ManagerApp` owns only capabilities, the shared
  catalog, and navigation into that workflow;
- UI presentation: the Textual stylesheet is isolated in `ui/theme.tcss` and
  included as package data, so layout changes do not require editing screen
  behavior and installed wheels retain the same rendering contract;
- existing-configuration adoption: an unmanaged live configuration is never
  parsed or silently replaced; the TUI reviews and confirms its exact
  fingerprint, desired state records that replacement precondition without host
  mutation, and direct/privileged apply rechecks it immediately before commit;
  loading, review, non-returning progress, typed rejection, result, and recovery
  copy comes from the validated interface catalog while fingerprints, revisions,
  and typed diagnostics remain literal non-markup evidence; unclassified
  planning failures state that no adoption occurred, an unclassified confirmed
  result preserves the no-host-mutation guarantee but treats the desired-state
  replacement precondition as unknown, and success clears the workflow stack
  before recomposing the dashboard;
- first-run readiness: one read-only application module classifies the
  configuration target, minimum-privilege helper, and configured core as ready,
  attention, or action-required; the dashboard prioritizes blocking setup work,
  exposes detailed guidance, supports an explicit recheck, and routes to core
  installation only after the helper is ready; the drill-down presentation
  catalog owns its title, aggregate conclusion, state markers, item framing,
  missing-detail fallback, next-step label, and recheck instruction, while the
  typed report's item titles, observations, diagnostics, and guidance remain
  literal non-markup evidence;
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

- An operator can discover keyboard navigation from `F1` without sacrificing
  printable form input; `?` remains available outside input focus. Dashboard
  shortcuts open only existing safe workflows, disappear outside their valid
  context, never bypass preview or confirmation, and cannot hide confirmed
  in-flight progress. Operations navigation groups core
  planning and read-only evidence without reading or mutating the host eagerly,
  and explains capabilities missing from the current startup mode.
- The dashboard contains profile counts and one recommendation, while the
  profiles workspace contains the complete inventory and capability-aware
  lifecycle entries. Cross-screen navigation uses typed action identity rather
  than selectors or translated labels; cancellation preserves context and
  lifecycle success refreshes the desired-state snapshot. Opening the inventory
  is explicitly read-only, and configuration changes remain plan-first and
  confirmation-bound. Profile details remain read-only, preserve endpoint
  intent without a share URI, hide credential-bearing links by default, and
  route every lifecycle entry through its existing plan or confirmation.
- The Network workspace separates declared network intent from observed host
  evidence, shows every profile's lifecycle/transport/port/public-address
  meaning, and cannot probe or mutate DNS, sockets, reachability, or firewalls
  merely by opening it. Listener diagnostics consume the same endpoint
  projection rather than maintaining a second protocol map.
- Settings applies the selected built-in theme across the running application,
  restores it from one strict per-user preference document, and reports
  session-only or unavailable persistence honestly. It discloses effective
  startup mode and paths without editing helper, desired-state, or host policy.
  Unreadable regular files have a hash-bound, archive-before-replace reset plan
  with explicit confirmation and stale-file rejection; unsafe targets remain
  manual recovery cases.
  No additional language is offered until a complete string catalog can
  preserve every safety workflow.
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
