# Host Readiness presentation acceptance — 2026-07-17

## Scope

Complete the presentation migration of the existing first-run Host Readiness
drill-down without changing its read-only probes, readiness priority, or trusted
core-update capability gate.

## Accepted behavior

- The injected interface copy catalog owns the page title, ready/action-required
  aggregate conclusion, ready/attention/action-required markers, item-title and
  next-step framing, missing-diagnostics fallback, and recheck instruction.
- The existing `HostReadinessReport` remains the application interface shared by
  Dashboard, Diagnostics, and the drill-down; this slice adds no adapter, port,
  probe, or host effect.
- Item titles, observations, diagnostics, and command guidance remain literal
  evidence. Bracketed values are displayed exactly and cannot become Textual
  markup.
- The core-update action remains visible only when the minimum-privilege helper
  is ready and the core requires action. Opening it still creates no plan and
  performs no activation.
- The screen contains no locale-authored Han text; its `Esc` binding uses the
  established common return copy.

## Test seam and evidence

- Confirmed Seam A: Textual `App.run_test()` and Pilot observe only mounted,
  user-visible behavior. The application report remains the existing typed seam.
- Red evidence: the injected marker catalog initially left the hard-coded
  `主机准备度` title visible.
- Red evidence: a marker-backed item initially rendered the hard-coded
  `[注意] [helper]` title and treated evidence as markup-enabled content.
- Focused Host Readiness behavior and Pilot tests: `10 passed, 87 deselected`
  in `2.87s`; the new dedicated Pilot file passes `2` journeys.
- Complete repository suite: `649 passed, 18 skipped` in `201.83s`.
- Ruff check passed; Ruff format reported `263 files already formatted`;
  strict mypy passed for `164 source files`; `git diff --check` passed.
- Source distribution and wheel built successfully. The wheel contains the
  updated `sb_manager/ui/copy_catalog.py` and
  `sb_manager/ui/screens/host_readiness.py`.
- Wheel SHA-256:
  `5fe4d51013fa6e0257d3e46c3bea65724abf352320577773e75a791ca187796b`.

## External release boundary

This slice changes Python presentation and tests only. It performs no network or
privileged host operation and does not replace the separately authorized live
systemd/OpenRC acceptance gate.
