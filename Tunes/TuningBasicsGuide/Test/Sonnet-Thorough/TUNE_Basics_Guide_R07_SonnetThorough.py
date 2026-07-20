#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision
R07 (Sonnet-Thorough sandbox variant).

SANDBOX NOTE: this script and its output live entirely under
``Tunes/TuningBasicsGuide/Test/Sonnet-Thorough/`` per this run's constraints. It
does NOT modify any existing file in the repo (not REV_LOG.md, not
Code/simoscal, not the R00-R06 scripts). It imports the R06 pipeline read-only
and adds one new overlay on top, saving to its own output folder.

R07 is based on R06 and runs the EXACT R06 pipeline unchanged (lambda axis
re-breakpoint, R01 limiter/fuelling writes, R03 lambda floors, R04 knock-retard
timing overlay, R05 wastegate feedforward overlay + X-axis re-breakpoint, and
the R06 overboost-limiter symbol-map fix). R07 adds ONE new thing: a small,
conservative BASE-TIMING ADVANCE overlay, requested directly ("increase base
timing to be more aggressive to make a little more power").

**Why this is deliberately small and narrowly scoped.** The 2026-07-08 R04 log
review (`Logs/BasicsGuide_R04/log_review.md`) is the only ignition-focused log
this project has. It explicitly recommends, in its "Recommended Next
Calibration Changes" section:

    "Medium - Do not pull more timing from
    IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2] ... based on this log. The R04
    ignition overlay did what it was intended to do."
    "High - Address boost overshoot next ... If wastegate feedforward
    correction is ambiguous, make a conservative PUT setpoint curve reduction
    in the overshoot regions instead of stacking more timing/load stress."

So the project's own log-driven process points AWAY from touching timing next.
Given the user has explicitly asked for more aggressive base timing anyway,
R07 honors that request but stays inside guardrails that keep it defensible
without a new log:

  1. **Never touch any of the 15 (rpm, load) cells R04 already tuned** in
     response to real logged knock (the diagonal knock-retard ridge plus its
     blend cells). Those are left byte-identical to R06.
  2. **Only touch cells that were still at stock** after R04/R05/R06 — i.e.
     genuinely untuned territory, not a reversal of a knock fix.
  3. **Stay inside the guide's own documented "safe starting curve"** (see
     `knowledge/ecu-tuning-basics.md` sec. "Timing", Exley's curve: negative in
     high-airmass rows until ~4500 rpm, meandering up to ~+3 to +5 deg by 6500
     rpm) rather than inventing a new target.
  4. **Stay at or below what R04 itself already validated at the same RPM
     column.** R04's own blend cells at (6000 rpm, 900 mg/stk) and
     (6500 rpm, 900 mg/stk) advance timing to +2.625 deg and +4.875 deg
     respectively — the calibrator's own judgment of how much timing that RPM
     band can carry. R07 raises the still-stock, higher-load cells at the same
     two RPM columns (1200 and 1400 mg/stk rows) only as far as, or a step
     below, those already-flashed values — never past them.

**The overlay.** In each of the nine active low-port-flap STND timing tables
(`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`), advance exactly 4 cells by a
flat +0.75 deg (2 storage steps at this table's 8-bit, 1/2.6667 deg/step
resolution — representable exactly, no rounding surprise):

    (6000 rpm, 1200 mg/stk):  1.875 -> 2.625 deg   (now equals the R04-validated
                                                     6000 rpm / 900 mg/stk cell)
    (6500 rpm, 1200 mg/stk):  3.375 -> 4.125 deg   (stays 0.75 deg BELOW the
                                                     R04-validated 6500 rpm /
                                                     900 mg/stk cell of 4.875)
    (6000 rpm, 1400 mg/stk):  1.875 -> 2.625 deg   (same reasoning as above)
    (6500 rpm, 1400 mg/stk):  3.375 -> 4.125 deg   (same reasoning as above)

These four cells sit in the top-end of the WOT operating path (the R04 log's
two pulls reached 6312-6674 rpm at 1200-1491 mg/stk — this is real, logged
operating territory, not a corner the car never sees) and were left at their
untouched stock value through R04/R05/R06 (confirmed by diffing against a
fresh R06 bin — see verification below). Advancing them keeps the curve's
existing shape (they were already flat with the row below at 1049.97 mg/stk;
+0.75 deg keeps that same flat relationship, just shifted up slightly) and
does not exceed what the same RPM columns already carry one row down.

36 cells total change (4 cells x 9 tables). Every other table in the bin is
unchanged relative to R06 — verified below with a full `unique_tables()`
value-compare, the same method used for R05/R06's own verification.

**This is still a starting point, not a finished calibration.** These four
cells per table are UNVALIDATED by any log. Flash -> log -> review before
trusting them, exactly like every other revision in this lineage. Watch
specifically for knock correction appearing at 6000-6500 rpm / 1200-1400
mg/stk that was not present in the 2026-07-08 R04 log. If it appears, revert
these four cells first.

Revision history (see the parent REV_LOG.md for R00-R06):
    R00-R06 — see Tunes/TuningBasicsGuide/REV_LOG.md (unmodified, chained
              through as-is; this sandbox script is additive only).
    R07 (this script) — R06 + a 36-cell (+0.75 deg, 4 cells x 9 tables) base
              timing advance at (6000/6500 rpm, 1200/1400 mg/stk), confined to
              cells R04/R05/R06 never touched, sized to stay at/below what R04
              already validated at the same RPM columns. Sandbox-only output
              under Tunes/TuningBasicsGuide/Test/Sonnet-Thorough/.
"""

from __future__ import annotations

import datetime as _dt
import sys
import warnings
from pathlib import Path

import numpy as np

# Make the parent TuningBasicsGuide/ scripts importable (read-only import; this
# does not modify any file there).
_PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PARENT))

from simoscal import (
    CalFile,
    compare_tables,
    format_report,
    render_table,
)
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import (
    OUTCOME_APPLIED,
    RecipeReport,
    TableOutcome,
)

from TUNE_Basics_Guide_R03 import (
    BIN_PATH,
    XDF_PATH,
    _apply_r03_writes,
    _merge_report,
    _rebreakpoint_lambda_family,
)
from TUNE_Basics_Guide_R04 import R04_TIMING_SYMBOLS, _apply_r04_timing_overlay
from TUNE_Basics_Guide_R05 import (
    R05_SUPERSEDES_SECTIONS,
    _apply_r05_wg_axis_rebreakpoint,
    _apply_r05_wg_overlay,
    _snapshot_r05_wg,
)

# apply_basics_sop is re-exported by simoscal but R06's fixed recipe mapping is
# what we need (overboost limiter -> IP_PUT_AMP_DIF_MAX_PRS_DIF_THR). It is
# picked up automatically since sop_recipe.py is shared/unmodified.
from simoscal import apply_basics_sop

# This script's own sandbox output root — never writes outside this folder.
OUT_ROOT = Path(__file__).resolve().parent / "TUNE_Basics_Guide_R07_out"
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R07_SonnetThorough.bin"

# --------------------------------------------------------------------------- #
# R07 base-timing advance overlay
# --------------------------------------------------------------------------- #
R07_SECTION_TIMING = "Timing — R07 base-timing advance overlay (more power)"
R07_TIMING_TITLE = "Basic Ignition Angle, VVL 0 Port Flap Low"

# (rpm, load mg/stk, target deg). Every one of these is a cell R04/R05/R06 never
# touched (confirmed against R04_TIMING_TARGETS below and by direct bin diff).
R07_TIMING_TARGETS = (
    (6000.0, 1200.0, 2.625),
    (6500.0, 1200.0, 4.125),
    (6000.0, 1400.0, 2.625),
    (6500.0, 1400.0, 4.125),
)

_R04_TOUCHED = {(rpm, load) for rpm, load, _ in __import__(
    "TUNE_Basics_Guide_R04"
).R04_TIMING_TARGETS}
for _rpm, _load, _ in R07_TIMING_TARGETS:
    assert (_rpm, _load) not in _R04_TOUCHED, (
        f"R07 target ({_rpm}, {_load}) collides with an R04 knock-retard cell — "
        "refusing to touch a cell that was tuned in response to real knock data."
    )


def _nearest_index(values: np.ndarray, target: float) -> int:
    flat = np.asarray(values, dtype=np.float64).ravel()
    return int(np.argmin(np.abs(flat - target)))


def _snapshot_r07_timing_targets(cal: CalFile) -> dict[str, object]:
    """Snapshot the R06-equivalent timing tables before the R07 overlay."""
    return {sym: render_table(cal.get(sym)) for sym in R04_TIMING_SYMBOLS}


def _apply_r07_timing_overlay(cal: CalFile) -> list[TableOutcome]:
    """Apply the small top-end base-timing advance to all 9 STND IGA tables."""
    outcomes: list[TableOutcome] = []

    for sym in R04_TIMING_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        x_axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()

        changed_cells: list[str] = []
        for rpm, load, target in R07_TIMING_TARGETS:
            x_idx = _nearest_index(x_axis, rpm)
            y_idx = _nearest_index(y_axis, load)
            old = float(values[y_idx, x_idx])
            values[y_idx, x_idx] = target
            changed_cells.append(
                f"{x_axis[x_idx]:.0f} rpm/{y_axis[y_idx]:.0f} mg/stk: "
                f"{old:.3f}->{target:.3f} ({target - old:+.3f})"
            )

        view.set(values)
        outcomes.append(TableOutcome(
            sym,
            R07_SECTION_TIMING,
            OUTCOME_APPLIED,
            detail=(
                f"{sym}  — {R07_TIMING_TITLE}: applied top-end base-timing "
                f"advance (unvalidated by any log — flash/log/review before "
                f"trusting); {'; '.join(changed_cells)}"
            ),
        ))

    return outcomes


def _write_r07_comparison_pngs(cal, snaps, r07_outcomes, png_dir: Path) -> int:
    png_count = 0
    for out in r07_outcomes:
        before = snaps.get(out.symbol)
        if before is None:
            continue
        after = cal.get(out.symbol)
        paths = compare_tables(before, after, png_dir)
        png_count += len(paths)
    return png_count


def build_r07(cal: CalFile):
    """Run the full R06 pipeline plus the new R07 overlay on an open CalFile."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)

        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        r05_snaps = _snapshot_r05_wg(cal)
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

        r07_snaps = _snapshot_r07_timing_targets(cal)
        r07_outcomes = _apply_r07_timing_overlay(cal)

    kept = tuple(
        o for o in (tuple(r03_report.outcomes) + tuple(r04_outcomes))
        if o.guide_section not in R05_SUPERSEDES_SECTIONS
    )
    report = RecipeReport(kept + tuple(r05_outcomes) + tuple(r07_outcomes))
    return report, r07_snaps, r07_outcomes


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R07_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)
    report, r07_snaps, r07_outcomes = build_r07(cal)

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")

    png_count = _write_r07_comparison_pngs(
        cal, r07_snaps, r07_outcomes, out_dir / "compare"
    )

    counts = report.counts()
    print(f"Recipe applied — {len(report.outcomes)} table outcomes:")
    for key in sorted(counts):
        print(f"    {key:18s} {counts[key]}")
    print(f"\n  saved bin      : {out_bin}")
    print(f"  checksums      : {'CLEAN' if clean else 'STALE — NOT flash-ready'}"
          f" ({', '.join(r.name for r in save_reports)})")
    print(f"  report         : {out_dir / 'report.md'}")
    print(f"  comparison PNGs: {png_count} under {out_dir / 'compare'}")
    if report.do_not_flash():
        print("\n  ⛔ DO NOT FLASH — see the report's coherence section. "
              "This is sandbox revision 7; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs, "
              "verify checksums, and get a validating log before flashing. "
              "This is sandbox revision 7 — the timing advance is UNVALIDATED.")


if __name__ == "__main__":
    main()
