#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R06.

R06 is based on R05 and runs the EXACT R05 pipeline unchanged: the lambda axis
re-breakpoint, the R01 limiter/fuelling writes, the R03 literal 0.80 lambda
minimum-value floors, the R04 local WOT knock-retard ignition overlay, and the
R05 wastegate feedforward boost-tracking overlay (both `IP_FAC_BPA_SP[0]/[1]`
Z maps plus their shared X-axis re-breakpoint). R06 adds NO new script-level
tuning overlay of its own.

**R06 = R05 + the shared-recipe OVERBOOST LIMITER FIX.** This is a bug fix in the
shared SOP recipe (`Code/simoscal/sop_recipe.py`), consumed by every revision
through `apply_basics_sop`. Its effect on the saved bin is real and is what makes
R06 a distinct revision from R05:

  * The recipe entry "Limiters — Overboost limit -> 2700" was mapped to the WRONG
    symbol: `C_PRS_IM_SP_LIM`  — Offset to the pressure behind air cleaner for the
    limitation of the manifold setpoint (a float32 manifold-setpoint limit, stock
    ~271696 hPa). Because stock already exceeded 2700, the guarded-ceiling writer
    correctly guarded-skipped it, so through R05 the OVERBOOST LIMIT WAS NEVER
    ACTUALLY WRITTEN.
  * It is now correctly mapped to `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  — Overpressure
    upstream throttle threshold for turbocharger overpressure diagnosis (the P0234
    overboost diagnosis): a 1x6 int16 hPa map, stock ~1800 in all six cells, XDF
    hard max 2716.96 hPa. R06 raises all six cells 1800 -> 2700 (just under the
    ceiling — do not exceed).
  * The guarded-ceiling writer was also fixed to BROADCAST across every cell with
    never-lower semantics (it previously only touched cell (0,0)), so all six
    overboost cells are raised, and any cell already above target is left
    untouched. It additionally refuses to write above a table's declared max
    (fail loud, never overflow a limiter's element width).

So relative to R05, the ONLY change in the saved bin is the six-cell overboost
table `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` (1800 -> 2700), and `C_PRS_IM_SP_LIM` is
no longer touched by the recipe. The R05 output (R05_20260709-145551) is now stale
because the overboost limit was never applied there. `C_PRS_IM_SP_LIM` (the
manifold-setpoint offset limit) is deliberately NOT changed by R06 — whether it
should also be raised is an open question, out of scope for this fix.

See `Docs/plans/2026-07-09-004-fix-overboost-symbol-map.md`,
`knowledge/ecu-tuning-basics.md` ("Limiters"), and memory
`limiter-xdf-declared-max-wrong.md`.

This is still **revision 6 — a starting point, not a finished calibration**. The
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
    R06 — R05 + shared-recipe overboost limiter fix. The recipe's "Overboost limit
          -> 2700" entry was repointed from the wrong `C_PRS_IM_SP_LIM`  — Offset
          for the manifold-setpoint limitation (which stock exceeds, so it was
          silently guarded-skipped through R05) to the real overboost table
          `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  — Overpressure upstream throttle
          threshold for turbocharger overpressure diagnosis (P0234), and the
          guarded-ceiling writer was fixed to broadcast across all cells
          (never-lower). R06 therefore raises all six overboost cells 1800 -> 2700
          (XDF hard max 2716.96). No new script-level overlay; the sole saved-bin
          delta versus R05 is that six-cell overboost table.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

from simoscal import (
    CalFile,
    apply_basics_sop,
    format_report,
)
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import RecipeReport

# R06 chains the full R05 pipeline (which is the full R04 pipeline, which is the
# full R03 pipeline + the R04 timing overlay) and reuses its wastegate overlay
# helpers verbatim — R06 introduces no new script-level tuning code, only the
# shared-recipe overboost fix that now flows through apply_basics_sop.
from TUNE_Basics_Guide_R03 import (
    BIN_PATH,
    OUT_ROOT,
    XDF_PATH,
    _apply_r03_writes,
    _merge_report,
    _rebreakpoint_lambda_family,
)
from TUNE_Basics_Guide_R04 import _apply_r04_timing_overlay
from TUNE_Basics_Guide_R05 import (
    R05_SUPERSEDES_SECTIONS,
    _apply_r05_wg_axis_rebreakpoint,
    _apply_r05_wg_overlay,
    _snapshot_r05_wg,
    _write_r05_comparison_pngs,
)

OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R06.bin"


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R06_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        # Full R04 pipeline (which is the full R03 pipeline + the R04 timing overlay).
        # apply_basics_sop now applies the corrected overboost limiter
        # (IP_PUT_AMP_DIF_MAX_PRS_DIF_THR 1800 -> 2700 across all six cells) — the
        # only saved-bin change R06 makes relative to R05.
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)

        # R05 wastegate overlay, reused unchanged. Re-breakpoint the shared X axis
        # FIRST so the before/after Z comparison PNGs are taken on the final axis,
        # then snapshot the two wastegate tables, then apply the Z cell edits.
        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        r05_snaps = _snapshot_r05_wg(cal)
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

    # Drop the recipe's generic wastegate skip row that the R05 overlay supersedes,
    # so the wastegate is reported once (as applied) rather than both skipped and
    # applied.
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
    # comparison PNGs focused on what the wastegate overlay changed.
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
              "This is revision 6; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. This is revision 6; iterate.")


if __name__ == "__main__":
    main()
