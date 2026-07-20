#!/usr/bin/env python3
"""Patched bin — TuningBasicsGuide, revision R07 (CBRICK + HSL + switch patch + TC).

R07 is based on R06 and runs the EXACT R06 CAL-edit pipeline unchanged (lambda
axis re-breakpoint, the six R01 limiter/fuelling writes, the R03 literal 0.80
lambda minimum-value floors, the R04 local WOT knock-retard ignition overlay, the
R05 wastegate feedforward overlay + shared X-axis re-breakpoint, and the R06
overboost-limiter fix). It adds NO new base-calibration tuning of its own.

**R07 = R06 calibration ON A PATCHED BIN, with the switch-patch traction control
turned on.** Relative to the R06 saved bin, R07 gains exactly four things:

  1. `SL CBRICK v1.2 - S50.btp`  — SimosTools anti-brick patch, applied.
  2. `SL HSL v1.1 - S50.btp`  — High Speed Logging patch (Mode3E logging in the
     SimosTools app), applied.
  3. `SL PATCH.29.33 - S50.btp`  — the 5-slot on-the-fly map switch patch
     (version 29.33), applied.
  4. Switch-patch traction control ENABLED on all five map slots: both
     `Enable SL TC`  — Enable the switch-patch's own slip-based traction control,
     and `Disable OEM TC`  — Disable the factory ECU-side TC torque intervention,
     set to 1 on slots 1-5 (patch-added 8-bit flags, no A2L symbol; addresses in
     TC_FLAGS below).

**⚠ FULL FLASH REQUIRED.** A switch-patched bin modifies ASW/code blocks, so it
must be flashed FULL (not CAL-only). Flashing this CAL-only is a wrong-flash
hazard. This script never flashes; the deliverable ends at a verified bin +
report + PNGs + REV_LOG entry, and Sam reviews before flashing.

Pipeline order (investigated empirically 2026-07-11, not assumed — see the R07
REV_LOG entry): **order A — patch the stock bin first, then run the R06 CAL-edit
pipeline on the patched base, then write the TC flags.** The three patches and the
R06 CAL edits touch DISJOINT byte regions (0 R06-edited bytes fall inside any
patch's declared blocks; 0 bytes are changed by both), so order A and order B
(CAL-edit first, then patch) were confirmed to produce a BYTE-IDENTICAL bin. Order
A is used because it reuses the R06 pipeline verbatim on the patched base, matching
the canonical `demos/apply_btp_patch.py` "patched bin is the base for tune
revisions" flow.

Slot-inheritance finding (investigated, not guessed): the switch patch's per-slot
switched tables are feature-enable flags and ADDITIVE modifiers / independent
per-slot limits (`PUT setpoint`, `RPM limiter`, `Speed limiter`, `Lambda
modifier`, `Spark modifier`, `Torque Request AT/MT Type 1-3`, flex-fuel enables) —
NONE are copies of the R06-edited base tables (lambda setpoint grid, timing,
wastegate feedforward, limiters). The R06 base calibration is therefore GLOBAL and
applies under every slot; no per-slot re-writes are needed. The per-slot limits
(RPM/Speed/PUT) carry the patch author's baked defaults and are flagged for Sam's
review, not tuned here.

This is still **revision 7 — a starting point, not a finished calibration**. The
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
          plus a re-breakpoint of their shared X axis last column (Exh flow factor
          1.25 -> 1.40) to unclamp and open the top end further.
    R06 — R05 + shared-recipe overboost limiter fix: the "Overboost limit -> 2700"
          entry was repointed from the wrong `C_PRS_IM_SP_LIM`  — Offset for the
          manifold-setpoint limitation to the real overboost table
          `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  — Overpressure upstream throttle
          threshold for turbocharger overpressure diagnosis (P0234), raised across
          all six cells 1800 -> 2700.
    R07 — R06 calibration applied to a PATCHED bin. Applies three BinToolz `.btp`
          patches to the stock bin (`SL CBRICK v1.2 - S50` anti-brick,
          `SL HSL v1.1 - S50` high-speed logging, `SL PATCH.29.33 - S50` 5-slot map
          switch), runs the full R06 CAL-edit pipeline on the patched base
          (disjoint byte regions — order-independent, verified), and turns the
          switch-patch traction control ON for all five slots by setting the
          patch-added flags `Enable SL TC` = 1 and `Disable OEM TC` = 1 on slots
          1-5. FULL FLASH REQUIRED. No new base-calibration tuning versus R06.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import warnings
from pathlib import Path

import numpy as np

from simoscal import (
    CalFile,
    apply_basics_sop,
    btp,
    format_report,
)
from simoscal.checksum import StaleChecksumWarning
from simoscal.safety import EditRangeWarning
from simoscal.sop_recipe import RecipeReport, TableOutcome

# R07 chains the full R06 CAL-edit pipeline verbatim (which is the full R05
# pipeline, which is the full R04 pipeline, ...). It introduces no new
# base-calibration tuning code — only the .btp patch application and the TC flags.
from TUNE_Basics_Guide_R03 import (
    BIN_PATH,   # Code/bin/5G0906259L__0002.bin — the read-only stock bin
    OUT_ROOT,
    XDF_PATH,   # Code/xdf/SC8S50.V1.0.xdf — the R06 CAL-edit XDF
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

OUT_BIN_NAME = "5G0906259L_0002_BasicsGuide_R07.bin"

REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH_DIR = REPO_ROOT / "BinToolz-main" / "patches"
# BinToolz's own switch-patch XDF — the one that loads under simoscal (U1). Used
# ONLY for the TC flags, the slot inspection, and switch_patch_sanity; the R06
# CAL edits keep using SC8S50.V1.0.xdf exactly as R06 does.
BT_XDF = REPO_ROOT / "BinToolz-main" / "definitions" / "S50 Switch Patch.29.33.V2.xdf"

# The three S50 patches, applied in this order (CBRICK -> HSL -> SWITCH). All were
# verified READY_TO_ACCEPT and confined on the stock bin and on each other; the S50
# variants match this car's SC8S50 file structure. Do NOT substitute 29.33.1 (no
# S50 variant) or older CBRICK/HSL versions.
PATCHES: tuple[tuple[str, Path, str], ...] = (
    ("SL CBRICK v1.2 - S50",  PATCH_DIR / "SL CBRICK v1.2 - S50.btp",  "SimosTools anti-brick patch"),
    ("SL HSL v1.1 - S50",     PATCH_DIR / "SL HSL v1.1 - S50.btp",     "High Speed Logging (Mode3E) patch"),
    ("SL PATCH.29.33 - S50",  PATCH_DIR / "SL PATCH.29.33 - S50.btp",  "5-slot on-the-fly map switch patch (v29.33)"),
)

# --------------------------------------------------------------------------- #
# Switch-patch traction-control flags (patch-added; NO A2L symbol — reference by
# title + address). Both are 8-bit scalars, 0 = off / 1 = on, identity MATH. In
# the BinToolz XDF each table's uniqueid EQUALS its (XDF) address; file offset in
# the bin = 0x200000 + address. Verified against both switch-patch XDFs 2026-07-11
# (knowledge/sc8s50-switchpatch-xdf.md). Confirmed to read 0 on the as-patched bin.
#
#   `Enable SL TC`   — Enable the switch-patch's own slip-based traction control
#   `Disable OEM TC` — Disable the factory ECU-side TC torque intervention
# --------------------------------------------------------------------------- #
ENABLE_SL_TC_ADDRS = (0x7D83F, 0x7D840, 0x7D841, 0x7D842, 0x7D843)   # slots 1-5
DISABLE_OEM_TC_ADDRS = (0x7D83A, 0x7D83B, 0x7D83C, 0x7D83D, 0x7D83E)  # slots 1-5
TC_FLAG_ON = 1.0

# DECISION (flagged for Sam's veto at the review gate): set BOTH flags to 1 on ALL
# FIVE slots, so TC behaviour is uniform regardless of which slot is selected from
# the stalk. Sam may want one slot left with OEM TC intact as a "safe" map — this
# is a one-line change (drop a slot from the tuples above) and is called out in the
# report so it is an explicit, easily-reversed choice.

# The TC behaviour tables (category "TC", 0xF8) are NOT tuned by R07 — their
# as-patched defaults are dumped into the report for Sam to review before flashing.
TC_BEHAVIOUR_CATEGORY = "TC"


def _apply_patches(stock: Path, out_dir: Path) -> tuple[Path, list[btp.ChangeResult]]:
    """Apply the three .btp patches to the stock bin in order (copy-on-write).

    Checks READY_TO_ACCEPT before each apply (fail loud, never force a NOT_READY),
    writes each patch's `format_change_report` into `out_dir`, and returns the final
    patched-base path plus the per-patch ChangeResults. The stock bin is never
    modified — every apply writes a new file into the run folder.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cur = stock
    results: list[btp.ChangeResult] = []
    for name, patch_path, _desc in PATCHES:
        pre = btp.check(cur, patch_path)
        if not pre.ready_to_apply:
            raise SystemExit(
                f"patch {name}: bin state is {pre.readiness}, requires "
                f"READY_TO_ACCEPT — refusing to apply (fail loud)."
            )
        out_bin = out_dir / f"_stage_{name.replace(' ', '_')}.bin"
        res = btp.apply(cur, patch_path, out_bin)
        if not res.confined:
            raise SystemExit(f"patch {name}: apply not confined to declared blocks — aborting.")
        (out_dir / f"{name.replace(' ', '_')}_change_report.md").write_text(
            btp.format_change_report(res), encoding="utf-8"
        )
        results.append(res)
        cur = out_bin
    return cur, results


def _run_r06_pipeline(cal: CalFile) -> tuple[RecipeReport, dict, list[TableOutcome]]:
    """Run the full R06 CAL-edit pipeline on an open CalFile (identical to R06).

    Returns the merged recipe report, the pre-overlay wastegate snapshots, and the
    R05 wastegate outcomes so the caller can emit the same R04->R05 comparison PNGs
    R06 does. Edits are staged in memory; the caller saves.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        lambda_outcomes = _rebreakpoint_lambda_family(cal)
        recipe_report = apply_basics_sop(cal)
        r03_outcomes = _apply_r03_writes(cal)
        r03_report = _merge_report(lambda_outcomes, recipe_report, r03_outcomes)
        r04_outcomes = _apply_r04_timing_overlay(cal)

        # R05 wastegate overlay: re-breakpoint the shared X axis FIRST so the
        # before/after Z PNGs are taken on the final axis, then snapshot, then
        # apply the Z cell edits. (Guards live; the axis-rebreakpoint asserts the
        # base is still stock 1.25 — it is, the patches don't touch this region.)
        r05_axis_outcome = _apply_r05_wg_axis_rebreakpoint(cal)
        r05_snaps = _snapshot_r05_wg(cal)
        r05_z_outcomes = _apply_r05_wg_overlay(cal)
        r05_outcomes = [r05_axis_outcome, *r05_z_outcomes]

    kept = tuple(
        o for o in (tuple(r03_report.outcomes) + tuple(r04_outcomes))
        if o.guide_section not in R05_SUPERSEDES_SECTIONS
    )
    return RecipeReport(kept + tuple(r05_outcomes)), r05_snaps, r05_outcomes


def _write_tc_flags(bin_in: Path, out_bin: Path) -> tuple[list[dict], list]:
    """Set both TC flags = 1 on all five slots; save the final checksum-clean bin.

    Opens `bin_in` (the R06-edited patched bin) with the BinToolz switch-patch XDF,
    confirms each flag reads its expected as-patched 0, writes 1, and saves the
    FINAL R07 bin with `correct_checksums=True` so CAL_CRC (dirtied by the patch and
    these writes) and ECM3 both verify CLEAN. Returns the per-flag old->new records
    and the save's ChecksumReports.
    """
    cal = CalFile.open(str(BT_XDF), str(bin_in))
    records: list[dict] = []
    for label, addrs in (("Enable SL TC", ENABLE_SL_TC_ADDRS),
                         ("Disable OEM TC", DISABLE_OEM_TC_ADDRS)):
        for slot, addr in enumerate(addrs, start=1):
            view = cal.get(addr)
            old = float(np.asarray(view.values).ravel()[0])
            if old not in (0.0, 1.0):
                raise SystemExit(
                    f"TC flag {label} slot {slot} ({addr:#x}) read {old!r}, "
                    "expected 0/1 — refusing to write (fail loud)."
                )
            view.set(np.array([[TC_FLAG_ON]], dtype=np.float64))
            records.append({"label": label, "slot": slot, "addr": addr,
                            "old": old, "new": TC_FLAG_ON})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", EditRangeWarning)
        save_reports = cal.save(str(out_bin), correct_checksums=True)
    return records, save_reports


def _read_tc_state(bin_path: Path) -> tuple[list[dict], list[dict]]:
    """Read back the 10 TC flags and dump the TC behaviour-table defaults.

    Returns (flag_records, behaviour_rows) from the final bin via the BinToolz XDF —
    used for the report and to assert every flag decoded to 1.
    """
    cal = CalFile.open(str(BT_XDF), str(bin_path))
    flags: list[dict] = []
    for label, addrs in (("Enable SL TC", ENABLE_SL_TC_ADDRS),
                         ("Disable OEM TC", DISABLE_OEM_TC_ADDRS)):
        for slot, addr in enumerate(addrs, start=1):
            val = float(np.asarray(cal.get(addr).values).ravel()[0])
            flags.append({"label": label, "slot": slot, "addr": addr, "value": val})

    behaviour: list[dict] = []
    for v in cal.unique_tables():
        if TC_BEHAVIOUR_CATEGORY in {c.name for c in v.table.categories}:
            vals = np.asarray(v.values, dtype=float).ravel()
            behaviour.append({
                "addr": int(v.uniqueid), "title": v.title, "units": v.units,
                "value": f"{vals.min():g}..{vals.max():g}" if vals.size > 1 else f"{vals[0]:g}",
            })
    behaviour.sort(key=lambda r: r["addr"])
    return flags, behaviour


def _build_report(
    recipe: RecipeReport,
    patch_results: list[btp.ChangeResult],
    tc_records: list[dict],
    tc_behaviour: list[dict],
    checksum_clean: bool,
    save_reports: list,
    sanity: btp.SanityResult,
    out_bin: Path,
) -> str:
    """Assemble the R07 review report: R07-specific sections + the recipe report."""
    L: list[str] = []
    L.append("# TUNE_Basics_Guide_R07 — patched bin (CBRICK + HSL + switch patch + TC)")
    L.append("")
    L.append("## ⚠ FULL FLASH REQUIRED — do NOT flash CAL-only")
    L.append("")
    L.append("This is a **switch-patched** bin: the three `.btp` patches modify "
             "ASW/code blocks, not just CAL. It **must be flashed FULL** (not "
             "CAL-only) in the SimosTools app. Flashing this CAL-only is a "
             "wrong-flash hazard. **This script never flashes** — review, then "
             "flash externally with a known-good stock recovery image on hand and "
             "the battery on a charger.")
    L.append("")
    L.append("## What R07 adds over R06")
    L.append("")
    L.append("R07 runs the **exact R06 base-calibration pipeline** (no new tuning) "
             "on a patched bin, and adds four things:")
    L.append("")
    for name, _p, desc in PATCHES:
        L.append(f"- **`{name}.btp`** — {desc}, applied.")
    L.append("- **Switch-patch traction control turned ON on all five slots** — "
             "`Enable SL TC` = 1 and `Disable OEM TC` = 1 on slots 1-5.")
    L.append("")

    L.append("## Patch application (order A: patch stock first, then R06 CAL edits)")
    L.append("")
    L.append("Pipeline order was investigated empirically, not assumed. The three "
             "patches and the R06 CAL edits touch **disjoint byte regions** (0 "
             "R06-edited bytes fall inside any patch's declared blocks; 0 bytes are "
             "changed by both), so order A (patch first) and order B (CAL edits "
             "first) were confirmed to produce a **byte-identical** bin. Order A is "
             "used — it reuses the R06 pipeline verbatim on the patched base.")
    L.append("")
    L.append("| Patch                    | Bytes changed | in CAL | Confined | CAL_CRC after | ECM3 after |")
    L.append("|--------------------------|---------------|--------|----------|---------------|------------|")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        cc = "stale" if (res.cal_crc and res.cal_crc.is_stale) else "clean"
        e3 = "stale" if (res.ecm3 and res.ecm3.is_stale) else "clean"
        L.append(f"| `{name}` | {res.changed_bytes:>13} | {res.changed_in_cal:>6} | "
                 f"{'YES':^8} | {cc:^13} | {e3:^10} |")
    L.append("")
    L.append("Each apply is copy-on-write (the stock recovery bin is never "
             "touched); per-patch `format_change_report`s are saved under "
             "`patches/` in this run folder.")
    L.append("")

    L.append("## Slot-inheritance finding (investigated, not guessed)")
    L.append("")
    L.append("The switch patch's per-slot switched tables are **feature-enable "
             "flags and additive modifiers / independent per-slot limits** — "
             "`PUT setpoint`, `RPM limiter`, `Speed limiter`, `Lambda modifier`, "
             "`Spark modifier`, `Torque Request AT/MT Type 1-3`, and the flex-fuel "
             "enables. **None of them are copies of the R06-edited base tables** "
             "(lambda setpoint grid, timing, wastegate feedforward, limiters). The "
             "R06 base calibration is therefore **global** and applies under every "
             "map slot — no per-slot re-writes are needed for the R06 tune to take "
             "effect.")
    L.append("")
    L.append("> **For Sam to review separately:** the per-slot `PUT setpoint`, "
             "`RPM limiter`, and `Speed limiter` tables carry the **patch author's "
             "baked defaults**, independent of the R06 calibration. They are not "
             "touched by R07. Inspect them (BinToolz XDF, `Map Slot 1-5` "
             "categories) before relying on a given slot.")
    L.append("")

    L.append("## Traction control flags — old → new (⚑ decision flagged for veto)")
    L.append("")
    L.append("**Decision:** both TC flags set to `1` on **all five slots**, so TC "
             "behaviour is uniform regardless of which slot is selected from the "
             "stalk. **Sam can veto this** — e.g. leave one slot with OEM TC intact "
             "as a \"safe\" map. It is a one-line change in the script "
             "(`ENABLE_SL_TC_ADDRS` / `DISABLE_OEM_TC_ADDRS`).")
    L.append("")
    L.append("Both are patch-added 8-bit scalars (0 = off / 1 = on), **no A2L "
             "symbol** — referenced by XDF title + address; file offset = "
             "`0x200000 +` address.")
    L.append("")
    L.append("| Flag (title) | Slot | Address | File offset | Old | New |")
    L.append("|--------------|------|---------|-------------|-----|-----|")
    for r in tc_records:
        L.append(f"| `{r['label']}` | {r['slot']} | `{r['addr']:#07x}` | "
                 f"`{0x200000 + r['addr']:#08x}` | {r['old']:g} | {r['new']:g} |")
    L.append("")
    L.append("`Enable SL TC` — Enable the switch-patch's own slip-based traction "
             "control (a PID controller intervening via ignition retard and "
             "wastegate). `Disable OEM TC` — Disable the factory ECU-side TC torque "
             "intervention so the two systems do not fight. (The ABS/ESC "
             "brake-based intervention is a separate module a CAL flag cannot "
             "touch.)")
    L.append("")

    L.append("## TC behaviour-table defaults (as-patched — NOT tuned by R07)")
    L.append("")
    L.append("R07 does **not** tune the TC behaviour tables (category `TC`). Their "
             "as-patched defaults are dumped here for review; changing them is a "
             "future revision informed by logs.")
    L.append("")
    L.append("| Address | Table (title) | Units | Value(s) |")
    L.append("|---------|---------------|-------|----------|")
    for r in tc_behaviour:
        units = r["units"] if r["units"] else "-"
        L.append(f"| `{r['addr']:#07x}` | {r['title']} | {units} | {r['value']} |")
    L.append("")

    L.append("## Checksums")
    L.append("")
    L.append(f"- `CAL_CRC` (CRC32 over the CAL block) — **corrected + "
             f"{'CLEAN' if checksum_clean else 'STALE'}** on the saved bin.")
    L.append(f"- `ECM3` (64-bit summation monitor) — "
             f"**{'CLEAN' if checksum_clean else 'STALE'}**.")
    L.append("- **ASW / code-block checksums — NOT verifiable here.** The patches "
             "modify ASW; SimosTools/VW_Flash compute those block checksums at "
             "**full-flash** time. This report does not imply they are clean — only "
             "that CAL_CRC and ECM3 are.")
    L.append(f"- switch-patch XDF sanity: {sanity.tables_resolved} slot/switch "
             f"tables resolved, {sanity.tables_decoded} decoded, "
             f"{len(sanity.decode_errors)} errors, "
             f"plausible = {'YES' if sanity.plausible else 'NO'}.")
    L.append("")

    L.append("## Logging reminder (HSL / Mode3E)")
    L.append("")
    L.append("The HSL patch enables **Mode3E high-speed logging** in the "
             "SimosTools app, but you must **import an HSL PID list** in the app "
             "for it to log (see `PIDs/` and `knowledge/simostools-app-guide.md`). "
             "Gear indexing in the resulting logs depends on which PID list is "
             "loaded — see `CLAUDE.md` (`Gear ()` is zero-indexed, +1 offset; "
             "`Gear (gear)` is the actual gear). Check the CSV header before "
             "interpreting gear.")
    L.append("")

    L.append(f"Saved bin: `{out_bin.name}` "
             f"({', '.join(r.name for r in save_reports)}).")
    L.append("")
    L.append("---")
    L.append("")
    L.append("# Inherited R00-R06 calibration report")
    L.append("")
    L.append(format_report(recipe))
    return "\n".join(L)


def main() -> None:
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = OUT_ROOT / f"R07_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Apply the three .btp patches to the stock bin (order A). Copy-on-write;
    #    the stock recovery image is never modified.
    patched_base, patch_results = _apply_patches(BIN_PATH, out_dir / "patches")

    # 2. Run the full R06 CAL-edit pipeline on the patched base (SC8S50 XDF).
    cal = CalFile.open(str(XDF_PATH), str(patched_base))
    recipe, r05_snaps, r05_outcomes = _run_r06_pipeline(cal)

    # Save the R06-edited patched bin as an intermediate; the TC-flag pass reopens
    # it with the BinToolz XDF and produces the final checksum-clean bin.
    stage_bin = out_dir / "_stage_r06_edited.bin"
    with warnings.catch_warnings():
        # The stage bin is DELIBERATELY saved with stale checksums (the final save
        # via _write_tc_flags corrects them), so squelch only that expected warning
        # — never blanket-ignore, which could mask an unexpected one.
        warnings.simplefilter("ignore", StaleChecksumWarning)
        cal.save(str(stage_bin), correct_checksums=False)

    # 3. Turn on the switch-patch TC flags (all five slots) and save the final bin.
    out_bin = out_dir / OUT_BIN_NAME
    tc_records, save_reports = _write_tc_flags(stage_bin, out_bin)

    # 4. Verify the final bin: checksums CLEAN, all ten TC flags decode to 1,
    #    switch-patch XDF sanity passes.
    verify_reports = CalFile.open(str(XDF_PATH), str(out_bin)).verify_checksums()
    clean = all((not r.can_verify) or (not r.is_stale) for r in verify_reports)
    tc_flags, tc_behaviour = _read_tc_state(out_bin)
    all_on = all(r["value"] == 1.0 for r in tc_flags)
    sanity = btp.switch_patch_sanity(out_bin, stock_bin_path=BIN_PATH)

    # 5. Comparison PNGs — same R04->R05 wastegate composites R06 produces.
    png_count, axis_changed = _write_r05_comparison_pngs(
        cal, r05_snaps, r05_outcomes, out_dir / "compare"
    )

    # 6. Review report.
    report_md = _build_report(
        recipe, patch_results, tc_records, tc_behaviour, clean,
        save_reports, sanity, out_bin,
    )
    (out_dir / "report.md").write_text(report_md, encoding="utf-8")

    # --- console summary --- #
    print("R07 — patched bin (CBRICK + HSL + switch patch + TC)")
    for (name, _p, _d), res in zip(PATCHES, patch_results):
        print(f"  patch {name:24s}: {res.changed_bytes:>5} bytes changed "
              f"({res.changed_in_cal} CAL), confined={res.confined}")
    print(f"  TC flags       : {sum(1 for r in tc_flags if r['value'] == 1.0)}/10 "
          f"set to 1 (all-five-slots decision — see report)")
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
        # report.md is already written above, so the failure is reviewable; exit
        # nonzero so a scripted caller detects the verification failure.
        print(f"\n  ⛔ ISSUES: {'; '.join(problems)} — investigate before flashing.")
        raise SystemExit(f"R07 verification failed: {'; '.join(problems)}")
    else:
        print("\n  ✅ Patches confined, checksums CLEAN, all 10 TC flags = 1, "
              "switch-patch sanity plausible.")
        print("  ⚠ FULL FLASH REQUIRED (not CAL-only). Review report + PNGs, then "
              "flash externally. This is revision 7; iterate.")


if __name__ == "__main__":
    main()
