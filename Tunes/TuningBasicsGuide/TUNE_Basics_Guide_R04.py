#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R04.

R04 is based on R03 and keeps all R03 behavior unchanged, including the literal
0.80 writes to the three lambda minimum-value floors:

  * `C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint
  * `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating protection
  * `IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo charger overheating
    prevention versus engine speed

R04 adds a conservative ignition-only correction for the first R01 flash logs'
repeated -3.0 deg WOT knock retard. The correction is applied after the full R03
pipeline to all nine active low-port-flap STND timing tables:

  * `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle,
    VVL 0 Port Flap Low

The overlay targets the observed knock cells from the 2026-07-07 logs:

  * 3500-4000 rpm at about 1400 mg/stk
  * 5000-5500 rpm at about 1200-1400 mg/stk
  * a smaller 6000-6500 rpm cluster at about 1050 mg/stk

Wastegate flow-factor tuning is intentionally left untouched because the current
logs do not include the intake/exhaust flow-factor channels needed to select the
proper wastegate cells.

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

from TUNE_Basics_Guide_R03 import (
    BIN_PATH,
    OUT_ROOT,
    XDF_PATH,
    _apply_r03_writes,
    _merge_report,
    _rebreakpoint_lambda_family,
    _write_comparison_pngs,
)

OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R04.bin"

R04_SECTION_TIMING = "Timing — R04 knock-retard ignition overlay"
R04_TIMING_SYMBOLS = tuple(
    f"IP_IGA_BAS_IVVT_VVL_PORT_L[STND][{i}][{e}]" for i in range(3) for e in range(3)
)
R04_TIMING_TITLE = "Basic Ignition Angle, VVL 0 Port Flap Low"

# (rpm, load mg/stk, target deg). Values are storage-safe; when the exact intended
# value is not representable, use the next-more-retarded representable value.
R04_TIMING_TARGETS = (
    (3500.0, 1400.0, -9.00),
    (4000.0, 1400.0, -6.75),
    (5000.0, 1400.0, -2.25),
    (5000.0, 1200.0, -2.25),
    (5500.0, 1200.0, -0.75),
    (6000.0, 1049.97, 1.875),
    (6500.0, 1049.97, 3.375),
    # Blend cells to avoid sharp timing cliffs around the observed knock pockets.
    (3500.0, 1200.0, -6.00),
    (4000.0, 1200.0, -5.25),
    (4500.0, 1400.0, -3.75),
    (5500.0, 1400.0, 0.00),
    (5000.0, 1049.97, 1.125),
    (5500.0, 1049.97, 0.75),
    (6000.0, 900.0, 2.625),
    (6500.0, 900.0, 4.875),
)


def _nearest_index(values: np.ndarray, target: float) -> int:
    flat = np.asarray(values, dtype=np.float64).ravel()
    return int(np.argmin(np.abs(flat - target)))


def _snapshot_r04_timing_targets(cal: CalFile) -> dict[str, object]:
    """Snapshot R03-equivalent timing tables before the R04 overlay.

    The resulting comparison PNGs show R03 -> R04 local timing pulls, not stock -> R04.
    """
    return {sym: render_table(cal.get(sym)) for sym in R04_TIMING_SYMBOLS}


def _apply_r04_timing_overlay(cal: CalFile) -> list[TableOutcome]:
    """Apply local knock-retard timing pulls to all low-port-flap STND IGA tables."""
    outcomes: list[TableOutcome] = []

    for sym in R04_TIMING_SYMBOLS:
        view = cal.get(sym)
        values = np.array(view.values, dtype=np.float64, copy=True)
        x_axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
        y_axis = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()

        changed_cells: list[str] = []
        for rpm, load, target in R04_TIMING_TARGETS:
            x_idx = _nearest_index(x_axis, rpm)
            y_idx = _nearest_index(y_axis, load)
            old = float(values[y_idx, x_idx])
            values[y_idx, x_idx] = target
            changed_cells.append(
                f"{x_axis[x_idx]:.0f} rpm/{y_axis[y_idx]:.0f} mg/stk: "
                f"{old:.2f}->{target:.2f} ({target - old:+.2f})"
            )

        view.set(values)
        outcomes.append(TableOutcome(
            sym,
            R04_SECTION_TIMING,
            OUTCOME_APPLIED,
            detail=(
                f"{sym}  — {R04_TIMING_TITLE}: applied local WOT knock-retard "
                f"timing overlay; {'; '.join(changed_cells)}"
            ),
        ))

    return outcomes


def _write_r04_comparison_pngs(cal: CalFile, snaps: dict, r04_outcomes: list[TableOutcome], png_dir: Path) -> tuple[int, int]:
    """Emit R03->R04 comparison PNGs for only the R04 timing overlay rows."""
    r04_report = RecipeReport(tuple(r04_outcomes))
    return _write_comparison_pngs(cal, snaps, r04_report, png_dir)


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R04_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)

        # Snapshot after R03 is staged, immediately before the R04 overlay.
        r04_snaps = _snapshot_r04_timing_targets(cal)
        r04_outcomes = _apply_r04_timing_overlay(cal)

    report = RecipeReport(tuple(r03_report.outcomes) + tuple(r04_outcomes))

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")

    # Only R04 timing symbols receive R03->R04 snapshots. Other already-applied R03
    # report rows are skipped by compare_tables here, keeping the R04 PNGs focused.
    png_count, axis_changed = _write_r04_comparison_pngs(
        cal, r04_snaps, r04_outcomes, out_dir / "compare"
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
              "This is revision 4; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. This is revision 4; iterate.")


if __name__ == "__main__":
    main()
