#!/usr/bin/env python3
"""TuningBasicsGuide R13 — the R12 calibration, re-declared in the tune API.

R13 changes **nothing** about the calibration. It is the same bin R12 produces,
byte for byte, written a different way: as one flat, self-contained declaration
using `simoscal.tune` instead of a chain of imports through five earlier
revision scripts.

That equivalence is the whole point of the revision. R12 imported private
helpers from R03, R07, R08, R10, and R11 and monkey-patched another module's
globals to inject its one change; understanding what it flashed meant mentally
executing five files. Everything below is on this page, in physical units, and
`build()` owns the verification pipeline that each earlier revision hand-rolled
its own copy of.

Because the calibration is unchanged, **R13 does not need to be flashed**. Its
job is to prove the new authoring path reproduces the old one exactly, so that
R14 onward can be written this way with the same confidence.

Run it and the byte-identity check runs itself: the raw-diff audit against the
R12 reference must report zero unexplained bytes, and this script additionally
asserts a full-file byte comparison.

Revision history (see REV_LOG.md):
    R00 — Base ecu-tuning-basics SOP plus the lambda axis re-breakpoint
          (HPDI[1] / MPI[1] / BAS[1] on the guide's breakpoints), clearing the
          base demo's LEAN-RISK DO NOT FLASH finding.
    R01 — Six limiter/fuelling writes the recipe left at stock: pedal threshold
          (72), max requested pressure (350000, raw), two max-intake-air tables
          (2000), max reference torque (1000), max allowed airmass (0.002).
    R02 — Report honesty only; bin byte-identical to R01.
    R03 — The guide's literal 0.80 on the three lambda minimum-value floors.
    R04 — Local WOT knock-retard timing overlay on the nine low-port-flap STND
          ignition grids, from the first R01 flash logs.
    R05 — Wastegate feedforward boost-tracking overlay plus a re-breakpoint of
          the shared exhaust-flow-factor X axis (1.25 → 1.40).
    R06 — Overboost limiter fix: repointed to the real P0234 threshold table
          `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`, raised 1800 → 2700.
    R07 — R06 calibration on a PATCHED bin (CBRICK + HSL + switch patch 29.33),
          with switch-patch traction control on for all five slots.
    R08 — Top-end wastegate deepening from the clean 3rd-gear R07 logs.
    R09 — Slot-2 26 psi shelf; established the min() semantics between the base
          PUT setpoint and the per-slot grids.
    R10 — `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
          compressor reshaped to 1.70 @ 1000 rpm / flat 3.1 above, after R09
          logs showed the cap trimming the shelf ~1.0–1.4 psi short.
    R11 — Parked the shared `IP_PUT_SP` ceiling at a non-binding 30 psi gauge
          and gave all five patch slots explicit lower caps.
    R12 — Slot 5 repurposed as a valet map: flat 1705 hPa absolute, floored so
          it cannot exceed 10 psi gauge.
    R13 — No calibration change. Re-declares the complete R12 calibration in
          the `simoscal.tune` API as one flat script with zero imports from
          other revision scripts, and asserts the output bin is byte-identical
          to R12's. The authoring path changes; the bytes do not.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from simoscal.tune import (
    SC8S50,
    SWITCH_PATCH_2933,
    PatchSpec,
    Tune,
    build,
)
from simoscal.tune.domains.switchpatch import PATCH_SPACE

# --------------------------------------------------------------------------- #
# Where everything lives
# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = REPO_ROOT / "Code"
BINTOOLZ = REPO_ROOT / "BinToolz-main"

XDF_PATH = CODE_ROOT / "xdf" / "SC8S50.V1.0.xdf"
BIN_PATH = CODE_ROOT / "bin" / "5G0906259L__0002.bin"       # stock recovery image
SWITCH_XDF = BINTOOLZ / "definitions" / "S50 Switch Patch.29.33.V2.xdf"
OUT_ROOT = Path(__file__).resolve().parent / "TUNE_Basics_Guide_out"
OUT_BIN_NAME = "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R13.bin"

#: The approved R12 output. R13 must reproduce it byte for byte.
R12_REFERENCE = (
    OUT_ROOT / "R12_20260715-165615"
    / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R12.bin"
)

PATCHES = (
    PatchSpec("SL CBRICK v1.2 - S50",
              BINTOOLZ / "patches" / "SL CBRICK v1.2 - S50.btp",
              "SimosTools anti-brick patch"),
    PatchSpec("SL HSL v1.1 - S50",
              BINTOOLZ / "patches" / "SL HSL v1.1 - S50.btp",
              "High Speed Logging (Mode3E) patch"),
    PatchSpec("SL PATCH.29.33 - S50",
              BINTOOLZ / "patches" / "SL PATCH.29.33 - S50.btp",
              "5-slot on-the-fly map switch patch (v29.33)"),
)

# --------------------------------------------------------------------------- #
# Fueling — the guide's lambda map and the breakpoints it was authored on
# --------------------------------------------------------------------------- #
LAMBDA_RPM = (1504, 2016, 2496, 3008, 3488, 4000, 4512, 4992, 5504, 5984, 6496, 7008)
LAMBDA_LOAD = (150.00, 299.99, 500.01, 700.00, 899.99, 1100.01, 1200.01, 1389.00)
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
LAMBDA_FLOOR = 0.80          # guide's literal target for the three floors
PEDAL_THRESHOLD_PCT = 72.0   # guide: heavy-throttle ~70–75; stock is flat 99.9

# --------------------------------------------------------------------------- #
# Ignition — absolute °CRK at the knock-prone points from the R01/R04 logs
# --------------------------------------------------------------------------- #
# (rpm, airmass mg/stk) -> commanded advance. The first seven are the measured
# knock pockets; the rest blend their surroundings so there is no timing cliff
# at the edge of a pulled cell.
TIMING = {
    (3500.0, 1400.0): -9.00,
    (4000.0, 1400.0): -6.75,
    (5000.0, 1400.0): -2.25,
    (5000.0, 1200.0): -2.25,
    (5500.0, 1200.0): -0.75,
    (6000.0, 1049.97): 1.875,
    (6500.0, 1049.97): 3.375,
    (3500.0, 1200.0): -6.00,
    (4000.0, 1200.0): -5.25,
    (4500.0, 1400.0): -3.75,
    (5500.0, 1400.0): 0.00,
    (5000.0, 1049.97): 1.125,
    (5500.0, 1049.97): 0.75,
    (6000.0, 900.0): 2.625,
    (6500.0, 900.0): 4.875,
}

# --------------------------------------------------------------------------- #
# Wastegate — feedforward position deltas (negative opens the gate sooner)
# --------------------------------------------------------------------------- #
# Grid axes: x = exhaust flow factor (col 15 = 1.40 after the re-breakpoint),
# y = intake flow factor. Both VVL maps always get the same deltas.
EXH_FLOW_AXIS_TOP = 1.40     # was 1.25; logged exhaust flow factor reaches ~1.33

# R05: sized from the mean PUT overshoot at each visited cell in the R04 logs.
WG_DELTAS_R05 = {
    (3, 12): -0.03, (3, 13): -0.04,                                   # blend row
    (4, 12): -0.08, (4, 13): -0.11, (5, 12): -0.09, (5, 13): -0.10,   # spool spike
    (5, 11): -0.05, (5, 14): -0.06, (6, 11): -0.03, (6, 12): -0.05,   # mid ridge
    (6, 13): -0.06, (6, 14): -0.06, (7, 13): -0.04,
    (6, 15): -0.11, (7, 14): -0.07, (7, 15): -0.11,                   # top end
    (8, 14): -0.03, (8, 15): -0.06,                                   # blend below
}
# R08: the sustained top-end overshoot in the clean 3rd-gear R07 logs leans 93%
# on the Int 1.05 row, so the pull is deep there and light on row 6.
WG_DELTAS_R08 = {
    (6, 14): -0.02, (6, 15): -0.02,
    (7, 14): -0.06, (7, 15): -0.04,
    (8, 14): -0.06, (8, 15): -0.04,
}

# --------------------------------------------------------------------------- #
# Boost — limiters, the compressor cap, and the parked base ceiling
# --------------------------------------------------------------------------- #
MANIFOLD_PRESSURE_MAX_HPA = 350000.0   # float-bug table; moved out of the way
INTAKE_AIR_MAX_MG = 2000               # genuine mg/stk
AIRMASS_CAP_MG = 2000                  # mg/stk in, kg/stk stored — see the API
TORQUE_REFERENCE_MAX_NM = 1000
OVERBOOST_THRESHOLD_HPA = 2700         # P0234 diagnosis threshold, raised

PQ_LOW_RPM, PQ_PLATEAU = 1.70, 3.1     # compressor pressure-quotient cap shape

# Parked non-binding base ceiling. Safe only because every selectable slot grid
# below is a verified lower cap under the R09-proven min() semantics.
BASE_CEILING_PSI = 30.0
PUT_RPM_AXIS = (3000.0, 3400.0, 4400.0, 5000.0, 5750.0, 6500.0)

# --------------------------------------------------------------------------- #
# Switch patch — the shared slot axis and the five selectable boost curves
# --------------------------------------------------------------------------- #
SLOT_RPM_AXIS = (3000, 3200, 3400, 3800, 4400, 4700, 5000, 5400, 5750, 6000, 6250, 6500)

# Slots 1 and 3 materialize the two documented R09 target shapes, resampled onto
# the finer shared slot axis. Clamped-linear, so the anchors are preserved
# exactly and nothing is invented between them.
_R09_AXIS_OLD = [2000.0, 3000.0, 4000.0, 5000.0, 5750.0, 6500.0]
_R09_TOPROW_OLD = [2699.0, 2699.0, 2500.0, 2350.0, 2299.0, 2199.0]
_R09_AXIS_NEW = [3000.0, 3400.0, 4400.0, 5000.0, 5750.0, 6500.0]
_R09_TOPROW_NEW = [2699.0, 2809.0, 2809.0, 2712.0, 2519.0, 2243.0]

SLOT_CONSERVATIVE = np.interp(SLOT_RPM_AXIS, _R09_AXIS_OLD, _R09_TOPROW_OLD)
SLOT_AGGRESSIVE = np.interp(SLOT_RPM_AXIS, _R09_AXIS_NEW, _R09_TOPROW_NEW)
# Intermediate: 24.4 psi plateau to 4400 rpm, then a smooth taper to 17.5 psi.
SLOT_INTERMEDIATE = (2699, 2699, 2699, 2699, 2699, 2645, 2589, 2503,
                     2414, 2350, 2286, 2223)

VALET_SLOT, VALET_CAP_PSI = 5, 10.0

SLOT_CURVES = {
    1: SLOT_CONSERVATIVE,     # conservative
    2: SLOT_INTERMEDIATE,     # intermediate
    3: SLOT_AGGRESSIVE,       # aggressive — the former R09/R10 shelf
    4: SLOT_CONSERVATIVE,     # same as slot 1
    # slot 5 is the valet cap, declared in psi so the library floors it
}
SLOT_LABELS = {
    1: "conservative",
    2: "intermediate",
    3: "aggressive — the former R09/R10 shelf",
    4: "conservative, same as slot 1",
}

SUMMARY = """\
R13 makes **no calibration change**. It reproduces the R12 bin byte for byte
from a single flat declaration, replacing R12's chain of imports through five
earlier revision scripts. Because the bytes are identical to the already-
reviewed R12, there is nothing new to flash — this revision exists to prove the
authoring path, not to change the car.
"""


def declare(tune: Tune) -> None:
    """The complete R00–R12 calibration, in the order the ECU layers it."""
    # -- Fueling: axes first, so the guide's grid lands on the loads it was
    #    authored for, then the recipe can write HPDI/MPI without mismatching.
    tune.fueling.rebreakpoint_lambda_axes(
        rpm=LAMBDA_RPM, load=LAMBDA_LOAD,
        intent="re-breakpoint lambda axes onto the loads the enrichment grid was authored for",
    )
    tune.fueling.lambda_grid(
        LAMBDA_CELLS, rpm_keys=LAMBDA_RPM, load_keys=LAMBDA_LOAD,
        intent="basic lambda enrichment map from the tuning guide (0.80 under high load)",
    )

    # -- The whole ecu-tuning-basics SOP, journaled per table.
    tune.apply_basics_sop()

    # -- Fueling and limiter values the recipe leaves at stock.
    tune.fueling.pedal_threshold(
        PEDAL_THRESHOLD_PCT,
        intent="drop full-load pedal threshold to ~72% so heavy throttle reaches full-load fueling",
    )
    tune.boost.manifold_pressure_max(
        MANIFOLD_PRESSURE_MAX_HPA,
        intent="raise the requested-IMP ceiling well clear so it never clamps the tune",
    )
    tune.limits.intake_air_max(
        INTAKE_AIR_MAX_MG,
        intent="raise both max-intake-air-per-stroke tables to 2000 mg/stk",
    )
    tune.limits.torque_reference_max(
        TORQUE_REFERENCE_MAX_NM,
        intent="lift the reference-torque monitor ceiling above the tune's crank torque",
    )
    tune.limits.airmass_cap_mg(
        AIRMASS_CAP_MG,
        intent="raise the airmass-setpoint cap to 2000 mg/stk (stored kg/stk, see the API)",
    )
    tune.fueling.lambda_floors(
        LAMBDA_FLOOR,
        intent="set the three lambda enrichment floors to 0.80 to permit the map's enrichment",
    )

    # -- Ignition: the measured knock pockets, on all nine cam-position grids.
    tune.ignition.retard_cells(
        TIMING,
        intent="pull timing at the R01/R04 measured knock pockets, blended so there is no cliff",
    )

    # -- Wastegate: unclamp the top of the map, then the two log-driven overlays.
    tune.wastegate.exh_flow_axis_last(
        EXH_FLOW_AXIS_TOP,
        intent="extend the exhaust-flow axis top to 1.40 (logged flow reaches ~1.33)",
    )
    tune.wastegate.overlay(WG_DELTAS_R05, intent="R05 overboost-ridge overlay")
    tune.wastegate.overlay(WG_DELTAS_R08, intent="R08 top-end deepening")

    # -- Boost: P0234 margin, then park the base ceiling on the R09 axis.
    tune.boost.overboost_threshold(
        OVERBOOST_THRESHOLD_HPA,
        intent="raise the P0234 overboost diagnosis threshold to give the tune margin",
    )
    tune.boost.put_rpm_axis(
        PUT_RPM_AXIS,
        intent="re-breakpoint the PUT-setpoint rpm axis onto the R09 grid",
    )
    tune.boost.put_ceiling_psi(
        BASE_CEILING_PSI, rounding="nearest",
        intent="park the non-binding base PUT ceiling at 30 psi above every selectable slot",
    )
    tune.boost.pressure_quotient_max(
        PQ_PLATEAU, low_rpm=PQ_LOW_RPM,
        intent="shape the compressor pressure-quotient cap (3.1 plateau above 1.70)",
    )

    # -- Switch patch: shared axis, the four tuned slots, then the valet cap.
    #    Every slot sits below the parked base ceiling, which is what makes the
    #    parked ceiling safe.
    tune.switchpatch.slot_rpm_axis(
        SLOT_RPM_AXIS,
        intent="set the shared switch-patch slot rpm axis to the fine 12-point grid",
    )
    for slot, curve in SLOT_CURVES.items():
        tune.switchpatch.slot_curve(
            slot, hpa=curve, require_as_patched=True,
            intent=f"switch-patch slot {slot} boost curve ({SLOT_LABELS[slot]})",
        )
    tune.switchpatch.slot_curve(
        VALET_SLOT, psi=VALET_CAP_PSI, require_as_patched=True,
        intent=f"valet map: never above {VALET_CAP_PSI:g} psi gauge",
    )

    # -- Traction control: the patch's own on all five slots, factory TC off so
    #    the two do not fight.
    tune.switchpatch.traction_control(
        intent="enable the patch's own traction control on all slots, factory TC off",
    )

    # -- A gate build() runs on the finished file.
    tune.switchpatch.require_sanity(stock_bin=BIN_PATH)


def main() -> None:
    if not R12_REFERENCE.is_file():
        raise SystemExit(f"Missing the R12 reference bin: {R12_REFERENCE}")

    tune = Tune.open(
        SC8S50, xdf=XDF_PATH, bin=BIN_PATH, patches=PATCHES,
        extra_spaces={PATCH_SPACE: (SWITCH_PATCH_2933, SWITCH_XDF)},
    )
    declare(tune)

    result = build(
        tune, "R13", out_root=OUT_ROOT, bin_name=OUT_BIN_NAME,
        reference_bin=R12_REFERENCE,
        title="TUNE_Basics_Guide_R13 — the R12 calibration, re-declared",
        summary=SUMMARY,
    )

    # The equivalence claim, checked rather than asserted in prose.
    identical = result.bin_path.read_bytes() == R12_REFERENCE.read_bytes()
    print(f"R13 saved  : {result.bin_path}")
    print(f"R13 report : {result.report_path}")
    print(f"R13 journal: {len(result.journal)} entries; "
          f"{len(result.journal.tables_touched())} tables touched")
    print(f"R13 audit  : {result.diff.summary()}")
    print(f"R13 vs R12 : {'BYTE-IDENTICAL' if identical else 'DIFFERENT'}")
    if not identical:
        raise SystemExit(
            "R13 is NOT byte-identical to R12. The raw-diff audit above "
            "localizes every difference to a table; investigate before "
            "adopting the new authoring path."
        )
    print(
        "\nR13 verified offline: the tune API reproduces R12 exactly. Nothing "
        "to flash — the calibration is unchanged. This script never flashes."
    )


if __name__ == "__main__":
    main()
