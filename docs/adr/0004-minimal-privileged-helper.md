# ADR-0004: Use a single-shot allowlisted privileged helper

Status: Accepted  
Date: 2026-07-16

## Context

The interactive manager must eventually write protected configuration and core
artifacts and ask the init system to refresh a service. Running the Textual UI,
network clients, parsers, and protocol planners as root would turn a broad
application into the privilege boundary.

The artifact pipeline already acquires and verifies archives without root and
can activate a versioned distribution behind one atomic `current` link. The
remaining boundary should expose that narrow behavior without becoming a
general command runner or filesystem API.

## Decision

The manager uses a single-shot privileged helper, installed as
`sb-manager-privileged`, with these constraints:

1. It is invoked through an operator-configured authorization mechanism such as
   sudo, doas, or polkit. The repository does not silently edit authorization
   policy.
2. It refuses to run unless its effective user is root.
3. It reads one versioned JSON request from standard input and emits one
   redacted JSON result. Unknown operations, fields, and schema versions fail.
4. It has no network client and never performs release discovery or download.
5. Operation destinations are fixed by root-owned policy in the helper. A
   request cannot choose an arbitrary installation root, lock path, service, or
   command.
6. The first allowlisted operation is `activate-core`. The request contains only
   an exact version, supported architecture, and lowercase SHA-256. The archive
   name is derived, not supplied.
7. The helper opens the archive from its fixed incoming directory with
   `O_NOFOLLOW`, requires a regular bounded-size file, copies and hashes it into
   a private working directory, and rejects a mismatch before parsing it.
8. Safe staging, version self-verification, versioned installation, locking,
   atomic activation, and conflict-aware rollback reuse the tested deep artifact
   modules. Private copies and transient staging are cleaned after the request.
9. Additional privileged operations require their own typed request, tests, and
   explicit allowlist entry. No operation accepts a shell string.

Initial fixed host paths are:

- incoming archives: `/var/lib/sing-box-manager/incoming`;
- private work: `/var/lib/sing-box-manager/work`;
- installed core: `/opt/sing-box-manager/core`;
- core lock: `/run/lock/sing-box-manager-core.lock`.

Internal tests may inject an isolated policy root. The installed command exposes
no flags or environment variables that override these paths.

## Consequences

- Network-facing and interactive code remains unprivileged.
- Authorization policy stays visible to and controlled by the operator.
- A compromised unprivileged process can request only allowlisted mutations and
  still must provide bytes matching an accepted digest.
- The helper package must be upgraded deliberately before new privileged
  behavior becomes available.
- Service/config mutation remains pending until its own request schema and
  transactional policy are designed.

## Rejected alternatives

### Run the entire manager with sudo

Rejected because the TUI, network stack, parsers, and every dependency would
execute with unrestricted host privileges.

### Expose a privileged shell-command proxy

Rejected because argument filtering is not a stable security boundary and would
allow application bugs to become arbitrary root command execution.

### Keep a privileged daemon running

Rejected for the single-host scope because it adds lifecycle, authentication,
socket ownership, and protocol-upgrade complexity without a current need.
