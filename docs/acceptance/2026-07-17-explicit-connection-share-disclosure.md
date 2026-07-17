# Explicit connection-share disclosure acceptance — 2026-07-17

## Scope

This slice closes a disclosure gap in two Textual journeys: reopening an
applied profile and completing the first successful profile apply. The complete
share URI is credential-bearing even when the public endpoint is safe to show.

Primary test seam: confirmed Seam A, Textual `App.run_test()` plus Pilot.

## Accepted behavior

- The public server address and port remain immediately visible.
- The complete share URI is not mounted in a terminal control by default.
- The page explains that the link contains full access credentials and should
  be shown only in a private terminal.
- One explicit `显示一次连接链接` action mounts a selectable, read-only text
  area and removes the reveal action.
- The operator can immediately conceal the URI. Conceal removes the text and
  itself, and the same page offers no second reveal.
- Reveal state belongs only to the current page. The module performs no
  clipboard write and no desired-state or host mutation.
- Persisted profile details and successful first apply use the same presentation
  module, so disclosure policy cannot drift between the two journeys.

## TDD evidence

- Persisted-details red: the existing share-URI input was already mounted before
  any operator action (`1 failed`). Focused green: `1 passed`.
- Successful-apply red: the existing result screen still mounted the complete
  share-URI input immediately after apply (`1 failed`).
- Combined focused green after adopting the shared module: `2 passed`.
- Immediate-conceal red: the first revealed page had no conceal action
  (`1 failed`). Combined focused green after implementation remained
  `2 passed`.
- Full suite: `525 passed, 18 skipped`.
- Static gates: Ruff lint passed, all `240` files are formatted, mypy passed for
  `148` source files, and `git diff --check` passed.
- Release build produced both sdist and wheel; wheel inspection confirms
  `sb_manager/ui/connection_share.py` is packaged. Wheel SHA-256:
  `bb8a94d8a798b0e7ccbb07d8fcb6cd1c96d41d7a18cc91d718d29bc3ea10c0ab`.

## Release boundary

This change affects Textual presentation only. It does not alter protocol
material, connection URI generation, desired state, configuration projection,
privileged requests, host mutation, or package policy. Stable sing-box 1.14 and
authorized live systemd/OpenRC smoke tests remain external release gates.
