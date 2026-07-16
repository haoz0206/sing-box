# Live configuration identity acceptance — 2026-07-17

Audited implementation: the repository state identified by the exact wheel
SHA-256 recorded below.

## Capability verdict

The diagnostics center can now distinguish an empty configuration target, an
untracked existing target, a target matching the desired-state replacement
precondition, a missing recorded target, an externally changed target, and an
unavailable identity probe. The check is read-only, compares only SHA-256
identities, never returns configuration content, and does not claim semantic
`sing-box check` validation.

The application loads desired state once per report. A corrupt state document
therefore suppresses only the comparison that lacks a trustworthy baseline;
host-readiness and runtime evidence continue independently.

## Repository-local evidence

- The complete pytest suite passes without root or network authorization: 326
  passed and 16 opt-in integration cases skipped.
- The diagnostics-center application behavior file passes 14 examples covering
  the complete identity decision table, desired-state corruption, and each
  independent probe failure.
- The production composition test proves that the diagnostics center receives
  the access-mode-selected direct or privileged configuration inspector.
- The existing Textual diagnostics journeys pass for on-demand loading,
  prioritized presentation, refresh after recovery, unexpected-failure retry,
  and the single dashboard diagnostics entry.
- Ruff formatting and lint checks pass for all 183 files.
- mypy passes for all 113 source files.
- `git diff --check` passes.
- The complete generated-protocol integration suite passes the real
  `sing-box 1.14.0-alpha.45 check`: 13 passed.
- The wheel and source distribution build successfully.
- The exact wheel SHA-256 is
  `33a0afb2cda36c8991ebd659a67f015e4a11ae779914c45a82eade7345d13107`.
  That wheel passes the isolated package-release install test and the pinned
  Debian 12, Ubuntu 24.04, and Alpine 3.20 package/authorization acceptance.

## Remaining release gates

1. Run the opt-in systemd smoke on approved, recoverable Debian 12 and Ubuntu
   24.04 hosts.
2. Run the opt-in OpenRC smoke on an approved, recoverable Alpine 3.20 host.
3. Repeat the real configuration and artifact suites after upstream publishes
   stable sing-box 1.14. The currently validated 1.14 artifact remains
   [1.14.0-alpha.45](https://github.com/SagerNet/sing-box/releases/tag/v1.14.0-alpha.45).

## Explicitly not proven by this check

- semantic validity of the live configuration;
- DNS reachability or domain ownership;
- certificate expiry;
- port ownership;
- apply history or redacted raw-log presentation.
