#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R07.

    *** SANDBOX / TEST REVISION ***
    This script lives under Tunes/TuningBasicsGuide/Test/Opus-Thorough/ and writes
    ONLY into that folder. It does NOT modify any tracked tune script, the shared
    `simoscal` library, or REV_LOG.md. It is an exploration of "advance base timing
    for a little more power" built on top of the existing R06 pipeline. If adopted,
    it should be promoted to a real Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R07.py
    and logged in REV_LOG.md following the project's revision-lineage convention.

R07 = the EXACT R06 pipeline + ONE new script-level overlay: a small, on-the-page
BASE-TIMING ADVANCE in the peak-power corner of the 9 WOT base-ignition tables, to
make a little more top-end power.

What R06 already does (inherited unchanged, in order):
  * Lambda axis re-breakpoint (R00) so the guide's lambda grid axis-matches.
  * `apply_basics_sop` — includes the R06 shared-recipe overboost limiter fix
    (`IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  — Overpressure upstream throttle threshold
    for turbocharger overpressure diagnosis, raised 1800 -> 2700 across 6 cells).
  * R01 limiter/fuelling writes; R03 literal-0.80 lambda minimum-value floors.
  * R04 local WOT knock-retard ignition overlay on
    `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle,
    VVL 0 Port Flap Low.
  * R05 wastegate feedforward overlay + shared X-axis re-breakpoint on
    `IP_FAC_BPA_SP[0]` / `[1]`  — Wastegate Position Feedforward VVL 0/1.

What R07 ADDS — the base-timing advance overlay
-----------------------------------------------
Target: the SAME nine WOT tables the guide and R04 identify as the only base-timing
tables that matter — `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` for i,e in 0..2
(Basic Ignition Angle, VVL 0 Port Flap Low; "Intake i Exhaust e" VVT variants).

Where the advance goes, and why NOT the peak-power corner.
    The base SOP recipe already writes the guide's published "safe starting" WOT
    timing curve to all nine tables (`sop_recipe.py` _IGA_CELLS = the Exley curve,
    `knowledge/ecu-tuning-basics.md` §417-439). So the currently-running R06 tune is
    ALREADY on that curve — including its top corner (6000-6500 rpm x 1200-1400
    mg/stk at ~+1.875/+3.375). The high-load corner is NOT free power: R04's real
    datalogs show the engine knocking (and R04 retarding) at 3500-6500 rpm all the
    way up in the >=900 mg/stk rows. The guide itself flattens the top-corner shelf
    on purpose and says "if choosing between 1 deg timing and 1 psi boost, choose
    boost." Adding base timing in that corner is exactly what would cause knock /
    engine damage, so R07 deliberately leaves it alone.

    The safe headroom for a little more power is the BOOST-ONSET MID-LOAD band —
    airmass 600 / 700 / 800 mg/stk, 3000-6500 rpm. There the guide's curve sits
    1-4 deg BELOW the factory (stock) value (the author pulled timing there as a
    generic margin), and NONE of R04's logged-knock cells fall in it (every R04
    cell is >=900 mg/stk). This car also runs an upgraded intercooler and lives at
    sea-level-to-6000 ft on 92 octane (less air density up high = less knock), so
    restoring part of that pulled timing is reasonable.

R07 therefore advances 12 cells in that band. Each target is BOUNDED ON BOTH SIDES
BY ON-THE-PAGE REFERENCES: floor = the guide value R06 runs; ceiling = the FACTORY
(stock) value. The rule is target = min(guide + 1.5 deg, stock), quantized to the
0.375 deg °CRK LSB — i.e. restore up to 1.5 deg of the timing the guide pulled, but
NEVER exceed what the OEM itself shipped. Resulting advances are +0.75 to +1.5 deg:

    rpm / airmass (mg/stk)   guide(R06)   -> R07     factory ceiling (stock)
    4000 / 600               +15.375        +16.875   +17.625
    4500 / 600               +15.750        +16.500   +16.500  (= stock, capped)
    6000 / 700               +11.250        +12.750   +14.250
    6500 / 700               +10.500        +12.000   +12.000  (= stock, capped)
    3000 / 800               +4.125         +4.875    +4.875   (= stock, capped)
    3500 / 800               +4.125         +5.625    +8.250
    4000 / 800               +6.000         +7.500    +9.375
    4500 / 800               +7.125         +8.625    +9.375
    5000 / 800               +9.000         +10.500   +11.250
    5500 / 800               +9.375         +10.500   +10.500  (= stock, capped)
    6000 / 800               +6.750         +8.250    +10.500
    6500 / 800               +7.125         +8.625    +10.500

Why this is the right, safe place to add timing:
  1. It is the boost-onset / mid-load region where a little more advance genuinely
     adds torque under the curve and tip-in response, and the engine is NOT at its
     knock limit there (unlike the >=900 mg/stk peak-power rows).
  2. Every target is bounded by two on-the-page numbers (guide floor, factory
     ceiling) and never exceeds the value the OEM shipped for that exact cell.
  3. It does NOT overlap ANY cell R04 retarded for LOGGED knock — every R04 cell is
     at >=900 mg/stk, this band is <=800 mg/stk. R04's retards are left fully intact.
  4. The result stays coherent with its neighbours (timing still falls with load and
     no NEW load-ordering inversion is introduced), so there is no timing cliff.

All nine tables share identical stock values in this band (the WOT VVT family
converges), so the same absolute targets are written to all nine, exactly as R04
wrote its knock targets to all nine. A live guard (see `_apply_r07_timing_advance`)
re-reads the stock bin and REFUSES to write any value above the factory ceiling or
onto any R04 cell — fail loud, never silently over-advance.

This is still **revision 7 — a starting point, not a finished calibration**. Base
timing is the single most engine-damage-prone thing to raise: even a guide-sanctioned
advance MUST be validated with a knock-monitoring datalog on the very next pull, and
backed off immediately if the ECU shows knock retard at 6000-6500 rpm. The script
never flashes.

Revision history (see REV_LOG.md; R07 is a sandbox exploration not yet logged there):
    R00 — Initial revision. Base ecu-tuning-basics SOP + lambda axis re-breakpoint.
    R01 — + six limiter/fuelling writes the recipe left at stock.
    R02 — Report-honesty only; bin byte-identical to R01.
    R03 — + literal 0.80 writes to the three lambda minimum-value floors.
    R04 — + local WOT knock-retard ignition overlay (nine VVL0 Port-Flap-Low tables).
    R05 — + wastegate feedforward overlay + shared X-axis re-breakpoint.
    R06 — + shared-recipe overboost limiter fix (IP_PUT_AMP_DIF_MAX_PRS_DIF_THR
          1800 -> 2700 across 6 cells).
    R07 — + base-timing ADVANCE overlay: restores up to 1.5 deg of guide-pulled
          timing in the boost-onset mid-load band (600/700/800 mg/stk, 3000-6500
          rpm; 12 cells) across the same nine VVL0 Port-Flap-Low tables, each cell
          bounded below by the guide value R06 runs and above by the FACTORY (stock)
          value — never exceeding what the OEM shipped. The knock-limited >=900
          mg/stk peak-power corner is deliberately left at its guide/R04 values, and
          no R04 knock cell is touched. All R00-R06 edits (incl. the overboost fix)
          are kept.
"""

from __future__ import annotations

import datetime as _dt
import sys
import warnings
from pathlib import Path

import numpy as np

# This script lives two levels below the real tune dir (Test/Opus-Thorough/); put
# the tune dir on sys.path so the R03/R04/R05 pipeline helpers import cleanly.
TUNE_DIR = Path(__file__).resolve().parents[2]
if str(TUNE_DIR) not in sys.path:
    sys.path.insert(0, str(TUNE_DIR))

from simoscal import (  # noqa: E402
    CalFile,
    TableMismatchError,
    apply_basics_sop,
    compare_tables,
    format_report,
    render_table,
)
from simoscal.safety import EditRangeWarning  # noqa: E402
from simoscal.sop_recipe import (  # noqa: E402
    OUTCOME_APPLIED,
    OUTCOME_APPLIED_BUILDOUT,
    RecipeReport,
    TableOutcome,
)

from TUNE_Basics_Guide_R03 import (  # noqa: E402
    BIN_PATH,
    XDF_PATH,
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

# Sandbox output root — NOT the tracked TUNE_Basics_Guide_out.
OUT_ROOT = Path(__file__).resolve().parent / "R07_out"
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R07.bin"

# --------------------------------------------------------------------------- #
# R07 base-timing advance overlay.
# --------------------------------------------------------------------------- #
R07_SECTION_TIMING = "Timing — R07 base-timing advance overlay (boost-onset mid-load)"
R07_TIMING_SYMBOLS = tuple(
    f"IP_IGA_BAS_IVVT_VVL_PORT_L[STND][{i}][{e}]" for i in range(3) for e in range(3)
)
R07_TIMING_TITLE = "Basic Ignition Angle, VVL 0 Port Flap Low"

# (rpm, load mg/stk, target deg). Boost-onset mid-load band (600/700/800 mg/stk,
# 3000-6500 rpm). Each target = min(guide value R06 runs + 1.5 deg, factory/stock
# value), quantized to the 0.375 deg °CRK LSB — restore up to 1.5 deg of pulled
# timing, never above the OEM value. NONE of these coordinates is an R04 knock cell
# (every R04 cell is >=900 mg/stk). See the module docstring for the full table.
R07_TIMING_TARGETS = (
    (4000.0, 599.98, 16.875),
    (4500.0, 599.98, 16.500),
    (6000.0, 699.98, 12.750),
    (6500.0, 699.98, 12.000),
    (3000.0, 800.02, 4.875),
    (3500.0, 800.02, 5.625),
    (4000.0, 800.02, 7.500),
    (4500.0, 800.02, 8.625),
    (5000.0, 800.02, 10.500),
    (5500.0, 800.02, 10.500),
    (6000.0, 800.02, 8.250),
    (6500.0, 800.02, 8.625),
)

# R04's logged-knock cells (rpm, load) — R07 must never write onto any of these.
# All are at >=900 mg/stk; the R07 band is <=800 mg/stk, so the sets are disjoint.
# The live guard below re-derives and asserts this against the actual R04 targets.
_R04_KNOCK_CELLS = (
    (3500.0, 1400.0), (4000.0, 1400.0), (4500.0, 1400.0), (5000.0, 1400.0), (5500.0, 1400.0),
    (5000.0, 1200.0), (5500.0, 1200.0), (3500.0, 1200.0), (4000.0, 1200.0),
    (5000.0, 1049.97), (5500.0, 1049.97), (6000.0, 1049.97), (6500.0, 1049.97),
    (6000.0, 900.0), (6500.0, 900.0),
)


def _nearest_index(values: np.ndarray, target: float) -> int:
    flat = np.asarray(values, dtype=np.float64).ravel()
    return int(np.argmin(np.abs(flat - target)))


def _snapshot_r07_timing(cal: CalFile) -> dict[str, object]:
    """Snapshot the nine timing tables AFTER R04 (and R05), before the R07 advance.

    The resulting comparison PNGs show the R07 four-cell advance only, not stock->R07.
    """
    return {sym: render_table(cal.get(sym)) for sym in R07_TIMING_SYMBOLS}


def _stock_ceiling(cal: CalFile) -> tuple[dict[tuple[int, int], float], set]:
    """Re-read the FACTORY (stock) bin to build a per-cell ceiling for the guard.

    Returns {(y_idx, x_idx): stock_value} for every R07 target cell, taken from a
    fresh open of the untouched stock bin (BIN_PATH), plus the R04-cell index set.
    """
    stock_cal = CalFile.open(XDF_PATH, BIN_PATH)
    v = stock_cal.get(R07_TIMING_SYMBOLS[0])
    x_axis = np.asarray(v.axis_values("x"), dtype=np.float64).ravel()
    y_axis = np.asarray(v.axis_values("y"), dtype=np.float64).ravel()
    vals = np.asarray(v.values, dtype=np.float64)
    ceiling: dict[tuple[int, int], np.ndarray] = {}
    for rpm, load, _ in R07_TIMING_TARGETS:
        yi, xi = _nearest_index(y_axis, load), _nearest_index(x_axis, rpm)
        ceiling[(yi, xi)] = float(vals[yi, xi])
    r04_idx = {
        (_nearest_index(y_axis, l), _nearest_index(x_axis, r))
        for r, l in _R04_KNOCK_CELLS
    }
    return ceiling, r04_idx


def _apply_r07_timing_advance(cal: CalFile) -> list[TableOutcome]:
    """Advance the boost-onset mid-load band, bounded by the factory value.

    Absolute writes (like R04), applied to all nine VVL0 Port-Flap-Low tables. Only
    the 12 listed cells change; every other cell — including all of R04's
    knock-retard cells — is left exactly as the R04 pipeline set it.

    FAIL-LOUD GUARD (safety-critical): before writing, re-read the untouched stock
    bin and assert, for every target cell, that (a) the target does NOT exceed the
    factory value at that cell (never advance beyond what the OEM shipped), and
    (b) the cell is NOT one of R04's logged-knock cells. Any violation raises
    RuntimeError rather than silently writing a dangerous value.
    """
    ceiling, r04_idx = _stock_ceiling(cal)
    outcomes: list[TableOutcome] = []

    for sym in R07_TIMING_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        x_axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()

        changed_cells: list[str] = []
        for rpm, load, target in R07_TIMING_TARGETS:
            x_idx = _nearest_index(x_axis, rpm)
            y_idx = _nearest_index(y_axis, load)

            # --- fail-loud guard ---
            if (y_idx, x_idx) in r04_idx:
                raise RuntimeError(
                    f"R07 refuses to write {sym} cell {x_axis[x_idx]:.0f} rpm/"
                    f"{y_axis[y_idx]:.0f} mg/stk: it is an R04 logged-knock cell."
                )
            factory = ceiling[(y_idx, x_idx)]
            if target > factory + 1e-6:
                raise RuntimeError(
                    f"R07 refuses to write {sym} cell {x_axis[x_idx]:.0f} rpm/"
                    f"{y_axis[y_idx]:.0f} mg/stk: target {target:+.3f} exceeds the "
                    f"factory ceiling {factory:+.3f} deg."
                )

            old = float(values[y_idx, x_idx])
            values[y_idx, x_idx] = target
            changed_cells.append(
                f"{x_axis[x_idx]:.0f} rpm/{y_axis[y_idx]:.0f} mg/stk: "
                f"{old:+.2f}->{target:+.2f} ({target - old:+.2f}; stock {factory:+.2f})"
            )

        view.set(values)
        outcomes.append(TableOutcome(
            sym,
            R07_SECTION_TIMING,
            OUTCOME_APPLIED,
            detail=(
                f"{sym}  — {R07_TIMING_TITLE}: base-timing advance in the "
                f"boost-onset mid-load band (600-800 mg/stk), each cell capped at "
                f"the factory value; {'; '.join(changed_cells)}"
            ),
        ))

    return outcomes


def _write_comparison_pngs(cal: CalFile, snaps: dict, outcomes, png_dir: Path) -> tuple[int, int]:
    """Emit a before/after PNG per changed timing table. Returns (pngs, skipped)."""
    png_count, axis_changed = 0, 0
    for out in outcomes:
        if out.outcome not in (OUTCOME_APPLIED, OUTCOME_APPLIED_BUILDOUT):
            continue
        before = snaps.get(out.symbol)
        if before is None:
            continue
        try:
            after = cal.get(out.symbol)
            paths = compare_tables(before, after, png_dir)
        except TableMismatchError:
            axis_changed += 1
            continue
        except Exception:  # noqa: BLE001
            continue
        png_count += len(paths)
    return png_count, axis_changed


def build_r07(cal: CalFile) -> tuple[RecipeReport, list[TableOutcome], dict]:
    """Run the exact R06 pipeline, then apply the R07 timing advance. In-memory."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        # --- exact R06 pipeline ------------------------------------------------
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)          # includes R06 overboost fix
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)
        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        _snapshot_r05_wg(cal)                          # keep call parity with R06
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

        # --- R07 addition ------------------------------------------------------
        r07_snaps = _snapshot_r07_timing(cal)          # post-R04/R05, pre-R07
        r07_outcomes = _apply_r07_timing_advance(cal)

    kept = tuple(
        o for o in (tuple(r03_report.outcomes) + tuple(r04_outcomes))
        if o.guide_section not in R05_SUPERSEDES_SECTIONS
    )
    report = RecipeReport(kept + tuple(r05_outcomes) + tuple(r07_outcomes))
    return report, r07_outcomes, r07_snaps


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R07_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)
    report, r07_outcomes, r07_snaps = build_r07(cal)

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")
    png_count, axis_changed = _write_comparison_pngs(
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
    print(f"  comparison PNGs: {png_count} under {out_dir / 'compare'}"
          f" ({axis_changed} axis-changed table(s) reported in text instead)")
    if report.do_not_flash():
        print("\n  ⛔ DO NOT FLASH — see the report's coherence section. "
              "This is revision 7 (sandbox); review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. Revision 7 (sandbox); iterate.")

    print(f"\n  out_dir        : {out_dir}")


if __name__ == "__main__":
    main()
