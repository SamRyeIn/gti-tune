#!/usr/bin/env python3
"""Patched bin — TuningBasicsGuide, revision R09 (slot-2 boost increase to 26 psi).

R09 is based on R08 and runs the EXACT R08 pipeline unchanged (the three .btp
patches, the full R06 CAL-edit pipeline, the R05 + R08 wastegate feedforward
overlays, and the switch-patch TC flags on all five slots). It adds TWO new
things that together raise the boost target on **map slot 2 only**:

**1. Base `IP_PUT_SP`  — Boost pressure setpoint: reshape to a 26 psi shelf.**
The full-load (top) row is reshaped from the descending R08 curve into a rounded
26 psi (gauge) plateau between 3400 and 4400 rpm, joining the R08 tail from
5000 rpm up. This is done by RE-BREAKPOINTING the table's own RPM axis
(`ldp_n_ip_put_sp`, addr 0x2fd2) — grep-verified to be referenced by NOTHING
except `IP_PUT_SP`, so the re-breakpoint has zero blast radius. The stock axis
wastes a column on 2000 rpm (redundant: 2000 and 3000 both sit at 24.4 psi), so
that column is spent on the new 3400 breakpoint; below 3000 rpm the ECU clamps to
the first column (24.4 psi), byte-identical low-end behaviour to R08.

  RPM axis : [2000, 3000, 4000, 5000, 5750, 6500] -> [3000, 3400, 4400, 5000, 5750, 6500]
  Top row  : [2699, 2699, 2500, 2350, 2299, 2199] -> [2699, 2809, 2809, 2712, 2519, 2243] hPa abs
  psi gauge: [24.4, 24.4, 21.5, 19.3, 18.6, 17.2] -> [24.4, 26.0, 26.0, 24.6, 21.8, 17.8]
  (ambient conversion: hPa_abs = psi_gauge * 68.95 + 1016)

Only the full-load row + the shared RPM axis change; the three part-load rows are
left as-is (the axis moves under near-flat 591-1062 hPa data — negligible).

**2. Slot 1/3/4/5 PUT-setpoint CAPS held at the R08 curve.**
`IP_PUT_SP` is the shared ceiling for ALL five map slots. The switch patch adds a
per-slot PUT-setpoint CAP table (8x12, hPa) that binds by min() against the base:
all five ship at a uniform 4000 hPa (~43 psi, non-binding), which is why the car
currently follows the base curve. Raising the base alone would raise ALL five
slots. To confine the 26 psi shelf to slot 2, the caps for slots 1, 3, 4, 5 are
filled with the R08 full-load curve (resampled onto the cap's own 12-point RPM
axis) so `min(new_base, R08_cap)` reproduces the R08 target on those slots. The
curve is written to ALL EIGHT load rows of each cap so it binds correctly at full
load regardless of the cap's (uncharacterised, raw 0-7) load-axis mapping, while
staying well above the part-load base (<=1062 hPa) so part-load is untouched.

  Slot 1 = 0x7D41A   CAP -> R08 curve
  Slot 2 = 0x7D4DA   UNTOUCHED (stays 4000 hPa) -> gets the full 26 psi base
  Slot 3 = 0x7D59A   CAP -> R08 curve
  Slot 4 = 0x7D65A   CAP -> R08 curve
  Slot 5 = 0x7D71A   CAP -> R08 curve

**Cap semantics = min() is evidenced, not yet in-car proven.** All five caps sit
at 4000 hPa today while the car tracks the ~2699 hPa base curve — impossible
under override semantics (the car would target 43 psi). The clean confirmation is
an in-car check: a slot-1 pull on R09 should match R08 exactly. FLAG THIS in the
first R09 log review.

**This is a large step: +4 to +5.4 psi across 3400-5000 rpm on slot 2** vs R08.
Watch the fuel system in the R09 logs — R08 already ran LPFP ~84.7% duty and HPFP
~94.3% effective volume at LOWER boost; the midrange may become fuel-limited.
Also re-watch knock at 3000-3500 rpm (R07 had -2.6/-3.0 deg episodes there) now
that the plateau lives right in that band.

This is still **revision 9 — a starting point, not a finished calibration**. The
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
          the Int 1.05 row) to close the sustained top-end PUT overshoot in the
          clean 3rd-gear R07 logs. Identical deltas to both VVL tables.
    R09 — R08 + slot-2 boost increase to a 26 psi (gauge) shelf. Base `IP_PUT_SP`
          — Boost pressure setpoint full-load row reshaped via a re-breakpoint of
          its private RPM axis `ldp_n_ip_put_sp` (breakpoints at 3400/4400 hold
          26 psi, joining the R08 tail at 5000+), and the per-slot PUT-setpoint
          caps for slots 1/3/4/5 (0x7D41A/0x7D59A/0x7D65A/0x7D71A) filled with the
          R08 curve so only slot 2 (0x7D4DA, left non-binding) sees the increase.
          Cap = min() semantics evidenced but pending in-car slot-1 proof.
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

# R09 chains the full R08 pipeline verbatim (patches + R06 CAL edits + R05/R08
# wastegate overlays + TC flags), then adds the base reshape and slot caps.
from TUNE_Basics_Guide_R03 import BIN_PATH, OUT_ROOT, XDF_PATH
from TUNE_Basics_Guide_R05 import (
    _snapshot_r05_wg,
    _write_r05_comparison_pngs,
)
from TUNE_Basics_Guide_R07 import (
    BT_XDF,
    PATCHES,
    _apply_patches,
    _read_tc_state,
    _run_r06_pipeline,
    _write_tc_flags,
)
from TUNE_Basics_Guide_R08 import _apply_r08_wg_overlay

OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R09.bin"

R09_SECTION_PUT = "Boost — R09 slot-2 26 psi shelf (base IP_PUT_SP reshape)"
R09_SECTION_CAP = "Boost — R09 slot 1/3/4/5 PUT caps (hold at R08)"

# Ambient reference for the psi<->hPa conversion (documented in Docs/brainstorms).
AMBIENT_HPA = 1016.0
PSI_PER_HPA = 68.95  # hPa_abs = psi_gauge * PSI_PER_HPA + AMBIENT_HPA

# --- Change 1: base IP_PUT_SP reshape ------------------------------------- #
IP_PUT_SP_SYMBOL = "IP_PUT_SP"
IP_PUT_AXIS_SYMBOL = "ldp_n_ip_put_sp"      # 0x2fd2 — private to IP_PUT_SP
IP_PUT_TOP_ROW = 3                          # full-load row index (4 load rows)

R09_PUT_AXIS_OLD = [2000.0, 3000.0, 4000.0, 5000.0, 5750.0, 6500.0]
R09_PUT_AXIS_NEW = [3000.0, 3400.0, 4400.0, 5000.0, 5750.0, 6500.0]
# Full-load target (hPa abs). col0 kept at the R08 value so <3000 rpm is unchanged.
R09_PUT_TOPROW_OLD = [2699.0, 2699.0, 2500.0, 2350.0, 2299.0, 2199.0]
R09_PUT_TOPROW_NEW = [2699.0, 2809.0, 2809.0, 2712.0, 2519.0, 2243.0]

# --- Change 2: per-slot PUT-setpoint caps --------------------------------- #
# uid -> slot number. Slot 2 (0x7D4DA) is deliberately absent: it stays at the
# non-binding 4000 hPa default so it receives the full raised base.
R09_SLOT_CAP_UIDS = {"0x7d41a": 1, "0x7d59a": 3, "0x7d65a": 4, "0x7d71a": 5}
SLOT2_UID = "0x7d4da"
CAP_DEFAULT_HPA = 4000.0                    # as-patched non-binding value
CAP_ROWS, CAP_COLS = 8, 12
# Cap's own 12-point RPM axis (read from the bin; fixed by the patch).
CAP_RPM_AXIS = [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500]
# R08 full-load curve resampled (clamped-linear) onto CAP_RPM_AXIS — the value the
# caps must hold so slots 1/3/4/5 reproduce R08 under min() against the raised base.
R09_SLOT_CAP_CURVE = [
    float(round(np.interp(r, R09_PUT_AXIS_OLD, R09_PUT_TOPROW_OLD)))
    for r in CAP_RPM_AXIS
]


def _psi(hpa: float) -> float:
    """hPa absolute -> psi gauge (display only)."""
    return (hpa - AMBIENT_HPA) / PSI_PER_HPA


def _apply_r09_put_reshape(cal: CalFile) -> list[TableOutcome]:
    """Re-breakpoint the IP_PUT_SP RPM axis and reshape its full-load row to the
    26 psi shelf. Fails loud if the axis or the full-load row do not match the
    expected post-R08 baseline (guards against the base shifting under us)."""
    # 1. Axis re-breakpoint (private axis — zero blast radius, grep-verified).
    ax = cal.get(IP_PUT_AXIS_SYMBOL)
    ax_shape = np.asarray(ax.values).shape
    ax_old = np.asarray(ax.values, dtype=np.float64).ravel()
    if not np.allclose(ax_old, R09_PUT_AXIS_OLD, atol=1.0):
        raise ValueError(
            f"{IP_PUT_AXIS_SYMBOL}: expected RPM axis {R09_PUT_AXIS_OLD}, found "
            f"{ax_old.tolist()} — refusing to re-breakpoint (base changed?)."
        )
    ax.set(np.asarray(R09_PUT_AXIS_NEW, dtype=np.float64).reshape(ax_shape))

    # 2. Full-load row reshape (parts-load rows untouched).
    view = cal.get(IP_PUT_SP_SYMBOL)
    z = np.array(view.values, dtype=np.float64, copy=True)
    if not np.allclose(z[IP_PUT_TOP_ROW], R09_PUT_TOPROW_OLD, atol=2.0):
        raise ValueError(
            f"{IP_PUT_SP_SYMBOL}: expected full-load row ~{R09_PUT_TOPROW_OLD}, "
            f"found {z[IP_PUT_TOP_ROW].tolist()} — refusing to reshape."
        )
    lower_before = z[:IP_PUT_TOP_ROW].copy()
    z[IP_PUT_TOP_ROW] = R09_PUT_TOPROW_NEW
    view.set(z)

    # Fail loud if the part-load rows moved (they must not).
    z_after = np.asarray(cal.get(IP_PUT_SP_SYMBOL).values, dtype=np.float64)
    if not np.array_equal(z_after[:IP_PUT_TOP_ROW], lower_before):
        raise ValueError(f"{IP_PUT_SP_SYMBOL}: part-load rows changed — refusing.")

    seg = ", ".join(
        f"{int(r)}rpm {_psi(h):.1f}psi"
        for r, h in zip(R09_PUT_AXIS_NEW, R09_PUT_TOPROW_NEW)
    )
    detail = (
        f"{IP_PUT_SP_SYMBOL}  — Boost pressure setpoint: full-load row reshaped to "
        f"a 26 psi (gauge) shelf via a re-breakpoint of its private RPM axis "
        f"{IP_PUT_AXIS_SYMBOL} (0x2fd2). Axis {R09_PUT_AXIS_OLD} -> "
        f"{R09_PUT_AXIS_NEW} (redundant 2000-rpm column spent on the 3400 "
        f"breakpoint; <3000 rpm clamps to 24.4 psi = R08). Full-load target: "
        f"{seg}. Part-load rows unchanged. Zero blast radius — the RPM axis is "
        f"referenced only by IP_PUT_SP."
    )
    return [TableOutcome(IP_PUT_SP_SYMBOL, R09_SECTION_PUT, OUTCOME_APPLIED, detail=detail)]


def _write_r09_slot_caps(bin_in: Path, bin_out: Path) -> list[dict]:
    """Fill slots 1/3/4/5 PUT-setpoint caps with the R08 curve; leave slot 2.

    Opens `bin_in` with the BinToolz switch-patch XDF, confirms each capped slot
    is at the as-patched uniform 4000 hPa (fail loud otherwise), writes the R08
    curve to all eight load rows, verifies slot 2 is left non-binding, and saves
    `bin_out` WITHOUT correcting checksums (the final TC-flag save does that once).
    Returns per-slot old->new records for the report.
    """
    cal = CalFile.open(str(BT_XDF), str(bin_in))

    # Confirm the cap RPM axis matches what R09_SLOT_CAP_CURVE was resampled onto.
    cap_axis = np.asarray(cal.get(SLOT2_UID).axis_values("x"), dtype=np.float64).ravel()
    if not np.allclose(cap_axis, CAP_RPM_AXIS, atol=1.0):
        raise SystemExit(
            f"Slot cap RPM axis {cap_axis.tolist()} != expected {CAP_RPM_AXIS} — "
            "refusing to write caps (the resampled curve would be misaligned)."
        )

    curve = np.asarray(R09_SLOT_CAP_CURVE, dtype=np.float64)
    new_z = np.tile(curve, (CAP_ROWS, 1))
    records: list[dict] = []
    for uid, slot in R09_SLOT_CAP_UIDS.items():
        view = cal.get(uid)
        old = np.asarray(view.values, dtype=np.float64)
        if old.shape != (CAP_ROWS, CAP_COLS):
            raise SystemExit(f"slot {slot} cap {uid}: shape {old.shape} != (8, 12).")
        if not np.allclose(old, CAP_DEFAULT_HPA, atol=1.0):
            raise SystemExit(
                f"slot {slot} cap {uid}: expected uniform {CAP_DEFAULT_HPA} hPa "
                f"(as-patched), found min {old.min():.1f} max {old.max():.1f} — "
                "refusing to overwrite a non-default cap."
            )
        view.set(new_z.copy())
        records.append({"slot": slot, "uid": uid, "old": CAP_DEFAULT_HPA})

    # Slot 2 must remain non-binding.
    slot2 = np.asarray(cal.get(SLOT2_UID).values, dtype=np.float64)
    if not np.allclose(slot2, CAP_DEFAULT_HPA, atol=1.0):
        raise SystemExit(
            f"slot 2 cap {SLOT2_UID} is not at the non-binding {CAP_DEFAULT_HPA} "
            f"hPa (min {slot2.min():.1f}) — it would clamp the 26 psi target."
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(bin_out), correct_checksums=False)
    return records


def _write_r09_boost_png(cal: CalFile, cap_records: list[dict], png_dir: Path) -> Path | None:
    """Best-effort boost-curve comparison PNG (R08 base vs R09 slot 2 vs slot caps)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    png_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(R09_PUT_AXIS_OLD, [_psi(h) for h in R09_PUT_TOPROW_OLD],
            "o-", color="#1f77b4", label="R08 base (slots 1/3/4/5 hold here)")
    ax.plot(R09_PUT_AXIS_NEW, [_psi(h) for h in R09_PUT_TOPROW_NEW],
            "o-", color="#2ca02c", label="R09 slot 2 (26 psi shelf)")
    ax.plot(CAP_RPM_AXIS, [_psi(h) for h in R09_SLOT_CAP_CURVE],
            "x--", color="#7f7f7f", alpha=0.7, label="Slot 1/3/4/5 cap")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Boost target (psi gauge)", fontweight="bold")
    ax.set_title("R09 boost target — base/caps (R08) vs slot 2 (26 psi shelf)")
    ax.grid(True, which="both", alpha=0.3)
    ax.minorticks_on()
    ax.legend()
    out = png_dir / "r09_boost_curves.png"
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)
    return out


def _build_report_r09(
    recipe: RecipeReport,
    patch_results: list[btp.ChangeResult],
    tc_flags: list[dict],
    cap_records: list[dict],
    checksum_clean: bool,
    save_reports: list,
    sanity: btp.SanityResult,
    out_bin: Path,
    boost_png: Path | None,
) -> str:
    L: list[str] = []
    L.append("# TUNE_Basics_Guide_R09 — slot-2 boost increase to 26 psi (patched bin)")
    L.append("")
    L.append("## ⚠ FULL FLASH REQUIRED — do NOT flash CAL-only")
    L.append("")
    L.append("R09 inherits R07's switch-patched ASW, so this bin **must be flashed "
             "FULL** (not CAL-only). **This script never flashes** — review, then "
             "flash externally with the stock recovery image on hand and the "
             "battery on a charger.")
    L.append("")
    L.append("## ⚠ In-car validation required — cap semantics")
    L.append("")
    L.append("The 26 psi shelf is confined to slot 2 by holding the slot 1/3/4/5 "
             "PUT caps at the R08 curve, which assumes **cap = min() against the "
             "base**. This is evidenced (all caps ship at 4000 hPa while the car "
             "tracks the ~2699 hPa base — impossible under override semantics) but "
             "not yet proven in-car. **First R09 drive: log a slot-1 pull and "
             "confirm it matches R08 exactly.** If slot 1 shows the 26 psi shelf, "
             "the cap direction is wrong — do not keep driving slot 2.")
    L.append("")
    L.append("## Change 1 — base `IP_PUT_SP` full-load reshape (26 psi shelf)")
    L.append("")
    L.append("Re-breakpointed the table's own RPM axis `ldp_n_ip_put_sp` (0x2fd2, "
             "referenced by nothing else — zero blast radius) and reshaped the "
             "full-load row. Part-load rows untouched.")
    L.append("")
    L.append("| rpm (new) | rpm (old) | R08 psi | R09 psi | R08 hPa | R09 hPa |")
    L.append("|-----------|-----------|---------|---------|---------|---------|")
    for rn, ro, ho, hn in zip(R09_PUT_AXIS_NEW, R09_PUT_AXIS_OLD,
                              R09_PUT_TOPROW_OLD, R09_PUT_TOPROW_NEW):
        L.append(f"| {int(rn):>9} | {int(ro):>9} | {_psi(ho):>7.1f} | "
                 f"{_psi(hn):>7.1f} | {int(ho):>7} | {int(hn):>7} |")
    L.append("")
    L.append("Below 3000 rpm the ECU clamps to the first column (24.4 psi) — "
             "byte-identical low-end behaviour to R08.")
    L.append("")
    L.append("## Change 2 — slot 1/3/4/5 PUT caps held at R08")
    L.append("")
    L.append("Filled each cap's eight load rows with the R08 full-load curve "
             "resampled onto the cap's 12-point RPM axis. Slot 2 left at the "
             "non-binding 4000 hPa default.")
    L.append("")
    L.append("| Slot | uid | Action |")
    L.append("|------|-----|--------|")
    for rec in cap_records:
        L.append(f"| {rec['slot']} | `{rec['uid']}` | cap -> R08 curve (was "
                 f"{CAP_DEFAULT_HPA:.0f} hPa) |")
    L.append(f"| 2 | `{SLOT2_UID}` | **untouched** (4000 hPa non-binding) -> full "
             "26 psi base |")
    L.append("")
    L.append("Cap curve (hPa abs) on CAP_RPM_AXIS: "
             + ", ".join(f"{int(r)}:{int(h)}" for r, h in
                         zip(CAP_RPM_AXIS, R09_SLOT_CAP_CURVE)) + ".")
    L.append("")
    if boost_png is not None:
        L.append(f"Boost-curve comparison: `{boost_png.relative_to(out_bin.parent)}`.")
        L.append("")
    L.append("## Watch items for the R09 logs")
    L.append("")
    L.append("- **Fuel system** — R08 ran LPFP ~84.7% duty / HPFP ~94.3% effective "
             "volume at lower boost; the +4 to +5.4 psi midrange may become "
             "fuel-limited. Watch rail pressure hold and LPFP duty on slot 2.")
    L.append("- **Knock at 3000-3500 rpm** — the plateau now sits right where R07 "
             "logged -2.6/-3.0 deg retard episodes; timing is at the edge, not "
             "conservative.")
    L.append("- **Boost tracking / overshoot** on the new plateau shape (spool "
             "bite through 3320-3450 was +13.6-15.8 kPa on R08).")
    L.append("")
    L.append("## Inherited R08 state (unchanged)")
    L.append("")
    L.append("| Patch                    | Bytes changed | in CAL | Confined |")
    L.append("|--------------------------|---------------|--------|----------|")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        L.append(f"| `{name}` | {res.changed_bytes:>13} | {res.changed_in_cal:>6} | "
                 f"{'YES':^8} |")
    L.append("")
    n_on = sum(1 for r in tc_flags if r["value"] == 1.0)
    L.append(f"- Switch-patch TC flags: **{n_on}/10 read back = 1** (all five slots).")
    L.append(f"- switch-patch XDF sanity: {sanity.tables_resolved} tables resolved, "
             f"{sanity.tables_decoded} decoded, {len(sanity.decode_errors)} errors, "
             f"plausible = {'YES' if sanity.plausible else 'NO'}.")
    L.append(f"- Wastegate feedforward: R05 + R08 overlays inherited unchanged in "
             "`IP_FAC_BPA_SP[0]` / `[1]`  — Wastegate Position Feedforward VVL 0/1.")
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
    L.append("# Inherited R00-R08 calibration report (+ R09 boost rows)")
    L.append("")
    L.append(format_report(recipe))
    return "\n".join(L)


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R09_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Apply the three .btp patches to the stock bin (identical to R07/R08).
    patched_base, patch_results = _apply_patches(BIN_PATH, out_dir / "patches")

    # 2. Full R08 CAL pipeline on the patched base (R06 recipe + R05/R08 wastegate
    #    overlays), then the R09 base-reshape.
    cal = CalFile.open(str(XDF_PATH), str(patched_base))
    recipe, _r05_snaps, _r05_outcomes = _run_r06_pipeline(cal)
    wg_snaps = _snapshot_r05_wg(cal)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        r08_outcomes = _apply_r08_wg_overlay(cal)
        r09_outcomes = _apply_r09_put_reshape(cal)
    recipe = RecipeReport(tuple(recipe.outcomes) + tuple(r08_outcomes) + tuple(r09_outcomes))

    # 3. Stage save (SC8S50 XDF, no checksums), then slot caps + TC flags on the
    #    BinToolz XDF, with checksums corrected once at the final TC-flag save.
    stage_bin = out_dir / "_stage_r09_edited.bin"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(stage_bin), correct_checksums=False)
    caps_bin = out_dir / "_stage_r09_caps.bin"
    cap_records = _write_r09_slot_caps(stage_bin, caps_bin)
    out_bin = out_dir / OUT_BIN_NAME
    _tc_records, save_reports = _write_tc_flags(caps_bin, out_bin)

    # 4. Verify: checksums CLEAN, TC flags all 1, sanity plausible, and read back
    #    the base reshape + slot caps from the FINAL bin.
    verify_reports = CalFile.open(str(XDF_PATH), str(out_bin)).verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)
    tc_flags, _tc_behaviour = _read_tc_state(out_bin)
    all_on = all(r["value"] == 1.0 for r in tc_flags)
    sanity = btp.switch_patch_sanity(out_bin, stock_bin_path=BIN_PATH)

    fin = CalFile.open(str(XDF_PATH), str(out_bin))
    fin_axis = np.asarray(fin.get(IP_PUT_AXIS_SYMBOL).values, dtype=np.float64).ravel()
    fin_top = np.asarray(fin.get(IP_PUT_SP_SYMBOL).values, dtype=np.float64)[IP_PUT_TOP_ROW]
    base_ok = (np.allclose(fin_axis, R09_PUT_AXIS_NEW, atol=1.0)
               and np.allclose(fin_top, R09_PUT_TOPROW_NEW, atol=2.0))
    finbt = CalFile.open(str(BT_XDF), str(out_bin))
    caps_ok = all(
        np.allclose(np.asarray(finbt.get(uid).values, dtype=np.float64),
                    np.tile(R09_SLOT_CAP_CURVE, (CAP_ROWS, 1)), atol=2.0)
        for uid in R09_SLOT_CAP_UIDS
    )
    slot2_ok = np.allclose(
        np.asarray(finbt.get(SLOT2_UID).values, dtype=np.float64), CAP_DEFAULT_HPA, atol=1.0
    )

    # 5. Comparison PNGs — inherited wastegate composites + the R09 boost curve.
    png_count, axis_changed = _write_r05_comparison_pngs(
        cal, wg_snaps, r08_outcomes, out_dir / "compare"
    )
    boost_png = _write_r09_boost_png(fin, cap_records, out_dir / "compare")

    # 6. Review report.
    report_md = _build_report_r09(
        recipe, patch_results, tc_flags, cap_records, clean, save_reports, sanity,
        out_bin, boost_png,
    )
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")

    # --- console summary --- #
    print("R09 — slot-2 boost increase to 26 psi shelf (patched bin)")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        print(f"  patch {name:24s}: {res.changed_bytes:>5} bytes changed "
              f"({res.changed_in_cal} CAL), confined={res.confined}")
    print(f"  base reshape   : IP_PUT_SP axis -> {[int(x) for x in R09_PUT_AXIS_NEW]}, "
          f"full-load psi -> {[round(_psi(h), 1) for h in R09_PUT_TOPROW_NEW]}  "
          f"(readback {'OK' if base_ok else 'MISMATCH'})")
    print(f"  slot caps      : slots {sorted(R09_SLOT_CAP_UIDS.values())} -> R08 curve, "
          f"slot 2 untouched  (readback {'OK' if caps_ok and slot2_ok else 'MISMATCH'})")
    print(f"  TC flags       : {sum(1 for r in tc_flags if r['value'] == 1.0)}/10 read back = 1")
    print(f"  saved bin      : {out_bin}")
    print(f"  checksums      : {'CLEAN' if clean else 'STALE — NOT flash-ready'}"
          f" ({', '.join(r.name for r in save_reports)})")
    print(f"  switch sanity  : resolved {sanity.tables_resolved}, decoded "
          f"{sanity.tables_decoded}, plausible={sanity.plausible}")
    print(f"  report         : {out_dir / 'report.md'}")
    print(f"  comparison PNGs: {png_count} WG under {out_dir / 'compare'}"
          f"{' + boost curve' if boost_png else ''}")

    problems = []
    if not clean:
        problems.append("checksums STALE")
    if not all_on:
        problems.append("not all TC flags decoded to 1")
    if not sanity.plausible:
        problems.append("switch-patch sanity not plausible")
    if not base_ok:
        problems.append("base reshape readback mismatch")
    if not (caps_ok and slot2_ok):
        problems.append("slot cap readback mismatch")
    if recipe.do_not_flash():
        problems.append("recipe coherence: DO NOT FLASH")
    if problems:
        print(f"\n  ⛔ ISSUES: {'; '.join(problems)} — investigate before flashing.")
        raise SystemExit(f"R09 verification failed: {'; '.join(problems)}")
    else:
        print("\n  ✅ Patches confined, checksums CLEAN, 10/10 TC flags = 1, base "
              "reshape + slot caps verified, switch-patch sanity plausible.")
        print("  ⚠ FULL FLASH REQUIRED (not CAL-only). Slot-1 pull must match R08 "
              "in-car (cap-semantics proof). Review report + PNGs, then flash "
              "externally. This is revision 9; iterate.")


if __name__ == "__main__":
    main()
