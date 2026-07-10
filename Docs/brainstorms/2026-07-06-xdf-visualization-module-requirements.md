# Requirements — XDF/BIN Library Phase 3: Visualization Module

**Date:** 2026-07-06
**Topic:** Plot `simoscal` tables (surface/line + heatmap/colormap) for inspection, the pre-flash review gate, and cross-bin comparison
**Status:** Requirements captured — ready for `/ce-plan`
**Related notes:** [[xdf-bin-library-requirements]] (Phase 1, the substrate), [[2026-07-06-xdf-export-module-requirements]] (Phase 2, source of `RenderedTable`)

## Problem

`simoscal` (Phase 1) reads/edits/writes calibration tables in physical units; Phase 2
exports them to CSV/xlsx. Neither lets you *see* a table's shape, and TunerPro — the
only current visual option — is Windows-only while the primary dev machine is a Mac.
Three needs are equally important and currently unmet without TunerPro:
inspecting/understanding a table, visually confirming an edit before it's flashed
(the human review gate called out in the Phase 1 plan), and comparing the same table
across two bins (e.g. stock vs. tuned) or before/after an in-session edit.

## Goals & Success Criteria

- Any selected table (or batch of tables) renders to static image files showing
  physical values, built on Phase 2's `RenderedTable`/`render_table()` — no
  reimplementation of axis-label/degenerate-shape logic.
- 2D tables (X and Y axes) get **both** a 3D surface plot and a 2D heatmap/colormap
  by default; the heatmap always overlays each cell's numeric value (TunerPro-style),
  regardless of table size.
- 1D tables (single axis) get a line plot. Scalar (1×1) tables are skipped — nothing
  to plot (Phase 2's export still covers them as label + value).
- Two tables of "the same" calibration item can be compared — regardless of whether
  they come from two different `.bin` files or from one `CalFile` before/after an
  edit — via one comparison function that doesn't care about that provenance.
- Table selection for plotting (single or comparison, batched) reuses Phase 2's
  `unique_tables()`-based model: symbol/title list, category name, or "all" — same
  API shape across the whole read side of `simoscal`.
- Output is static PNG files organized into folders by XDF category, mirroring
  Phase 2's category grouping.
- Library function(s) only, callable from a script — no CLI/GUI (consistent with
  Phases 1–2).

## Scope

### In scope (Phase 3)

- `plot_table(view)` (or equivalent): for a 2D `TableView`, produces a surface PNG
  and a heatmap PNG; for 1D, a line-plot PNG; for scalar, produces nothing.
- `compare_tables(view_a, view_b)` (or equivalent): takes two `TableView`s of the
  same table (matched by uniqueid/symbol) and produces:
  - **2D:** a 3-panel composite — bin A heatmap (top-left), bin B heatmap
    (top-right), delta heatmap (bottom-center). The top-row panels share one
    color/value scale (visual honesty); the delta panel gets its own independent
    diverging scale centered on zero. A matching 3-panel surface composite is
    produced by default; heatmap and surface comparison outputs are each
    independently toggleable off.
  - **1D:** a 2-panel composite — both lines overlaid on a shared scale (top),
    delta line below (bottom).
- Batch wrappers for both single-table and comparison plotting that accept the
  same symbol/category/"all" selection model as Phase 2's `export_tables()`.
- PNG output, one file (or file set) per table, grouped into category subfolders.
- Hard error (not a silent skip) if the two tables in a comparison have mismatched
  shapes/axes — consistent with the project's fail-loud ethos for anything that
  could mislead a reviewer.

### Out of scope (Phase 3)

- **Interactive/on-screen viewing** (rotating a 3D surface, hover tooltips, zoom).
  Static images only — matches the project's headless, script-driven pattern from
  Phases 1–2.
- **CLI or GUI.** Same decision as Phases 1–2.
- **Vector output formats** (SVG/PDF) — PNG only for now; not ruled out forever,
  just not building it now.
- **Comparison across more than two bins/revisions at once.**
- **Any write/edit path.** Purely a read-only consumer, same framing as Phase 2.

## Key Flows

1. **Single-table inspection** — select a table (or a whole category, or "all");
   get its surface + heatmap PNGs (2D) or line PNG (1D) saved under that table's
   category folder.
2. **Pre-flash review** — after editing a table (`.set()`), compare its pre-edit
   snapshot against its current in-memory state using the same comparison path as
   two-bin comparison (Flow 3), to visually confirm exactly what changed before
   saving/flashing.
3. **Two-bin comparison** — open two `CalFile`s (e.g. stock and current tune)
   against the same XDF; select a table or category; get the 3-panel (2D) or
   2-panel (1D) composite comparison PNG(s).
4. **Programmatic reuse** — call `plot_table`/`compare_tables` directly (no file
   selection wrapper) from a script or notebook, without hitting disk-selection
   logic.

## Acceptance Examples

- **AE1** — Plot a 2D table: a surface PNG and a heatmap PNG are produced; the
  heatmap shows every cell's numeric value overlaid; axis labels/units match the
  table's X/Y breakpoints (as already resolved by `RenderedTable`).
- **AE2** — Plot a 1D table: one line-plot PNG is produced; the x-axis matches the
  table's axis breakpoints/units, the y-axis is the table's Z units.
- **AE3** — Plot a scalar (1×1) table: no plot file is produced.
- **AE4** — Compare a 2D table across two bins: a 3-panel heatmap composite is
  produced (bin A / bin B / delta); the top two panels share one color scale; the
  delta panel uses an independent zero-centered diverging scale. A matching
  3-panel surface composite is also produced by default.
- **AE5** — Compare a 1D table across two bins: a 2-panel composite is produced
  (overlay on top with shared scale, delta below).
- **AE6** — Toggling the surface comparison off for a 2D pair leaves only the
  heatmap composite; toggling heatmap off leaves only the surface composite.
- **AE7** — Batch-plot an entire category by name: one file set is produced for
  every non-scalar table in that category, organized under that category's
  subfolder — mirrors Phase 2's category-export batching.
- **AE8** — Before/after comparison: capture a table's values before `.set()`,
  apply an edit, and compare pre- vs. post-edit state through the same
  `compare_tables` path used for two separate `.bin` files — no second `.bin`
  file required.
- **AE9** — Comparing two tables with mismatched shapes/axes raises a clear error
  naming the tables involved — never silently produces a misleading plot.

## Key Decisions

- **Static images only, no interactivity.** Matches the project's headless,
  script-driven pattern established in Phases 1–2 (and the user's general
  "render off-screen, save directly" convention elsewhere).
- **Architecture: build directly on `RenderedTable`/`render_table()` (Phase 2),
  no new abstraction layer.** Considered inserting a library-agnostic `PlotSpec`
  layer between `RenderedTable` and the plotting backend, to keep the backend
  swappable later — rejected as speculative abstraction for a need (an
  interactive/alternate backend) that doesn't exist yet.
- **2D tables get both surface and heatmap by default; heatmap always overlays
  cell values regardless of table size.** TunerPro fidelity was named explicitly
  in the Phase 1 origin plan ("colormap tables (heatmap-style, TunerPro-like)");
  scalars are skipped since there's nothing to plot.
- **Comparison is generic over two `TableView`s, independent of provenance.** One
  code path serves both "two different `.bin` files" and "before/after an edit
  in one session" — the function only needs two decoded views of the same
  calibration item, not two files.
- **Fixed comparison layouts:** 2D → 3-panel (A / B / delta), 1D → 2-panel
  (overlay / delta); "actual value" panels share a scale, delta panels get their
  own independent (diverging, zero-centered) scale. Both heatmap and surface
  comparison variants ship by default, each independently toggleable off.
- **Selection model reused from Phase 2.** Symbol/title list, category, or "all"
  (via `unique_tables()`) — for API consistency across export and visualization.
- **Output organization mirrors Phase 2.** One file (or file set) per table,
  grouped into category subfolders.
- **Mismatched-shape comparisons hard-fail.** Consistent with the project's
  fail-loud safety ethos — a plot is a review tool, so a misleading plot is a
  safety-adjacent failure mode, not just a cosmetic bug.

## Deferred / Out of Scope

- Interactive/on-screen plotting (rotate, hover, zoom).
- CLI/GUI front end.
- Vector output formats (SVG/PDF).
- Multi-bin (>2) comparison/overlay.
- Any write/edit path.

## Outstanding Questions

- **Plotting library (planning-time, non-blocking):** matplotlib is the evident
  default given static/headless output, but pin it down (and the new
  `pyproject.toml` dependency) during `/ce-plan`.
- **Before/after snapshot mechanics (planning-time, non-blocking):** Phase 1's
  `TableView.values` is lazily cached (U3); capturing a "before" snapshot ahead
  of `.set()` needs a concrete mechanism (e.g. copy the array before editing) —
  an implementation detail, not a product question.
- **Exact color palettes (planning-time, non-blocking):** which sequential
  colormap for value panels and which diverging colormap for delta panels is a
  design detail to settle during planning/implementation, not a blocker here.
