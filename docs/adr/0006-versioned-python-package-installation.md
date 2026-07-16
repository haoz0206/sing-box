# ADR-0006: Install versioned Python package releases behind stable launchers

Status: Accepted  
Date: 2026-07-16

## Context

The Python rewrite previously assumed that a root-owned virtual environment
already existed at `/opt/sing-box-manager/venv`. That left initial deployment
outside the product and made `pip install --upgrade` an attractive but
non-transactional update path. A failed in-place upgrade could leave the TUI
and privileged helper on different or incomplete versions.

The authorization policy also named the helper inside that virtual
environment. A versioned package layout therefore needs a stable real helper
path without granting sudo/doas access to a symlink or generic interpreter.

## Decision

`sb-manager-install` owns Python package deployment:

1. Its default action is a read-only plan containing the local wheel path,
   package version, exact SHA-256, dependency source, versioned release path,
   stable launcher path, and atomic `current` link.
2. Confirmed installation requires root and rechecks that exact plan under an
   exclusive install lock.
3. The source wheel is opened without following symlinks, privately copied
   while hashing, and the copy is the only wheel visible to the environment
   builder.
4. Dependencies come either from an explicitly reviewed offline wheelhouse or
   from an explicitly authorized package index. The two modes are mutually
   exclusive.
5. Each package release is an immutable virtual environment at
   `/opt/sing-box-manager/releases/<version>-<wheel-sha256>/venv`.
6. A failed build removes only the inactive candidate. The active release and
   stable launchers continue to work.
7. Root-owned real launcher files live in `/opt/sing-box-manager/bin`. Each
   launcher dispatches its own allowlisted command name through
   `/opt/sing-box-manager/current/venv/bin` without a shell.
8. One relative, atomically replaced `current` symlink switches the TUI,
   package installer, policy installer, and privileged helper together.
9. sudo/doas policy authorizes only the stable real
   `/opt/sing-box-manager/bin/sb-manager-privileged` launcher with no arguments.

## Consequences

- Package upgrade failure cannot partially replace the active application.
- TUI and helper version selection changes together.
- Initial bootstrap still needs a trusted Python environment capable of
  starting `sb-manager-install`; that environment is temporary and is not the
  deployed runtime.
- Offline wheelhouse deployment remains the recommended trust mode. Index use
  is visible and requires an explicit flag.
- Package release retention and explicit rollback policy can be added without
  changing launcher or authorization paths.

## Rejected alternatives

### Upgrade one fixed virtual environment in place

Rejected because pip failure can leave a partially changed environment and
there is no atomic boundary between TUI and helper versions.

### Authorize a helper below the `current` symlink

Rejected because the privileged command path would itself be a symlink and
would not satisfy the existing trusted-helper policy.

### Run pip or Python through sudo/doas from the TUI

Rejected because it would turn the authorization rule into a general package
execution capability. Package installation remains a separate, root-confirmed
operator workflow.
