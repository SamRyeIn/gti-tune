#!/usr/bin/env python3
"""Patched bin — TuningBasicsGuide, revision R08 (top-end wastegate FF deepening).

R08 is based on R07 and runs the EXACT R07 pipeline unchanged (the three .btp
patches, the full R06 CAL-edit pipeline on the patched base, and the switch-patch
TC flags on all five slots). It adds ONE new thing:

**R08 = top-end wastegate feedforward deepening.** It lowers six cells in the two
wastegate position feedforward tables so the wastegate opens sooner in the
sustained top-end overboost region found in the clean R07 3rd-gear logs:

  * `IP_FAC_BPA_SP[0]`  — Wastegate Position Feedforward, VVL 0 (Map for boost
    pressure actuator setpoint)
  * `IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward, VVL 1 (same title)

Cells = commanded wastegate position (1 = closed, 0 = open); axes are
X = exhaust flow factor (last column re-breakpointed to 1.40 by R05),
Y = intake flow factor. Same deltas to BOTH tables, per the guide.

Log analysis (`Logs/BasicsGuide_R07/`, clean 3rd-gear WOT pulls only —
simostools-2026_07_12-16_02_51 / 16_05_57 / 16_07_36; the two 2nd-gear pulls were
excluded: one is spool-transient-dominated and the other is contaminated by
switch-patch TC interventions with up to 11.5 km/h front-vs-rear wheel slip):

  * Mid-range 3300-5800 rpm: mean PUT error +0.1 kPa — the R05 overlay did its
    job; those cells are NOT touched again.
  * Top-end 5800-6700 rpm: sustained mean +8.5 kPa, max +15.1 kPa, while the WG
    integral only reaches ~-16% (has headroom but is slow — feedforward short).

**Key finding — the flow-factor trajectory is a hysteresis loop, not monotonic
with rpm.** Exh flow factor peaks ~1.33 at 5200-5800 rpm (where tracking is GOOD,
-2.4 kPa) and falls back to ~1.10 by 6200-6700 rpm (where the WORST overshoot
lives, +10.6 kPa). The good and bad regions overlap in Exh-flow space; the real
discriminator is the INTAKE flow factor row: the worst band runs Int ~1.04 (93%
weight on the Int 1.05 row), the good bands Int ~0.94-1.00. The R08 deltas are
therefore ROW-WEIGHTED — deep on the Int 1.05 row (and its Int 1.25 blend), light
on the Int 0.90 row — rather than uniform like R05's ridge pull.

Sizing: simulating the ECU's bilinear lookup at every logged clean-pull WOT
point, the deltas open the wastegate -5.2% mean in the worst 6200-6700 band
(~70% of the guide's 0.05-per-psi rule for its +10.6 kPa error — a conservative
second pass), -3.3 to -3.9% in the adjacent bands (absorbed by their I-terms,
which currently idle at -4 to -6% doing work the feedforward should do), and
0.000 below 3300 rpm (spool untouched).

This is still **revision 8 — a starting point, not a finished calibration**. The
script never flashes, and the bin REQUIRES A FULL FLASH (switch-patched ASW).

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
          plus a re-breakpoint of their shared X axis last column (Exh flow factor
          1.25 -> 1.40) to unclamp and open the top end further.
    R06 — R05 + shared-recipe overboost limiter fix: the "Overboost limit -> 2700"
          entry was repointed from the wrong `C_PRS_IM_SP_LIM`  — Offset for the
          manifold-setpoint limitation to the real overboost table
          `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  — Overpressure upstream throttle
          threshold for turbocharger overpressure diagnosis (P0234), raised across
          all six cells 1800 -> 2700.
    R07 — R06 calibration applied to a PATCHED bin (SL CBRICK v1.2, SL HSL v1.1,
          SL PATCH.29.33 5-slot map switch), switch-patch traction control ON for
          all five slots. FULL FLASH REQUIRED. No new base-calibration tuning.
    R08 — R07 + top-end wastegate feedforward deepening in `IP_FAC_BPA_SP[0]` /
          `[1]`  — Wastegate Position Feedforward VVL 0/1: six cells on the
          Int 0.90/1.05/1.25 x Exh 1.00/1.40 corner lowered (row-weighted onto
          the Int 1.05 row) to close the sustained +8.5 kPa mean / +15.1 kPa max
          top-end (5800-6700 rpm) PUT overshoot in the clean 3rd-gear R07 logs.
          Identical deltas to both VVL tables; mid-range and spool cells untouched.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import CalFile, btp, format_report
from simoscal.checksum import StaleChecksumWarning
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import OUTCOME_APPLIED, RecipeReport, TableOutcome

# R08 chains the full R07 pipeline verbatim (patches + R06 CAL edits + TC flags).
from TUNE_Basics_Guide_R03 import BIN_PATH, OUT_ROOT, XDF_PATH
from TUNE_Basics_Guide_R05 import (
    R05_WG_SYMBOLS,
    R05_WG_TITLE,
    WG_MAX,
    WG_MIN,
    _snapshot_r05_wg,
    _write_r05_comparison_pngs,
)
from TUNE_Basics_Guide_R07 import (
    PATCHES,
    _apply_patches,
    _read_tc_state,
    _run_r06_pipeline,
    _write_tc_flags,
)

OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R08.bin"

R08_SECTION_WG = "Wastegate — R08 top-end feedforward deepening"

# Wastegate table geometry (unchanged from R05; X col 15 = 1.40 after the R05
# re-breakpoint, which _run_r06_pipeline re-applies on every build):
#   X (Exh flow factor): ... 13:0.90 14:1.00 15:1.40
#   Y (Int flow factor): ... 6:0.90 7:1.05 8:1.25 9:1.50
#
# Delta map (row, col) -> wastegate-position change ON TOP of the R05 values;
# negative = open more. Sized from the clean 3rd-gear R07 logs (see module
# docstring): the sustained top-end overshoot leans 93% on the Int 1.05 row while
# the well-tracking 4500-5800 bands lean on Int 0.90-1.00, so the pull is deep on
# rows 7/8 and light on row 6. Cell comments give the measured evidence.
R08_WG_DELTAS: dict[tuple[int, int], float] = {
    # --- Int 0.90 row: light — protects 3300-5200 rpm (mean err +0.1 kPa) ---
    (6, 14): -0.02,   # Int0.90 x Exh1.00 : top-end fringe, +9.8 kPa wmean but low weight
    (6, 15): -0.02,   # Int0.90 x Exh1.40 : top-end fringe, +8.1 kPa wmean, low weight

    # --- Int 1.05 row: main pull — the 6200-6700 rpm overshoot band (Int ~1.04,
    #     Exh ~1.08-1.14) puts 93% of its row weight here; +9.4 kPa wmean at c14 ---
    (7, 14): -0.06,   # Int1.05 x Exh1.00 : worst-band anchor, +9.4 kPa wmean
    (7, 15): -0.04,   # Int1.05 x Exh1.40 : shared with the good 5200-5800 band
                      #                     (Exh ~1.31, err -2.4) — lighter pull

    # --- Int 1.25 row: blend — log reaches Int 1.063; mirrors row 7 so there is
    #     no wastegate-position cliff just above the operating edge ---
    (8, 14): -0.06,   # Int1.25 x Exh1.00 : blend above the worst-band corner
    (8, 15): -0.04,   # Int1.25 x Exh1.40 : blend above the top-end endpoint
}


def _apply_r08_wg_overlay(cal: CalFile) -> list[TableOutcome]:
    """Lower the six top-end cells in BOTH wastegate feedforward tables.

    Applies the identical :data:`R08_WG_DELTAS` map to VVL 0 and VVL 1 on top of
    the already-applied R05 overlay, refuses any cell that would clamp against the
    physical [0, 1] wastegate-position range, and raises if the two tables did not
    receive identical deltas or the changed-cell count is wrong (fail loud, never
    silently alter an unexpected number of cells).
    """
    outcomes: list[TableOutcome] = []
    applied_deltas: list[np.ndarray] = []

    for sym in R05_WG_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        before = np.array(view.values, dtype=np.float64, copy=True)

        for (r, c), d in R08_WG_DELTAS.items():
            new = float(values[r, c]) + d
            clamped = min(max(new, WG_MIN), WG_MAX)
            if clamped != new:
                raise ValueError(
                    f"{sym}: cell ({r},{c}) hit the physical WG bound "
                    f"[{WG_MIN}, {WG_MAX}] (target {new:.3f}); refusing to write a "
                    "clamped wastegate value — review R08_WG_DELTAS."
                )
            values[r, c] = clamped

        delta = values - before
        changed = int(np.count_nonzero(delta))
        if changed != len(R08_WG_DELTAS):
            raise ValueError(
                f"{sym}: expected {len(R08_WG_DELTAS)} changed cells, got {changed}"
            )

        view.set(values)
        applied_deltas.append(delta)

        detail = (
            f"{sym}  — {R05_WG_TITLE}: lowered {changed} top-end cells on top of "
            "the R05 overlay (open WG sooner above ~5800 rpm). Row-weighted onto "
            "the Int 1.05 row (-0.06 at Exh 1.00, -0.04 at Exh 1.40) with a "
            "mirrored Int 1.25 blend and a light Int 0.90 fringe (-0.02), sized "
            "from the clean 3rd-gear R07 logs: sustained top-end overshoot "
            "+8.5 kPa mean / +15.1 kPa max, worst 6200-6700 rpm band +10.6 kPa at "
            "Int ~1.04 x Exh ~1.10. Simulated bilinear lookup over the logs: "
            "-5.2% WG position in the worst band, -3.3 to -3.9% adjacent, 0.000 "
            "below 3300 rpm. Same deltas applied to both VVL tables; cells = WG "
            "position (1=closed, 0=open)."
        )
        outcomes.append(TableOutcome(sym, R08_SECTION_WG, OUTCOME_APPLIED, detail=detail))

    if not np.array_equal(applied_deltas[0], applied_deltas[1]):
        raise ValueError(
            "VVL 0 and VVL 1 wastegate tables received different deltas — the guide "
            "requires identical edits to both. Refusing to continue."
        )

    return outcomes


def _build_report_r08(
    recipe: RecipeReport,
    patch_results: list[btp.ChangeResult],
    tc_flags: list[dict],
    checksum_clean: bool,
    save_reports: list,
    sanity: btp.SanityResult,
    out_bin: Path,
) -> str:
    """Assemble the R08 review report: the R08 wastegate section, a condensed
    restatement of the inherited R07 patch/TC state, and the full recipe report."""
    L: list[str] = []
    L.append("# TUNE_Basics_Guide_R08 — top-end wastegate FF deepening (patched bin)")
    L.append("")
    L.append("## ⚠ FULL FLASH REQUIRED — do NOT flash CAL-only")
    L.append("")
    L.append("R08 inherits R07's switch-patched ASW, so this bin **must be flashed "
             "FULL** (not CAL-only) in the SimosTools app. **This script never "
             "flashes** — review, then flash externally with the stock recovery "
             "image on hand and the battery on a charger.")
    L.append("")
    L.append("## What R08 adds over R07")
    L.append("")
    L.append("Exactly one change: six cells lowered in `IP_FAC_BPA_SP[0]` / "
             "`IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward VVL 0/1 (XDF "
             "title \"Map for boost pressure actuator setpoint\"). No other table, "
             "axis, patch, or flag differs from the R07 bin — verify with "
             "`cal.unique_tables()` value-compare against the flashed R07 bin.")
    L.append("")
    L.append("| Cell (row, col) | Int FF x Exh FF | Delta  | Why |")
    L.append("|-----------------|-----------------|--------|-----|")
    why = {
        (6, 14): "top-end fringe (light — protects 3300-5200 rpm, mean err +0.1 kPa)",
        (6, 15): "top-end fringe (light)",
        (7, 14): "worst-band anchor: 6200-6700 rpm, +10.6 kPa at Int ~1.04 x Exh ~1.10",
        (7, 15): "top-end endpoint, shared with the good 5200-5800 band (err -2.4) — lighter",
        (8, 14): "Int 1.25 blend, mirrors row 7 (log reaches Int 1.063)",
        (8, 15): "Int 1.25 blend, mirrors row 7",
    }
    x_lbl = {14: "1.00", 15: "1.40"}
    y_lbl = {6: "0.90", 7: "1.05", 8: "1.25"}
    for (r, c), d in sorted(R08_WG_DELTAS.items()):
        L.append(f"| ({r}, {c}) | {y_lbl[r]} x {x_lbl[c]} | {d:+.2f} | {why[(r, c)]} |")
    L.append("")
    L.append("Evidence: clean 3rd-gear R07 pulls only (16_02_51 / 16_05_57 / "
             "16_07_36). The 2nd-gear pulls were excluded — 16_10_19 is "
             "contaminated by switch-patch TC interventions (up to 11.5 km/h "
             "front-vs-rear slip, torque cut ~410 -> 220-290 Nm), which also "
             "explains that pull's lean lambda tails. Simulated ECU bilinear "
             "lookup over every logged WOT point: -5.2% WG position mean in the "
             "worst 6200-6700 band (~70% of the guide's 0.05/psi rule), -3.3 to "
             "-3.9% in adjacent bands (absorbed by I-terms idling at -4 to -6%), "
             "0.000 below 3300 rpm.")
    L.append("")

    L.append("## Inherited R07 state (unchanged)")
    L.append("")
    L.append("| Patch                    | Bytes changed | in CAL | Confined |")
    L.append("|--------------------------|---------------|--------|----------|")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        L.append(f"| `{name}` | {res.changed_bytes:>13} | {res.changed_in_cal:>6} | "
                 f"{'YES':^8} |")
    L.append("")
    n_on = sum(1 for r in tc_flags if r["value"] == 1.0)
    L.append(f"- Switch-patch TC flags: **{n_on}/10 read back = 1** (`Enable SL TC` "
             "and `Disable OEM TC`, slots 1-5) — same all-five-slots decision as "
             "R07; the R07 logs confirmed the TC intervening on real 2nd-gear "
             "wheel slip.")
    L.append(f"- switch-patch XDF sanity: {sanity.tables_resolved} tables resolved, "
             f"{sanity.tables_decoded} decoded, {len(sanity.decode_errors)} errors, "
             f"plausible = {'YES' if sanity.plausible else 'NO'}.")
    L.append("")

    L.append("## Checksums")
    L.append("")
    L.append(f"- `CAL_CRC` — **corrected + {'CLEAN' if checksum_clean else 'STALE'}** "
             f"on the saved bin; `ECM3` — **{'CLEAN' if checksum_clean else 'STALE'}**.")
    L.append("- **ASW / code-block checksums — NOT verifiable here**; "
             "SimosTools/VW_Flash compute them at full-flash time.")
    L.append("")
    L.append(f"Saved bin: `{out_bin.name}` "
             f"({', '.join(r.name for r in save_reports)}).")
    L.append("")
    L.append("---")
    L.append("")
    L.append("# Inherited R00-R07 calibration report (+ R08 wastegate rows)")
    L.append("")
    L.append(format_report(recipe))
    return "\n".join(L)


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R08_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Apply the three .btp patches to the stock bin (order A, copy-on-write) —
    #    identical to R07.
    patched_base, patch_results = _apply_patches(BIN_PATH, out_dir / "patches")

    # 2. Full R06 CAL-edit pipeline on the patched base, then the R08 overlay.
    #    Snapshot the two wastegate tables AFTER the R05 overlay so the comparison
    #    PNGs show exactly the R07 -> R08 wastegate change.
    cal = CalFile.open(str(XDF_PATH), str(patched_base))
    recipe, _r05_snaps, _r05_outcomes = _run_r06_pipeline(cal)
    r08_snaps = _snapshot_r05_wg(cal)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        r08_outcomes = _apply_r08_wg_overlay(cal)
    recipe = RecipeReport(tuple(recipe.outcomes) + tuple(r08_outcomes))

    # 3. Stage save (checksums corrected at the final TC-flag save, as in R07),
    #    then the TC flags + final bin.
    stage_bin = out_dir / "_stage_r08_edited.bin"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(stage_bin), correct_checksums=False)
    out_bin = out_dir / OUT_BIN_NAME
    _tc_records, save_reports = _write_tc_flags(stage_bin, out_bin)

    # 4. Verify: checksums CLEAN, all ten TC flags decode to 1, switch-patch
    #    sanity plausible.
    verify_reports = CalFile.open(str(XDF_PATH), str(out_bin)).verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)
    tc_flags, _tc_behaviour = _read_tc_state(out_bin)
    all_on = all(r["value"] == 1.0 for r in tc_flags)
    sanity = btp.switch_patch_sanity(out_bin, stock_bin_path=BIN_PATH)

    # 5. Comparison PNGs — R07 -> R08 wastegate composites only.
    png_count, axis_changed = _write_r05_comparison_pngs(
        cal, r08_snaps, r08_outcomes, out_dir / "compare"
    )

    # 6. Review report.
    report_md = _build_report_r08(
        recipe, patch_results, tc_flags, clean, save_reports, sanity, out_bin
    )
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")

    # --- console summary --- #
    print("R08 — top-end wastegate FF deepening (patched bin)")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        print(f"  patch {name:24s}: {res.changed_bytes:>5} bytes changed "
              f"({res.changed_in_cal} CAL), confined={res.confined}")
    print(f"  R08 WG overlay : {len(R08_WG_DELTAS)} cells x 2 tables "
          f"(rows Int 0.90/1.05/1.25, cols Exh 1.00/1.40)")
    print(f"  TC flags       : {sum(1 for r in tc_flags if r['value'] == 1.0)}/10 read back = 1")
    print(f"  saved bin      : {out_bin}")
    print(f"  checksums      : {'CLEAN' if clean else 'STALE — NOT flash-ready'}"
          f" ({', '.join(r.name for r in save_reports)})")
    print(f"  switch sanity  : resolved {sanity.tables_resolved}, decoded "
          f"{sanity.tables_decoded}, plausible={sanity.plausible}")
    print(f"  report         : {out_dir / 'report.md'}")
    print(f"  comparison PNGs: {png_count} under {out_dir / 'compare'}"
          f" ({axis_changed} axis-changed table(s) reported in text instead)")

    problems = []
    if not clean:
        problems.append("checksums STALE")
    if not all_on:
        problems.append("not all TC flags decoded to 1")
    if not sanity.plausible:
        problems.append("switch-patch sanity not plausible")
    if recipe.do_not_flash():
        problems.append("recipe coherence: DO NOT FLASH")
    if problems:
        print(f"\n  ⛔ ISSUES: {'; '.join(problems)} — investigate before flashing.")
        raise SystemExit(f"R08 verification failed: {'; '.join(problems)}")
    else:
        print("\n  ✅ Patches confined, checksums CLEAN, all 10 TC flags = 1, "
              "switch-patch sanity plausible.")
        print("  ⚠ FULL FLASH REQUIRED (not CAL-only). Review report + PNGs, then "
              "flash externally. This is revision 8; iterate.")


if __name__ == "__main__":
    main()
