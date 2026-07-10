# Plan — Phase 3: Visualization Module (surface / heatmap / line PNGs + comparison)

**Date:** 2026-07-06
**Type:** feat
**Origin:** [[2026-07-06-xdf-visualization-module-requirements]] (`Docs/brainstorms/2026-07-06-xdf-visualization-module-requirements.md`)
**Status:** ✅ **Complete** — U1–U5 all shipped (2026-07-06). `simoscal/plot.py`
with `plot_table`/`compare_tables`/`plot_tables`/`compare_bins`/`TableMismatchError`;
45 new tests (`test_plot.py` 35 + `test_acceptance_plot.py` AE1–AE9, 10); full
suite 212 passed. `matplotlib>=3.7` added to `[project.dependencies]`. Open
question resolved: default surface angle `elev=30, azim=-120` validated visually
against real tables (`ID_PORT_SP`, `IP_PUT_MAX_CAP_H_DIAG`) — relief reads well,
kept as default.

## Summary

Add a `simoscal.plot` module that renders any selection of calibration tables to
static PNG images — 3D surface + value-overlaid heatmap for 2D tables, line plot
for 1D tables, nothing for scalars — plus a provenance-agnostic `compare_tables`
that produces fixed composite comparison images (3-panel for 2D, 2-panel for 1D).
It builds directly on Phase 2's `RenderedTable`/`render_table()` (the table→grid
layer) and reuses Phase 2's `select_tables()` selection model, so the read side
of `simoscal` keeps one consistent selection API across export and visualization.
Read-only and entirely additive — no changes to the Phase 1 read/edit/write/
checksum paths.

## Problem Frame

See [[2026-07-06-xdf-visualization-module-requirements]] for the full statement.
In short: `simoscal` can read/edit tables and export them to CSV/xlsx, but there
is no way to *see* a table's shape without TunerPro, which is Windows-only while
the dev machine is a Mac. Three unmet needs: inspecting/understanding a table,
visually confirming an edit before it is flashed (the Phase 1 human review gate),
and comparing the same table across two bins (stock vs. tuned) or before/after an
in-session edit.

This phase is a pure read-side consumer, like Phase 2. It does not touch
`writer.py`, `checksum.py`, or any bin-mutation path, so the ECU-bricking safety
stakes that dominate the write side do not apply. The one safety-adjacent concern
carried forward is *fidelity of a review artifact*: a plot is used to confirm an
edit before flashing, so a **misleading** plot (e.g. a silently-produced
comparison of two mismatched tables) is a real failure mode — hence the hard-fail
on mismatched comparisons rather than a silent skip.

## Requirements (from origin doc)

- Any selected table (or batch) renders to static PNG(s) in physical units, built
  on `RenderedTable`/`render_table()` — no reimplementation of axis-label or
  degenerate-shape logic.
- 2D tables → **both** a 3D surface plot and a heatmap; the heatmap always
  overlays every cell's numeric value (TunerPro-style), regardless of size.
- 1D tables → a line plot. Scalar (1×1) tables → nothing produced.
- `compare_tables(a, b)` compares two views of the same calibration item,
  independent of provenance (two `.bin`s *or* before/after one edit): 2D → 3-panel
  composite (A / B share one scale, delta on its own zero-centered diverging
  scale); 1D → 2-panel (overlay on shared scale + delta below). Both heatmap and
  surface comparison variants ship by default, each independently toggleable off.
- Batch selection reuses Phase 2's symbol/category/"all" model (`select_tables`).
- PNG output, one file set per table, grouped into per-category subfolders.
- Library functions only (no CLI/GUI).
- Mismatched shapes/axes in a comparison → hard error naming the tables, never a
  misleading plot.
- Acceptance examples AE1–AE9.

## Research Findings (this codebase)

Confirmed by reading `render.py`, `calfile.py`, `export.py`, the Phase 2 plan,
and the test suite:

- **`RenderedTable` already carries everything the plots need** and nothing more
  is required from it: `symbol`, `title`, `units` (z), `x_labels`/`y_labels`
  (decoded breakpoints or a `0..N-1` index fallback), `x_units`/`y_units`,
  `categories` (tuple of names), and `values` (always a 2D `(rows, cols)` array).
  `y_labels is None` iff the table is a single row (1D or scalar). **No change to
  `render.py` is needed.**
- **Degeneracy is shape-driven** (`rows == 1` and/or `cols == 1`), never
  schema-driven — the same principle `render_table` already follows. Plot
  dispatch branches on `rendered.values.shape`: `(1,1)` → skip, single row →
  line, otherwise → surface + heatmap. (Phase 2 Research: 2,619 real tables are
  `(1,1)`, 573 are `(1,N)`; max shape 25×39, so per-table annotation volume is a
  non-issue.)
- **`render_table(view)` is a safe pre-edit snapshot mechanism** (resolves the
  requirements doc's before/after open question). `render_table` stores a
  reference to `view.values`; `TableView.set()`/`set_cell()` call
  `view.invalidate()`, which *drops* the cached array (`self._values = None`) and
  lets the next `.values` decode a **new** array — it never mutates the old array
  in place. So a `RenderedTable` captured before an edit still holds the pre-edit
  values afterward. The before/after flow is therefore just: `before =
  render_table(view)` → `view.set(...)` → `compare_tables(before, view)`. No new
  snapshot API and no copy in `render.py` are required. (U3 still defensively
  copies inside its own delta math so comparison never aliases caller arrays.)
- **`CalFile.get()` accepts an int uniqueid** (`model.get(key)` handles
  symbol/title/uniqueid; confirmed in README quick start). This gives
  `compare_bins` a robust cross-file match: select from `cal_a`, look up the same
  table in `cal_b` by `view_a.uniqueid`, which fails loud (`KeyError`) if the two
  bins were opened against different XDFs.
- **`select_tables()` (Phase 2, `export.py`) is directly reusable** for batch
  selection — same symbols/category/`all_tables` spec, dedup by uniqueid. No new
  `CalFile` query surface is needed (same conclusion Phase 2 reached).
- **Phase 2 grouped by category via duplication** (a multi-category table is
  written under every one of its categories; a category-less table is skipped in
  xlsx). Phase 3 mirrors the duplication but **diverges on the category-less
  case** — see Key Decision 6.
- **Packaging/test conventions to match:** runtime deps live in
  `[project.dependencies]` (Phase 2 added `openpyxl` there, not as an extra);
  the mini fixture (`tests/fixtures/mini.xdf`) has real decodable bytes for
  `SYM_10X10` (10×10), `PROFILE_1D` (1×5, embedded x-axis), `SYM_SCALAR` (1×1);
  acceptance suites skip cleanly without the real files via the `real_cal`
  fixture / `requires_real_files` guard.

## Key Technical Decisions

1. **Plotting library: matplotlib, used headless via the object API (no
   `pyplot`).** matplotlib is the settled default for static/headless output
   (resolves origin Q on library). The module constructs
   `matplotlib.figure.Figure` objects directly and saves with `figure.savefig(...,
   format="png")`, **never importing `matplotlib.pyplot`** — this avoids pyplot's
   global figure registry and interactive-backend selection, which is the correct
   pattern for a headless, script-driven library and keeps it thread-safe and
   side-effect-free on import. 3D surfaces use `fig.add_subplot(projection="3d")`
   (importing `mpl_toolkits.mplot3d` once to register the projection).
2. **matplotlib is a core runtime dependency, not an optional extra.** Consistent
   with how Phase 2 added `openpyxl` to `[project.dependencies]`. Considered a
   `[viz]` optional-extra to keep the base install lean; rejected for consistency
   and because the plot module is a first-class part of the read side, not a
   fringe add-on. Pin `matplotlib>=3.7` (for `TwoSlopeNorm` / modern colormap
   registry). Noted under Risks.
3. **Build directly on `RenderedTable`; no new abstraction layer.** Plot functions
   consume `RenderedTable` (the Phase 2 grid form) — no intermediate `PlotSpec`
   layer (explicitly rejected in the requirements doc as speculative).
4. **Public plot/compare functions accept `TableView | RenderedTable`.** They
   normalize by calling `render_table()` on a view, or using a `RenderedTable`
   as-is. This satisfies the requirements doc's `plot_table(view)` ergonomics
   *and* the before/after flow, which must pass a pre-edit `RenderedTable`
   snapshot (Research Findings). One code path, provenance-agnostic (Decision 8).
5. **Shape-driven dispatch, scalars skipped.** `(1,1)` → produce nothing (return
   empty list). Single row → one line PNG. Otherwise → surface + heatmap PNGs.
   Branches on `rendered.values.shape`, mirroring `render_table`'s own rule.
6. **Output is a directory of per-category subfolders; category-less tables go to
   `_uncategorized/`.** Batch functions take an `out_dir`; each table's PNG set is
   written under `out_dir/<sanitized category>/` for every category it belongs to
   (duplication, mirroring Phase 2 xlsx). **Divergence from Phase 2:** a table
   with no categories is written under `out_dir/_uncategorized/` rather than
   silently dropped — because a plot can be requested for one explicit table by
   symbol, and silently producing no file for an explicitly-named table violates
   the project's fail-loud/never-surprise ethos. Filenames are
   `<sanitized name>__<kind>.png` where name = symbol, else title, else
   `uniqueid_hex`, and kind ∈ {`surface`, `heatmap`, `line`, `compare_surface`,
   `compare_heatmap`, `compare_line`}. A filename sanitizer (analogous to Phase
   2's `_sanitize_sheet_name`) strips path-hostile characters.
7. **Heatmap always overlays every cell value (TunerPro fidelity), with adaptive
   text.** Cell text uses a concise display format (default `"{:.4g}"`,
   caller-overridable) — the PNG is an eyeballing aid; CSV/xlsx export remains the
   full-precision record. Text color auto-contrasts against each cell's fill
   luminance for legibility; font size scales down for larger grids. Always on
   regardless of size (max real grid 25×39 ≈ 975 cells is fine).
8. **Comparison is one provenance-agnostic function over two normalized inputs.**
   `compare_tables(a, b)` handles two-bin and before/after identically. Delta is
   defined **`b − a`** (documented: "second minus first" — read as tuned−stock or
   after−before). It validates first (Decision 9), then renders.
9. **Mismatch is a hard fail with a named error.** A new
   `TableMismatchError` (raised by `compare_tables`) fires when the two inputs
   differ in `values.shape`, or in `x_labels`/`y_labels` (axis breakpoints), with
   a message naming both tables (symbol/title/uniqueid). Never a silent skip and
   never a misleading plot — the one safety-adjacent rule of this phase.
10. **Fixed comparison layouts with two independent scales.** 2D → a single
    composite figure per variant: top-left A, top-right B (shared value norm =
    common vmin/vmax across A and B), bottom-center delta (diverging, symmetric
    zero-centered norm vmin=−M, vmax=+M with M = max|delta|). 1D → a 2-panel
    composite: top overlay of both lines on a shared y-scale, bottom delta line.
    Heatmap and surface comparison variants are separate files, each toggleable
    (`heatmap=`/`surface=` kwargs). Scalar comparisons produce nothing (nothing
    to plot), consistent with Decision 5.
11. **Default colormaps: sequential `viridis` for value panels, diverging
    `RdBu_r` for delta panels** (resolves origin Q on palettes). Perceptually
    uniform + colorblind-safe for values; a zero-centered diverging map for
    deltas. Both exposed as kwargs (`value_cmap=`, `delta_cmap=`) so a caller can
    switch to a TunerPro-like `turbo` if desired, without a redesign.
13. **3D surfaces bake in a fixed, well-chosen viewing angle.** Because output is
    a static PNG with no interactive rotation (Out of Scope), the camera angle is
    the only chance to read the surface — a poor default can hide the shape behind
    itself. Every surface figure (single-table and comparison) sets an explicit
    `ax.view_init(elev=..., azim=...)` — default `elev=30, azim=-120` (a
    conventional three-quarter view that shows both axes and the surface's relief),
    plus `set_box_aspect` for undistorted proportions. The elevation/azimuth are
    exposed as kwargs (`elev=`, `azim=`) so a caller can re-aim a surface whose
    relief a single default hides. The value colorbar (Decision 11) is retained on
    surface figures so height is legible even where the 2D projection is
    ambiguous.
12. **Numeric logic is factored into small pure helpers, separate from
    rendering.** Delta computation, shared-scale (vmin/vmax) derivation, the
    all-equal-delta guard, and mismatch validation are pure array functions,
    unit-testable without matplotlib. The matplotlib parts are proven by
    integration checks (file created, non-empty, correct panel/axes count),
    avoiding brittle golden-image comparisons.

## High-Level Technical Design

```
                 CalFile(s) + selection spec (symbols / category / all_tables)
                                    │
                                    ▼
   plot_tables(cal, out_dir, ...)          compare_bins(cal_a, cal_b, out_dir, ...)   (U4)
        │  select_tables() [Phase 2]            │  select_tables(cal_a) → match cal_b by uniqueid
        ▼                                       ▼
   for each view:                          for each (view_a, view_b):
     plot_table(view, dir) ──┐               compare_tables(view_a, view_b, dir) ──┐
                             │                                                     │
                             ▼                                                     ▼
                  ┌────────────────────────── normalize: TableView|RenderedTable ─┘
                  ▼                                                    (U2 / U3, Decision 4)
        render_table(view) → RenderedTable  [Phase 2, unchanged]
                  │
        shape-driven dispatch (Decision 5)
      ┌───────────┼─────────────────────────┬───────────────────────────┐
   (1,1) skip   single row → line       2D → surface + heatmap      compare → composite
                                             (U1 figure builders)     (U3 figure builders)
                  │                                                     validate first →
                  ▼                                                     TableMismatchError (U3)
        Figure objects (headless, no pyplot) ── savefig(png) ──► out_dir/<category>/<name>__<kind>.png
```

## Implementation Units

### U1. Plot module scaffold + single-table figure builders

- **Goal:** Stand up `simoscal/plot.py` with the matplotlib dependency and the
  three pure figure builders — surface, heatmap (with value overlay), line — that
  turn a `RenderedTable` into an in-memory `Figure`. No disk I/O yet.
- **Requirements:** Goals (render on `RenderedTable`); Scope (surface+heatmap for
  2D, line for 1D); Key Decisions 1, 2, 3, 5, 7, 11; AE1, AE2.
- **Dependencies:** none (Phase 2 `RenderedTable` complete).
- **Files:** `Code/simoscal/plot.py` (new), `Code/pyproject.toml` (add
  `matplotlib>=3.7` to `[project.dependencies]`), `Code/tests/test_plot.py` (new).
- **Approach:** Import matplotlib's object API only — `from matplotlib.figure
  import Figure`, and `import mpl_toolkits.mplot3d` once to register the `"3d"`
  projection; do **not** import `pyplot`. Builders:
  - `_heatmap_figure(rt, *, value_cmap="viridis", fmt="{:.4g}") -> Figure`:
    `imshow` of `rt.values` with axis ticks from `rt.x_labels`/`rt.y_labels`,
    axis titles from `rt.x_units`/`rt.y_units`, a colorbar, figure title from
    `rt.symbol`/`rt.title`; overlays each cell's value as text with luminance-based
    contrast and grid-size-adaptive font size (Decision 7).
  - `_surface_figure(rt, *, value_cmap="viridis", elev=30, azim=-120) -> Figure`:
    `add_subplot(projection="3d")`, `plot_surface` over `meshgrid(rt.x_labels,
    rt.y_labels)` with `rt.values` as Z; axis labels from units; a value colorbar;
    a fixed camera via `ax.view_init(elev=elev, azim=azim)` and `set_box_aspect`
    for undistorted proportions so the static PNG reads the surface well
    (Decision 13).
  - `_line_figure(rt, *, ...) -> Figure`: `rt.values[0]` vs `rt.x_labels`; x label
    from `rt.x_units`, y label from `rt.units` (z).
  Builders assume a valid shape for their kind (dispatch happens in U2); scalars
  are never handed to a builder.
- **Test scenarios:**
  - Happy — `_heatmap_figure` on the mini `SYM_10X10` `RenderedTable`: returns a
    `Figure` with one image whose array equals `rt.values`; the number of overlaid
    text artifacts equals `rows*cols` (100); tick labels match `rt.x_labels`.
  - Happy — `_surface_figure` on `SYM_10X10`: returns a `Figure` with one 3D axes;
    savefig to a `BytesIO` yields a non-empty PNG (smoke).
  - Edge — surface camera: the 3D axes' `elev`/`azim` equal the requested angle
    (default `30`/`-120`, and a passed-through override), so the baked-in view is
    the chosen one (Decision 13).
  - Happy — `_line_figure` on `PROFILE_1D` (1×5): one line whose y-data equals
    `rt.values[0]` and x-data equals `rt.x_labels` (embedded breakpoints
    `1000..5000`, not an index).
  - Edge — value-overlay format: a cell rendered with `fmt="{:.4g}"` shows the
    expected truncated string for a many-digit value.
  - Edge — a 1×N table with a label-only x-axis (index fallback): `_line_figure`
    uses `0..N-1` x-data without error.
- **Verification:** builders return `Figure`s with the expected artifact counts;
  each savefigs to a non-empty PNG buffer; `import simoscal.plot` succeeds with no
  window/backend side effects.

### U2. `plot_table()` — single-table dispatch + PNG output

- **Goal:** Normalize a `TableView | RenderedTable`, dispatch on shape, build the
  right figure(s), and write PNG(s) to a directory; scalars produce nothing.
- **Requirements:** Goals; Scope (`plot_table`); Key Decisions 4, 5, 6; AE1, AE2,
  AE3.
- **Dependencies:** U1.
- **Files:** `Code/simoscal/plot.py` (add `plot_table`, `_normalize`,
  `_sanitize_filename`, `_write_figure`), `Code/tests/test_plot.py`.
- **Approach:** `plot_table(source, out_dir, *, surface=True, heatmap=True,
  value_cmap="viridis", fmt="{:.4g}") -> list[Path]`. `_normalize(source)` returns
  a `RenderedTable` (calls `render_table` if given a `TableView`, else passes
  through — Decision 4). Branch on `rt.values.shape`: `(1,1)` → return `[]`;
  single row → write `_line_figure` as `<name>__line.png`; else → write
  `_surface_figure` (if `surface`) and/or `_heatmap_figure` (if `heatmap`).
  `out_dir` is created if absent (`mkdir(parents=True, exist_ok=True)`); files are
  written flat into `out_dir` here (category subfoldering is U4's job — `plot_table`
  takes an already-resolved directory). `_sanitize_filename(name)` builds the stem
  from symbol → title → `uniqueid_hex`. `_write_figure` calls `fig.savefig(path,
  format="png")`. Returns the list of written paths (for callers/tests).
- **Test scenarios:**
  - Happy (AE1) — `plot_table(SYM_10X10 view, dir)`: writes exactly
    `SYM_10X10__surface.png` and `SYM_10X10__heatmap.png`; both files exist and
    are non-empty.
  - Happy (AE2) — `plot_table(PROFILE_1D view, dir)`: writes exactly
    `PROFILE_1D__line.png`; no surface/heatmap file.
  - Edge (AE3) — `plot_table(SYM_SCALAR view, dir)`: returns `[]`; directory holds
    no PNG for it.
  - Edge — toggles: `surface=False` on a 2D table writes only the heatmap;
    `heatmap=False` writes only the surface.
  - Edge — passing a `RenderedTable` directly (not a view) produces identical
    output (Decision 4 normalization).
  - Edge — a table whose symbol contains a path-hostile char sanitizes to a safe
    filename without raising.
- **Verification:** correct file set per shape and per toggle; scalar yields no
  file; returned paths match files on disk.

### U3. Comparison figure builders + `compare_tables()`

- **Goal:** Validate two normalized tables, compute the delta, and produce the
  fixed composite comparison figures (3-panel 2D, 2-panel 1D), with the hard-fail
  on mismatch.
- **Requirements:** Scope (`compare_tables`, composites, hard error); Key
  Decisions 4, 8, 9, 10, 11, 12; AE4, AE5, AE6, AE8, AE9.
- **Dependencies:** U1 (reuses styling helpers), U2 (`_normalize`,
  `_sanitize_filename`, `_write_figure`).
- **Files:** `Code/simoscal/plot.py` (add `compare_tables`, `TableMismatchError`,
  `_check_comparable`, `_delta`, `_shared_limits`, `_diverging_limits`,
  `_compare_heatmap_figure`, `_compare_surface_figure`, `_compare_line_figure`),
  `Code/simoscal/__init__.py` (export `TableMismatchError` — kept with the module's
  other exports, finalized in U5), `Code/tests/test_plot.py`.
- **Approach:** `compare_tables(a, b, out_dir, *, surface=True, heatmap=True,
  value_cmap="viridis", delta_cmap="RdBu_r", fmt="{:.4g}") -> list[Path]`.
  Normalize both (Decision 4). `_check_comparable(rt_a, rt_b)` raises
  `TableMismatchError` (naming both via symbol/title/uniqueid) if
  `values.shape` differ or `x_labels`/`y_labels` differ (Decision 9). Pure
  helpers: `_delta(a, b) = b.values - a.values` on copies (Decision 8);
  `_shared_limits(a, b)` → `(vmin, vmax)` across both value arrays;
  `_diverging_limits(delta)` → symmetric `(-M, +M)` with `M = max(|delta|)`, and
  an **all-equal guard** (M==0 → fall back to `(-1, 1)` so the diverging norm is
  valid and the panel renders flat). Dispatch on shape: `(1,1)` → `[]`; single row
  → `_compare_line_figure` (2-panel: overlay + delta) → `<name>__compare_line.png`;
  else → `_compare_heatmap_figure` (if `heatmap`) and/or `_compare_surface_figure`
  (if `surface`), each a 3-panel composite (A/B on shared norm, delta on diverging
  norm) → `<name>__compare_heatmap.png` / `<name>__compare_surface.png`.
- **Test scenarios:**
  - Happy (AE4) — compare two 2D `RenderedTable`s (synthesize B from A's values
    with a known offset): `_compare_heatmap_figure` returns a `Figure` with 3
    value axes; `_shared_limits` equals the min/max across A and B;
    `_diverging_limits(delta)` is symmetric about 0. Writes
    `<name>__compare_heatmap.png` and `<name>__compare_surface.png`.
  - Happy (AE5) — compare two 1D tables: writes exactly `<name>__compare_line.png`;
    figure has 2 axes (overlay + delta); the delta line equals `b − a`.
  - Happy (AE6) — toggles: `surface=False` leaves only the heatmap composite;
    `heatmap=False` leaves only the surface composite.
  - Edge (AE8) — before/after via one view: `before = render_table(view)`;
    `view.set(edited)`; `compare_tables(before, view, dir)` produces the composite
    and the delta reflects exactly the edit (proves `render_table` snapshots the
    pre-edit state per Research Findings — no second bin).
  - Edge — identical tables (all-zero delta): renders without a divide-by-zero /
    degenerate-norm error (all-equal guard); delta panel is produced.
  - Error (AE9) — mismatched shapes (e.g. `(10,10)` vs `(1,5)`) raise
    `TableMismatchError` whose message names both tables; mismatched axis
    breakpoints at equal shape also raise.
  - Edge — scalar comparison (two `(1,1)`) returns `[]`.
- **Verification:** pure helpers (`_delta`, `_shared_limits`,
  `_diverging_limits`, `_check_comparable`) pass exact numeric/exception unit
  tests; composites savefig to non-empty PNGs with the right panel counts;
  mismatch raises with a table-naming message; before/after path works off one
  `CalFile`.

### U4. Batch wrappers — `plot_tables()` and `compare_bins()`

- **Goal:** Selection-driven batch entry points that reuse Phase 2's
  `select_tables()` and lay output out into per-category subfolders.
- **Requirements:** Scope (batch wrappers, category-subfolder output); Key Flows
  1–3; Key Decisions 6, 8; AE7.
- **Dependencies:** U2, U3, and Phase 2's `select_tables` (`export.py`).
- **Files:** `Code/simoscal/plot.py` (add `plot_tables`, `compare_bins`,
  `_category_dirs`), `Code/tests/test_plot.py`.
- **Approach:**
  - `plot_tables(cal, out_dir, *, symbols=None, category=None, all_tables=False,
    surface=True, heatmap=True, ...) -> list[Path]`: `select_tables(cal, ...)`
    (imported from `export`), then for each view render once and, for each of its
    categories (or `_uncategorized` if none — Decision 6), call `plot_table` into
    `out_dir/<sanitized category>/`. A multi-category table is written under each
    category (duplication, mirroring Phase 2). Aggregate and return all paths.
  - `compare_bins(cal_a, cal_b, out_dir, *, symbols=None, category=None,
    all_tables=False, surface=True, heatmap=True, ...) -> list[Path]`:
    `select_tables(cal_a, ...)`; for each `view_a`, get the matching table in
    `cal_b` via `cal_b.get(view_a.uniqueid)` (fails loud if the bins were opened
    on different XDFs); `compare_tables(view_a, view_b, out_dir/<category>/)` per
    category. Same `_uncategorized` and duplication rules.
  - `_category_dirs(rt)` → the list of sanitized subfolder names for a table
    (its categories, or `["_uncategorized"]`).
- **Test scenarios:**
  - Happy (AE7) — `plot_tables(mini_cal, dir, category="Fuel Trim")`: every
    non-scalar table in that category gets its PNG set under `dir/Fuel Trim/`; a
    scalar member (`SYM_SCALAR`) produces no file; the directory structure matches
    the category.
  - Happy — multi-category table (`SYM_SCALAR` is in `Fuel Trim` + one more, but is
    scalar → skipped): use a non-scalar multi-category table to confirm its file
    set appears under each of its category folders (duplication).
  - Edge — a category-less table (mini `Duplicate A`, no `CATEGORYMEM`) selected by
    symbol lands under `dir/_uncategorized/` rather than being dropped (Decision 6).
  - Happy — `compare_bins` over two `CalFile`s built from the same mini XDF but
    different bin bytes: composites are produced under the right category folders;
    a spot-checked delta equals the byte difference.
  - Error — `compare_bins` where `cal_b` lacks a selected uniqueid (simulated by a
    mismatched model) surfaces `get`'s `KeyError` (fail-loud), not a silent skip.
  - Integration — `plot_tables(real_cal, dir, category="Axis")` (skips without
    real files) produces a non-empty set of PNGs organized under `dir/Axis/`.
- **Verification:** batch output tree matches the category grouping; scalars
  skipped; category-less tables land in `_uncategorized`; duplication across
  categories works; `compare_bins` matches by uniqueid and fails loud on a missing
  match.

### U5. Public API wiring + acceptance suite + README

- **Goal:** Export the module's public surface, prove AE1–AE9 end-to-end, and
  document the module in the existing README style.
- **Requirements:** AE1–AE9; Key Flows 1–4; README documentation parity with
  Phase 2.
- **Dependencies:** U1, U2, U3, U4.
- **Files:** `Code/simoscal/__init__.py` (export `plot_table`, `compare_tables`,
  `plot_tables`, `compare_bins`, `TableMismatchError`; add to `__all__`),
  `Code/tests/test_acceptance_plot.py` (new, mirrors
  `test_acceptance_export.py`'s mini-fixture + `real_cal` skip pattern),
  `Code/README.md` (add a "Visualization (Phase 3)" section with the API-surface
  table and a quick-start snippet; update the intro line that lists phases).
- **Approach:** Finalize `__init__` exports. Write `test_acceptance_plot.py` with
  one test per AE (AE1–AE9), each asserting the *observable* contract (files
  produced/skipped, panel counts, delta values, mismatch error) against the mini
  fixture — fast and always-on — plus one real-data pass that skips cleanly when
  the bundled files are absent. README section documents `plot_table`,
  `compare_tables`, `plot_tables`, `compare_bins`, `TableMismatchError`, the PNG /
  category-subfolder output model, and the before/after (`render_table` snapshot)
  recipe.
- **Test scenarios (mapped to AEs):** AE1 2D → surface+heatmap files with value
  overlay; AE2 1D → line file; AE3 scalar → no file; AE4 2D compare → 3-panel
  heatmap composite (shared top scale, zero-centered delta) + surface composite;
  AE5 1D compare → 2-panel composite; AE6 comparison toggles; AE7 category batch →
  file set per non-scalar table under the category folder; AE8 before/after via one
  `CalFile`; AE9 mismatched compare → `TableMismatchError` naming both tables.
- **Verification:** the AE1–AE9 suite passes against the mini fixture and skips
  cleanly without the real files (consistent with `test_acceptance_export.py`);
  `from simoscal import plot_table, compare_tables, plot_tables, compare_bins,
  TableMismatchError` succeeds; README documents the module in the Phase 2 style.

## Scope Boundaries

**In:** static PNG rendering of 2D (surface + value-overlaid heatmap), 1D (line),
scalar-skip; provenance-agnostic `compare_tables` with fixed 3-panel/2-panel
composites and independent shared/diverging scales; symbol/category/all batch
selection reusing Phase 2; per-category subfolder output with `_uncategorized`
fallback; hard-fail on mismatched comparisons; matplotlib as a runtime dependency.

**Out (per requirements doc, retained):** interactive/on-screen viewing (rotate,
hover, zoom); CLI/GUI; vector formats (SVG/PDF); comparison of more than two
bins at once; any write/edit path.

### Deferred to Follow-Up Work
- Vector (SVG/PDF) output — PNG-only now; the figure builders would extend to it
  trivially if needed, but not built.
- Caller-configurable composite layouts / DPI / figure size — sensible fixed
  defaults ship; expose knobs only if a real need appears.
- A TunerPro-exact colormap match — defaults are `viridis`/`RdBu_r` with
  `value_cmap`/`delta_cmap` kwargs as the escape hatch (e.g. `turbo`); pixel-exact
  TunerPro parity is not a goal.

## Open Questions

None blocking. The three origin-doc outstanding questions are resolved here:
- **Plotting library** → matplotlib, headless object API, core dependency
  (Decisions 1–2).
- **Before/after snapshot mechanics** → `render_table(view)` is itself the
  snapshot; no new API or array copy in `render.py` (Research Findings, Decision 4,
  AE8).
- **Color palettes** → `viridis` (values) / `RdBu_r` (delta), both overridable
  (Decision 11).

## Risks & Dependencies

- **New runtime dependency (`matplotlib`).** Heavier than Phase 2's `openpyxl`
  (pulls in `pillow`, `contourpy`, etc.). Deliberate, for consistency with Phase
  2's dependency handling; base install grows. Mitigated by the headless
  object-API usage (no GUI backend needed).
- **Headless correctness.** Using `pyplot` could pick an interactive backend and
  fail/pop windows in a script/CI context. Avoided by construction — object API
  only, `savefig(format="png")`, no `pyplot` import (Decision 1). A test asserts
  `import simoscal.plot` has no window/backend side effects.
- **Golden-image brittleness.** Pixel-comparing PNGs across matplotlib versions is
  fragile. Avoided by testing pure numeric helpers exactly and asserting only
  structural/among-files facts for the rendered output (Decision 12).
- **`_uncategorized` divergence from Phase 2.** Phase 3 writes category-less tables
  to `_uncategorized/` where Phase 2 xlsx skips them — an intentional, documented
  difference (Decision 6), noted so it is not mistaken for an inconsistency.
- **Degenerate diverging norm.** Identical tables give an all-zero delta; the
  `_diverging_limits` all-equal guard prevents a zero-width norm (Decision 10,
  tested in U3).

## Sources & Research

- `Code/simoscal/render.py`, `Code/simoscal/calfile.py`, `Code/simoscal/export.py`,
  `Code/simoscal/__init__.py` — read to confirm the `RenderedTable` fields,
  `TableView` lazy-cache/`invalidate` snapshot behavior, `CalFile.get`'s int-
  uniqueid support, and `select_tables` reusability.
- `Code/tests/conftest.py`, `Code/tests/test_acceptance_export.py`,
  `Code/tests/fixtures/mini.xdf` — test/fixture conventions this phase follows
  (mini fixture symbols/shapes/categories, `real_cal` skip guard, acceptance-suite
  shape).
- `Code/pyproject.toml`, `Code/README.md` — packaging (runtime deps in
  `[project.dependencies]`) and README API-surface-table style to match.
- `Docs/plans/2026-07-06-001-feat-xdf-export-module-plan.md` — the Phase 2 plan
  this one mirrors (selection model, category grouping, Research Findings on real
  table-shape/category census).
- `Docs/brainstorms/2026-07-06-xdf-visualization-module-requirements.md` — origin
  requirements doc for this phase.
