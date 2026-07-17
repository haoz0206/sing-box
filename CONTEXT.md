# Sing-box Manager

This context describes how an operator's desired proxy service relates to the
configuration currently active on one managed host.

## Language

**Desired state**:
The versioned set of profiles and host intentions owned by the manager.
_Avoid_: UI state, generated JSON

**Live configuration**:
The sing-box configuration currently present at the host's configured target.
_Avoid_: Desired state, draft

**Managed configuration**:
A live configuration whose exact identity was produced and recorded by the
manager after a successful apply.
_Avoid_: Any syntactically valid sing-box configuration

**Unmanaged configuration**:
A live configuration whose identity is not proven by the manager's desired
state, regardless of who originally created it.
_Avoid_: Legacy configuration, foreign configuration

**Adoption**:
An operator-approved transition that authorizes replacement of one specifically
observed unmanaged configuration. Adoption does not import profiles or mutate
the live configuration.
_Avoid_: Import, automatic migration

**Import**:
Conversion of external configuration semantics into manager-owned desired
state. Import is distinct from adoption and may be unsupported for some input.
_Avoid_: Adoption, file copy

**Replacement precondition**:
The recorded identity that the live configuration must still have immediately
before an apply may replace it.
_Avoid_: Backup, confirmation

**Package release**:
One immutable, root-owned Python environment identified by the manager package
version and exact source-wheel SHA-256.
_Avoid_: Development virtual environment, in-place pip upgrade

**Active package release**:
The package release selected by the root-owned atomic `current` link. Stable
launchers resolve all manager commands through this one selection.
_Avoid_: Latest downloaded wheel, whichever command appears first in PATH

**Retained package release**:
An inactive immutable package release still present below the root-owned
`releases/` directory and eligible for an explicit rollback plan.
_Avoid_: Previous version, backup venv

**Package rollback**:
An operator-confirmed atomic activation of one exact retained package release.
It never guesses which release the operator intended.
_Avoid_: Downgrade install, manual symlink edit

**Profile removal**:
An operator-confirmed lifecycle transition that removes one exact profile from
desired state. Removing a draft changes desired state only; removing an applied
profile first transactionally applies the complete remaining managed
configuration and commits desired state only after host success.
_Avoid_: Delete inbound JSON, forget profile, unlink configuration

**Profile edit**:
An operator-confirmed, revision-bound change to the supported mutable intent of
one stable profile. Metadata-only changes may update desired state, while any
field that changes generated server configuration uses one complete live
transaction.
_Avoid_: Patch generated JSON, recreate profile, rotate credentials

**Listen port edit**:
A profile edit that selects one validated fixed port or requests automatic
selection. Draft changes remain desired-state-only. Changing the actual port of
an applied profile rechecks availability under the shared lock, reprojects the
complete configuration, and commits desired state only after host success.
Changing only automatic/fixed policy for the same actual port does not refresh
the service.
_Avoid_: Firewall mutation, editing generated inbound JSON, unchecked port swap

**Profile availability**:
Whether one previously applied profile currently participates in the complete
managed configuration. An active profile contributes an inbound; a paused
profile retains its stable identity, credentials, endpoint, and port intent but
does not contribute an inbound. A confirmed transition commits desired state
only after the complete host transaction succeeds.
_Avoid_: Draft status, profile removal, stopping the whole sing-box service

**Profile purpose**:
The operator outcome used only to rank choices at the start of the add-profile
journey: general setup, low latency, restricted-network connection options, or
existing-client compatibility. It is ephemeral navigation intent and is not
manager desired state.
_Avoid_: Protocol, persisted profile metadata, detected network condition

**Protocol variant**:
One exact guided form the operator can open. It includes a transport distinction
such as VLESS TLS WebSocket versus VLESS TLS gRPC, while persisted desired state
continues to use protocol, TLS intent, and transport intent separately.
_Avoid_: Protocol kind alone, generated inbound type

**Protocol recommendation**:
An ordered, read-only shortlist for one profile purpose. Every choice states a
reason and a tradeoff, never applies automatically, and does not guarantee
connectivity or suitability for a particular network.
_Avoid_: Network probe result, automatic protocol selection, compatibility proof

**Diagnostics center**:
One read-only, prioritized report that combines manager desired-state
consistency, host readiness, and runtime health into stable checks and one
recommended operator action. A failed probe becomes its own check and does not
erase independent evidence.
_Avoid_: Raw log dump, runtime status page, readiness wizard

**Generated configuration inspection**:
A read-only projection of one desired-state snapshot into a disposable complete
sing-box document followed by the configured semantic validator. It reports
valid, invalid, or unavailable evidence without applying the document, and
redacts persisted protocol material from validator diagnostics.
_Avoid_: Live configuration identity, apply dry-run, displaying generated JSON

**Public domain resolution**:
A bounded, read-only DNS observation of normalized public server addresses and
TLS server names in one desired-state snapshot. Repeated domains resolve once,
literal IP endpoints are counted without DNS, and partial failures preserve
successful address evidence. Resolution proves reachability through local DNS,
not that an address belongs to the managed host.
_Avoid_: Public IP ownership proof, ACME certificate status, connectivity test

**Managed certificate condition**:
The read-only validity state of the public leaf certificate selected by an
enabled, applied profile's TLS intent. It distinguishes healthy, expiring,
expired, not-yet-valid, missing, invalid, and unavailable evidence without
reading or returning private-key material.
_Avoid_: ACME issuance attempt, TLS reachability, private-key validation

**Listener ownership**:
Conservative process evidence for the exact TCP or UDP endpoint expected by an
enabled, applied profile. A listener belongs to sing-box only when every
observed socket inode has complete ownership evidence.
_Avoid_: Port availability, service health, listener existence alone

**Live configuration identity**:
The read-only SHA-256 observation of the configured sing-box target, compared
with the exact replacement precondition recorded in desired state. It can prove
that the target is absent, untracked, unchanged, missing, or changed without
returning configuration content.
_Avoid_: Generated configuration validation, imported configuration, runtime health

**Diagnostic action**:
Optional typed navigation from the report's highest-priority finding into an
existing safe review or planning workflow. Opening the destination never
confirms or performs the underlying mutation, and the action is unavailable
when its prerequisite application module is absent or not ready.
_Avoid_: Shell command button, parsing guidance text, bypassing confirmation

**Apply history**:
A durable, newest-bounded record of exact configuration-apply attempts. An
`in-progress` entry means the final host result is unknown and requires
inspection; it never implies success from desired state alone. Entries retain
only candidate identity, counts, typed outcome, timestamps, and bounded redacted
diagnostics.
_Avoid_: Desired-state revision history, generated configuration backup, raw log

**Contextual shortcut**:
A keyboard navigation action that is visible and active only when its existing
destination workflow is currently safe to open. It never bypasses that
workflow's plan, confirmation, or host-effect policy, and printable keys remain
available to focused form fields outside the shortcut's context.
_Avoid_: Global command execution, hidden mutation, shell alias

**Operations workspace**:
A capability-aware navigation space for core lifecycle planning and read-only
runtime evidence. Opening it performs no probe or mutation; each available tool
starts only after an explicit selection, while unavailable tools remain visible
as explanations rather than dead controls.
_Avoid_: Dashboard miscellaneous buttons, direct mutation shortcut, empty menu

**Profiles workspace**:
The task-oriented view of one desired-state snapshot that owns the complete
profile inventory and its lifecycle entry points. The dashboard exposes only
profile counts, one safest recommendation, and navigation into this workspace;
ordinary return preserves the workspace context, while lifecycle success
refreshes the snapshot through the dashboard. The inventory itself is read-only
and states that every configuration change first presents a plan and requires
explicit confirmation; its locale-specific status, port, row, and action copy
comes from the validated interface copy catalog.
_Avoid_: Full profile rows on the dashboard, cross-screen CSS event routing,
stale inventory after mutation, inventory buttons presented as immediate host
effects

**Profile details**:
The scrollable, read-only view of one stable profile identity, lifecycle state,
server-address intent, listen-port intent, and optional client connection
information. A credential-bearing share URI stays hidden until an explicit
one-page reveal and can be hidden permanently for that page. Capability-aware
lifecycle buttons only open existing plan or confirmation workflows; they do
not mutate desired state or the host from the details view. Locale-specific
details, disclosure, and read-failure copy comes from the validated interface
copy catalog.
_Avoid_: Live runtime evidence, always-visible share URI, lifecycle mutation
performed by the details screen, missing endpoint intent when no URI exists

**Network inventory**:
A read-only projection of one desired-state revision into profile lifecycle,
listener transport, selected or pending port, public address intent, and the
deduplicated listener endpoints expected to be active. It performs no DNS,
socket, reachability, public-IP, or firewall observation; those remain separate
evidence seams.
_Avoid_: Runtime listener observation, port availability result, firewall rule,
network scan

**Interface preferences**:
The current Unix operator's versioned, local TUI choices, initially limited to
the application-wide dark/light color scheme. A valid choice is restored on
the next process start. Missing storage uses the default; unreadable, unsafe,
or future-schema storage is preserved and degrades to a usable session without
changing desired state or the managed host.
_Avoid_: Host setting, desired state, live configuration, automatic repair

**Interface preference reset**:
An operator-confirmed replacement of one exact unreadable, regular preference
document with schema-v1 defaults. Review exposes only SHA-256 and effects;
confirmation rechecks the bytes, preserves them in a hash-named private
archive, and never changes desired state or the managed host.
_Avoid_: Automatic repair, deleting unknown preferences, schema downgrade

**Interface copy catalog**:
The immutable, locale-specific set of semantic text identities and templates
used by one completely migrated TUI journey. A catalog must cover every
declared identity with the exact required placeholders before construction;
an additional locale is not offered until every user-visible safety journey is
catalogued.
_Avoid_: Screen-local translation dictionary, partial locale, translated domain key

**Effective settings**:
The disclosure-safe startup choices actually used by the running manager,
including host-access mode, init system, desired-state path, live-config policy,
transaction directory, and interface-preference path. They are read-only
evidence, not editable copies of CLI arguments.
_Avoid_: Proposed setting, raw argv, mutable desired state, helper policy editor

**Dashboard recommendation**:
The single safest next step selected from desired state and independent runtime,
readiness, and certificate evidence. It carries a stable recommendation
identity, optional structured values, and a stable action identity when the
destination capability exists. The presentation adapter renders both identities
through the validated interface copy catalog, so application policy neither
produces translated guidance nor parses it to choose navigation. Pending
evidence may withhold an action; opening one never bypasses an existing plan or
confirmation.
_Avoid_: Presentation-ready application strings, status text parsed by the UI,
a list of equally primary buttons

**Probe failure**:
An unexpected inability to complete a read-only dashboard observation. It is a
conservative, retryable UI state: the original exception is not disclosed, no
healthy conclusion is inferred, and the safest next action remains reinspection
until a fresh report succeeds.
_Avoid_: Unhealthy runtime result, failed host mutation, ignored worker exception

**Unexpected read failure**:
A read-only TUI workflow failed before its application interface could return a
typed, disclosure-safe report. The screen shows generic retry guidance and never
stores or renders the exception text; typed unavailable reports continue to show
their already-sanitized evidence.
_Avoid_: Probe finding, typed unavailable report, raw exception presentation

**Unknown mutation result**:
A confirmed effectful workflow failed before returning a typed terminal result,
so the TUI cannot prove which live configuration, runtime, artifact, or desired
state is current. It hides the exception, makes no safety claim, and requires
read-only identity, health, and history checks before any retry.
_Avoid_: Typed transaction failure, assumed rollback, automatic retry
