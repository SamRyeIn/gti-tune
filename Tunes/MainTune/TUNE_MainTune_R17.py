#!/usr/bin/env python3
"""MainTune R17 — restore the guide's high-RPM base-timing values.

R17 inherits the complete R16 calibration and patch set. Relative to R16, it
changes eighteen cells in each of the nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps so every one of their 256 cells matches the
tuning basics guide exactly. Eleven cells remove R16's high-RPM EQT advance;
seven cells remove the older R04 knock-retard overlay. The exact R16 Spark-IAT
work and every other calibration area remain identical to R16. This script
builds a human-review candidate and never flashes an ECU.

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
OUT_BIN_NAME = "Patched_259L_R17.bin"

R16_REFERENCE = (
    REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
    / "R16_20260826-113234"
    / "Patched_259L_R16.bin"
)
R16_REFERENCE_SHA256 = (
    "061d878dee5d5229e9273b5e9ca7c5ad5e4706475639623f73c253bc0c2021bd"
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
R17 retains the tuning-guide author's exact Spark IAT calibration in
`IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
N_32, TIA, including the 35.25 °C breakpoint in the shared
`ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA versus N_32,
TIA axis. `IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of
Reference IGA versus N_32, TIA retains R16's curve-preserving resample.

R17 removes both R16's EQT Stage 2 `Ignition Table Output` match and R04's
knock-retard overlay from all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps. Every one of their 256 cells matches the guide
example's exact encoded values. Relative to R16, eleven cells per map are lower
and seven are higher; the higher cells deliberately remove the documented R04
3500–4500 rpm high-load protection. Stock knock detection remains untouched.

Every Spark-IAT, boost, wastegate, fueling, limiter, slot, and patch declaration
remains identical to R16. This is a starting point for human review and logging,
not a finished calibration, and the script never flashes.
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


def _apply_r17_guide_timing(tune: Tune) -> None:
    """Write the complete guide table and prove every staged cell."""
    guide = np.asarray(TIMING_GUIDE_CELLS, dtype=np.float64)
    if guide.shape != (16, 16) or not np.all(np.isfinite(guide)):
        raise RuntimeError(
            "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition "
            "angle, VVL 0 port-flap-low: guide table must be finite and 16 × 16"
        )

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
        TIMING_GUIDE_TARGETS,
        intent="replace the complete base-ignition grid with the tuning basics "
               "guide's exact encoded table; remove the R04 knock-retard overlay "
               "and R16 EQT high-RPM advance while retaining stock knock detection",
    )

    staged = []
    for name in BASE_IGNITION_TABLES:
        values = tune.values(name)
        _require_close(
            f"{tune.table(name).label}: staged complete guide table",
            values,
            guide,
            atol=1e-8,
        )
        staged.append(values)
    if not all(np.array_equal(staged[0], values) for values in staged[1:]):
        raise RuntimeError(
            "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, "
            "VVL 0 port-flap-low cam-position maps diverged after the R17 write"
        )

def declare(tune: Tune) -> float:
    """Declare the complete R17 calibration and return Reference-IAT deviation."""
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

    _apply_r17_guide_timing(tune)

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
    if not R16_REFERENCE.is_file():
        raise SystemExit(f"Missing the verified R16 reference bin: {R16_REFERENCE}")
    reference_hash = _sha256(R16_REFERENCE)
    if reference_hash != R16_REFERENCE_SHA256:
        raise SystemExit(
            f"R16 reference hash mismatch: {reference_hash}; "
            f"expected {R16_REFERENCE_SHA256}"
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
        "R17",
        out_root=OUT_ROOT,
        bin_name=OUT_BIN_NAME,
        reference_bin=R16_REFERENCE,
        title="TUNE_MainTune_R17 — restore complete guide base timing",
        summary=SUMMARY,
    )

    if _sha256(BIN_PATH) != stock_hash_before:
        raise RuntimeError(f"Untouched recovery image changed unexpectedly: {BIN_PATH}")

    print(f"R17 saved  : {result.bin_path}")
    print(f"R17 report : {result.report_path}")
    print(f"R17 journal: {len(result.journal)} entries; "
          f"{len(result.journal.tables_touched())} tables touched")
    print(f"R17 audit  : {result.diff.summary()}")
    print(f"R17 Reference IGA migration max deviation: "
          f"{reference_iat_deviation:.6f}°CRK")
    print(
        "\nReview all nine "
        "`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, "
        "VVL 0 port-flap-low cam-position R16-to-R17 comparison plots before "
        "any human-performed CAL flash. This script never flashes."
    )


if __name__ == "__main__":
    main()
