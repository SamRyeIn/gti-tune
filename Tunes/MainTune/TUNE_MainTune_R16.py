#!/usr/bin/env python3
"""MainTune R16 — exact Spark IAT correction and EQT-matched high-RPM timing.

R16 is the first MainTune revision. It inherits the complete R15 calibration
and patch set, then changes only:

* `ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA versus
  N_32, TIA: shared intake-air-temperature axis;
* `IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
  N_32, TIA: the tuning-guide author's exact 10 × 10 grid;
* `IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of Reference IGA
  versus N_32, TIA: resampled onto the shared axis to preserve its prior curve;
* twelve cells in each of the nine
  `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
  port-flap-low cam-position maps: the EQT Stage 2 log's encoded table-output
  curve from 5000 rpm upward across 1050/1200/1400 mg/stk.

The EQT target comes from `References/20220522_EQTS2_3Gear1.csv` and matches its
`Ignition Table Output` channel, not its correction-dependent final timing.
Knock detection, boost, wastegate, fueling, limiters, and switch slots remain
identical to R15. This script builds a human-review candidate and never flashes
an ECU.

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
"""

from __future__ import annotations

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
from simoscal.tune.journal import KIND_AXIS


REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = REPO_ROOT / "Code"
BINTOOLZ = REPO_ROOT / "BinToolz-main"

XDF_PATH = CODE_ROOT / "xdf" / "SC8S50.V1.0.xdf"
BIN_PATH = CODE_ROOT / "bin" / "5G0906259L__0002.bin"
SWITCH_XDF = BINTOOLZ / "definitions" / "S50 Switch Patch.29.33.V2.xdf"
OUT_ROOT = Path(__file__).resolve().parent / "MainTune_out"
OUT_BIN_NAME = "Patched_259L_R16.bin"

R15_REFERENCE = (
    REPO_ROOT / "Tunes" / "TuningBasicsGuide" / "TUNE_Basics_Guide_out"
    / "R15_20260810-212341"
    / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R15.bin"
)
R15_REFERENCE_SHA256 = (
    "02f09df6fbe4ef057f47a05a5b52656ca8bdbbfdd587c9e24f0de25d7073207a"
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


# Fueling — guide grid and the axes on which it was authored.
LAMBDA_RPM = (
    1504, 2016, 2496, 3008, 3488, 4000,
    4512, 4992, 5504, 5984, 6496, 7008,
)
LAMBDA_LOAD = (
    150.00, 299.99, 500.01, 700.00,
    899.99, 1100.01, 1200.01, 1389.00,
)
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


# Base timing — inherited R04 values, followed by R16's EQT table-output curve.
TIMING_R04 = {
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
EQT_TIMING_LOADS = (1049.97, 1200.0, 1400.0)
EQT_TABLE_OUTPUT_BY_RPM = {
    5000.0: 1.875,
    5500.0: 3.750,
    6000.0: 6.000,
    6500.0: 8.250,
}
TIMING_R16_SOURCE = {
    (5000.0, 1049.97): 1.125,
    (5000.0, 1200.0): -2.250,
    (5000.0, 1400.0): -2.250,
    (5500.0, 1049.97): 0.750,
    (5500.0, 1200.0): -0.750,
    (5500.0, 1400.0): 0.000,
    (6000.0, 1049.97): 1.875,
    (6000.0, 1200.0): 1.875,
    (6000.0, 1400.0): 1.875,
    (6500.0, 1049.97): 3.375,
    (6500.0, 1200.0): 3.375,
    (6500.0, 1400.0): 3.375,
}
TIMING_R16_TARGETS = {
    (rpm, load): target
    for rpm, target in EQT_TABLE_OUTPUT_BY_RPM.items()
    for load in EQT_TIMING_LOADS
}
BASE_IGNITION_TABLES = tuple(
    f"ignition_base_vvl0_i{intake}_e{exhaust}"
    for intake in range(3)
    for exhaust in range(3)
)


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


# Boost, limiters, and switch-patch slots — inherited unchanged from R15.
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
VALET_SLOT, VALET_CAP_PSI = 5, 10.0


def _stock_full_load_curve(rpm_axis: tuple[float, ...]) -> np.ndarray:
    """Read and resample the factory full-load boost target from the stock bin."""
    cal = CalFile.open(
        str(XDF_PATH), str(BIN_PATH), structure=structure_of(BIN_PATH)
    )
    put = cal.get("IP_PUT_SP")
    stock_rpm = np.asarray(put.axis_values("x"), dtype=np.float64).ravel()
    stock_curve = np.asarray(put.values, dtype=np.float64)[-1, :]
    return np.interp(rpm_axis, stock_rpm, stock_curve)


SLOT_CURVES = {
    1: _stock_full_load_curve(SLOT_RPM_AXIS),
    2: SLOT_CONSERVATIVE,
    3: SLOT_INTERMEDIATE,
    4: SLOT_AGGRESSIVE,
}
SLOT_LABELS = {
    1: "stock — factory `IP_PUT_SP` — Pressure up throttle setpoint (~21.6 psi)",
    2: "conservative (~24.5 psi)",
    3: "intermediate (~24.5 psi, held)",
    4: "aggressive (~26 psi) — the former R09/R10 shelf",
}


SUMMARY = """\
R16 installs the tuning-guide author's exact Spark IAT calibration in
`IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
N_32, TIA, including the 35.25 °C breakpoint in the shared
`ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA versus N_32,
TIA axis. `IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of
Reference IGA versus N_32, TIA is resampled onto that new axis; its dense
physical curve stays within one 0.375°CRK encoding step of R15.

R16 also matches the EQT Stage 2 log's `Ignition Table Output` curve from 5000
rpm upward in the 1050, 1200, and 1400 mg/stk rows of all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps: 1.875° at 5000, 3.750° at 5500, 6.000° at
6000, and 8.250° at 6500 rpm. The encoded piecewise-linear curve fits all 132
logged EQT WOT samples from 5000–6336 rpm with 0.189° RMS error. Stock knock
detection remains untouched; final delivered timing will still reflect this
tune's IAT and other corrections.

Every boost, wastegate, fueling, limiter, slot, and patch declaration remains
identical to R15. This is a starting point for human review and logging, not a
finished calibration, and the script never flashes.
"""


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


def _timing_indices(tune: Tune, name: str) -> dict[tuple[float, float], tuple[int, int]]:
    rpm_axis = tune.axis(name, "x")
    load_axis = tune.axis(name, "y")
    if rpm_axis is None or load_axis is None:
        raise RuntimeError(f"{tune.table(name).label}: missing physical axes")
    indices = {}
    for rpm, load in TIMING_R16_TARGETS:
        column = int(np.argmin(np.abs(rpm_axis - rpm)))
        row = int(np.argmin(np.abs(load_axis - load)))
        if not np.isclose(rpm_axis[column], rpm, atol=1e-6):
            raise RuntimeError(f"{tune.table(name).label}: missing {rpm:g} rpm breakpoint")
        if not np.isclose(load_axis[row], load, atol=0.02):
            raise RuntimeError(f"{tune.table(name).label}: missing {load:g} mg/stk breakpoint")
        indices[(rpm, load)] = (row, column)
    return indices


def _apply_r16_high_rpm_timing(tune: Tune) -> None:
    """Guard R15 values, set the EQT table-output curve, and prove isolation."""
    snapshots = {name: tune.values(name) for name in BASE_IGNITION_TABLES}
    first = snapshots[BASE_IGNITION_TABLES[0]]
    for name, values in snapshots.items():
        if not np.array_equal(values, first):
            raise RuntimeError(
                f"{tune.table(name).label}: the nine R15 timing grids are not identical"
            )
        indices = _timing_indices(tune, name)
        for point, expected in TIMING_R16_SOURCE.items():
            row, column = indices[point]
            if not np.isclose(values[row, column], expected, atol=1e-8):
                raise RuntimeError(
                    f"{tune.table(name).label}: R15 source at {point[0]:g} rpm / "
                    f"{point[1]:g} mg/stk is {values[row, column]:.3f}°CRK, "
                    f"expected {expected:.3f}°CRK"
                )

    tune.ignition.retard_cells(
        TIMING_R16_TARGETS,
        intent="match `References/20220522_EQTS2_3Gear1.csv` Ignition Table "
               "Output from 5000 rpm upward across the 1050/1200/1400 mg/stk "
               "high-load rows; retain stock knock detection",
    )

    for name, before in snapshots.items():
        after = tune.values(name)
        indices = _timing_indices(tune, name)
        expected_mask = np.zeros(before.shape, dtype=bool)
        for point, target in TIMING_R16_TARGETS.items():
            row, column = indices[point]
            expected_mask[row, column] = True
            if not np.isclose(after[row, column], target, atol=1e-8):
                raise RuntimeError(
                    f"{tune.table(name).label}: staged target mismatch at "
                    f"{point[0]:g} rpm / {point[1]:g} mg/stk"
                )
        changed_mask = ~np.isclose(after, before, rtol=0.0, atol=1e-8)
        if not np.array_equal(changed_mask, expected_mask):
            unexpected = np.argwhere(changed_mask != expected_mask).tolist()
            raise RuntimeError(
                f"{tune.table(name).label}: cells outside the twelve-cell R16 mask "
                f"changed or a target did not change: {unexpected}"
            )

        rpm_axis = tune.axis(name, "x")
        load_axis = tune.axis(name, "y")
        column_4500 = int(np.argmin(np.abs(rpm_axis - 4500.0)))
        row_900 = int(np.argmin(np.abs(load_axis - 900.0)))
        if not np.array_equal(after[:, :column_4500 + 1], before[:, :column_4500 + 1]):
            raise RuntimeError(f"{tune.table(name).label}: timing below 5000 rpm moved")
        if not np.array_equal(after[:row_900 + 1, :], before[:row_900 + 1, :]):
            raise RuntimeError(f"{tune.table(name).label}: timing at or below 900 mg/stk moved")

    staged = [tune.values(name) for name in BASE_IGNITION_TABLES]
    if not all(np.array_equal(staged[0], values) for values in staged[1:]):
        raise RuntimeError(
            "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, "
            "VVL 0 port-flap-low cam-position maps diverged after the R16 write"
        )


def declare(tune: Tune) -> float:
    """Declare the complete R16 calibration and return Reference-IAT deviation."""
    tune.fueling.rebreakpoint_lambda_axes(
        rpm=LAMBDA_RPM,
        load=LAMBDA_LOAD,
        intent="re-breakpoint lambda axes onto the loads the enrichment grid was authored for",
    )
    tune.fueling.lambda_grid(
        LAMBDA_CELLS,
        rpm_keys=LAMBDA_RPM,
        load_keys=LAMBDA_LOAD,
        intent="basic lambda enrichment map from the tuning guide (0.80 under high load)",
    )

    tune.apply_basics_sop()
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

    tune.ignition.retard_cells(
        TIMING_R04,
        intent="retain the R04 timing pulls at measured knock pockets and their edge blends",
    )
    _apply_r16_high_rpm_timing(tune)

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
            intent=f"retain switch-patch slot {slot} boost curve ({SLOT_LABELS[slot]})",
        )
    tune.switchpatch.slot_curve(
        VALET_SLOT,
        psi=VALET_CAP_PSI,
        require_as_patched=True,
        intent=f"retain the valet-map ceiling at no more than {VALET_CAP_PSI:g} psi gauge",
    )
    tune.switchpatch.traction_control(
        intent="retain switch-patch traction control on all slots with factory TC disabled",
    )
    tune.switchpatch.require_sanity(stock_bin=BIN_PATH)
    return reference_iat_deviation


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    if not R15_REFERENCE.is_file():
        raise SystemExit(f"Missing the verified R15 reference bin: {R15_REFERENCE}")
    reference_hash = _sha256(R15_REFERENCE)
    if reference_hash != R15_REFERENCE_SHA256:
        raise SystemExit(
            f"R15 reference hash mismatch: {reference_hash}; "
            f"expected {R15_REFERENCE_SHA256}"
        )
    stock_hash_before = _sha256(BIN_PATH)

    tune = Tune.open(
        SC8S50,
        xdf=XDF_PATH,
        bin=BIN_PATH,
        patches=PATCHES,
        extra_spaces={PATCH_SPACE: (SWITCH_PATCH_2933, SWITCH_XDF)},
    )
    reference_iat_deviation = declare(tune)

    result = build(
        tune,
        "R16",
        out_root=OUT_ROOT,
        bin_name=OUT_BIN_NAME,
        reference_bin=R15_REFERENCE,
        title="TUNE_MainTune_R16 — exact Spark IAT correction and EQT-matched timing",
        summary=SUMMARY,
    )

    if _sha256(BIN_PATH) != stock_hash_before:
        raise RuntimeError(f"Untouched recovery image changed unexpectedly: {BIN_PATH}")

    print(f"R16 saved  : {result.bin_path}")
    print(f"R16 report : {result.report_path}")
    print(f"R16 journal: {len(result.journal)} entries; "
          f"{len(result.journal.tables_touched())} tables touched")
    print(f"R16 audit  : {result.diff.summary()}")
    print(f"R16 Reference IGA migration max deviation: "
          f"{reference_iat_deviation:.6f}°CRK")
    print(
        "\nReview `ldpm_tia_iga_cor_sel` — Basis for temperature correction of "
        "IGA versus N_32, TIA, both IGA temperature-correction grids, and all "
        "nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition "
        "angle, VVL 0 port-flap-low cam-position comparison plots before any "
        "human-performed CAL flash. This script never flashes."
    )


if __name__ == "__main__":
    main()
