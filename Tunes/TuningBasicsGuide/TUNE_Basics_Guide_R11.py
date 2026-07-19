#!/usr/bin/env python3
"""TuningBasicsGuide R11 — explicit switch-patch PUT caps (patched bin).

R11 starts from the untouched recovery image, applies the established CBRICK,
HSL, and 5-slot switch-patch pipeline, then reproduces the R06/R08/R10 base
calibration.  It deliberately does *not* call the R09 helpers: instead it
parks `IP_PUT_SP` — Pressure up throttle setpoint at a non-binding 30 psi
gauge-equivalent full-load ceiling and gives every selectable patch `PUT
setpoint` grid an explicit lower cap.  The output is CAL-flash eligible only
when the verified R07 patch set is already installed; otherwise installing or
changing the patch set requires a human-reviewed FULL flash.  This script never
flashes an ECU.

Revision history: R00 SOP baseline; R01 limiters/fuelling; R02 report-only;
R03 lambda floors; R04 knock timing; R05/R08 wastegate feedforward; R06 P0234
threshold fix; R07 patches + TC; R09 slot-2 shelf; R10 `IP_PQ_CHA_MAX` —
Maximum allowed pressure quotient at turbo charger compressor.  R11 moves the
WOT target shape into all five patch grids while retaining the R10 compressor,
fuel, timing, wastegate, and traction-control calibration unchanged.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import CalFile, btp, compare_tables, format_report, render_table
from simoscal.checksum import StaleChecksumWarning
from simoscal.codec import file_offset_for
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import OUTCOME_APPLIED, RecipeReport, TableOutcome

from TUNE_Basics_Guide_R03 import BIN_PATH, OUT_ROOT, XDF_PATH
from TUNE_Basics_Guide_R07 import (
    BT_XDF,
    PATCHES,
    _apply_patches,
    _read_tc_state,
    _run_r06_pipeline,
    _write_tc_flags,
)
from TUNE_Basics_Guide_R08 import _apply_r08_wg_overlay
from TUNE_Basics_Guide_R09 import (
    AMBIENT_HPA,
    IP_PUT_AXIS_SYMBOL,
    IP_PUT_SP_SYMBOL,
    IP_PUT_TOP_ROW,
    PSI_PER_HPA,
    R09_PUT_AXIS_NEW,
    R09_PUT_AXIS_OLD,
    R09_PUT_TOPROW_NEW,
    R09_PUT_TOPROW_OLD,
    _psi,
)
from TUNE_Basics_Guide_R10 import IP_PQ_SYMBOL, _apply_r10_pq_cha_max


OUT_BIN_NAME = "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R11.bin"
R10_REFERENCE = (
    OUT_ROOT / "R10_20260713-000102" /
    "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R10.bin"
)

# The stored calibration is absolute hPa.  Convert 30 psi gauge once using the
# documented reference; half-up gives the approved stored 3085 hPa ceiling.
R11_SHARED_CEILING_HPA = float(int(30.0 * PSI_PER_HPA + AMBIENT_HPA + 0.5))
R11_SLOT_RPM_AXIS = np.asarray(
    [3000, 3200, 3400, 3800, 4400, 4700, 5000, 5400, 5750, 6000, 6250, 6500],
    dtype=np.float64,
)

# Bright-green sketch: 24.4 psi plateau through 4400 rpm, then a smooth taper
# through roughly 22.3 psi at 5200 rpm to 17.5 psi at 6500 rpm.  These are hPa
# absolute values, never gauge-psi writes.
R11_SLOT2_CURVE_HPA = np.asarray(
    [2699, 2699, 2699, 2699, 2699, 2645, 2589, 2503, 2414, 2350, 2286, 2223],
    dtype=np.float64,
)

CAP_DEFAULT_HPA = 4000.0
CAP_ROWS, CAP_COLS = 8, 12
PUT_GRID_UIDS = {
    1: "0x7d41a", 2: "0x7d4da", 3: "0x7d59a", 4: "0x7d65a", 5: "0x7d71a",
}
PUT_AXIS_UID = "0x7d7dc"
PUT_AXIS_HEADER_UID = "0x7d7da"
PUT_AXIS_HEADER_VALUE = 12.0


def _resample(axis: np.ndarray, source_axis: list[float], source: list[float]) -> np.ndarray:
    """Clamped-linear resample of a documented source target."""
    return np.interp(axis, source_axis, source).astype(np.float64)


R11_SLOT1_CURVE_HPA = _resample(R11_SLOT_RPM_AXIS, R09_PUT_AXIS_OLD, R09_PUT_TOPROW_OLD)
R11_SLOT3_CURVE_HPA = _resample(R11_SLOT_RPM_AXIS, R09_PUT_AXIS_NEW, R09_PUT_TOPROW_NEW)
R11_SLOT_CURVES_HPA = {
    1: R11_SLOT1_CURVE_HPA,
    2: R11_SLOT2_CURVE_HPA,
    3: R11_SLOT3_CURVE_HPA,
    4: R11_SLOT1_CURVE_HPA.copy(),
    5: R11_SLOT1_CURVE_HPA.copy(),
}


def _validate_r11_configuration() -> None:
    """Reject unsafe/misaligned R11 configuration before any bin is opened."""
    axis = R11_SLOT_RPM_AXIS
    if axis.shape != (CAP_COLS,) or not np.all(np.isfinite(axis)) or not np.all(np.diff(axis) > 0):
        raise ValueError(f"R11 PUT SP RPM Axis: expected {CAP_COLS} finite increasing values, got {axis.tolist()}.")
    if not np.array_equal(axis[[0, 2, 4, 6, 8, 11]], np.asarray(R09_PUT_AXIS_NEW)):
        raise ValueError("R11 PUT SP RPM Axis no longer preserves all R09 `IP_PUT_SP` anchors.")
    if set(R11_SLOT_CURVES_HPA) != set(PUT_GRID_UIDS):
        raise ValueError("R11 slot-curve map must contain exactly slots 1 through 5.")
    for slot, curve in R11_SLOT_CURVES_HPA.items():
        if curve.shape != (CAP_COLS,) or not np.all(np.isfinite(curve)):
            raise ValueError(f"slot {slot}: expected {CAP_COLS} finite cap values.")
        if not np.all((curve > 0) & (curve < R11_SHARED_CEILING_HPA)):
            raise ValueError(f"slot {slot}: cap must be positive and strictly below {R11_SHARED_CEILING_HPA} hPa.")
    if not (np.array_equal(R11_SLOT_CURVES_HPA[1], R11_SLOT_CURVES_HPA[4])
            and np.array_equal(R11_SLOT_CURVES_HPA[1], R11_SLOT_CURVES_HPA[5])):
        raise ValueError("slots 1, 4, and 5 must retain the same R08-style curve.")
    slot2 = R11_SLOT_CURVES_HPA[2]
    slot1 = R11_SLOT_CURVES_HPA[1]
    if not np.isclose(slot2.max(), slot1.max(), atol=0.01):
        raise ValueError("slot 2 must equal slot 1's maximum target.")
    plateau = slot2[axis <= 4400]
    if not np.allclose(plateau, slot2.max(), atol=0.01):
        raise ValueError("slot 2 must remain flat at its maximum through 4400 rpm.")
    after_4400 = axis > 4400
    if not np.all(slot2[after_4400] > slot1[after_4400]):
        raise ValueError("slot 2 must remain strictly above slot 1 after 4400 rpm.")


def _apply_r11_shared_put_ceiling(cal: CalFile) -> list[TableOutcome]:
    """Set only the full-load `IP_PUT_SP` — Pressure up throttle setpoint row.

    The R08 baseline is asserted before its private RPM axis is retained in R09
    layout.  Lower rows must remain byte-identical; the parked base can only be
    safe when all five lower patch caps are verified later in this script.
    """
    axis_view = cal.get(IP_PUT_AXIS_SYMBOL)
    old_axis = np.asarray(axis_view.values, dtype=np.float64).ravel()
    if not np.allclose(old_axis, R09_PUT_AXIS_OLD, atol=1.0):
        raise ValueError(
            f"{IP_PUT_AXIS_SYMBOL}: expected R08 axis {R09_PUT_AXIS_OLD}, found {old_axis.tolist()}."
        )
    view = cal.get(IP_PUT_SP_SYMBOL)
    z = np.asarray(view.values, dtype=np.float64)
    if z.shape != (4, 6) or not np.allclose(z[IP_PUT_TOP_ROW], R09_PUT_TOPROW_OLD, atol=2.0):
        raise ValueError(
            f"{IP_PUT_SP_SYMBOL} — Pressure up throttle setpoint: R08 full-load baseline mismatch."
        )
    part_load = z[:IP_PUT_TOP_ROW].copy()
    axis_view.set(np.asarray(R09_PUT_AXIS_NEW, dtype=np.float64).reshape(axis_view.shape))
    new_z = z.copy()
    new_z[IP_PUT_TOP_ROW] = R11_SHARED_CEILING_HPA
    view.set(new_z)
    readback = np.asarray(cal.get(IP_PUT_SP_SYMBOL).values, dtype=np.float64)
    if not np.array_equal(readback[:IP_PUT_TOP_ROW], part_load):
        raise ValueError(f"{IP_PUT_SP_SYMBOL} — Pressure up throttle setpoint: part-load rows moved.")
    if not np.allclose(readback[IP_PUT_TOP_ROW], R11_SHARED_CEILING_HPA, atol=2.0):
        raise ValueError(f"{IP_PUT_SP_SYMBOL} — Pressure up throttle setpoint: shared ceiling readback failed.")
    return [TableOutcome(
        IP_PUT_SP_SYMBOL, "Boost — R11 parked shared PUT ceiling", OUTCOME_APPLIED,
        detail=(f"{IP_PUT_SP_SYMBOL} — Pressure up throttle setpoint: retained private "
                f"RPM axis {R09_PUT_AXIS_NEW}; wrote only full-load row to the non-binding "
                f"{R11_SHARED_CEILING_HPA:.0f} hPa ({_psi(R11_SHARED_CEILING_HPA):.1f} psi gauge) "
                "ceiling. All part-load rows are byte-identical to R08."),
    )]


def _write_r11_slot_caps(bin_in: Path, bin_out: Path) -> list[dict]:
    """Write/read back the shared patch axis and every tiled slot cap."""
    cal = CalFile.open(str(BT_XDF), str(bin_in))
    header = float(np.asarray(cal.get(PUT_AXIS_HEADER_UID).values, dtype=np.float64).item())
    if not np.isclose(header, PUT_AXIS_HEADER_VALUE):
        raise SystemExit(f"PUT SP RPM Axis Header at 0x7D7DA is {header}, not {PUT_AXIS_HEADER_VALUE}.")
    old_axis = np.asarray(cal.get(PUT_AXIS_UID).values, dtype=np.float64).ravel()
    expected_old_axis = np.asarray([2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500])
    if not np.allclose(old_axis, expected_old_axis, atol=1.0):
        raise SystemExit(f"PUT SP RPM Axis: expected as-patched {expected_old_axis.tolist()}, got {old_axis.tolist()}.")
    for slot, uid in PUT_GRID_UIDS.items():
        old = np.asarray(cal.get(uid).values, dtype=np.float64)
        if old.shape != (CAP_ROWS, CAP_COLS) or not np.allclose(old, CAP_DEFAULT_HPA, atol=1.0):
            raise SystemExit(
                f"slot {slot} PUT setpoint at {uid}: expected as-patched {CAP_DEFAULT_HPA} hPa "
                f"{CAP_ROWS}x{CAP_COLS} default, got shape {old.shape} range {old.min():.1f}-{old.max():.1f}."
            )
    axis_view = cal.get(PUT_AXIS_UID)
    axis_view.set(R11_SLOT_RPM_AXIS.reshape(axis_view.shape))
    records: list[dict] = []
    for slot, uid in PUT_GRID_UIDS.items():
        curve = R11_SLOT_CURVES_HPA[slot]
        cal.get(uid).set(np.tile(curve, (CAP_ROWS, 1)))
        records.append({"slot": slot, "uid": uid, "curve": curve.copy()})
    new_axis = np.asarray(cal.get(PUT_AXIS_UID).values, dtype=np.float64).ravel()
    if not np.allclose(new_axis, R11_SLOT_RPM_AXIS, atol=1.0):
        raise SystemExit("PUT SP RPM Axis readback mismatch after write.")
    if not np.isclose(float(np.asarray(cal.get(PUT_AXIS_HEADER_UID).values).item()), PUT_AXIS_HEADER_VALUE):
        raise SystemExit("PUT SP RPM Axis Header changed from 12.")
    for rec in records:
        actual = np.asarray(cal.get(rec["uid"]).values, dtype=np.float64)
        if not np.allclose(actual, np.tile(rec["curve"], (CAP_ROWS, 1)), atol=2.0):
            raise SystemExit(f"slot {rec['slot']} PUT setpoint readback mismatch.")
        if np.allclose(actual, CAP_DEFAULT_HPA, atol=1.0):
            raise SystemExit(f"slot {rec['slot']} PUT setpoint remained non-binding default.")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(bin_out), correct_checksums=False)
    return records


def _write_r11_curve_plots(out_dir: Path) -> list[Path]:
    """Render all-five review plot plus the requested fixed-scale slots 1–3 plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    roles = {1: "slot 1 — R08 conservative", 2: "slot 2 — intermediate", 3: "slot 3 — former 26 psi shelf", 4: "slot 4 — retained R08", 5: "slot 5 — retained R08"}
    colours = {1: "#1f77b4", 2: "#00b140", 3: "#d62728", 4: "#9467bd", 5: "#8c564b"}
    paths: list[Path] = []
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axhline(_psi(R11_SHARED_CEILING_HPA), color="#555555", linestyle="--", label="shared IP_PUT_SP ceiling")
    for slot in range(1, 6):
        ax.plot(R11_SLOT_RPM_AXIS, [_psi(h) for h in R11_SLOT_CURVES_HPA[slot]], "o-", color=colours[slot], label=roles[slot])
    ax.set(xlabel="Engine speed (rpm)", ylabel="Boost target (psi gauge)", title="R11 effective WOT targets — shared ceiling and all patch slots")
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8); fig.tight_layout()
    path = out_dir / "r11_all_slot_targets.png"; fig.savefig(path, dpi=120); plt.close(fig); paths.append(path)
    fig, ax = plt.subplots(figsize=(10, 6))
    for slot in (1, 2, 3):
        ax.plot(R11_SLOT_RPM_AXIS, [_psi(h) for h in R11_SLOT_CURVES_HPA[slot]], "o-", color=colours[slot], label=roles[slot])
    ax.set(xlabel="Engine speed (rpm)", ylabel="Boost target (psi gauge)", title="R11 boost target vs RPM — slots 1, 2, and 3", ylim=(0, 30))
    ax.set_yticks(np.arange(0, 31, 5)); ax.grid(True, alpha=0.3); ax.legend(); fig.tight_layout()
    path = out_dir / "r11_slots_1_2_3_boost_target.png"; fig.savefig(path, dpi=120); plt.close(fig); paths.append(path)
    return paths


def _byte_offsets(view, *, rows: list[int] | None = None) -> set[int]:
    """Return byte offsets for selected rows of an XDF-backed table."""
    emb = view.table.z.embedded
    assert emb is not None
    start = file_offset_for(emb.address, view._cal.model.base_offset, view._cal.model.base_subtract)
    width = emb.elem_bits // 8
    wanted = range(emb.rows) if rows is None else rows
    offsets: set[int] = set()
    for row in wanted:
        for col in range(emb.cols):
            index = col * emb.rows + row if emb.column_major else row * emb.cols + col
            offsets.update(range(start + index * width, start + (index + 1) * width))
    return offsets


def _raw_diff_audit(r10_bin: Path, r11_bin: Path) -> dict:
    """Account for every R10→R11 raw difference: declared data plus CAL_CRC."""
    before, after = r10_bin.read_bytes(), r11_bin.read_bytes()
    if len(before) != len(after):
        raise ValueError("R10/R11 file-size mismatch.")
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    r11 = CalFile.open(str(XDF_PATH), str(r11_bin))
    allowed = _byte_offsets(r11.get(IP_PUT_SP_SYMBOL), rows=[IP_PUT_TOP_ROW])
    bt = CalFile.open(str(BT_XDF), str(r11_bin))
    allowed |= _byte_offsets(bt.get(PUT_AXIS_UID))
    for uid in PUT_GRID_UIDS.values():
        allowed |= _byte_offsets(bt.get(uid))
    allowed |= set(range(0x200304, 0x200308))  # corrected CAL_CRC storage
    unexplained = changed - allowed
    if unexplained:
        sample = ", ".join(hex(x) for x in sorted(unexplained)[:12])
        raise ValueError(f"R10→R11 raw diff has {len(unexplained)} unexplained byte(s): {sample}.")
    return {"changed": len(changed), "allowed": len(allowed), "unexplained": 0}


def _build_report(recipe: RecipeReport, patch_results: list[btp.ChangeResult], tc_flags: list[dict],
                  save_reports: list, sanity: btp.SanityResult, out_bin: Path,
                  checksum_clean: bool, base_ok: bool, slots_ok: bool,
                  raw_audit: dict, plots: list[Path],
                  base_actual: np.ndarray, patch_axis_actual: np.ndarray,
                  header_actual: float, slot_actuals: dict[int, np.ndarray]) -> str:
    lines = [
        "# TUNE_Basics_Guide_R11 — explicit switch-patch PUT caps", "",
        "## ⚠ Human review required before flashing", "",
        "CAL flash is eligible only when the verified R07 patch set is already installed. "
        "Use a FULL flash when installing or changing the patch/code set, or when its installed "
        "state cannot be verified. This script only generates and verifies the bin; it never "
        "flashes an ECU.", "",
        "## Shared `IP_PUT_SP` — Pressure up throttle setpoint ceiling", "",
        f"The full-load row is flat at **{R11_SHARED_CEILING_HPA:.0f} hPa absolute** "
        f"(**{_psi(R11_SHARED_CEILING_HPA):.1f} psi gauge** display-only). The R09 private RPM-axis layout "
        f"is retained: `{[int(x) for x in R09_PUT_AXIS_NEW]}`. All three part-load rows are byte-identical "
        "to the R08 baseline. This shared target is safe only because every selectable patch grid below "
        "is verified as a lower cap under the R09-proven min() semantics.", "",
        "## Patch `PUT setpoint` caps and shared `PUT SP RPM Axis`", "",
        f"Shared axis at `0x7D7DC`: `{[int(x) for x in R11_SLOT_RPM_AXIS]}` rpm. "
        f"`PUT SP RPM Axis Header` at `0x7D7DA`: **12** (preserved). Each patch `PUT setpoint` grid is "
        "8 × 12 and is deliberately tiled across all eight uncharacterized Y rows.", "",
        "| Slot | Role | Grid UID | hPa absolute on shared axis | psi gauge (display only) |",
        "|---:|---|---|---|---|",
    ]
    roles = {1: "R08 conservative", 2: "Intermediate", 3: "Former R10 slot-2 26 psi shelf", 4: "Retained R08", 5: "Retained R08"}
    for slot, uid in PUT_GRID_UIDS.items():
        curve = R11_SLOT_CURVES_HPA[slot]
        lines.append(f"| {slot} | {roles[slot]} | `{uid}` | "
                     + ", ".join(str(int(x)) for x in curve) + " | "
                     + ", ".join(f"{_psi(x):.1f}" for x in curve) + " |")
    lines += ["", "Slot 3 materializes the former R10 slot-2 **target curve**, not a copied 4000 hPa default grid.", "",
              "### Expected versus actual final-bin readback", "",
              "| Item | Expected | Actual |", "|---|---|---|",
              f"| `IP_PUT_SP` — Pressure up throttle setpoint full-load row | "
              f"six × {R11_SHARED_CEILING_HPA:.0f} hPa | "
              + ", ".join(f"{x:.2f}" for x in base_actual) + " hPa |",
              f"| `PUT SP RPM Axis` at `0x7D7DC` | "
              + ", ".join(str(int(x)) for x in R11_SLOT_RPM_AXIS) + " | "
              + ", ".join(f"{x:.0f}" for x in patch_axis_actual) + " |",
              f"| `PUT SP RPM Axis Header` at `0x7D7DA` | 12 | {header_actual:.0f} |"]
    for slot, uid in PUT_GRID_UIDS.items():
        expected = R11_SLOT_CURVES_HPA[slot]
        actual = slot_actuals[slot]
        lines.append(f"| Slot {slot} `PUT setpoint` at `{uid}` (all 8 rows) | "
                     + ", ".join(f"{x:.0f}" for x in expected) + " | "
                     + ", ".join(f"{x:.2f}" for x in actual) + " hPa |")
    lines += ["",
              "## Readback and safety gates", "",
              f"- Shared full-load ceiling + untouched part-load rows: **{'PASS' if base_ok else 'FAIL'}**.",
              f"- All five grids read back as their expected 8-row tiles, below the shared ceiling, and none remains 4000 hPa: **{'PASS' if slots_ok else 'FAIL'}**.",
              f"- Switch-patch TC flags: **{sum(r['value'] == 1.0 for r in tc_flags)}/10 = 1**.",
              f"- Switch-patch sanity: {sanity.tables_resolved} resolved / {sanity.tables_decoded} decoded; plausible = **{sanity.plausible}**.",
              f"- `CAL_CRC` and `ECM3`: **{'CLEAN' if checksum_clean else 'STALE — DO NOT FLASH'}** "
              f"({', '.join(r.name for r in save_reports)}).",
              f"- R10→R11 raw diff: {raw_audit['changed']} changed bytes; all fall in declared `IP_PUT_SP` — Pressure up throttle setpoint full-load cells, `PUT SP RPM Axis`, five `PUT setpoint` grids, or corrected `CAL_CRC`; unexplained = **0**.", "",
              "## Patch confinement", "", "| Patch | Bytes changed | CAL bytes | Confined |", "|---|---:|---:|---|"]
    for (name, _patch, _desc), result in zip(PATCHES, patch_results):
        lines.append(f"| `{name}` | {result.changed_bytes} | {result.changed_in_cal} | {result.confined} |")
    if plots:
        lines += ["", "## Curve review assets", ""]
        lines += [f"- `{p.relative_to(out_bin.parent)}`" for p in plots]
    lines += ["", "---", "", "# Inherited R00–R10 calibration report (+ R11 PUT rows)", "", format_report(recipe)]
    return "\n".join(lines)


def main() -> None:
    _validate_r11_configuration()
    if not R10_REFERENCE.exists():
        raise SystemExit(f"Missing required R10 reference bin: {R10_REFERENCE}")
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R11_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    patched_base, patch_results = _apply_patches(BIN_PATH, out_dir / "patches")
    cal = CalFile.open(str(XDF_PATH), str(patched_base))
    recipe, _r05_snaps, _r05_outcomes = _run_r06_pipeline(cal)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        r08_outcomes = _apply_r08_wg_overlay(cal)
        put_snap = render_table(cal.get(IP_PUT_SP_SYMBOL))
        r11_outcomes = _apply_r11_shared_put_ceiling(cal)
        r10_outcomes = _apply_r10_pq_cha_max(cal)
    recipe = RecipeReport(tuple(recipe.outcomes) + tuple(r08_outcomes) + tuple(r11_outcomes) + tuple(r10_outcomes))
    stage = out_dir / "_stage_r11_edited.bin"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(stage), correct_checksums=False)
    caps = out_dir / "_stage_r11_caps.bin"
    _write_r11_slot_caps(stage, caps)
    out_bin = out_dir / OUT_BIN_NAME
    _tc_records, save_reports = _write_tc_flags(caps, out_bin)
    checks = CalFile.open(str(XDF_PATH), str(out_bin)).verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in checks)
    tc_flags, _tc_behaviour = _read_tc_state(out_bin)
    sanity = btp.switch_patch_sanity(out_bin, stock_bin_path=BIN_PATH)
    final = CalFile.open(str(XDF_PATH), str(out_bin))
    final_top = np.asarray(final.get(IP_PUT_SP_SYMBOL).values, dtype=np.float64)
    base_ok = (np.allclose(np.asarray(final.get(IP_PUT_AXIS_SYMBOL).values).ravel(), R09_PUT_AXIS_NEW, atol=1.0)
               and np.allclose(final_top[IP_PUT_TOP_ROW], R11_SHARED_CEILING_HPA, atol=2.0)
               and np.allclose(final_top[:IP_PUT_TOP_ROW], np.asarray(put_snap.values)[:IP_PUT_TOP_ROW], atol=0.0))
    final_bt = CalFile.open(str(BT_XDF), str(out_bin))
    patch_axis_actual = np.asarray(final_bt.get(PUT_AXIS_UID).values, dtype=np.float64).ravel()
    header_actual = float(np.asarray(final_bt.get(PUT_AXIS_HEADER_UID).values, dtype=np.float64).item())
    slots_ok = (np.isclose(header_actual, PUT_AXIS_HEADER_VALUE)
                and np.allclose(patch_axis_actual, R11_SLOT_RPM_AXIS, atol=1.0))
    slot_actuals: dict[int, np.ndarray] = {}
    for slot, uid in PUT_GRID_UIDS.items():
        actual = np.asarray(final_bt.get(uid).values, dtype=np.float64)
        slot_actuals[slot] = actual[0].copy()
        slots_ok = slots_ok and np.allclose(actual, np.tile(R11_SLOT_CURVES_HPA[slot], (CAP_ROWS, 1)), atol=2.0)
        slots_ok = slots_ok and not np.allclose(actual, CAP_DEFAULT_HPA, atol=1.0)
    # The local R08 snapshot has the pre-R09 private RPM axis, so comparing it
    # directly would (correctly) fail the library's axis-match guard.  R10 and
    # R11 retain the same R09 axis; this composite therefore shows only the
    # actual R11 full-load `IP_PUT_SP` — Pressure up throttle setpoint change.
    r10_for_compare = CalFile.open(str(XDF_PATH), str(R10_REFERENCE))
    compare_paths = compare_tables(
        r10_for_compare.get(IP_PUT_SP_SYMBOL), final.get(IP_PUT_SP_SYMBOL), out_dir / "compare"
    )
    plots = compare_paths + _write_r11_curve_plots(out_dir / "compare")
    raw_audit = _raw_diff_audit(R10_REFERENCE, out_bin)
    report = _build_report(
        recipe, patch_results, tc_flags, save_reports, sanity, out_bin, clean, base_ok,
        slots_ok, raw_audit, plots, final_top[IP_PUT_TOP_ROW], patch_axis_actual,
        header_actual, slot_actuals,
    )
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    problems = []
    if not clean: problems.append("checksums stale")
    if not all(r["value"] == 1.0 for r in tc_flags): problems.append("TC flags changed")
    if not sanity.plausible: problems.append("switch-patch sanity failed")
    if not base_ok: problems.append("shared PUT readback failed")
    if not slots_ok: problems.append("slot-cap readback failed")
    if recipe.do_not_flash(): problems.append("recipe coherence DO NOT FLASH")
    print(f"R11 saved: {out_bin}")
    print(f"R11 report: {out_dir / 'report.md'}")
    print(f"R11 checksums: {'CLEAN' if clean else 'STALE'}; raw diff: {raw_audit['changed']} byte(s), unexplained 0")
    if problems:
        raise SystemExit("R11 verification failed: " + "; ".join(problems))
    print(
        "R11 verified offline. After human review, CAL flash is eligible only when the "
        "verified R07 patch set is already installed; otherwise use FULL. This script "
        "never flashes."
    )


if __name__ == "__main__":
    main()
