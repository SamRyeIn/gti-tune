# Fix hand-off: overboost limiter is mapped to the wrong symbol

**Date:** 2026-07-09
**Owner to hand to:** a coding agent with repo access (fresh context assumed — everything needed is in this doc)
**Scope:** one recipe entry + its writer + two tests, then regenerate the tune output
**Stakes:** this recipe writes real ECU `.bin` files that get flashed. A wrong
limiter value can brick the ECU or damage the engine. Fail loud, verify at the
byte level, never silently lower a limiter. See memory `simostools-safety-stakes`.

---

## 1. What's wrong (root cause)

The SOP recipe maps **"Limiters — Overboost limit → 2700"** to the symbol
`C_PRS_IM_SP_LIM`. That is the **wrong table**.

- `C_PRS_IM_SP_LIM` — XDF title *"Offset to the pressure behind air cleaner for
  the limitation of the manifold setpoint"*. It is a **float32** manifold-setpoint
  pressure limit, a sibling of `C_PRS_IM_SP_MAX` (adjacent addresses `0x9ca8` vs
  `0x9cac`). Stock value on `5G0906259L__0002.bin` = **271695.8 hPa**. It is **not**
  the overboost limit. Because stock (271696) already exceeds the 2700 target, the
  guarded-ceiling writer correctly **guarded-skips** it — so today the recipe does
  nothing here and the real overboost table is never touched.

- The **real overboost table** is `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — XDF title
  *"Overpressure upstream throttle threshold for Turbocharger overpressure
  diagnosis"* (this is the P0234 overboost diagnosis). It is a **1×6 int16 hPa**
  map, stock = **~1799.97 hPa in all six cells**, and its XDF declared **max =
  2716.96 hPa**. Raising it to 2700 is the intended edit (1800 → 2700), and 2700
  sits just under the hard ceiling — that is what the guide's "never exceed the
  upper limit" warning is about.

This was confirmed three ways: the guide screenshots' TunerPro window title, the
XDF `<title>`/units/shape, and a stock-bin decode. See
`knowledge/ecu-tuning-basics.md` (section "Limiters", overboost entry) and memory
`limiter-xdf-declared-max-wrong.md`, both already corrected to reflect this.

**Evidence you can reproduce** (bin file offset = `0x200000 + XDF address`):

| Symbol                            | XDF addr | Type   | Scale (raw→value)        | Stock (decoded)      | XDF max      |
|-----------------------------------|----------|--------|--------------------------|----------------------|--------------|
| `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  | `0x3570` | int16  | `raw / 12.06017666543982`| ~1799.97 hPa ×6 cells| 2716.96 hPa  |
| `C_PRS_IM_SP_LIM` (wrong one)     | `0x9ca8` | float32| identity                 | 271695.8 hPa         | 10000 (soft) |
| `C_PRS_IM_SP_MAX` (its sibling)   | `0x9cac` | float32| identity                 | 239996.0 hPa         | 10000 (soft) |

Files: XDF `Code/xdf/SC8S50.V1.0.xdf`, stock bin `Code/bin/5G0906259L__0002.bin`.

---

## 2. The fix

### 2a. Repoint the recipe entry

**File:** `Code/simoscal/sop_recipe.py`, the `RecipeEntry` at **lines ~576–587**.

Current:
```python
RecipeEntry(
    guide_section="Limiters — Overboost limit → 2700",
    description="Raise the overboost (P0234) limit to 2700 hPa; never write over a higher value",
    kind=KIND_GUARDED_CEILING,
    symbols=("C_PRS_IM_SP_LIM",),  # candidate only — see reason; resolver will accept, U3 guards
    target=2700.0,
    reason=(
        "C_PRS_IM_SP_LIM is an OFFSET-to-baro constant whose stock value does "
        "not match the guide's overboost-limit screenshot; treated as a "
        "guarded raise, but flagged for manual confirmation before flashing."
    ),
),
```

Change `symbols` to the correct table and drop the now-obsolete `reason`
caveat (replace with a one-line note recording the correction + the hard cap):
```python
RecipeEntry(
    guide_section="Limiters — Overboost limit → 2700",
    description="Raise the overboost (P0234) limit to 2700 hPa across all cells; never lower a higher cell",
    kind=KIND_GUARDED_CEILING,          # see 2b — must broadcast across all 6 cells
    symbols=("IP_PUT_AMP_DIF_MAX_PRS_DIF_THR",),
    target=2700.0,
    reason=(
        "Overpressure-upstream-throttle threshold (P0234), 1x6 int16 hPa, stock "
        "~1800. XDF hard max is 2716.96 hPa, so 2700 is intentionally just under "
        "the ceiling — do not exceed. (Corrected 2026-07-09 from C_PRS_IM_SP_LIM, "
        "which is a manifold-setpoint limit, not overboost.)"
    ),
),
```

Confirm the recipe's symbol resolver accepts `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`
against the cal (it exists in the XDF; verify it loads).

### 2b. Fix the writer so it covers all six cells (IMPORTANT)

`KIND_GUARDED_CEILING` is handled by `_guarded_ceiling_write` at **line ~1042**.
That function only reads and writes **cell (0,0)**:
```python
current = float(view.values.ravel()[0])   # first cell only
...
view.set_cell(0, 0, target)               # writes first cell only
```
This was fine for the 1×1 constant `C_PRS_IM_SP_LIM`, but
`IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` is **1×6**. A bare symbol swap would raise one
cell and leave the other five at ~1800 — a silent, wrong tune.

Make the guarded-ceiling write operate over **every cell**, preserving the
"never lower" semantics:
- For each cell: write `target` only where `cell < target - tol`; leave cells at
  or above `target` untouched (never lower).
- Overall outcome: `applied` if ≥1 cell was raised; `already_satisfied` if all
  cells already equal target; `guarded_skip` (byte-identical) if all cells are
  already ≥ target and none equal it.
- Keep the existing `FloatBugGuardError` → `guard_blocked` handling and the `tol`
  logic. Report `old`/`new` sensibly for a map (e.g. min→target, or per-cell
  detail).
- Do **not** write above the table's XDF declared max. 2700 < 2716.96 so this is
  fine, but the writer/guard must still reject an over-max value rather than
  overflow the int16.

Either extend `_guarded_ceiling_write` to broadcast (cleanest — it keeps the
never-lower guard that plain `KIND_LITERAL_BROADCAST` lacks), or add a new
`KIND_GUARDED_BROADCAST` and point the entry at it. Prefer extending the existing
function so all guarded-ceiling entries (turbo speed, compressor temp, etc.)
become cell-correct for free; those are 1×1 today so behavior is unchanged for
them.

---

## 3. Update the tests (they currently assert the *wrong* behavior)

Two tests encode the old mis-mapping and will fail after the fix — update them,
don't delete the coverage:

- **`Code/tests/test_sop_recipe.py:485`** `test_overboost_candidate_guarded_skip`
  — currently asserts `C_PRS_IM_SP_LIM` stays byte-identical / `GUARDED_SKIP`.
  Rewrite to assert the overboost entry now targets
  `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` and **applies** 1800→2700 across **all 6 cells**
  (outcome `APPLIED`; every cell == 2700 within tolerance).

- **`Code/tests/test_acceptance_sop.py:124`** `test_overboost_guarded_skip_byte_identical`
  (acceptance AE2) — same swap: overboost is now `APPLIED`, not `GUARDED_SKIP`.

**Keep AE2's "never-lower guard" coverage alive.** No real guarded-ceiling limiter
is stock-above-target anymore (turbo speed 189k<220k, compressor temp 185<300,
overboost 1800<2700 all apply). Add a dedicated never-lower test with a **synthetic**
setup: pre-write a cell above `target` (e.g. set an overboost cell to 3000), run
the guarded write, and assert that cell is left unchanged while cells below target
are raised. That preserves the AE2 guarantee independent of stock values.

---

## 4. Regenerate the tune output and verify

1. Re-run the tune recipe that includes the limiters (the shared recipe list in
   `sop_recipe.py` drives `Tunes/TuningBasicsGuide/`). Produce a fresh output dir.
2. In the new `report.md`, confirm:
   - `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` appears under **applied** with `1799.97 →
     2700` (or equivalent) — check the change count reflects **6 cells**.
   - `C_PRS_IM_SP_LIM` is **no longer targeted** by the overboost entry (it should
     not appear as a guarded_skip for overboost anymore).
   - The coherence check still passes.
3. Byte-level verify: decode `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` from the new bin and
   confirm all six cells decode to 2700 hPa (raw = 2700 × 12.06018 ≈ 32562), and
   that no other table changed vs the prior output except this one. Use the
   library's value-compare (see memory `tune-bin-verification`: byte offset =
   `0x200000 + XDF address`; `CAL_CRC` at `0x200304`).
4. Run the suites: `pytest Code/tests/test_sop_recipe.py Code/tests/test_acceptance_sop.py`.
5. Update `Tunes/TuningBasicsGuide/REV_LOG.md` with a one-line entry: overboost
   limiter repointed from `C_PRS_IM_SP_LIM` to `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`;
   the previous `R05_20260709-145551` output is now stale (overboost was never
   applied there). Regenerate/supersede as appropriate.

---

## 5. Do NOT do (out of scope / open question)

- **Do not invent a value for `C_PRS_IM_SP_LIM`.** The guide does not call for
  changing it. It is a manifold-setpoint limit (sibling of `C_PRS_IM_SP_MAX`,
  which the guide raises to 350000). Whether `C_PRS_IM_SP_LIM` should *also* be
  raised is an **open question for Sam** — flag it, don't guess. It must not be
  left set to 2700.
- Do not touch any other limiter mapping; the rest of the recipe's symbols were
  cross-checked against the R05 report and are correct.

## Source-of-truth references
- Guide: `knowledge/ecu-tuning-basics.md` — "Limiters" section (quick-ref + prose),
  overboost entry, both corrected 2026-07-09.
- Memory: `limiter-xdf-declared-max-wrong.md` — corrected to name
  `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` as the overboost table.
- Prior (buggy) output: `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_out/R05_20260709-145551/report.md`
  — see its `guarded_skip (1)` row for `C_PRS_IM_SP_LIM`, the symptom of this bug.
