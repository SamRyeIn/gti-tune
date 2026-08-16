# Interactive evidence plots (synced hover crosshair) — requirements

**Date:** 2026-08-01
**Status:** Brainstorm complete, ready for planning
**Follows:** `2026-07-12-analysis-plot-redesign-requirements.md`, which explicitly
deferred "Interactive (HTML) plots" as out of scope (line 131 of that doc). This
brainstorm picks that item back up.

## Problem

The analysis battery (`Code/simoscal/analysis/evidence.py`) writes static PNGs
for every evidence plot. On the stacked multi-panel plots — the log overview
(`_plot_overview`) and TC activity (`_plot_tc_activity`) — reading a value at a
specific moment means eyeballing the same x-position across up to six separate
panels by hand, which is error-prone and slow. On the per-check RPM plots
(boost, knock, lambda, rail pressure, turbo heat, wastegate, ignition) reading
the exact value of a specific pull's line at a specific RPM requires the same
kind of squinting against gridlines.

## Goals & success criteria

1. Hovering the mouse over any of the in-scope plots shows a vertical line at
   the cursor's x-position, drawn across every panel of that plot
   simultaneously.
2. The hover also shows a tooltip with the exact value of every trace at that
   x-position, in every panel.
3. This is additive: the existing static PNGs, the battery's checks, and
   `analysis_findings.{json,md}` content are completely unchanged.

**Verification:** rerun `python -m simoscal.analysis Logs/<Tune>_R<NN>` on a
real log folder (e.g. the next one produced by the tuning loop), open the new
`.html` files in a browser, and confirm: (a) the crosshair line appears across
all panels of a given plot on hover, (b) tooltip values match the source data
at that x-position, (c) the PNG outputs and `analysis_findings.json` are
byte-identical to a run before this change (except for the new HTML files
being present).

## Scope

**In — get an interactive HTML twin alongside the existing PNG:**

- Log overview plot (`_plot_overview`) — stacked time panels: rpm/gear, pedal,
  PUT/PUT SP, lambda/lambda SP, knock retard, IAT, with shaded WOT pull spans.
- TC activity plot (`_plot_tc_activity`) — stacked time panels: wheel slip,
  ignition intervention, wastegate intervention, torque req vs torque.
- The seven per-check RPM plots: `_plot_boost`, `_plot_knock`, `_plot_lambda`,
  `_plot_rail`, `_plot_turbo`, `_plot_wastegate`, `_plot_ignition`.

**Out:**

- Coverage plots (`_plot_coverage` / `analysis_coverage_*.png`) — unchanged,
  per the prior brainstorm.
- Any change to checks, thresholds, pull detection, or findings content.
- Replacing the PNGs — they stay, unchanged, for `log_review.md`/Obsidian
  embedding.
- Backfilling HTML for already-reviewed log folders (e.g. `BasicsGuide_R04`) —
  this applies to future battery runs only.
- Cross-linking the crosshair between separate plot files (e.g. syncing the
  overview plot's time cursor with a per-check RPM plot) — different x
  domains, out of scope.
- `Tunes/` compare PNGs (`simoscal.plot`) — different module, not evidence
  plots, untouched.

## Key decisions

1. **Library: Plotly.** Chosen over Bokeh (crosshair-across-figures is a
   first-class primitive there too, but Plotly is more standard and needs less
   custom wiring for tooltips) and over mpld3 + hand-written D3 (would reuse
   the existing matplotlib code but "linked crosshair across subplots" isn't a
   built-in mpld3 plugin, making it the most fragile option despite looking
   like the smallest diff). Plotly is Python-native, matching the project rule
   to keep all work in the language/tooling already in use.
2. **Output: HTML twin, not a replacement.** Each in-scope plot gets a
   `analysis_<id>.html` next to its existing `analysis_<id>.png`, viewed
   standalone in a browser. `log_review.md` continues to embed the PNGs as
   today; it is not required to link to the HTML files (may, but not a
   requirement of this feature).
3. **Sync scope: per-file, not global.** Each HTML file's crosshair syncs only
   its own panels (the overview's six time panels sync with each other; the
   TC activity plot's four time panels sync with each other; each per-check
   RPM plot syncs across whatever pull lines it draws in that one panel).
   Nothing links across separate HTML files.
4. **Hover content: line + tooltip values**, not just the visual line — the
   tooltip shows every trace's exact value at the hovered x-position, across
   all panels of that plot.
5. **Missing-channel degradation stays as-is** — a plot/panel that's skipped
   today for missing data is skipped in both its PNG and HTML form; no new
   error paths.

## Acceptance examples

- **AE1 — overview crosshair:** opening `analysis_overview_<stem>.html` and
  hovering over the rpm panel draws a vertical line at the same time-position
  in the pedal, PUT, lambda, knock, and IAT panels simultaneously, with a
  tooltip showing each panel's value(s) at that instant.
- **AE2 — TC activity crosshair:** same behavior on
  `analysis_tc_activity_<stem>.html` across its four panels.
- **AE3 — per-check RPM tooltip:** hovering `analysis_wastegate.html` at a
  given RPM shows a tooltip with both base and final wastegate position (and
  per-pull values) at that RPM.
- **AE4 — presentation-only:** rerunning the battery on a log folder produces
  `analysis_findings.json` byte-identical to a run before this change, with
  the PNGs also unchanged; only new `.html` files appear.
- **AE5 — graceful skip:** a plot that's skipped for missing channels (e.g.
  TC activity on a log with no wheel-speed channels) produces neither a PNG
  nor an HTML file — same skip behavior in both forms.

## Deferred / out of scope

- Backfilling HTML for historical log folders.
- Linking cursors across separate plot files or across the time/RPM x-domain
  boundary.
- Embedding interactive plots inside Obsidian notes (Obsidian's markdown
  preview doesn't execute arbitrary JS/iframes by default — would need a
  plugin; not pursued here).
- Any restyling of the coverage plots or `Tunes/` compare PNGs.

## Outstanding questions

- **Not blocking:** Plotly's default standalone HTML embeds its own JS
  (~3-4 MB per file unless a CDN-linked mode is used, which needs internet
  access to render). Whether to embed-JS (offline-viewable, larger files) or
  CDN-link (smaller files, needs internet) is an implementation choice to
  settle in `/ce-plan`, not a product decision — flagging here so it isn't
  missed.
