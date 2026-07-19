# Sonnet-Thorough sandbox — R07 base-timing advance

This folder is a sandboxed addition only. It does not modify any file outside
`Tunes/TuningBasicsGuide/Test/Sonnet-Thorough/`. It builds on the real,
unmodified `TUNE_Basics_Guide_R06.py` pipeline (imported read-only) and adds
one new overlay: a small, conservative base-timing advance, per the request
"increase base timing to be more aggressive to make a little more power."

## What changed

`TUNE_Basics_Guide_R07_SonnetThorough.py` runs the full R06 pipeline
unchanged, then advances exactly 4 cells (rpm, load mg/stk) in each of the 9
active `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle,
VVL 0 Port Flap Low tables, by a flat **+0.75 deg**:

| rpm  | load (mg/stk) | R06 value | R07 value | delta  |
|------|----------------|-----------|-----------|--------|
| 6000 | 1200           | 1.875     | 2.625     | +0.750 |
| 6500 | 1200           | 3.375     | 4.125     | +0.750 |
| 6000 | 1400           | 1.875     | 2.625     | +0.750 |
| 6500 | 1400           | 3.375     | 4.125     | +0.750 |

36 cells total (4 cells x 9 tables). All 9 tables carried identical stock
values at these cells, so the same 4-cell delta applies to all 9.

## Why these cells, why this size

- All 4 cells were **untouched by R04/R05/R06** — confirmed by asserting them
  against `R04_TIMING_TARGETS` in code (script refuses to run if a target
  collides with an R04 knock-retard cell) and by direct bin diff (see below).
  None of the 15 cells R04 pulled/blended in response to real logged knock are
  touched, forward or backward.
- Sizing anchors to what R04 **already validated at the same RPM columns**:
  R04's own blend cells at (6000 rpm, 900 mg/stk) and (6500 rpm, 900 mg/stk)
  are +2.625 deg and +4.875 deg. R07 brings the higher-load, still-stock cells
  at those same two RPM columns (1200 and 1400 mg/stk rows) up to 2.625 deg
  and 4.125 deg — the 6000 rpm cells now match the R04-validated value at that
  RPM; the 6500 rpm cells stay 0.75 deg *below* the R04-validated value at that
  RPM (conservative, since these rows carry more load).
- Falls inside the guide's own documented "safe starting curve" (
  `knowledge/ecu-tuning-basics.md`, Timing section: "meandering up to ~+3-5
  deg by 6500 rpm").
- +0.75 deg = exactly 2 storage steps at this table's 8-bit / (1/2.6667
  deg-per-step) resolution — representable with zero rounding error.
- These 4 cells are real, logged WOT operating territory: the 2026-07-08 R04
  validation log's two pulls reached 6312-6674 rpm at 918-1491 mg/stk.

## Verification performed

1. **Script run**: `python3 TUNE_Basics_Guide_R07_SonnetThorough.py` completed
   with `checksums: CLEAN (CAL_CRC, ECM3)` and "Coherence check passed" (144
   table outcomes: 90 applied, 48 applied_buildout, 6 skipped — same shape as
   R06's own report, plus the 9 new R07 timing rows).
2. **Full-bin diff vs a fresh in-memory R06 build**: called
   `CalFile.unique_tables()` on both a freshly-built R06-equivalent bin and the
   R07 bin (3814 unique tables each) and value-compared every one. Result:
   **exactly 9 tables differ** — the 9 `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][*][*]`
   tables, each by a max deviation of exactly 0.75 deg. Every other table
   (limiters, fueling, wastegate, lambda, axes, etc.) is untouched.
3. **Re-opened the saved .bin from disk** (not the in-memory object) and
   re-diffed just the 9 timing tables cell-by-cell against the R06 build.
   Confirmed **exactly 4 changed cells per table** (36 total), each landing at
   the intended value with **zero storage error**: 1.8750->2.6250 and
   3.3750->4.1250, both exact.
4. Checksums (`CAL_CRC`, `ECM3`) verified clean on the saved bin via
   `cal.verify_checksums()`.

## Caveats / what this is NOT

- **Unvalidated by any log.** No flash/log cycle exists for these 4 cells.
  Per this project's own iteration philosophy (tune, flash, log, review,
  iterate), this is a starting hypothesis, not a proven-safe calibration.
- The R04 log review's own "Recommended Next Calibration Changes" pointed
  toward boost-overshoot work next, not more timing. This overlay honors an
  explicit user request for more base timing but does not have log support of
  its own — flag this to the car's owner explicitly.
- Watch the next log specifically for knock correction at 6000-6500 rpm /
  1200-1400 mg/stk (Knock Cyl 1-4 channels). If any appears, these 4 cells
  should be the first thing reverted, back to the R06 values in the table
  above.
- This sandbox output (`TUNE_Basics_Guide_R07_out/`) is separate from the
  project's real `TUNE_Basics_Guide_out/` — it was not added to the real
  `REV_LOG.md` or promoted to a real `TUNE_Basics_Guide_R07.py`, per this
  run's sandbox constraints. If this is to become the project's actual next
  revision, it should be re-created as `TUNE_Basics_Guide_R07.py` in the
  parent folder with a REV_LOG.md entry, following the R04/R05/R06 pattern.
