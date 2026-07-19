#!/usr/bin/env python3
"""Patched bin — TuningBasicsGuide, revision R10 (raise the compressor pressure-quotient cap).

R10 is based on R09 and runs the EXACT R09 pipeline unchanged (the three .btp
patches, the full R06 CAL-edit pipeline, the R05 + R08 wastegate feedforward
overlays, the switch-patch TC flags on all five slots, the R09 base `IP_PUT_SP`
26 psi shelf reshape, and the R09 slot 1/3/4/5 PUT-setpoint caps). It adds
EXACTLY ONE new calibration change:

**`IP_PQ_CHA_MAX`  — Maximum allowed pressure quotient at turbo charger
compressor (8x8, unitless): reshape from flat 2.80 to the guide's default RPM
shape — 1.70 at the 1000 RPM breakpoint, flat 3.1 from ~2000 up to 7000 RPM.**

The stock table ships flat 9.30; the ecu-tuning-basics SOP recipe flattens it to
2.80 as part of the "Option 2" boost method (`KIND_LITERAL_BROADCAST`), so the
R09 baseline this revision builds on reads a uniform 2.80 across all 64 cells.
The table's X axis is RPM `[1000, 2000, 3000, 4000, 5000, 6000, 6500, 7000]`
(shared identically across all 8 Y rows), so R10 writes column 0 (1000 RPM) to
1.70 and columns 1-7 (2000-7000 RPM) to 3.1, uniform down all 8 rows — the
ecu-tuning-basics SOP's documented default shape, raised from its 2.80 default
plateau to 3.1. XDF z-data at 0x1ab9a (uint16, scale 1/4096): 3.1 stores as raw
12698 = 3.100098 decoded and 1.70 stores as raw 6963 = 1.700195 decoded, both
within the 1/4096 ≈ 2.44e-4 storage resolution.

### Why — R09 slot-2 logs (Logs/BasicsGuide_R09/log_review.md)

The R09 slot-2 pulls proved the 26 psi full-load shelf is delivered ~1.0-1.4 psi
SHORT (actual ~24.6-25.3 psi against the 26.0 target) from 3300-5800 rpm, and
the shortfall is COMMANDED, not a plant/wastegate limit:

- `Torque Lim ()` code 128 — "Temporary torque limitation because of operation
  at maximum charge pressure ratio (Max Pressure ratio table)" (guide p. 29) —
  appears ONLY on slot-2 files and ONLY at 3500-4800 rpm (the shelf zone; 233
  samples across the five slot-2 pull files). Its table is `IP_PQ_CHA_MAX`.
- Delivered slot-2 PUT plateaus at exactly 2.80 × the measured pre-compressor
  pressure — the cap, not the wastegate, sets the achievable boost. The
  persistent positive wastegate integral (+15 %, gate held 67-72 % closed) is
  the closed loop chasing the un-trimmed logged `PUT SP` while the limiter caps
  the achievable setpoint downstream; wastegate feedforward cannot recover this
  gap while PQ 2.80 binds.

Required PQ to clear the shelf, from 219 settled capped log rows: 2.887-2.958 on
the logged day (~101.6 kPa ambient) and ~3.02 on a low-pressure (99 kPa) day. So
3.0 is INSUFFICIENT margin; 3.1 clears the worst realistic sea-level case with
~0.08 headroom. Sam has explicitly acknowledged the compressor-protection risk
(this cap is genuine compressor protection near the IS20 map edge) and requested
3.1.

### Watch items for the R10 logs

- **Turbo speed** — was 208 of 220 krpm (~5 % margin) on R09 shelf pulls; more
  delivered boost from clearing the cap will push it higher. This is the primary
  safety watch.
- **HPFP effective volume** — was 97-98 % (essentially at ceiling) on R09 shelf
  pulls; more airmass has almost no high-pressure-pump headroom. Watch rail
  pressure hold and lambda.
- Re-confirm `Torque Lim ()` code 128 is now SILENT in the shelf zone (the direct
  proof the cap was the constraint) and that the shelf now delivers ~26 psi.
- Top-end down-ramp / P0234 margin (was 775 hPa on R09), knock at 3000-3500 rpm
  (cyl 1 recurring at -3.0°): unchanged by R10, keep watching.

This is still **revision 10 — a starting point, not a finished calibration**. The
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
    R10 — R09 + reshape `IP_PQ_CHA_MAX`  — Maximum allowed pressure quotient at
          turbo charger compressor (8x8): from flat 2.80 to the SOP default RPM
          shape, 1.70 at 1000 RPM / flat 3.1 from ~2000-7000 RPM (raised from the
          shape's 2.80 default plateau). R09 slot-2 logs proved the 26 psi shelf
          is trimmed ~1.0-1.4 psi short by this cap (torque-limit code 128 =
          operation at max charge-pressure ratio; delivered PUT plateaued at
          exactly 2.80 x pre-compressor pressure). Required PQ 2.89-3.02 across
          the logged/low-pressure days; 3.1 clears the worst sea-level case with
          ~0.08 margin. Sam acknowledged the compressor-protection risk and
          requested 3.1. Everything else carries over from R09 unchanged.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import CalFile, btp, compare_tables, format_report, render_table
from simoscal.checksum import StaleChecksumWarning
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import OUTCOME_APPLIED, RecipeReport, TableOutcome

# R10 chains the full R09 pipeline verbatim (patches + R06 CAL edits + R05/R08
# wastegate overlays + TC flags + R09 base reshape + R09 slot caps), then adds
# the single IP_PQ_CHA_MAX raise.
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
    CAP_DEFAULT_HPA,
    CAP_ROWS,
    IP_PUT_AXIS_SYMBOL,
    IP_PUT_SP_SYMBOL,
    IP_PUT_TOP_ROW,
    R09_PUT_AXIS_NEW,
    R09_PUT_TOPROW_NEW,
    R09_SLOT_CAP_CURVE,
    R09_SLOT_CAP_UIDS,
    SLOT2_UID,
    _apply_r09_put_reshape,
    _psi,
    _write_r09_slot_caps,
)

# R10+ output bins carry the CBRICK + HSL + switch-patch-29.33 prefix (see the
# `bin-naming-patch-prefix` memory) so the flashed name is self-describing.
OUT_BIN_NAME = "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R10.bin"

R10_SECTION_PQ = ("Boost — R10 compressor pressure-quotient cap (IP_PQ_CHA_MAX "
                  "1.70 @ 1000 RPM / flat 3.1 @ 2000-7000 RPM)")

# --- R10 change: reshape the compressor pressure-quotient cap -------------- #
IP_PQ_SYMBOL = "IP_PQ_CHA_MAX"     # 8x8, z-data 0x1ab9a, uint16 scale 1/4096
R10_PQ_OLD = 2.80                  # R09 baseline (recipe-flattened; stock is 9.30)
R10_PQ_RPM_AXIS = (1000, 2000, 3000, 4000, 5000, 6000, 6500, 7000)  # X axis, all rows
R10_PQ_LOW_RPM_VAL = 1.70          # column 0 (1000 RPM) — SOP default shape
R10_PQ_NEW = 3.1                   # columns 1-7 (2000-7000 RPM)
PQ_ROWS, PQ_COLS = 8, 8


def _apply_r10_pq_cha_max(cal: CalFile) -> list[TableOutcome]:
    """Reshape `IP_PQ_CHA_MAX`  — Maximum allowed pressure quotient at turbo
    charger compressor (8x8) from the R09 flat-2.80 baseline to the
    ecu-tuning-basics SOP's default RPM shape: 1.70 at the 1000 RPM breakpoint
    (column 0), flat 3.1 from ~2000 up to 7000 RPM (columns 1-7), uniform down
    all 8 Y rows.

    Fails loud if the table is not the expected uniform R09 baseline (flat 2.80)
    or if the X axis isn't the expected RPM breakpoints, guarding against the
    recipe/base shifting under us. No silent clamp: the write is verified by
    reading the table back in-memory before the outcome is emitted.
    """
    view = cal.get(IP_PQ_SYMBOL)
    z = np.asarray(view.values, dtype=np.float64)
    if z.shape != (PQ_ROWS, PQ_COLS):
        raise ValueError(
            f"{IP_PQ_SYMBOL}: shape {z.shape} != ({PQ_ROWS}, {PQ_COLS}) — refusing."
        )
    if not np.allclose(z, R10_PQ_OLD, atol=1e-2):
        raise ValueError(
            f"{IP_PQ_SYMBOL}: expected uniform R09 baseline {R10_PQ_OLD}, found "
            f"min {z.min():.4f} max {z.max():.4f} — refusing to reshape (base changed?)."
        )
    x_axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
    if not np.allclose(x_axis, R10_PQ_RPM_AXIS, atol=1.0):
        raise ValueError(
            f"{IP_PQ_SYMBOL}: expected RPM X axis {R10_PQ_RPM_AXIS}, found "
            f"{x_axis.tolist()} — refusing (axis changed?)."
        )

    z_new = np.full((PQ_ROWS, PQ_COLS), R10_PQ_NEW, dtype=np.float64)
    z_new[:, 0] = R10_PQ_LOW_RPM_VAL
    view.set(z_new)

    z_after = np.asarray(cal.get(IP_PQ_SYMBOL).values, dtype=np.float64)
    expect_after = z_new
    if not np.allclose(z_after, expect_after, atol=5e-4):
        raise ValueError(
            f"{IP_PQ_SYMBOL}: readback does not match target shape — refusing "
            f"(write did not take)."
        )
    detail = (
        f"{IP_PQ_SYMBOL}  — Maximum allowed pressure quotient at turbo charger "
        f"compressor (8x8): reshaped from flat {R10_PQ_OLD} to {R10_PQ_LOW_RPM_VAL} "
        f"at the 1000 RPM breakpoint (column 0, all 8 rows) and flat {R10_PQ_NEW} "
        f"from ~2000 up to 7000 RPM (columns 1-7, all 8 rows) — the ecu-tuning-basics "
        f"SOP's default RPM shape, raised from its 2.80 default plateau to 3.1 "
        f"(z-data 0x1ab9a, uint16 scale 1/4096; 3.1 stores raw 12698 = 3.100098 "
        f"decoded, 1.70 stores raw 6963 = 1.700195 decoded). R09 slot-2 logs showed "
        f"the 26 psi shelf trimmed ~1.0-1.4 psi short by this cap (torque-limit code "
        f"128 = max charge-pressure-ratio; delivered PUT plateaued at exactly 2.80 x "
        f"measured pre-compressor pressure). Required PQ 2.89-3.02 across "
        f"logged/low-pressure days; 3.1 clears the worst sea-level case with ~0.08 "
        f"margin. Compressor protection near the IS20 map edge — Sam acknowledged the "
        f"risk and requested 3.1. Watch turbo speed (208/220 krpm on R09) and HPFP."
    )
    return [TableOutcome(IP_PQ_SYMBOL, R10_SECTION_PQ, OUTCOME_APPLIED, detail=detail)]


def _build_report_r10(
    recipe: RecipeReport,
    patch_results: list[btp.ChangeResult],
    tc_flags: list[dict],
    cap_records: list[dict],
    checksum_clean: bool,
    save_reports: list,
    sanity: btp.SanityResult,
    out_bin: Path,
    pq_readback: np.ndarray,
    pq_paths: list[Path],
) -> str:
    L: list[str] = []
    L.append("# TUNE_Basics_Guide_R10 — raise compressor pressure-quotient cap (patched bin)")
    L.append("")
    L.append("## ⚠ FULL FLASH REQUIRED — do NOT flash CAL-only")
    L.append("")
    L.append("R10 inherits R07's switch-patched ASW, so this bin **must be flashed "
             "FULL** (not CAL-only). **This script never flashes** — review, then "
             "flash externally with the stock recovery image on hand and the "
             "battery on a charger.")
    L.append("")
    L.append("## R10 change — `IP_PQ_CHA_MAX` reshape (the one calibration change)")
    L.append("")
    L.append("`IP_PQ_CHA_MAX`  — Maximum allowed pressure quotient at turbo charger "
             "compressor (8x8, unitless): reshaped from flat **2.80** (R09 baseline; "
             "stock is 9.30, flattened to 2.80 by the SOP Option-2 recipe) to the "
             "ecu-tuning-basics SOP's default RPM shape — **1.70 at the 1000 RPM** "
             "breakpoint (column 0, all 8 rows), **flat 3.1 from ~2000 up to 7000 "
             "RPM** (columns 1-7, all 8 rows). Everything else carries over from R09 "
             "unchanged.")
    L.append("")
    L.append("| Table | Shape | RPM axis | R09 (all cells) | R10 | Readback |")
    L.append("|-------|-------|----------|------------------|-----|----------|")
    L.append(f"| `IP_PQ_CHA_MAX` | {PQ_ROWS}x{PQ_COLS} | "
             f"{list(R10_PQ_RPM_AXIS)} | {R10_PQ_OLD:.2f} | "
             f"{R10_PQ_LOW_RPM_VAL:.2f} @ 1000 rpm, {R10_PQ_NEW:.2f} @ 2000-7000 rpm | "
             f"col0 {pq_readback[:, 0].min():.6f}-{pq_readback[:, 0].max():.6f}, "
             f"col1-7 {pq_readback[:, 1:].min():.6f}-{pq_readback[:, 1:].max():.6f} |")
    L.append("")
    if pq_paths:
        names = ", ".join(f"`{p.relative_to(out_bin.parent)}`" for p in pq_paths)
        L.append(f"Before/after comparison: {names}.")
        L.append("")
    L.append("### Why (Logs/BasicsGuide_R09/log_review.md)")
    L.append("")
    L.append("R09 slot-2 pulls delivered the 26 psi shelf ~1.0-1.4 psi short "
             "(actual ~24.6-25.3 psi vs 26.0 target, 3300-5800 rpm). The shortfall "
             "is **commanded, not plant**: `Torque Lim ()` code 128 (operation at "
             "maximum charge-pressure ratio — the `IP_PQ_CHA_MAX` table) fired only "
             "on slot-2 files in the shelf zone, and delivered PUT plateaued at "
             "exactly **2.80 x** the measured pre-compressor pressure. From 219 "
             "settled capped log rows the required PQ is 2.887-2.958 on the logged "
             "day (~101.6 kPa ambient) and ~3.02 on a low-pressure (99 kPa) day — so "
             "3.0 is insufficient margin; **3.1 clears the worst realistic "
             "sea-level case with ~0.08 headroom**. This cap is genuine compressor "
             "protection near the IS20 map edge; Sam acknowledged the risk and "
             "requested 3.1.")
    L.append("")
    L.append("### Watch items for the R10 logs")
    L.append("")
    L.append("- **Turbo speed** — 208 of 220 krpm (~5 % margin) on R09 shelf pulls; "
             "clearing the cap delivers more boost and will push it higher. Primary "
             "safety watch.")
    L.append("- **HPFP effective volume** — 97-98 % (at ceiling) on R09 shelf pulls; "
             "almost no high-pressure-pump headroom for more airmass. Watch rail "
             "pressure hold and lambda.")
    L.append("- **`Torque Lim ()` code 128** — should now be SILENT in the shelf "
             "zone (direct proof the cap was the constraint); confirm the shelf now "
             "delivers ~26 psi.")
    L.append("- Top-end down-ramp / P0234 margin (775 hPa on R09) and knock at "
             "3000-3500 rpm (cyl 1 at -3.0°): unchanged by R10, keep watching.")
    L.append("")
    L.append("## Inherited R09 state (unchanged)")
    L.append("")
    L.append("### Base `IP_PUT_SP` 26 psi shelf + slot caps (from R09)")
    L.append("")
    L.append("| rpm (new) | rpm (old) | R08 psi | R09 psi | R08 hPa | R09 hPa |")
    L.append("|-----------|-----------|---------|---------|---------|---------|")
    from TUNE_Basics_Guide_R09 import R09_PUT_AXIS_OLD, R09_PUT_TOPROW_OLD
    for rn, ro, ho, hn in zip(R09_PUT_AXIS_NEW, R09_PUT_AXIS_OLD,
                              R09_PUT_TOPROW_OLD, R09_PUT_TOPROW_NEW):
        L.append(f"| {int(rn):>9} | {int(ro):>9} | {_psi(ho):>7.1f} | "
                 f"{_psi(hn):>7.1f} | {int(ho):>7} | {int(hn):>7} |")
    L.append("")
    L.append("| Slot | uid | Action |")
    L.append("|------|-----|--------|")
    for rec in cap_records:
        L.append(f"| {rec['slot']} | `{rec['uid']}` | cap -> R08 curve (was "
                 f"{CAP_DEFAULT_HPA:.0f} hPa) |")
    L.append(f"| 2 | `{SLOT2_UID}` | **untouched** (4000 hPa non-binding) -> full "
             "26 psi base |")
    L.append("")
    L.append("(No comparison PNG regenerated for `IP_PUT_SP` / the slot caps — R10 "
             "does not change them; see `Logs/BasicsGuide_R09/log_review.md` and the "
             "R09 report for their before/after.)")
    L.append("")
    L.append("### Patches / TC flags / wastegate (from R07/R08)")
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
    L.append("- Wastegate feedforward: R05 + R08 overlays inherited unchanged in "
             "`IP_FAC_BPA_SP[0]` / `[1]`  — Wastegate Position Feedforward VVL 0/1 "
             "(not re-plotted here since R10 does not touch them; see the R08 report "
             "for their before/after).")
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
    L.append("# Inherited R00-R09 calibration report (+ R10 PQ cap row)")
    L.append("")
    L.append(format_report(recipe))
    return "\n".join(L)


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R10_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Apply the three .btp patches to the stock bin (identical to R07/R08/R09).
    patched_base, patch_results = _apply_patches(BIN_PATH, out_dir / "patches")

    # 2. Full R09 CAL pipeline on the patched base (R06 recipe + R05/R08 wastegate
    #    overlays + R09 base reshape), then the single R10 IP_PQ_CHA_MAX raise.
    cal = CalFile.open(str(XDF_PATH), str(patched_base))
    recipe, _r05_snaps, _r05_outcomes = _run_r06_pipeline(cal)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        r08_outcomes = _apply_r08_wg_overlay(cal)
        r09_outcomes = _apply_r09_put_reshape(cal)
        pq_snap = render_table(cal.get(IP_PQ_SYMBOL))  # R09 baseline (flat 2.80)
        r10_outcomes = _apply_r10_pq_cha_max(cal)
    recipe = RecipeReport(
        tuple(recipe.outcomes) + tuple(r08_outcomes) + tuple(r09_outcomes)
        + tuple(r10_outcomes)
    )

    # 3. Stage save (SC8S50 XDF, no checksums), then R09 slot caps + TC flags on
    #    the BinToolz XDF, with checksums corrected once at the final TC-flag save.
    stage_bin = out_dir / "_stage_r10_edited.bin"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(stage_bin), correct_checksums=False)
    caps_bin = out_dir / "_stage_r10_caps.bin"
    cap_records = _write_r09_slot_caps(stage_bin, caps_bin)
    out_bin = out_dir / OUT_BIN_NAME
    _tc_records, save_reports = _write_tc_flags(caps_bin, out_bin)

    # 4. Verify: checksums CLEAN, TC flags all 1, sanity plausible, and read back
    #    the base reshape + slot caps + the R10 PQ raise from the FINAL bin.
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
    pq_readback = np.asarray(fin.get(IP_PQ_SYMBOL).values, dtype=np.float64)
    pq_ok = (
        pq_readback.shape == (PQ_ROWS, PQ_COLS)
        and np.allclose(pq_readback[:, 0], R10_PQ_LOW_RPM_VAL, atol=5e-4)
        and np.allclose(pq_readback[:, 1:], R10_PQ_NEW, atol=5e-4)
    )
    finbt = CalFile.open(str(BT_XDF), str(out_bin))
    caps_ok = all(
        np.allclose(np.asarray(finbt.get(uid).values, dtype=np.float64),
                    np.tile(R09_SLOT_CAP_CURVE, (CAP_ROWS, 1)), atol=2.0)
        for uid in R09_SLOT_CAP_UIDS
    )
    slot2_ok = np.allclose(
        np.asarray(finbt.get(SLOT2_UID).values, dtype=np.float64), CAP_DEFAULT_HPA, atol=1.0
    )

    # 5. Comparison PNGs — the one table R10 actually changed: IP_PQ_CHA_MAX
    #    (R09 flat-2.80 baseline vs the R10 reshape), same heatmap+surface
    #    composite used for every other table's before/after. No PNGs are
    #    emitted for tables R10 left untouched (IP_FAC_BPA_SP[0]/[1], IP_PUT_SP,
    #    slot caps) — a "before/after" composite for those would misleadingly
    #    imply this revision changed them.
    pq_paths = compare_tables(pq_snap, fin.get(IP_PQ_SYMBOL), out_dir / "compare")

    # 6. Review report.
    report_md = _build_report_r10(
        recipe, patch_results, tc_flags, cap_records, clean, save_reports, sanity,
        out_bin, pq_readback, pq_paths,
    )
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")

    # --- console summary --- #
    print("R10 — reshape compressor pressure-quotient cap IP_PQ_CHA_MAX "
          f"({R10_PQ_LOW_RPM_VAL} @ 1000 rpm, flat {R10_PQ_NEW} @ 2000-7000 rpm) (patched bin)")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        print(f"  patch {name:24s}: {res.changed_bytes:>5} bytes changed "
              f"({res.changed_in_cal} CAL), confined={res.confined}")
    print(f"  R10 PQ cap     : IP_PQ_CHA_MAX 8x8 -> {R10_PQ_LOW_RPM_VAL} @ 1000 rpm, "
          f"flat {R10_PQ_NEW} @ 2000-7000 rpm  "
          f"(readback col0 {pq_readback[:, 0].min():.6f}-{pq_readback[:, 0].max():.6f}, "
          f"col1-7 {pq_readback[:, 1:].min():.6f}-{pq_readback[:, 1:].max():.6f}, "
          f"{'OK' if pq_ok else 'MISMATCH'})")
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
    print(f"  comparison PNGs: {len(pq_paths)} IP_PQ_CHA_MAX under {out_dir / 'compare'}")

    problems = []
    if not clean:
        problems.append("checksums STALE")
    if not all_on:
        problems.append("not all TC flags decoded to 1")
    if not sanity.plausible:
        problems.append("switch-patch sanity not plausible")
    if not pq_ok:
        problems.append("IP_PQ_CHA_MAX readback mismatch")
    if not base_ok:
        problems.append("base reshape readback mismatch")
    if not (caps_ok and slot2_ok):
        problems.append("slot cap readback mismatch")
    if recipe.do_not_flash():
        problems.append("recipe coherence: DO NOT FLASH")
    if problems:
        print(f"\n  ⛔ ISSUES: {'; '.join(problems)} — investigate before flashing.")
        raise SystemExit(f"R10 verification failed: {'; '.join(problems)}")
    else:
        print("\n  ✅ Patches confined, checksums CLEAN, 10/10 TC flags = 1, "
              "IP_PQ_CHA_MAX reshaped (1.70 @ 1000 rpm / 3.1 @ 2000-7000 rpm), "
              "base reshape + slot caps verified, switch-patch sanity plausible.")
        print("  ⚠ FULL FLASH REQUIRED (not CAL-only). Watch turbo speed (208/220 "
              "krpm) and HPFP (97-98%) on the R10 shelf logs; confirm code 128 goes "
              "silent. Review report + PNGs, then flash externally. Revision 10; "
              "iterate.")


if __name__ == "__main__":
    main()
