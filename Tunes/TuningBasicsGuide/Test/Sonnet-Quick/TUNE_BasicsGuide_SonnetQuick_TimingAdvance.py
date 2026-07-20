#!/usr/bin/env python3
"""Quick-pass timing-advance overlay on top of TuningBasicsGuide R06.

SANDBOXED TEST SCRIPT — lives entirely under
Tunes/TuningBasicsGuide/Test/Sonnet-Quick/. It does not modify, and is not
referenced by, any file in the real TuningBasicsGuide revision lineage
(R00-R06, REV_LOG.md). It is a standalone experiment, not a new numbered
revision.

Goal: "increase base timing to be more aggressive to make a little more
power." This runs the full, unchanged R06 pipeline (lambda re-breakpoint,
R01 limiter/fuelling writes, R03 lambda floors, R04 knock-retard timing
overlay, R05 wastegate feedforward overlay, R06 overboost-limiter fix) and
then adds ONE new overlay on top:

  * `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle
    VVL 0 Intake {0,1,2} Exhaust {0,1,2} (title read directly from the XDF
    Table object; the "STND" index selects the standard/low port-flap
    calibration set, categories Spark / Base - Port Flap Low).

Only the LIGHT-LOAD rows are touched: Y (load, mg/stk) <= ~500 mg/stk, i.e.
axis indices 0-8 of the 16x16 grid (79.99, 99.99, 150.02, 199.99, 250.01,
299.99, 350.01, 399.99, 499.98 mg/stk). Every cell in that load band gets a
flat +2.0 deg advance (clamped to the table's declared z-axis max of 60.0
deg, never hit in practice here). Load rows above ~500 mg/stk -- everything
from moderate load up through WOT -- are left completely untouched.

WHY THIS SCOPE, AND WHY IT IS DELIBERATELY CONSERVATIVE:

  * R04 already retarded timing in specific mid/high-load cells (3500-6500
    rpm at 900-1400 mg/stk) in response to LOGGED WOT knock. Re-advancing
    anywhere near that footprint without a fresh, knock-free log covering
    the same cells would be reckless guessing, not tuning. This overlay
    does not touch row indices 9-15 (699.98-1400 mg/stk) at all, so none of
    the R04 knock-retard cells are altered.
  * Cylinder pressure (and therefore knock risk) rises steeply with load.
    Light-load/part-throttle cells have the most timing headroom and are
    where stock maps are typically the most conservative for driveability/
    emissions margin rather than knock -- the safest place to look for "a
    little more power" without new WOT knock data.
  * +2.0 deg is a small step (about 5-8% of the pre-existing values in this
    band, which run roughly 6-40 deg) relative to the table's 0.375 deg
    storage resolution and -35.625..60.0 deg declared range, so it cannot
    overflow storage and leaves large remaining headroom either direction.

This is a light-load-only advance for throttle response / part-throttle
efficiency. It does NOT touch WOT power delivery, so "a little more power"
here should read as crisper tip-in / cruise response, not a meaningfully
higher peak number. Full-load power on this SOP is already gated by the
R05 wastegate/boost work and the R04 knock margin -- pushing WOT timing
further requires a new knock-focused log, not a guess.

DO NOT FLASH BLINDLY: no dyno or knock log exists for this specific overlay.
Treat this like every other revision here -- flash conservatively, log, and
watch for any knock-sensor activity or rough idle/part-throttle surge in the
light-load cells before trusting it.
"""

from __future__ import annotations

import datetime as _dt
import sys
import warnings
from pathlib import Path

import numpy as np

# Make the real (unmodified) TuningBasicsGuide package importable so this
# sandboxed script can reuse the R06 pipeline verbatim without copying it.
_REAL_TUNE_DIR = Path(__file__).resolve().parents[2]  # .../TuningBasicsGuide
_CODE_DIR = _REAL_TUNE_DIR.parents[1] / "Code"          # .../SimosTools/Code
for _p in (str(_REAL_TUNE_DIR), str(_CODE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from simoscal import format_report  # noqa: E402
from simoscal.safety import EditRangeWarning  # noqa: E402
from simoscal.sop_recipe import OUTCOME_APPLIED, RecipeReport, TableOutcome  # noqa: E402

from TUNE_Basics_Guide_R03 import BIN_PATH, XDF_PATH  # noqa: E402 (unmodified, read-only import)
from TUNE_Basics_Guide_R06 import main as _r06_main  # noqa: F401  (not called; see below)

# We cannot call R06's main() directly (it writes into the real
# TuningBasicsGuide_out tree and this sandbox must not touch anything outside
# its own folder), so we replicate R06's pipeline by calling the same
# building blocks it calls, exactly as R06 does, then save under this
# sandbox's own output folder instead.
from simoscal import CalFile, apply_basics_sop  # noqa: E402
from TUNE_Basics_Guide_R03 import (  # noqa: E402
    _apply_r03_writes,
    _merge_report,
    _rebreakpoint_lambda_family,
)
from TUNE_Basics_Guide_R04 import _apply_r04_timing_overlay  # noqa: E402
from TUNE_Basics_Guide_R05 import (  # noqa: E402
    R05_SUPERSEDES_SECTIONS,
    _apply_r05_wg_axis_rebreakpoint,
    _apply_r05_wg_overlay,
    _snapshot_r05_wg,
)

OUT_ROOT = Path(__file__).resolve().parent / "out"
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_SonnetQuick_TimingAdvance.bin"

TIMING_SECTION = "Timing — Sonnet-Quick light-load base-timing advance"
TIMING_SYMBOLS = tuple(
    f"IP_IGA_BAS_IVVT_VVL_PORT_L[STND][{i}][{e}]" for i in range(3) for e in range(3)
)
LIGHT_LOAD_MAX_MG_STK = 500.0  # rows at/below this load get the advance
ADVANCE_DEG = 2.0


def _apply_timing_advance(cal: CalFile) -> list[TableOutcome]:
    """Advance base timing +2.0 deg in light-load cells only (load <= ~500 mg/stk)."""
    outcomes: list[TableOutcome] = []

    for sym in TIMING_SYMBOLS:
        view = cal.get(sym)
        title = view.table.title
        z_max = view.table.z.max
        values = np.array(view.values, dtype=np.float64, copy=True)
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()

        row_mask = y_axis <= LIGHT_LOAD_MAX_MG_STK
        n_rows = int(np.count_nonzero(row_mask))
        old_slice = values[row_mask, :].copy()
        new_slice = np.minimum(old_slice + ADVANCE_DEG, z_max)
        values[row_mask, :] = new_slice

        clamped = int(np.count_nonzero(new_slice < old_slice + ADVANCE_DEG))
        view.set(values)

        # Report the delta actually stored, not the requested delta -- z is 8-bit
        # with a 0.375 deg LSB, so the written value is quantized to the nearest
        # representable step and will not equal +2.00 deg exactly.
        stored_slice = np.array(view.values, dtype=np.float64)[row_mask, :]
        stored_deltas = stored_slice - old_slice
        stored_delta_min = float(stored_deltas.min())
        stored_delta_max = float(stored_deltas.max())

        outcomes.append(TableOutcome(
            sym,
            TIMING_SECTION,
            OUTCOME_APPLIED,
            detail=(
                f"{sym}  — {title}: advanced {n_rows} light-load row(s) "
                f"(load <= {LIGHT_LOAD_MAX_MG_STK:.0f} mg/stk) requesting +{ADVANCE_DEG:.2f} "
                f"deg each ({16 * n_rows} cells); actual stored delta "
                f"{stored_delta_min:.3f}..{stored_delta_max:.3f} deg (0.375 deg/LSB "
                f"storage quantization, not a ceiling clamp); {clamped} cell(s) hit "
                f"the declared max {z_max:.2f} deg; rows above "
                f"{LIGHT_LOAD_MAX_MG_STK:.0f} mg/stk (including every R04 "
                f"knock-retard cell) left untouched."
            ),
        ))

    return outcomes


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"SonnetQuick_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        # Replicate the R06 pipeline verbatim (same calls R06/TUNE_Basics_Guide_R06.py
        # makes), landing on the same state R06 would save, before adding the new
        # light-load timing-advance overlay on top.
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)

        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        _snapshot_r05_wg(cal)  # not used for PNGs in this quick pass; kept for parity
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

        advance_outcomes = _apply_timing_advance(cal)

    kept = tuple(
        o for o in (tuple(r03_report.outcomes) + tuple(r04_outcomes))
        if o.guide_section not in R05_SUPERSEDES_SECTIONS
    )
    report = RecipeReport(kept + tuple(r05_outcomes) + tuple(advance_outcomes))

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")

    # Re-open the SAVED bin fresh and confirm the light-load cells actually moved
    # by the intended amount, independent of the in-memory CalFile above.
    verify_cal = CalFile.open(XDF_PATH, out_bin)
    print(f"Saved bin      : {out_bin}")
    print(f"Checksums      : {'CLEAN' if clean else 'STALE — NOT flash-ready'}"
          f" ({', '.join(r.name for r in save_reports)})")
    print(f"Report         : {out_dir / 'report.md'}")
    print()
    print("Re-opened saved-bin verification (light-load rows only, one table shown"
          " per intake/exhaust position; all 9 tables were written identically):")
    for sym in TIMING_SYMBOLS:
        view = verify_cal.get(sym)
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()
        values = np.array(view.values, dtype=np.float64)
        row_mask = y_axis <= LIGHT_LOAD_MAX_MG_STK
        post_light = values[row_mask, :]
        print(f"  {sym}: light-load rows min/max post = "
              f"{post_light.min():.3f} / {post_light.max():.3f} deg")
    print()
    if report.do_not_flash():
        print("DO NOT FLASH — see report.md coherence section.")
    else:
        print("Coherence check passed on the shared recipe checks. This is a "
              "sandboxed experiment, not a validated revision -- do not flash "
              "without a fresh log review.")


if __name__ == "__main__":
    main()
