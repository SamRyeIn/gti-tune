# Plan — Phase 2: Export Module (CSV / xlsx)

**Date:** 2026-07-06
**Type:** feat
**Origin:** [[2026-07-06-xdf-export-module-requirements]] (`docs/brainstorms/2026-07-06-xdf-export-module-requirements.md`)
**Status:** ✅ **Phase 2 complete** — **U1–U5 all done** (RenderedTable/render_table, select_tables, write_csv, write_xlsx, export_tables + AE1–AE7 acceptance suite).

## Summary

Add a `simoscal` export module that turns any selection of tables (explicit
symbols, a category, or all tables) into CSV and xlsx output, values in
physical units, grid-shaped like TunerPro. The core deliverable is a shared,
public rendering layer (`RenderedTable` / `render_table()`) so the CSV/xlsx
writers stay trivially consistent with each other and Phase 3 (visualization)
can consume the same table→grid shape later without redesign. Read-only — no
changes to the Phase 1 read/write/checksum paths.

## Problem Frame

See [[2026-07-06-xdf-export-module-requirements]] for the full problem
statement. In short: `simoscal` can read/edit tables via the Python API, but
there is no flat-file output for archiving, cross-tune comparison, or handing
values to another tool — every such need currently means throwaway script
code. This phase is entirely additive and entirely read-side; it does not
touch `writer.py`, `checksum.py`, or the bin-mutation path at all, so the
safety stakes that dominated Phase 1 (bricking the ECU, silent corruption)
don't apply here — the worst failure mode is an incorrect or crashing export,
not a corrupted `.bin`.

## Requirements (from origin doc)

- Export any selection of tables (symbols/titles, a category, or all) to CSV
  and to xlsx, in physical units, full float precision.
- Grid layout (X across, Y down, Z fills the matrix); 1D tables and
  scalar/constant tables degrade naturally, not forced into a uniform 2-axis
  shape.
- CSV: all selected tables in **one file**, stacked as separate labeled
  blocks. xlsx: tables grouped onto sheets **by XDF category**.
- A public, reusable rendering layer (`RenderedTable`) so Phase 3
  (visualization) can consume the same table→grid shape later.
- One-way (no import/round-trip), library-only (no CLI). *(Both decided in
  the requirements doc.)*
- Acceptance examples AE1–AE7 (2D grid fidelity, 1D shape, constant shape,
  xlsx category grouping, CSV multi-table stacking, selection dedup, direct
  rendering-layer reuse).

## Research Findings (empirical, this codebase)

These correct/sharpen a few assumptions in the requirements doc and drive the
Key Technical Decisions below:

- **There is no `XDFCONSTANT` in this project.** `simoscal/xdf.py` doesn't
  parse an `XDFCONSTANT` element, and `SC8S50.V1.0.xdf` contains zero of them.
  Every calibration — including what TunerPro users think of as a "constant"
  — is an `XDFTABLE`. A "scalar" is simply a table whose z-axis `EMBEDDEDDATA`
  is `(1, 1)`: **2,619 of the 3,814 real tables** are this shape.
- **`Table.x` / `Table.y` are never `None`** in the real XDF — every table
  carries both `XDFAXIS` elements, even when they're label-only (no
  `EMBEDDEDDATA`, just a placeholder `LABEL`). So "1D" isn't a schema
  distinction either: **573 real tables** are `(1, N)` shape with `N > 1`
  (zero are `(N, 1)`). Degeneracy is a **shape** property (`rows == 1` and/or
  `cols == 1`), never a presence/absence-of-axis property.
- **Label-only axes carry no real text.** Every one of the **6,237** x/y
  axis instances with `embedded is None` has only the trivial `"-"` label —
  confirmed by scanning all 3,814 real tables. So falling back to a raw
  `0..N-1` index when `axis_values()` returns `None` loses nothing (resolves
  requirements doc Q2).
- **Most tables belong to more than one category.** 660 categories exist;
  **2,683 of 3,814 tables (70%)** are cross-listed under 2+ categories (8,669
  total table↔category memberships). "Grouped by category" for xlsx
  therefore means a multi-category table is written onto **every** one of
  its categories' sheets, not a single "primary" one.
- **Table grids are small** (max observed shape is 25×39), so per-table
  output size is not a concern; the concern for a full "all tables" xlsx dump
  is sheet **count** (660) and duplication (8,669 memberships), not per-cell
  volume.

## Key Technical Decisions

1. **Architecture — public `RenderedTable`, not a private writer detail.**
   A shared rendering layer (`render_table(view) -> RenderedTable`) is the
   one source of truth for "table → grid," used by both the CSV and xlsx
   writers. It's exposed as a public type (not kept internal to `export.py`)
   so a future Phase 3 (visualization) can request the grid form of a table
   directly, without going through a file. *(Approach 3 from the brainstorm,
   chosen over keeping the rendering layer private or duplicating
   per-format logic.)*
2. **Degeneracy is shape-driven.** `render_table()` branches on `shape`
   (`rows == 1` / `cols == 1` / both), never on whether `Table.x`/`Table.y`
   is `None` — see Research Findings. This is simpler than the requirements
   doc's framing (which treated "1D" and "constant" as if they were distinct
   XDF concepts) and requires no `XDFCONSTANT`-specific parsing.
3. **Axis fallback: raw index.** When `axis_values()` returns `None`
   (label-only axis), the header is `0..N-1`. Confirmed safe empirically —
   resolves requirements doc Q2 definitively rather than deferring it.
4. **xlsx dependency: `openpyxl`.** The natural default for a numpy-only
   project needing `.xlsx` writing (resolves requirements doc Q1). Becomes a
   new **runtime** dependency (Phase 1 had only `numpy`) — called out under
   Risks.
5. **Multi-category tables duplicate across sheets.** Because 70% of tables
   are multi-category, "grouped by category" means writing a table's grid
   onto every one of its categories' sheets, not choosing one. This matches
   how TunerPro itself cross-lists a table.
6. **No new `CalFile` method.** Category-based selection filters
   `cal.unique_tables()` by `table.categories` client-side, inside the export
   module — this need is local to export, so it doesn't grow the Phase 1
   query surface (`CalFile.get/search/unique_tables/categories`).
7. **Selection dedup by uniqueid.** Symbol-list and category selections are
   unioned via uniqueid (same semantics as `CalFile.unique_tables()`), so a
   table matched by both an explicit symbol and a category filter is emitted
   once (AE6).
8. **Full float precision, no rounding.** This is a read path — no
   quantization concern the way `.bin` writes have. Values are written via
   Python's default float formatting.
9. **CSV: one file, stacked blocks. xlsx: sheets by category.** Both decided
   in the requirements doc; retained as-is.
10. **No import/round-trip, no CLI.** Both decided in the requirements doc;
    retained as-is. Editing stays through the existing `table.set`/
    `set_cell` API.

## High-Level Technical Design

```
CalFile.unique_tables() / get() / categories()
              │
              ▼
  select_tables(cal, symbols?, category?, all_tables?)   (U2)
   → list[TableView], deduped by uniqueid
              │
              ▼
  render_table(view) → RenderedTable                     (U1)
   symbol, title, units, categories, x_labels, y_labels, values
              │
      ┌───────┴────────┐
      ▼                ▼
 write_csv(...)   write_xlsx(...)                         (U3, U4)
 one file,        one workbook,
 stacked blocks   sheets by category
      │                │
      └───────┬────────┘
              ▼
     export_tables(cal, path, ...)                         (U5)
   dispatches by path suffix (.csv / .xlsx)
```

## Implementation Units

### U1. `RenderedTable` + `render_table()` — shared rendering layer
- **Goal:** A public, shared function that turns any `TableView` into a
  `RenderedTable` grid — the single source of truth for "table → grid" that
  both writers (and later, Phase 3) consume.
- **Requirements:** Goals (reusable rendering layer); Scope (`RenderedTable`);
  Key Decisions 1–3; AE1, AE2, AE3, AE7.
- **Dependencies:** none (Phase 1 complete).
- **Files:** `Code/simoscal/render.py` (new), `Code/simoscal/__init__.py`
  (export `RenderedTable`, `render_table`), `Code/tests/test_render.py`
  (new), `Code/tests/fixtures/mini.xdf` (add one fixture table covering the
  real `(1, N)` 1D case with a genuine embedded x-axis — the existing mini
  tables' x/y axes are all label-only), `Code/tests/test_xdf.py` and
  `Code/tests/test_read.py` (update the two hardcoded mini-table-count
  assertions, currently `4`, to match the new count).
- **Approach:** `RenderedTable` is a frozen dataclass: `symbol`, `title`,
  `units` (z units), `categories` (tuple of category name strings),
  `x_labels` (tuple of floats, or an index fallback), `y_labels` (same, or
  `None` when the table is a single row), `values` (2D numpy array, always
  `(rows, cols)` even in degenerate cases). `render_table()` reads
  `view.table.categories`, `view.shape`, `view.values`, and
  `view.axis_values('x'/'y')`; branches purely on `shape` per Key Decision 2.
  When an axis's `axis_values()` is `None`, substitutes a `0..N-1` index
  tuple per Key Decision 3.
- **Test scenarios:** Happy — render the mini `SYM_10X10` table (10×10,
  label-only x/y): labels are `0..9` index fallback; `values` matches
  `TableView.values` exactly. Happy — render the new 1D fixture table (real
  embedded x-axis): `x_labels` are decoded breakpoints, not indices; no
  `y_labels`. Edge — render `SYM_SCALAR` (1×1): no axis headers, single
  value. Edge — render a real 2D table (e.g.
  `IP_PRS_UP_THR_DIF_WIDE_OPEN_THR`, shape `(6, 6)`) against `real_cal`:
  labels match `axis_values()` exactly. Integration — render every table in
  `real_cal.unique_tables()` (3,814 tables) without exception, a smoke test
  that every shape/degeneracy branch survives the full real dataset.
- **Verification:** unit tests for the 2D/1D/1×1 cases pass; the full-real-
  data smoke test raises nothing; prior mini-fixture tests stay green after
  the count update.

### U2. Table selection resolution
- **Goal:** Turn a caller's selection spec — explicit symbols/titles, a
  category name, or "all" — into a deduplicated `list[TableView]`.
- **Requirements:** Scope (table selection); Key Decisions 6–7; AE6.
- **Dependencies:** none (independent of U1; only needs the existing
  `CalFile`/`TableView` surface).
- **Files:** `Code/simoscal/export.py` (new — selection logic is the first
  piece of the export module), `Code/tests/test_export.py` (new).
- **Approach:** A module-level `select_tables(cal, *, symbols=None,
  category=None, all_tables=False)` function. Category filtering reads
  `view.table.categories` names directly off `cal.unique_tables()` — no new
  `CalFile` method (Key Decision 6). Symbol/title entries resolve via
  `cal.get()`, reusing its existing `KeyError`/`AmbiguousTableError`
  semantics rather than reimplementing lookup. Results are unioned by
  `uniqueid` (Key Decision 7). Calling with none of the three selection
  inputs is a usage error (`ValueError`), since there's no sensible default.
- **Test scenarios:** Happy — select by an explicit 2-symbol list (mini
  fixture) returns exactly those tables. Happy — select by category
  (`"Boost Control"`) returns every mini table tagged with it. Happy —
  `all_tables=True` returns `cal.unique_tables()` verbatim. Edge — a symbol
  list and a category that overlap: the overlapping table appears exactly
  once. Error — an unknown symbol raises `KeyError`; an ambiguous symbol
  raises `AmbiguousTableError` (both delegated to `cal.get()`, not
  reimplemented). Error — no selection input raises `ValueError`.
  Integration — select the real `"Axis"` category (`real_cal`) and confirm a
  plausible non-zero count (444, per Research Findings).
- **Verification:** all selection modes covered against the mini fixture;
  the real-data category selection returns the expected count.

### U3. CSV writer
- **Goal:** Write a list of `RenderedTable`s to a single CSV file as stacked,
  labeled grid blocks.
- **Requirements:** Scope (CSV writer); Key Decisions 8–9; AE1, AE2, AE3, AE5.
- **Dependencies:** U1 (consumes `RenderedTable`).
- **Files:** `Code/simoscal/export.py` (add `write_csv()`),
  `Code/tests/test_export.py`.
- **Approach:** Stdlib `csv` module — no new dependency. For each
  `RenderedTable`, in call order: a metadata header (symbol, title, units),
  then the grid (a header row of `x_labels` with a blank leading cell if the
  table has 2+ rows or columns; one row per `y_labels` entry prefixed by
  that label, or a single bare value line for the 1×1 case), then a blank
  separator line before the next block. Floats written at full precision
  (Key Decision 8) — no manual rounding.
- **Test scenarios:** Happy — write one 10×10 table; re-parse the CSV and
  confirm the recovered grid equals `TableView.values` exactly. Happy —
  write three tables (2D + 1D + 1×1) in one call; confirm three labeled
  blocks appear, in order, cleanly separated. Edge — a many-decimal-digit
  value round-trips exactly through `str` → `float`. Integration — export a
  handful of real tables (`real_cal`) to CSV and re-parse; spot-checked
  cells match `.values`.
- **Verification:** round-trip parse of the written CSV reconstructs every
  table's grid and metadata without loss.

### U4. xlsx writer
- **Goal:** Write a list of `RenderedTable`s to a single xlsx workbook,
  tables grouped onto sheets by XDF category.
- **Requirements:** Scope (xlsx writer); Key Decisions 4–5, 9; AE4.
- **Dependencies:** U1.
- **Files:** `Code/simoscal/export.py` (add `write_xlsx()`),
  `Code/pyproject.toml` (add `openpyxl` to `dependencies`),
  `Code/tests/test_export.py`.
- **Approach:** `openpyxl.Workbook()`. For each category name represented
  across the selected tables' `categories` (union), create a sheet (name
  sanitized/truncated to Excel's 31-character sheet-name limit) and write
  every table carrying that category as a grid block — same block layout as
  U3, factored into a shared helper rather than duplicated. A table in N
  categories is written onto N sheets in full (Key Decision 5), not linked
  or referenced once.
- **Test scenarios:** Happy — three tables across two categories: workbook
  has exactly two sheets, each with the correct table subset. Edge — a
  table in two categories appears identically on both sheets. Edge — a
  category name at/over the 31-character limit is sanitized without
  crashing or colliding with another sheet name. Integration — export the
  real `"Axis"` category slice (444 tables) and confirm the workbook loads
  via `openpyxl.load_workbook` with the expected sheet/table count.
- **Verification:** workbook opens via `openpyxl`; sheet set matches
  expected categories; a sampled table's grid matches its
  `RenderedTable.values`.

### U5. Public entry point + acceptance suite
- **Goal:** Wire selection (U2), rendering (U1), and the writers (U3/U4)
  behind one function, and prove the requirements doc's acceptance examples
  end-to-end.
- **Requirements:** AE1–AE7; Key Decision 10; README documentation.
- **Dependencies:** U1, U2, U3, U4.
- **Files:** `Code/simoscal/export.py` (add `export_tables()`),
  `Code/simoscal/__init__.py` (export `export_tables`, `write_csv`,
  `write_xlsx`, `select_tables`, `RenderedTable`, `render_table`),
  `Code/tests/test_acceptance_export.py` (new, mirrors the existing
  `test_acceptance.py` real-file skip pattern), `Code/README.md` (document
  the export module in the existing API-surface-table style).
- **Approach:** `export_tables(cal, path, *, symbols=None, category=None,
  all_tables=False)` resolves selection (U2), renders every match (U1), and
  dispatches to `write_csv`/`write_xlsx` (U3/U4) by the output path's suffix
  (`.csv` vs `.xlsx`); an unrecognized suffix raises a clear usage error
  rather than guessing a format.
- **Test scenarios (mapped to requirements doc AEs):** AE1 — 2D grid header/
  row/values match `TableView.values`. AE2 — 1D table has no spurious second
  axis. AE3 — 1×1 table has no grid structure. AE4 — xlsx sheet-per-category
  with correct membership. AE5 — CSV single-file, ordered, labeled blocks.
  AE6 — category + explicit-symbol selection unions without duplicates.
  AE7 — calling `render_table()` directly (no file involved) matches the
  numbers the writers produced for the same table.
- **Verification:** the acceptance suite (AE1–AE7) passes against the mini
  fixture (fast, always-on) and skips cleanly without the real files
  (`real_cal` unavailable), consistent with the existing `test_acceptance.py`
  convention; README documents the new module's public API.

## Scope Boundaries

**In:** CSV export (one file, stacked blocks), xlsx export (sheets by
category), a public `RenderedTable`/`render_table()` rendering layer,
symbol/category/all-tables selection, full-precision values.

**Out (per requirements doc, retained):** import/round-trip back into a
`.bin`; a CLI or GUI; caller-configurable rounding; caller-configurable sheet
grouping; visualization (Phase 3) — this phase only ensures `RenderedTable`
is a usable foundation for it, not building any plotting/rendering-to-image
logic.

### Deferred to Follow-Up Work
- Round-trip import (edit-in-spreadsheet workflow) — no evidence of need yet;
  revisit only if it comes up.
- Caller-configurable sheet grouping / rounding — not built; the fixed
  defaults (category grouping, full precision) cover the stated use cases.
- Performance work for very large "export everything" xlsx dumps (660
  sheets, up to ~2,146 tables on one sheet) — not a demonstrated problem
  today (see Risks), so not addressed pre-emptively.

## Open Questions

None blocking. All three outstanding questions from the requirements doc
were resolved during planning research:
- **Q1 (xlsx library):** resolved — `openpyxl` (Key Decision 4).
- **Q2 (axis fallback):** resolved — raw index, confirmed safe empirically
  (Key Decision 3, Research Findings).
- **Q3 (output naming):** not applicable — both writers take one explicit,
  caller-supplied output path (one file / one workbook per call), so there's
  no auto-naming convention to design.

## Risks & Dependencies

- **New runtime dependency (`openpyxl`).** Phase 1 kept runtime dependencies
  to `numpy` only; this phase adds `openpyxl` for xlsx writing. Low risk —
  mature, widely used library — but a deliberate departure worth noting.
- **Full "all tables" xlsx export is sheet-heavy.** 660 categories and 8,669
  table↔category memberships (70% of tables are multi-category) mean a
  full-dump xlsx workbook will have 660 sheets, some large (e.g. "Engine
  Diagnostic" ≈ 2,146 tables). Per-table grids are small (max 25×39), so this
  is about sheet count/duplication, not data volume — likely slower to open
  in Excel than the CSV equivalent, but not a correctness problem. No design
  change made now; noted for whoever runs a full dump.
- **Fixture change touches existing tests.** Adding a 1D table to
  `mini.xdf` (U1) requires updating two pre-existing hardcoded counts in
  `test_xdf.py` and `test_read.py` — small and contained, but must land in
  the same change or those tests break.

## Sources & Research

- `Code/simoscal/model.py`, `Code/simoscal/calfile.py`, `Code/simoscal/xdf.py`
  — read in full to confirm `Table`/`TableView`/`XdfModel` query surface and
  the absence of an `XDFCONSTANT` code path.
- Empirical queries against `real_cal` (`xdf/SC8S50.V1.0.xdf` +
  `bin/5G0906259L__0002.bin`) via the existing library: table-shape census
  (2,619 at 1×1, 573 at `(1,N)`, max shape 25×39), category census (660
  categories, 2,683 multi-category tables, 8,669 total memberships), and a
  full scan of label-only axes (6,237, all trivial `"-"` labels).
- `Code/tests/conftest.py`, `Code/tests/fixtures/mini.xdf`,
  `Code/tests/test_xdf.py`, `Code/tests/test_read.py` — existing fixture/test
  conventions this phase's tests follow (real-file skip guard, mini-fixture
  hardcoded counts).
- `Code/README.md`, `docs/plans/2026-07-05-001-feat-xdf-bin-library-plan.md`
  — Phase 1 conventions (plan structure, README API-surface-table style).
- `docs/brainstorms/2026-07-06-xdf-export-module-requirements.md` — origin
  requirements doc for this phase.
