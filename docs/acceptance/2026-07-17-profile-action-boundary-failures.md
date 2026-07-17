# Profile action boundary-failure acceptance — 2026-07-17

## Scope

This slice closes unclassified-failure gaps around profile-detail actions. It
covers read-only planning for edit, removal, pause/resume, and template clone,
including clone review after a name change. It also covers the confirmed
desired-state-only clone worker. Application interfaces and host transactions
remain unchanged.

## Accepted behavior

- Existing typed validation, no-change, stale-selection, missing-profile, and
  unavailable-port results retain their actionable presentation.
- An unclassified planning exception never leaves the event handler failed and
  never renders the exception text.
- Planning-failure screens truthfully state that no operation was executed and
  direct the operator through a fresh list/detail read before retrying.
- Initial template planning and name-review planning use the same safe policy.
- An unclassified exception after template confirmation does not claim that a
  draft was or was not created; desired state is presented as unknown.
- Template creation still truthfully states that live configuration and service
  state are outside that desired-state-only workflow.
- No automatic or one-click retry is offered.

## Verification evidence

- Red evidence: each planning exception escaped its Textual event handler,
  exposed the private test token in the traceback, and left the prior screen
  active.
- Red evidence: the confirmed clone exception produced
  `textual.worker.WorkerFailed` and exposed the private test token.
- New focused boundary journeys: `6 passed`.
- Complete edit, removal, availability, and clone acceptance files: `41 passed`.
- Full test suite: `517 passed, 18 skipped`.
- Ruff format reported `239 files already formatted`; Ruff lint passed.
- Strict mypy passed for `147 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully.
- Wheel SHA-256:
  `4b39092da788ac864291c4a5c8ed9cc57b5010b16f3c63f3d3b5b397c0fcbd46`.

## Release boundary

No protocol, dependency, package policy, privileged request, configuration
projection, transaction, or runtime adapter changed. Stable sing-box 1.14 is
still unreleased as of this acceptance run, and authorized live systemd/OpenRC
smoke tests remain external release gates.
