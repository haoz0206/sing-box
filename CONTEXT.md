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
