# Secret-free profile template cloning acceptance — 2026-07-17

## Scope

This record covers read-only template planning, unique-name policy, copied and
reset facet semantics, explicit desired-state confirmation, stale-plan
protection, the complete Textual details-to-dashboard journey, production
composition, package construction, and supported-distribution installation
policy.

## Evidence

- Full local suite: `430 passed, 18 skipped`.
- Focused cloning/application/TUI/composition tests: `11 passed`.
- Existing details/edit/pause/remove/first-profile regression set: passed.
- Ruff formatting: `208 files already formatted`.
- Ruff lint: `All checks passed`.
- mypy strict source check: `Success: no issues found in 127 source files`.
- Git whitespace check: passed.
- Real sing-box integration: `15 passed` against `1.14.0-alpha.45`.
- Source distribution and wheel build: passed.
- Package release install integration from the exact wheel: `1 passed`.
- Distribution policy acceptance using host networking for the configured
  host-loopback package proxy:
  - Debian 12 / sudo: passed;
  - Ubuntu 24.04 / sudo: passed;
  - Alpine 3.20 / doas: passed.
- Wheel: `dist/sing_box_manager-0.1.0-py3-none-any.whl`.
- Wheel SHA-256:
  `c719bec19b7c26156f1b7857c9d775a35043120bc44630165446651cf2b3db4c`.

The 18 skipped tests remain explicit opt-in external gates, chiefly live
systemd/OpenRC execution and release tests requiring separately configured
inputs.

## Accepted behavior

- Every profile detail view can open the template journey when cloning is
  available, regardless of draft, applied, online, or paused source state.
- Planning reads desired state without acquiring the mutation lock or changing
  the source profile.
- The default name uses `<source> 副本` and increments a suffix until it is
  unique.
- Operator-entered names are trimmed; blank and duplicate names remain on the
  form with actionable guidance and no desired-state mutation.
- The review identifies protocol, public server address, TLS strategy, and
  transport strategy as copied only when present.
- Authentication material, listen port, and runtime state are always shown as
  reset before confirmation.
- Confirmation is required before the shared manager mutation lock is
  acquired.
- Confirmation rechecks the desired-state revision, source profile, and name;
  stale or missing inputs do not create a draft.
- The copied non-secret source intent is compared independently of revision, so
  an external same-revision edit cannot silently change the reviewed template.
- The source profile and current live-configuration SHA-256 precondition remain
  unchanged.
- The new profile has a stable ID, `DRAFT` status, automatic port selection,
  no protocol material, and copied non-secret intent.
- No material generator, configuration applier, privileged helper, or runtime
  operation is invoked by cloning.
- A successful Textual result returns to a recomposed dashboard where the new
  draft is immediately visible and can enter the existing apply journey.
- Production composition uses the same `JsonFileStateStore` and `FileApplyLock`
  as other desired-state mutations.

## Remaining external release gates

- Repeat the real-core gate against upstream stable sing-box 1.14 when
  released.
- Run the authorized live systemd and OpenRC smoke harnesses on approved,
  recoverable hosts.

These gates continue to block calling the overall project a stable production
replacement, but they do not invalidate this interaction slice.
