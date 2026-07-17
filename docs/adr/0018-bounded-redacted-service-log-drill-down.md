# ADR 0018: Bounded and redacted service-log drill-down

- Status: Accepted
- Date: 2026-07-17

## Context

The diagnostics center explains typed health and readiness findings, but an
operator investigating a failed start or rejected connection still needs the
underlying recent service evidence. Telling the operator to leave the product
and construct a `journalctl` or `logread` command breaks the guided workflow.
Showing an unrestricted journal is also unsafe: it can be very large, can
contain terminal control sequences, and may disclose persisted credentials or
previously unknown authentication values.

The capability must work for systemd and OpenRC without making Textual parse
subprocess output, granting the manager arbitrary file access, or turning a
read-only diagnostic action into a privileged host mutation.

## Decision

Add a narrow `RuntimeLogSource` system seam alongside the mutating `Runtime`
seam. It returns a typed `RuntimeLogCapture` containing source identity,
availability, bounded raw lines, and failure diagnostics. Keeping observation
separate prevents every apply-test runtime from acquiring an unrelated logging
method and lets the product report that logs are unavailable without affecting
service health checks.

Production adapters use argument arrays, never a shell:

- systemd invokes `journalctl --unit <service> --lines <limit> --no-pager
  --output short-iso --quiet` and normalizes the legacy no-entry marker to an
  empty capture;
- OpenRC invokes `logread` without follow flags, filters the finite syslog ring
  buffer by a case-insensitive literal service name, and retains only the
  requested matching tail locally because Alpine 3.20 BusyBox `logread` has no
  pattern or line-limit option.

Both commands have a five-second timeout. Requests must contain 1–500 lines;
the TUI asks for 200. OpenRC filtering never treats a customized service name as
a regular expression. Missing binaries, permissions, command failures,
timeouts, and an empty or non-matching log buffer remain distinct typed outcomes.
Output is decoded as UTF-8 with malformed bytes replaced so one damaged journal
record cannot abort the whole diagnostic workflow.

`ServiceLogService` is the single disclosure-policy boundary. It loads the
same desired-state snapshot used by the manager, derives authentication values
from every persisted protocol material type, and redacts exact matches. It also
redacts common password, token, authorization, credential, UUID, private-key,
and URI-userinfo forms that may not yet exist in desired state. ANSI escape
sequences and non-printing control characters are removed, every line is
limited to 4096 characters, and the application reapplies the requested line
bound even if an adapter violates it. Adapter diagnostics pass through the same
redactor.

The diagnostics center exposes “查看近期服务日志” as a secondary drill-down,
independent of its single prioritized recovery action. `ServiceLogsScreen`
loads and refreshes in a Textual thread worker, states the 200-line/read-only
policy, renders log text with markup disabled, reports the source and redaction
count, and keeps retry available after failure. It never follows the journal,
exports logs, changes the service, or invokes the privileged helper.

The same injected interface copy catalog flows into the screen from both
Diagnostics Center and Operations. It owns page framing, read-only scope,
source/redaction templates, typed empty and unavailable presentation,
missing-detail fallback, initial/repeated loading states, generic failure
recovery, and refresh copy. Source labels, sanitized log lines, and typed
diagnostics remain literal non-markup evidence and cannot select behavior.

## Consequences

- Operators can move from an actionable finding to recent evidence without
  memorizing init-system commands.
- The UI receives only bounded, sanitized, already-redacted text and typed
  availability; it contains no subprocess or parsing policy.
- systemd journal and OpenRC syslog differences remain inside adapters.
- OpenRC log availability is best-effort because a host may not run a compatible
  syslog ring buffer or may deny unprivileged `logread`; this is presented as an
  unavailable diagnostic, not as a broken runtime.
- The privileged helper allowlist is unchanged. Reading broader root-only logs
  requires a separate least-privilege and disclosure design.
- Exact-value redaction intentionally favors secrecy over perfect log fidelity.

## Rejected alternatives

### Put `journalctl` and `logread` calls in Textual

Rejected because the UI would own init-system selection, subprocess failure
classification, bounds, and security filtering.

### Add log reading to the existing `Runtime` protocol

Rejected because apply transactions require refresh, health, and recovery but
do not need log disclosure. Enlarging that seam would couple unrelated tests
and privileged runtime policy to an optional diagnostic capability.

### Read complete journal or log files

Rejected because it creates unbounded memory and disclosure risk, depends on
distro-specific file paths and rotation policy, and may require broad root file
access.

### Stream or continuously follow logs

Rejected for the first slice because it adds cancellation, backpressure,
screen-lifecycle, and secret-lifetime concerns. Explicit bounded refresh is a
complete troubleshooting workflow with a smaller security surface.

### Route logs through the privileged helper

Rejected because the current helper is a fixed-policy mutation boundary, not a
general root observation service. Expanding it would require a new request
schema, authorization policy, output cap, and information-disclosure review.
