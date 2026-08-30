"""Which base ignition map does the ECU actually deliver at WOT?

The R20 plan needs this. Its per-slot ``Spark modifier`` guard (KTD3) is a
ceiling on **delivered** timing -- base + modifier -- so it has to read the base
map the ECU is really on at wide-open throttle. There are 36 candidates:
``IP_IGA_BAS_IVVT_VVL_PORT_[HL][STND|LFT_1][i][e]`` -- Basic ignition angle maps
for the two port-flap positions, two valve-lift curves, and a 3x3 grid of
intake/exhaust cam-phasing interpolation nodes.

The method is to simulate the ECU's own bilinear lookup on each candidate at
every WOT sample's (rpm, airmass) and compare the result to the logged
``Ign Table`` channel, which reports the base-table output. The operative map is
the one whose residual collapses; a wrong map lands degrees away.

Two of the four family axes are settled by the logs directly rather than by
fitting -- ``Port Flap Pos`` and ``Valve Lift Pos`` are logged channels, and at
WOT they are pinned. Only the cam-node pair ``[i][e]`` has to be fitted, and
because the ECU *interpolates between* those nine maps rather than selecting
one, the honest answer could have been a blend. It is not: on this bin all nine
cam-node grids of a family are byte-identical, so the cam-phasing index cannot
change the answer and no blend has to be resolved.

Run from this folder:

    ../../Code/.venv/bin/python find_operative_ign_map.py
"""

from __future__ import annotations

import csv
import glob
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Code"))

from simoscal import CalFile  # noqa: E402
from simoscal.checksum import SC8S50_STRUCTURE  # noqa: E402
from simoscal.tune.profile import resolve  # noqa: E402
from simoscal.tune.profiles import SC8S50  # noqa: E402

#: The bin that was flashed for these logs, and the definition it was cut from.
R19_BIN = (
    Path(__file__).resolve().parents[2]
    / "Tunes/MainTune/MainTune_out/R19_20260830-074033/Patched_259L_R19.bin"
)
BASE_XDF = Path(__file__).resolve().parents[2] / "Code/xdf/SC8S50.V1.0.xdf"

#: Log channels this analysis reads, by the header text SimosTools writes.
RPM = "Engine Speed (rpm)"
AIRMASS = "Airmass (g/stk)"
IGN_TABLE = "Ign Table (°)"
PEDAL = "Pedal Pos (%)"
PORT_FLAP = "Port Flap Pos (%)"
VALVE_LIFT = "Valve Lift Pos ()"
INTAKE_CAM = "Intake Cam Pos (°)"
EXH_CAM = "Exh Cam Position (°)"
GEAR = "Gear (gear)"

CHANNELS = (RPM, AIRMASS, IGN_TABLE, PEDAL, PORT_FLAP, VALVE_LIFT,
            INTAKE_CAM, EXH_CAM, GEAR)

#: WOT, and clear of the low-load corner where the map is flat and tells us
#: nothing: pedal pinned, on boost, and above the torque-converter region.
WOT_PEDAL_PCT = 95.0
WOT_MIN_RPM = 2500.0
WOT_MIN_AIRMASS_G = 0.80

#: The nine PORT_L[STND] maps, as the profile names them.
CAM_NODES = tuple((i, e) for i in range(3) for e in range(3))


def load(path: Path) -> dict[str, np.ndarray]:
    columns: dict[str, list[float]] = {c: [] for c in CHANNELS}
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            for channel in CHANNELS:
                try:
                    columns[channel].append(float(row[channel]))
                except (TypeError, ValueError, KeyError):
                    columns[channel].append(np.nan)
    return {c: np.asarray(v, dtype=float) for c, v in columns.items()}


def load_folder(folder: Path) -> dict[str, np.ndarray]:
    logs = [load(Path(p)) for p in sorted(glob.glob(str(folder / "simostools-*.csv")))]
    if not logs:
        raise SystemExit(f"no simostools-*.csv in {folder}")
    return {c: np.concatenate([lg[c] for lg in logs]) for c in CHANNELS}


def wot_mask(data: dict[str, np.ndarray]) -> np.ndarray:
    finite = np.isfinite(data[RPM]) & np.isfinite(data[AIRMASS]) & np.isfinite(data[IGN_TABLE])
    return (
        finite
        & (data[PEDAL] > WOT_PEDAL_PCT)
        & (data[RPM] > WOT_MIN_RPM)
        & (data[AIRMASS] > WOT_MIN_AIRMASS_G)
    )


def bilinear(grid: np.ndarray, x_axis: np.ndarray, y_axis: np.ndarray,
             x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """The ECU's own lookup: bilinear inside the grid, clamped at the edges.

    Vectorised over samples. ``grid`` is indexed ``[y, x]`` -- rows are the Y
    (airmass) breakpoints, columns the X (rpm) breakpoints, which is how both
    the XDF and :mod:`simoscal` lay these out.
    """
    xi = np.clip(np.searchsorted(x_axis, x) - 1, 0, len(x_axis) - 2)
    yi = np.clip(np.searchsorted(y_axis, y) - 1, 0, len(y_axis) - 2)
    tx = np.clip((x - x_axis[xi]) / (x_axis[xi + 1] - x_axis[xi]), 0.0, 1.0)
    ty = np.clip((y - y_axis[yi]) / (y_axis[yi + 1] - y_axis[yi]), 0.0, 1.0)
    return (
        grid[yi, xi] * (1 - tx) * (1 - ty)
        + grid[yi, xi + 1] * tx * (1 - ty)
        + grid[yi + 1, xi] * (1 - tx) * ty
        + grid[yi + 1, xi + 1] * tx * ty
    )


def read_maps() -> tuple[dict[tuple[int, int], np.ndarray], np.ndarray, np.ndarray]:
    """The nine PORT_L[STND] grids plus the rpm and airmass axes they share."""
    cal = CalFile.open(str(BASE_XDF), str(R19_BIN), structure=SC8S50_STRUCTURE)
    resolved = resolve(SC8S50, cal)
    grids: dict[tuple[int, int], np.ndarray] = {}
    x_axis = y_axis = None
    for i, e in CAM_NODES:
        view = resolved.view(f"ignition_base_vvl0_i{i}_e{e}")
        grids[(i, e)] = np.asarray(view.values, dtype=float)
        axes = {which: np.asarray(view.axis_values(which), dtype=float).ravel()
                for which in ("x", "y")}
        if x_axis is None:
            x_axis, y_axis = axes["x"], axes["y"]
        else:
            assert np.array_equal(x_axis, axes["x"]), "the nine must share one rpm axis"
            assert np.array_equal(y_axis, axes["y"]), "the nine must share one airmass axis"
    return grids, x_axis, y_axis


def residual_stats(predicted: np.ndarray, actual: np.ndarray) -> dict[str, float]:
    error = predicted - actual
    return {
        "mean": float(np.mean(error)),
        "median": float(np.median(error)),
        "rms": float(np.sqrt(np.mean(error ** 2))),
        "p95_abs": float(np.percentile(np.abs(error), 95)),
        "max_abs": float(np.max(np.abs(error))),
    }


def main() -> None:
    folder = Path(__file__).resolve().parent
    data = load_folder(folder)
    wot = wot_mask(data)

    print(f"{wot.sum()} WOT samples of {len(wot)} across "
          f"{len(glob.glob(str(folder / 'simostools-*.csv')))} logs\n")

    print("Family axes, settled from logged channels rather than fitted:")
    for label, channel in (("Port flap", PORT_FLAP), ("Valve lift", VALVE_LIFT)):
        values = data[channel][wot]
        values = values[np.isfinite(values)]
        unique, counts = np.unique(np.round(values, 2), return_counts=True)
        order = np.argsort(-counts)
        share = counts[order[0]] / counts.sum() * 100
        top = ", ".join(f"{unique[k]:g} ({counts[k] / counts.sum() * 100:.1f}%)"
                        for k in order[:3])
        print(f"  {label:11s} {top}   -> dominant value holds {share:.1f}% of WOT")
    for label, channel in (("Intake cam", INTAKE_CAM), ("Exhaust cam", EXH_CAM)):
        values = data[channel][wot]
        values = values[np.isfinite(values)]
        print(f"  {label:11s} {values.min():7.2f} .. {values.max():7.2f} deg, "
              f"mean {values.mean():6.2f}")

    grids, x_axis, y_axis = read_maps()
    rpm = data[RPM][wot]
    airmass_mg = data[AIRMASS][wot] * 1000.0
    actual = data[IGN_TABLE][wot]

    predictions = {
        node: bilinear(grid, x_axis, y_axis, rpm, airmass_mg)
        for node, grid in grids.items()
    }
    #: Any node will do once they are shown identical; [0][0] is the one the
    #: profile lists first and the one this script quotes throughout.
    best_guess = (0, 0)

    print("\nAre the nine cam-node grids distinguishable at all?")
    reference = grids[(0, 0)]
    identical = all(np.array_equal(reference, grids[n]) for n in CAM_NODES)
    print(f"  all nine PORT_L[STND][i][e] byte-identical: {identical}")
    if identical:
        print("  -> the cam-phasing index cannot change delivered timing on this")
        print("     bin, so the guard needs no cam state and no blend.")

    print("\nResidual of the map lookup against the logged Ign Table (deg CRK),")
    print("split by the one family axis that is not pinned at WOT:")
    lift = np.round(data[VALVE_LIFT][wot])
    for value, family in ((0, "STND  (the 9 mapped grids)"), (1, "LFT_1 (a different family)")):
        selected = lift == value
        if not selected.any():
            continue
        stats = residual_stats(predictions[best_guess][selected], actual[selected])
        print(f"  lift={value} {family:28s} n={selected.sum():5d}  "
              f"mean {stats['mean']:+7.3f}  rms {stats['rms']:6.3f}  "
              f"p95|e| {stats['p95_abs']:6.3f}")
    print("  The LFT_1 rows missing by degrees is the control: a wrong map in this")
    print("  family does not fit, so the STND fit is not fitting noise.")

    print("\nLogged vs looked-up by rpm band, STND only, above 1150 mg/stk:")
    print(f"  {'rpm band':>13} {'n':>5} {'logged':>8} {'map':>8} {'diff':>8}")
    stnd = (lift == 0) & (airmass_mg > 1150.0)
    for low, high in ((2900, 3200), (3400, 3700), (3900, 4200), (4400, 4700),
                      (4900, 5200), (5400, 5700), (5900, 6200), (6300, 6700)):
        selected = stnd & (rpm >= low) & (rpm < high)
        if selected.sum() < 5:
            print(f"  {low:5d}-{high:<7d} {selected.sum():5d}  (too few)")
            continue
        logged = float(np.mean(actual[selected]))
        looked_up = float(np.mean(predictions[best_guess][selected]))
        print(f"  {low:5d}-{high:<7d} {selected.sum():5d} {logged:8.2f} "
              f"{looked_up:8.2f} {logged - looked_up:+8.3f}")

    print("\nHoldout: the same map re-scored on each log on its own,")
    print("STND samples included as logged (a pull that touches LFT_1 shows it).")
    for path in sorted(glob.glob(str(folder / "simostools-*.csv"))):
        one = load(Path(path))
        mask = wot_mask(one)
        if mask.sum() < 20:
            print(f"  {Path(path).name}: {mask.sum()} WOT samples, skipped")
            continue
        predicted = bilinear(grids[best_guess], x_axis, y_axis,
                             one[RPM][mask], one[AIRMASS][mask] * 1000.0)
        stats = residual_stats(predicted, one[IGN_TABLE][mask])
        print(f"  {Path(path).name}: n={mask.sum():4d}  "
              f"mean {stats['mean']:+.3f}  rms {stats['rms']:.3f}  "
              f"max|e| {stats['max_abs']:.3f}")


if __name__ == "__main__":
    main()
