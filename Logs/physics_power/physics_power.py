"""
Physics-derived horsepower and torque from SimosTools datalogs — F = ma, not the
ECU's own estimate.

Every WOT pull in `Logs/BasicsGuide_R*/` is turned into a power and torque curve
from first principles: differentiate the *undriven* wheel speed to get true
ground acceleration, add the road-load forces the car has to overcome at that
speed, convert to power at the driven-tyre surface, then back out crank power
and torque. Nothing in this script reads `Calc HP`, `Calc TQ` or `Torque` except
to plot them alongside the derived curves for comparison.

The model
---------
Ground-frame force balance on the car::

    F_tractive = (m_car + m_wheel_eq) * a  +  F_road(v)

    F_road(v)  = A' + B*v + C*(rho/rho_ref)*v^2        (EPA coastdown road load)

`a` and `v` come from the mean of the two *rear* wheel-speed channels. The rears
are undriven, so they read true ground speed; the front (driven) pair — and
`Vehicle Speed`, which is the front pair — run 1-4 % fast under power because the
driven tyres slip. Using the fronts inflates acceleration during the boost ramp
(see `gear_consistency.png`).

Power at the driven-tyre *surface* uses the front wheel speed, so the difference
between the two is exactly the tyre-slip loss:

    P_ground = F_tractive * v_rear          (power delivered to the road)
    P_axle   = F_tractive * v_front         (P_ground + tyre slip loss)
    P_crank  = P_axle / eta_driveline  +  I_engine * omega_e * domega_e/dt
    T_crank  = P_crank / omega_e

The last term is the power spent spinning the crank, dual-mass flywheel, clutch
pack and gearbox input shafts up — it is taken straight from the logged engine
speed, so it needs no gear ratios and is automatically correct in every gear.

Where the numbers come from
---------------------------
* Road load `A`/`B`/`C`: EPA 2017 Test Car List, the *tested* 2017 VW GTI 1.984 L
  6-speed "automated manual" (= DSG), axle 3.44 — an actual measured track
  coastdown, not a guessed Cd. It rolls tyre rolling resistance, bearing drag and
  aerodynamic drag into one measured curve. Its `C` term implies CdA = 0.673 m^2,
  which agrees with Cd 0.31 x 2.17 m^2 for a Mk7 Golf.
* `A` is scaled by the mass ratio (rolling resistance is proportional to load);
  `C` is scaled by the air density actually logged at the time of the pull.
* `I_ENGINE_SIDE` is fitted from the data — see `gear_consistency.png` and the
  report. `M_WHEEL_EQ` is the four wheel/tyre/brake assemblies' rotational
  inertia expressed as an equivalent mass.

Usage:
    Code/.venv/bin/python Logs/physics_power/physics_power.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, asdict
from math import factorial
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Code"))

from simoscal.analysis.log import LogFile, load_logset  # noqa: E402
from simoscal.analysis.pulls import detect_pulls  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
PLOT_DIR = OUT_DIR / "plots"

# --------------------------------------------------------------------------- #
# Vehicle constants
# --------------------------------------------------------------------------- #
LB_TO_KG = 0.45359237
LBF_TO_N = 4.4482216
MPH_PER_MS = 2.2369363
W_PER_HP = 745.6999
NM_PER_LBFT = 1.3558179
G = 9.80665

#: Car + driver, as specified by Sam.
VEHICLE_MASS_LB = 3400.0
VEHICLE_MASS_KG = VEHICLE_MASS_LB * LB_TO_KG

#: EPA 2017 Test Car List, 2017 VW GTI 1.984 L, 6-speed automated manual (DSG),
#: axle ratio 3.44. Target coastdown coefficients, F[lbf] = A + B*v + C*v^2 with
#: v in mph. Equivalent test weight 3500 lb.
EPA_COAST_A_LBF = 34.463
EPA_COAST_B_LBF_PER_MPH = 0.19533
EPA_COAST_C_LBF_PER_MPH2 = 0.018508
EPA_TEST_WEIGHT_LB = 3500.0

#: Same coefficients in SI: F[N] = A + B*v + C*v^2 with v in m/s.
ROAD_A_N = EPA_COAST_A_LBF * LBF_TO_N
ROAD_B_N_PER_MS = EPA_COAST_B_LBF_PER_MPH * LBF_TO_N * MPH_PER_MS
ROAD_C_N_PER_MS2 = EPA_COAST_C_LBF_PER_MPH2 * LBF_TO_N * MPH_PER_MS**2

#: Reference air density the coastdown was corrected to (SAE J1263 / EPA: 20 degC,
#: 98.21 kPa dry). The C term is rescaled to the density logged during each pull.
RHO_REF = 1.16814
R_DRY_AIR = 287.05

#: Rotational inertia of the four wheel/tyre/brake/hub assemblies, expressed as
#: the equivalent extra mass the engine must accelerate: 4 * I_wheel / r^2, with
#: I_wheel ~ 1.25 kg m^2 for a 225/40R18 on a cast 18" wheel and r = 0.316 m
#: (the 0.632 m rolling diameter SimosTools is configured with). It is applied as
#: two halves — the undriven pair spins up at the ground rate, the driven pair at
#: its own rate, which differ by several percent under power and by 15 % when the
#: front tyres light up in 2nd gear.
M_WHEEL_EQ_KG = 50.0

#: Engine-side rotational inertia: crank assembly + dual-mass flywheel + the
#: DQ250's wet dual-clutch pack + gearbox input shafts, referred to crank speed.
#: Fitted from the 2nd-vs-3rd gear cross-check (see `gear_consistency.png`);
#: consistent with a hand estimate of 0.30-0.35 kg m^2 for this driveline.
I_ENGINE_SIDE = 0.35
I_ENGINE_SIDE_BAND = (0.20, 0.50)

#: Mechanical efficiency of gearbox + final drive under load. This is *only* the
#: geartrain: tyre rolling resistance and bearing drag are already in the
#: coastdown term, and inertia is accounted for separately, so this is well above
#: the "12-15 % drivetrain loss" figure quoted for chassis-dyno numbers (which
#: bundles all of those together).
ETA_DRIVELINE = 0.93
ETA_BAND = (0.90, 0.95)

# --------------------------------------------------------------------------- #
# Signal processing constants
# --------------------------------------------------------------------------- #
#: Savitzky-Golay differentiation window, specified as the *rpm span* it covers
#: rather than a time span, so a fast 2nd-gear pull and a slow 4th-gear pull get
#: the same amount of smoothing on the rpm axis and stay comparable.
RPM_SMOOTH_SPAN = 600.0
SG_ORDER = 2
SG_MIN_HALF, SG_MAX_HALF = 4, 30

#: The log's `Time` column is printed to ~0.25 s, but samples are evenly spaced.
#: A uniform grid is reconstructed and cross-checked against the coarse stamps.
TIME_GRID_TOLERANCE_S = 0.40

#: Pull-window trimming, on top of `simoscal.analysis.pulls.detect_pulls`.
PEDAL_MIN_PCT = 95.0
RPM_MIN = 3000.0

#: A pull only enters the aggregates if it actually sweeps the engine: anything
#: shorter is a partial squirt whose "peak" is just wherever the driver lifted.
FULL_PULL_RPM_SPAN = 1500.0
FULL_PULL_RPM_MAX = 5500.0

#: Acceleration noise a pull is allowed to carry, m/s^2. The speed channel's
#: quantisation step sets a noise floor on the fitted derivative; the R01 logging
#: profile records `Vehicle Speed` to 1 km/h, which on a short 2nd-gear pull is
#: far too coarse to differentiate. Such pulls are rejected, never quietly used.
ACCEL_NOISE_LIMIT = 0.12

#: Seconds trimmed off the end of every pull window. The DSG asks the engine for
#: a torque reduction before it shifts, so the last few tenths of a WOT pull are a
#: commanded cut, not the engine running out of breath — including them puts a
#: false cliff on the top of every curve.
PRESHIFT_TRIM_S = 0.40

#: Lateral acceleration above which a pull was taken in a bend rather than in a
#: straight line. Cornering bleeds tractive effort into tyre slip angle and shifts
#: load across the axle, so such a pull understates the engine.
CORNERING_FLAG_MS2 = 1.5

#: Steady-cruise mask used to read road grade off the longitudinal accelerometer.
#: It must be steady (no dv/dt to subtract), straight (no lateral load transfer)
#: and off-throttle-ish (no squat), because the accelerometer is body-mounted and
#: cannot tell road grade from body pitch.
CRUISE_ACCEL_MAX = 0.25
CRUISE_SPEED_MIN = 11.0
CRUISE_LAT_MAX = 0.40
CRUISE_PEDAL_MAX = 60.0
CRUISE_MIN_SAMPLES = 25

#: Above this driven-wheel slip the front tyres are spinning, not just deforming;
#: the pull is still derived but flagged, because grip — not the engine — is
#: setting the acceleration for part of it.
SLIP_FLAG_PCT = 8.0

#: Curves are resampled onto this rpm grid for averaging and comparison.
RPM_GRID = np.arange(3000.0, 6600.0, 50.0)

FOLDERS = [
    "BasicsGuide_R01", "BasicsGuide_R04", "BasicsGuide_R07",
    "BasicsGuide_R08", "BasicsGuide_R09", "BasicsGuide_R11", "BasicsGuide_R14",
]


# --------------------------------------------------------------------------- #
# Numerics
# --------------------------------------------------------------------------- #
def savgol(y: np.ndarray, dt: float, half: int, deriv: int = 0) -> np.ndarray:
    """Savitzky-Golay smooth (`deriv=0`) or derivative (`deriv=1`) of `y`.

    A local order-`SG_ORDER` polynomial is least-squares fitted over a window of
    `2*half+1` samples; the fitted polynomial's value or slope at the window
    centre is the output. Unbiased for a signal that is locally quadratic, which
    a WOT speed trace is over ~1 s.
    """
    x = np.arange(-half, half + 1) * dt
    coef = np.linalg.pinv(np.vander(x, SG_ORDER + 1, increasing=True))[deriv]
    coef = coef * factorial(deriv)
    padded = np.pad(y, half, mode="edge")
    return np.convolve(padded, coef[::-1], mode="valid")


def quantisation_step(y: np.ndarray) -> float:
    """Smallest non-zero step the channel ever takes — its recorded resolution."""
    steps = np.diff(np.unique(y[np.isfinite(y)]))
    steps = steps[steps > 0]
    return float(np.min(steps)) if steps.size else 0.0


def accel_noise_floor(v_raw: np.ndarray, dt: float, half: int) -> float:
    """Noise the fitted derivative inherits from the speed channel's resolution.

    A uniformly-quantised channel of step `q` has measurement noise `q/sqrt(12)`;
    a least-squares slope over `N = 2*half+1` evenly-spaced samples scales that by
    `sqrt(12 / (N(N^2-1))) / dt`. Gives m/s^2.
    """
    n = 2 * half + 1
    sigma_v = quantisation_step(v_raw) / np.sqrt(12.0)
    return float(sigma_v * np.sqrt(12.0 / (n * (n**2 - 1))) / dt)


def uniform_dt(lf: LogFile) -> tuple[float, float]:
    """Sample interval of a log, and the worst mismatch against its own stamps.

    SimosTools writes an evenly-sampled log but prints `Time` coarsely, so the
    raw per-row `diff` is useless for differentiation. The interval is recovered
    from the total span, and the reconstructed uniform grid is compared back
    against the printed stamps; the returned residual is the check.
    """
    t = lf.time
    n = lf.n_rows
    dt = (t[-1] - t[0]) / (n - 1)
    residual = float(np.max(np.abs(t - (t[0] + np.arange(n) * dt))))
    return dt, residual


# --------------------------------------------------------------------------- #
# The physics
# --------------------------------------------------------------------------- #
def cruise_grade_pct(lf: LogFile, dt: float, half: int) -> Optional[float]:
    """Road grade over this log, read off the ECU longitudinal accelerometer.

    `Accel. Long` is a real chassis sensor (an ECU RAM read of the ESP sensor
    cluster), so it measures `dv/dt + g*sin(grade) + g*sin(body pitch)`. Body
    pitch is the problem: the car squats under power by about the same amount a
    1 % grade would show, and with the same sign, so the residual *during* a WOT
    pull is not grade. Restricting to steady, straight, low-pedal cruise kills the
    pitch and the dv/dt term together and leaves the grade.

    An unknown sensor zero-offset rides along, so this is best read as a relative
    figure between pulls rather than an absolute grade.
    """
    if not (lf.has("accel_long") and lf.has("wheel_rl")):
        return None
    v = (lf.channel("wheel_rl") + lf.channel("wheel_rr")) / 2.0 / 3.6
    a = savgol(v, dt, half, deriv=1)
    residual = lf.channel("accel_long") - a
    mask = (np.abs(a) < CRUISE_ACCEL_MAX) & (v > CRUISE_SPEED_MIN)
    if lf.has("accel_lat"):
        mask &= np.abs(lf.channel("accel_lat")) < CRUISE_LAT_MAX
    if lf.has("pedal"):
        mask &= lf.channel("pedal") < CRUISE_PEDAL_MAX
    mask &= np.isfinite(residual)
    if mask.sum() < CRUISE_MIN_SAMPLES:
        return None
    return float(100.0 * np.sin(np.clip(residual[mask].mean() / G, -1.0, 1.0)))


def air_density(lf: LogFile) -> np.ndarray:
    """Ambient air density from the logged barometric pressure and temperature."""
    p_pa = lf.channel("ambient_press") * 1000.0
    t_k = lf.channel("ambient_temp") + 273.15
    return p_pa / (R_DRY_AIR * t_k)


def road_load_force(v: np.ndarray, rho: np.ndarray, mass_kg: float) -> dict:
    """EPA coastdown road load, split into its rolling and aerodynamic parts.

    The `A` term is rolling resistance and scales with vehicle load, so it is
    rescaled from the EPA test weight to this car's mass. The `C` term is
    aerodynamic and scales with the air density actually logged.
    """
    rolling = ROAD_A_N * (mass_kg / (EPA_TEST_WEIGHT_LB * LB_TO_KG)) + ROAD_B_N_PER_MS * v
    aero = ROAD_C_N_PER_MS2 * (rho / RHO_REF) * v**2
    return {"rolling": rolling, "aero": aero, "total": rolling + aero}


@dataclass
class PullCurve:
    """One WOT pull reduced to power and torque, plus the terms behind them."""

    revision: str
    file: str
    pull_index: int
    gear: Optional[int]
    n_samples: int
    duration_s: float
    dt_s: float
    sg_half: int
    speed_source: str           # "undriven" (rear pair) or "driven" (fallback)
    accel_noise: float          # m/s^2 the speed channel's resolution costs us
    ambient_c: float
    ambient_kpa: float
    rho: float
    t: np.ndarray               # s, zeroed at pull start
    rpm: np.ndarray
    v_kmh: np.ndarray
    accel: np.ndarray           # m/s^2, true ground acceleration
    slip_pct: np.ndarray        # driven vs undriven wheel speed
    lat_accel: Optional[np.ndarray]   # m/s^2, ECU lateral accelerometer
    grade_cruise_pct: Optional[float] # road grade read off the long. accelerometer
                                      # during steady cruise in the same log
    f_inertia: np.ndarray       # N, translational + wheel rotational
    f_rolling: np.ndarray       # N
    f_aero: np.ndarray          # N
    hp_ground: np.ndarray       # power delivered to the road
    hp_crank: np.ndarray
    tq_crank_nm: np.ndarray
    hp_ecu: Optional[np.ndarray]
    tq_ecu_nm: Optional[np.ndarray]

    @property
    def label(self) -> str:
        return f"{self.revision} #{self.pull_index} (gear {self.gear})"

    @property
    def full_pull(self) -> bool:
        """True if the pull actually sweeps the engine, so its peak means something."""
        return (self.rpm.max() - self.rpm.min() >= FULL_PULL_RPM_SPAN
                and self.rpm.max() >= FULL_PULL_RPM_MAX)

    @property
    def cornering(self) -> bool:
        """True if the pull was taken in a bend rather than in a straight line."""
        if self.lat_accel is None or not np.any(np.isfinite(self.lat_accel)):
            return False
        return bool(np.nanmax(np.abs(self.lat_accel)) > CORNERING_FLAG_MS2)

    @property
    def traction_limited(self) -> bool:
        """True if the driven tyres spun rather than merely deformed."""
        return bool(np.nanmax(self.slip_pct) > SLIP_FLAG_PCT) if np.any(
            np.isfinite(self.slip_pct)) else False


def derive_pull(
    lf: LogFile,
    revision: str,
    pull_index: int,
    gear: Optional[int],
    lo: int,
    hi: int,
    *,
    mass_kg: float = VEHICLE_MASS_KG,
    m_wheel_eq: float = M_WHEEL_EQ_KG,
    i_engine: float = I_ENGINE_SIDE,
    eta: float = ETA_DRIVELINE,
    grade_pct: float = 0.0,
) -> Optional[PullCurve]:
    """Reduce one detected pull window to power and torque curves.

    Derivatives are taken over the whole file and only then sliced to the pull,
    so the window never has to be padded at the pull's own edges.
    """
    dt, _ = uniform_dt(lf)
    ch = lf.channel
    rpm_all = ch("rpm")

    # True ground speed: the undriven (rear) pair. `Vehicle Speed` is the driven
    # pair and reads high under power, so it is only a fallback for old logs.
    if lf.has("wheel_rl") and lf.has("wheel_rr"):
        v_ground_raw = (ch("wheel_rl") + ch("wheel_rr")) / 2.0 / 3.6
        speed_source = "undriven"
    else:
        v_ground_raw = ch("vehicle_speed") / 3.6
        speed_source = "driven"
    if lf.has("wheel_fl") and lf.has("wheel_fr"):
        v_driven_raw = (ch("wheel_fl") + ch("wheel_fr")) / 2.0 / 3.6
    else:
        v_driven_raw = ch("vehicle_speed") / 3.6

    # Window sized in rpm, not seconds, so every gear is smoothed equally.
    span_s = max((hi - lo) * dt, 1e-6)
    rpm_rate = abs(rpm_all[hi] - rpm_all[lo]) / span_s
    half = int(np.clip(round(RPM_SMOOTH_SPAN / max(rpm_rate, 1.0) / dt / 2.0),
                       SG_MIN_HALF, SG_MAX_HALF))

    # Reject a pull whose speed channel is too coarsely quantised to differentiate
    # over the window this pull can afford, rather than reporting its noise as power.
    noise = accel_noise_floor(v_ground_raw, dt, half)
    if noise > ACCEL_NOISE_LIMIT:
        return None

    v = savgol(v_ground_raw, dt, half)
    a = savgol(v_ground_raw, dt, half, deriv=1)
    v_driven = savgol(v_driven_raw, dt, half)
    a_driven = savgol(v_driven_raw, dt, half, deriv=1)
    omega_e = savgol(rpm_all * 2.0 * np.pi / 60.0, dt, half)
    alpha_e = savgol(rpm_all * 2.0 * np.pi / 60.0, dt, half, deriv=1)

    rho = air_density(lf)
    road = road_load_force(v, rho, mass_kg)
    f_grade = mass_kg * G * (grade_pct / 100.0)

    # The undriven pair spins up at the ground rate; the driven pair at its own,
    # which is what makes a wheelspinning 2nd-gear pull come out right.
    f_inertia = mass_kg * a + (m_wheel_eq / 2.0) * (a + a_driven)
    f_tractive = f_inertia + road["total"] + f_grade

    p_ground = f_tractive * v
    p_axle = f_tractive * v_driven
    p_crank = p_axle / eta + i_engine * omega_e * alpha_e

    # Keep only genuine in-gear WOT samples inside the detected window.
    idx = np.arange(lo, hi + 1)
    keep = (rpm_all[idx] >= RPM_MIN) & np.isfinite(p_crank[idx]) & (omega_e[idx] > 1.0)
    if lf.has("pedal"):
        keep &= ch("pedal")[idx] >= PEDAL_MIN_PCT
    if gear is not None and lf.has("gear"):
        keep &= np.round(ch("gear")[idx]) == gear
    idx = idx[keep]
    trim = int(round(PRESHIFT_TRIM_S / dt))
    if idx.size > trim + 10:
        idx = idx[:-trim]
    if idx.size < 10:
        return None

    if speed_source == "undriven":
        slip = np.where(v[idx] > 1.0, 100.0 * (v_driven[idx] - v[idx]) / v[idx], np.nan)
    else:
        slip = np.full(idx.size, np.nan)   # no undriven reference in this profile
    return PullCurve(
        revision=revision, file=lf.name, pull_index=pull_index, gear=gear,
        n_samples=int(idx.size), duration_s=float((idx[-1] - idx[0]) * dt),
        dt_s=dt, sg_half=half, speed_source=speed_source, accel_noise=noise,
        ambient_c=float(np.nanmedian(ch("ambient_temp")[idx])),
        ambient_kpa=float(np.nanmedian(ch("ambient_press")[idx])),
        rho=float(np.nanmedian(rho[idx])),
        t=(idx - idx[0]) * dt,
        rpm=rpm_all[idx], v_kmh=v[idx] * 3.6, accel=a[idx], slip_pct=slip,
        lat_accel=ch("accel_lat")[idx] if lf.has("accel_lat") else None,
        grade_cruise_pct=cruise_grade_pct(lf, dt, half),
        f_inertia=f_inertia[idx], f_rolling=road["rolling"][idx], f_aero=road["aero"][idx],
        hp_ground=p_ground[idx] / W_PER_HP,
        hp_crank=p_crank[idx] / W_PER_HP,
        tq_crank_nm=p_crank[idx] / omega_e[idx],
        hp_ecu=ch("calc_hp")[idx] if lf.has("calc_hp") else None,
        tq_ecu_nm=ch("torque")[idx] if lf.has("torque") else None,
    )


# --------------------------------------------------------------------------- #
# Collection
# --------------------------------------------------------------------------- #
def collect(min_duration_s: float = 1.4, **kw) -> list[PullCurve]:
    """Every qualifying WOT pull across every log folder, reduced to a curve."""
    curves: list[PullCurve] = []
    for folder in FOLDERS:
        path = REPO / "Logs" / folder
        if not path.is_dir():
            continue
        logset = load_logset(path)
        by_name = {f.name: f for f in logset.files}
        revision = folder.split("_")[-1]
        for pull in detect_pulls(logset):
            if pull.duration_s is not None and pull.duration_s < min_duration_s:
                continue
            lf = by_name[pull.file]
            curve = derive_pull(lf, revision, pull.index, pull.gear,
                                pull.start_row, pull.end_row, **kw)
            if curve is not None:
                curves.append(curve)
    return curves


def onto_grid(rpm: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Resample a curve onto `RPM_GRID`, NaN outside the pull's own rpm range."""
    order = np.argsort(rpm)
    out = np.interp(RPM_GRID, rpm[order], y[order], left=np.nan, right=np.nan)
    out[(RPM_GRID < rpm.min()) | (RPM_GRID > rpm.max())] = np.nan
    return out


def mean_curve(curves: list[PullCurve], attr: str) -> np.ndarray:
    """Sample-mean of several pulls' curves on the common rpm grid."""
    usable = [c for c in curves if getattr(c, attr) is not None]
    if not usable:
        return np.full(RPM_GRID.shape, np.nan)
    stack = np.vstack([onto_grid(c.rpm, getattr(c, attr)) for c in usable])
    counts = np.sum(np.isfinite(stack), axis=0)
    out = np.full(RPM_GRID.shape, np.nan)
    # Do not let one pull's extreme end define the mean where the others stopped.
    ok = counts >= min(2, len(usable))
    out[ok] = np.nansum(stack[:, ok], axis=0) / counts[ok]
    return out


def full(curves: list[PullCurve], gear: Optional[int] = None,
         revision: Optional[str] = None, clean: bool = False,
         require_undriven: bool = True) -> list[PullCurve]:
    """Pulls that swept the engine — the only ones whose peaks are comparable.

    By default a pull must also have an undriven speed reference. Without one
    (the R01 logging profile) there is no way to separate driven-wheel slip from
    real acceleration, and a wheelspinning pull reads wildly high; those pulls
    stay in the table with a note but never enter an aggregate.

    `clean=True` additionally drops traction-limited pulls (front tyres spinning).
    """
    sel = [c for c in curves if c.full_pull]
    if require_undriven:
        # Measured on the logs that have both references: with no undriven wheel
        # to compare against, a 3rd-gear pull reads only +0.7 % high but a 2nd-gear
        # one reads +32 %, because the wheelspin cannot be seen let alone removed.
        sel = [c for c in sel
               if c.speed_source == "undriven" or (c.gear is not None and c.gear >= 3)]
    if gear is not None:
        sel = [c for c in sel if c.gear == gear]
    if revision is not None:
        sel = [c for c in sel if c.revision == revision]
    if clean:
        sel = [c for c in sel if not c.traction_limited]
    return sel


def peak(curve: PullCurve, attr: str, rpm_min: float = 3500.0) -> float:
    y = getattr(curve, attr)
    m = curve.rpm >= rpm_min
    return float(np.nanmax(y[m])) if m.any() else float("nan")


def peak_rpm(curve: PullCurve, attr: str, rpm_min: float = 3500.0) -> float:
    y = np.where(curve.rpm >= rpm_min, getattr(curve, attr), -np.inf)
    return float(curve.rpm[int(np.nanargmax(y))])


# --------------------------------------------------------------------------- #
# Plot helpers
# --------------------------------------------------------------------------- #
GEAR_COLOR = {1: "#8c564b", 2: "#d62728", 3: "#1f77b4", 4: "#2ca02c", 5: "#9467bd"}
REV_COLOR = {}


def grid(ax):
    ax.grid(True, which="major", alpha=0.45)
    ax.grid(True, which="minor", alpha=0.18)
    ax.minorticks_on()


def bold_labels(ax, xlabel, ylabel):
    ax.set_xlabel(xlabel, fontweight="bold")
    ax.set_ylabel(ylabel, fontweight="bold")


def hp_axis(ax, y_hp, label="hp"):
    """Right-hand kW twin so the numbers can be read either way."""
    tw = ax.twinx()
    tw.set_ylim(np.asarray(ax.get_ylim()) * W_PER_HP / 1000.0)
    tw.set_ylabel("kW")
    return tw


def save(fig, name):
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOT_DIR / name
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {path.relative_to(REPO)}")
    return path


# --------------------------------------------------------------------------- #
# Plots
# --------------------------------------------------------------------------- #
def plot_headline(curves: list[PullCurve]) -> Path:
    """The answer to the question: crank HP and TQ vs rpm, and vs time."""
    best = full(curves, gear=3, revision="R14")
    best.sort(key=lambda c: -peak(c, "hp_crank"))
    third = full(curves, gear=3)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    (ax_hp, ax_tq), (ax_ht, ax_tt) = axes

    # --- vs rpm, every 3rd-gear pull, coloured by revision -----------------
    revs = sorted({c.revision for c in third})
    cmap = plt.get_cmap("viridis", len(revs))
    for i, rev in enumerate(revs):
        sel = [c for c in third if c.revision == rev]
        REV_COLOR[rev] = cmap(i)
        for ax, attr in ((ax_hp, "hp_crank"), (ax_tq, "tq_crank_nm")):
            ax.plot(RPM_GRID, mean_curve(sel, attr), color=cmap(i), lw=2.2,
                    label=f"{rev}  (n={len(sel)})")
    for ax, ylab, title in (
        (ax_hp, "Crank power (hp)", "Derived crank power vs engine speed — 3rd-gear WOT pulls"),
        (ax_tq, "Crank torque (Nm)", "Derived crank torque vs engine speed — 3rd-gear WOT pulls"),
    ):
        bold_labels(ax, "Engine speed (rpm)", ylab)
        ax.set_title(title, fontsize=10)
        grid(ax)
        ax.legend(fontsize=8, ncol=2, title="tune revision", title_fontsize=8)

    ax_tq2 = ax_tq.twinx()
    ax_tq2.set_ylim(np.asarray(ax_tq.get_ylim()) / NM_PER_LBFT)
    ax_tq2.set_ylabel("lb-ft")
    ax_hp2 = ax_hp.twinx()
    ax_hp2.set_ylim(np.asarray(ax_hp.get_ylim()) * W_PER_HP / 1000.0)
    ax_hp2.set_ylabel("kW")

    # --- vs time, the best R14 3rd-gear pulls ------------------------------
    for c in best[:3]:
        col = GEAR_COLOR.get(c.gear, "k")
        ax_ht.plot(c.t, c.hp_crank, lw=1.8, label=f"{c.file[-8:]}  peak {peak(c,'hp_crank'):.0f} hp")
        ax_tt.plot(c.t, c.tq_crank_nm, lw=1.8, label=f"{c.file[-8:]}  peak {peak(c,'tq_crank_nm'):.0f} Nm")
    for ax, ylab, title in (
        (ax_ht, "Crank power (hp)", "Derived crank power vs time — R14 3rd-gear pulls"),
        (ax_tt, "Crank torque (Nm)", "Derived crank torque vs time — R14 3rd-gear pulls"),
    ):
        bold_labels(ax, "Time from pull start (s)", ylab)
        ax.set_title(title, fontsize=10)
        grid(ax)
        ax.legend(fontsize=8)

    fig.suptitle(
        f"Physics-derived power and torque  —  F = ma on {VEHICLE_MASS_LB:.0f} lb "
        f"({VEHICLE_MASS_KG:.0f} kg), EPA coastdown road load, "
        f"eta={ETA_DRIVELINE:.2f}, I_engine={I_ENGINE_SIDE:.2f} kg m^2",
        fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return save(fig, "01_power_torque_headline.png")


def plot_best_pull(curves: list[PullCurve]) -> Path:
    """One pull, taken apart: speed, acceleration, force budget, power budget."""
    cands = [c for c in full(curves, gear=3, revision="R14") if c.speed_source == "undriven"]
    c = max(cands, key=lambda x: peak(x, "hp_crank"))

    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    (a1, a2), (a3, a4), (a5, a6) = axes

    a1.plot(c.t, c.v_kmh, color="#1f77b4", lw=2, label="ground speed (undriven wheels)")
    a1.plot(c.t, c.v_kmh * (1 + c.slip_pct / 100.0), color="#d62728", lw=1.2, ls="--",
            label="driven-wheel speed")
    bold_labels(a1, "Time from pull start (s)", "Speed (km/h)")
    a1.set_title("Speed — the driven wheels run ahead of the ground", fontsize=10)
    a1.legend(fontsize=8); grid(a1)
    a1b = a1.twinx(); a1b.plot(c.t, c.slip_pct, color="#7f7f7f", lw=1, alpha=0.7)
    a1b.set_ylabel("driven-wheel slip (%)", color="#7f7f7f")

    a2.plot(c.t, c.accel, color="#ff7f0e", lw=2)
    bold_labels(a2, "Time from pull start (s)", "Longitudinal acceleration (m/s²)")
    a2.set_title(f"Ground acceleration — d/dt of undriven wheel speed "
                 f"({(2*c.sg_half+1)*c.dt_s:.2f} s window)", fontsize=10)
    grid(a2)
    a2b = a2.twinx(); a2b.set_ylim(np.asarray(a2.get_ylim()) / G); a2b.set_ylabel("g")

    a3.stackplot(c.t, np.clip(c.f_inertia, 0, None), c.f_aero, c.f_rolling,
                 labels=["inertia  (m + m_wheel) · a", "aerodynamic drag  ½ρCdA v²",
                         "rolling resistance  A′ + B·v"],
                 colors=["#1f77b4", "#d62728", "#2ca02c"], alpha=0.85)
    bold_labels(a3, "Time from pull start (s)", "Tractive force (N)")
    a3.set_title("Force budget at the contact patch", fontsize=10)
    a3.legend(fontsize=8, loc="upper right"); grid(a3)

    ftot = c.f_inertia + c.f_aero + c.f_rolling
    a4.plot(c.rpm, 100 * c.f_inertia / ftot, lw=2, color="#1f77b4", label="inertia")
    a4.plot(c.rpm, 100 * c.f_aero / ftot, lw=2, color="#d62728", label="aero drag")
    a4.plot(c.rpm, 100 * c.f_rolling / ftot, lw=2, color="#2ca02c", label="rolling resistance")
    bold_labels(a4, "Engine speed (rpm)", "Share of tractive force (%)")
    a4.set_title("How much the drag models matter", fontsize=10)
    a4.legend(fontsize=8); grid(a4)

    a5.plot(c.rpm, c.hp_ground, lw=2, color="#2ca02c", label="at the road (contact patch)")
    a5.plot(c.rpm, c.hp_crank, lw=2.4, color="#1f77b4", label="at the crank")
    if c.hp_ecu is not None:
        a5.plot(c.rpm, c.hp_ecu, lw=1.4, ls="--", color="#7f7f7f", label="ECU `Calc HP`")
    bold_labels(a5, "Engine speed (rpm)", "Power (hp)")
    a5.set_title("Power vs engine speed", fontsize=10)
    a5.legend(fontsize=8); grid(a5)

    a6.plot(c.rpm, c.tq_crank_nm, lw=2.4, color="#1f77b4", label="derived crank torque")
    if c.tq_ecu_nm is not None:
        a6.plot(c.rpm, c.tq_ecu_nm, lw=1.6, ls="--", color="#7f7f7f",
                label="ECU torque model  `Torque (Nm)`")
    bold_labels(a6, "Engine speed (rpm)", "Torque (Nm)")
    a6.set_title("Torque vs engine speed — derived against the ECU's own model", fontsize=10)
    a6.legend(fontsize=8); grid(a6)
    a6b = a6.twinx(); a6b.set_ylim(np.asarray(a6.get_ylim()) / NM_PER_LBFT); a6b.set_ylabel("lb-ft")

    fig.suptitle(f"Anatomy of one pull — {c.revision}  {c.file}  (gear {c.gear}, "
                 f"{c.ambient_c:.0f} °C, {c.ambient_kpa:.0f} kPa, ρ = {c.rho:.3f} kg/m³)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    return save(fig, "02_pull_anatomy.png")


def plot_gear_consistency(curves: list[PullCurve]) -> Path:
    """The model's own check: one engine must make one curve in every gear."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    (a1, a2), (a3, a4) = axes

    for ax, source, title in (
        (a1, "undriven", "Ground speed from the UNDRIVEN wheels  ← model as built"),
        (a2, "driven", "Ground speed from the DRIVEN wheels  (`Vehicle Speed`)"),
    ):
        for gear in (2, 3):
            sel = [c for c in full(curves, gear=gear)
                   if c.revision in ("R07", "R08", "R09", "R14")]
            if source == "driven":
                sel = [derive_pull_driven(c) for c in sel]
                sel = [c for c in sel if c is not None]
            if not sel:
                continue
            ax.plot(RPM_GRID, mean_curve(sel, "tq_crank_nm"), lw=2.4,
                    color=GEAR_COLOR[gear], label=f"gear {gear}  (n={len(sel)})")
        for gear, col in ((3, "#1f77b4"), (2, "#d62728")):
            ax.plot(RPM_GRID, mean_curve(full(curves, gear=gear), "tq_ecu_nm"),
                    lw=1.2, ls=":", color=col, label=f"ECU model, gear {gear}")
        bold_labels(ax, "Engine speed (rpm)", "Crank torque (Nm)")
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8); grid(ax)
        ax.set_ylim(100, 460)

    # Inertia fit: the gear-2 / gear-3 gap vs assumed engine-side inertia.
    inertias = np.linspace(0.0, 0.6, 13)
    gaps, ecu_gap = [], None
    for i_e in inertias:
        cs = collect(i_engine=i_e)
        g2 = [c for c in full(cs, gear=2) if c.revision in ("R07", "R08", "R09", "R14")]
        g3 = [c for c in full(cs, gear=3) if c.revision in ("R07", "R08", "R09", "R14")]
        m2, m3 = mean_curve(g2, "tq_crank_nm"), mean_curve(g3, "tq_crank_nm")
        ok = np.isfinite(m2) & np.isfinite(m3)
        gaps.append(float(np.mean(m3[ok] - m2[ok])))
        if ecu_gap is None:
            e2, e3 = mean_curve(g2, "tq_ecu_nm"), mean_curve(g3, "tq_ecu_nm")
            ecu_gap = float(np.mean(e3[ok] - e2[ok]))
    gaps = np.asarray(gaps)
    a3.plot(inertias, gaps, "o-", color="#1f77b4", lw=2, label="derived  (3rd − 2nd)")
    a3.axhline(ecu_gap, color="#7f7f7f", ls="--", lw=1.6,
               label=f"ECU model's own gear gap = {ecu_gap:+.0f} Nm")
    fit = float(np.interp(ecu_gap, gaps[::-1], inertias[::-1]))
    a3.axvline(fit, color="#d62728", ls=":", lw=1.6, label=f"fit: I = {fit:.2f} kg m²")
    a3.axvline(I_ENGINE_SIDE, color="#2ca02c", ls="-", lw=1.2, alpha=0.6,
               label=f"used: I = {I_ENGINE_SIDE:.2f} kg m²")
    bold_labels(a3, "Assumed engine-side rotational inertia (kg m²)",
                "Mean 3rd − 2nd gear torque gap (Nm)")
    a3.set_title("Fitting the engine-side inertia from cross-gear agreement", fontsize=10)
    a3.legend(fontsize=8); grid(a3)

    # Sensitivity of the headline number to every assumption.
    base = collect()
    ref = np.nanmean([peak(c, "hp_crank") for c in full(base, gear=3, revision="R14")])
    scen = [
        ("mass 3300 lb", dict(mass_kg=3300 * LB_TO_KG)),
        ("mass 3500 lb", dict(mass_kg=3500 * LB_TO_KG)),
        (f"eta = {ETA_BAND[0]:.2f}", dict(eta=ETA_BAND[0])),
        (f"eta = {ETA_BAND[1]:.2f}", dict(eta=ETA_BAND[1])),
        (f"I_eng = {I_ENGINE_SIDE_BAND[0]:.2f}", dict(i_engine=I_ENGINE_SIDE_BAND[0])),
        (f"I_eng = {I_ENGINE_SIDE_BAND[1]:.2f}", dict(i_engine=I_ENGINE_SIDE_BAND[1])),
        ("wheel inertia 0", dict(m_wheel_eq=0.0)),
        ("wheel inertia x2", dict(m_wheel_eq=2 * M_WHEEL_EQ_KG)),
        ("road +1 % grade", dict(grade_pct=1.0)),
        ("road −1 % grade", dict(grade_pct=-1.0)),
    ]
    names, deltas = [], []
    for name, kw in scen:
        cs = collect(**kw)
        val = np.nanmean([peak(c, "hp_crank") for c in full(cs, gear=3, revision="R14")])
        names.append(name); deltas.append(val - ref)
    order = np.argsort(np.abs(deltas))
    ypos = np.arange(len(order))
    a4.barh(ypos, np.asarray(deltas)[order],
            color=["#d62728" if d < 0 else "#2ca02c" for d in np.asarray(deltas)[order]])
    a4.set_yticks(ypos); a4.set_yticklabels([names[i] for i in order], fontsize=8)
    a4.axvline(0, color="k", lw=1)
    bold_labels(a4, f"Change in peak crank hp (baseline {ref:.0f} hp)", "")
    a4.set_title("Sensitivity of the headline number to each assumption", fontsize=10)
    grid(a4)

    fig.suptitle("Model verification — cross-gear agreement, inertia fit, sensitivity",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    return save(fig, "03_verification.png")


def derive_pull_driven(c: PullCurve) -> Optional[PullCurve]:
    """Re-derive a curve using the driven wheels as the ground-speed source."""
    return _DRIVEN_CACHE.get((c.revision, c.file, c.pull_index))


_DRIVEN_CACHE: dict = {}


def build_driven_cache() -> None:
    """Populate the driven-wheel variant of every curve, for the slip comparison."""
    for folder in FOLDERS:
        path = REPO / "Logs" / folder
        if not path.is_dir():
            continue
        logset = load_logset(path)
        by_name = {f.name: f for f in logset.files}
        revision = folder.split("_")[-1]
        for pull in detect_pulls(logset):
            if pull.duration_s is not None and pull.duration_s < 1.4:
                continue
            lf = by_name[pull.file]
            if not lf.has("wheel_fl"):
                continue
            patched = _DrivenAsGround(lf)
            curve = derive_pull(patched, revision, pull.index, pull.gear,
                                pull.start_row, pull.end_row)
            if curve is not None:
                _DRIVEN_CACHE[(revision, lf.name, pull.index)] = curve


class _DrivenAsGround:
    """A LogFile view whose 'undriven' channels are the driven wheels.

    Used only to show what the answer would have been had the driven-wheel speed
    (i.e. `Vehicle Speed`) been treated as true ground speed.
    """

    def __init__(self, lf: LogFile):
        self._lf = lf

    def __getattr__(self, item):
        return getattr(self._lf, item)

    def has(self, cid):
        return self._lf.has(cid)

    def channel(self, cid):
        if cid == "wheel_rl":
            return self._lf.channel("wheel_fl")
        if cid == "wheel_rr":
            return self._lf.channel("wheel_fr")
        return self._lf.channel(cid)


def plot_revisions(curves: list[PullCurve]) -> Path:
    """Every pull, every revision — the tune's progress in physical units."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    (a1, a2), (a3, a4) = axes

    revs = sorted({c.revision for c in curves})
    for ax, attr, ylab in ((a1, "hp_crank", "Peak crank power (hp)"),
                           (a2, "tq_crank_nm", "Peak crank torque (Nm)")):
        for gear in (2, 3, 4):
            xs, ys = [], []
            for i, rev in enumerate(revs):
                sel = full(curves, gear=gear, revision=rev)
                if not sel:
                    continue
                xs.append(i); ys.append(np.mean([peak(c, attr) for c in sel]))
                ax.errorbar(i, ys[-1], yerr=np.std([peak(c, attr) for c in sel]),
                            fmt="none", ecolor=GEAR_COLOR[gear], alpha=0.6, capsize=3)
            if xs:
                ax.plot(xs, ys, "o-", color=GEAR_COLOR[gear], label=f"gear {gear}")
        ax.set_xticks(range(len(revs))); ax.set_xticklabels(revs)
        bold_labels(ax, "Tune revision", ylab)
        ax.set_title(f"{ylab} by revision (bars = pull-to-pull spread)", fontsize=10)
        ax.legend(fontsize=8); grid(ax)

    third = full(curves, gear=3)
    for c in sorted(third, key=lambda x: x.revision):
        a3.plot(c.rpm, c.hp_crank, lw=0.9, alpha=0.55,
                color=REV_COLOR.get(c.revision, "#888888"))
    for rev in revs:
        sel = [c for c in third if c.revision == rev]
        if sel:
            a3.plot(RPM_GRID, mean_curve(sel, "hp_crank"), lw=2.6,
                    color=REV_COLOR.get(rev, "#888888"), label=rev)
    bold_labels(a3, "Engine speed (rpm)", "Crank power (hp)")
    a3.set_title("Every 3rd-gear pull (thin) and the per-revision mean (thick)", fontsize=10)
    a3.legend(fontsize=8, ncol=2); grid(a3)

    ecu = [c for c in full(curves, gear=3) if c.hp_ecu is not None]
    a4.scatter([peak(c, "hp_crank") for c in ecu], [peak(c, "hp_ecu") for c in ecu],
               s=26, alpha=0.75, color="#1f77b4", label="3rd gear")
    ecu2 = [c for c in full(curves, gear=2) if c.hp_ecu is not None]
    a4.scatter([peak(c, "hp_crank") for c in ecu2], [peak(c, "hp_ecu") for c in ecu2],
               s=26, alpha=0.75, color="#d62728", label="2nd gear")
    vals = ([peak(c, "hp_crank") for c in ecu + ecu2]
            + [peak(c, "hp_ecu") for c in ecu + ecu2])
    lo, hi = min(vals) - 8, max(vals) + 8
    a4.plot([lo, hi], [lo, hi], "k--", lw=1, label="1:1")
    a4.set_xlim(lo, hi); a4.set_ylim(lo, hi)
    ratio = np.mean([peak(c, "hp_ecu") / peak(c, "hp_crank") for c in ecu + ecu2])
    a4.set_title(f"SimosTools' own estimate reads {100*(ratio-1):+.0f} % against the "
                 f"physics-derived number", fontsize=10)
    bold_labels(a4, "Derived crank power (hp)", "ECU `Calc HP` (hp)")
    a4.legend(fontsize=8); grid(a4)

    fig.suptitle("Derived power and torque across the tune lineage",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    return save(fig, "04_revisions.png")


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def write_report(curves: list[PullCurve], plots: list[Path]) -> Path:
    rows = []
    for c in sorted(curves, key=lambda x: (x.revision, x.pull_index)):
        rows.append({
            "revision": c.revision, "pull": c.pull_index, "file": c.file,
            "gear": c.gear, "n": c.n_samples, "duration_s": round(c.duration_s, 2),
            "rpm_lo": int(c.rpm.min()), "rpm_hi": int(c.rpm.max()),
            "speed_source": c.speed_source,
            "ambient_c": round(c.ambient_c, 1), "rho": round(c.rho, 4),
            "hp_ground": round(peak(c, "hp_ground"), 1),
            "hp_crank": round(peak(c, "hp_crank"), 1),
            "hp_crank_at_rpm": int(peak_rpm(c, "hp_crank")),
            "tq_crank_nm": round(peak(c, "tq_crank_nm"), 1),
            "tq_crank_lbft": round(peak(c, "tq_crank_nm") / NM_PER_LBFT, 1),
            "tq_crank_at_rpm": int(peak_rpm(c, "tq_crank_nm")),
            "hp_ecu": round(peak(c, "hp_ecu"), 1) if c.hp_ecu is not None else None,
            "tq_ecu_nm": round(peak(c, "tq_ecu_nm"), 1) if c.tq_ecu_nm is not None else None,
            "max_slip_pct": (round(float(np.nanmax(c.slip_pct)), 2)
                             if np.any(np.isfinite(c.slip_pct)) else None),
            "accel_noise_ms2": round(c.accel_noise, 3),
            "max_lat_accel_ms2": (round(float(np.nanmax(np.abs(c.lat_accel))), 2)
                                  if c.lat_accel is not None else None),
            "grade_cruise_pct": (round(c.grade_cruise_pct, 2)
                                 if c.grade_cruise_pct is not None else None),
            "cornering": bool(c.cornering),
            "full_pull": bool(c.full_pull),
            "traction_limited": bool(c.traction_limited),
        })
    (OUT_DIR / "physics_power_pulls.json").write_text(json.dumps(rows, indent=2))

    def fmt(v, w, spec=""):
        return f"{v:{spec}}".ljust(w) if not isinstance(v, (int, float)) or isinstance(v, bool) \
            else f"{v:{spec}}".rjust(w)

    hdr = ["Rev", "Pull", "Gear", "s", "rpm span", "Ground hp", "Crank hp", "@rpm",
           "Crank Nm", "lb-ft", "@rpm", "ECU hp", "ECU Nm", "Slip %", "Lat g", "Grade %", "Note"]
    widths = [4, 4, 4, 5, 11, 9, 8, 5, 8, 6, 5, 6, 6, 6, 6, 7, 34]
    lines = ["| " + " | ".join(h.ljust(w) for h, w in zip(hdr, widths)) + " |",
             "|-" + "-|-".join("-" * w for w in widths) + "-|"]
    for r in rows:
        note = []
        if r["speed_source"] != "undriven":
            note.append("driven speed only")
        if not r["full_pull"]:
            note.append("partial sweep")
        if r["traction_limited"]:
            note.append("wheelspin")
        if r["cornering"]:
            note.append("in a bend")
        cells = [r["revision"], str(r["pull"]), str(r["gear"]), f"{r['duration_s']:.1f}",
                 f"{r['rpm_lo']}-{r['rpm_hi']}", f"{r['hp_ground']:.0f}",
                 f"{r['hp_crank']:.0f}", str(r["hp_crank_at_rpm"]),
                 f"{r['tq_crank_nm']:.0f}", f"{r['tq_crank_lbft']:.0f}",
                 str(r["tq_crank_at_rpm"]),
                 "-" if r["hp_ecu"] is None else f"{r['hp_ecu']:.0f}",
                 "-" if r["tq_ecu_nm"] is None else f"{r['tq_ecu_nm']:.0f}",
                 "-" if r["max_slip_pct"] is None else f"{r['max_slip_pct']:.1f}",
                 "-" if r["max_lat_accel_ms2"] is None else f"{r['max_lat_accel_ms2']/9.80665:.2f}",
                 "-" if r["grade_cruise_pct"] is None else f"{r['grade_cruise_pct']:+.2f}",
                 ", ".join(note)]
        lines.append("| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |")
    print("\n".join(lines))
    (OUT_DIR / "physics_power_pulls.md").write_text("\n".join(lines) + "\n")

    # Headline aggregates, printed so a run of the script states its own answer.
    print()
    for gear in (2, 3, 4):
        for rev in sorted({c.revision for c in curves}):
            sel = full(curves, gear=gear, revision=rev)
            if not sel:
                continue
            hp = [peak(c, "hp_crank") for c in sel]
            tq = [peak(c, "tq_crank_nm") for c in sel]
            gp = [peak(c, "hp_ground") for c in sel]
            flag = " (wheelspin-limited)" if all(c.traction_limited for c in sel) else ""
            print(f"  gear {gear}  {rev}  n={len(sel)}  "
                  f"road {np.mean(gp):5.0f} hp | crank {np.mean(hp):5.0f} ± {np.std(hp):3.0f} hp"
                  f" | {np.mean(tq):5.0f} ± {np.std(tq):3.0f} Nm"
                  f" ({np.mean(tq)/NM_PER_LBFT:.0f} lb-ft){flag}")
    return OUT_DIR / "physics_power_pulls.md"


def report_speed_source_bias(curves: list[PullCurve]) -> None:
    """How much treating the driven wheels as ground speed costs, measured.

    Re-derives the pulls that *do* have an undriven reference as if they did not,
    which is the error the R01-profile logs carry and cannot have removed.
    """
    pairs = []
    for c in full(curves):
        d = derive_pull_driven(c)
        if d is not None:
            pairs.append((peak(c, "hp_crank"), peak(d, "hp_crank"), c.gear))
    if not pairs:
        return
    print("\n  Driven-wheel-speed bias (what an R01-profile log cannot correct):")
    for gear in sorted({g for _, _, g in pairs}):
        sel = [(a, b) for a, b, g in pairs if g == gear]
        rel = np.mean([(b - a) / a for a, b in sel]) * 100
        print(f"    gear {gear}: n={len(sel)}  driven-speed reading is {rel:+.1f} % "
              f"({np.mean([b - a for a, b in sel]):+.0f} hp)")


def main() -> None:
    print("Deriving power and torque from F = ma ...")
    curves = collect()
    print(f"  {len(curves)} qualifying WOT pulls across {len({c.revision for c in curves})} revisions")
    print("Building the driven-wheel comparison variant ...")
    build_driven_cache()
    plots = [plot_headline(curves), plot_best_pull(curves)]
    plots.append(plot_gear_consistency(curves))
    plots.append(plot_revisions(curves))
    write_report(curves, plots)
    report_speed_source_bias(curves)
    print("done")


if __name__ == "__main__":
    main()
