#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R00.

Adapted from ``Code/demos/apply_sop_recipe.py``. Same pipeline (open stock bin →
stage recipe edits in memory → save checksum-clean bin → verify → report + PNGs),
into a fresh timestamped directory under ``TUNE_Basics_Guide_out/`` so prior runs
are kept for comparison.

What R00 adds over the base demo — the **lambda axis re-breakpoint**:

    The guide's Basic-lambda-setpoint grid was authored on a re-breakpointed bin,
    so on the stock bin the base demo reports IP_LAMB_BAS_HPDI[1] / MPI[1] as
    ``axis_mismatch`` and does NOT write them. Boost is raised but fuelling is
    not → **LEAN RISK at full load** (the base demo's DO NOT FLASH banner).

    R00 re-breakpoints the two *shared* lambda axes (the named breakpoint tables
    ``ldpm_n_32_1_lasp`` / ``ldpm_maf_1_lasp`` at 0xb2e1 / 0x54700) to the guide's
    RPM/load breakpoints, then lets the recipe write the guide's 8×12 grid to
    HPDI[1] and MPI[1] verbatim. Those two axes are shared by a THIRD table,
    ``IP_LAMB_BAS[1]``, which the recipe does not target — so R00 also rewrites
    ``IP_LAMB_BAS[1]``'s cells to the same guide grid, keeping the whole lambda
    setpoint family coherent on the new breakpoints (never leave a table's cells
    reinterpreted on axes it didn't author). The shared axes are used ONLY by this
    lambda family (verified against the XDF), so the blast radius is contained.

    With fuelling now in place, the recipe's coherence check clears the lambda
    LEAN-RISK finding automatically (it reasons about *state*, not bytes).

This is still **revision 0 — a starting point, not a finished calibration**:
review the report and PNGs, then flash → log → review → iterate. This script
never flashes, and a saved bin is not flash-ready while the report shows DO NOT
FLASH. See ``REV_LOG.md`` for revision lineage.

Revision history (see REV_LOG.md):
    R00 — Initial revision. Base ecu-tuning-basics SOP plus the lambda axis
          re-breakpoint (HPDI[1] / MPI[1] / BAS[1] written on guide breakpoints),
          which clears the base demo's LEAN-RISK DO NOT FLASH finding.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import (
    CalFile,
    TableMismatchError,
    apply_basics_sop,
    compare_tables,
    format_report,
    render_table,
    resolve_symbol_map,
)
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import (
    KIND_AXIS_WRITE,
    OUTCOME_APPLIED,
    OUTCOME_APPLIED_BUILDOUT,
    RecipeReport,
    TableOutcome,
    is_write_kind,
)

# Code/ holds the library, XDF and bin; this script lives in Tunes/TuningBasicsGuide/.
CODE_ROOT = Path(__file__).resolve().parents[2] / "Code"
XDF_PATH = CODE_ROOT / "xdf" / "SC8S50.V1.0.xdf"
BIN_PATH = CODE_ROOT / "bin" / "5G0906259L__0002.bin"
OUT_ROOT = Path(__file__).resolve().parent / "TUNE_Basics_Guide_out"
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R00.bin"

# --------------------------------------------------------------------------- #
# Lambda axis re-breakpoint — guide's Basic-lambda-setpoint grid + axes.
# The guide authored this map on a re-breakpointed bin; we reproduce the exact
# breakpoints and 8×12 grid rather than resample. Values are kept explicit and
# reviewable (safety: never write fuelling numbers that aren't on the page).
# --------------------------------------------------------------------------- #
LAMBDA_SECTION = "Fueling — Basic lambda setpoint (HPDI + MPI)"
LAMBDA_X = (1504, 2016, 2496, 3008, 3488, 4000, 4512, 4992, 5504, 5984, 6496, 7008)
LAMBDA_Y = (150.00, 299.99, 500.01, 700.00, 899.99, 1100.01, 1200.01, 1389.00)
LAMBDA_CELLS = (
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.92, 0.89, 0.87, 0.87),
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.95, 0.92, 0.89, 0.87, 0.85, 0.85),
    (1.00, 1.00, 1.00, 1.00, 0.97, 0.95, 0.92, 0.88, 0.86, 0.84, 0.82, 0.82),
    (1.00, 1.00, 1.00, 1.00, 0.95, 0.92, 0.88, 0.84, 0.83, 0.81, 0.80, 0.80),
    (1.00, 1.00, 1.00, 0.98, 0.93, 0.89, 0.87, 0.82, 0.80, 0.80, 0.80, 0.80),
    (1.00, 1.00, 0.98, 0.95, 0.90, 0.86, 0.84, 0.82, 0.80, 0.80, 0.80, 0.80),
)
# The two named breakpoint tables that ARE the shared lambda axes.
LAMBDA_X_AXIS_SYMBOL = "ldpm_n_32_1_lasp"   # RPM breakpoints (0xb2e1)
LAMBDA_Y_AXIS_SYMBOL = "ldpm_maf_1_lasp"    # load breakpoints (0x54700)
# The full lambda setpoint family sharing those axes. HPDI[1]/MPI[1] are written
# by the recipe once the axes match; BAS[1] is not in the recipe, so we write it
# here to keep the family coherent on the re-breakpointed axes.
LAMBDA_BASE_SYMBOL = "IP_LAMB_BAS[1]"


def _snapshot_write_targets(cal: CalFile) -> dict[str, object]:
    """Pre-edit ``RenderedTable`` per write-target symbol (for before/after PNGs).

    We can't know the final per-table outcome before applying, so we snapshot
    every resolved table belonging to a write-kind entry; snapshots whose entry
    ends up skipped are simply never looked up again.
    """
    snaps: dict[str, object] = {}
    for resolved in resolve_symbol_map(cal):
        entry = resolved.entry
        if not is_write_kind(entry.kind):
            continue
        for res in resolved.resolutions:
            if res.resolved and res.view is not None:
                snaps[res.symbol] = render_table(res.view)
        # axis_write also drives a separate axis table beyond its own symbol.
        if entry.kind == KIND_AXIS_WRITE and resolved.resolutions[0].resolved:
            axis_symbol = entry.target.axis_symbol
            try:
                snaps[axis_symbol] = render_table(cal.get(axis_symbol))
            except Exception:  # noqa: BLE001 - a missing axis table is simply not snapshotted
                pass
    return snaps


def _rebreakpoint_lambda_family(cal: CalFile) -> list[TableOutcome]:
    """Re-breakpoint the shared lambda axes and write BAS[1]'s cells (R00 pre-pass).

    Must run BEFORE :func:`apply_basics_sop` so that, with the axes now matching
    the guide's breakpoints, the recipe's literal writer accepts and writes
    HPDI[1] / MPI[1] instead of reporting ``axis_mismatch``. Returns synthetic
    :class:`TableOutcome` rows so the report honestly records the axis writes and
    the BAS[1] cell write (which the recipe itself does not cover).

    Guards stay live: writes go through the range-checked ``set`` (no ``override``);
    only the expected out-of-display-range *warnings* are squelched by the caller.
    """
    outcomes: list[TableOutcome] = []
    grid = np.array(LAMBDA_CELLS, dtype=np.float64)

    xv = cal.get(LAMBDA_X_AXIS_SYMBOL)
    xv.set(np.array(LAMBDA_X, dtype=np.float64).reshape(xv.shape))
    outcomes.append(TableOutcome(
        LAMBDA_X_AXIS_SYMBOL, LAMBDA_SECTION, OUTCOME_APPLIED,
        detail=(f"re-breakpointed shared RPM axis to guide "
                f"({len(LAMBDA_X)} bp, {LAMBDA_X[0]}–{LAMBDA_X[-1]}); "
                "shared by BAS/HPDI/MPI lambda tables"),
    ))

    yv = cal.get(LAMBDA_Y_AXIS_SYMBOL)
    yv.set(np.array(LAMBDA_Y, dtype=np.float64).reshape(yv.shape))
    outcomes.append(TableOutcome(
        LAMBDA_Y_AXIS_SYMBOL, LAMBDA_SECTION, OUTCOME_APPLIED,
        detail=(f"re-breakpointed shared load axis to guide "
                f"({len(LAMBDA_Y)} bp, {LAMBDA_Y[0]:g}–{LAMBDA_Y[-1]:g}); "
                "shared by BAS/HPDI/MPI lambda tables"),
    ))

    bv = cal.get(LAMBDA_BASE_SYMBOL)
    bv.set(grid)
    outcomes.append(TableOutcome(
        LAMBDA_BASE_SYMBOL, LAMBDA_SECTION, OUTCOME_APPLIED,
        detail=("wrote 8x12 guide lambda grid; kept coherent with HPDI[1]/MPI[1] "
                "on the re-breakpointed shared axes"),
    ))
    return outcomes


def _write_comparison_pngs(cal: CalFile, snaps: dict, report, png_dir: Path) -> tuple[int, int]:
    """Emit a before/after PNG per changed non-scalar table. Returns (pngs, skipped)."""
    png_count, axis_changed = 0, 0
    for out in report.outcomes:
        if out.outcome not in (OUTCOME_APPLIED, OUTCOME_APPLIED_BUILDOUT):
            continue
        before = snaps.get(out.symbol)
        if before is None:
            continue
        try:
            after = cal.get(out.symbol)
        except Exception:  # noqa: BLE001
            continue
        try:
            paths = compare_tables(before, after, png_dir)  # scalars → [] by design
        except TableMismatchError:
            # A table whose own axis was re-breakpointed (the lambda family, and
            # PUT setpoint's Y axis) — before/after axes differ, so a composite
            # would be misleading. The report's detail covers it instead.
            axis_changed += 1
            continue
        png_count += len(paths)
    return png_count, axis_changed


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R00_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)
    snaps = _snapshot_write_targets(cal)  # stock, before any edits

    # Apply the recipe (stages edits in memory) — squelch the expected
    # out-of-XDF-range warnings; they are captured into the report instead. The
    # lambda re-breakpoint runs first so HPDI[1]/MPI[1] axis-match and get written.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        report = apply_basics_sop(cal)

    # Merge the pre-pass outcomes so the report reflects everything R00 wrote;
    # coherence/DO NOT FLASH is recomputed from the merged outcomes.
    report = RecipeReport(tuple(lambda_outcomes) + report.outcomes)

    out_bin = out_dir / OUT_BIN_NAME
    save_reports = cal.save(out_bin, correct_checksums=True)
    verify_reports = cal.verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)

    (out_dir / "report.md").write_text(format_report(report), encoding="utf-8")
    png_count, axis_changed = _write_comparison_pngs(
        cal, snaps, report, out_dir / "compare"
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
              "This is revision 0; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. This is revision 0; iterate.")


if __name__ == "__main__":
    main()
