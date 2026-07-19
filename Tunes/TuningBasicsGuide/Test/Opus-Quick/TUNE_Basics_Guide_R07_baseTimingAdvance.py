#!/usr/bin/env python3
"""QUICK-PASS base-timing advance on top of the R06 pipeline (sandbox / Test).

This is a time-boxed experiment written under Tunes/TuningBasicsGuide/Test/Opus-Quick/.
It does NOT touch any existing file, the shared recipe, or the REV_LOG. It reuses
the existing R03/R04/R05/R06 helpers verbatim by import.

Goal (user): "increase base timing to be more aggressive to make a little more
power."

What it does
------------
Runs the EXACT R06 saved-bin pipeline (lambda re-breakpoint, R01 limiter/fuelling
writes, R03 lambda floors, R04 knock-retard timing overlay, R05 wastegate
feedforward overlay + X-axis re-breakpoint, and the R06 corrected overboost
limiter), then adds ONE new overlay of its own:

  * A flat +1.0 deg ignition ADVANCE applied to the WOT / high-load region of the
    nine active low-port-flap standard base-ignition tables
    `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle,
    VVL 0 Port Flap Low.

Why this table family
---------------------
This is the same base-ignition family the existing R04 analysis and the real WOT
datalogs land in — the ECU's base spark-advance map that the WOT torque path reads
before knock correction. Advancing it is the literal "more aggressive base timing"
the user asked for. Keeping the change inside this one family keeps the blast
radius tight and consistent with every prior revision.

Region and knock protection (the important part)
------------------------------------------------
1. The advance is applied ONLY in the WOT power region: rpm >= 2500 AND
   load >= 500 mg/stk. Low-rpm / part-load cells are left alone — that is where
   knock is worst and where advance buys the least power.
2. Every cell that R04 deliberately RETARDED for observed WOT knock
   (the `R04_TIMING_TARGETS` (rpm, load) pockets) is SKIPPED — this overlay never
   re-advances a knock cell, so R04's knock protection is fully preserved. This is
   done by resolving each R04 target to its nearest (rpm, load) index and masking
   those indices out before advancing.

The +1.0 deg step is intentionally small and uniform: enough to be a real "little
more power" nudge on a knock-tolerant day, small enough to stay conservative on a
knock-limited engine. It is a revision-0 experiment, not a finished calibration.
"""

from __future__ import annotations

import datetime as _dt
import sys
import warnings
from pathlib import Path

import numpy as np

# This script lives at Tunes/TuningBasicsGuide/Test/Opus-Quick/, so add the guide
# directory (where the R0x sibling scripts live) to the import path. The library
# itself (simoscal) is on the venv's site-packages.
GUIDE_DIR = Path(__file__).resolve().parents[2]
if str(GUIDE_DIR) not in sys.path:
    sys.path.insert(0, str(GUIDE_DIR))

from simoscal import CalFile, apply_basics_sop, format_report, render_table
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import OUTCOME_APPLIED, RecipeReport, TableOutcome

# Reuse the whole existing pipeline verbatim — no existing file is modified.
from TUNE_Basics_Guide_R03 import (
    BIN_PATH,
    XDF_PATH,
    _apply_r03_writes,
    _merge_report,
    _rebreakpoint_lambda_family,
)
from TUNE_Basics_Guide_R04 import (
    R04_TIMING_TARGETS,
    _apply_r04_timing_overlay,
)
from TUNE_Basics_Guide_R05 import (
    R05_SUPERSEDES_SECTIONS,
    _apply_r05_wg_axis_rebreakpoint,
    _apply_r05_wg_overlay,
)

# Write ONLY under the sandbox folder this script lives in.
OUT_ROOT = Path(__file__).resolve().parent / "out"
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R07_baseTimingAdvance.bin"

# ---- base-timing advance overlay parameters -------------------------------- #
BT_SECTION = "Timing — R07 base-timing advance (Opus quick pass)"
BT_SYMBOLS = tuple(
    f"IP_IGA_BAS_IVVT_VVL_PORT_L[STND][{i}][{e}]" for i in range(3) for e in range(3)
)
BT_TITLE = "Basic Ignition Angle, VVL 0 Port Flap Low"
BT_ADVANCE_DEG = 1.0        # flat ignition advance to add (more positive = more advance)
BT_RPM_MIN = 2500.0         # only advance the WOT power band, not low-rpm lugging
BT_LOAD_MIN = 500.0         # only advance high load (mg/stk); part-load left at stock


def _nearest_index(values: np.ndarray, target: float) -> int:
    flat = np.asarray(values, dtype=np.float64).ravel()
    return int(np.argmin(np.abs(flat - target)))


def _r04_protected_cells(x_axis: np.ndarray, y_axis: np.ndarray) -> set[tuple[int, int]]:
    """(y_idx, x_idx) cells R04 retarded for knock — never re-advanced here."""
    protected: set[tuple[int, int]] = set()
    for rpm, load, _target in R04_TIMING_TARGETS:
        protected.add((_nearest_index(y_axis, load), _nearest_index(x_axis, rpm)))
    return protected


def _apply_base_timing_advance(cal: CalFile) -> list[TableOutcome]:
    outcomes: list[TableOutcome] = []
    for sym in BT_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        x_axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()  # rpm
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()  # load

        protected = _r04_protected_cells(x_axis, y_axis)

        n_cells = 0
        max_delta = 0.0
        for yi, load in enumerate(y_axis):
            if load < BT_LOAD_MIN:
                continue
            for xi, rpm in enumerate(x_axis):
                if rpm < BT_RPM_MIN:
                    continue
                if (yi, xi) in protected:
                    continue  # preserve R04 knock protection
                old = float(values[yi, xi])
                values[yi, xi] = old + BT_ADVANCE_DEG
                n_cells += 1
                max_delta = max(max_delta, abs(values[yi, xi] - old))

        view.set(values)
        outcomes.append(TableOutcome(
            sym,
            BT_SECTION,
            OUTCOME_APPLIED,
            detail=(
                f"{sym}  — {BT_TITLE}: +{BT_ADVANCE_DEG:.2f} deg base-timing advance "
                f"in WOT region (rpm>={BT_RPM_MIN:.0f}, load>={BT_LOAD_MIN:.0f} mg/stk); "
                f"{n_cells} cell(s) advanced, {len(protected)} R04 knock cell(s) preserved"
            ),
        ))
    return outcomes


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R07_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        # ---- exact R06 saved-bin pipeline ---- #
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)            # includes R06 overboost fix
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)    # knock retard first
        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

        # ---- new R07 base-timing advance (after R04, skipping R04 knock cells) ---- #
        bt_snaps = {s: render_table(cal.get(s)) for s in BT_SYMBOLS}
        bt_outcomes = _apply_base_timing_advance(cal)

    kept = tuple(
        o for o in (tuple(r03_report.outcomes) + tuple(r04_outcomes))
        if o.guide_section not in R05_SUPERSEDES_SECTIONS
    )
    report = RecipeReport(kept + tuple(r05_outcomes) + tuple(bt_outcomes))

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")

    counts = report.counts()
    print(f"Recipe applied — {len(report.outcomes)} table outcomes:")
    for key in sorted(counts):
        print(f"    {key:18s} {counts[key]}")
    print(f"\n  saved bin : {out_bin}")
    print(f"  checksums : {'CLEAN' if clean else 'STALE — NOT flash-ready'}"
          f" ({', '.join(r.name for r in save_reports)})")
    print(f"  report    : {out_dir / 'report.md'}")
    if report.do_not_flash():
        print("\n  DO NOT FLASH — coherence check flagged something; review the report.")
    else:
        print("\n  Coherence check passed. STILL review + log before flashing. "
              "This is a revision-0 experiment.")

    # Keep the out_dir path for the verifier.
    (OUT_ROOT / "LATEST").write_text(str(out_dir), encoding="utf-8")


if __name__ == "__main__":
    main()
