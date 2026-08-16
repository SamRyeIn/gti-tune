#!/usr/bin/env python3
"""TuningBasicsGuide R15 — walk back R08's wastegate deepening where it now under-delivers.

R15 changes **one thing**: five cells of `IP_FAC_BPA_SP[0]` / `[1]` — Wastegate
Position Feedforward, VVL 0 / VVL 1 move back toward their R07 values. Every
other table — the slot assignments R14 introduced, timing, fuelling, limiters,
the P0234 threshold, the compressor cap — is byte-identical to R14.

Why:

* The R14 logs (`Logs/BasicsGuide_R14/log_review.md`, Medium 2) show slot 4
  delivering up to **1.5 psi short** of its 26 psi target at 4000-4500 rpm,
  narrowing to on-target by redline, while `WG I Value` climbs from +0.7 % to
  +17.8 % with rpm. The closed loop is spending its integral doing feedforward's
  job, which is the signature of a feedforward base that is too **open** at high
  flow for the target it now has to serve.

* The cells carrying that shortfall are **exactly the six R08 lowered**, still
  at R08's values. R08 opened them to cut a measured top-end overboost against
  the R08-era targets; R10 then unclamped `IP_PQ_CHA_MAX` — Maximum allowed
  pressure quotient at turbo charger compressor, and R14 put the aggressive
  curve on slot 4. The overboost R08 was correcting no longer exists, so its
  edit now reads as a shortfall. R15 is therefore a *walk-back of a specific
  prior edit*, not a fresh reshape — a much better-bounded change.

How it was sized (`Logs/BasicsGuide_R14/size_r15_wastegate.py`):

Commanded feedforward position is a bilinear-weighted sum of table cells, so the
position change in an rpm band is linear in the cell deltas. The sizing script
builds that design matrix from the logged operating points and solves a bounded
least squares against the per-band shortfall, at the guide's ~0.05-position-per-
psi rule and R08's own ~70 % conservatism factor. Two bounds carry the safety
argument:

* **Never above the R07 value.** R08's deltas are the upper bound, so R15 can at
  most undo R08 in a cell — it can never write a more-closed feedforward than
  this lineage has already run and logged.
* **Never negative.** R15 only walks back. The Int 0.75 rows are excluded
  outright: they carry the upshift-overboost load (log review High 1), which
  cannot be sized because the `PUT` channel railed during the only instance.

The already-correct 6000-6500 rpm band (-1.0 kPa) is weighted up in the solve so
the edit does not push a band that is right into overshoot to buy a little more
elsewhere. Predicted result over the logged points, per rpm band:

    band        R14 actual   R15 predicted
    3500-4000     -5.5 kPa      -2.9 kPa
    4000-4500    -10.4 kPa      -7.2 kPa
    4500-5000     -6.5 kPa      -4.1 kPa
    5000-5500     -7.9 kPa      -4.5 kPa
    5500-6000     -5.5 kPa      -2.0 kPa
    6000-6500     -1.0 kPa      +1.4 kPa

That recovers roughly half the shortfall, on purpose. Fully closing it would
need cells more closed than R07, which is not justified on one session's logs
and would push airmass through a fuel system that already runs 96-98 % HPFP
effective volume through the shelf zone. If the next logs still show a gap, R16
can go past R07 with evidence.

**Primary watch item for the validation logs: fuel.** This edit adds boost where
the high-pressure pump has least headroom. It adds least there by construction
(+0.46 psi at 4000-4500, the tightest band), but HPFP effective volume and DI
rail hold are what decide whether R15 stands.

Because this is a real calibration change, **R15 is a starting point, not a
finished tune** — flash it, log it, review, iterate. On this car the R07 patch
set is already installed and R15 moves calibration bytes only, so a CAL flash is
eligible (see REV_LOG.md).

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
    R14 — Add a stock map (slot 1, factory boost target ~21.6 psi read live from
          the stock bin) and reorder the drivable slots least→most aggressive
          (1 stock, 2 conservative, 3 intermediate, 4 aggressive); slot 5 valet
          unchanged. Only the four per-slot `PUT setpoint` grids move; the shared
          base calibration is identical to R13/R12.
    R15 — Walk back R08's wastegate deepening in the five feedforward cells the
          R14 logs show under-delivering, bounded at the R07 values. Slot-4
          tracking was 1.5 psi short at 4000-4500 rpm with the WG integral
          carrying +18 %. Only `IP_FAC_BPA_SP[0]` / `[1]` move.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from simoscal import CalFile
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
OUT_BIN_NAME = "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R15.bin"

#: The flashed-and-logged R14 output. R15's byte audit is against this: only the
#: two wastegate feedforward maps and the checksums may differ.
R14_REFERENCE = (
    OUT_ROOT / "R14_20260810-111002"
    / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin"
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
LAMBDA_FLOOR = 0.80          # min-lambda floor; log-confirmed for this bin (rich logs)
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
# R15: the R14 logs invert R08's premise — the top end now *under*-delivers by up
# to 1.5 psi with the WG integral carrying +18 %, because R10 unclamped the
# compressor cap and R14 gave slot 4 the aggressive curve. These are R08's own
# cells, walked back toward R07 by a bounded least squares against the measured
# per-band shortfall (Logs/BasicsGuide_R14/size_r15_wastegate.py). Every value is
# capped at its R07 level: R15 can undo R08, never exceed it. (8, 14) solved to
# zero and is deliberately left at its R08 value; the Int 0.75 rows are untouched
# because they carry the un-sizable upshift-overboost load.
WG_DELTAS_R15 = {
    (6, 14): +0.020,   # Int 0.90 x Exh 1.00: 0.655 -> 0.675  (= R07)
    (6, 15): +0.020,   # Int 0.90 x Exh 1.40: 0.610 -> 0.630  (= R07)
    (7, 14): +0.060,   # Int 1.05 x Exh 1.00: 0.540 -> 0.600  (= R07)
    (7, 15): +0.010,   # Int 1.05 x Exh 1.40: 0.525 -> 0.535  (R07 is 0.565)
    (8, 15): +0.040,   # Int 1.25 x Exh 1.40: 0.475 -> 0.515  (= R07)
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

# The three tuned shapes are the R09-lineage curves, resampled onto the finer
# shared slot axis. Clamped-linear, so the anchors are preserved exactly and
# nothing is invented between them. Unchanged from R14.
_R09_AXIS_OLD = [2000.0, 3000.0, 4000.0, 5000.0, 5750.0, 6500.0]
_R09_TOPROW_OLD = [2699.0, 2699.0, 2500.0, 2350.0, 2299.0, 2199.0]
_R09_AXIS_NEW = [3000.0, 3400.0, 4400.0, 5000.0, 5750.0, 6500.0]
_R09_TOPROW_NEW = [2699.0, 2809.0, 2809.0, 2712.0, 2519.0, 2243.0]

SLOT_CONSERVATIVE = np.interp(SLOT_RPM_AXIS, _R09_AXIS_OLD, _R09_TOPROW_OLD)
SLOT_AGGRESSIVE = np.interp(SLOT_RPM_AXIS, _R09_AXIS_NEW, _R09_TOPROW_NEW)
# Intermediate: 24.4 psi plateau to 4400 rpm, then a smooth taper to 17.5 psi.
SLOT_INTERMEDIATE = (2699, 2699, 2699, 2699, 2699, 2645, 2589, 2503,
                     2414, 2350, 2286, 2223)


def _stock_full_load_curve(rpm_axis: tuple[float, ...]) -> np.ndarray:
    """Stock full-load boost target, resampled onto the slot rpm axis.

    Read live from the stock recovery bin's `IP_PUT_SP` — Pressure up throttle
    setpoint (highest load row), so the stock slot is provably the factory
    target (~2502–2506 hPa absolute, ~21.6 psi gauge) rather than a transcribed
    number. Clamped-linear onto the 12-point slot axis.
    """
    cal = CalFile.open(str(XDF_PATH), str(BIN_PATH))
    put = cal.get("IP_PUT_SP")
    stock_x = np.asarray(put.axis_values("x"), dtype=np.float64).ravel()
    stock_top = np.asarray(put.values, dtype=np.float64)[-1, :]
    return np.interp(rpm_axis, stock_x, stock_top)


SLOT_STOCK = _stock_full_load_curve(SLOT_RPM_AXIS)

VALET_SLOT, VALET_CAP_PSI = 5, 10.0

# R14 ordering, unchanged: slots 1→4 least → most aggressive; slot 5 valet.
SLOT_CURVES = {
    1: SLOT_STOCK,            # stock factory boost target (~21.6 psi)
    2: SLOT_CONSERVATIVE,     # conservative (~24.5 psi, ramps down)
    3: SLOT_INTERMEDIATE,     # intermediate (~24.5 psi, held then taper)
    4: SLOT_AGGRESSIVE,       # aggressive (~26 psi — the log-validated slot)
    # slot 5 is the valet cap, declared in psi so the library floors it
}
SLOT_LABELS = {
    1: "stock — factory IP_PUT_SP boost target (~21.6 psi)",
    2: "conservative (~24.5 psi)",
    3: "intermediate (~24.5 psi, held)",
    4: "aggressive (~26 psi) — the former R09/R10 shelf",
}

SUMMARY = """\
R15 walks back **R08's wastegate feedforward deepening** in the five cells the
R14 logs show under-delivering. Slot 4 tracked up to **1.5 psi short** of its
26 psi target at 4000-4500 rpm while `WG I Value` climbed to +17.8 % — the
closed loop doing feedforward's job. Those cells are exactly the six R08
lowered: R08 opened them to cut an overboost that R10 (compressor cap) and R14
(slot-4 curve) have since removed, so its edit now reads as a shortfall.

Deltas were solved, not guessed — commanded position is linear in the cells, so
a bounded least squares against the measured per-band shortfall gives them, at
the guide's 0.05-position-per-psi rule and R08's own ~70 % conservatism. **Every
value is capped at its R07 level**: R15 can undo R08 in a cell, never write a
more-closed feedforward than this lineage has run. The Int 0.75 rows are left
alone — they carry the upshift-overboost load, which cannot be sized while the
`PUT` channel rails.

This recovers roughly half the shortfall on purpose. Watch **fuel** on the
validation logs: HPFP effective volume already runs 96-98 % through the shelf
zone, and this edit adds boost there. Only `IP_FAC_BPA_SP[0]` / `[1]` move —
slot assignments, timing, fuelling and limiters are byte-identical to R14.
Starting point, not a finished tune.
"""


def declare(tune: Tune) -> None:
    """The complete calibration, in the order the ECU layers it. Only the two
    wastegate feedforward maps differ from R14."""
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
        intent="raise the three min-lambda floors from stock 0.72-0.75 to 0.80 — "
               "logs came back rich under load, so leaning the floors pulls the "
               "measured mixture back toward target (log-driven, per-bin call)",
    )

    # -- Ignition: the measured knock pockets, on all nine cam-position grids.
    tune.ignition.retard_cells(
        TIMING,
        intent="pull timing at the R01/R04 measured knock pockets, blended so there is no cliff",
    )

    # -- Wastegate: unclamp the top of the map, then the log-driven overlays in
    #    lineage order. R15's overlay is the only one that closes cells: it walks
    #    R08 back where the R14 logs show that edit now costing boost.
    tune.wastegate.exh_flow_axis_last(
        EXH_FLOW_AXIS_TOP,
        intent="extend the exhaust-flow axis top to 1.40 (logged flow reaches ~1.33)",
    )
    tune.wastegate.overlay(WG_DELTAS_R05, intent="R05 overboost-ridge overlay")
    tune.wastegate.overlay(WG_DELTAS_R08, intent="R08 top-end deepening")
    tune.wastegate.overlay(
        WG_DELTAS_R15,
        intent="R15 walk-back of R08 in the five cells the R14 logs show "
               "under-delivering (bounded at the R07 values, solved against the "
               "measured per-band shortfall)",
    )

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

    # -- Switch patch: shared axis, the four tuned/stock slots ordered
    #    least→most aggressive, then the valet cap. Unchanged from R14.
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
    if not R14_REFERENCE.is_file():
        raise SystemExit(f"Missing the R14 reference bin: {R14_REFERENCE}")

    tune = Tune.open(
        SC8S50, xdf=XDF_PATH, bin=BIN_PATH, patches=PATCHES,
        extra_spaces={PATCH_SPACE: (SWITCH_PATCH_2933, SWITCH_XDF)},
    )
    declare(tune)

    result = build(
        tune, "R15", out_root=OUT_ROOT, bin_name=OUT_BIN_NAME,
        reference_bin=R14_REFERENCE,
        title="TUNE_Basics_Guide_R15 — wastegate feedforward walked back toward R07",
        summary=SUMMARY,
    )

    print(f"R15 saved  : {result.bin_path}")
    print(f"R15 report : {result.report_path}")
    print(f"R15 journal: {len(result.journal)} entries; "
          f"{len(result.journal.tables_touched())} tables touched")
    print(f"R15 audit  : {result.diff.summary()}")
    print(
        "\nOnly IP_FAC_BPA_SP[0] and [1] should differ from R14 (5 cells each, "
        "plus the stored checksums). Read report.md and the compare/ PNGs "
        "before flashing. This script never flashes."
    )


if __name__ == "__main__":
    main()
