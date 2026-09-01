"""Validate MainTune R20 against its AE5/AE6/AE7 logging gate.

R20 gives map slot 5 the same boost curve as slot 4 plus a patch-added
``Spark modifier`` ignition offset.  The requested within-session slot-4 / slot-5
A/B was not logged: all ten detected pulls are slot 5.  R19 is therefore used
only as a cross-session control, with day and fuel explicitly left as confounds.

The script answers:

1. AE5 timing delivery in actual 3rd gear and in true post-shift 4th-gear
   segments.  The modifier lands in ``Ign Avg``, not ``Ign Table``.
2. AE6 per-cylinder knock depth, ramping, simultaneous-cylinder samples, and
   chronology.  Both 3rd and post-shift 4th gear are included.
3. AE7 3rd-gear F=ma wheel power, trimmed to each pull's attributed gear.
4. The unchanged-boost control, using logged PUT setpoint and actual PUT.

It also demonstrates why the original timing residual model failed: ``Knock
Avg`` does not represent the pull-5 high-rpm event well, while the worst logged
per-cylinder correction does; and the 6.376-degree pull-7 outlier occurs in a
low-rpm combustion-mode / valve-lift transition outside the steady-WOT model.

Usage:
    ../../Code/.venv/bin/python analyze_r20_validation.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
R19_DIR = HERE.parent / "BasicsGuide_R19"
PLOT_DIR = HERE / "plots"
sys.path.insert(0, str(R19_DIR))

from analyze_r19_validation import (  # noqa: E402
    BANDS,
    CHANNELS as R19_CHANNELS,
    KNOCK_KEYS,
    R19_TAGS,
    SAMPLE_S,
    knock_events,
    loaded_mask,
    power_estimate,
    style_axis,
)

CHANNELS = dict(R19_CHANNELS)
CHANNELS.update({
    "comb_mode": "Comb Mode ()",
    "fuel_flow": "Fuel Flow (mg/stk)",
    "fuel_flow_sp": "Fuel Flow SP (mg/stk)",
    "valve_lift": "Valve Lift Pos ()",
})

RPM_AXIS = np.asarray(
    [400, 700, 1000, 1250, 1500, 1750, 2000, 2500,
     3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500],
    dtype=float,
)
LOAD_AXIS_MG = np.asarray(
    [79.99, 100.00, 150.02, 199.99, 250.01, 299.99, 350.01, 399.99,
     498.99, 599.98, 699.98, 800.02, 900.02, 1049.97, 1200.01, 1400.00],
    dtype=float,
)
MODIFIER_ROW = np.asarray(
    [1.125, 1.500, 2.250, 3.000, 3.750, 2.250, 1.500, 1.125],
    dtype=float,
)
MODIFIER_GRID = np.zeros((LOAD_AXIS_MG.size, RPM_AXIS.size), dtype=float)
MODIFIER_GRID[-2:, 8:] = MODIFIER_ROW


def load(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {
        key: np.asarray([float(row[column]) for row in rows], dtype=float)
        for key, column in CHANNELS.items()
    }


def load_tagged(folder: Path, tags: tuple[str, ...]) -> list[tuple[str, dict[str, np.ndarray]]]:
    logs = []
    for tag in tags:
        matches = list(folder.glob(f"simostools-*{tag}.csv"))
        if len(matches) != 1:
            raise RuntimeError(f"expected one log matching {tag}, found {len(matches)}")
        logs.append((tag, load(matches[0])))
    return logs


def load_r20() -> list[tuple[str, dict[str, np.ndarray]]]:
    return [(path.stem[-8:], load(path)) for path in sorted(HERE.glob("simostools-*.csv"))]


def modifier_lookup(airmass_mg: np.ndarray, rpm: np.ndarray) -> np.ndarray:
    """Bilinear lookup of R20's patch-added slot-5 ``Spark modifier`` grid."""
    load = np.clip(np.asarray(airmass_mg, dtype=float), LOAD_AXIS_MG[0], LOAD_AXIS_MG[-1])
    speed = np.clip(np.asarray(rpm, dtype=float), RPM_AXIS[0], RPM_AXIS[-1])
    iy = np.clip(np.searchsorted(LOAD_AXIS_MG, load) - 1, 0, LOAD_AXIS_MG.size - 2)
    ix = np.clip(np.searchsorted(RPM_AXIS, speed) - 1, 0, RPM_AXIS.size - 2)
    ty = (load - LOAD_AXIS_MG[iy]) / (LOAD_AXIS_MG[iy + 1] - LOAD_AXIS_MG[iy])
    tx = (speed - RPM_AXIS[ix]) / (RPM_AXIS[ix + 1] - RPM_AXIS[ix])
    lower = (1.0 - tx) * MODIFIER_GRID[iy, ix] + tx * MODIFIER_GRID[iy, ix + 1]
    upper = (1.0 - tx) * MODIFIER_GRID[iy + 1, ix] + tx * MODIFIER_GRID[iy + 1, ix + 1]
    return (1.0 - ty) * lower + ty * upper


def true_fourth_mask(data: dict[str, np.ndarray]) -> np.ndarray:
    """Post-shift 4th gear, excluding the DSG's early gear-channel flip.

    The channel changes to 4 while engine speed is still rising in physical
    3rd.  The first rpm trough in the following 1.4 seconds marks completion of
    the shift; only samples from that trough onward are true 4th gear.
    """
    nominal = loaded_mask(data, 4)
    indices = np.flatnonzero(nominal)
    if not indices.size:
        return np.zeros(data["rpm"].size, dtype=bool)
    first = int(indices[0])
    stop = min(data["rpm"].size, first + 35)
    trough = first + int(np.argmin(data["rpm"][first:stop]))
    after = np.zeros(data["rpm"].size, dtype=bool)
    after[trough:] = True
    return nominal & after


def timing_mask(data: dict[str, np.ndarray], gear: int) -> np.ndarray:
    mask = loaded_mask(data, 3) if gear == 3 else true_fourth_mask(data)
    mask &= data["rpm"] >= 3400.0
    mask &= data["comb_mode"] == 0.0
    mask &= data["valve_lift"] == 0.0
    for key in KNOCK_KEYS:
        mask &= data[key] >= -0.01
    return mask


def timing_bands(logs, gear: int, expected_modifier: bool) -> list[dict | None]:
    rows: list[dict | None] = []
    for lo, hi in BANDS:
        delivered, expected = [], []
        for _, data in logs:
            mask = timing_mask(data, gear) & (data["rpm"] >= lo) & (data["rpm"] < hi)
            if not mask.any():
                continue
            delivered.append(data["ign"][mask] - data["ign_table"][mask])
            if expected_modifier:
                expected.append(modifier_lookup(data["airmass"][mask] * 1000.0, data["rpm"][mask]))
            else:
                expected.append(np.zeros(mask.sum(), dtype=float))
        if not delivered:
            rows.append(None)
            continue
        observed = np.concatenate(delivered)
        model = np.concatenate(expected)
        rows.append({
            "n": observed.size,
            "observed": float(np.mean(observed)),
            "expected": float(np.mean(model)),
            "residual": float(np.mean(observed - model)),
        })
    return rows


def print_timing(r19, r20) -> None:
    for gear in (3, 4):
        base = timing_bands(r19, gear, False)
        boosted = timing_bands(r20, gear, True)
        print(f"\nGear {gear} knock-clean timing delivery (Ign Avg - Ign Table):")
        print("  band       n19   n20    R19    R20    gain  expected  residual")
        for (lo, hi), row19, row20 in zip(BANDS, base, boosted):
            if row19 is None or row20 is None:
                continue
            print(
                f"  {lo}-{hi}  {row19['n']:5d} {row20['n']:5d}  "
                f"{row19['observed']:+5.2f}  {row20['observed']:+5.2f}  "
                f"{row20['observed'] - row19['observed']:+5.2f}  "
                f"{row20['expected']:+8.2f}  {row20['residual']:+8.2f}"
            )


def timing_residual_probes(r20) -> None:
    by_tag = dict(r20)
    pull7 = by_tag["08_00_09"]
    base = pull7["ign_table"] + modifier_lookup(pull7["airmass"] * 1000.0, pull7["rpm"])
    residual = pull7["ign"] - base - pull7["knock_avg"]
    broad = loaded_mask(pull7, 3) & (pull7["airmass"] >= 0.9)
    stable = timing_mask(pull7, 3)
    broad_peak = int(np.flatnonzero(broad)[np.argmax(np.abs(residual[broad]))])
    print("\nTiming residual probes:")
    print(
        f"  08_00_09 broad-model max {residual[broad_peak]:+.3f} deg at "
        f"{pull7['rpm'][broad_peak]:.0f} rpm; combustion mode "
        f"{pull7['comb_mode'][broad_peak]:.0f}, valve lift {pull7['valve_lift'][broad_peak]:.0f}"
    )
    print(f"  08_00_09 steady-model max {np.max(np.abs(residual[stable])):.3f} deg")

    pull5 = by_tag["07_57_32"]
    event = (
        loaded_mask(pull5, 3)
        & (pull5["rpm"] >= 5450.0)
        & (pull5["rpm"] <= 6247.0)
    )
    base = pull5["ign_table"] + modifier_lookup(pull5["airmass"] * 1000.0, pull5["rpm"])
    avg_residual = pull5["ign"] - base - pull5["knock_avg"]
    worst_cylinder = np.min(np.column_stack([pull5[key] for key in KNOCK_KEYS]), axis=1)
    cylinder_residual = pull5["ign"] - base - worst_cylinder
    for label, values in (("Knock Avg", avg_residual[event]),
                          ("worst cylinder", cylinder_residual[event])):
        print(
            f"  pull 5 event with {label:14s}: rms {np.sqrt(np.mean(values ** 2)):.3f}, "
            f"bias {np.mean(values):+.3f}, max |residual| {np.max(np.abs(values)):.3f} deg"
        )


def knock_chronology(r20) -> tuple[list[dict], list[dict]]:
    pulls = [(tag, data) for tag, data in r20 if loaded_mask(data).any()]
    rows = []
    print("\nChronological knock, including 3rd and 4th gear:")
    print("  pull  file       loaded s  cyl-events  worst  same-sample two-cylinder")
    for index, (tag, data) in enumerate(pulls, 1):
        events = knock_events([(tag, data)])
        array = np.column_stack([data[key] for key in KNOCK_KEYS])
        simultaneous = loaded_mask(data) & ((array < -0.01).sum(axis=1) >= 2)
        row = {
            "index": index,
            "tag": tag,
            "loaded_s": float(loaded_mask(data).sum() * SAMPLE_S),
            "events": len(events),
            "worst": min((event["worst_deg"] for event in events), default=0.0),
            "simultaneous": int(simultaneous.sum()),
        }
        rows.append(row)
        print(
            f"  {index:4d}  {tag}  {row['loaded_s']:8.2f}  {row['events']:10d}  "
            f"{row['worst']:+5.2f}  {row['simultaneous']:26d}"
        )
    for label, half in (("first five", rows[:5]), ("last five", rows[5:])):
        events = sum(row["events"] for row in half)
        exposure = sum(row["loaded_s"] for row in half)
        print(f"  {label}: {events} events / {exposure:.2f} s = {60.0 * events / exposure:.2f} per loaded min")
    return rows, knock_events(pulls)


def print_power(r19, r20) -> tuple[list[dict], list[dict]]:
    all_results = []
    print("\n3rd-gear F=ma wheel power, trimmed to each pull's own gear:")
    print("  session  mean hp  range hp  pulls")
    for name, logs in (("R19", r19), ("R20", r20)):
        results = [result for tag, data in logs
                   if (result := power_estimate(tag, data)) is not None and result["gear"] == 3]
        peaks = np.asarray([result["peak_wheel_hp"] for result in results])
        print(f"  {name:7s}  {peaks.mean():7.0f}  {peaks.min():.0f}-{peaks.max():.0f}  {peaks.size:5d}")
        all_results.append(results)
    return all_results[0], all_results[1]


def boost_bands(logs) -> list[dict | None]:
    rows = []
    for lo, hi in BANDS:
        setpoint, actual = [], []
        for _, data in logs:
            mask = loaded_mask(data, 3) & (data["rpm"] >= lo) & (data["rpm"] < hi)
            if mask.any():
                setpoint.append(data["put_sp"][mask])
                actual.append(data["put"][mask])
        if not setpoint:
            rows.append(None)
            continue
        sp = np.concatenate(setpoint)
        put = np.concatenate(actual)
        rows.append({"n": sp.size, "sp": float(sp.mean()), "put": float(put.mean()),
                     "error": float(np.mean(put - sp))})
    return rows


def print_boost(r19, r20) -> tuple[list[dict | None], list[dict | None]]:
    rows19, rows20 = boost_bands(r19), boost_bands(r20)
    print("\n3rd-gear boost control, R19 slot 4 vs R20 slot 5:")
    print("  band       SP19    SP20   delta SP   PUT19   PUT20   error19  error20")
    for (lo, hi), a, b in zip(BANDS, rows19, rows20):
        if a is None or b is None:
            continue
        print(
            f"  {lo}-{hi}  {a['sp']:7.2f} {b['sp']:7.2f}  {b['sp'] - a['sp']:+8.2f}  "
            f"{a['put']:7.2f} {b['put']:7.2f}  {a['error']:+7.2f}  {b['error']:+7.2f}"
        )
    return rows19, rows20


def lambda_probe(r20) -> None:
    tag, data = next((tag, data) for tag, data in r20 if tag == "07_55_19")
    error = data["lambda"] - data["lambda_sp"]
    mask = loaded_mask(data, 3) & (data["torque"] >= 250.0) & (error > 0.05)
    indices = np.flatnonzero(mask)
    print("\nLambda High probe:")
    print(
        f"  {tag}: {indices.size} samples ({indices.size * SAMPLE_S:.2f} s), "
        f"{data['rpm'][indices].min():.0f}-{data['rpm'][indices].max():.0f} rpm, "
        f"max error {error[indices].max():+.3f}; fuel flow actual-minus-SP "
        f"{np.min(data['fuel_flow'][indices] - data['fuel_flow_sp'][indices]):+.2f} to "
        f"{np.max(data['fuel_flow'][indices] - data['fuel_flow_sp'][indices]):+.2f} mg/stk"
    )


def plot_validation(r19, r20, knock_rows, power19, power20, boost19, boost20) -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    centres = np.asarray([0.5 * (lo + hi) for lo, hi in BANDS])

    ax = axes[0, 0]
    for gear, marker in ((3, "o"), (4, "s")):
        rows = timing_bands(r20, gear, True)
        x = [centre for centre, row in zip(centres, rows) if row]
        observed = [row["observed"] for row in rows if row]
        expected = [row["expected"] for row in rows if row]
        ax.plot(x, observed, marker=marker, label=f"R20 gear {gear} observed")
        ax.plot(x, expected, marker=marker, linestyle="--", label=f"gear {gear} model")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Ign Avg - Ign Table (°CRK)", fontweight="bold")
    ax.set_title("Slot-5 modifier delivery, knock-clean samples")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[0, 1]
    x = [row["index"] for row in knock_rows]
    ax.bar(x, [row["events"] for row in knock_rows], color="tab:red", alpha=0.72)
    ax.set_xlabel("Chronological pull number", fontweight="bold")
    ax.set_ylabel("Cylinder-events", fontweight="bold")
    ax.set_title("Knock does not decline monotonically through the drive")
    ax.set_xticks(x)
    style_axis(ax)

    ax = axes[1, 0]
    for name, results, colour in (("R19", power19, "tab:blue"),
                                  ("R20", power20, "tab:orange")):
        peaks = [result["peak_wheel_hp"] for result in results]
        ax.scatter(np.arange(1, len(peaks) + 1), peaks, label=name, color=colour, s=46)
        ax.axhline(np.mean(peaks), color=colour, linestyle="--", linewidth=1.2)
    ax.set_xlabel("Qualifying 3rd-gear pull", fontweight="bold")
    ax.set_ylabel("Peak F=ma wheel power (hp)", fontweight="bold")
    ax.set_title("Cross-session power; fuel and day are confounds")
    ax.legend()
    style_axis(ax)

    ax = axes[1, 1]
    for name, rows, colour in (("R19 slot 4", boost19, "tab:blue"),
                               ("R20 slot 5", boost20, "tab:orange")):
        ax.plot(centres, [row["error"] for row in rows], marker="o", label=name, color=colour)
    ax.axhline(0.0, color="0.4", linewidth=1.0)
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("PUT - PUT SP (kPa)", fontweight="bold")
    ax.set_title("Boost tracking with matched setpoint curves")
    ax.legend()
    style_axis(ax)

    fig.suptitle("MainTune R20 validation", fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r20_validation.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_knock_traces(r20) -> None:
    by_tag = dict(r20)
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=False)
    for ax, tag in zip(axes, ("07_57_32", "08_01_14")):
        data = by_tag[tag]
        mask = loaded_mask(data)
        for cylinder, key in enumerate(KNOCK_KEYS, 1):
            ax.plot(data["rpm"][mask], data[key][mask], label=f"Cylinder {cylinder}")
        ax.axhline(-1.5, color="0.3", linestyle="--", linewidth=1.0,
                   label="R20 stop line")
        ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
        ax.set_ylabel("Knock correction (°CRK)", fontweight="bold")
        ax.set_title(f"{tag}: 3rd gear and logged 4th-gear carry")
        ax.legend(ncol=3, fontsize=8)
        style_axis(ax)
    fig.suptitle("R20 per-cylinder knock traces", fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r20_knock_traces.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_cumulative_knock_events(r20) -> None:
    """Plot accumulated cylinder-retard events against loaded-WOT exposure.

    The horizontal axis advances only during ``loaded_mask`` samples.  Each
    vertical step is one per-cylinder event returned by ``knock_events``:
    retard at or below -1.0 deg, with short gaps merged according to the
    session's established event definition.
    """
    PLOT_DIR.mkdir(exist_ok=True)
    pulls = [(tag, data) for tag, data in r20 if loaded_mask(data).any()]
    events_by_tag = {
        tag: len(knock_events([(tag, data)]))
        for tag, data in pulls
    }
    cumulative_wot_s = [0.0]
    cumulative_events = [0]
    labels = []
    for index, (tag, data) in enumerate(pulls, 1):
        cumulative_wot_s.append(cumulative_wot_s[-1] + loaded_mask(data).sum() * SAMPLE_S)
        cumulative_events.append(cumulative_events[-1] + events_by_tag[tag])
        labels.append((cumulative_wot_s[-1], cumulative_events[-1], index))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.step(cumulative_wot_s, cumulative_events, where="post", color="tab:red",
            linewidth=2.2)
    ax.scatter(cumulative_wot_s[1:], cumulative_events[1:], color="tab:red", zorder=3)
    for x, y, index in labels:
        ax.annotate(str(index), (x, y), xytext=(0, 7), textcoords="offset points",
                    ha="center", fontsize=8)
    ax.set_xlabel("Cumulative loaded-WOT time (s)", fontweight="bold")
    ax.set_ylabel("Cumulative cylinder knock-retard events", fontweight="bold")
    ax.set_title("R20 cumulative knock-retard events vs loaded-WOT time")
    style_axis(ax)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r20_cumulative_knock_events_vs_wot_time.png", dpi=150,
                bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    r19 = load_tagged(R19_DIR, R19_TAGS)
    r20 = load_r20()
    print_timing(r19, r20)
    timing_residual_probes(r20)
    knock_rows, _ = knock_chronology(r20)
    power19, power20 = print_power(r19, r20)
    boost19, boost20 = print_boost(r19, r20)
    lambda_probe(r20)
    plot_validation(r19, r20, knock_rows, power19, power20, boost19, boost20)
    plot_knock_traces(r20)
    plot_cumulative_knock_events(r20)
    print(f"\nwrote {PLOT_DIR / 'r20_validation.png'}")
    print(f"wrote {PLOT_DIR / 'r20_knock_traces.png'}")
    print(f"wrote {PLOT_DIR / 'r20_cumulative_knock_events_vs_wot_time.png'}")


if __name__ == "__main__":
    main()
