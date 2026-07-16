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
