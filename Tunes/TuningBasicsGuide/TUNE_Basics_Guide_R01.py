#!/usr/bin/env python3
"""Apply the ecu-tuning-basics SOP to the stock bin — TuningBasicsGuide, revision R01.

Extends R00. Same pipeline (open stock bin → stage recipe edits in memory → save
checksum-clean bin → verify → report + PNGs), into a fresh timestamped directory
under ``TUNE_Basics_Guide_out/`` so prior runs are kept for comparison.

R01 keeps everything R00 did (the lambda axis re-breakpoint — see below) and adds
six limiter/fuelling writes the base recipe left at stock, all with targets read
directly off the guide (``knowledge/ecu-tuning-basics.md`` §280-316, §340-379) and
verified against the bin:

    1. ID_PV_AV_FL       — Pedal value threshold for LV_FL_RAW    → flat 72 %
                           (guide: heavy-throttle table ~70-75 across; stock flat
                           99.9 %, so enrichment only near WOT — 72 fattens earlier)
    2. C_PRS_IM_SP_MAX   — Maximum allowed PRS_IM_SP               → 350000 hPa
                           (guide float-bug item; float32, stock 239996. 350000
                           exceeds the XDF *display* max 10000, so .set trips the
                           FloatBugGuard — written via set_raw, which is safe here:
                           our library writes float bytes directly and cannot hit
                           the TunerPro editor "float bug" the guard was motivated by)
    3+4. IP_M_AIR_CYL_MAX_STND_VVL[STND]/[LFT_1]
                         — Maximum intake air of the engine…       → flat 2000 mg/stk
                           (guide: two max-intake-air tables → 2000 across; stock
                           515-1275, well under the display max 2778 — clean .set)
    5. IP_TQI_REF_MAX_MON — Maximum reference indicated engine torque → flat 1000 Nm
                           (guide: "move out of the way", screenshot 58 shows flat
                           1000; stock 535-568, under the display max 1024 — clean .set)
    6. C_M_AIR_CYL_SP_MAX — Maximum allowed M_AIR_CYL_SP           → 0.002 (stored)
                           (guide float-bug item: "→ 2000 (if it displays wrong,
                           type 0.002)", screenshots 62-63. float32 with the XDF's
                           identity equation X, so this library reads/writes exactly
                           what TunerPro does. Stock stores 0.001389 (TunerPro shows
                           1389 — ×1e6, a kg/stroke↔mg/stk unit scale). The correct
                           stored value for the guide's target is therefore 0.002,
                           NOT 2000 — writing 2000 would set the ceiling ~1e6× too
                           high and would NOT trip any guard. See REV_LOG.md.)

R00's lambda axis re-breakpoint (unchanged, still runs first):

    The guide's Basic-lambda-setpoint grid was authored on a re-breakpointed bin,
    so on the stock bin the recipe reports IP_LAMB_BAS_HPDI[1] / MPI[1] as
    axis_mismatch and does NOT write them → LEAN RISK. R01 (like R00) re-breakpoints
    the two shared lambda axes (ldpm_n_32_1_lasp / ldpm_maf_1_lasp) to the guide's
    RPM/load breakpoints, lets the recipe write HPDI[1]/MPI[1] verbatim, and also
    rewrites IP_LAMB_BAS[1] (the third table on those shared axes) to stay coherent.

This is still **revision 1 — a starting point, not a finished calibration**: review
the report and PNGs, then flash → log → review → iterate. This script never flashes,
and a saved bin is not flash-ready while the report shows DO NOT FLASH.

Revision history (see REV_LOG.md):
    R00 — Initial revision. Base ecu-tuning-basics SOP plus the lambda axis
          re-breakpoint (HPDI[1] / MPI[1] / BAS[1] on guide breakpoints), which
          clears the base demo's LEAN-RISK DO NOT FLASH finding.
    R01 — Adds six limiter/fuelling writes the recipe left at stock: pedal
          threshold (72), max requested pressure (350000, set_raw), two max-intake-air
          tables (2000), max reference torque (1000), and max allowed airmass
          (stored 0.002 — the guide's float-bug value, not 2000).
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
OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R01.bin"

# --------------------------------------------------------------------------- #
# Lambda axis re-breakpoint — guide's Basic-lambda-setpoint grid + axes (R00).
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

# --------------------------------------------------------------------------- #
# R01 limiter/fuelling writes — targets straight off the guide, verified in-bin.
# Each value is the literal the guide prints; nothing is inferred beyond the
# documented float-bug unit fix on C_M_AIR_CYL_SP_MAX (0.002, not 2000).
# --------------------------------------------------------------------------- #
R01_SECTION_FUEL = "Fueling — Heavy-throttle pedal threshold (R01)"
R01_SECTION_LIM = "Limiters — R01 additions"

# 1. Pedal value threshold — guide: heavy-throttle table ~70-75 across → flat 72.
PEDAL_THRESHOLD_SYMBOL = "ID_PV_AV_FL"
PEDAL_THRESHOLD_VALUE = 72.0

# 2. Max requested pressure — guide float-bug item → 350000 (set_raw: above the
#    XDF display max, so .set would trip the FloatBugGuard).
PRS_MAX_SYMBOL = "C_PRS_IM_SP_MAX"
PRS_MAX_VALUE = 350000.0

# 3+4. Two max-intake-air tables → flat 2000 mg/stk.
INTAKE_AIR_SYMBOLS = (
    "IP_M_AIR_CYL_MAX_STND_VVL[STND]",
    "IP_M_AIR_CYL_MAX_STND_VVL[LFT_1]",
)
INTAKE_AIR_VALUE = 2000.0

# 5. Max reference indicated engine torque — guide: move out of the way → flat 1000.
TQ_REF_MAX_SYMBOL = "IP_TQI_REF_MAX_MON"
TQ_REF_MAX_VALUE = 1000.0

# 6. Max allowed airmass — guide: "→ 2000 (if it displays wrong, type 0.002)".
#    This is NOT a TunerPro rendering bug — it is a real unit scale. The ECU stores
#    this ceiling in kg/stk, but the XDF (both SC8S50.V1.0 and SC8S50.ALL) mislabels
#    it identity-scaled mg/stk (equation X, mg/stk, max 20000, addr 0x9BD4). So the
#    raw value for a 2000 mg/stk ceiling is 0.002 kg/stk. Stock decodes to 0.001389
#    (= 1389 mg/stk, just above the stock intake-air max ~1275) — proof the label is
#    wrong; a real ceiling can't be 0.0014 mg/stk. DO NOT "write the physical 2000":
#    2000 raw = 2000 kg/stk = 2,000,000 mg/stk (~1.44M x stock) = limiter removed.
#    Contrast items 3+4 above (IP_M_AIR_CYL_MAX_STND_VVL): those ARE genuine mg/stk,
#    so they correctly take 2000.0. See knowledge/ecu-tuning-basics.md note (2).
AIR_CYL_SP_MAX_SYMBOL = "C_M_AIR_CYL_SP_MAX"
AIR_CYL_SP_MAX_VALUE = 0.002  # 0.002 kg/stk == 2000 mg/stk (NOT 2000 raw)

# Recipe entries R01 supersedes: the recipe reports these as skip_vague /
# guard_blocked (it leaves the bytes at stock); R01 actually writes them, so its
# outcomes replace the recipe's rows in the merged report.
R01_SUPERSEDES = frozenset({PRS_MAX_SYMBOL, TQ_REF_MAX_SYMBOL, AIR_CYL_SP_MAX_SYMBOL})
# Every symbol R01 snapshots for before/after PNGs (non-scalar ones render; the
# two float32 scalars carry their old→new in the report text instead).
R01_TARGET_SYMBOLS = (
    PEDAL_THRESHOLD_SYMBOL,
    PRS_MAX_SYMBOL,
    *INTAKE_AIR_SYMBOLS,
    TQ_REF_MAX_SYMBOL,
    AIR_CYL_SP_MAX_SYMBOL,
)


def _snapshot_write_targets(cal: CalFile) -> dict[str, object]:
    """Pre-edit ``RenderedTable`` per recipe write-target symbol (for PNGs).

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


def _snapshot_r01_targets(cal: CalFile) -> dict[str, object]:
    """Pre-edit snapshot of the R01 write targets (stock, before any edits)."""
    snaps: dict[str, object] = {}
    for sym in R01_TARGET_SYMBOLS:
        try:
            snaps[sym] = render_table(cal.get(sym))
        except Exception:  # noqa: BLE001 - reported as unresolved by the writer instead
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


def _apply_r01_writes(cal: CalFile) -> list[TableOutcome]:
    """Stage the six R01 limiter/fuelling writes; return their report rows.

    Runs AFTER :func:`apply_basics_sop`. None of these six collide with the
    recipe: the recipe leaves ID_PV_AV_FL and the two intake-air tables untouched,
    and reports C_PRS_IM_SP_MAX / IP_TQI_REF_MAX_MON / C_M_AIR_CYL_SP_MAX as
    skip/guard_blocked (bytes at stock). The returned outcomes supersede those
    three recipe rows in the merged report (see :data:`R01_SUPERSEDES`).
    """
    outcomes: list[TableOutcome] = []

    # 1. Pedal value threshold → flat 72 % (heavy-throttle enrichment before WOT).
    pv = cal.get(PEDAL_THRESHOLD_SYMBOL)
    pv.set(np.full(pv.shape, PEDAL_THRESHOLD_VALUE, dtype=np.float64))
    outcomes.append(TableOutcome(
        PEDAL_THRESHOLD_SYMBOL, R01_SECTION_FUEL, OUTCOME_APPLIED,
        detail=(f"pedal threshold → flat {PEDAL_THRESHOLD_VALUE:g}% "
                f"(guide: heavy-throttle ~70-75 across; stock flat 99.9%)"),
    ))

    # 2. Max requested pressure → 350000 hPa via set_raw (above XDF display max;
    #    identity equation X so raw==physical for this float32 constant).
    prv = cal.get(PRS_MAX_SYMBOL)
    prs_old = float(np.asarray(prv.values).ravel()[0])
    prv.set_raw(np.array([[PRS_MAX_VALUE]], dtype=np.float64))
    outcomes.append(TableOutcome(
        PRS_MAX_SYMBOL, R01_SECTION_LIM, OUTCOME_APPLIED,
        detail=("max requested pressure → 350000 hPa (guide float-bug item; "
                "set_raw bypasses the FloatBugGuard — display max is a TunerPro "
                "editor artifact, not an ECU limit)"),
        old=prs_old, new=PRS_MAX_VALUE,
    ))

    # 3+4. Two max-intake-air tables → flat 2000 mg/stk.
    for sym in INTAKE_AIR_SYMBOLS:
        iv = cal.get(sym)
        iv.set(np.full(iv.shape, INTAKE_AIR_VALUE, dtype=np.float64))
        outcomes.append(TableOutcome(
            sym, R01_SECTION_LIM, OUTCOME_APPLIED,
            detail=(f"max intake air → flat {INTAKE_AIR_VALUE:g} mg/stk "
                    f"(guide: two tables → 2000 across; stock 515-1275)"),
        ))

    # 5. Max reference indicated engine torque → flat 1000 Nm.
    tv = cal.get(TQ_REF_MAX_SYMBOL)
    tv.set(np.full(tv.shape, TQ_REF_MAX_VALUE, dtype=np.float64))
    outcomes.append(TableOutcome(
        TQ_REF_MAX_SYMBOL, R01_SECTION_LIM, OUTCOME_APPLIED,
        detail=(f"max reference torque → flat {TQ_REF_MAX_VALUE:g} Nm "
                f"(guide: move out of the way; stock 535-568)"),
    ))

    # 6. Max allowed airmass → stored 0.002 (guide float-bug fix, NOT 2000).
    av = cal.get(AIR_CYL_SP_MAX_SYMBOL)
    air_old = float(np.asarray(av.values).ravel()[0])
    av.set(np.array([[AIR_CYL_SP_MAX_VALUE]], dtype=np.float64))
    outcomes.append(TableOutcome(
        AIR_CYL_SP_MAX_SYMBOL, R01_SECTION_LIM, OUTCOME_APPLIED,
        detail=("max allowed airmass → stored 0.002 (guide float-bug item: "
                "'2000 (if it displays wrong, type 0.002)'. float32 identity "
                "equation X, so 0.002 is the correct stored value — 2000 would "
                "be ~1e6× too high, a kg/stroke↔mg/stk unit scale)"),
        old=air_old, new=AIR_CYL_SP_MAX_VALUE,
    ))

    return outcomes


def _merge_report(
    lambda_outcomes: list[TableOutcome],
    recipe: RecipeReport,
    r01_outcomes: list[TableOutcome],
) -> RecipeReport:
    """Merge the pre-pass, recipe, and R01 outcomes into one report.

    Recipe rows for the three symbols R01 actually writes are dropped
    (superseded) so the report shows each table once, with its true final state.
    """
    kept = tuple(o for o in recipe.outcomes if o.symbol not in R01_SUPERSEDES)
    return RecipeReport(tuple(lambda_outcomes) + kept + tuple(r01_outcomes))


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
    out_dir = OUT_ROOT / f"R01_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal = CalFile.open(XDF_PATH, BIN_PATH)
    snaps = _snapshot_write_targets(cal)  # recipe targets, stock (before edits)
    snaps.update(_snapshot_r01_targets(cal))  # R01 targets, stock (before edits)

    # Apply the recipe (stages edits in memory) — squelch the expected
    # out-of-XDF-range warnings; they are captured into the report instead. The
    # lambda re-breakpoint runs first so HPDI[1]/MPI[1] axis-match and get written;
    # the R01 writes run after so they supersede the recipe's skip/guard rows.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r01_outcomes = _apply_r01_writes(cal)

    report = _merge_report(lambda_outcomes, recipe_report, r01_outcomes)

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
              "This is revision 1; review, then iterate.")
    else:
        print("\n  ✅ Coherence check passed — still review the report + PNGs and "
              "verify checksums before flashing. This is revision 1; iterate.")


if __name__ == "__main__":
    main()
