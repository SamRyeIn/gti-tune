#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R05.

Revision history (see REV_LOG.md):
    DRAFT00 — Not applicable (this lineage uses R* revisions only).
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
    R04 — R03 + local WOT knock-retard ignition overlay in
          `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle,
          VVL 0 Port Flap Low, targeting repeated WOT knock retard in the first R01
          flash logs.
    R05 — R04 + wastegate feedforward tuning. Lowers cells in the two PUT-overshoot
          regions identified in the R04 validation log (spool spike ~3000-3500 rpm;
          top-end persistent overboost ~6000-6500 rpm with WG integral saturating),
          and re-breakpoints the shared WG X axis (Exh flow factor) last column
          1.25 -> 1.40 so logged Exh flow factor 1.33 interpolates instead of
          clamping. Targets both `IP_FAC_BPA_SP[0]` / `[1]` — Wastegate Position
          Feedforward VVL 0/1 (cells = WG position, 1 = closed, 0 = open;
          overboost -> lower to open WG more). See REV_LOG.md.

R05 is based on R04 and keeps all R04 behavior unchanged, including the R04
knock-retard ignition overlay and the R03 lambda floor writes.

The wastegate edits target two regions from the 2026-07-08 R04 validation log
(`Logs/BasicsGuide_R04/simostools-2026_07_08-22_10_57.csv`, two 3rd-gear WOT
pulls). This is the first revision to touch wastegate control; prior revisions
explicitly deferred it as log-dependent.

  Region A — spool spike (~3000-3500 rpm):
      Exh FF 0.75-0.91 x Int FF 0.62-0.78, PUT error +11 to +22 kPa.
      Feedforward commands WG nearly closed right as boost crosses target; the
      PID P/D term reacts but cannot catch the transient overboost spike.
  Region B — top-end persistent (~6000-6500 rpm):
      Exh FF 1.08-1.33 x Int FF 0.97-1.07, PUT error +10 to +16 kPa sustained.
      Logged Exh FF 1.33 exceeds the stock last X-axis column (1.25), so the ECU
      clamps to that column's value (WG too closed). The WG integral term saturates
      at its -27.5% floor (26 of 185 points <= -20% in pull 1) — the closed-loop
      controller runs out of authority because feedforward is too far off.

This is still revision 5 — a starting point, not a finished calibration: review
the report and PNGs, then flash -> log -> review -> iterate. This script never
flashes, and a saved bin is not flash-ready while the report shows DO NOT FLASH.
"""

from __future__ import annotations

import datetime as _dt
import sys
import warnings
from pathlib import Path

import numpy as np

# This script lives in Test/GLM-5.2/; the R04 script (and its R03 chain) lives in
# the grandparent TuningBasicsGuide/ directory. Add that to sys.path so the import works.
_PARENT = Path(__file__).resolve().parents[2]
if str(_PARENT) not in sys.path:
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
from simoscal.plot import TableMismatchError

from TUNE_Basics_Guide_R04 import (
    BIN_PATH,
    XDF_PATH,
    _apply_r03_writes,
    _apply_r04_timing_overlay,
    _merge_report,
    _rebreakpoint_lambda_family,
    _snapshot_r04_timing_targets,
    _write_comparison_pngs,
    apply_basics_sop,
)

# R05 writes to its own output root under Test/GLM-5.2/ so this experimental
# revision is isolated from the main TUNE_Basics_Guide_out/ lineage directory.
OUT_ROOT = Path(__file__).resolve().parent / "TUNE_Basics_Guide_out"
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R05.bin"

R05_SECTION_WG = "Wastegate — R05 feedforward tuning (PUT tracking)"
R05_SECTION_AXIS = "Wastegate — R05 X-axis re-breakpoint (Exh flow factor)"

# The two wastegate feedforward tables. Cells = WG position (1 = closed, 0 = open).
# X = exhaust flow factor, Y = intake flow factor. Both share the same axes:
#   ldp_fac_1_ip_fac_bpa_sp (X, 0x196fc) — shared by both tables (and the axis
#       table itself); no other table embeds this address (blast radius verified).
#   ldp_fac_2_ip_fac_bpa_sp (Y, 0x1974a) — left stock.
WG_SYMBOLS = ("IP_FAC_BPA_SP[0]", "IP_FAC_BPA_SP[1]")
WG_TITLE = "Wastegate Position Feedforward"
WG_X_AXIS_SYMBOL = "ldp_fac_1_ip_fac_bpa_sp"

# Edited X axis (Exh flow factor). Stock last breakpoint 1.25 -> 1.40 so the
# logged Exh FF 1.33 (R04 log, top-end) interpolates between the 1.00 and 1.40
# columns instead of clamping at 1.25. All other breakpoints unchanged.
EDITED_X_AXIS = (
    0.0, 0.25, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60,
    0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00, 1.40,
)

# Cell deltas applied to BOTH tables (guide: apply changes to both). All deltas
# are negative (open WG more) to address overboost. Indices are (row, col) in the
# 10x16 grid: rows = Int FF [0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25,
# 1.50], cols = Exh FF [0.0, 0.25, ..., 0.90, 1.00, 1.40].
#
# Region A — spool corner. Exh 0.75-0.90 (cols 10-13) x Int 0.60-0.90 (rows 4-6).
#   PUT error +11 to +22 kPa -> ~0.08-0.09 lower (guide: ~0.05 per 1 psi / ~7 kPa).
# Region B — top-end. Exh 1.00 (col 14) & 1.40 (col 15) x Int 0.90-1.50 (rows 6-9).
#   PUT error +10 to +16 kPa sustained, WG integral saturating -> ~0.035-0.07
#   lower, heavier at the far corner where overshoot grows and the integral
#   saturates. Col 15 also drops because at 1.40 it now represents higher flow.
# Blend — neighbors of A and B get ~half the delta to avoid WG-position cliffs.
WG_CELL_DELTAS = {
    # Region A (spool corner)
    (4, 10): -0.09, (4, 11): -0.09, (4, 12): -0.09, (4, 13): -0.09,
    (5, 10): -0.09, (5, 11): -0.09, (5, 12): -0.09, (5, 13): -0.09,
    (6, 10): -0.08, (6, 11): -0.08, (6, 12): -0.08, (6, 13): -0.08,
    # Region B (top-end)
    (6, 14): -0.05, (6, 15): -0.065,
    (7, 14): -0.055, (7, 15): -0.07,
    (8, 14): -0.045, (8, 15): -0.06,
    (9, 14): -0.035, (9, 15): -0.04,
    # Blend neighbors (~half delta)
    (3, 10): -0.03, (3, 11): -0.03, (3, 12): -0.03, (3, 13): -0.03,
    (5, 14): -0.03, (5, 15): -0.035,
    (4, 9): -0.035, (5, 9): -0.035, (6, 9): -0.03,
}


def _apply_r05_wg_cells(cal: CalFile) -> list[TableOutcome]:
    """Apply the WG feedforward cell edits to both VVL 0 / VVL 1 tables.

    Reads each table's current (R04-state = stock WG) values, applies the delta
    map, clamps at the physical floor (WG fully open = 0.0), and writes via
    ``.set()``. The X-axis re-breakpoint is applied separately in
    :func:`_apply_r05_wg_axis` so that a before/after cell comparison with
    matching axes is still possible.
    """
    outcomes: list[TableOutcome] = []
    for sym in WG_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        changed: list[str] = []
        for (r, c), d in WG_CELL_DELTAS.items():
            old = float(values[r, c])
            new = max(old + d, 0.0)
            values[r, c] = new
            changed.append(f"({r},{c}) {old:.3f}->{new:.3f} ({new-old:+.3f})")
        view.set(values)
        n = len(changed)
        outcomes.append(TableOutcome(
            sym, R05_SECTION_WG, OUTCOME_APPLIED,
            detail=(
                f"{sym}  — {WG_TITLE}: lowered {n} cells in the two PUT-overshoot "
                f"regions (spool corner Exh 0.75-0.90 x Int 0.60-0.90; top-end "
                f"Exh 1.00-1.40 x Int 0.90-1.50). Max delta "
                f"{min(WG_CELL_DELTAS.values()):.3f}. All deltas open WG more "
                f"(overboost -> lower cells). Blend neighbors ~half delta."
            ),
        ))
    return outcomes


def _apply_r05_wg_axis(cal: CalFile) -> list[TableOutcome]:
    """Re-breakpoint the shared WG X axis (Exh flow factor) last column 1.25 -> 1.40.

    Applied AFTER the cell edits and after the cell comparison snapshots so the
    before/after cell comparison still has matching axes. The axis table
    ``ldp_fac_1_ip_fac_bpa_sp`` (0x196fc) is shared only by the two WG tables
    (and itself) — blast radius verified, no other table embeds this address.
    """
    outcomes: list[TableOutcome] = []
    xv = cal.get(WG_X_AXIS_SYMBOL)
    old = np.array(xv.values, dtype=np.float64).ravel()
    xv.set(np.array(EDITED_X_AXIS, dtype=np.float64).reshape(xv.shape))
    outcomes.append(TableOutcome(
        WG_X_AXIS_SYMBOL, R05_SECTION_AXIS, OUTCOME_APPLIED,
        detail=(
            f"re-breakpointed shared WG X axis (Exh flow factor) last column "
            f"{old[-1]:.2f} -> {EDITED_X_AXIS[-1]:.2f}. The R04 log shows Exh FF "
            f"reaching 1.33 (top-end), which exceeded the stock last column 1.25 "
            f"and clamped — causing WG to command too closed. At 1.40 the logged "
            f"1.33 interpolates between the 1.00 and 1.40 columns. Shared by "
            f"IP_FAC_BPA_SP[0]/[1] only (blast radius verified)."
        ),
    ))
    return outcomes


def _snapshot_wg_tables(cal: CalFile) -> dict[str, object]:
    """Pre-edit RenderedTable per WG symbol (R04-state = stock WG cells + stock axis)."""
    return {sym: render_table(cal.get(sym)) for sym in WG_SYMBOLS}


def _write_wg_comparison_pngs(
    before: dict[str, object],
    after_cells: dict[str, object],
    png_dir: Path,
) -> int:
    """Emit before/after/delta PNGs for the WG cell edits.

    Compares ``before`` (stock cells, stock axis) against ``after_cells`` (edited
    cells, stock axis) — both have matching axes because the X-axis re-breakpoint
    is applied AFTER this comparison. This is why the axis edit is staged last.
    """
    png_count = 0
    png_dir.mkdir(parents=True, exist_ok=True)
    for sym in WG_SYMBOLS:
        try:
            paths = compare_tables(before[sym], after_cells[sym], png_dir)
            png_count += len(paths)
        except TableMismatchError:
            # Should not happen (axes match at this point), but guard anyway.
            pass
    return png_count


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R05_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        # Full R04 pipeline (chains R03 -> recipe -> R03 writes -> R04 timing).
        # R05 does not touch timing tables, so R04's own comparison PNGs are not
        # regenerated here (they live under their own R04_<stamp>/compare/ run).
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)

        # R05: snapshot WG tables (R04-state = stock WG), apply cell edits, snapshot
        # again (edited cells, stock axis), then apply axis re-breakpoint last.
        wg_before = _snapshot_wg_tables(cal)
        r05_cell_outcomes = _apply_r05_wg_cells(cal)
        wg_after_cells = _snapshot_wg_tables(cal)
        r05_axis_outcomes = _apply_r05_wg_axis(cal)

    report = RecipeReport(
        tuple(r03_report.outcomes)
        + tuple(r04_outcomes)
        + tuple(r05_cell_outcomes)
        + tuple(r05_axis_outcomes)
    )

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")

    # R05 WG cell comparison PNGs (stock WG -> edited cells, matching axes).
    # R04's ignition-overlay comparison PNGs are intentionally NOT regenerated
    # here — R05 doesn't touch timing tables, so re-emitting R04's before/after
    # ignition plots in an R05 output folder would be misleading. The R04
    # artifacts live under their own R04_<stamp>/compare/ run.
    wg_png_count = _write_wg_comparison_pngs(
        wg_before, wg_after_cells, out_dir / "compare"
    )

    counts = report.counts()
    print(f"Recipe applied — {len(report.outcomes)} table outcomes:")
    for key in sorted(counts):
        print(f"    {key:18s} {counts[key]}")
    print(f"\n  saved bin      : {out_bin}")
    print(f"  checksums      : {'CLEAN' if clean else 'STALE — NOT flash-ready'}"
          f" ({', '.join(r.name for r in save_reports)})")
    print(f"  report         : {out_dir / 'report.md'}")
    print(f"  WG cell PNGs   : {wg_png_count} under {out_dir / 'compare'}"
          f" (axis re-breakpoint reported in text — before/after axes differ)")
    if report.do_not_flash():
        print("\n  ⛔ DO NOT FLASH — see the report's coherence section. "
              "This is revision 5; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. This is revision 5; iterate.")


if __name__ == "__main__":
    main()
