# Plan — SOP Tune Recipe

**Date:** 2026-07-06
**Type:** feat
**Origin:** [[2026-07-06-sop-tune-recipe-requirements]] (`Docs/brainstorms/2026-07-06-sop-tune-recipe-requirements.md`)
**Status:** completed

## Summary

Add a `simoscal` recipe module that applies `ecu-tuning-basics.md`'s concrete,
log-independent instructions to the stock `bin/5G0906259L__0002.bin` via
`xdf/SC8S50.V1.0.xdf`, using the existing Phase 1–3 read/edit/write/checksum/
compare API unchanged. Output is a saved, checksum-verified `.bin`, a
structured report (applied / skipped-vague / skipped-log-dependent /
guarded-and-skipped, per table), and before/after comparison PNGs for every
changed non-scalar table — no new safety, checksum, or plotting logic, no
flashing. Scalar (1,1) changes are covered by the report's old→new values,
since `compare_tables` produces no PNG for scalars by design (see Key
Decision 6).

## Problem Frame

See the origin requirements doc for the full problem statement. In short:
`ecu-tuning-basics.md` documents a manual TunerPro SOP; `simoscal` (Code/) can
already read/edit/write the same bin programmatically with safety guards, but
nothing bridges "the guide's instructions" to "a modified `.bin` produced via
`simoscal`."

## Requirements (from origin doc, amended 2026-07-07 per user direction)

- Apply the guide's literal example values for: Max Torque at Clutch, TTA/ATT
  (approximated proportional build-out), PUT setpoint boost curve + Max PR
  flatten + torque-tune selector, Basic Ignition Angle timing, fueling/lambda
  tables, cylinder head temp setpoint, and the limiter tables with explicit
  numbers (with Overboost limit specifically guarded).
- **Amendment (2026-07-07):** the Basic Ignition Angle literal table is
  propagated to **all 9 VVL-0 Port Flap Low tables**
  (`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`), not just
  Intake 0 / Exhaust 0 — user direction, consistent with the guide's "only
  the 9 'VVL 0' Port Flap Low tables matter."
- **Amendment (2026-07-07):** Spark IAT correction is **in scope** (user has
  the upgraded intercooler the author's table assumes). Target
  `IP_IGA_BAS_TEMP_N_32` with the author's table as transcribed and
  double-entry-verified in `knowledge/ecu-tuning-basics.md` (row-mapped onto
  stock Y breakpoints — see U2).
- Skip and report (never guess): wastegate flow-factor tables, torque-request
  pedal-feel tables, vague/screenshot-only limiter entries, V30/LB6 variant
  tables, ethanol/Flex Fuel, DSG farts, pops & bangs.
- Guarded write pattern: read current value before writing any "raise this
  limiter" edit with an irreversible-if-overshot risk (Overboost limit is the
  named example); skip + warn if the guard condition fails.
- Output: saved bin passing `verify_checksums()` after
  `save(correct_checksums=True)`; a report enumerating every in-scope table's
  outcome; before/after comparison PNGs for every non-scalar table actually
  changed, reusing Phase 3 `compare_tables`/`compare_bins` (which by design
  produce no PNG for (1,1) scalars — those are reviewed via the report's
  old→new values instead; see Key Decision 6).
- AE1–AE5 from the origin doc (full value-match, guard behavior, checksum
  cleanliness, complete accounting, comparison PNG coverage).

## Research Findings (empirical, this codebase)

Queried the real `CalFile` (`xdf/SC8S50.V1.0.xdf` + `bin/5G0906259L__0002.bin`)
to check whether the guide's sections map onto discoverable XDF structure
before committing to a design:

- **The XDF's own category taxonomy tracks the guide's section structure
  closely.** Of 660 categories, the ones matching guide sections exist
  verbatim or near-verbatim: `Torque Request`, `Torque Model`,
  `Airflow to Torque - Port Flap High/Low`, `Torque to Airflow - Port Flap
  High/Low`, `Boost Control`, `Boost Display`, `Overboost`, `Underboost`,
  `Turbocharger`, `Spark`, `Fuel`, `Flex Fuel`, `Speed Limiter`. This means
  table discovery can be **category-first, keyword-second**, not a blind
  full-text search over 3,814 tables.
- **Concrete symbol matches confirmed by title + shape + units cross-check
  against the guide:**
  - Max Torque at Clutch → `IP_TQ_POW_MAX_AT[POW_n][type]` (AT/DCT, 9×20,
    Nm), `IP_TQ_POW_MAX_MT[POW_n][type]` (MT, 7×20, Nm), and
    `IP_TQ_POW_MAX_ECO[n]` (Eco, 10×12, Nm) — multiple Power-Class (PC)
    variants exist per the guide's "many PCs exist, set them all the same"
    note.
  - TTA (Torque → Airflow) → `IP_MAF_STK_SP_VVL_CAM_H[...]` /
    `IP_MAF_STK_SP_VVL_CAM_L[...]` (Port Flap High/Low × VVL × cam
    variants, 16×16, mg/stk) — matches guide units exactly.
  - ATT (Airflow → Torque) → `IP_TQI_REF_N_M_AIR_VVL_CAM_H[...]` /
    `..._CAM_L[...]` (same variant structure, 16×16, Nm).
  - PUT setpoint (boost curve, Option 2) → `IP_PUT_SP`, shape (4, 6), units
    hPa — **structurally an exact match** to the guide's example table (4 Y
    rows × 6 RPM columns, last row is the shaped curve). **Corrected
    2026-07-07 (empirical):** stock rows 1–3, the X axis (2000…6500), and
    the row values match the guide's table to two decimals — the guide's
    example bin is effectively this bin — **but the stock Y-axis last
    breakpoint is 2500.05 hPa, not 2698.97**. The author edited the axis
    itself ("set axis to max boost"). Applying Option 2 therefore requires
    **one axis-cell write** (2500.05 → 2698.97 in the separate axis table
    `ldp_map_sp_ip_put_sp`, (1,4), hPa) plus the 6 last-row cell values —
    without it, the fail-loud axis-match rule correctly rejects the whole
    boost curve. See the `axis_write` treatment in U1/U2.
  - Basic Ignition Angle → the `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]`
    family — 16×16, °CRK. **Corrected 2026-07-07:** the guide is explicit
    that Port Flap **Low** (WOT, port flap = 0) is the edit set — "only the
    9 'VVL 0' Port Flap Low tables matter" — and the sweep confirmed exactly
    9 `[STND]` (VVL 0) tables per port family (Intake 0–2 × Exhaust 0–2).
    Per user direction the literal Intake 0/Exhaust 0 table is written to
    all 9 `_PORT_L[STND]` tables; `_PORT_H` and `[LFT_1]` (VVL 1) stay
    stock. Minimum (`IP_IGA_MIN_BAS_*`) and MBT (`IP_IGA_REF_IVVT_*`)
    families confirmed present and are never touched.
  - Speed limiter → `LMVLim_vMax_vLim_C_VW.VehSpdl2Lvl1/Lvl2/Lvl3/NotAcv`,
    all (1,1), km/h — exactly the guide's "four overall maximal velocity
    tables."
  - Turbo shaft speed limiter → `C_N_TCHA_MAX` / `C_N_TCHA_MAX_SP`
    ("Maximum turbo charger speed" / "...setpoint for turbo charger
    protection"), both (1,1), rpm — matches "both tables" in the guide.
  - Charge air pressure too high → `IP_PUT_MAX_CAP_H_DIAG`, (6,6), hPa —
    title matches the guide's diagnosis-table description verbatim.
- **2026-07-07 follow-up sweep (real `CalFile`, full guide-table pass):
  strong candidates found for most of the previously-unresolved entries,
  pending the U1 title+units+shape+category cross-check:**
  - Max PR → `IP_PQ_CHA_MAX` ("Maximum allowed pressure quotient at turbo
    charger compressor", 8×8, "-") — matches the guide's 8-ambient-row ×
    8-RPM PR table; verify the Y axis is ambient temp.
  - Cylinder head temp setpoint → `CoTE_tHdCtlSp_M_VW` (6×6, °C) plus
    siblings `_v_T_VW` (1×4) and `_agIgRedAvrg_T_VW` (1×5) — check the
    guide screenshot to pick which one(s) the cut-5 rule targets.
  - Compressor temp maps → `C_TIA_THR_TCHA_MAX` / `C_TIA_THR_TCHA_MAX_SP`
    (both (1,1), °C) — the "→ 300" pair candidates.
  - Max requested pressure → `C_PRS_IM_SP_MAX` ("Maximum allowed
    PRS_IM_SP", (1,1), hPa) — also a `FLOAT_BUG_SYMBOLS` member.
  - Max allowed airmass → `C_M_AIR_CYL_SP_MAX` ("Maximum allowed
    M_AIR_CYL_SP", (1,1), mg/stk) — also a `FLOAT_BUG_SYMBOLS` member.
  - Overboost limit → `C_PRS_IM_SP_LIM` ("Offset to the pressure behind air
    cleaner for the limitation of the manifold setpoint", (1,1), hPa) —
    plausible but the title reads as an offset-over-baro, not an absolute;
    confirm by reading the stock value against the guide's stock screenshot
    before trusting the 2700 target.
  - Max reference indicated engine torque → `IP_TQI_REF_MAX_MON` ((1,7),
    Nm) — resolvable for *reporting*, but stays skipped-vague (guide gives
    no number).
  - Pedal-feel (skipped-vague) → `IP_FAC_TQ_REQ_DRIV_H_VS_DCT` /
    `..._L_VS_DCT` (12×12) — resolvable for reporting only.
  - Lambda → `IP_LAMB_BAS`, `IP_LAMB_BAS_HPDI[1]`, `IP_LAMB_BAS_MPI[1]`
    (8×12, "-"); full-load enrichment family (`IP_LAMB_FL_SP`,
    `IP_LAMB_FL_SP_TIA`, `IP_LAMB_OHP_EXT`) are the candidates for the
    fueling-influence / heavy-throttle entries — needs per-table matching
    against the guide's fueling section.
  - Spark IAT correction → `IP_IGA_BAS_TEMP_N_32` ("Basis for temperature
    correction of Basic IGA versus N_32, TIA", 10×10, °CRK) — **confirmed
    decisively 2026-07-07**: stock X axis (608…6080 rpm) matches the
    guide's screenshot exactly, and the stock 80.25 °C row is already
    byte-identical to the author's bottom row. The author's full table is
    transcribed (double-entry verified) into
    `knowledge/ecu-tuning-basics.md`. Two constraints found: (a) the author
    also re-breakpointed the Y axis (35.25 added, 70.5 dropped vs stock);
    (b) the sibling `IP_IGA_REF_TEMP_N_32` (MBT-side) shares identical
    breakpoints, so an axis rewrite would ripple beyond the one table —
    the recipe therefore keeps the stock Y axis and row-maps (see U2). The
    `_REF_` sibling and the NEG/POS weighting-factor tables stay stock.
  - Torque-tune selector → `LC_PUT_SP_TOL_ENA_AMP` ("Use AMP for
    calculation of PUT out of pressure ratio (instead of PRS_CHA_UP)",
    (1,1), unitless) — **confirmed 2026-07-07 from the guide's screenshot**
    `23-torque-tune-selector.png`, whose TunerPro window title reads
    "Pressure Ratio Calc Toggle 1=AMP 0=PRS_CHA_UP" and shows the value set
    to 1.00. The title semantics match the XDF description exactly, the
    title search is a unique hit, and the stock value is 0 (guide sets 1).
    Treatment: `literal_scalar`, target 1.
  - **Still no candidate found:** the 2× max intake air tables (only
    unrelated MAF thresholds matched). These remain genuinely unresolved
    and fail safe (reported, never written).
- **Several guide tables did not resolve to a confident symbol via this
  session's keyword search** — Max PR (Turbo Max Pressure Ratio), wastegate
  flow-factor tables (out of scope anyway), cylinder head temp setpoint,
  compressor temp maps, max requested pressure, max allowed airmass, and the
  two max-intake-air tables. This is expected: the guide's plain-English
  names don't always match the XDF's internal naming, and confirming a match
  needs the same title+units+shape+category cross-check used above, done
  carefully per table rather than assumed. **This drives Key Decision 1**
  below — a dedicated, checked-in symbol-mapping step precedes any write
  logic, and any table that doesn't clear the cross-check is treated exactly
  like a "vague guide instruction" (skip + report, never guessed).

## Key Technical Decisions

1. **Symbol mapping is its own artifact, resolved once and reviewed, not
   inlined as string literals scattered through the recipe.** A single
   module-level table (guide section → one or more XDF symbols → target
   value/curve → treatment) is the one place recipe authors and reviewers
   check "does this symbol really mean what the guide says." Any entry that
   can't be confirmed by title+units+shape+category cross-check (per Research
   Findings) is marked unresolved and the recipe skips it with the same
   "needs manual value — see guide" reporting used for vague guide text —
   unresolved-symbol and vague-instruction are the same failure mode from the
   report's point of view.
2. **The recipe is a plain function over an already-open `CalFile`, not a
   new `CalFile` method or a CLI.** `apply_basics_sop(cal) -> RecipeReport`
   takes a caller-supplied `CalFile` (already opened against the stock bin +
   XDF) and stages edits via the existing `TableView.set`/`set_cell` API —
   consistent with how Phase 2 (export) and Phase 3 (visualization) added
   pure functions on top of Phase 1 rather than new `CalFile` surface.
3. **Guard pattern is a small shared helper, not special-cased per table.**
   A `_guarded_ceiling_write(view, ..., target, current_limit_check)` helper
   reads the current value, applies only if the guard condition holds, and
   returns a per-table outcome (`applied` / `already_satisfied` /
   `guarded_skip`) for the report — `already_satisfied` covers current ==
   target (no write staged, not a guard failure). Reused for Overboost limit
   and any other "raise this limiter" edit that shares the same
   irreversible-if-overshot shape (per requirements doc Key Decision 3/AE2).
   Edits that aren't a ceiling-raise (e.g. flattening Max PR to 2.80, cutting
   5 from cylinder head temp cells) don't go through this helper — they use
   plain `set`/`set_cell` since there's no analogous irreversibility risk
   documented for them.
   Relatedly, existing-safety-layer interactions are report outcomes, not
   crashes: several in-scope limiter writes (350,000 / 2000 / 2700) land on
   `safety.FLOAT_BUG_SYMBOLS` constants, whose guard raises
   `FloatBugGuardError` unconditionally on an over-limit write. The recipe
   catches per-entry `FloatBugGuardError` (and `RawRangeError`) and records a
   distinct `guard_blocked` outcome with the error text — one table's guard
   never aborts the rest of the recipe, and never passes silently. Any
   `EditRangeWarning` emitted by a successful write is captured into that
   entry's report detail string.
4. **TTA/ATT build-out is a small numeric helper, not literal cell values.**
   Since the guide gives no complete table for these (Research Findings),
   the recipe computes, per table, a linear extension of the existing
   torque↔airmass relationship above 400 Nm/mg-stk (fit or extrapolate from
   the table's own un-touched rows), rather than copying the author's
   specific row edits. This is inherently an approximation and is labeled as
   such in the report (distinct outcome from "applied literal value").
5. **Report is a plain dataclass list, not a new file format.** `RecipeReport`
   is a list of per-table outcome records (symbol, guide section, outcome,
   old/new value or curve, reason if skipped). Rendered to a human-readable
   summary (e.g. printed or written as text/Markdown) by a thin formatting
   function — no new persistence layer, no schema to version.
6. **Comparison PNGs reuse Phase 3 verbatim — which means scalars get no
   PNG.** For every table with outcome `applied` (literal or build-out), the
   recipe (or the demo script wrapping it) calls `render_table()` before
   mutation and `compare_tables()` after, writing into a dedicated output
   directory — no new plotting code. `compare_tables` produces nothing for
   (1,1) tables by design, and a large share of the applied edits are
   scalars (all four speed-limiter values, both turbo shaft limiters, the
   torque-tune selector, the float-bug limiter constants). Those are
   reviewed via the report's old→new values — AE5 coverage is therefore
   scoped to non-scalar changed tables, since a before/after PNG of a single
   number adds nothing over the report line and satisfying it literally
   would require the new plotting logic AE5 itself forbids.
7. **Output location and naming mirror the `demos/` convention.** A demo
   script (`Code/demos/apply_sop_recipe.py`) drives
   `CalFile.open` → `apply_basics_sop` → `save(correct_checksums=True)` →
   `verify_checksums()` → report + comparison PNGs, matching how
   `demos/export_cal.py` and `demos/plot_cal.py` already wrap library calls
   for this specific car's bin/XDF. The library logic itself
   (`apply_basics_sop`, the symbol map, the report type) lives in
   `simoscal/` so it's importable and testable independent of the demo.
8. **No new runtime dependencies.** Everything needed (edit API, checksum
   verify, `compare_tables`) already exists in `simoscal`; this phase adds no
   new library.

## High-Level Technical Design

```
Symbol map (data)                       simoscal/sop_recipe.py
guide section → symbol(s) →                    │
  target value/curve → treatment                │
        │                                        │
        ▼                                        ▼
apply_basics_sop(cal) -> RecipeReport   ───► for each symbol-map entry:
                                               resolved? no  → report: unresolved (U1)
                                               resolved? yes:
                                                 ceiling-raise? → _guarded_ceiling_write (U3)
                                                 TTA/ATT?       → build-out helper (U4)
                                                 else           → set/set_cell (U2)
        │
        ▼
RecipeReport (per-table outcomes)  ──►  format_report() (U5)
        │
        ▼
Code/demos/apply_sop_recipe.py (U6)
  CalFile.open → apply_basics_sop → save(correct_checksums=True)
  → verify_checksums() → write report → compare_tables/compare_bins PNGs
```

## Implementation Units

### U1. Symbol map + resolution
- **Goal:** A single, reviewable data structure mapping every guide
  instruction (in-scope and explicitly-skipped) to its XDF symbol(s) — or to
  "unresolved" when the cross-check in Research Findings can't confirm one —
  plus the lookup logic that resolves it against a live `CalFile`.
- **Requirements:** Key Decision 1; requirements doc's full "In scope" /
  "Out of scope" tables; AE4 (every table accounted for).
- **Dependencies:** none (Phase 1–3 complete).
- **Files:** `Code/simoscal/sop_recipe.py` (new — symbol-map data + a
  `resolve_symbol_map(cal)` function), `Code/tests/test_sop_recipe.py` (new).
- **Approach:** The map is a list of small records: `guide_section`,
  `description`, `symbols` (tuple, possibly empty when unresolved),
  `kind` (`literal_table` / `literal_scalar` / `axis_write` /
  `guarded_ceiling` / `tta_att_buildout` / `skip_log_dependent` /
  `skip_vague`), and enough of a
  target spec (a value, a curve as row/column labels + cells, or a cut/offset
  rule) to drive the write step. Every guide instruction named in the
  requirements doc's "In scope" and "Out of scope" tables gets exactly one
  entry, so nothing falls through uncategorized (AE4). `resolve_symbol_map(
  cal)` looks up each entry's `symbols` against `cal.get()`/`cal.search()`
  and raises nothing — an unresolved or missing symbol becomes part of the
  data (kind stays whatever was declared; a separate `resolved: bool` field
  flips false), so resolution failures are data, not exceptions. Note
  `cal.get()` raises `KeyError` on a missing key and `AmbiguousTableError`
  on a multi-match; the resolver catches both, and an ambiguous match gets
  its own reason string (it's a different failure than "missing" and needs
  a different fix — disambiguation, not discovery).
  Resolution lead for the "unresolved" limiter constants:
  `safety.FLOAT_BUG_SYMBOLS` (`safety.py`) already grounds four float32
  boost/airmass-ceiling constants against this exact XDF (`C_M_AIR_CYL_FL`,
  `C_M_AIR_CYL_SP_MAX`, `C_PRS_IM_SP_LIM`, `C_PRS_IM_SP_MAX`) — by the
  guide's own float-bug list these should cover max requested pressure and
  max allowed airmass (plus the overboost pressure-setpoint pair). Start the
  title+units+shape+category cross-check from those symbols rather than a
  fresh keyword search.
- **Test scenarios:** Happy — every entry in the map has a non-empty
  `guide_section` and a valid `kind`. Happy — resolving against the real
  `cal` confirms the Research-Findings-verified symbols (`IP_PUT_SP`,
  `LMVLim_vMax_vLim_C_VW.*`, `C_N_TCHA_MAX*`, `IP_TQ_POW_MAX_*`,
  `IP_IGA_BAS_IVVT_VVL_PORT_H[STND]*`, TTA/ATT symbol families) resolve
  successfully with the expected shape/units. Edge — an entry whose declared
  symbol doesn't exist in `cal` resolves with `resolved=False`, not a
  crash. Integration — every `skip_*`-kind entry has no symbols required
  (or is explicitly marked not-applicable), confirming skip entries aren't
  silently expected to resolve.
- **Verification:** the real-file resolution test shows every
  Research-Findings-confirmed symbol resolving; unresolved entries (Max PR,
  cylinder head temp setpoint, compressor temp maps, max requested pressure,
  max allowed airmass, 2× max intake air — none confirmed this session) are
  explicitly flagged `resolved=False` rather than guessed, and a human
  (implementer, at U1 completion) does the title+units+shape+category
  cross-check from Research Findings on each one before deciding whether it
  graduates to a literal entry or stays a documented "needs manual value."

### U2. Literal-value write path
- **Goal:** Apply every `literal_table` / `literal_scalar` entry (Max Torque
  at Clutch, PUT setpoint curve, Max PR flatten, torque-tune selector, Basic
  Ignition Angle — written to all 9 `_PORT_L[STND]` tables, Spark IAT
  correction, fueling-influence/heavy-throttle/lambda tables, cylinder
  head temp cut-5 rule, and the non-guarded limiter values) via the existing
  `TableView.set`/`set_cell` API.
- **Requirements:** Requirements doc "In scope" table (all non-guarded,
  non-TTA/ATT rows); AE1.
- **Dependencies:** U1 (consumes the resolved symbol map).
- **Files:** `Code/simoscal/sop_recipe.py` (add the literal-write step),
  `Code/tests/test_sop_recipe.py`.
- **Approach:** For a `literal_table` entry, values are matched to the
  table's own axis breakpoints (not blindly positional) so a bin whose axes
  differ slightly from the guide's example bin fails loud (existing
  `simoscal` range/shape behavior) rather than silently writing to the wrong
  cell. The cylinder head temp "cut 5 from everything over 90" rule is
  expressed as a small transform (read current values, subtract 5 where
  >90) rather than a literal target grid, since the guide states it as a
  rule, not a table.
  **`axis_write` treatment (2026-07-07, from the empirical PUT finding):**
  the PUT setpoint entry is a paired write — one cell in the axis table
  `ldp_map_sp_ip_put_sp` (last breakpoint 2500.05 → 2698.97) plus the 6
  last-row cells of `IP_PUT_SP`. Axis tables are ordinary XDF tables, so
  the existing `set_cell` path applies, but with two extra guards: (a) the
  implementer must confirm at U1 that no *other* table shares
  `ldp_map_sp_ip_put_sp` as its axis (a shared-axis write would silently
  re-breakpoint tables outside the recipe — if shared, the entry degrades
  to `unresolved`, never written); (b) the new breakpoint must keep the
  axis strictly monotonic. This is the only `axis_write` entry — the Spark
  IAT and TTA/ATT entries deliberately avoid axis writes (IAT's axis is
  shared with its `_REF_` sibling; TTA's stock axis already reaches 550 Nm).
  Two multi-target/row-mapped literal entries (2026-07-07 amendments):
  - **Basic Ignition Angle:** one literal target grid (the guide's
    Intake 0/Exhaust 0 starting values), written identically to all 9
    `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` tables. One symbol-map entry
    with 9 symbols; the report records each of the 9 individually.
  - **Spark IAT correction (`IP_IGA_BAS_TEMP_N_32`):** the author's table
    is **row-mapped onto the stock Y breakpoints** — no axis write, since
    the Y axis is shared with the `_REF_` sibling. Stock rows −30…30 °C →
    0.00 (kills the cold-timing add); stock rows 40.5 / 50.25 / 60 / 80.25
    → the author's rows at those same breakpoints (80.25 is already
    identical → no-op); the stock **70.5 row is left untouched and
    reported** ("kept at stock — author's table has no 70.5 breakpoint"),
    never interpolated. The author's 35.25 row (all zeros) has no stock
    counterpart and is dropped; with the stock axis the zero region runs
    through 30 °C and pulls start at 40.5 °C, matching the author's
    "don't pull until 40 °C" intent.
- **Test scenarios:** Happy — against the mini fixture, a literal 2D
  table entry writes exactly the declared values at the declared axis
  breakpoints. Happy — a literal scalar entry (e.g. torque-tune selector)
  writes the single value. Edge — the cylinder-head cut-5 rule leaves cells
  ≤90 untouched and reduces cells >90 by exactly 5. Happy — the Basic
  Ignition Angle entry writes the identical grid to all 9 `_PORT_L[STND]`
  tables and none of the `_PORT_H` or `[LFT_1]` siblings change. Edge — the
  Spark IAT row-mapping writes author rows only at matching stock Y
  breakpoints, leaves the 70.5 row byte-identical to stock, and reports it.
  Error — an axis mismatch
  between the entry's declared breakpoints and the table's actual axis
  raises rather than writing to a mismatched cell (relies on existing
  `simoscal` behavior — this test confirms the recipe doesn't swallow or
  reinterpret that error). Error — a write to a `FLOAT_BUG_SYMBOLS` table
  that trips `FloatBugGuardError` is recorded as `guard_blocked` with the
  error text, the table stays byte-identical, and the recipe continues to
  the next entry (per Key Decision 3). Edge — a write that emits
  `EditRangeWarning` still applies, and the warning text lands in that
  entry's report detail. Integration — running the full literal-write step
  against the real `cal` and reading back every written table confirms exact
  match to the requirements doc's literal values.
- **Verification:** every literal-kind entry's post-write value matches the
  requirements doc exactly (AE1) on the real bin; the axis-mismatch error
  path is exercised, not just assumed.

### U3. Guarded ceiling-write helper
- **Goal:** A shared helper for "raise this limiter, but never touch it if
  it's already past the ceiling" edits (Overboost limit named explicitly;
  reused for any other entry sharing that shape).
- **Requirements:** Requirements doc Key Decision 3; AE2.
- **Dependencies:** U1.
- **Files:** `Code/simoscal/sop_recipe.py` (add
  `_guarded_ceiling_write`), `Code/tests/test_sop_recipe.py`.
- **Approach:** Reads the table's current value(s) first; writes the target
  only if current ≤ target (per guide: "if already >2700, don't touch"),
  otherwise records a `guarded_skip` outcome with the current value in the
  report — never writes a lower value over a higher one.
- **Test scenarios:** Happy — current value below target: writes target,
  outcome `applied`. Edge — current value already above target: no write
  occurs (table byte-identical after the call), outcome `guarded_skip` with
  the observed current value recorded. Edge — current value exactly equal to
  target: no write staged (byte-identical under minimal-diff anyway),
  outcome `already_satisfied` — not re-written, not flagged as a
  skip-due-to-guard. Integration — run
  against the real Overboost limit symbol (once resolved in U1) and confirm
  the guard fires correctly against its actual stock value.
- **Verification:** AE2 passes — a bin whose Overboost limit already exceeds
  2700 comes out of the recipe byte-identical for that table, reported as
  guarded-and-skipped, not applied.

### U4. TTA/ATT proportional build-out
- **Goal:** Extend each TTA/ATT table's existing near-linear torque↔airmass
  relationship above 400 Nm/mg-stk, approximating the guide's "build it out"
  instruction without copying literal values that don't apply to this bin.
- **Requirements:** Requirements doc Key Decision 2b; "In scope" TTA/ATT row.
- **Dependencies:** U1.
- **Files:** `Code/simoscal/sop_recipe.py` (add the build-out helper),
  `Code/tests/test_sop_recipe.py`.
- **Approach:** For each resolved TTA/ATT table, fit a linear relationship
  from the rows/cells at or below 400 (left untouched per the guide) and
  extrapolate that same slope into the higher rows, keeping TTA and its
  paired ATT table consistent (guide's DSG-clutch-clamping rationale) by
  deriving both from the same fitted relationship. Flagged in the report
  with outcome `applied_buildout` (distinct from `applied` literal writes)
  so a reviewer knows this table's new values are a derived approximation,
  not a guide-literal number. Empirical note (2026-07-07): the stock TTA
  axis already has rows to 550 Nm with populated, roughly-linear values —
  the build-out may reduce to verifying linearity and making small
  adjustments (or none), which the fit-and-compare logic handles naturally;
  an `already_satisfied`-style outcome is fine here.
- **Test scenarios:** Happy — a synthetic near-linear TTA table (fixture)
  build-out extends the fitted line correctly above 400, and rows ≤400 stay
  byte-identical. Happy — the paired ATT table's build-out stays consistent
  with its TTA counterpart (same fitted relationship applied). Edge — a
  table whose sub-400 rows are not well-approximated by a line (low
  R²/fit-residual) is flagged in the report rather than silently written
  with a poor fit. Integration — run against a real TTA/ATT symbol pair from
  U1 and visually sanity-check (via U6's comparison PNGs) that the built-out
  region continues the pre-400 trend smoothly.
- **Verification:** rows ≤400 nm/mg-stk are unchanged; the build-out’s slope
  matches the pre-400 fit; poor-fit tables are reported, not silently
  applied.

### U5. `RecipeReport` + formatting
- **Goal:** Collect every table's outcome across U2–U4 into one structured
  report and render it human-readably.
- **Requirements:** Key Decision 5; AE4.
- **Dependencies:** U1–U4 (consumes their outcomes).
- **Files:** `Code/simoscal/sop_recipe.py` (add `RecipeReport`,
  `format_report()`), `Code/simoscal/__init__.py` (export
  `apply_basics_sop`, `RecipeReport`, `format_report`),
  `Code/tests/test_sop_recipe.py`.
- **Approach:** `RecipeReport` is a frozen dataclass wrapping a tuple of
  per-table outcome records (symbol, guide section, outcome enum, detail
  string, old/new value or curve where applicable). `format_report()`
  renders a Markdown table grouped by outcome (applied / applied_buildout /
  already_satisfied / guarded_skip / guard_blocked / skip_log_dependent /
  skip_vague / unresolved) — no new file format, just a string the demo
  script (U6) writes to disk. For scalar (1,1) entries the old→new values in
  the report are the review artifact (no PNG exists for them; Key Decision
  6), so the formatter always includes them for applied scalar outcomes.
  **Coherence section (2026-07-07):** the tune is a coupled system, but the
  recipe applies entries independently — so `format_report()` opens with a
  coherence check that flags **DO NOT FLASH** when dependent entries
  diverge: boost curve applied without the fueling entries (lean risk),
  without the Max PR flatten (PR cap defeats the curve), without the
  torque-tune selector (Option 2 not activated), or fueling applied without
  boost (harmless, noted only). Rules are a small declared list alongside
  the symbol map, not scattered logic. A report with any DO-NOT-FLASH line
  still saves the bin (the human gate decides), but the warning is the
  first thing printed.
- **Test scenarios:** Happy — a report built from a handful of synthetic
  outcomes renders a Markdown table with the right grouping and counts.
  Integration — `apply_basics_sop(cal)` on the real `cal` returns a report
  whose entries collectively cover every guide instruction named in the
  requirements doc's "In scope" and "Out of scope" tables (AE4), with none
  missing.
- **Verification:** AE4 passes on the real bin — the report accounts for
  every named table/instruction, no silent gaps.

### U6. Demo script + full pipeline (save/verify/compare) + acceptance suite
- **Goal:** Wire U1–U5 behind `apply_basics_sop(cal) -> RecipeReport`, add
  the demo script that drives the full load→apply→save→verify→report→compare
  pipeline against the real bin, and prove AE1–AE5 end-to-end.
- **Requirements:** AE1–AE5; Key Decisions 6–7; README documentation.
- **Dependencies:** U1, U2, U3, U4, U5.
- **Files:** `Code/simoscal/sop_recipe.py` (add `apply_basics_sop()`
  orchestrating U1–U4 and returning the U5 report),
  `Code/demos/apply_sop_recipe.py` (new), `Code/tests/test_acceptance_sop.py`
  (new, mirrors the existing `test_acceptance*.py` real-file skip pattern),
  `Code/README.md` (document the recipe module in the existing
  API-surface-table style).
- **Approach:** `apply_basics_sop(cal)` runs symbol resolution (U1), then
  each write kind's step (U2–U4) in the order the guide presents them (torque
  request → TTA/ATT → boost → timing → fueling → cooling → limiters),
  returning the assembled `RecipeReport` (U5) without saving anything itself
  — saving/verifying/writing the report and PNGs to disk is the demo
  script's job, keeping the library function pure (stages edits on the
  `CalFile` passed in, doesn't touch the filesystem). The demo script opens
  the stock bin, then snapshots pre-edit `RenderedTable`s via
  `render_table()` for every candidate write target — it can't know the
  final outcomes before applying, so it calls the exposed
  `resolve_symbol_map(cal)` itself and snapshots every resolved entry with a
  write-kind (`literal_*` / `guarded_ceiling` / `tta_att_buildout`);
  snapshots whose entry ends up skipped are simply discarded. It then calls
  `apply_basics_sop`, saves with
  `correct_checksums=True`, verifies checksums, writes the formatted report,
  and generates `compare_tables()` PNGs per changed table into a dedicated
  output directory.
- **Test scenarios (mapped to requirements doc AEs):** AE1 — every
  `literal`/`literal_scalar`/`applied_buildout`-kind table matches its
  expected value/curve exactly on the real bin; every skip/unresolved-kind
  table is byte-identical to stock. AE2 — Overboost-limit guard behavior on
  the real bin's actual current value. AE3 — `verify_checksums()` reports
  clean after `save(correct_checksums=True)`. AE4 — report accounts for
  every named instruction. AE5 — a comparison PNG exists for every
  non-scalar table with outcome `applied` or `applied_buildout`; scalar
  (1,1) applied entries instead assert the report records their old→new
  values (`compare_tables` produces no PNG for scalars by design — Key
  Decision 6).
- **Verification:** the acceptance suite (AE1–AE5) passes against the real
  bin/XDF (skips cleanly if absent, per existing convention); the demo
  script run produces a saved bin, a Markdown report, and a PNG directory;
  README documents the new module's public API.

## Iteration Model (2026-07-07, explicit per user direction)

This recipe produces **revision 0 of the tune — a starting point, not a
finished calibration.** The intended workflow is a loop:

```
recipe → review (report + PNGs) → flash → log → review logs → iterate
```

Expected per the guide on the first logged pulls: PUT deviating from
setpoint up top (wastegate flow factors are stock — the guide's method for
them is log-driven by design), possible P0234/limp if overboost is
aggressive, and airmass not exactly matching TTA cells (spark-efficiency
effect — normal). Iteration targets, in rough order: wastegate flow
factors from PUT-vs-target deviation, timing from consistent multi-cylinder
knock corrections at specific airmass/RPM cells, then boost-curve shaping
to taste.

Consequences for this phase's design (no new units, just framing):

- The recipe stays **deterministic and re-runnable**: it always starts from
  the stock bin and applies the full symbol map, so a re-run after a map
  adjustment (e.g. a timing cell eased after a knock log) regenerates the
  whole output cleanly rather than layering edits on an edited bin. Manual
  per-iteration tweaks belong in the symbol map's target values, keeping
  every revision reviewable in one place.
- The demo script's output directory is the per-revision review artifact
  (bin + report + PNGs together); keep prior runs' directories rather than
  overwriting, so revisions can be compared (`compare_bins` works across
  any two saved bins).
- Log ingestion itself (parsing SimosTools/datalogs, computing PUT
  deviation, suggesting wastegate flow-factor changes) is **Phase 4**, per
  `Code/README.md` — deferred, not designed here.

## Scope Boundaries

**In:** symbol mapping + resolution, literal-value writes, guarded ceiling
writes, TTA/ATT proportional build-out, a structured report, comparison PNGs,
a demo script driving the full pipeline, an acceptance suite (AE1–AE5).

**Out (per requirements doc, retained):** a general config-driven tuning
tool; wastegate flow-factor automation from a datalog; IS38/V30/LB6/ethanol/
DSG-fart/pops-and-bangs variants; flashing.

### Deferred to Follow-Up Work
- Resolving the remaining unconfirmed symbols (Max PR, cylinder head temp
  setpoint, compressor temp maps, max requested pressure, max allowed
  airmass, 2× max intake air tables) — flagged in U1 as a required
  implementer step (title+units+shape+category cross-check) before those
  entries can graduate from "unresolved" to "literal," rather than pre-
  resolved in this plan.
- A datalog-ingestion path enabling wastegate flow-factor automation — noted
  in the requirements doc as a candidate for the datalog-driven Phase 4
  already called out in `Code/README.md`.

## Open Questions

None blocking *implementation*. ~~Torque-tune selector~~ — **resolved
2026-07-07**: `LC_PUT_SP_TOL_ENA_AMP`, confirmed from the guide's
screenshot title (see Research Findings); the former flash gate is closed.
Remaining item, gating flash-worthiness of individual entries only:

- Exact symbols for a handful of limiter/cooling tables — scoped into U1 as
  implementer work with a defined verification method (title+units+shape+
  category cross-check against the guide text). Candidates for most were
  identified in the 2026-07-07 sweep; any that stay unconfirmed are
  reported, not written.

## Risks & Dependencies

- **Guide values may not byte-for-byte match this bin's stock baseline.**
  The guide's example values are from *an* example bin (requirements doc
  Outstanding Questions). The comparison PNGs + checksum verification (U6)
  are the intended catch, per the requirements doc's Key Decision 1 — not
  addressed by new pre-flight validation in this plan.
- **TTA/ATT build-out is inherently approximate** (Key Decision 4/U4). A
  poor linear fit on a given table is reported, not silently written, but
  the overall approach trades literal accuracy for applicability to this
  specific bin — an accepted tradeoff per the requirements doc.
- **Symbol resolution risk concentrated in U1.** Because several guide
  tables didn't resolve to a confirmed symbol during this planning session's
  research, U1 carries more open verification work than a typical first
  unit. Sequencing it first (before any write logic) means resolution
  ambiguity surfaces early rather than discovered mid-implementation.

## Sources & Research

- `Docs/brainstorms/2026-07-06-sop-tune-recipe-requirements.md` — origin
  requirements doc for this plan.
- `knowledge/ecu-tuning-basics.md` — the guide being scripted (already
  ingested from `Docs/3. ECU Tuning - Basics.docx`; not reopened).
- `Code/README.md`, `Docs/plans/2026-07-06-001-feat-xdf-export-module-plan.md`
  — existing plan/README conventions this plan follows (Implementation Unit
  structure, API-surface-table documentation style, `demos/` wrapping
  pattern).
- Empirical queries against the real `CalFile`
  (`xdf/SC8S50.V1.0.xdf` + `bin/5G0906259L__0002.bin`) via
  `cal.categories()`, `cal.search()`, and category-filtered
  `cal.unique_tables()`: confirmed category taxonomy matches guide section
  structure; confirmed concrete symbols for Max Torque at Clutch, TTA, ATT,
  PUT setpoint, Basic Ignition Angle, Speed Limiter, Turbo shaft speed
  limiter, and Charge air pressure too high (see Research Findings); found
  no confident match this session for Max PR, wastegate (out of scope
  anyway), cylinder head temp setpoint, compressor temp maps, max requested
  pressure, max allowed airmass, or the two max-intake-air tables.
