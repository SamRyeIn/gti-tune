# Tune report redesign — requirements

**Date:** 2026-07-20
**Status:** Brainstorm complete, ready for planning
**Affects:** `Code/simoscal/tune/pipeline.py` (markdown emit), `report_html.py`
(HTML emit), `journal.py` (data). Human-facing artifact:
`Tunes/<Tune>/<Tune>_out/R<NN>_<ts>/report.md` (+ `report.html`).

## Problem

The per-revision `report.md` was useful early in the project and has become
harder to read the deeper you dig. Worked example: `R14_20260720-222812/report.md`
(426 lines) whose actual change is tiny — add a stock map on slot 1, reorder the
five `IP_PUT_SP` boost slots least→most (~5 tables, 724 bytes vs R13). Specific
failures:

1. **The report conflates two questions at one granularity and answers neither
   cleanly:** (A) what does the whole bin do vs stock, and (B) what did *this*
   revision change vs the last flashed bin. R14's 5 real changes are buried in
   150 rows that are byte-identical to R13. The intro prose says "only the four
   per-slot grids move… byte-identical to R13" while the journal lists all 153 —
   the reader reconciles that by hand.
2. **No folding by intent.** One decision ("interpolate max torque to 275–440")
   is exploded into 25 near-identical `IP_TQ_POW_MAX_*` rows; "raise TTA above
   400 to the linear trend" into ~18 `IP_MAF_STK_SP_VVL_CAM_*` rows. Each carries
   identical Before/After and identical Why text.
3. **Worst-of-both Before/After.** `226..361 → 275..440` collapses a whole grid
   to two numbers (too little to judge safety) while the row count is too high to
   skim (too much to read).
4. **Five status labels with no legend.** applied / unchanged / blocked /
   skipped / superseded — meanings aren't stated, and `superseded` rows carry
   nested paragraphs quoting another recipe's skip reason.
5. **The "Why / detail" column is a paragraph in a table cell**, blowing column
   width to ~300 chars — unreadable in a terminal.
6. **The Artifacts section is a 220-line raw dump** of every PNG filename,
   including several literally named `_X_ x_Y_ y__compare_heatmap.png`. It is a
   directory listing, not an index.

## Goals & success criteria

1. Opening the report, the safety-relevant delta (what changed vs the last
   flashed bin) is visible without scrolling or hand-reconciling prose vs table.
2. The 150+ per-table edits read as the handful of *decisions* they represent,
   while every per-table row remains recoverable in the same file.
3. No information is lost vs today's journal — the full audit trail survives.
4. Both `report.md` and `report.html` change together and stay consistent.

**Verification:** re-run R14 and R13 through the new generator and confirm
(a) the delta section lists exactly the 5 `IP_PUT_SP` slot tables and its byte
count matches the raw-diff gate (724), (b) the folded intent-group counts sum to
the old 153 applied rows (nothing dropped, only grouped), (c) every per-table
row is still present inside the folds, and (d) `report.md` and `report.html`
agree.

## Scope

**In scope**

- Restructure `report.md` / `report.html` layout (below).
- Fold the edit journal by intent; keep per-table rows behind collapsible
  `<details>` blocks.
- Add a "changed vs previous revision" delta section driven off the existing
  `reference_bin=` diff (the raw-diff gate already computes it).
- Add a status-label legend; replace the 220-line artifact dump with grouped
  inline plots + a pointer line.

**Out of scope**

- The verification gates themselves (checksums, readback, raw-diff audit) — logic
  unchanged; only how their result is *presented*.
- `journal.json` schema/content — stays the full source of truth (all 5 states,
  recipe lineage). This is a presentation-only change.
- The analysis-battery `log_review` reports (different artifact, different code).

## Target structure (report.md / report.html)

Ordered top to bottom. Sections 1 and 2 are co-equal, delta first:

1. **Header + human-review banner** (keep).
2. **Changed vs R<NN-1>** — the delta. Only tables that differ from the last
   flashed bin, in physical units, with their compare plot inline. One-line trust
   statement from the raw-diff gate ("724 bytes, all attributed"). "Everything
   else byte-identical to R<NN-1>."
3. **Full picture vs stock — folded by intent.** One line per decision:
   `intent — effect (N tables)`, with a `* changed this rev` marker on groups
   that overlap the delta. Each line expands (`<details>`) to the full per-table
   rows (ID + description, Before/After, status). Group key derives from the
   `intent=` string / numbered stage prefix already in the journal data.
4. **Verification gates** (keep, with the status legend nearby).
5. **Plots** — grouped under their intent, inline; replace the flat dump with a
   single "all N comparison plots in `compare/`" pointer.

## Key decisions

- **KD1 — Both sections, delta first.** Section 2 (delta vs prev) and section 3
  (full vs stock, folded) are co-equal; the delta leads because that is what
  gets reviewed before a flash.
- **KD2 — Collapsible fold, single file.** Per-table rows live inside `<details>`
  under each intent group in `report.md` — not a sibling file. Renders folded on
  GitHub/HTML; raw `<details>` tags are acceptable in a plain terminal since the
  rows stay visible.
- **KD3 — Keep all 5 status labels, add a legend.** applied / unchanged /
  blocked / skipped / superseded stay (Sam wants the lineage); a short legend
  defines each. The nested cross-recipe skip-reason text does NOT belong in the
  human report — collapse it to one line and leave the full lineage in the JSON.
- **KD4 — Delta reuses the existing reference-bin diff.** No new comparison
  machinery; the raw-diff audit already diffs vs R<NN-1>.

## Acceptance examples

- **AE1** Open R14's report → section 2 shows the 5 `IP_PUT_SP` slot tables and
  nothing else, boost targets in psi, byte count = 724 matching the gate.
- **AE2** Section 3 shows the max-torque decision as one line "(25 tables)";
  expanding it reveals all 25 `IP_TQ_POW_MAX_*` rows with their per-table
  Before/After.
- **AE3** Summing every intent group's table count equals the old "applied: 153".
- **AE4** A reviewer reads what R14 does and whether it is safe to flash without
  scrolling past ~one screen before reaching the delta.
- **AE5** `report.html` and `report.md` present the same sections in the same
  order with the same numbers.

## Outstanding questions

- **OQ1 (deferred)** Inside a fold, keep today's `min..max` Before/After range,
  or show something richer (per-cell delta count, changed-cell heatmap thumbnail)?
  Range is fine for v1; revisit if folds still read thin.
- **OQ2 (deferred)** Intent-group key: is `intent=` alone reliable enough to
  produce clean groups, or does grouping need the numbered stage prefix
  ("1. Torque request", "2. Torque → Airflow") as a fallback? Resolve during
  planning by inspecting the R14 journal's intent strings.

## Handoff

Next: `/ce-plan` to turn this into an implementation plan against
`simoscal/tune/`.
