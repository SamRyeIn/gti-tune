#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R05.

R05 is based on R04 and keeps every R00-R04 change unchanged (lambda axis
re-breakpoint, the six R01 limiter/fuelling writes, the R03 literal 0.80 lambda
minimum-value floors, and the R04 local WOT knock-retard ignition overlay). It
runs the exact R04 pipeline, then adds ONE new thing:

**R05 = wastegate feedforward boost-tracking overlay.** It lowers cells in the
two wastegate position feedforward tables so the wastegate opens sooner where the
R04 log overboosts:

  * `IP_FAC_BPA_SP[0]`  — Wastegate Position Feedforward, VVL 0 (Map for boost
    pressure actuator setpoint)
  * `IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward, VVL 1 (Map for boost
    pressure actuator setpoint)

Cells = commanded wastegate position (1 = closed, 0 = open); axes are
X = exhaust flow factor, Y = intake flow factor. Per the guide, overboost -> lower
the cell (open the wastegate more), ~0.05 wastegate position per 1 psi off target,
and the SAME cell deltas are applied to BOTH tables (their small pre-existing
VVL0/VVL1 differences are preserved).

R05 also **re-breakpoints the shared X axis last column from Exh flow factor 1.25
to 1.40** (`ldp_fac_1_ip_fac_bpa_sp`, verified used ONLY by these two tables) and
slopes that last column further open. The R04 log reaches Exh flow factor ~1.33,
which clamps against the stock 1.25 endpoint into a flat shelf; moving the endpoint
to 1.40 turns the whole top-end operating range (Exh ~1.00-1.33) into a resolvable,
monotonically-more-open gradient instead. Simulating the ECU's bilinear lookup at
every logged operating point, this opens the wastegate an extra ~0.01-0.02 across
the sustained-overboost, integral-saturated top end while leaving the spool-spike
and all Exh<=1.00 (low-flow) cells byte-identical to the cells-only version. The
axis lives in one shared byte region, so the re-breakpoint applies identically to
both VVL tables by construction. So R05 changes three things relative to R04: the
two `IP_FAC_BPA_SP` Z maps and their shared X-axis breakpoint table. No other
table is touched.

Log analysis (`Logs/BasicsGuide_R04/simostools-2026_07_08-22_10_57.csv`, two
actual-3rd-gear WOT pulls): PUT overshoots PUT SP along a single continuous
diagonal ridge of flow-factor cells, in three severity zones —

  * Spool spike, ~3100-3400 rpm: Exh FF ~0.86-0.91 x Int FF ~0.62-0.74,
    PUT error up to +22.2 kPa (+3.2 psi). Fast transient; the P-D term reacts but
    the integral barely moves.
  * Mid-range, ~3500-5400 rpm (persists after the spike): Exh FF ~0.86-1.27 x
    Int FF ~0.83-1.06, steady PUT error ~+5 to +8 kPa (~+0.7 to +1.2 psi).
  * Top-end, ~5800-6700 rpm: Exh FF ~1.07-1.31 x Int FF ~0.97-1.10, PUT error
    ~+8 to +17 kPa sustained while the wastegate integral saturates toward its
    ~-28% floor and final position drops to ~35% — the closed loop is out of
    authority, so lowering the feedforward base is what actually helps here.

Each edited cell's pull is sized from its measured mean overboost at that
flow-factor cell (heavier at the spool-spike corner and the saturated top-end,
lighter in the mid-range), smoothed along the ridge, with a light upper blend row
to avoid a wastegate-position cliff. Values are conservative (~2/3 of the raw
0.05/psi rule on the transient spike) because this is the first wastegate
revision — flash, log, review, iterate.

This is still **revision 5 — a starting point, not a finished calibration**. The
script never flashes, and a saved bin is not flash-ready while the report shows
DO NOT FLASH.

Revision history (see REV_LOG.md):
    R00 — Initial revision. Base ecu-tuning-basics SOP plus the lambda axis
          re-breakpoint (HPDI[1] / MPI[1] / BAS[1] on guide breakpoints), which
          clears the base demo's LEAN-RISK DO NOT FLASH finding.
    R01 — Adds six limiter/fuelling writes the recipe left at stock: pedal
          threshold (72), max requested pressure (350000, set_raw), two max-intake-air
          tables (2000), max reference torque (1000), and max allowed airmass
          (stored 0.002 — the guide's float-bug value, not 2000).
    R02 — Report-honesty only; bin byte-identical to R01. Supersedes recipe rows by
          guide section and documents the known deliberate skips.
    R03 — Applies the guide's literal 0.80 target to the three lambda minimum-value
          floors: `C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint;
          `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating
          protection; `IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo
          charger overheating prevention versus engine speed.
    R04 — R03 + local timing reductions in `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`
          — Basic Ignition Angle, VVL 0 Port Flap Low, targeting repeated WOT knock
          retard in the first R01 flash logs.
    R05 — R04 + wastegate feedforward boost-tracking overlay in
          `IP_FAC_BPA_SP[0]` / `[1]`  — Wastegate Position Feedforward VVL 0/1,
          lowering the overboost flow-factor ridge (spool spike, mid-range, and
          integral-saturated top-end) found in the 2026-07-08 R04 log, plus a
          re-breakpoint of their shared X axis last column (Exh flow factor
          1.25 -> 1.40) to unclamp and open the top end further. Changes those two
          Z maps and their shared X-axis breakpoint table relative to R04;
          identical deltas to both VVL tables.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import (
    CalFile,
    apply_basics_sop,
    format_report,
    render_table,
)
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import (
    OUTCOME_APPLIED,
    RecipeReport,
    TableOutcome,
)

# R05 chains R04's timing overlay and, through R04, the full R03 pipeline.
from TUNE_Basics_Guide_R03 import (
    BIN_PATH,
    OUT_ROOT,
    XDF_PATH,
    _apply_r03_writes,
    _merge_report,
    _rebreakpoint_lambda_family,
    _write_comparison_pngs,
)
from TUNE_Basics_Guide_R04 import _apply_r04_timing_overlay

OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R05.bin"

R05_SECTION_WG = "Wastegate — R05 feedforward boost-tracking overlay"
# VVL 0 and VVL 1 wastegate position feedforward tables. Same delta to both.
R05_WG_SYMBOLS = ("IP_FAC_BPA_SP[0]", "IP_FAC_BPA_SP[1]")
R05_WG_TITLE = "Wastegate Position Feedforward"

# The base recipe deliberately skips the wastegate as log-dependent
# (KIND_SKIP_LOG_DEPENDENT). R05 supplies those log-driven values, so its applied
# rows supersede that generic skip row — the report then shows the wastegate once,
# as applied, instead of both skipped and applied (mirrors R03's supersede-by-section).
R05_SUPERSEDES_SECTIONS = frozenset({"Wastegate (flow-factor tuning)"})

# Physical bounds for a wastegate-position cell (1 = closed, 0 = open). Edits are
# clamped here defensively; with the deltas below no cell reaches either bound.
WG_MIN, WG_MAX = 0.0, 1.0

# Shared X-axis (Exh flow factor) breakpoint table for BOTH wastegate maps. Verified
# (grep of the XDF) to be referenced ONLY by IP_FAC_BPA_SP[0] and [1], so editing it
# is contained to these two tables. R05 moves the last breakpoint 1.25 -> 1.40 to
# unclamp the top-end operating range (logged Exh flow factor reaches ~1.33).
R05_WG_X_AXIS_SYMBOL = "ldp_fac_1_ip_fac_bpa_sp"
R05_WG_X_AXIS_LAST_IDX = 15
R05_WG_X_AXIS_OLD = 1.25
R05_WG_X_AXIS_NEW = 1.40

# Wastegate table geometry (verified against the R04 bin and the XDF, addr 0x199f6):
#   X axis (Exh flow factor), 16 cols (col 15 re-breakpointed 1.25 -> 1.40 by R05):
#     0:0.00 1:0.25 2:0.35 3:0.40 4:0.45 5:0.50 6:0.55 7:0.60
#     8:0.65 9:0.70 10:0.75 11:0.80 12:0.85 13:0.90 14:1.00 15:1.40(was 1.25)
#   Y axis (Int flow factor), 10 rows:
#     0:0.00 1:0.15 2:0.30 3:0.45 4:0.60 5:0.75 6:0.90 7:1.05 8:1.25 9:1.50
#
# Delta map (row, col) -> wastegate-position change; negative = open more.
# Sized from the measured mean PUT overshoot at each visited flow-factor cell in
# the R04 log (~0.05 per psi, 7 kPa ~= 1 psi), smoothed along the overboost ridge.
# The comment on each cell records Int/Exh flow factor, the rpm band it is hit in,
# and the measured mean/max overboost that justifies its pull.
R05_WG_DELTAS: dict[tuple[int, int], float] = {
    # --- Upper blend row (Int 0.45) — half-step so zone A has no WG cliff above ---
    (3, 12): -0.03,   # Int0.45 x Exh0.85 : blend above the spool-spike corner
    (3, 13): -0.04,   # Int0.45 x Exh0.90 : blend above the spool-spike corner

    # --- Zone A: spool spike, ~3100-3400 rpm, PUT error up to +22 kPa (+3.2 psi) ---
    (4, 12): -0.08,   # Int0.60 x Exh0.85 : spike corner edge, +6 kPa mean
    (4, 13): -0.11,   # Int0.60 x Exh0.90 : worst cell, +17.6 mean / +22.2 max kPa
    (5, 12): -0.09,   # Int0.75 x Exh0.85 : +9.9 kPa mean
    (5, 13): -0.10,   # Int0.75 x Exh0.90 : +12.6 kPa mean

    # --- Zone MID: post-spike, ~3500-5400 rpm, steady +5 to +8 kPa (~+0.7-1.2 psi) ---
    (5, 11): -0.05,   # Int0.75 x Exh0.80 : left edge of the mid ridge
    (5, 14): -0.06,   # Int0.75 x Exh1.00 : mid ridge bridging toward top-end
    (6, 11): -0.03,   # Int0.90 x Exh0.80 : light blend, ridge left edge
    (6, 12): -0.05,   # Int0.90 x Exh0.85 : +5.6 kPa mean
    (6, 13): -0.06,   # Int0.90 x Exh0.90 : most-visited mid cell, +4.9 kPa mean (24 samples)
    (6, 14): -0.06,   # Int0.90 x Exh1.00 : most-visited mid cell, +5.0 kPa mean (30 samples)
    (7, 13): -0.04,   # Int1.05 x Exh0.90 : lower-left blend of the mid/top ridge

    # --- Zone B: top-end, ~5800-6700 rpm, +8 to +17 kPa while WG integral saturates ---
    # The col-15 cells sit at the re-breakpointed Exh 1.40 endpoint and are pulled
    # deeper than the row-6/7 col-14 (Exh 1.00) cells, so the top-end segment slopes
    # progressively MORE open as exhaust flow climbs toward the logged ~1.33 max
    # (instead of the stock flat clamp shelf above 1.25). Verified by simulating the
    # ECU bilinear lookup over the log: opens ~0.01-0.02 more across the sustained
    # top-end overboost, and 0.000 change at Exh<=1.00 (spool/mid) vs cells-only.
    (6, 15): -0.11,   # Int0.90 x Exh1.40 : top-end endpoint, slope-down anchor
    (7, 14): -0.07,   # Int1.05 x Exh1.00 : mid + saturated top-end (integral to -28%)
    (7, 15): -0.11,   # Int1.05 x Exh1.40 : top-end endpoint, +12.8/+17.1 kPa band
    (8, 14): -0.03,   # Int1.25 x Exh1.00 : blend below the top-end corner
    (8, 15): -0.06,   # Int1.25 x Exh1.40 : blend below the top-end endpoint
}


def _apply_r05_wg_axis_rebreakpoint(cal: CalFile) -> TableOutcome:
    """Move the shared Exh-flow-factor X-axis last breakpoint 1.25 -> 1.40.

    Must run BEFORE :func:`_snapshot_r05_wg` so the before/after Z comparison PNGs
    are taken on the final axis (otherwise the axis change would make the composite
    misleading and it would be dropped as an axis mismatch). Writing this one shared
    byte region updates the X axis of BOTH wastegate tables at once. Raises if the
    stored last breakpoint is not the expected stock 1.25 (fail loud if the base
    changed under us).
    """
    ax = cal.get(R05_WG_X_AXIS_SYMBOL)
    values = np.array(ax.values, dtype=np.float64, copy=True)
    flat = values.ravel()
    old = float(flat[R05_WG_X_AXIS_LAST_IDX])
    if abs(old - R05_WG_X_AXIS_OLD) > 1e-3:
        raise ValueError(
            f"{R05_WG_X_AXIS_SYMBOL}: expected stock last breakpoint "
            f"{R05_WG_X_AXIS_OLD}, found {old:.4f} — refusing to re-breakpoint."
        )
    flat[R05_WG_X_AXIS_LAST_IDX] = R05_WG_X_AXIS_NEW
    ax.set(flat.reshape(ax.shape))
    return TableOutcome(
        R05_WG_X_AXIS_SYMBOL, R05_SECTION_WG, OUTCOME_APPLIED,
        detail=(
            f"{R05_WG_X_AXIS_SYMBOL}  — Wastegate feedforward X axis (Exh flow "
            f"factor): re-breakpointed last column {R05_WG_X_AXIS_OLD:g} -> "
            f"{R05_WG_X_AXIS_NEW:g}. Shared by IP_FAC_BPA_SP[0]/[1] only, so this "
            "unclamps the top-end operating range (logged Exh flow factor ~1.33) "
            "for both VVL tables at once; paired with a deeper last-column slope "
            "so the wastegate opens progressively more as exhaust flow climbs."
        ),
        old=old, new=R05_WG_X_AXIS_NEW,
    )


def _snapshot_r05_wg(cal: CalFile) -> dict[str, object]:
    """Snapshot the two wastegate tables after R04 is staged, before the R05 overlay.

    The resulting comparison PNGs then show the R04 -> R05 wastegate change (R04
    leaves these tables at stock, so R04-staged == stock for these two symbols).
    """
    return {sym: render_table(cal.get(sym)) for sym in R05_WG_SYMBOLS}


def _apply_r05_wg_overlay(cal: CalFile) -> list[TableOutcome]:
    """Lower the overboost-ridge cells in BOTH wastegate feedforward tables.

    Applies the identical :data:`R05_WG_DELTAS` map to VVL 0 and VVL 1, clamps
    each edited cell to the physical [0, 1] wastegate-position range, and returns
    a report row per table. Raises if the two tables did not receive identical
    deltas or if the intended cell count did not change (fail loud, never silently
    alter an unexpected number of cells).
    """
    outcomes: list[TableOutcome] = []
    applied_deltas: list[np.ndarray] = []

    for sym in R05_WG_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        stock = np.array(view.values, dtype=np.float64, copy=True)
        x_axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()

        for (r, c), d in R05_WG_DELTAS.items():
            new = float(values[r, c]) + d
            clamped = min(max(new, WG_MIN), WG_MAX)
            if clamped != new:
                raise ValueError(
                    f"{sym}: cell ({r},{c}) hit the physical WG bound "
                    f"[{WG_MIN}, {WG_MAX}] (target {new:.3f}); refusing to write a "
                    "clamped wastegate value — review R05_WG_DELTAS."
                )
            values[r, c] = clamped

        delta = values - stock
        changed = int(np.count_nonzero(delta))
        if changed != len(R05_WG_DELTAS):
            raise ValueError(
                f"{sym}: expected {len(R05_WG_DELTAS)} changed cells, got {changed}"
            )

        view.set(values)
        applied_deltas.append(delta)

        # Compact, reviewable per-zone summary in the report detail.
        def _rng(rows, cols):
            sub = delta[np.ix_(rows, cols)]
            nz = sub[np.abs(sub) > 1e-9]
            return f"{nz.min():+.3f}..{nz.max():+.3f}" if nz.size else "none"

        detail = (
            f"{sym}  — {R05_WG_TITLE}: lowered {changed} cells along the R04-log "
            f"overboost ridge (open WG sooner). "
            f"Spool spike (Int0.60-0.75 x Exh0.85-0.90): {_rng([4, 5], [12, 13])}; "
            f"mid-range (Int0.75-0.90 x Exh0.80-1.00): {_rng([5, 6], [11, 12, 13, 14])}; "
            f"top-end (Int0.90-1.05 x Exh1.00-1.40): {_rng([6, 7], [14, 15])}; "
            f"blends (Int0.45 & Int1.25): {_rng([3, 8], [12, 13, 14, 15])}. "
            f"Same deltas applied to both VVL tables; cells = WG position "
            f"(1=closed, 0=open); axes X=Exh flow factor, Y=Int flow factor."
        )
        outcomes.append(TableOutcome(sym, R05_SECTION_WG, OUTCOME_APPLIED, detail=detail))

    # Safety: the guide requires the SAME change on both tables. Fail loud otherwise.
    if not np.array_equal(applied_deltas[0], applied_deltas[1]):
        raise ValueError(
            "VVL 0 and VVL 1 wastegate tables received different deltas — the guide "
            "requires identical edits to both. Refusing to continue."
        )

    return outcomes


def _write_r05_comparison_pngs(cal: CalFile, snaps: dict, r05_outcomes: list[TableOutcome], png_dir: Path) -> tuple[int, int]:
    """Emit R04->R05 comparison PNGs for only the two R05 wastegate tables."""
    r05_report = RecipeReport(tuple(r05_outcomes))
    return _write_comparison_pngs(cal, snaps, r05_report, png_dir)


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R05_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        # Full R04 pipeline (which is the full R03 pipeline + the R04 timing overlay).
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)

        # R05 wastegate overlay. Re-breakpoint the shared X axis FIRST so the
        # before/after Z comparison PNGs are taken on the final axis, then snapshot
        # the two wastegate tables, then apply the Z cell edits.
        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        r05_snaps = _snapshot_r05_wg(cal)
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

    # Drop the recipe's generic wastegate skip row that R05 now supersedes, so the
    # wastegate is reported once (as applied) rather than both skipped and applied.
    kept = tuple(
        o for o in (tuple(r03_report.outcomes) + tuple(r04_outcomes))
        if o.guide_section not in R05_SUPERSEDES_SECTIONS
    )
    report = RecipeReport(kept + tuple(r05_outcomes))

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")

    # Only the two R05 wastegate symbols receive R04->R05 snapshots, keeping the
    # comparison PNGs focused on what R05 actually changed.
    png_count, axis_changed = _write_r05_comparison_pngs(
        cal, r05_snaps, r05_outcomes, out_dir / "compare"
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
              "This is revision 5; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. This is revision 5; iterate.")


if __name__ == "__main__":
    main()
