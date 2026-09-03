"""MainTune R23 — optimise the pump-92 aggressive slot: fuel it, then spend the clean band.

R23 inherits the complete R22 calibration and changes **map slot 3** — the
aggressive ~26 psi curve, the everyday pump-92 map and the in-drive fallback.
It is the first revision in this lineage aimed at making that slot better
rather than at running an experiment beside it, and it is sized against every
pull the car has ever done on that curve: 51 plain-92 logs across R09, R11,
R14, R15, R17, R18 and R19, plus R22's four dosed control pulls, pooled by
`Logs/aggressive_slot_lineage/`. The slot *number* carrying the curve moved
three times over that span, so the pooling keys on the logged `PUT SP` —
Pressure up throttle setpoint cap (2806-2809 hPa, against 2699 for every other
slot this car has run) rather than on the number.

**What that population says.** Knock on this curve is not spread out. It sits
in two places:

    rpm band     events/min   deepest   median airmass   Lambda SP   EQT
    3000-3500        15.85     -2.62         1382         0.922     0.870
    3500-4000         0.00         -            -         0.880     0.820
    4000-4500         1.21     -1.50         1559         0.848     0.800
    4500-5000         8.99     -3.00         1490         0.806     0.790
    5000-5500         3.31     -3.00         1429         0.800     0.780
    5500-6000         3.15     -3.00         1366         0.800     0.790
    6000-6600         2.65     -3.00         1203         0.800     0.780

3000-3500 rpm is the worst band in the lineage and 3500-4500 is close to
silent — one event in 90 seconds of loaded WOT across seven sessions. That is
the shape R23 acts on: **fuel the band that knocks, and spend the band that
does not.**

**Fuelling.** The EQT Stage 2 reverse-engineering
(`knowledge/eqt-s2-timing-reverse-engineering.md`) is the only evidence in this
project that ties knock to fuelling rather than to timing, and the gap it
exposes is largest exactly where the knock is: +0.052 lambda at 3000-3500. So
R23 enriches the 3008 rpm column of `IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda
setpoint grid from 0.980/0.950 to 0.930 on both loaded rows, and takes the
5504-7008 rpm columns from 0.800 to 0.780, which is EQT's own top-end figure.

It does **not** reach EQT's 0.870 at 3000-3500, and the reason is the pump, not
appetite. `HPFP Eff Vol` — high-pressure fuel pump effective volume already
runs a median 89 % in that band and touches 100 % at 3500-4500, and
`Logs/aggressive_slot_lineage/size_r23.py` replays the ECU's own lambda lookup
over 8497 loaded samples (median error 0.001 lambda) to price each candidate
against it. Reaching 0.870 there needs +4.3 % fuel and puts the 99th percentile
at 99.4 % — the pump saturates, rail pressure falls short, and the mixture goes
lean anyway. The affordable step is the one written here: +0.8 % fuel,
p99 96.2 %, max 97.7 %. **Getting the rest needs less air, not more fuel** —
see the boost proposal in `Tunes/README_NEXT_STEPS.md`, which is deliberately
not built into this revision.

**Timing.** Slot 3's `Spark modifier` — map slot ignition offset grid, neutral
since the patch was installed, takes **+0.750 °CRK at 3500 and 4000 rpm** on
the two loaded airmass rows, and nothing anywhere else. Those are the two
columns covering the band that logged one knock event in 90 seconds, and EQT
ran 3.75-5.63 °CRK more timing there than this calibration does. +0.750 is two
encoding steps — a deliberately small first step into a band this lineage has
never spent.

Delivered timing at 1400 mg/stk goes -6.750 to -6.000 at 3500 rpm and -4.500 to
-3.750 at 4000 rpm. Both knock bands are left alone: 3000-3500 gets fuel and no
timing, and 4500-5000 gets neither.

**Two changes in one revision, and why they are still readable.** The lambda
and ignition moves sit in different rpm bands — 3000-3500 for fuel, 3500-4500
for timing — so the next log can attribute each on its own without a control
slot. They overlap only at the 3500 rpm boundary, where the 3008 lambda column
still has some weight; that band's knock rate is currently zero, so a rise
there is the one ambiguous outcome and is called out in `REV_LOG.md` § R23.

**Per-slot fuelling, and a table nobody has ever written.** The base lambda grid
is shared by all five slots, so enriching it enriches all five. The patch
provides five `Lambda modifier` — map slot lambda offset grids for exactly this,
and R23 is the first revision in the lineage to use one: slots 1 and 2 carry a
**positive** offset holding them at their prior lambda, and slots 3, 4 and 5
take the enrichment.

That routing is chosen for its failure mode, not for elegance. The grid's sign
has never been observed on this car — the sibling `Spark modifier` grid's sign
was measured from the R20 and R22 logs, but no revision has ever written a
lambda cell. Writing the enrichment into the *base* grid and using the modifier
only to hold two low-boost slots back means every way the modifier can be wrong
is a rich failure:

* wrong sign — slots 1 and 2 run richer still, on the two lowest-boost maps in
  the ladder, which is where the pump has the most headroom;
* inert grid — all five slots run the enrichment, which is what slot 3 is
  getting deliberately;
* correct — only slots 1 and 2 are held back, which is the intent.

Slot 3 itself carries a neutral modifier, so the map this revision is about is
not exposed to the question at all. `switchpatch.slot_lambda_map` enforces the
same discipline structurally: it bounds delivered lambda under **both** sign
conventions and refuses any write that would be unsafe either way.

**Boost is unchanged.** All five `PUT setpoint` — map slot boost cap grids are
read off the R22 bin and written back identically, so R23 is a fuelling and
timing revision on a boost curve the car has already run 55 logged pulls on.

This script builds a human-review candidate and never flashes an ECU.

Revision history (full rationale in Tunes/REV_LOG.md):
    R00 — Base tuning-guide SOP plus the lambda-axis re-breakpoint.
    R01 — Six limiter and fueling writes the base recipe left at stock.
    R02 — Report-honesty correction; calibration byte-identical to R01.
    R03 — Guide-author 0.80 values on the three lambda minimum floors.
    R04 — Local knock-retard overlay in all nine low-port-flap timing maps.
    R05 — Wastegate feedforward overlay and exhaust-flow-axis extension.
    R06 — Correct P0234 overboost-threshold routing and 2700 hPa value.
    R07 — Add CBRICK, HSL, switch patch 29.33, and patch traction control.
    R08 — Deepen top-end wastegate feedforward from R07 log evidence.
    R09 — Add the 26 psi boost shelf and establish slot/base min semantics.
    R10 — Raise the compressor pressure-quotient cap above the boost shelf.
    R11 — Park the base boost ceiling and make every slot an explicit cap.
    R12 — Repurpose slot 5 as a 10 psi valet map.
    R13 — Re-declare R12 in the flat simoscal.tune API; no byte change.
    R14 — Add a stock slot and reorder drivable slots least to most aggressive.
    R15 — Walk five wastegate cells back toward R07 from R14 log evidence.
    R16 — Install the exact Spark IAT table and match EQT table timing above 5000 rpm.
    R17 — Remove R04/R16 timing overlays and restore the complete guide table exactly.
    R18 — Pull timing locally at 4500-5000 rpm / 1200-1400 mg/stk from R17 logs.
    R19 — Guide knock fast-loop tables plus a sized wastegate feedforward close.
    R20 — Turn slot 5 into an octane-boosted timing map on slot 4's boost curve.
    R21 — Cut slot 5's 4000/4500 rpm peak-load timing; apex and top end held.
         Built and verified, never flashed; superseded by R22.
    R22 — Reorder the slot ladder by fuel requirement and add a mid-boost
         octane slot, so the boost-versus-timing trade is testable against a
         control in one session. Flashed and logged; the experiment came back
         null and the octane dose measured as worthless on the everyday map.
    R23 — Optimise the pump-92 aggressive slot: enrich 3000-3500 rpm and the
         top end as far as the fuel pump allows, add +0.750 CRK at 3500 and
         4000 rpm where the lineage has never knocked, and hold slots 1 and 2
         at their prior lambda through the first use of the per-slot `Lambda
         modifier` grids. Boost unchanged.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np

from simoscal import CalFile, structure_of
from simoscal.tune import (
    SC8S50,
    SWITCH_PATCH_2933,
    PatchSpec,
    Tune,
    build,
)
from simoscal.tune.domains.switchpatch import PATCH_SPACE
from simoscal.tune.profiles.switchpatch_2933 import S50_PUT_GRID_UIDS
from simoscal.tune.journal import KIND_AXIS


REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = REPO_ROOT / "Code"
BINTOOLZ = REPO_ROOT / "BinToolz-main"

XDF_PATH = CODE_ROOT / "xdf" / "SC8S50.V1.0.xdf"
BIN_PATH = CODE_ROOT / "bin" / "5G0906259L__0002.bin"
SWITCH_XDF = BINTOOLZ / "definitions" / "S50 Switch Patch.29.33.V2.xdf"
OUT_ROOT = Path(__file__).resolve().parent / "MainTune_out"
OUT_BIN_NAME = "Patched_259L_R23.bin"

#: The authoritative R22 run (Tunes/REV_LOG.md § R22) — the bin that is in the
#: car, the bin whose logs this revision is a response to, and the bin R23's
#: byte-level audit is taken against.
#:
#: It is also read directly, for all five boost curves: see `_curve_from_r22`.
#: R23 changes no boost at all, and the cheapest way to *prove* that is to read
#: each slot's cap off the flashed bin and write it back, rather than to
#: re-derive five curves from constants and hope the arithmetic lands on the
#: same bytes. R22 already put every curve on the slot it belongs on, so this is
#: a straight per-slot copy rather than the permutation R22 performed.
R22_REFERENCE = (
    REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
    / "R22_20260901-060746"
    / "Patched_259L_R22.bin"
)
R22_REFERENCE_SHA256 = (
    "08372bdee7c1c6b7b0ca89c8f9da31515622080927c99439f5578e6965bb475e"
)


PATCHES = (
    PatchSpec(
        "SL CBRICK v1.2 - S50",
        BINTOOLZ / "patches" / "SL CBRICK v1.2 - S50.btp",
        "SimosTools anti-brick patch",
    ),
    PatchSpec(
        "SL HSL v1.1 - S50",
        BINTOOLZ / "patches" / "SL HSL v1.1 - S50.btp",
        "High Speed Logging (Mode3E) patch",
    ),
    PatchSpec(
        "SL PATCH.29.33 - S50",
        BINTOOLZ / "patches" / "SL PATCH.29.33 - S50.btp",
        "5-slot on-the-fly map switch patch (v29.33)",
    ),
)


# Fueling — the guide grid, the axes it was authored on, and R23's enrichment.
LAMBDA_RPM = (
    1504, 2016, 2496, 3008, 3488, 4000,
    4512, 4992, 5504, 5984, 6496, 7008,
)
LAMBDA_LOAD = (
    150.00, 299.99, 500.01, 700.00,
    899.99, 1100.01, 1200.01, 1389.00,
)
#: The two rows that carry wide-open throttle. Loaded WOT on this engine runs
#: 1200-1600 mg/stk, so these are the only rows R23 touches — and 1389 is the
#: top of the axis, which is why both are written to the same value in every
#: column R23 moves.
LAMBDA_LOADED_ROWS = (6, 7)

#: R22's grid, carried forward unchanged except in the cells named below. Kept
#: under its own name so the enrichment is a *diff* against a stated starting
#: point rather than a retyped table where a slipped digit would look
#: deliberate.
LAMBDA_CELLS_R22 = (
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00),
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.92, 0.89, 0.87, 0.87),
    (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.95, 0.92, 0.89, 0.87, 0.85, 0.85),
    (1.00, 1.00, 1.00, 1.00, 0.97, 0.95, 0.92, 0.88, 0.86, 0.84, 0.82, 0.82),
    (1.00, 1.00, 1.00, 1.00, 0.95, 0.92, 0.88, 0.84, 0.83, 0.81, 0.80, 0.80),
    (1.00, 1.00, 1.00, 0.98, 0.93, 0.89, 0.87, 0.82, 0.80, 0.80, 0.80, 0.80),
    (1.00, 1.00, 0.98, 0.95, 0.90, 0.86, 0.84, 0.82, 0.80, 0.80, 0.80, 0.80),
)

#: The enrichment, as ``{rpm breakpoint: lambda}`` written into both loaded rows.
#:
#: **3008 rpm — 0.980/0.950 to 0.930.** 3000-3500 rpm is the worst knock band on
#: this boost curve (15.85 events per loaded minute over 51 pump-92 logs,
#: deepest -2.62 CRK, and -4.50 CRK on R22's dosed control), it commands the
#: leanest lambda of any boosted band, and it carries the largest gap to EQT
#: Stage 2's fuelling (+0.052). The knock events themselves cluster at
#: 3026-3156 rpm, which is this column.
#:
#: This is **not** EQT's 0.870, and the limit is the pump rather than the
#: intent: `Logs/aggressive_slot_lineage/size_r23.py` prices each candidate by
#: replaying the ECU's own lookup over 8497 loaded samples and scaling the
#: logged `HPFP Eff Vol` by the fuel ratio. 0.870 costs +4.3 % fuel and puts the
#: 99th percentile at 99.4 %, i.e. the pump on its stop, where enrichment stops
#: arriving and the mixture goes lean regardless of what is commanded. 0.930
#: costs +0.8 % and lands at p99 96.2 %, max 97.7 %.
#:
#: **5504-7008 rpm — 0.800 to 0.780.** EQT's own top-end figure, and the pump
#: has 25-30 points of headroom there (median 70-78 %). 5000-6600 rpm carries
#: three of the lineage's -3.00 CRK events. 7008 moves with the others so the
#: top of the axis stays flat: leaving it at 0.800 would make the grid lean out
#: again above 6496 rpm, which is inside the rev range.
LAMBDA_R23_ENRICHED = {
    3008.0: 0.93,
    5504.0: 0.78,
    5984.0: 0.78,
    6496.0: 0.78,
    7008.0: 0.78,
}

#: The grid's storage step, 1/1024 lambda. Asserted, not assumed: an enrichment
#: that is not a whole number of steps is not the enrichment declared here, and
#: the offsets that hold slots 1 and 2 back have to land on the same lattice or
#: they will not return those slots to the value they held.
LAMBDA_STEP = 1.0 / 1024.0


def _quantise_lambda(value: float) -> float:
    """The nearest lambda the grid can actually store."""
    return round(float(value) / LAMBDA_STEP) * LAMBDA_STEP


def _lambda_cells_r23() -> tuple[tuple[float, ...], ...]:
    """R22's grid with the enriched columns written into both loaded rows."""
    rows = [list(row) for row in LAMBDA_CELLS_R22]
    for rpm, value in LAMBDA_R23_ENRICHED.items():
        column = LAMBDA_RPM.index(int(rpm))
        for row in LAMBDA_LOADED_ROWS:
            if value > rows[row][column] + 1e-12:
                raise RuntimeError(
                    f"`IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda setpoint grid: "
                    f"{rpm:g} rpm, row {row} would go from "
                    f"{rows[row][column]:.4f} to {value:.4f} — leaner, not "
                    "richer. R23 declares an enrichment; refusing."
                )
            rows[row][column] = value
    return tuple(tuple(row) for row in rows)


LAMBDA_CELLS = _lambda_cells_r23()

#: The slots held back at their prior lambda through the per-slot `Lambda
#: modifier` grids. Slots 1 and 2 are the bad-tank and conservative maps: the
#: lowest boost, the most fuel-pump headroom, and the two places in the ladder
#: where an unenriched reference is worth keeping. Slots 3, 4 and 5 take the
#: enrichment from the base grid.
HOLD_LAMBDA_SLOTS = (1, 2)

#: What "prior lambda" means, per enriched rpm column: the value R22's grid held
#: on its **1389 mg/stk** row. The 1200.01 row held 0.980 at 3008 rpm rather
#: than 0.950, so holding both rows to one figure enriches slots 1 and 2
#: slightly at 1200 mg/stk. That is deliberate and it is the safe direction: the
#: modifier grid's top airmass row has to match the row below it (loaded WOT
#: runs past the 1389 breakpoint, and only a flat last segment is bounded
#: there), so one of the two figures has to give, and the richer one is the one
#: that cannot hurt.
LAMBDA_HOLD_TARGET = {
    3008.0: 0.95,
    5504.0: 0.80,
    5984.0: 0.80,
    6496.0: 0.80,
    7008.0: 0.80,
}

#: The bound `switchpatch.slot_lambda_map` holds every written cell to, as
#: (richest, leanest) **delivered** lambda — base grid plus modifier — and it is
#: checked under both sign conventions, because the patch's sign has never been
#: observed on this car.
#:
#: 0.955 lean: nothing in this calibration commands leaner than 0.950 anywhere
#: in boost, so a cell that would deliver past this is not an enrichment gone
#: slightly wrong, it is a leanout.
#: 0.755 rich: below EQT Stage 2's richest logged 0.780, and past the point
#: where `HPFP Eff Vol` can hold rail pressure — beyond it extra enrichment
#: stops arriving and the mixture goes lean regardless of what is commanded.
DELIVERED_LAMBDA_RANGE = (0.755, 0.955)


LAMBDA_FLOOR = 0.80
PEDAL_THRESHOLD_PCT = 72.0


# Spark IAT correction — exact guide-author table.
IAT_RPM = (608, 1312, 1696, 2016, 2496, 3008, 4000, 4512, 5024, 6080)
IAT_AXIS_R15 = (-30.00, -20.25, -9.75, 0.00, 30.00, 40.50, 50.25, 60.00, 70.50, 80.25)
IAT_AXIS_R16 = (-30.00, -20.25, -9.75, 0.00, 30.00, 35.25, 40.50, 50.25, 60.00, 80.25)
IAT_BASIC_CELLS = (
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    (0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00),
    (-1.12, -1.12, -1.12, -1.12, -1.12, -1.12, -1.87, -1.87, -1.87, -1.87),
    (-1.87, -2.25, -2.25, -2.25, -2.62, -1.87, -3.00, -3.00, -3.75, -3.75),
    (-3.37, -3.37, -3.00, -4.12, -4.12, -4.12, -4.12, -4.12, -4.87, -4.87),
    (-7.12, -7.12, -7.50, -7.50, -7.87, -7.87, -9.00, -9.00, -10.12, -10.12),
)
IAT_ENCODING_STEP_DEG = 0.375


# Base timing — complete guide table, encoded at the ECU's 0.375°CRK step.
TIMING_GUIDE_RPM = (
    400, 700, 1000, 1250, 1500, 1750, 2000, 2500,
    3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500,
)
TIMING_GUIDE_LOAD = (
    79.99, 100.00, 150.02, 199.99, 250.01, 299.99, 350.01, 399.99,
    498.99, 599.98, 699.98, 800.02, 900.02, 1049.97, 1200.01, 1400.00,
)
TIMING_GUIDE_CELLS = (
    (17.625, 21.375, 23.250, 26.625, 28.875, 24.000, 25.875, 27.000, 37.875, 40.125, 40.125, 40.125, 40.125, 40.125, 40.125, 40.125),
    (16.500, 18.000, 18.375, 21.375, 31.125, 37.125, 36.375, 36.750, 34.125, 37.875, 40.125, 40.125, 40.125, 40.125, 40.125, 40.125),
    (10.125, 10.125, 10.500, 15.000, 30.000, 36.375, 38.625, 33.375, 31.875, 33.375, 40.125, 40.125, 40.125, 37.500, 36.000, 40.125),
    (8.250, 8.250, 9.750, 16.875, 28.875, 32.250, 27.375, 26.250, 25.125, 25.875, 32.250, 33.750, 31.500, 30.375, 27.750, 29.250),
    (6.375, 6.375, 9.750, 16.125, 24.750, 24.375, 22.125, 21.375, 21.375, 22.125, 27.750, 27.375, 27.375, 26.250, 24.750, 25.125),
    (5.625, 5.625, 9.375, 15.000, 21.375, 21.375, 21.000, 19.500, 18.000, 19.125, 22.875, 24.375, 23.250, 23.625, 22.500, 23.250),
    (4.875, 4.875, 9.375, 14.250, 17.625, 18.750, 16.875, 18.000, 16.500, 17.625, 20.625, 20.625, 21.375, 21.375, 21.000, 21.750),
    (4.500, 4.500, 6.000, 9.000, 12.750, 17.250, 16.125, 15.000, 15.000, 16.125, 19.125, 19.125, 19.500, 20.250, 19.875, 20.625),
    (4.500, 4.500, 0.375, -5.250, 4.500, 9.375, 12.375, 12.000, 12.000, 13.875, 16.875, 16.500, 16.875, 17.625, 18.000, 19.125),
    (0.000, 0.000, 0.750, -3.000, 3.000, 4.125, 4.875, 10.125, 13.875, 14.250, 15.375, 15.750, 16.500, 16.875, 16.500, 18.000),
    (-4.125, -4.125, -2.250, -3.750, 1.125, 1.875, 1.500, 7.125, 9.750, 11.250, 12.000, 13.125, 13.875, 14.250, 11.250, 10.500),
    (-5.625, -5.625, -3.000, -4.125, 0.375, 1.125, 0.375, 1.500, 4.125, 4.125, 6.000, 7.125, 9.000, 9.375, 6.750, 7.125),
    (-12.375, -12.375, -7.875, -5.625, -3.000, -5.625, -3.000, -0.750, 0.000, 1.125, 1.500, 2.625, 2.250, 2.625, 3.375, 5.625),
    (-16.125, -16.125, -11.625, -9.000, -6.750, -8.250, -4.875, -4.125, -3.750, -2.625, -1.875, 1.125, 1.875, 1.500, 3.000, 4.500),
    (-18.000, -18.000, -14.250, -12.000, -9.750, -8.250, -6.750, -6.750, -6.750, -5.250, -4.125, -3.000, -0.750, 0.750, 1.875, 3.375),
    (-18.000, -18.000, -15.000, -12.750, -10.500, -9.000, -8.625, -8.250, -7.500, -6.750, -4.500, -3.000, -0.750, 0.750, 1.875, 3.375),
)
TIMING_GUIDE_TARGETS = {
    (rpm, load): TIMING_GUIDE_CELLS[row][column]
    for row, load in enumerate(TIMING_GUIDE_LOAD)
    for column, rpm in enumerate(TIMING_GUIDE_RPM)
}
TIMING_R18_LOCAL_TARGETS = {
    (4500.0, 1200.01): -3.750,
    (4500.0, 1400.00): -3.750,
    (5000.0, 1200.01): -2.250,
    (5000.0, 1400.00): -2.250,
}
TIMING_R18_TARGETS = dict(TIMING_GUIDE_TARGETS)
TIMING_R18_TARGETS.update(TIMING_R18_LOCAL_TARGETS)
BASE_IGNITION_TABLES = tuple(
    f"ignition_base_vvl0_i{intake}_e{exhaust}"
    for intake in range(3)
    for exhaust in range(3)
)


# Knock fast loop — the three guide tables, on the axes they are authored on.
#
# Sign convention: the knock correction is a NEGATIVE angle, so KNOCK_RECOVERY_STEP
# ("increase") is the amount returned per decay step, not extra retard. All three
# tables share the same engine-speed breakpoints.
KNOCK_RPM = (736, 1248, 1760, 2240, 3008, 4000, 4992, 6016)

# `IP_IGA_DEC_KNK` — Spark retard at recognised knocking, on rpm x airmass.
KNOCK_RETARD_LOAD = (348.99327077, 648.00924697, 898.99784848, 1100.00915541)
KNOCK_RETARD_STOCK = (
    (-1.500, -1.500, -1.500, -1.500, -1.500, -1.875, -1.875, -2.625),
    (-2.250, -2.250, -2.250, -2.250, -2.250, -2.250, -2.250, -2.250),
    (-2.250, -2.250, -2.250, -2.250, -2.625, -3.000, -3.000, -3.000),
    (-2.250, -2.250, -2.250, -2.250, -2.625, -3.000, -3.000, -3.000),
)
#: The guide's reduced grid (screenshot `image56`). TunerPro renders the 3-step
#: value as -1.12; the ECU's own encoding step is 0.375 °CRK, so the exact value
#: is -1.125 and every target below is a whole number of encoding steps.
KNOCK_RETARD_TARGET = (
    (-0.750, -0.750, -0.750, -0.750, -0.750, -1.125, -1.125, -1.125),
    (-1.125, -1.125, -1.125, -1.125, -1.125, -1.125, -1.125, -1.125),
    (-1.125, -1.125, -1.125, -1.125, -1.500, -1.500, -1.500, -1.500),
    (-1.500, -1.500, -1.500, -1.500, -1.500, -1.500, -1.500, -1.500),
)

# `IP_DLY_INC_FAST_KNK` — number of segments between each increase of fast loop.
KNOCK_RECOVERY_DELAY_STOCK = (2, 5, 7, 9, 16, 21, 27, 33)
#: Guide target (screenshot `image84`): untouched below 3008 rpm, ~30 % sooner above.
KNOCK_RECOVERY_DELAY_TARGET = (2, 5, 7, 9, 12, 15, 18, 21)

# `IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock
# is detected, on rpm x current correction. Stock is 0.375 everywhere except the
# 736 rpm column's two most-retarded rows.
KNOCK_RECOVERY_STEP_CORRECTION = (-6.0, -3.0, -1.5, -0.75)
KNOCK_RECOVERY_STEP_STOCK = (
    (0.750, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375),
    (0.750, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375),
    (0.375, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375),
    (0.375, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375, 0.375),
)
#: Guide target: 0.75 °CRK across, i.e. two encoding steps per decay step.
KNOCK_RECOVERY_STEP_TARGET = 0.750

#: The ECU's ignition encoding step. Every knock target must be a multiple of it,
#: or the value written back is not the value declared here.
KNOCK_ENCODING_STEP_DEG = 0.375


# Wastegate — inherited R05, R08, and R15 overlays.
EXH_FLOW_AXIS_TOP = 1.40
WG_DELTAS_R05 = {
    (3, 12): -0.03, (3, 13): -0.04,
    (4, 12): -0.08, (4, 13): -0.11, (5, 12): -0.09, (5, 13): -0.10,
    (5, 11): -0.05, (5, 14): -0.06, (6, 11): -0.03, (6, 12): -0.05,
    (6, 13): -0.06, (6, 14): -0.06, (7, 13): -0.04,
    (6, 15): -0.11, (7, 14): -0.07, (7, 15): -0.11,
    (8, 14): -0.03, (8, 15): -0.06,
}
WG_DELTAS_R08 = {
    (6, 14): -0.02, (6, 15): -0.02,
    (7, 14): -0.06, (7, 15): -0.04,
    (8, 14): -0.06, (8, 15): -0.04,
}
WG_DELTAS_R15 = {
    (6, 14): +0.020,
    (6, 15): +0.020,
    (7, 14): +0.060,
    (7, 15): +0.010,
    (8, 15): +0.040,
}
# ---- the intake-flow-factor re-breakpoint ---------------------------------- #
#
# Row 8 of `ldp_fac_2_ip_fac_bpa_sp` — the intake-flow-factor axis of the two
# feedforward maps — sits at 1.25, and row 9 at 1.50. Nothing in 2537 logged WOT
# samples exceeds 1.201, so both rows sit entirely above the operating envelope
# while the 5000-6000 rpm shortfall (median intake 1.06-1.10) and redline
# (median 1.00) are left sharing the cells on rows 6 and 7. Moving row 8 down to
# 1.15 gives the shortfall band a cell of its own: its weight there roughly
# doubles (0.201 -> 0.384) while staying negligible at redline (0.033 -> 0.066).
#
# This axis breakpoints those two maps and nothing else in the XDF, which is why
# it is safe to move at all. `tune.wastegate.move_intake_flow_breakpoint`
# resamples both maps as it moves the breakpoint, so the move alone changes no
# commanded position — `_apply_r19_wastegate` asserts exactly that against the
# logged operating points before any cell is edited.
WG_INTAKE_ROW = 8
WG_INTAKE_BREAKPOINT_OLD = 1.25
WG_INTAKE_BREAKPOINT_NEW = 1.15
#: The operating envelope the resample must hold exactly, in both flow factors.
#: Logged 3rd-gear WOT ranges are exhaust 0.677-1.449 and intake up to 1.201;
#: these carry margin on each side. Above intake 1.21 the top rows are
#: extrapolated, which is sound only while this engine cannot reach there — see
#: REV_LOG.md § R19 for what that costs if the turbo is ever changed.
WG_INTAKE_PRESERVE_TO = 1.21
WG_EXHAUST_RANGE = (0.65, 1.46)

#: Solved by `Logs/BasicsGuide_R18/size_r19_wastegate.py` from 2537 pooled
#: 3rd-gear WOT samples across both R18 sessions, against a bilinear replay of
#: the ECU's own lookup that reproduces the logged `WG Pos Base (%)` to 0.066
#: points RMS. Re-solved on the post-re-breakpoint geometry. Bounded at the
#: factory value — never more closed than stock — and with 4500-5000 rpm (HPFP
#: effective volume already 96 %) and 6000-6500 rpm (already +1.7 kPa over
#: target) held at zero so the solve cannot buy the shortfall band with fuel
#: headroom or redline overshoot it does not have.
#:
#: Row 8's values below are the *resampled* ones at intake 1.15, not R18's
#: values at 1.25.
WG_DELTAS_R19 = {
    (6, 14): +0.010,   # Int 0.90 x Exh 1.00: 0.675 -> 0.685 (stock 0.735)
    (8, 15): +0.066,   # Int 1.15 x Exh 1.40: 0.525 -> 0.591 (stock 0.625)
}
#: The stock value of each cell above, on the same re-breakpointed geometry,
#: asserted before the overlay is applied so "never more closed than stock" is a
#: checked bound rather than a comment.
WG_STOCK_CAP_R19 = {
    (6, 14): 0.735, (8, 15): 0.625,
}


# Boost, limiters, and switch-patch slots — inherited unchanged from R16.
MANIFOLD_PRESSURE_MAX_HPA = 350000.0
INTAKE_AIR_MAX_MG = 2000
AIRMASS_CAP_MG = 2000
TORQUE_REFERENCE_MAX_NM = 1000
OVERBOOST_THRESHOLD_HPA = 2700
PQ_LOW_RPM, PQ_PLATEAU = 1.70, 3.1
BASE_CEILING_PSI = 30.0
PUT_RPM_AXIS = (3000.0, 3400.0, 4400.0, 5000.0, 5750.0, 6500.0)

SLOT_RPM_AXIS = (
    3000, 3200, 3400, 3800, 4400, 4700,
    5000, 5400, 5750, 6000, 6250, 6500,
)
_R09_AXIS_OLD = (2000.0, 3000.0, 4000.0, 5000.0, 5750.0, 6500.0)
_R09_TOPROW_OLD = (2699.0, 2699.0, 2500.0, 2350.0, 2299.0, 2199.0)
_R09_AXIS_NEW = (3000.0, 3400.0, 4400.0, 5000.0, 5750.0, 6500.0)
_R09_TOPROW_NEW = (2699.0, 2809.0, 2809.0, 2712.0, 2519.0, 2243.0)
SLOT_CONSERVATIVE = np.interp(SLOT_RPM_AXIS, _R09_AXIS_OLD, _R09_TOPROW_OLD)
SLOT_AGGRESSIVE = np.interp(SLOT_RPM_AXIS, _R09_AXIS_NEW, _R09_TOPROW_NEW)
SLOT_INTERMEDIATE = (
    2699, 2699, 2699, 2699, 2699, 2645,
    2589, 2503, 2414, 2350, 2286, 2223,
)
#: The three slots this revision defines, by role.
#:
#: R22 reorders the ladder by **fuel requirement** rather than by boost. Slots
#: 1-3 are safe on pump 92; slots 4 and 5 require the VP Octanium dose. The
#: aggressive ~26 psi curve that had been slot 4 since R14 moves to slot 3 and
#: becomes the control, so the pump-gas everyday map and the A/B baseline are
#: the same slot and carry the exact calibration every log since R14 was scored
#: against. The in-drive fallback is now **slot 3**, not slot 4.
CONTROL_SLOT = 3
MID_BOOSTER_SLOT = 4
BOOSTER_SLOT = 5

#: R22 already put every curve on the slot it belongs on, so R23 reads slot N of
#: the R22 bin into slot N. There is no permutation this time and no boost change
#: at all; `_check_slot_ladder` proves it cell by cell.

#: The slots that carry a `Spark modifier` — map slot ignition offset. Every
#: other slot's grid stays at the patch's neutral 0.00°, which is asserted after
#: the writes rather than assumed.
OCTANE_SLOTS = (MID_BOOSTER_SLOT, BOOSTER_SLOT)

#: The everyday pump-92 map — the slot this revision exists to improve, and the
#: one whose 55 logged pulls sized every number in it. An alias rather than a
#: second literal, because a slot 3 that drifted from `CONTROL_SLOT` would leave
#: the timing and the fuelling pointing at different maps.
EVERYDAY_SLOT = CONTROL_SLOT

#: R23's ignition offset for the everyday slot: the rpm columns, and the offset
#: written into both loaded airmass rows of each.
#:
#: 3500 and 4000 rpm are the two columns covering the band this boost curve has
#: never knocked in — **zero** events over 40.7 loaded seconds at 3500-4000 and
#: one over 49.7 s at 4000-4500, across seven sessions and 51 logs. EQT Stage 2
#: runs 3.75-5.63 CRK more timing than this calibration in the same cells
#: (`Docs/eqt-timing-re/maps/gap_eqt_minus_R22_slots_13_(base).csv`), so the
#: headroom is not speculative — but that is a different box code on a dosed-
#: equivalent fuel, and this lineage moves in bounded steps. +0.750 is two
#: encoding steps.
#:
#: Nothing is written at 3000, 4500 or 5000 rpm. Those are the two knock bands:
#: 3000-3500 gets fuel instead, and 4500-5000 gets neither until the boost
#: question in README_NEXT_STEPS is settled.
R23_SPARK_RPM = (3500, 4000)
R23_SPARK_DEG = (0.750, 0.750)

#: The `Spark modifier` grid's own rpm breakpoints, in the eight columns R20
#: writes. These are the base ignition maps' engine-speed breakpoints — the
#: grids reuse that axis table byte for byte — so they are the top eight of
#: `TIMING_GUIDE_RPM`, asserted below rather than assumed.
SPARK_MODIFIER_RPM = TIMING_GUIDE_RPM[8:]

#: The airmass rows R20 writes: the top two of the shared airmass axis. WOT in
#: 3rd gear reaches ~1600 mg/stk, above the grid's 1400 top breakpoint, so the
#: 1400 row is what the engine actually runs on at the top of a pull. The 1200
#: row is written identically — `slot_spark_map` requires the top row to match
#: the one below it, which makes clamp-versus-extrapolate above 1400 moot.
SPARK_MODIFIER_ROWS_MG = (TIMING_GUIDE_LOAD[14], TIMING_GUIDE_LOAD[15])

#: The advance each octane slot adds, in °CRK, one value per
#: `SPARK_MODIFIER_RPM`. These two shapes are the experiment.
#:
#: R20 ran +1.125/+1.500/+2.250/+3.000/+3.750/+2.250/+1.500/+1.125 on the full
#: ~26 psi boost curve, and its logs indicted exactly one band: 4500-5000 rpm
#: went from 4.2 to 27.5 knock events per loaded minute against the R19 slot-4
#: baseline (Poisson p ~ 0.0006), carrying both of the session's -2.25 °CRK
#: cuts, at 4615 and 4653 rpm and a 1505 mg/stk mean. The +3.750 apex at 5000
#: rpm logged **zero** events over 9.5 s at 1423 mg/stk, improving on R19's
#: 9.7/min — so the binding variable looked like cylinder filling, not the size
#: of the offset.
#:
#: There are two ways to act on that, and R22 runs both against one control:
#:
#: * **Slot 5** keeps the timing cut R21 built — 4000 and 4500 brought down to
#:   +1.500, the apex and the top end held — on the full boost curve.
#: * **Slot 4** keeps R20's timing exactly, uncut, on ~1.6 psi less boost.
#:
#: If the load hypothesis is right, slot 4 runs the indicted timing cleanly at
#: reduced filling. If it is wrong, slot 4 knocks the way R20 did and the cut is
#: the right response. The two octane slots differ in exactly `CHANGED_COLUMNS` and in
#: the boost curve, and nothing else.
#:
#: Every value is a whole multiple of the grid's 0.375 °CRK storage step;
#: `slot_spark_map` refuses a non-storable offset rather than rounding it.
SPARK_MODIFIER_DEG = (1.125, 1.500, 1.500, 1.500, 3.750, 2.250, 1.500, 1.125)

#: R20's shape — the calibration that is in the car right now, and the one the
#: mid-boost slot restores. Declared once and aliased so the two cannot drift:
#: slot 4 carrying anything other than R20's exact timing would make the
#: reduced-boost comparison measure two changes instead of one.
R20_SPARK_MODIFIER_DEG = (1.125, 1.500, 2.250, 3.000, 3.750, 2.250, 1.500, 1.125)
MID_SPARK_MODIFIER_DEG = R20_SPARK_MODIFIER_DEG

#: The rpm columns in which the two octane slots differ, by index into
#: `SPARK_MODIFIER_RPM` — the columns R21 cut and slot 4 does not.
CHANGED_COLUMNS = (2, 3)

#: The grid's storage step. Asserted, not assumed — a declared offset that is
#: not a whole number of steps is not the offset that gets written.
SPARK_ENCODING_STEP_DEG = 0.375

#: The delivered-timing ceiling handed to `slot_spark_map`, in °CRK. The guard
#: caps **base + modifier**, not the offset: +3.00° onto a cell already at
#: +3.375° is a very different engine from +3.00° onto one at -7.50°.
#:
#: Both octane slots peak at +4.500° delivered (base +3.375 at 6500 rpm / 1400
#: mg/stk, plus the +1.125 offset). Slot 5's cut and slot 4's reduced boost are
#: both below that peak, so the ceiling is unchanged from R20 and one figure
#: covers both slots. +5.0 clears it by half a degree while staying tight enough
#: to catch a transposition — the 5000 rpm offset landing in the 6500 column
#: would deliver +7.125° and trip this.
MAX_DELIVERED_DEG = 5.0


#: The R18 logs the re-breakpoint no-op is asserted against.
R18_LOG_DIR = REPO_ROOT / "Logs" / "BasicsGuide_R18"
#: Half an encoding step of the feedforward table (~6.1e-5). A re-breakpoint that
#: moves any logged commanded position by more than this is not a resample.
WG_REBREAKPOINT_TOLERANCE = 3.05e-5


def _require_close(label: str, actual, expected, *, atol: float = 1e-8) -> None:
    actual_array = np.asarray(actual, dtype=np.float64)
    expected_array = np.asarray(expected, dtype=np.float64)
    if actual_array.shape != expected_array.shape:
        raise RuntimeError(
            f"{label}: shape {actual_array.shape} does not match {expected_array.shape}"
        )
    if not np.all(np.isfinite(actual_array)):
        raise RuntimeError(f"{label}: source contains a non-finite value")
    if not np.allclose(actual_array, expected_array, rtol=0.0, atol=atol):
        delta = float(np.max(np.abs(actual_array - expected_array)))
        raise RuntimeError(f"{label}: source mismatch; maximum absolute delta {delta:g}")


def _stock_wastegate_feedforward() -> np.ndarray:
    """The factory `IP_FAC_BPA_SP[0]` grid and its intake axis.

    Returned as a pair because R19 moves that axis: the stock cap for a cell has
    to be read off the stock *surface* at the cell's new intake breakpoint, not
    off the stock cell that used to live at that index.
    """
    cal = CalFile.open(
        str(XDF_PATH), str(BIN_PATH), structure=structure_of(BIN_PATH)
    )
    table = cal.get("IP_FAC_BPA_SP[0]")
    return (np.asarray(table.values, dtype=np.float64),
            np.asarray(table.axis_values("y"), dtype=np.float64).ravel())


def _stock_full_load_curve(rpm_axis: tuple[float, ...]) -> np.ndarray:
    """Read and resample the factory full-load boost target from the stock bin."""
    cal = CalFile.open(
        str(XDF_PATH), str(BIN_PATH), structure=structure_of(BIN_PATH)
    )
    put = cal.get("IP_PUT_SP")
    stock_rpm = np.asarray(put.axis_values("x"), dtype=np.float64).ravel()
    stock_curve = np.asarray(put.values, dtype=np.float64)[-1, :]
    return np.interp(rpm_axis, stock_rpm, stock_curve)


#: At and above this engine speed, map slot 1 follows slot 2's conservative
#: curve instead of the factory target.
#:
#: The factory `IP_PUT_SP` — Pressure up throttle setpoint full-load row is
#: essentially flat at ~2503 hPa, while the conservative curve starts at 2699 hPa
#: and decays through it at roughly 4020 rpm. Below the crossing the factory
#: target is the lower of the two; above it, the conservative curve is, falling
#: to 2199 hPa (~17.2 psi) by 6500 rpm against the factory 2506. So this makes
#: slot 1 shed boost at high rpm rather than hold the factory target there,
#: while its low end is untouched — the least aggressive slot gets less
#: aggressive exactly where cylinder pressure and knock risk are worst.
#:
#: The shared slot axis has no 4100 rpm breakpoint — it steps 3800 then 4400 —
#: so this threshold selects the eight breakpoints at and above 4400. Any value
#: in (3800, 4400] yields the identical curve; 4100 is where it was asked for.
#: Because the two curves cross inside that same interval, the result is also
#: exactly the **lower** of the two at every breakpoint, which `_slot1_curve`
#: asserts rather than leaving as a coincidence.
SLOT1_FOLLOW_SLOT2_AT_OR_ABOVE_RPM = 4100.0


def _slot1_curve(rpm_axis: tuple[float, ...]) -> np.ndarray:
    """Map slot 1: the factory target at low rpm, slot 2's curve above.

    Slot 1 remains the least aggressive slot and the bad-tank /
    hand-the-keys-over map, and this makes it more so: at and above
    `SLOT1_FOLLOW_SLOT2_AT_OR_ABOVE_RPM` it takes slot 2's conservative curve,
    which sits **below** the factory target there — down to ~17.2 psi at 6500 rpm
    against the factory ~21.6. Its low end is still the factory value, read live
    off the recovery bin by `_stock_full_load_curve`, so the slot keeps the
    provenance R14 established for the part of the range where the factory
    number is the conservative one.

    It is still called the stock map, but from this revision that is a **name,
    not a claim**: above 4400 rpm it is deliberately below the factory target.
    """
    factory = _stock_full_load_curve(rpm_axis)
    conservative = np.asarray(SLOT_CONSERVATIVE, dtype=np.float64)
    axis = np.asarray(rpm_axis, dtype=np.float64)
    if factory.shape != conservative.shape or factory.shape != axis.shape:
        raise RuntimeError(
            "`PUT setpoint` — map slot 1 boost cap: the factory curve, slot 2's "
            "curve and the rpm axis must all be the same length"
        )

    high = axis >= SLOT1_FOLLOW_SLOT2_AT_OR_ABOVE_RPM
    if not np.any(high) or np.all(high):
        raise RuntimeError(
            "`PUT setpoint` — map slot 1 boost cap: "
            f"{SLOT1_FOLLOW_SLOT2_AT_OR_ABOVE_RPM:g} rpm splits the axis into "
            f"{int(high.sum())} high and {int((~high).sum())} low breakpoints; "
            "it must select some of each"
        )
    curve = np.where(high, conservative, factory)

    # The threshold lands inside the interval where the two curves cross, so the
    # composed curve is the lower of the two at every breakpoint. If that stops
    # being true, the threshold has been moved off the crossing and slot 1 would
    # be taking the *higher* value somewhere — a silent boost lift on the map
    # that exists to be the safe one.
    if not np.array_equal(curve, np.minimum(factory, conservative)):
        raise RuntimeError(
            "`PUT setpoint` — map slot 1 boost cap: at "
            f"{SLOT1_FOLLOW_SLOT2_AT_OR_ABOVE_RPM:g} rpm the composed curve is "
            "not the lower of the factory and conservative curves at every "
            "breakpoint; the threshold has moved off the crossing"
        )
    _require_close(
        "`PUT setpoint` — map slot 1 boost cap: high-rpm section must be slot 2's",
        curve[high], conservative[high], atol=1e-9,
    )
    _require_close(
        "`PUT setpoint` — map slot 1 boost cap: low-rpm section must be the "
        "factory target read off the recovery bin",
        curve[~high], factory[~high], atol=1e-9,
    )
    return curve


def _curve_from_r22(slot: int, expected: np.ndarray, label: str) -> np.ndarray:
    """Read one map slot's boost curve off the flashed R22 bin.

    R23 changes no boost. The strongest way to say that is to read each slot's
    cap off the bin that is in the car and write the same numbers back, rather
    than to re-derive five curves from constants and trust that the arithmetic
    lands on the same bytes. The build's own byte audit then has nothing to
    forgive in these five tables.

    `expected` is the curve this script independently declares for that slot, so
    the read is checked rather than trusted; a mismatch means the R22 bin is not
    the bin this revision thinks it is.

    `switchpatch.slot_curve` tiles a single rpm curve across all eight
    uncharacterized Y rows, so a source grid that was *not* row-uniform would be
    silently flattened on its way to the new slot. That is asserted here, before
    the curve is used, along with the rpm axis it is sampled on.
    """
    cal = CalFile.open(
        str(SWITCH_XDF), str(R22_REFERENCE), structure=structure_of(R22_REFERENCE)
    )
    view = cal.get(int(S50_PUT_GRID_UIDS[slot], 16))
    grid = np.asarray(view.values, dtype=np.float64)
    axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()

    if grid.shape != (8, len(SLOT_RPM_AXIS)):
        raise RuntimeError(
            f"`PUT setpoint` — map slot {slot} boost cap "
            f"({S50_PUT_GRID_UIDS[slot]}) on the R22 bin is "
            f"{grid.shape}, not (8, {len(SLOT_RPM_AXIS)})"
        )
    _require_close(
        f"`PUT setpoint` — map slot {slot} boost cap: R22 rpm axis",
        axis,
        SLOT_RPM_AXIS,
        atol=1e-6,
    )
    if not np.all(grid == grid[0]):
        raise RuntimeError(
            f"`PUT setpoint` — map slot {slot} boost cap on the R22 bin is not "
            "uniform across its eight Y rows; copying it to another slot would "
            "flatten it. Refusing to build."
        )
    _require_close(
        f"`PUT setpoint` — map slot {slot} boost cap: the {label} curve read "
        f"off the R22 bin must be the one this script declares",
        grid[0],
        expected,
        atol=1.0,
    )
    return grid[0].copy()


_STOCK_WASTEGATE, _STOCK_WASTEGATE_AXIS = _stock_wastegate_feedforward()

#: Every slot's curve, read off the R22 bin rather than retyped. R23's whole
#: boost claim is "unchanged", and this is what makes that provable.
SLOT_CURVES = {
    1: _curve_from_r22(1, _slot1_curve(SLOT_RPM_AXIS), "slot 1 composed"),
    2: _curve_from_r22(2, SLOT_CONSERVATIVE, "conservative ~24.5 psi"),
    CONTROL_SLOT: _curve_from_r22(
        CONTROL_SLOT, SLOT_AGGRESSIVE, "aggressive ~26 psi"),
    MID_BOOSTER_SLOT: _curve_from_r22(
        MID_BOOSTER_SLOT, SLOT_INTERMEDIATE, "intermediate ~24.4 psi"),
    BOOSTER_SLOT: _curve_from_r22(
        BOOSTER_SLOT, SLOT_AGGRESSIVE, "aggressive ~26 psi"),
}
_R22_AGGRESSIVE = SLOT_CURVES[CONTROL_SLOT]
_R22_INTERMEDIATE = SLOT_CURVES[MID_BOOSTER_SLOT]
SLOT_LABELS = {
    1: "stock — ~21.6 psi factory `IP_PUT_SP` — Pressure up throttle setpoint "
       "below 4400 rpm, slot 2's conservative curve at 4400 and above (down to "
       "~17.2 psi at redline), pump 92, prior lambda held",
    2: "conservative (~24.5 psi), pump 92, prior lambda held",
    CONTROL_SLOT: "aggressive (~26 psi), pump 92, ENRICHED, +0.750 °CRK at 3500 "
                  "and 4000 rpm — the everyday map and the in-drive fallback, "
                  "and what this revision optimises",
    MID_BOOSTER_SLOT: "mid (~24.4 psi) with R20's uncut octane timing, enriched "
                      "— DOSED TANK ONLY",
    BOOSTER_SLOT: "aggressive (~26 psi) with R21's cut octane timing, enriched "
                  "— DOSED TANK ONLY",
}
SLOT_CURVE_INTENTS = {
    slot: (f"retain map slot {slot}'s boost cap exactly as R22 flashed it, read "
           f"off the R22 bin rather than retyped ({SLOT_LABELS[slot]})")
    for slot in (1, 2, CONTROL_SLOT, MID_BOOSTER_SLOT, BOOSTER_SLOT)
}

#: The largest boost delta the two octane slots are allowed to be apart, in hPa.
#: Not a safety bound — a design bound, inherited from R22 and re-checked here
#: because R23 claims to leave the ladder alone: if this changed, some boost
#: curve moved.
OCTANE_BOOST_DELTA_MAX_HPA = 200.0


def _check_slot_ladder() -> tuple[float, float]:
    """Prove R23 leaves the ladder exactly where R22 put it, before writing.

    Every curve here was read off the R22 bin, so the interesting failures are
    a mis-declared *expectation* (caught in `_curve_from_r22`) and a slot that
    stopped standing in the relationship the labels claim. Both are checked:
    slots 3 and 5 must still carry one identical aggressive curve, slot 4 must
    still sit at or below it everywhere, and slot 1 must still be the least
    aggressive map at every breakpoint.

    Returns the peak and maximum boost separation in hPa, for the report.
    """
    if not np.array_equal(SLOT_CURVES[CONTROL_SLOT], _R22_AGGRESSIVE):
        raise RuntimeError(
            f"slot {CONTROL_SLOT} must carry the aggressive curve read off the "
            f"R22 bin's slot {CONTROL_SLOT}"
        )
    if not np.array_equal(SLOT_CURVES[BOOSTER_SLOT], _R22_AGGRESSIVE):
        raise RuntimeError(
            f"slot {BOOSTER_SLOT} must carry the same aggressive curve as slot "
            f"{CONTROL_SLOT}, or the two differ in boost as well as timing"
        )
    if not np.array_equal(SLOT_CURVES[MID_BOOSTER_SLOT], _R22_INTERMEDIATE):
        raise RuntimeError(
            f"slot {MID_BOOSTER_SLOT} must carry the intermediate curve read "
            f"off the R22 bin's slot {MID_BOOSTER_SLOT}"
        )

    # Slot 1 is the map you reach for when something is wrong, so it has to be
    # at or below every other slot at every breakpoint. Composing it from two
    # curves rather than reading one makes that worth checking.
    for other in (2, CONTROL_SLOT, MID_BOOSTER_SLOT, BOOSTER_SLOT):
        if not np.all(SLOT_CURVES[1] <= SLOT_CURVES[other] + 1e-9):
            over = [
                f"{rpm:g} rpm: {one:.0f} > {two:.0f} hPa"
                for rpm, one, two in zip(SLOT_RPM_AXIS, SLOT_CURVES[1],
                                         SLOT_CURVES[other]) if one > two + 1e-9
            ]
            raise RuntimeError(
                "map slot 1 must be the least aggressive slot, but exceeds "
                f"slot {other} at {', '.join(over)}"
            )

    mid = SLOT_CURVES[MID_BOOSTER_SLOT]
    top = SLOT_CURVES[BOOSTER_SLOT]
    if not np.all(mid <= top + 1e-9):
        over = [
            f"{rpm:g} rpm: {m:.0f} > {t:.0f} hPa"
            for rpm, m, t in zip(SLOT_RPM_AXIS, mid, top) if m > t + 1e-9
        ]
        raise RuntimeError(
            f"slot {MID_BOOSTER_SLOT} is the mid-boost slot but exceeds slot "
            f"{BOOSTER_SLOT} at {', '.join(over)}"
        )
    delta = top - mid
    if not np.any(delta > 0.0):
        raise RuntimeError(
            f"slots {MID_BOOSTER_SLOT} and {BOOSTER_SLOT} carry identical boost "
            "curves; the ladder R22 built is not the one this bin holds"
        )
    if float(delta.max()) > OCTANE_BOOST_DELTA_MAX_HPA:
        raise RuntimeError(
            f"slots {MID_BOOSTER_SLOT} and {BOOSTER_SLOT} separate by "
            f"{delta.max():.0f} hPa, above the declared "
            f"{OCTANE_BOOST_DELTA_MAX_HPA:.0f} hPa design bound"
        )
    return float(top.max() - mid.max()), float(delta.max())


SUMMARY = """\
R23 inherits the complete R22 calibration — every base ignition cell, the knock
fast-loop tables, the wastegate feedforward and its re-breakpointed intake axis,
the exact Spark IAT tables, the limiters, the patch set, and **all five `PUT
setpoint` — map slot boost caps** — and changes fuelling and one slot's timing.

**Boost is unchanged.** Every slot's cap is read off the flashed R22 bin and
written back, so the five boost tables are provably the ones the car has already
run 55 logged pulls on rather than five curves re-derived from constants.

**What R23 is for.** Map slot 3 — the aggressive ~26 psi curve — is the everyday
pump-92 map and the in-drive fallback. Every pull this car has ever done on that
curve was pooled to size this revision: 51 plain-92 logs across R09, R11, R14,
R15, R17, R18 and R19 plus R22's four dosed control pulls, keyed on the logged
boost cap rather than on the slot number, which has moved three times. That
population says the knock is in two places and nowhere else:

    rpm band     events/min   deepest   airmass   Lambda SP   EQT     HPFP med
    3000-3500        15.85     -2.62      1382      0.922     0.870     88.9 %
    3500-4000         0.00         -         -      0.880     0.820     92.7 %
    4000-4500         1.21     -1.50      1559      0.848     0.800     94.8 %
    4500-5000         8.99     -3.00      1490      0.806     0.790     93.2 %
    5000-5500         3.31     -3.00      1429      0.800     0.780     86.2 %
    5500-6000         3.15     -3.00      1366      0.800     0.790     75.6 %
    6000-6600         2.65     -3.00      1203      0.800     0.780     69.3 %

So: fuel the band that knocks, and spend the band that does not.

**Fuelling — `IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda setpoint grid**, on the
two loaded rows (1200.01 and 1389.00 mg/stk):

    rpm      3008     5504     5984     6496     7008
    R22     0.980/   0.800    0.800    0.800    0.800
            0.950
    R23     0.930    0.780    0.780    0.780    0.780

3008 rpm is the column the 3000-3500 knock cluster sits in — every event in that
band lands at 3026-3156 rpm — and it commands the leanest lambda of any boosted
band while carrying the largest gap to EQT Stage 2's fuelling. 5504-7008 takes
EQT's own top-end figure, where the pump has 25-30 points of headroom and three
of the lineage's -3.00 °CRK events sit. 7008 moves with the rest so the grid
does not lean out again above 6496 rpm, which is inside the rev range.

**This is not EQT's 0.870 at 3008, and the limit is the fuel pump.**
`Logs/aggressive_slot_lineage/size_r23.py` replays the ECU's own lambda lookup
over 8497 loaded samples — median error 0.001 lambda — and scales the logged
`HPFP Eff Vol` by the fuel ratio each candidate needs. 0.870 costs +4.3 % fuel
and puts the 99th percentile at 99.4 %: the pump on its stop, where enrichment
stops arriving and the mixture goes lean regardless of what is commanded. 0.930
costs +0.8 % and lands at p99 96.2 %, max 97.7 %. Closing the rest of the gap
needs **less air**, not more fuel, which is the boost proposal in
`Tunes/README_NEXT_STEPS.md` and is deliberately not built into this revision.

**Per-slot fuelling, through a table nobody has written before.** The base
lambda grid is shared by all five slots. The patch provides five `Lambda
modifier` — map slot lambda offset grids for exactly this, and R23 is the first
revision in the lineage to use one: slots 1 and 2 carry a **positive** offset
(+0.0205 at 3008, +0.0195 at 5504-7008) holding them at the lambda they ran
under R22, and slots 3, 4 and 5 take the enrichment.

The routing is chosen for its failure mode. The grid's sign has never been
observed on this car — the sibling `Spark modifier` grid's sign was measured
from the R20 and R22 logs, but no revision has ever written a lambda cell. The
enrichment therefore goes into the *base* grid, a path logged since R00, and the
modifier is used only to take it back off the two lowest-boost maps. Wrong sign:
slots 1 and 2 run richer still, where the pump has the most headroom. Inert
grid: all five slots run the enrichment, which is what slot 3 is getting
deliberately. Correct: only slots 1 and 2 are held back. Slot 3 itself carries a
neutral grid, so the map this revision is about is not exposed at all.
`switchpatch.slot_lambda_map` bounds delivered lambda under **both** sign
conventions and refuses any write that is unsafe either way.

**Timing — slot 3's `Spark modifier` — map slot ignition offset**, neutral since
the patch went on, takes +0.750 °CRK at 3500 and 4000 rpm on the two loaded
airmass rows, and nothing anywhere else:

    rpm            3000    3500    4000    4500    5000    5500    6000    6500
    base          -7.500  -6.750  -4.500  -3.750  -2.250  +0.750  +1.875  +3.375
    slot 3 mod      -     +0.750  +0.750    -       -       -       -       -
    slot 3 dlv    -7.500  -6.000  -3.750  -3.750  -2.250  +0.750  +1.875  +3.375

Those two columns cover the band this boost curve has never knocked in: zero
events over 40.7 loaded seconds at 3500-4000 and one over 49.7 s at 4000-4500,
across seven sessions. EQT runs 3.75-5.63 °CRK more timing in the same cells.
+0.750 is two encoding steps — a deliberately small first step. Both knock bands
are left alone: 3000-3500 gets fuel and no timing, 4500-5000 gets neither.

**Two changes, and why the next log can still separate them.** The lambda and
ignition moves sit in different rpm bands, so each is attributable without a
control slot. They overlap only at the 3500 rpm boundary, where the 3008 lambda
column still carries some weight — and that band's knock rate is currently zero,
so a rise there is the one ambiguous outcome. Slots 1 and 2 keep R22's fuelling,
so the ladder still holds an unenriched reference.

**Slots 4 and 5 are for a dosed tank only** — pump 92 AKI dosed with VP Octanium
Unleaded at 10-11 oz per 10 US gallons. Octanium 2855 contains TEL and would
destroy the catalyst and the O2 sensor this project's log analysis depends on.
They keep R22's timing exactly and gain the enrichment along with slot 3.
**Slot 3 is the everyday map and the in-drive fallback.**

Delivered timing is capped at +5.00 °CRK by `slot_spark_map`, which reads the
live base map to check base + modifier rather than the offset alone. Every slot
writes its 1200 and 1400 mg/stk rows identically, because WOT reaches ~1600
mg/stk and only a flat last segment is bounded above the top breakpoint.

This is a starting point for human review and logging, not a finished
calibration, and the script never flashes. See `Tunes/REV_LOG.md` § R23 for the
logging gate.
"""


def _apply_r16_iat(tune: Tune) -> float:
    """Write the exact Basic grid and preserve the shared-axis Reference curve."""
    rpm_axis = tune.values("ignition_temp_rpm_axis").ravel()
    old_iat_axis = tune.values("ignition_temp_iat_axis").ravel()
    old_reference = tune.values("ignition_temp_correction_reference")
    author_grid = np.asarray(IAT_BASIC_CELLS, dtype=np.float64)
    new_iat_axis = np.asarray(IAT_AXIS_R16, dtype=np.float64)

    _require_close(
        "`ldpm_n_32_5_igsp` — Basis for temperature correction of IGA versus "
        "N_32, TIA: shared engine-speed axis",
        rpm_axis,
        IAT_RPM,
    )
    _require_close(
        "`ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA "
        "versus N_32, TIA: shared intake-air-temperature axis",
        old_iat_axis,
        IAT_AXIS_R15,
    )
    if author_grid.shape != (10, 10) or not np.all(np.isfinite(author_grid)):
        raise RuntimeError(
            "`IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of "
            "Basic IGA versus N_32, TIA: author grid must be finite and 10 × 10"
        )
    if new_iat_axis.shape != (10,) or not np.all(np.diff(new_iat_axis) > 0.0):
        raise RuntimeError(
            "`ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA "
            "versus N_32, TIA: R16 axis must be finite and strictly increasing"
        )
    if old_reference.shape != (10, 10) or not np.all(np.isfinite(old_reference)):
        raise RuntimeError(
            "`IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of "
            "Reference IGA versus N_32, TIA: source grid must be finite and 10 × 10"
        )

    migrated_reference = np.column_stack([
        np.interp(new_iat_axis, old_iat_axis, old_reference[:, column])
        for column in range(old_reference.shape[1])
    ])

    tune.write(
        "ignition_temp_iat_axis",
        new_iat_axis,
        kind=KIND_AXIS,
        intent="replace the stock IAT breakpoints with the tuning-guide author's "
               "exact axis: add 35.25 °C and remove 70.50 °C",
    )
    tune.write(
        "ignition_temp_correction_basic",
        author_grid,
        intent="install the tuning-guide author's exact Spark IAT correction: "
               "zero through 35.25 °C, then the authored warm-IAT retard rows",
    )
    tune.write(
        "ignition_temp_correction_reference",
        migrated_reference,
        intent="resample the existing Reference IGA correction onto the new shared "
               "IAT axis so its physical response is preserved",
    )

    staged_axis = tune.values("ignition_temp_iat_axis").ravel()
    staged_basic = tune.values("ignition_temp_correction_basic")
    staged_reference = tune.values("ignition_temp_correction_reference")
    _require_close(
        "`ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA "
        "versus N_32, TIA: staged R16 axis",
        staged_axis,
        new_iat_axis,
    )
    _require_close(
        "`IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic "
        "IGA versus N_32, TIA: staged author grid",
        staged_basic,
        author_grid,
        atol=0.01,
    )

    dense_iat = np.linspace(old_iat_axis[0], old_iat_axis[-1], 4001)
    max_deviation = max(
        float(np.max(np.abs(
            np.interp(dense_iat, old_iat_axis, old_reference[:, column])
            - np.interp(dense_iat, staged_axis, staged_reference[:, column])
        )))
        for column in range(old_reference.shape[1])
    )
    if max_deviation > IAT_ENCODING_STEP_DEG + 1e-9:
        raise RuntimeError(
            "`IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of "
            "Reference IGA versus N_32, TIA: shared-axis migration changes the "
            f"physical curve by {max_deviation:.6f}°CRK, above one "
            f"{IAT_ENCODING_STEP_DEG:.3f}°CRK encoding step"
        )
    return max_deviation


def _apply_r18_local_timing(tune: Tune) -> None:
    """Write the guide baseline plus the local R18 correction and prove it."""
    expected = np.asarray(TIMING_GUIDE_CELLS, dtype=np.float64).copy()
    if expected.shape != (16, 16) or not np.all(np.isfinite(expected)):
        raise RuntimeError(
            "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition "
            "angle, VVL 0 port-flap-low: guide table must be finite and 16 × 16"
        )

    for (rpm, load), target in TIMING_R18_LOCAL_TARGETS.items():
        column = TIMING_GUIDE_RPM.index(int(rpm))
        row = TIMING_GUIDE_LOAD.index(load)
        expected[row, column] = target

    for name in BASE_IGNITION_TABLES:
        _require_close(
            f"{tune.table(name).label}: engine-speed axis",
            tune.axis(name, "x"),
            TIMING_GUIDE_RPM,
            atol=1e-6,
        )
        _require_close(
            f"{tune.table(name).label}: airmass axis",
            tune.axis(name, "y"),
            TIMING_GUIDE_LOAD,
            atol=1.01,
        )

    tune.ignition.retard_cells(
        TIMING_R18_TARGETS,
        intent="retain the complete R17 tuning-guide base-ignition grid, then "
               "pull 0.75° at 4500 rpm and 1.50° at 5000 rpm in the 1200 and "
               "1400 mg/stk rows to address repeatable R17 knock while retaining "
               "stock knock detection and correction behavior",
    )

    staged = []
    for name in BASE_IGNITION_TABLES:
        values = tune.values(name)
        _require_close(
            f"{tune.table(name).label}: staged R18 local timing table",
            values,
            expected,
            atol=1e-8,
        )
        staged.append(values)
    if not all(np.array_equal(staged[0], values) for values in staged[1:]):
        raise RuntimeError(
            "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, "
            "VVL 0 port-flap-low cam-position maps diverged after the R18 write"
        )

def _apply_r19_knock(tune: Tune) -> None:
    """Write the three guide knock fast-loop tables and prove what landed.

    Every check here exists because one of these tables is easy to get wrong in
    a way the bin will happily accept: the shared rpm axis must be the one the
    guide authored against, the retard grid must still be stock before it is
    replaced (so R19 is not silently stacking on an unnoticed earlier edit),
    every target must be a whole number of the ECU's 0.375 °CRK encoding step,
    and the retard grid must end up strictly shallower than stock in every cell
    while the backstop `IP_IGA_MAX_KNK` — Maximum value for spark retard is
    left byte-identical.
    """
    retard_stock = np.asarray(KNOCK_RETARD_STOCK, dtype=np.float64)
    retard_target = np.asarray(KNOCK_RETARD_TARGET, dtype=np.float64)
    delay_stock = np.asarray(KNOCK_RECOVERY_DELAY_STOCK, dtype=np.float64)
    delay_target = np.asarray(KNOCK_RECOVERY_DELAY_TARGET, dtype=np.float64)
    step_stock = np.asarray(KNOCK_RECOVERY_STEP_STOCK, dtype=np.float64)
    step_target = np.full_like(step_stock, KNOCK_RECOVERY_STEP_TARGET)

    for name in ("knock_retard", "knock_recovery_delay", "knock_recovery_step"):
        _require_close(
            f"{tune.table(name).label}: engine-speed axis",
            tune.axis(name, "x"),
            KNOCK_RPM,
            atol=1e-6,
        )
    _require_close(
        f"{tune.table('knock_retard').label}: airmass axis",
        tune.axis("knock_retard", "y"),
        KNOCK_RETARD_LOAD,
        atol=1e-6,
    )
    _require_close(
        f"{tune.table('knock_recovery_step').label}: accumulated-correction axis",
        tune.axis("knock_recovery_step", "y"),
        KNOCK_RECOVERY_STEP_CORRECTION,
        atol=1e-6,
    )

    # R19 is the first revision in this lineage to touch knock control at all,
    # so each table must read exactly stock going in.
    _require_close("`IP_IGA_DEC_KNK` — Spark retard at recognised knocking: "
                   "inherited value", tune.values("knock_retard"), retard_stock)
    _require_close("`IP_DLY_INC_FAST_KNK` — number of segments between each "
                   "increase of fast loop: inherited value",
                   tune.values("knock_recovery_delay").ravel(), delay_stock)
    _require_close("`IP_IGA_INC_KNK` — Increasing value of knock integrated "
                   "correction when knock is detected: inherited value",
                   tune.values("knock_recovery_step"), step_stock)

    # Every declared angle must sit on the ECU's own encoding grid, or the value
    # read back is not the value this script says it wrote.
    for label, grid in (
        ("`IP_IGA_DEC_KNK` — Spark retard at recognised knocking", retard_target),
        ("`IP_IGA_INC_KNK` — Increasing value of knock integrated correction "
         "when knock is detected", step_target),
    ):
        steps = grid / KNOCK_ENCODING_STEP_DEG
        if not np.allclose(steps, np.round(steps), rtol=0.0, atol=1e-9):
            raise RuntimeError(
                f"{label}: a target is not a whole multiple of the "
                f"{KNOCK_ENCODING_STEP_DEG:.3f}°CRK encoding step"
            )

    # Direction guards. The retard grid may only get shallower, the delay only
    # shorter, and the recovery step only larger — R19 speeds recovery up and
    # softens the initial cut; it must not deepen or slow anything anywhere.
    if not np.all(retard_target > retard_stock):
        raise RuntimeError(
            "`IP_IGA_DEC_KNK` — Spark retard at recognised knocking: a target "
            "cell is not strictly shallower than stock"
        )
    if not np.all(delay_target <= delay_stock):
        raise RuntimeError(
            "`IP_DLY_INC_FAST_KNK` — number of segments between each increase "
            "of fast loop: a target segment count is longer than stock"
        )
    if not np.all(step_target >= step_stock):
        raise RuntimeError(
            "`IP_IGA_INC_KNK` — Increasing value of knock integrated correction "
            "when knock is detected: a target step is smaller than stock"
        )

    backstop_before = tune.values("knock_retard_max")

    tune.write(
        "knock_retard",
        retard_target,
        intent="halve the initial knock cut to the tuning guide's grid "
               "(-0.75/-1.125/-1.50 °CRK) so a single detected event costs less "
               "timing, leaving `IP_IGA_MAX_KNK` — Maximum value for spark "
               "retard as the unchanged backstop on total accumulated retard",
    )
    tune.write(
        "knock_recovery_delay",
        delay_target.reshape(tune.values("knock_recovery_delay").shape),
        intent="shorten the fast-loop decay interval above 3008 rpm "
               "(16/21/27/33 -> 12/15/18/21 segments) so a cut taken at 4500-6000 "
               "rpm clears before the following upshift rather than after it; "
               "the four breakpoints below 3008 rpm keep their stock values",
    )
    tune.write(
        "knock_recovery_step",
        step_target,
        intent="return 0.75 °CRK per decay step everywhere instead of 0.375, "
               "the guide's value, doubling how much timing each step hands back",
    )

    _require_close("`IP_IGA_DEC_KNK` — Spark retard at recognised knocking: "
                   "staged value", tune.values("knock_retard"), retard_target)
    _require_close("`IP_DLY_INC_FAST_KNK` — number of segments between each "
                   "increase of fast loop: staged value",
                   tune.values("knock_recovery_delay").ravel(), delay_target)
    _require_close("`IP_IGA_INC_KNK` — Increasing value of knock integrated "
                   "correction when knock is detected: staged value",
                   tune.values("knock_recovery_step"), step_target)
    _require_close("`IP_IGA_MAX_KNK` — Maximum value for spark retard: must be "
                   "untouched by the knock recovery change",
                   tune.values("knock_retard_max"), backstop_before)


def _apply_r19_wastegate(tune: Tune) -> None:
    """Re-breakpoint the intake axis, prove it changed nothing, then close cells.

    The order matters and is the whole safety argument. The re-breakpoint is
    performed first and asserted to be a no-op against the *logged* operating
    points — 2537 pooled 3rd-gear WOT samples from both R18 sessions. Only then
    are cells edited. So any boost behaviour change in the next log is
    attributable to the two-cell close, never to the geometry move.
    """
    axis_before = tune.axis("wastegate_feedforward_vvl0", "y")
    _require_close(
        "`ldp_fac_2_ip_fac_bpa_sp` — intake flow factor axis: breakpoint being "
        "moved must still be at its inherited value",
        axis_before[WG_INTAKE_ROW],
        WG_INTAKE_BREAKPOINT_OLD,
        atol=1e-6,
    )
    before_maps = {
        name: tune.values(name) for name in ("wastegate_feedforward_vvl0",
                                             "wastegate_feedforward_vvl1")
    }
    exh_axis = tune.axis("wastegate_feedforward_vvl0", "x")

    tune.wastegate.move_intake_flow_breakpoint(
        WG_INTAKE_ROW,
        WG_INTAKE_BREAKPOINT_NEW,
        preserve_to=WG_INTAKE_PRESERVE_TO,
        exhaust_range=WG_EXHAUST_RANGE,
        intent="give the 5000-6000 rpm boost shortfall a feedforward cell of "
               "its own by moving the intake flow factor breakpoint 1.25 -> "
               "1.15, resampling both maps so no commanded position changes "
               "at any 3rd-gear WOT point this engine is logged at; part-throttle "
               "and lift states are NOT covered by that assertion",
    )

    axis_after = tune.axis("wastegate_feedforward_vvl0", "y")
    _assert_feedforward_unchanged(
        exh_axis, axis_before, before_maps,
        axis_after, {name: tune.values(name) for name in before_maps},
    )

    after_resample = tune.values("wastegate_feedforward_vvl0")
    for (row, col), delta in WG_DELTAS_R19.items():
        cap = WG_STOCK_CAP_R19[(row, col)]
        stock_here = float(np.interp(
            axis_after[row], _STOCK_WASTEGATE_AXIS, _STOCK_WASTEGATE[:, col]
        ))
        _require_close(
            f"`IP_FAC_BPA_SP[0]` — Map for boost pressure actuator setpoint "
            f"cell ({row}, {col}): declared stock cap",
            cap,
            stock_here,
            atol=5e-4,
        )
        if after_resample[row, col] + delta > cap + 5e-4:
            raise RuntimeError(
                f"`IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure actuator "
                f"setpoint cell ({row}, {col}): "
                f"{after_resample[row, col]:.3f} {delta:+.3f} = "
                f"{after_resample[row, col] + delta:.3f} would be more closed "
                f"than the factory value {cap:.3f} at intake "
                f"{axis_after[row]:.3f}"
            )

    tune.wastegate.overlay(
        WG_DELTAS_R19,
        intent="close two feedforward cells back toward stock to cover the "
               "4.3-7.3 kPa boost shortfall from 5000 rpm up that leaves the "
               "closed loop carrying 8.6-12.1 % integral; deltas solved from "
               "2537 pooled 3rd-gear WOT samples across both R18 sessions on "
               "the re-breakpointed geometry and bounded at the factory value, "
               "with the fuel-limited 4500-5000 rpm band and the "
               "already-over-target 6000-6500 rpm band held. The boost "
               "setpoint is unchanged",
    )


def _bilinear(grid: np.ndarray, x_axis, y_axis, x: float, y: float) -> float:
    """The ECU's own feedforward lookup, unrolled — validated against the logs.

    Replaying this against `WG Pos Base (%)` over the R18 sessions reproduces
    the logged feedforward to 0.066 points RMS, which is what licenses using it
    to assert that a re-breakpoint changed nothing.
    """
    xi = float(np.clip(np.interp(x, x_axis, np.arange(len(x_axis))),
                       0, len(x_axis) - 1))
    yi = float(np.clip(np.interp(y, y_axis, np.arange(len(y_axis))),
                       0, len(y_axis) - 1))
    x0, y0 = int(np.floor(xi)), int(np.floor(yi))
    x1, y1 = min(x0 + 1, len(x_axis) - 1), min(y0 + 1, len(y_axis) - 1)
    fx, fy = xi - x0, yi - y0
    return (grid[y0, x0] * (1 - fx) * (1 - fy) + grid[y0, x1] * fx * (1 - fy)
            + grid[y1, x0] * (1 - fx) * fy + grid[y1, x1] * fx * fy)


def _assert_feedforward_unchanged(
    exh_axis, axis_before, before_maps, axis_after, after_maps
) -> None:
    """Refuse to continue unless the re-breakpoint moved no commanded position.

    Checked over the actual logged operating points rather than a grid sweep: a
    re-breakpoint that is harmless on paper but moves the surface somewhere the
    engine really runs is the failure this exists to catch.
    """
    points = _logged_operating_points()
    worst, worst_at = 0.0, None
    for name in before_maps:
        for exh, intake in points:
            was = _bilinear(before_maps[name], exh_axis, axis_before, exh, intake)
            now = _bilinear(after_maps[name], exh_axis, axis_after, exh, intake)
            if abs(now - was) > worst:
                worst, worst_at = abs(now - was), (name, exh, intake)
    if worst > WG_REBREAKPOINT_TOLERANCE:
        name, exh, intake = worst_at
        raise RuntimeError(
            f"the intake-axis re-breakpoint changed the commanded wastegate "
            f"position by {worst * 100:.4f} points at {name} exhaust "
            f"{exh:.3f} / intake {intake:.3f}, above the "
            f"{WG_REBREAKPOINT_TOLERANCE * 100:.4f}-point tolerance. The "
            f"resample is wrong; refusing to build."
        )
    print(f"Intake-axis re-breakpoint verified a no-op over "
          f"{len(points)} logged operating points: worst commanded-position "
          f"change {worst * 100:.6f} points")


def _logged_operating_points() -> tuple[tuple[float, float], ...]:
    """Every 3rd-gear WOT (exhaust, intake) flow-factor pair from the R18 logs."""
    points = []
    for path in sorted(R18_LOG_DIR.glob("simostools-*.csv")):
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    if (float(row["Pedal Pos (%)"]) < 90
                            or float(row["Gear (gear)"]) != 3
                            or float(row["Engine Speed (rpm)"]) < 3000):
                        continue
                    points.append((float(row["Exh Flow Factor ()"]),
                                   float(row["Intake Flow Fact ()"])))
                except (KeyError, TypeError, ValueError):
                    continue
    if len(points) < 2000:
        raise RuntimeError(
            f"only {len(points)} logged WOT operating points found under "
            f"{R18_LOG_DIR}; the re-breakpoint no-op check needs the R18 logs"
        )
    return tuple(points)



def _validated_offsets(slot: int, declared) -> np.ndarray:
    """Check one slot's declared offsets before anything is written.

    Shape, finiteness, sign, and storage-lattice representability. The domain
    method re-checks representability against the live table; this catches a bad
    constant at the point where the error message can still name the revision's
    own declaration rather than a cell index.
    """
    label = f"`Spark modifier` — map slot {slot} ignition offset"
    offsets = np.asarray(declared, dtype=np.float64)
    if offsets.shape != (len(SPARK_MODIFIER_RPM),):
        raise RuntimeError(
            f"{label}: {offsets.size} offsets for {len(SPARK_MODIFIER_RPM)} rpm "
            "breakpoints; there must be exactly one each, in order"
        )
    if not np.all(np.isfinite(offsets)):
        raise RuntimeError(f"{label}: a declared offset is not finite")
    # Advance only. A sign slip here would retard an octane slot relative to the
    # control while every document about this revision says the opposite.
    if not np.all(offsets > 0.0):
        raise RuntimeError(
            f"{label}: every offset must advance; R22 does not retard either "
            "octane slot anywhere"
        )
    steps = offsets / SPARK_ENCODING_STEP_DEG
    if not np.allclose(steps, np.round(steps), rtol=0.0, atol=1e-9):
        raise RuntimeError(
            f"{label}: a declared offset is not a whole multiple of the "
            f"{SPARK_ENCODING_STEP_DEG:.3f}°CRK storage step, so the value "
            "written back is not the value declared"
        )
    return offsets


def _apply_r22_slot_timing(tune: Tune) -> dict[int, np.ndarray]:
    """Write both octane slots' `Spark modifier` grids and prove what landed.

    Returns each octane slot's delivered-timing row (base + modifier) at the top
    airmass breakpoint, so `main` can print the numbers a human reviews rather
    than the offsets, which are not by themselves the thing that can hurt the
    engine.

    The domain method carries the guards that make each write safe — exact
    breakpoints, storage-lattice representability, the top-row flatness rule, and
    the delivered-timing ceiling read off the live base map. What is added here
    is revision-level, and it is mostly about the *relationship* between the two
    slots, which no single-slot check can see:

    * slot 4 restores R20's timing **exactly**, so the reduced-boost slot changes
      one thing against the calibration that is in the car, not two;
    * slot 5 keeps R21's shape, differing from slot 4 in exactly the columns R21
      cut and never upward;
    * both slots start at the patch's neutral, and slots 1-3 and all nine shared
      base ignition maps are untouched afterwards. That last one is the
      invariant the whole revision rests on: if the base maps moved, the control
      moved with them and R22 is not an A/B against anything.
    """
    declared = {
        MID_BOOSTER_SLOT: _validated_offsets(
            MID_BOOSTER_SLOT, MID_SPARK_MODIFIER_DEG
        ),
        BOOSTER_SLOT: _validated_offsets(BOOSTER_SLOT, SPARK_MODIFIER_DEG),
    }
    mid = declared[MID_BOOSTER_SLOT]
    top = declared[BOOSTER_SLOT]

    _require_close(
        f"`Spark modifier` — map slot {MID_BOOSTER_SLOT} ignition offset: the "
        "reduced-boost slot must carry R20's timing exactly",
        mid,
        R20_SPARK_MODIFIER_DEG,
        atol=1e-9,
    )
    moved = tuple(int(i) for i in np.flatnonzero(~np.isclose(top, mid)))
    if moved != tuple(CHANGED_COLUMNS):
        raise RuntimeError(
            f"`Spark modifier`: slots {MID_BOOSTER_SLOT} and {BOOSTER_SLOT} "
            f"differ in rpm columns {[SPARK_MODIFIER_RPM[i] for i in moved]}, "
            f"but the revision declares "
            f"{[SPARK_MODIFIER_RPM[i] for i in CHANGED_COLUMNS]}"
        )
    if not np.all(top <= mid + 1e-9):
        raise RuntimeError(
            f"`Spark modifier`: slot {BOOSTER_SLOT} is the reduced-timing slot; "
            f"it must not exceed slot {MID_BOOSTER_SLOT} in any column"
        )

    # The grids reuse the base ignition maps' own axis tables, so their
    # breakpoints must be exactly the ones the timing constants are written on.
    for slot in OCTANE_SLOTS:
        _require_close(
            f"`Spark modifier` — map slot {slot} ignition offset: engine-speed axis",
            tune.axis(f"slot{slot}_spark_modifier", "x", space=PATCH_SPACE)[8:],
            SPARK_MODIFIER_RPM,
            atol=1e-6,
        )
        _require_close(
            f"`Spark modifier` — map slot {slot} ignition offset: airmass axis",
            tune.axis(f"slot{slot}_spark_modifier", "y", space=PATCH_SPACE)[14:],
            SPARK_MODIFIER_ROWS_MG,
            atol=1.01,
        )

    base_before = {name: tune.values(name) for name in BASE_IGNITION_TABLES}
    others_before = {
        slot: tune.values(f"slot{slot}_spark_modifier", space=PATCH_SPACE)
        for slot in (1, 2, CONTROL_SLOT)
    }

    intents = {
        MID_BOOSTER_SLOT:
            "give slot 4 R20's uncut ignition offset on the intermediate "
            "~24.4 psi boost curve: R20's 4500-5000 rpm knock (27.5 events per "
            "loaded minute against slot 4's 4.2, p ~ 0.0006, both -2.25 °CRK "
            "cuts) came at 1505 mg/stk while the larger +3.750 apex logged zero "
            "at 1423, so this slot holds the indicted timing and removes ~1.6 psi "
            "of cylinder filling instead — the reduced-boost half of the trade "
            "slot 5 tests from the other side",
        BOOSTER_SLOT:
            "carry R21's cut ignition offset forward unchanged on the full "
            "~26 psi boost curve: the 4000 and 4500 rpm columns stay at +1.500 "
            "°CRK, the +3.750 apex at 5000 rpm is held because it logged zero "
            "events, and 5500-6500 is held — the reduced-timing half of the "
            "trade, measured against slot 4's reduced-boost half and slot 3's "
            "no-modifier control in the same session",
    }
    for slot in OCTANE_SLOTS:
        tune.switchpatch.slot_spark_map(
            slot,
            rpm=SPARK_MODIFIER_RPM,
            rows={airmass: tuple(declared[slot])
                  for airmass in SPARK_MODIFIER_ROWS_MG},
            max_delivered_degrees=MAX_DELIVERED_DEG,
            base_map=BASE_IGNITION_TABLES[0],
            require_as_patched=True,
            intent=intents[slot],
        )

    delivered_by_slot: dict[int, np.ndarray] = {}
    for slot in OCTANE_SLOTS:
        offsets = declared[slot]
        staged = tune.values(f"slot{slot}_spark_modifier", space=PATCH_SPACE)
        written = ~np.isclose(staged, 0.0, atol=1e-6)
        if int(written.sum()) != 2 * len(SPARK_MODIFIER_RPM):
            raise RuntimeError(
                f"`Spark modifier` — map slot {slot} ignition offset: "
                f"{int(written.sum())} cells are non-neutral, not the declared "
                f"{2 * len(SPARK_MODIFIER_RPM)}"
            )
        for row in (14, 15):
            _require_close(
                f"`Spark modifier` — map slot {slot} ignition offset: staged "
                f"{SPARK_MODIFIER_ROWS_MG[row - 14]:g} mg/stk row",
                staged[row][8:],
                offsets,
                atol=1e-6,
            )
        delivered = base_before[BASE_IGNITION_TABLES[0]][15][8:] + offsets
        if float(delivered.max()) > MAX_DELIVERED_DEG + 1e-9:
            raise RuntimeError(
                f"slot {slot} delivers {delivered.max():+.3f}°CRK, above the "
                f"declared {MAX_DELIVERED_DEG:+.2f}°CRK ceiling"
            )
        delivered_by_slot[slot] = delivered

    for name, before in base_before.items():
        if not np.array_equal(before, tune.values(name)):
            raise RuntimeError(
                f"{tune.table(name).label} changed while writing the octane "
                "slots' `Spark modifier` grids; the shared base ignition maps "
                f"must be byte-identical to R20 or slot {CONTROL_SLOT} is not a "
                "control"
            )
    for slot, before in others_before.items():
        after = tune.values(f"slot{slot}_spark_modifier", space=PATCH_SPACE)
        if not np.array_equal(before, after):
            raise RuntimeError(
                f"`Spark modifier` — map slot {slot} ignition offset changed "
                "while writing the octane slots' grids; slots 1-3 must not move "
                "here. Slot 3 gets its own offset later, from "
                "`_apply_r23_everyday_timing`, and slots 1 and 2 stay at the "
                "patch's neutral 0.00° for good"
            )

    return delivered_by_slot


def _apply_r23_everyday_timing(tune: Tune) -> np.ndarray:
    """Give the everyday pump-92 slot its +0.750 °CRK at 3500 and 4000 rpm.

    The one ignition change in R23, and the narrowest one this lineage has made:
    two rpm columns, two airmass rows, four cells. It goes on slot 3's own
    `Spark modifier` — map slot ignition offset grid rather than into the shared
    base ignition maps, so slots 1, 2, 4 and 5 keep exactly the timing R22
    flashed and the addition is attributable to one map.

    Returns the delivered timing row (base + modifier) at 1400 mg/stk across the
    grid's eight written rpm breakpoints, for the report.
    """
    offsets = np.asarray(R23_SPARK_DEG, dtype=np.float64)
    if offsets.shape != (len(R23_SPARK_RPM),):
        raise RuntimeError(
            "`Spark modifier` — map slot 3 ignition offset: "
            f"{offsets.size} offsets for {len(R23_SPARK_RPM)} rpm breakpoints"
        )
    if not np.all(np.isfinite(offsets)) or not np.all(offsets > 0.0):
        raise RuntimeError(
            "`Spark modifier` — map slot 3 ignition offset: every offset must "
            "be finite and must advance; R23 does not retard the everyday slot"
        )
    steps = offsets / SPARK_ENCODING_STEP_DEG
    if not np.allclose(steps, np.round(steps), rtol=0.0, atol=1e-9):
        raise RuntimeError(
            "`Spark modifier` — map slot 3 ignition offset: a declared offset "
            f"is not a whole multiple of the {SPARK_ENCODING_STEP_DEG:.3f}°CRK "
            "storage step, so the value written back is not the value declared"
        )

    # The columns must be breakpoints of the grid's own rpm axis, and the two
    # rows must be the top two of its airmass axis — the same axes the base
    # ignition maps use, asserted rather than assumed.
    for index, rpm in enumerate(R23_SPARK_RPM):
        if rpm not in SPARK_MODIFIER_RPM:
            raise RuntimeError(
                f"`Spark modifier` — map slot {EVERYDAY_SLOT} ignition offset: "
                f"{rpm} rpm is not one of the grid's written breakpoints "
                f"{SPARK_MODIFIER_RPM}"
            )
        del index
    _require_close(
        f"`Spark modifier` — map slot {EVERYDAY_SLOT} ignition offset: "
        "engine-speed axis",
        tune.axis(f"slot{EVERYDAY_SLOT}_spark_modifier", "x",
                  space=PATCH_SPACE)[8:],
        SPARK_MODIFIER_RPM,
        atol=1e-6,
    )
    _require_close(
        f"`Spark modifier` — map slot {EVERYDAY_SLOT} ignition offset: "
        "airmass axis",
        tune.axis(f"slot{EVERYDAY_SLOT}_spark_modifier", "y",
                  space=PATCH_SPACE)[14:],
        SPARK_MODIFIER_ROWS_MG,
        atol=1.01,
    )

    base_before = {name: tune.values(name) for name in BASE_IGNITION_TABLES}
    others_before = {
        slot: tune.values(f"slot{slot}_spark_modifier", space=PATCH_SPACE)
        for slot in SLOT_CURVES if slot != EVERYDAY_SLOT
    }

    tune.switchpatch.slot_spark_map(
        EVERYDAY_SLOT,
        rpm=R23_SPARK_RPM,
        rows={airmass: tuple(offsets) for airmass in SPARK_MODIFIER_ROWS_MG},
        max_delivered_degrees=MAX_DELIVERED_DEG,
        base_map=BASE_IGNITION_TABLES[0],
        require_as_patched=True,
        intent=(
            f"advance the everyday pump-92 slot by +{offsets[0]:.3f} °CRK at "
            f"{', '.join(str(r) for r in R23_SPARK_RPM)} rpm on the two loaded "
            "airmass rows: 3500-4000 rpm logged zero knock events over 40.7 "
            "loaded seconds and 4000-4500 one over 49.7 s across 51 pump-92 "
            "logs on this exact boost curve, while EQT Stage 2 runs 3.75-5.63 "
            "°CRK more timing in the same cells. Two encoding steps into the "
            "one band this curve has never knocked in; the two bands that do "
            "knock get nothing"
        ),
    )

    staged = tune.values(f"slot{EVERYDAY_SLOT}_spark_modifier", space=PATCH_SPACE)
    written = ~np.isclose(staged, 0.0, atol=1e-6)
    expected_cells = len(SPARK_MODIFIER_ROWS_MG) * len(R23_SPARK_RPM)
    if int(written.sum()) != expected_cells:
        raise RuntimeError(
            f"`Spark modifier` — map slot {EVERYDAY_SLOT} ignition offset: "
            f"{int(written.sum())} cells are non-neutral, not the declared "
            f"{expected_cells}. R23 writes two rpm columns and nothing else"
        )
    columns = [SPARK_MODIFIER_RPM.index(rpm) + 8 for rpm in R23_SPARK_RPM]
    for row in (14, 15):
        _require_close(
            f"`Spark modifier` — map slot {EVERYDAY_SLOT} ignition offset: "
            f"staged {SPARK_MODIFIER_ROWS_MG[row - 14]:g} mg/stk row",
            staged[row][columns], offsets, atol=1e-6,
        )

    for name, before in base_before.items():
        if not np.array_equal(before, tune.values(name)):
            raise RuntimeError(
                f"{tune.table(name).label} changed while writing slot "
                f"{EVERYDAY_SLOT}'s `Spark modifier` grid; the shared base "
                "ignition maps must be byte-identical to R22 or every other "
                "slot's timing moved too"
            )
    for slot, before in others_before.items():
        after = tune.values(f"slot{slot}_spark_modifier", space=PATCH_SPACE)
        if not np.array_equal(before, after):
            raise RuntimeError(
                f"`Spark modifier` — map slot {slot} ignition offset changed "
                f"while writing slot {EVERYDAY_SLOT}'s grid"
            )

    delivered = base_before[BASE_IGNITION_TABLES[0]][15][8:].copy()
    for column, offset in zip(columns, offsets):
        delivered[column - 8] += offset
    return delivered


def _apply_r23_lambda_holds(tune: Tune) -> dict[int, np.ndarray]:
    """Hold slots 1 and 2 at their prior lambda while the base grid goes richer.

    The first use of the patch's `Lambda modifier` — map slot lambda offset
    grids in this lineage, and the routing is chosen for its failure mode. The
    enrichment itself is written into the shared base grid, which is a path this
    project has used since R00 and whose behaviour is logged; the modifier is
    used only to take it *back off* the two lowest-boost slots. Every way the
    modifier can be wrong is therefore a rich failure on a low-demand map, and
    the slot R23 is actually about — slot 3 — carries a neutral grid and is not
    exposed to the question at all.

    Returns each held slot's offset row, for the report.
    """
    holds: dict[int, np.ndarray] = {}
    rpm = tuple(sorted(LAMBDA_R23_ENRICHED))
    for slot in HOLD_LAMBDA_SLOTS:
        offsets = []
        for value in rpm:
            column = LAMBDA_RPM.index(int(value))
            enriched = _quantise_lambda(LAMBDA_CELLS[LAMBDA_LOADED_ROWS[-1]][column])
            prior = _quantise_lambda(LAMBDA_HOLD_TARGET[value])
            offset = prior - enriched
            steps = offset / LAMBDA_STEP
            if not np.isclose(steps, round(steps), rtol=0.0, atol=1e-9):
                raise RuntimeError(
                    f"`Lambda modifier` — map slot {slot} lambda offset: "
                    f"{offset:+.6f} at {value:g} rpm is not a whole multiple of "
                    f"the {LAMBDA_STEP:.7f} storage step"
                )
            if offset <= 0.0:
                raise RuntimeError(
                    f"`Lambda modifier` — map slot {slot} lambda offset: "
                    f"{offset:+.6f} at {value:g} rpm does not hold the slot "
                    "back. Every offset here must be positive — R23 uses this "
                    "grid only to undo an enrichment, never to add one, which "
                    "is what makes a wrong sign a rich failure rather than a "
                    "lean one"
                )
            offsets.append(offset)
        holds[slot] = np.asarray(offsets, dtype=np.float64)

    # The modifier grid shares the base lambda grid's axes, so a mismatch means
    # the two are not describing the same cells.
    for slot in HOLD_LAMBDA_SLOTS:
        _require_close(
            f"`Lambda modifier` — map slot {slot} lambda offset: engine-speed axis",
            tune.axis(f"slot{slot}_lambda_modifier", "x", space=PATCH_SPACE),
            LAMBDA_RPM, atol=1e-6,
        )
        _require_close(
            f"`Lambda modifier` — map slot {slot} lambda offset: load axis",
            tune.axis(f"slot{slot}_lambda_modifier", "y", space=PATCH_SPACE),
            LAMBDA_LOAD, atol=0.02,
        )

    untouched_before = {
        slot: tune.values(f"slot{slot}_lambda_modifier", space=PATCH_SPACE)
        for slot in SLOT_CURVES if slot not in HOLD_LAMBDA_SLOTS
    }
    for slot in HOLD_LAMBDA_SLOTS:
        tune.switchpatch.slot_lambda_map(
            slot,
            rpm=rpm,
            rows={LAMBDA_LOAD[row]: tuple(holds[slot])
                  for row in LAMBDA_LOADED_ROWS},
            delivered_lambda_range=DELIVERED_LAMBDA_RANGE,
            base_grid="lambda_basic_hpdi",
            require_as_patched=True,
            intent=(
                f"hold map slot {slot} at the lambda it ran under R22 while the "
                "shared base grid goes richer for slots 3, 4 and 5: slots 1 and "
                "2 are the bad-tank and conservative maps, and keeping their "
                "fuelling where it has been logged leaves an unenriched "
                "reference in the ladder. Positive offsets only, so a wrong "
                "sign on this never-yet-written grid makes these two slots "
                "richer rather than leaner"
            ),
        )

    for slot, before in untouched_before.items():
        after = tune.values(f"slot{slot}_lambda_modifier", space=PATCH_SPACE)
        if not np.array_equal(before, after):
            raise RuntimeError(
                f"`Lambda modifier` — map slot {slot} lambda offset moved while "
                f"holding slots {HOLD_LAMBDA_SLOTS} back. Slot {EVERYDAY_SLOT} "
                "in particular must stay neutral: it is the map this revision "
                "is about, and a neutral grid is what keeps it clear of the "
                "unresolved sign question"
            )
    return holds


def declare(tune: Tune) -> tuple[float, tuple[float, float],
                                 dict[int, np.ndarray], np.ndarray,
                                 dict[int, np.ndarray]]:
    """Declare the complete R23 calibration.

    Returns the Reference-IAT migration deviation, the peak and maximum boost
    separation between the two octane slots, each octane slot's delivered timing
    row at 1400 mg/stk, the everyday slot's delivered timing row, and the lambda
    offsets holding slots 1 and 2 back — the numbers a human reads before
    flashing.
    """
    peak_gap, max_gap = _check_slot_ladder()

    tune.fueling.rebreakpoint_lambda_axes(
        rpm=LAMBDA_RPM,
        load=LAMBDA_LOAD,
        intent="re-breakpoint lambda axes onto the loads the enrichment grid was authored for",
    )
    tune.fueling.lambda_grid(
        LAMBDA_CELLS,
        rpm_keys=LAMBDA_RPM,
        load_keys=LAMBDA_LOAD,
        intent="basic lambda enrichment map, R22's grid with R23's enrichment "
               "at 3008 and 5504-7008 rpm on the two loaded rows",
    )

    tune.apply_basics_sop()

    # `apply_basics_sop` writes `IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda
    # setpoint grid and its MPI twin from the guide's own literal table, so
    # R23's enrichment has to be laid over them *after* the SOP runs or the SOP
    # would quietly put the guide values back. `Fuel Split MPI` reads 0.000 at
    # WOT, so the HPDI grid is the one that actually fuels a pull — but all
    # three basic-lambda grids are written identically here, as every revision
    # since R00 has kept them.
    tune.fueling.lambda_grid(
        LAMBDA_CELLS,
        tables=("lambda_basic_hpdi", "lambda_basic_mpi"),
        rpm_keys=LAMBDA_RPM,
        load_keys=LAMBDA_LOAD,
        intent="enrich the operative WOT lambda grid: 3008 rpm to 0.930 for the "
               "worst knock band on this boost curve, and 5504-7008 rpm to "
               "0.780, EQT Stage 2's own top-end figure — both sized against "
               "logged HPFP effective volume, which is what stops this being "
               "EQT's 0.870 at 3008",
    )
    _apply_r19_knock(tune)
    reference_iat_deviation = _apply_r16_iat(tune)

    tune.fueling.pedal_threshold(
        PEDAL_THRESHOLD_PCT,
        intent="drop full-load pedal threshold to ~72% so heavy throttle reaches full-load fueling",
    )
    tune.boost.manifold_pressure_max(
        MANIFOLD_PRESSURE_MAX_HPA,
        intent="raise the requested-manifold-pressure ceiling clear of the tune",
    )
    tune.limits.intake_air_max(
        INTAKE_AIR_MAX_MG,
        intent="raise both maximum-intake-air-per-stroke tables to 2000 mg/stk",
    )
    tune.limits.torque_reference_max(
        TORQUE_REFERENCE_MAX_NM,
        intent="lift the reference-torque monitor ceiling above the tune's crank torque",
    )
    tune.limits.airmass_cap_mg(
        AIRMASS_CAP_MG,
        intent="raise the airmass-setpoint cap to 2000 mg/stk; the API stores kg/stk",
    )
    tune.fueling.lambda_floors(
        LAMBDA_FLOOR,
        intent="retain the log-validated 0.80 minimum-lambda floors for this bin",
    )

    _apply_r18_local_timing(tune)

    tune.wastegate.exh_flow_axis_last(
        EXH_FLOW_AXIS_TOP,
        intent="retain the exhaust-flow axis extension to 1.40 from logged flow coverage",
    )
    tune.wastegate.overlay(WG_DELTAS_R05, intent="retain the R05 overboost-ridge overlay")
    tune.wastegate.overlay(WG_DELTAS_R08, intent="retain the R08 top-end deepening")
    tune.wastegate.overlay(
        WG_DELTAS_R15,
        intent="retain the R15 bounded walk-back in the five R14 under-delivery cells",
    )
    _apply_r19_wastegate(tune)

    tune.boost.overboost_threshold(
        OVERBOOST_THRESHOLD_HPA,
        intent="retain the 2700 hPa P0234 pressure-difference threshold",
    )
    tune.boost.put_rpm_axis(
        PUT_RPM_AXIS,
        intent="retain the R09 pressure-up-throttle setpoint rpm axis",
    )
    tune.boost.put_ceiling_psi(
        BASE_CEILING_PSI,
        rounding="nearest",
        intent="park the non-binding base pressure-up-throttle ceiling above every slot",
    )
    tune.boost.pressure_quotient_max(
        PQ_PLATEAU,
        low_rpm=PQ_LOW_RPM,
        intent="retain the 1.70 low-rpm and 3.1 plateau compressor-ratio cap",
    )

    tune.switchpatch.slot_rpm_axis(
        SLOT_RPM_AXIS,
        intent="retain the shared switch-patch slot rpm axis on its 12-point grid",
    )
    for slot, curve in SLOT_CURVES.items():
        tune.switchpatch.slot_curve(
            slot,
            hpa=curve,
            require_as_patched=True,
            intent=SLOT_CURVE_INTENTS[slot],
        )
    delivered_by_slot = _apply_r22_slot_timing(tune)
    everyday_delivered = _apply_r23_everyday_timing(tune)
    lambda_holds = _apply_r23_lambda_holds(tune)
    tune.switchpatch.traction_control(
        intent="retain switch-patch traction control on all slots with factory TC disabled",
    )
    tune.switchpatch.require_sanity(stock_bin=BIN_PATH)
    return (reference_iat_deviation, (peak_gap, max_gap), delivered_by_slot,
            everyday_delivered, lambda_holds)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not R22_REFERENCE.is_file():
        raise SystemExit(f"Missing the verified R22 reference bin: {R22_REFERENCE}")
    reference_hash = _sha256(R22_REFERENCE)
    if reference_hash != R22_REFERENCE_SHA256:
        raise SystemExit(
            f"R22 reference hash mismatch: {reference_hash}; "
            f"expected {R22_REFERENCE_SHA256}"
        )
    stock_hash_before = _sha256(BIN_PATH)

    tune = Tune.open(
        SC8S50,
        xdf=XDF_PATH,
        bin=BIN_PATH,
        patches=PATCHES,
        extra_spaces={PATCH_SPACE: (SWITCH_PATCH_2933, SWITCH_XDF)},
    )
    (reference_iat_deviation, (peak_gap, max_gap), delivered_by_slot,
     everyday_delivered, lambda_holds) = declare(tune)

    result = build(
        tune,
        "R23",
        out_root=OUT_ROOT,
        bin_name=OUT_BIN_NAME,
        reference_bin=R22_REFERENCE,
        title="TUNE_MainTune_R23 — optimise the pump-92 aggressive slot: enrich "
              "the knock band as far as the fuel pump allows, and add timing "
              "where this curve has never knocked",
        summary=SUMMARY,
    )

    if _sha256(BIN_PATH) != stock_hash_before:
        raise RuntimeError(f"Untouched recovery image changed unexpectedly: {BIN_PATH}")

    print(f"R23 saved  : {result.bin_path}")
    print(f"R23 report : {result.report_path}")
    print(f"R23 journal: {len(result.journal)} entries; "
          f"{len(result.journal.tables_touched())} tables touched")
    print(f"R23 audit  : {result.diff.summary()}")
    print(f"R23 Reference IGA migration max deviation: "
          f"{reference_iat_deviation:.6f}°CRK")
    print("R23 slot ladder (boost cap peak, absolute hPa / psi gauge) — "
          "unchanged from R22:")
    for slot, curve in SLOT_CURVES.items():
        peak = float(np.max(curve))
        print(f"  slot {slot}: {peak:7.0f} hPa  {(peak - 1013.25) / 68.9476:5.2f} psi"
              f"  — {SLOT_LABELS[slot]}")
    print(f"R23 octane slots separate by {peak_gap:.0f} hPa at peak, "
          f"{max_gap:.0f} hPa maximum ({max_gap / 68.9476:.2f} psi)")

    enriched = tuple(sorted(LAMBDA_R23_ENRICHED))
    print("R23 lambda, loaded rows (1200.01 / 1389.00 mg/stk):")
    print("  rpm       " + "".join(f"{v:>9.0f}" for v in enriched))
    for row in LAMBDA_LOADED_ROWS:
        before = [LAMBDA_CELLS_R22[row][LAMBDA_RPM.index(int(v))] for v in enriched]
        after = [LAMBDA_CELLS[row][LAMBDA_RPM.index(int(v))] for v in enriched]
        print(f"  {LAMBDA_LOAD[row]:>7.2f} R22" + "".join(f"{v:>9.3f}" for v in before))
        print(f"  {LAMBDA_LOAD[row]:>7.2f} R23" + "".join(f"{v:>9.3f}" for v in after))
    for slot, offsets in lambda_holds.items():
        print(f"  slot {slot} `Lambda modifier` hold (+ = held leaner, the "
              f"inferred sign): "
              + ", ".join(f"{rpm:g}:{off:+.4f}"
                          for rpm, off in zip(enriched, offsets)))
    print(f"  delivered lambda bounded to {DELIVERED_LAMBDA_RANGE} under both "
          f"sign conventions")

    for slot in OCTANE_SLOTS:
        print(f"R23 slot {slot} delivered timing at 1400 mg/stk (°CRK): "
              + ", ".join(f"{rpm:g}:{deg:+.3f}"
                          for rpm, deg in zip(SPARK_MODIFIER_RPM,
                                              delivered_by_slot[slot])))
    print(f"R23 slot {EVERYDAY_SLOT} delivered timing at 1400 mg/stk (°CRK): "
          + ", ".join(f"{rpm:g}:{deg:+.3f}"
                      for rpm, deg in zip(SPARK_MODIFIER_RPM,
                                          everyday_delivered)))
    print(f"R23 slot {EVERYDAY_SLOT} ignition offset: "
          + ", ".join(f"{rpm:g}:{deg:+.3f}"
                      for rpm, deg in zip(R23_SPARK_RPM, R23_SPARK_DEG))
          + " °CRK, and neutral in every other cell")

    print(
        f"\nReview the R22-to-R23 comparison plots before any human-performed "
        f"CAL flash. Exactly six tables may differ from R22: the three basic "
        f"lambda setpoint grids (`IP_LAMB_BAS[1]`, `IP_LAMB_BAS_HPDI[1]` and "
        f"`IP_LAMB_BAS_MPI[1]`), the two `Lambda modifier` — map slot lambda "
        f"offset grids for slots {' and '.join(str(s) for s in HOLD_LAMBDA_SLOTS)}, "
        f"and the `Spark modifier` — map slot ignition offset for slot "
        f"{EVERYDAY_SLOT}.\n"
        f"\nALL FIVE `PUT setpoint` — map slot boost caps must show NO CHANGE "
        f"AT ALL, and so must the nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` "
        f"— Basic ignition angle maps, the knock fast-loop tables, the wastegate "
        f"feedforward, and slots {MID_BOOSTER_SLOT} and {BOOSTER_SLOT}'s "
        f"`Spark modifier` grids. R23 changes fuelling and one slot's timing; "
        f"anything else in the diff is a bug.\n"
        f"\nSlots {MID_BOOSTER_SLOT} and {BOOSTER_SLOT} remain calibrated for "
        f"pump 92 AKI dosed with VP Octanium Unleaded at 10-11 oz per 10 US "
        f"gallons and will knock on an undosed tank. Slot {CONTROL_SLOT} is the "
        f"everyday map and the in-drive fallback.\n"
        f"\nSee Tunes/REV_LOG.md § R23 for the logging gate. The first pull on "
        f"this bin settles a question no log has ever answered: read `Lambda SP` "
        f"on slots 1 or 2 at 3000-3500 rpm loaded WOT against slot "
        f"{EVERYDAY_SLOT}'s. If they differ, the `Lambda modifier` grid works "
        f"and its sign is the one assumed here; if they read the same, the grid "
        f"is inert and all five slots are running the enrichment. Both outcomes "
        f"are safe and both are worth knowing.\n"
        f"\nThis script never flashes."
    )


if __name__ == "__main__":
    main()
