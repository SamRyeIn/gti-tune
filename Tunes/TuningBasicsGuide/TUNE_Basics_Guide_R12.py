#!/usr/bin/env python3
"""TuningBasicsGuide R12 — slot-5 valet boost cap (patched bin).

R12 rebuilds the complete R11 calibration from the untouched recovery image and
changes only the patch-added slot-5 `PUT setpoint` grid.  Its cap is a flat,
deliberately-under-10-psi-gauge 1705 hPa absolute on every shared RPM breakpoint.
The patch provides five slots; this repurposes slot 5 rather than changing ASW
code to add a sixth.  The script generates and verifies a bin only; it never
flashes an ECU.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import CalFile, btp, compare_tables, format_report
from simoscal.checksum import StaleChecksumWarning
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import RecipeReport

import TUNE_Basics_Guide_R11 as r11
from TUNE_Basics_Guide_R03 import BIN_PATH, OUT_ROOT, XDF_PATH
from TUNE_Basics_Guide_R07 import _apply_patches, _read_tc_state, _run_r06_pipeline, _write_tc_flags
from TUNE_Basics_Guide_R08 import _apply_r08_wg_overlay
from TUNE_Basics_Guide_R10 import _apply_r10_pq_cha_max


OUT_BIN_NAME = "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R12.bin"
R11_REFERENCE = (
    OUT_ROOT / "R11_20260713-112124" /
    "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R11.bin"
)
VALET_SLOT = 5
# Floor, rather than round, so the encoded ceiling cannot exceed 10 psi gauge.
VALET_CAP_HPA = float(np.floor(10.0 * r11.PSI_PER_HPA + r11.AMBIENT_HPA))
R11_SLOT5_CURVE_HPA = r11.R11_SLOT_CURVES_HPA[VALET_SLOT].copy()
R12_SLOT_CURVES_HPA = {
    slot: curve.copy() for slot, curve in r11.R11_SLOT_CURVES_HPA.items()
}
R12_SLOT_CURVES_HPA[VALET_SLOT] = np.full(r11.CAP_COLS, VALET_CAP_HPA, dtype=np.float64)


def _validate_r12_configuration() -> None:
    """Reject an unsafe valet configuration before opening or editing a bin."""
    curve = R12_SLOT_CURVES_HPA[VALET_SLOT]
    if curve.shape != (r11.CAP_COLS,) or not np.all(np.isfinite(curve)):
        raise ValueError("slot 5 valet cap must have 12 finite values.")
    if not np.all(curve == VALET_CAP_HPA):
        raise ValueError("slot 5 valet cap must be flat across the shared RPM axis.")
    if VALET_CAP_HPA <= r11.AMBIENT_HPA or VALET_CAP_HPA >= r11.R11_SHARED_CEILING_HPA:
        raise ValueError("slot 5 valet cap must be above ambient and below the shared ceiling.")
    if r11._psi(VALET_CAP_HPA) > 10.0:
        raise ValueError("slot 5 valet cap exceeds the requested 10 psi-gauge maximum.")
    for slot, curve in R12_SLOT_CURVES_HPA.items():
        if slot != VALET_SLOT and not np.array_equal(curve, r11.R11_SLOT_CURVES_HPA[slot]):
            raise ValueError(f"slot {slot} changed while configuring the slot-5 valet cap.")


def _raw_diff_audit(r11_bin: Path, r12_bin: Path) -> dict:
    """Prove R12 differs from the approved R11 reference only in slot 5 + CAL_CRC."""
    before, after = r11_bin.read_bytes(), r12_bin.read_bytes()
    if len(before) != len(after):
        raise ValueError("R11/R12 file-size mismatch.")
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    bt = CalFile.open(str(r11.BT_XDF), str(r12_bin))
    allowed = r11._byte_offsets(bt.get(r11.PUT_GRID_UIDS[VALET_SLOT]))
    allowed |= set(range(0x200304, 0x200308))  # corrected CAL_CRC storage
    unexplained = changed - allowed
    if unexplained:
        sample = ", ".join(hex(x) for x in sorted(unexplained)[:12])
        raise ValueError(f"R11→R12 raw diff has {len(unexplained)} unexplained byte(s): {sample}.")
    return {"changed": len(changed), "allowed": len(allowed), "unexplained": 0}


def _write_curve_plots(out_dir: Path) -> list[Path]:
    """Write valet-delta and all-slot effective-target review plots."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    axis = r11.R11_SLOT_RPM_AXIS
    ax.plot(axis, [r11._psi(x) for x in R11_SLOT5_CURVE_HPA], "o-", label="R11 slot 5")
    ax.plot(axis, [r11._psi(x) for x in R12_SLOT_CURVES_HPA[VALET_SLOT]], "o-", label="R12 slot 5 valet (max 10 psi)")
    ax.set(xlabel="Engine speed (rpm)", ylabel="Boost target (psi gauge)",
           title="R12 slot-5 valet cap", ylim=(0, 30))
    ax.set_yticks(np.arange(0, 31, 5)); ax.grid(True, alpha=0.3); ax.legend(); fig.tight_layout()
    path = out_dir / "r12_slot5_valet_target.png"
    fig.savefig(path, dpi=120); plt.close(fig)
    paths = [path]

    # Plot every selectable slot, including coincident curves. Slots 1 and 4
    # intentionally have identical values; their solid/dashed traces keep that
    # fact visible without inventing an offset in the actual target data.
    styles = {
        1: {"color": "#1f77b4", "linestyle": "-", "marker": "o"},
        2: {"color": "#2ca02c", "linestyle": "-", "marker": "s"},
        3: {"color": "#d62728", "linestyle": "-", "marker": "^"},
        4: {"color": "#ff7f0e", "linestyle": "--", "marker": None},
        5: {"color": "#9467bd", "linestyle": "-.", "marker": "D"},
    }
    roles = {
        1: "slot 1 — conservative",
        2: "slot 2 — intermediate",
        3: "slot 3 — aggressive: 24–26 psi ramp",
        4: "slot 4 — conservative (same values as slot 1)",
        5: "slot 5 — valet, max 10 psi",
    }
    fig, ax = plt.subplots(figsize=(10, 6))
    for slot in range(1, 6):
        style = styles[slot]
        ax.plot(axis, [r11._psi(x) for x in R12_SLOT_CURVES_HPA[slot]],
                label=roles[slot], linewidth=2, markersize=5, **style)
    ax.set(xlabel="Engine speed (rpm)", ylabel="Boost target (psi gauge)",
           title="R12 effective boost targets — all five selectable slots", ylim=(0, 30))
    ax.set_yticks(np.arange(0, 31, 5)); ax.grid(True, alpha=0.3); ax.legend(fontsize=8); fig.tight_layout()
    path = out_dir / "r12_all_slot_boost_targets.png"
    fig.savefig(path, dpi=120); plt.close(fig)
    paths.append(path)
    return paths


def _build_report(recipe: RecipeReport, save_reports: list, sanity: btp.SanityResult,
                  tc_flags: list[dict], raw_audit: dict, plots: list[Path],
                  slot_actuals: dict[int, np.ndarray]) -> str:
    lines = [
        "# TUNE_Basics_Guide_R12 — slot-5 valet boost cap", "",
        "## ⚠ Human review required before flashing", "",
        "This matching-patch calibration update is CAL-flash eligible only when the verified R07 patch set is already installed. "
        "Use a FULL flash if patch/code state is unknown or changes. This script never flashes an ECU.", "",
        "## Slot 5 valet target", "",
        f"The patch-added slot-5 `PUT setpoint` grid at `{r11.PUT_GRID_UIDS[VALET_SLOT]}` is an 8 × 12 grid tiled across "
        f"all eight uncharacterized rows. It is flat at **{VALET_CAP_HPA:.0f} hPa absolute** on the shared "
        f"`PUT SP RPM Axis` (`{[int(x) for x in r11.R11_SLOT_RPM_AXIS]}` rpm), which is **{r11._psi(VALET_CAP_HPA):.3f} psi gauge** "
        "and therefore does not exceed the requested 10 psi-gauge maximum. Under the R09-proven min() semantics, it is "
        "the active slot-5 WOT upper cap below R11's parked 30 psi-gauge shared `IP_PUT_SP` — Pressure up throttle setpoint ceiling.", "",
        "Slots 1–4, the shared axis/header, `IP_PUT_SP` — Pressure up throttle setpoint, `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger compressor, and all inherited traction-control flags retain R11 values.", "",
        "## Final-bin readback", "",
        "| Slot | Grid UID | First-row hPa absolute on shared axis |", "|---:|---|---|",
    ]
    for slot, uid in r11.PUT_GRID_UIDS.items():
        lines.append(f"| {slot} | `{uid}` | " + ", ".join(f"{x:.2f}" for x in slot_actuals[slot]) + " |")
    clean = all((not report.can_verify) or (not report.is_stale) for report in save_reports)
    lines += ["", "## Readback and safety gates", "",
              f"- `CAL_CRC` and `ECM3`: **{'CLEAN' if clean else 'STALE — DO NOT FLASH'}**.",
              f"- Switch-patch TC flags: **{sum(r['value'] == 1.0 for r in tc_flags)}/10 = 1**.",
              f"- Switch-patch sanity: {sanity.tables_resolved} resolved / {sanity.tables_decoded} decoded; plausible = **{sanity.plausible}**.",
              f"- R11→R12 raw diff: {raw_audit['changed']} changed bytes, confined to the slot-5 `PUT setpoint` grid and corrected `CAL_CRC`; unexplained = **0**.",
              "- The output remains a starting point: after human review and flash, log slot 5 separately and review `IP_PUT_SP` — Pressure up throttle setpoint tracking, lambda, rail pressure, knock, turbo speed, and P0234 margin.", ""]
    if plots:
        lines += ["## Curve review assets", ""] + [f"- `{path.name}`" for path in plots] + [""]
    lines += ["---", "", "# Inherited R00–R11 calibration report (+ R12 slot-5 valet cap)", "", format_report(recipe)]
    return "\n".join(lines)


def main() -> None:
    _validate_r12_configuration()
    if not R11_REFERENCE.exists():
        raise SystemExit(f"Missing required R11 reference bin: {R11_REFERENCE}")
    # R11's cap writer performs strict as-patched defaults and readback checks.
    # Override only its process-local curve map after our own R12-specific guards.
    r11.R11_SLOT_CURVES_HPA = R12_SLOT_CURVES_HPA
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R12_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    patched_base, _patch_results = _apply_patches(BIN_PATH, out_dir / "patches")
    cal = CalFile.open(str(XDF_PATH), str(patched_base))
    recipe, _r05_snaps, _r05_outcomes = _run_r06_pipeline(cal)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        r08_outcomes = _apply_r08_wg_overlay(cal)
        r11_outcomes = r11._apply_r11_shared_put_ceiling(cal)
        r10_outcomes = _apply_r10_pq_cha_max(cal)
    recipe = RecipeReport(tuple(recipe.outcomes) + tuple(r08_outcomes) + tuple(r11_outcomes) + tuple(r10_outcomes))
    stage = out_dir / "_stage_r12_edited.bin"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(stage), correct_checksums=False)
    caps = out_dir / "_stage_r12_caps.bin"
    r11._write_r11_slot_caps(stage, caps)
    out_bin = out_dir / OUT_BIN_NAME
    _tc_records, save_reports = _write_tc_flags(caps, out_bin)
    checks = CalFile.open(str(XDF_PATH), str(out_bin)).verify_checksums()
    clean = all((not report.can_verify) or (not report.is_stale) for report in checks)
    tc_flags, _tc_behaviour = _read_tc_state(out_bin)
    sanity = btp.switch_patch_sanity(out_bin, stock_bin_path=BIN_PATH)
    final_bt = CalFile.open(str(r11.BT_XDF), str(out_bin))
    slot_actuals: dict[int, np.ndarray] = {}
    slots_ok = True
    for slot, uid in r11.PUT_GRID_UIDS.items():
        actual = np.asarray(final_bt.get(uid).values, dtype=np.float64)
        slot_actuals[slot] = actual[0].copy()
        slots_ok &= np.allclose(actual, np.tile(R12_SLOT_CURVES_HPA[slot], (r11.CAP_ROWS, 1)), atol=2.0)
    before_bt = CalFile.open(str(r11.BT_XDF), str(R11_REFERENCE))
    compare_paths = compare_tables(before_bt.get(r11.PUT_GRID_UIDS[VALET_SLOT]), final_bt.get(r11.PUT_GRID_UIDS[VALET_SLOT]), out_dir / "compare")
    plots = compare_paths + _write_curve_plots(out_dir / "compare")
    raw_audit = _raw_diff_audit(R11_REFERENCE, out_bin)
    report = _build_report(recipe, save_reports, sanity, tc_flags, raw_audit, plots, slot_actuals)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    problems = []
    if not clean: problems.append("checksums stale")
    if not slots_ok: problems.append("slot-cap readback failed")
    if not all(r["value"] == 1.0 for r in tc_flags): problems.append("TC flags changed")
    if not sanity.plausible: problems.append("switch-patch sanity failed")
    if raw_audit["unexplained"]: problems.append("unexplained raw diff")
    if recipe.do_not_flash(): problems.append("recipe coherence DO NOT FLASH")
    print(f"R12 saved: {out_bin}")
    print(f"R12 report: {out_dir / 'report.md'}")
    print(f"R12 checksums: {'CLEAN' if clean else 'STALE'}; raw diff: {raw_audit['changed']} byte(s), unexplained 0")
    if problems:
        raise SystemExit("R12 verification failed: " + "; ".join(problems))
    print("R12 verified offline. After human review, flash only under the existing patched-lineage rule; this script never flashes.")


if __name__ == "__main__":
    main()
