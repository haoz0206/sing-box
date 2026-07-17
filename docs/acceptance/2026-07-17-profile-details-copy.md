# Profile details copy acceptance — 2026-07-17

## Scope

Turn profile details into a clear read-only evidence and navigation hub: show
durable endpoint intent independently from client credentials, preserve the
one-page disclosure policy, and keep every lifecycle effect behind its existing
plan or confirmation workflow.

This slice includes the profile-details screen, nested connection-share panel,
stale-details error, and unexpected read-failure screen. Edit, availability,
clone, removal, and draft-apply screens remain separate catalog slices.

## Accepted behavior

- The details view is scrollable and always states that it is read-only; its
  lifecycle buttons open a plan or confirmation and do not mutate from this
  page.
- Name, protocol, applied/paused/draft status, server-address intent, and fixed
  or apply-time automatic listen-port intent remain visible even when no client
  connection URI can be generated.
- A complete share URI remains absent from the DOM until explicit reveal. It is
  read-only, can be hidden immediately, cannot be revealed again on the same
  page, and is hidden again after leaving the page.
- Details, lifecycle labels, credential warnings and controls, expected stale
  reads, and unexpected read failures render through the validated
  simplified-Chinese catalog.
- Dynamic profile and endpoint values render as non-markup content.
- Optional edit, clone, availability, and removal entries remain
  capability-aware. Their existing application seams, plans, confirmations,
  error handling, and refresh behavior are unchanged.
- Four optional lifecycle dependencies are grouped behind one immutable
  `ProfileDetailsCapabilities` parameter, keeping the screen interface small as
  more presentation dependencies are injected.

## Test seam and TDD evidence

Confirmed Seam A remains Textual Pilot public behavior.

- Catalog tracer red: the injected marker catalog was ignored and the title
  remained `配置详情` rather than `目录配置详情`.
- Catalog tracer green: the same journey rendered `目录配置详情` and the nested
  share panel rendered `目录显示连接链接` from the injected catalog.
- Effect-scope tracer red: `#profile-details-safety` did not exist.
- Effect-scope tracer green: the page states that it is read-only and lifecycle
  actions only open plan or confirmation steps.
- Endpoint-intent tracer red: draft details had no server-address or listen-port
  widgets.
- Endpoint-intent tracer green: a draft without a share URI displays
  `服务器地址：draft.example.com` and `监听端口：应用时自动选择`.
- Existing Pilot scenarios continue to prove one-page share reveal/hide,
  non-disclosing read failure, details return, and all four lifecycle handoffs.

No private method, screen field, or internal collaborator is a test seam.

## Quality evidence

- Details and lifecycle-entry focused gate: 96 passed.
- Full acceptance suite: 149 passed.
- Full repository suite: 583 passed, 18 skipped.
- Ruff check passed; all 259 files were already formatted.
- Mypy strict passed for 161 source files, and `git diff --check` passed.
- Literal audit found no simplified-Chinese text in the complete details/error
  implementation range or `connection_share.py`.
- The built wheel contains `sb_manager/ui/app.py`,
  `sb_manager/ui/connection_share.py`, and `sb_manager/ui/copy_catalog.py`;
  SHA-256:
  `49d50b785fd4f745b2a116a27409f594f3ec73a6df92014cc3f05ae1d3e1b300`.

## Next migration boundary

Migrate the profile-edit review and confirmation journey through the same
catalog, preserving revision binding, field validation, host-effect disclosure,
and unknown-result semantics.
