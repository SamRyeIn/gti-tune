"""Size R23's enrichment against the pump, by replaying the ECU's own lookup.

Going richer is only worth proposing if the high-pressure fuel pump can deliver
it, and `HPFP Eff Vol` — high-pressure fuel pump effective volume already runs
in the high eighties at 3000-3500 rpm on this calibration. So the check has to
be per sample, not per band median: a change that leaves the median comfortable
can still push the 95th percentile onto the stop.

Three stages, in order:

1. **Replay.** Reproduce `Lambda SP` — the commanded lambda setpoint from
   `IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda setpoint grid by bilinear lookup on
   rpm x airmass, and score it against the logged channel. `Fuel Split MPI`
   reads 0.000 at WOT, so the HPDI grid is the operative one and a close match
   is expected; if the replay does not reproduce the log, nothing downstream is
   trustworthy and this fails loud rather than reporting a sized change.
2. **Candidates.** Apply each candidate grid and recompute the commanded lambda
   the same way.
3. **Pump.** Scale the logged pump volume by the fuel ratio ``old / new`` — a
   lambda that is 4 % richer needs 4 % more fuel through the same pump at the
   same speed — and report the distribution per band.

Everything downstream of the replay uses its **ratio**, never its absolute
value, and that is deliberate. The replay reproduces the logged setpoint to a
median 0.001 lambda across the population, but at 4500-5000 rpm the logged
command runs about 0.020 richer than the grid alone asks for, and about 0.009
richer at 5000-5500. That is not the airmass axis running off its top
breakpoint — 61 % of loaded samples do exceed 1389 mg/stk, and clamping beats
extrapolating there by an order of magnitude (median absolute error 0.00103
against 0.00830) — and it is not the full-load enrichment maps, which this
calibration holds at 1.000, nor the minimum-lambda floors, which cannot force a
richer mixture. Some other path enriches those two bands and it has not been
identified. A ratio cancels it; an absolute value would import it into a band
the grid never touches, which is exactly the error the first version of the
evidence figure made.

The doubled row is not decoration. R23 routes its enrichment through the base
grid and uses the five per-slot `Lambda modifier` grids to hold the *other*
slots at their prior lambda, precisely so that a wrong-signed or inert modifier
fails rich rather than lean. "Fails rich" is only safe while the pump can still
deliver it, so the doubled case is sized here too.

Run:  Code/.venv/bin/python Logs/aggressive_slot_lineage/size_r23.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from lineage import BANDS, REPO_ROOT, collect, loaded_mask

from simoscal import CalFile, structure_of

XDF = REPO_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
R22_BIN = (REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
           / "R22_20260901-060746" / "Patched_259L_R22.bin")
SWITCH_XDF_PATH = (REPO_ROOT / "BinToolz-main" / "definitions"
                   / "S50 Switch Patch.29.33.V2.xdf")
#: `PUT setpoint` — map slot 3 boost cap, the aggressive curve, on the R22 bin.
AGGRESSIVE_SLOT_UID = "0x7d59a"

#: The grid's storage step, 1/1024. Every candidate value must be a whole
#: multiple of it or the value sized here is not the value the ECU runs.
LAMBDA_STEP = 1.0 / 1024.0

#: The replay must reproduce the logged setpoint at least this well before any
#: candidate is sized against it, as a **median** absolute error. The mean is
#: the wrong statistic here: a handful of samples sit at lambda 1.000 because
#: full-load enrichment has not engaged on them yet, and those are not the grid
#: failing to explain the log, they are samples that are not reading the grid.
#: They are excluded by `FULL_LOAD_LAMBDA_MAX` and counted, not averaged in.
REPLAY_MEDIAN_ABS_MAX = 0.005
#: Above this the commanded lambda is not the full-load value at all — the
#: enrichment has not engaged — so the sample says nothing about the WOT grid.
FULL_LOAD_LAMBDA_MAX = 0.99
#: If more than this share of loaded samples are excluded that way, the gate
#: itself is wrong and the replay is not being scored on the population it
#: claims to describe.
NOT_ENGAGED_MAX_FRACTION = 0.05

#: Candidate enrichments, as ``{rpm breakpoint: lambda}`` written into both of
#: the two loaded airmass rows (1200.01 and 1389.00 mg/stk). Only the 3008 and
#: 3488 rpm columns move: 3000-3500 rpm carries the highest knock rate in the
#: lineage and the largest gap to EQT's fuelling, and it is the only boosted
#: band with pump headroom left.
CANDIDATES = {
    "as-is (R22)": {},
    "shipped in R23": {3008: 0.930, 5504: 0.780, 5984: 0.780,
                       6496: 0.780, 7008: 0.780},
    "3008 to 0.910": {3008: 0.910},
    "3008 to 0.900": {3008: 0.900},
    "3008 to 0.870 (EQT)": {3008: 0.870},
}

#: The band the enrichment is aimed at.
FOCUS = (3000, 3500)

#: EQT Stage 2's commanded lambda in the focus band — the figure the pump will
#: not let R23 reach on the current boost curve, and the target the boost
#: proposal is sized against.
EQT_FOCUS_LAMBDA = 0.870

#: The pump gate the boost proposal is solved to. Not a measured cliff: the
#: logged distribution simply never goes past 100 %, and rail pressure starts
#: falling short before it gets there (see the 97-101 % bin of
#: `HPFP Eff Vol` against `FP DI` - `FP DI SP`). 98 % at the 99th percentile
#: leaves the last two points as margin for a hotter day than any logged here.
PUMP_GATE_P99 = 98.0


def quantise(value: float) -> float:
    """The nearest value the grid can actually store."""
    return round(value / LAMBDA_STEP) * LAMBDA_STEP


def base_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`IP_LAMB_BAS_HPDI[1]` off the flashed R22 bin, with its two axes."""
    cal = CalFile.open(str(XDF), str(R22_BIN), structure=structure_of(R22_BIN))
    view = cal.get("IP_LAMB_BAS_HPDI[1]")
    return (np.asarray(view.values, dtype=np.float64),
            np.asarray(view.axis_values("x"), dtype=np.float64).ravel(),
            np.asarray(view.axis_values("y"), dtype=np.float64).ravel())


def lookup(grid: np.ndarray, rpm_axis: np.ndarray, load_axis: np.ndarray,
           rpm: np.ndarray, load: np.ndarray) -> np.ndarray:
    """Bilinear grid lookup, clamped at both axis ends as the ECU clamps."""
    x = np.clip(np.interp(rpm, rpm_axis, np.arange(rpm_axis.size)),
                0, rpm_axis.size - 1)
    y = np.clip(np.interp(load, load_axis, np.arange(load_axis.size)),
                0, load_axis.size - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1 = np.minimum(x0 + 1, rpm_axis.size - 1)
    y1 = np.minimum(y0 + 1, load_axis.size - 1)
    fx, fy = x - x0, y - y0
    return ((1 - fy) * ((1 - fx) * grid[y0, x0] + fx * grid[y0, x1])
            + fy * ((1 - fx) * grid[y1, x0] + fx * grid[y1, x1]))


def apply_candidate(grid: np.ndarray, rpm_axis: np.ndarray,
                    moves: dict[int, float]) -> np.ndarray:
    """A copy of the grid with the two loaded rows rewritten in named columns.

    Both loaded rows take the same value, which makes the result independent of
    where between 1200 and 1389 mg/stk a sample actually lands — the same reason
    R20 wrote the `Spark modifier` grid's top two rows identically.
    """
    out = grid.copy()
    for rpm, value in moves.items():
        column = int(np.flatnonzero(np.isclose(rpm_axis, rpm))[0])
        stored = quantise(value)
        if abs(stored - value) > 1e-9:
            print(f"    note: {value:.4f} at {rpm} rpm stores as {stored:.6f}")
        for row in (6, 7):
            if stored > out[row, column]:
                raise RuntimeError(
                    f"candidate leans out {rpm} rpm / row {row}: "
                    f"{out[row, column]:.4f} -> {stored:.4f}. Refusing to size "
                    "an enrichment that is a leanout."
                )
            out[row, column] = stored
    return out


def main() -> int:
    grid, rpm_axis, load_axis = base_grid()
    kept, _ = collect()
    pump = [s for s in kept if s.fuel == "plain 92"]

    rpm, load, logged, hpfp = [], [], [], []
    for s in pump:
        if "lambda_sp" not in s.data or "hpfp" not in s.data:
            continue
        m = loaded_mask(s.data)
        rpm.append(s.data["rpm"][m])
        load.append(s.data["airmass"][m] * 1000.0)
        logged.append(s.data["lambda_sp"][m])
        hpfp.append(s.data["hpfp"][m])
    rpm = np.concatenate(rpm); load = np.concatenate(load)
    logged = np.concatenate(logged); hpfp = np.concatenate(hpfp)
    good = np.isfinite(rpm) & np.isfinite(load) & np.isfinite(logged) & np.isfinite(hpfp)
    rpm, load, logged, hpfp = rpm[good], load[good], logged[good], hpfp[good]

    engaged = logged <= FULL_LOAD_LAMBDA_MAX
    excluded = 1.0 - engaged.mean()
    rpm, load, logged, hpfp = (rpm[engaged], load[engaged],
                               logged[engaged], hpfp[engaged])
    replay = lookup(grid, rpm_axis, load_axis, rpm, load)
    err = np.abs(replay - logged)
    median_abs = float(np.median(err))
    print(f"Replay of `Lambda SP` from `IP_LAMB_BAS_HPDI[1]` over {rpm.size} "
          f"loaded samples with full-load enrichment engaged: median |error| "
          f"{median_abs:.5f}, p95 {np.percentile(err, 95):.5f}, "
          f"max {err.max():.5f}")
    print(f"  {excluded:.2%} of loaded samples excluded as not engaged "
          f"(commanded lambda > {FULL_LOAD_LAMBDA_MAX:.2f})")
    if excluded > NOT_ENGAGED_MAX_FRACTION:
        raise SystemExit(
            f"{excluded:.1%} of loaded samples are not running full-load "
            f"enrichment, above the {NOT_ENGAGED_MAX_FRACTION:.0%} this gate "
            "allows; the loaded mask is not selecting WOT fuelling"
        )
    if median_abs > REPLAY_MEDIAN_ABS_MAX:
        raise SystemExit(
            f"replay median |error| {median_abs:.5f} exceeds "
            f"{REPLAY_MEDIAN_ABS_MAX:.3f} — the HPDI grid does not explain the "
            "logged setpoint, so nothing below is sized against the "
            "calibration the car actually runs"
        )

    focus = (rpm >= FOCUS[0]) & (rpm < FOCUS[1])
    print(f"\n{FOCUS[0]}-{FOCUS[1]} rpm holds {int(focus.sum())} loaded samples "
          f"({focus.sum() * 0.04:.1f} s); pump as logged: median "
          f"{np.median(hpfp[focus]):.1f} %, p95 {np.percentile(hpfp[focus], 95):.1f} %, "
          f"max {hpfp[focus].max():.1f} %")

    print(f"\n{'candidate':<22} {'lambda med':>10} {'vs EQT':>7} {'fuel':>7} "
          f"{'HPFP med':>9} {'HPFP p95':>9} {'HPFP max':>9} "
          f"{'2x med':>7} {'2x p95':>7} {'2x max':>7}")
    for label, moves in CANDIDATES.items():
        candidate = apply_candidate(grid, rpm_axis, moves)
        new = lookup(candidate, rpm_axis, load_axis, rpm, load)
        ratio = replay / new
        scaled = hpfp * ratio
        # The wrong-signed / inert case: every slot ends up carrying the
        # enrichment twice over, so the pump has to survive twice the delta.
        twice = {k: 2.0 * quantise(v) - float(grid[7, int(np.flatnonzero(
            np.isclose(rpm_axis, k))[0])]) for k, v in moves.items()}
        doubled = hpfp * (replay / lookup(
            apply_candidate(grid, rpm_axis, twice) if twice else grid,
            rpm_axis, load_axis, rpm, load))
        f = focus
        print(f"{label:<22} {np.median(new[f]):>10.4f} "
              f"{np.median(new[f]) - 0.8700:>+7.4f} "
              f"{np.median(ratio[f]) - 1.0:>+6.1%} "
              f"{np.median(scaled[f]):>9.1f} {np.percentile(scaled[f], 95):>9.1f} "
              f"{scaled[f].max():>9.1f} "
              f"{np.median(doubled[f]):>7.1f} {np.percentile(doubled[f], 95):>7.1f} "
              f"{doubled[f].max():>7.1f}")

    print("\nPer-band effect of the chosen candidate, all bands "
          "(the enrichment must not reach a band the pump cannot serve):")
    chosen = apply_candidate(grid, rpm_axis, CANDIDATES["shipped in R23"])
    new = lookup(chosen, rpm_axis, load_axis, rpm, load)
    scaled = hpfp * (replay / new)
    print(f"{'band':>12} {'logged':>8} {'grid':>8} {'resid':>7} {'R23':>8} "
          f"{'fuel':>7} {'HPFP now':>9} {'HPFP R23':>9} {'p95 R23':>9}")
    for lo, hi in BANDS:
        m = (rpm >= lo) & (rpm < hi)
        if not m.any():
            continue
        # `logged` is the commanded setpoint as the ECU reported it; `grid` is
        # what the base grid alone asks for; `resid` is the gap between them.
        # `R23` applies the grid's own ratio to the logged value, so a band the
        # grid does not touch reads unchanged rather than inheriting `resid`.
        ratio = replay[m] / new[m]
        print(f"  {lo:>5}-{hi:<5} {np.median(logged[m]):>8.4f} "
              f"{np.median(replay[m]):>8.4f} "
              f"{np.median(replay[m] - logged[m]):>+7.4f} "
              f"{np.median(logged[m] / ratio):>8.4f} "
              f"{np.median(ratio) - 1.0:>+6.1%} "
              f"{np.median(hpfp[m]):>9.1f} {np.median(scaled[m]):>9.1f} "
              f"{np.percentile(scaled[m], 95):>9.1f}")
    print("\nBOOST PROPOSAL — what it would take to fuel 3000-3500 rpm the way "
          "EQT does")
    print("Not built into R23; see Tunes/README_NEXT_STEPS.md. Sized here so the "
          "\nproposal is reproducible rather than asserted.")
    at_eqt = lookup(apply_candidate(grid, rpm_axis, {3008: EQT_FOCUS_LAMBDA}),
                    rpm_axis, load_axis, rpm, load)
    f = (rpm >= FOCUS[0]) & (rpm < FOCUS[1])
    # Per sample, not a band median scaled at the end: the samples that push the
    # pump hardest are not the ones carrying the median enrichment, so scaling a
    # percentile by a median ratio understates the answer. (It did, by five
    # points, until this was written the other way round.)
    scaled_at_eqt = hpfp * (replay / at_eqt)
    ratio = float(np.median((replay / at_eqt)[f]))
    p99_now = float(np.percentile(hpfp[f], 99))
    p99_at_eqt = float(np.percentile(scaled_at_eqt[f], 99))
    #: Fuel flow is airmass / lambda, and the pump moves fuel, so holding the
    #: pump where it is while lambda goes richer means airmass has to come down
    #: by the same factor the fuel went up by.
    airmass_scale = PUMP_GATE_P99 / p99_at_eqt
    print(f"  commanded lambda in band: {np.median(replay[f]):.4f} now, "
          f"{np.median(at_eqt[f]):.4f} at EQT's 0.870 in the 3008 column")
    print(f"  fuel required: {ratio - 1.0:+.1%}; HPFP p99 {p99_now:.1f} % -> "
          f"{p99_at_eqt:.1f} %, against a {PUMP_GATE_P99:.0f} % gate")
    print(f"  airmass must fall {1.0 - airmass_scale:.1%} for that to fit, i.e. "
          f"the boost cap scaled by {airmass_scale:.3f} in the band:")
    cal = CalFile.open(str(SWITCH_XDF_PATH), str(R22_BIN),
                       structure=structure_of(R22_BIN))
    view = cal.get(int(AGGRESSIVE_SLOT_UID, 16))
    cap = np.asarray(view.values, dtype=np.float64)[0]
    cap_rpm = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
    print(f"    {'rpm':>7} {'R22 hPa':>9} {'proposed':>9} {'delta psi':>10}")
    for value, hpa in zip(cap_rpm, cap):
        if not FOCUS[0] <= value < FOCUS[1] + 100:
            continue
        proposed = hpa * airmass_scale
        print(f"    {value:>7.0f} {hpa:>9.0f} {proposed:>9.0f} "
              f"{(proposed - hpa) / 68.9476:>10.2f}")
    print("  The cost is low-end torque on the everyday map, which is exactly "
          "what\n  the aggressive slot exists for — so this is a trade to take "
          "deliberately,\n  not a correction to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
