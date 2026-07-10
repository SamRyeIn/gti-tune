# Requirements — XDF/BIN Library Phase 2: Export Module

**Date:** 2026-07-06
**Topic:** Export `simoscal` tables to CSV / xlsx in physical units
**Status:** Requirements captured — ready for `/ce-plan`
**Related notes:** [[xdf-bin-library-requirements]] (Phase 1, the substrate this consumes)

## Problem

`simoscal` (Phase 1) can read and edit calibration tables in physical units, but the
only way to see the data today is through the Python API (`table.values`) or
TunerPro. There's no flat-file output — for archiving a tune's calibration,
comparing tables across two bins, or handing values to a spreadsheet or another
tool, someone would have to write throwaway script code every time. Phase 2 gives
`simoscal` a general-purpose, reusable export path.

## Goals & Success Criteria

- Any selected set of tables can be exported to **CSV** and to **xlsx**, with
  values in physical units (matching `TableView.values`, full float precision).
- Output is usable for multiple purposes without reshaping: human review in
  Excel/Numbers, side-by-side diffing across tune versions, and as an
  interchange format for other tools — this is a general-purpose export, not
  built around one workflow.
- Tables render as a grid: X-axis values as column headers, Y-axis values as
  row headers, Z-values filling the matrix — matching how the data looks in
  TunerPro. 1D tables and scalar constants degrade naturally (fewer axes, or
  just a label + value), not forced into a uniform 2-axis shape.
- The underlying grid representation is reusable outside the export path
  itself, so Phase 3 (visualization) can consume the same table→grid logic
  without reimplementing it.

## Scope

### In scope (Phase 2)
- A `RenderedTable` type: the public, shared intermediate that turns a
  `TableView` into a grid — metadata (symbol, title, Z units) + axis labels
  (with axis units, if the axes have them) + a 2D value array. Degenerate
  forms for 1D tables (single axis) and constants (no axes, single value).
- CSV writer: all selected tables in **one file**, stacked vertically as
  separate grid blocks, each preceded by its metadata header
  (symbol + title + units).
- xlsx writer: selected tables grouped onto sheets **by XDF category**; each
  table renders as its grid block (same layout as CSV) within its category's
  sheet.
- Table selection accepts, in one call: an explicit list of symbols/titles, a
  category name, or "all" (via `CalFile.unique_tables()`) — covering targeted,
  category-wide, and full-dump export in the same function.
- Full float precision in output — no rounding, since this is a read-only
  export, not a write/flash path where quantization matters.
- Library function(s) only, callable from a script — no CLI.

### Out of scope (Phase 2)
- **Import / round-trip.** No path from an edited CSV/xlsx back into the
  library to modify a bin. Editing stays through the existing Python API
  (`table.set` / `set_cell`). *(Decided — matches Phase 1's framing of export
  as a read-only consumer.)*
- **CLI or GUI.** Consistent with Phase 1's decision; a short script covers
  ad-hoc invocation.
- **Visualization** (plots, heatmap/colormap rendering) — Phase 3. This phase
  only needs to make sure `RenderedTable` is a usable foundation for it.
- Rounding/precision controls, custom sheet-grouping overrides, and per-table
  file output were considered and explicitly not chosen as the default (see
  Key Decisions) — not ruled out forever, just not building them now.

## Key Flows

1. **Targeted export** — select a short list of tables by symbol; export to
   CSV (one file, all tables stacked) and/or xlsx (grouped onto sheets by
   category).
2. **Category export** — select every table in a category (e.g. "Boost
   Control"); export to xlsx, landing together on that category's sheet.
3. **Full dump** — select all unique tables (`cal.unique_tables()`); export to
   CSV/xlsx as a flat-file archive of the whole calibration.
4. **Programmatic reuse** — call the rendering layer directly to get a
   `RenderedTable` for a table without writing any file (e.g. for a future
   visualization call).

## Acceptance Examples

- **AE1** — Export a 2D table (X + Y axes) to CSV: the grid's header row
  matches the table's X-axis breakpoints, the first column matches the
  Y-axis breakpoints, and the interior values equal `table.values` exactly
  (full precision, no rounding).
- **AE2** — Export a 1D table (X axis only, no Y): output has one header row
  of X values and one row of Z values — no spurious empty row/column for the
  missing axis.
- **AE3** — Export an `XDFCONSTANT` (no axes): output is a label (symbol +
  title + units) and its single value — no grid structure.
- **AE4** — Export three tables spanning two categories to xlsx: the workbook
  has one sheet per represented category, and each table's grid appears under
  its correct category's sheet.
- **AE5** — Export the same three tables to CSV: all three grid blocks appear
  in a single file, each preceded by its own symbol/title/units header, in
  the order requested.
- **AE6** — Selecting tables by category name and by explicit symbol list in
  the same export call both work and produce the union of matching tables
  (no duplicates, using `unique_tables()` dedup semantics).
- **AE7** — Calling the rendering function directly on a `TableView` (no file
  involved) returns a `RenderedTable` whose grid values match AE1 — confirming
  the export writers and the reusable rendering layer share one code path.

## Key Decisions

- **Architecture:** shared rendering layer exposed as a **public** type
  (`RenderedTable`) rather than kept private to the export writers (Approach
  3 over Approaches 1–2 considered during brainstorming) — small surface-area
  cost now, in exchange for Phase 3 (visualization) being able to consume the
  same table→grid shape without redesign, matching this project's established
  phased-foundation pattern from Phase 1.
- **Layout:** grid/matrix form (TunerPro-like: X across, Y down, Z fills the
  matrix) for both CSV and xlsx — not a tidy/long machine-format. Chosen for
  human readability; the export is explicitly general-purpose, not scoped to
  one machine-consumer.
- **CSV multi-table structure:** one file, tables stacked vertically as
  separate labeled blocks — not one-file-per-table.
- **xlsx multi-table structure:** tables grouped onto sheets by **XDF
  category** — not one-sheet-per-table, not caller-specified grouping.
- **Degenerate shapes:** 1D tables and constants shrink the grid naturally
  (fewer axes / no grid) rather than being forced into a uniform 2-axis shape
  or excluded from export entirely.
- **Precision:** full float precision, no rounding — this is a read path, so
  there's no quantization concern the way there is for `.bin` writes.
- **Selection:** one export entry point accepts symbols/titles, category, or
  "all," rather than requiring the caller to always pre-resolve a list of
  `TableView`s themselves.
- **No import path.** Export stays one-way (bin → file). *(Decided.)*
- **No CLI.** Library-only, consistent with Phase 1. *(Decided.)*

## Deferred / Out of Scope (beyond this phase)

- Round-trip import (edit-in-spreadsheet workflow) — noted as a possible
  future extension if a real need for it shows up, but explicitly not Phase 2.
- Caller-configurable sheet grouping (vs. fixed XDF-category grouping).
- Caller-configurable numeric rounding.
- CLI wrapper.

## Outstanding Questions

Non-blocking — sensible defaults exist; confirm during planning:

- **Q1 (xlsx library):** which dependency to add for `.xlsx` writing
  (`openpyxl` is the natural default given the project already uses only
  `numpy` as a runtime dependency) — an implementation detail for planning,
  not a product decision.
- **Q2 (axis fallback):** some XDF axes may not have embedded breakpoints
  (static/label-only or absent). Default behavior should fall back to raw
  row/col index as the header in that case — confirm this doesn't lose
  information planning needs to account for.
- **Q3 (output path/naming):** whether output filenames are always fully
  caller-specified, or whether the module should suggest a default naming
  convention (e.g. derived from bin filename) when the caller doesn't care —
  minor ergonomic detail for planning.
