"""Size R24's low-torque, linear-powerband boost cap for map slot 2.

The goal is a powerband that rises **linearly** with engine speed and peaks near
6000 rpm, with low torque everywhere below that. On this engine torque tracks
airmass per stroke, so power is proportional to ``airmass x rpm``. A powerband
that is linear in rpm is therefore, exactly, a **constant airmass** across the
range — and the power peak lands at the highest rpm the turbo can still hold
that airmass at. There is no curve-fitting in this: it falls out of P = T x N.

So the calibration problem is: what boost cap holds airmass flat at
``TARGET_MG``, and where does the turbo fall off it?

Two things bound the answer, and both come from measurement rather than from a
model:

* **Volumetric efficiency** — how much airmass per stroke this engine actually
  makes per kPa of manifold pressure, as a function of rpm — is taken from the
  same 55-log aggressive-curve population `lineage.py` pools, using only samples
  where the boost cap is *binding* so that spool transients do not contaminate
  it. Required cap is then ``TARGET_MG / VE(rpm)``.
* **The aggressive curve itself is the ceiling.** Above roughly 6150 rpm,
  holding the target airmass would need more boost than this car has ever been
  logged running, because VE is falling faster than the target needs. Asking for
  that is asking the turbo for an unlogged operating point, so the cap is
  clamped at map slot 3's curve, read off the R23 bin. Airmass therefore holds
  flat to ~6100 rpm and then falls with the taper — which is what puts the power
  peak where it is asked to be.

Below ~3400 rpm the cap is not binding today (the turbo is still spooling), so
the linear region starts there; the new cap does bind a little earlier than the
old one, which is the point of a low-torque map.

Run:  Code/.venv/bin/python Logs/aggressive_slot_lineage/size_r24_linear.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lineage as L  # noqa: E402

from simoscal import CalFile, structure_of  # noqa: E402
from simoscal.tune.profiles.switchpatch_2933 import S50_PUT_GRID_UIDS  # noqa: E402

REPO_ROOT = HERE.parents[1]
BINTOOLZ = REPO_ROOT / "BinToolz-main"
SWITCH_XDF = BINTOOLZ / "definitions" / "S50 Switch Patch.29.33.V2.xdf"

#: The R23 bin — the lineage tip, and the bin R24 is built on top of.
R23_REFERENCE = (
    REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
    / "R23_20260903-111406" / "Patched_259L_R23.bin"
)

#: The flat airmass the low-torque map holds, in mg/stk. Chosen with Sam on
#: 2026-09-03 from a sizing sweep: 1200 gives the straightest power line of the
#: candidates considered (R^2 0.999 against rpm), drops mid-range torque ~22 %,
#: and costs only a couple of percent of peak power because the cut is entirely
#: below 5900 rpm, where peak power is not.
TARGET_MG = 1200.0

#: The switch patch's shared 12-point slot rpm axis — the breakpoints the new
#: curve has to be expressed on.
SLOT_RPM_AXIS = (3000.0, 3200.0, 3400.0, 3800.0, 4400.0, 4700.0,
                 5000.0, 5400.0, 5750.0, 6000.0, 6250.0, 6500.0)

#: The everyday aggressive map, whose cap bounds the new one from above.
AGGRESSIVE_SLOT = 3

#: rpm bin width for the VE profile, in rpm.
BIN_W = 200.0
#: A sample counts toward VE only if the delivered pressure is within this of
#: the slot's own setpoint, i.e. the cap is binding and the turbo is not still
#: spooling onto it.
BINDING_TOL_KPA = 4.0
#: Fewest samples a bin needs before its VE is trusted.
BIN_MIN_N = 15
#: Standard-day ambient, for reporting gauge psi only. Nothing is sized on it.
AMBIENT_KPA = 101.3


def ve_profile() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Measured VE, current airmass and current pressure per rpm bin.

    VE here is the directly useful quantity rather than the textbook one: mg of
    air per stroke per kPa of manifold pressure. Inverting it gives the cap that
    delivers a wanted airmass, which is the whole job.
    """
    sessions, _ = L.collect()
    rpm, air, put, psp = [], [], [], []
    for s in sessions:
        d, m = s.data, L.loaded_mask(s.data)
        rpm.append(d["rpm"][m])
        air.append(d["airmass"][m] * 1000.0)
        put.append(d["put"][m])
        psp.append(d["put_sp"][m])
    rpm = np.concatenate(rpm)
    air = np.concatenate(air)
    put = np.concatenate(put)
    psp = np.concatenate(psp)
    print(f"{len(sessions)} aggressive-curve logs, {rpm.size} loaded samples")

    cent, ve, air_now, put_now = [], [], [], []
    for lo in np.arange(3000.0, 6600.0, BIN_W):
        s = (rpm >= lo) & (rpm < lo + BIN_W)
        if s.sum() < BIN_MIN_N:
            continue
        binding = s & (put >= psp - BINDING_TOL_KPA)
        use = binding if binding.sum() >= BIN_MIN_N else s
        cent.append(lo + BIN_W / 2.0)
        ve.append(float(np.median(air[use] / put[use])))
        air_now.append(float(np.median(air[s])))
        put_now.append(float(np.nanmedian(put[s])))
    return (np.asarray(cent), np.asarray(ve),
            np.asarray(air_now), np.asarray(put_now))


def aggressive_curve() -> np.ndarray:
    """Map slot 3's cap in hPa, read off the R23 bin on the slot rpm axis."""
    cal = CalFile.open(str(SWITCH_XDF), str(R23_REFERENCE),
                       structure=structure_of(R23_REFERENCE))
    view = cal.get(int(S50_PUT_GRID_UIDS[AGGRESSIVE_SLOT], 16))
    grid = np.asarray(view.values, dtype=np.float64)
    axis = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
    if not np.allclose(axis, SLOT_RPM_AXIS, atol=1e-6):
        raise RuntimeError(
            f"slot {AGGRESSIVE_SLOT} rpm axis on the R23 bin is {axis}, "
            f"not the declared {SLOT_RPM_AXIS}"
        )
    if not np.all(grid == grid[0]):
        raise RuntimeError(
            f"slot {AGGRESSIVE_SLOT} cap on the R23 bin is not uniform across "
            "its eight Y rows"
        )
    return grid[0].copy()


def size() -> dict[str, np.ndarray]:
    cent, ve, air_now, put_now = ve_profile()
    axis = np.asarray(SLOT_RPM_AXIS)
    ceiling = aggressive_curve()

    # VE onto the grid's own breakpoints. np.interp holds the end values flat
    # beyond the measured range, which is the same clamp the ECU applies to a
    # lookup off the end of an axis.
    ve_axis = np.interp(axis, cent, ve)
    required_hpa = TARGET_MG / ve_axis * 10.0
    cap = np.minimum(required_hpa, ceiling)
    clamped = required_hpa > ceiling + 1e-9

    # What the engine then makes, on the same measured VE.
    air_new = np.minimum(cap / 10.0 * ve_axis, TARGET_MG)
    air_old = np.interp(axis, cent, air_now)
    put_old = np.interp(axis, cent, put_now)

    return {
        "axis": axis, "ve": ve_axis, "required": required_hpa,
        "ceiling": ceiling, "cap": cap, "clamped": clamped,
        "air_new": air_new, "air_old": air_old, "put_old": put_old,
        "cent": cent, "ve_binned": ve, "air_now": air_now, "put_now": put_now,
    }


def report(r: dict[str, np.ndarray]) -> None:
    axis, cap = r["axis"], r["cap"]
    print(f"\n--- the new map slot 2 cap, flat {TARGET_MG:.0f} mg/stk ---")
    print(f"{'rpm':>6} {'VE':>6} {'need':>7} {'slot3':>7} {'CAP':>7} "
          f"{'psi g':>7} {'was':>7} {'d psi':>7} {'air':>7} {'clamp':>6}")
    for i, rpm in enumerate(axis):
        print(f"{rpm:6.0f} {r['ve'][i]:6.3f} {r['required'][i]:7.0f} "
              f"{r['ceiling'][i]:7.0f} {cap[i]:7.0f} "
              f"{(cap[i]/10 - AMBIENT_KPA)*0.145038:7.2f} "
              f"{(r['put_old'][i] - AMBIENT_KPA)*0.145038:7.2f} "
              f"{(cap[i]/10 - r['put_old'][i])*0.145038:7.2f} "
              f"{r['air_new'][i]:7.0f} {'yes' if r['clamped'][i] else '':>6}")

    # Predicted power, on a fine rpm grid so the peak is not an artefact of the
    # 12 breakpoints. The ECU interpolates the cap linearly between them.
    fine = np.arange(3000.0, 6600.0, 25.0)
    ve_f = np.interp(fine, r["cent"], r["ve_binned"])
    cap_f = np.interp(fine, axis, cap)
    air_f = np.minimum(cap_f / 10.0 * ve_f, TARGET_MG)
    p_new = air_f * fine
    air_old_f = np.interp(fine, r["cent"], r["air_now"])
    p_old = air_old_f * fine

    i_new, i_old = int(p_new.argmax()), int(p_old.argmax())
    print(f"\npeak power  now {fine[i_old]:.0f} rpm  ->  new {fine[i_new]:.0f} rpm")
    print(f"peak power change {100*(p_new[i_new]/p_old[i_old] - 1):+.1f} %")
    i41 = int(np.argmin(np.abs(fine - 4100)))
    print(f"torque at 4100 rpm {100*(air_f[i41]/air_old_f[i41] - 1):+.1f} %")

    # Linearity over the region the cap actually governs, up to the peak.
    seg = (fine >= 3400.0) & (fine <= fine[i_new])
    k = np.polyfit(fine[seg], p_new[seg], 1)
    resid = p_new[seg] - np.polyval(k, fine[seg])
    r2 = 1.0 - resid.var() / p_new[seg].var()
    r2_old = None
    resid_o = p_old[seg] - np.polyval(np.polyfit(fine[seg], p_old[seg], 1), fine[seg])
    r2_old = 1.0 - resid_o.var() / p_old[seg].var()
    print(f"linearity of power vs rpm, 3400 rpm to the peak: "
          f"R^2 {r2:.4f}  (aggressive curve over the same span: {r2_old:.4f})")

    print(f"\n{'rpm':>6} {'air now':>8} {'air new':>8} {'P now':>7} {'P new':>7} "
          f"{'rel now':>8} {'rel new':>8}")
    for rpm in range(3000, 6600, 200):
        j = int(np.argmin(np.abs(fine - rpm)))
        print(f"{rpm:6d} {air_old_f[j]:8.0f} {air_f[j]:8.0f} "
              f"{p_old[j]/1e6:7.3f} {p_new[j]/1e6:7.3f} "
              f"{100*p_old[j]/p_old[i_old]:7.1f}% {100*p_new[j]/p_new[i_new]:7.1f}%")

    print("\nCurve for the revision script, hPa on the 12-point slot rpm axis:")
    print("    " + ", ".join(f"{v:.0f}" for v in np.round(cap)))


if __name__ == "__main__":
    report(size())
