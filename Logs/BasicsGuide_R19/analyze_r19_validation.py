"""Validate MainTune R19 against the cool-air R18 baseline.

R19 is a paired knock-protection and wastegate-feedforward revision:

1. ``IP_IGA_DEC_KNK`` - Spark retard at recognised knocking, and the two
   companion knock-recovery tables, were changed to make a single detected
   event cost about -1.50 deg CRK instead of -3.00 and to hand the timing back
   faster, so the cut stops carrying across an upshift.
2. ``IP_FAC_BPA_SP[0]`` / ``[1]`` - Map for boost pressure actuator setpoint
   was re-breakpointed on its intake-flow-factor axis and two cells were
   closed, to hand the 5000-6000 rpm closed loop about 2.5 actuator-position
   points of feedforward it was having to wind in on the integrator.
   The nine ``IP_IGA_BAS_IVVT_VVL_PORT_L`` base ignition maps are untouched.

This script answers the five measurements the R19 revision-log gate names:

1. Recovery carry - time from knock onset back to zero retard, and whether the
   cut still spans an upshift.
2. Cut depth - should be about -1.50 deg per event, not -3.00.
3. Event rate and character - a shallower, faster-recovering cut returns the
   engine to the knock boundary sooner, so rate is expected to rise; character
   (simultaneity, ramping, accumulation) is what must not change.
4. Boost tracking at 5000-6000 rpm - PUT error and ``WG I Value`` against the
   R18 cool session, with ``WG Pos Base`` read directly so a feedforward gain
   that never reaches the flap is distinguishable from one that does.
5. Redline over-delivery - predicted to grow from +1.7 to about +2.4 kPa.

It also re-checks that delivered base timing (``Ign Table``) is unchanged from
R18, which is the check that R19 did not quietly stack a timing change onto a
knock change.

The R18 comparison set is the 2026-08-28 cool-air session only (ambient 19.5 C),
because the R19 session was logged at 16.5 C; the 2026-08-27 hot session is not
a matched-air control.

Every input log uses ``Gear (gear)``, so the logged value is the actual gear and
needs no offset. Gear-weighted power channels are trimmed to the pull's own gear.

Usage:
    ../../Code/.venv/bin/python analyze_r19_validation.py
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
R18_DIR = HERE.parent / "BasicsGuide_R18"
PLOT_DIR = HERE / "plots"
sys.path.insert(0, str(R18_DIR))

from analyze_r18_validation import (  # noqa: E402
    AIR_GAS_CONSTANT,
    CD,
    CRR,
    DERIVATIVE_WINDOW_S,
    DRIVELINE_EFFICIENCY,
    FRONTAL_AREA_M2,
    GRAVITY,
    MASS_FACTOR,
    MASS_KG,
    WATTS_TO_HP,
    contiguous_runs,
    local_slope,
    style_axis,
)

SAMPLE_S = 0.04

# The 2026-08-28 cool-air R18 session. The 2026-08-27 hot session is excluded.
R18_TAGS = ("12_07_40", "12_08_37", "12_10_17", "12_11_32",
            "12_13_03", "12_14_04", "12_17_04", "12_18_28")
R19_TAGS = ("10_26_12", "10_27_59", "10_28_58", "10_30_33",
            "10_31_49", "10_33_08", "10_34_08", "10_35_25")

BANDS = ((3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6500))
REDLINE_BAND = (6200, 6500)

# A cylinder is "in a knock event" at or beyond this retard.
KNOCK_EVENT_DEG = -1.0
# Contiguous knock samples separated by fewer than this many rows are one event.
KNOCK_GAP_ROWS = 10
# Retard shallower than this counts as recovered to zero.
RECOVERED_DEG = -0.05
# Half-width of the window examined around an onset for co-cylinder retard.
EVENT_HALF_ROWS = 5

CHANNELS = {
    "time": "Time",
    "rpm": "Engine Speed (rpm)",
    "pedal": "Pedal Pos (%)",
    "tps": "TPS (%)",
    "gear": "Gear (gear)",
    "ambient": "Ambient Press (kpa)",
    "ambient_temp": "Ambient Temp (°C)",
    "put": "PUT (kpa)",
    "put_sp": "PUT SP (kpa)",
    "airmass": "Airmass (g/stk)",
    "wg_i": "WG I Value (%)",
    "wg_pd": "WG P-D Value (%)",
    "wg_pos_base": "WG Pos Base (%)",
    "wg_pos_final": "WG Pos Final (%)",
    "intake_ff": "Intake Flow Fact ()",
    "exh_ff": "Exh Flow Factor ()",
    "lambda": "Lambda (l)",
    "lambda_sp": "Lambda SP (l)",
    "hpfp": "HPFP Eff Vol (%)",
    "lpfp": "LPFP Duty (%)",
    "turbo": "Turbo Speed (rpm)",
    "torque": "Torque (Nm)",
    "torque_req": "Torque Req (Nm)",
    "torque_lim": "Torque Lim ()",
    "ign": "Ign Avg (°)",
    "ign_table": "Ign Table (°)",
    "iat": "IAT (°C)",
    "knock_avg": "Knock Avg (°)",
    "knock_1": "Knock Cyl 1 (°)",
    "knock_2": "Knock Cyl 2 (°)",
    "knock_3": "Knock Cyl 3 (°)",
    "knock_4": "Knock Cyl 4 (°)",
    "vehicle_speed": "Vehicle Speed (km/h)",
    "wheel_rl": "Wheel Speed RL (km/h)",
    "wheel_rr": "Wheel Speed RR (km/h)",
    "calc_hp": "Calc HP (hp)",
}

KNOCK_KEYS = ("knock_1", "knock_2", "knock_3", "knock_4")


def load(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {
        key: np.asarray([float(row[column]) for row in rows], dtype=float)
        for key, column in CHANNELS.items()
    }


def load_tagged(folder: Path, tags: tuple[str, ...]) -> list[tuple[str, dict[str, np.ndarray]]]:
    out = []
    for tag in tags:
        matches = list(folder.glob(f"simostools-*{tag}.csv"))
        if len(matches) != 1:
            raise RuntimeError(f"expected one log matching {tag} in {folder}, found {len(matches)}")
        out.append((tag, load(matches[0])))
    return out


def loaded_mask(data: dict[str, np.ndarray], gear: int | None = None) -> np.ndarray:
    """Loaded WOT samples. ``gear=None`` keeps every gear, so a cut that carries
    across an upshift stays inside the window."""
    mask = (
        (data["pedal"] >= 90.0)
        & (data["rpm"] >= 3000.0)
        & (data["airmass"] >= 0.9)
        & (data["tps"] >= 60.0)
    )
    if gear is not None:
        mask &= np.rint(data["gear"]) == gear
    return mask


def pull_gear(data: dict[str, np.ndarray]) -> int:
    """The gear the longest loaded run of this log sits in."""
    runs = contiguous_runs(loaded_mask(data))
    if not runs:
        return 0
    indices = max(runs, key=len)
    gears, counts = np.unique(np.rint(data["gear"][indices]), return_counts=True)
    return int(gears[np.argmax(counts)])


def knock_events(logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict]:
    """Enumerate loaded knock events across every gear, with recovery timing."""
    events: list[dict] = []
    for tag, data in logs:
        loaded = loaded_mask(data)
        for key in KNOCK_KEYS:
            retard = data[key]
            for run in contiguous_runs(loaded & (retard <= KNOCK_EVENT_DEG), KNOCK_GAP_ROWS):
                onset = int(run[0])
                worst = int(run[np.argmin(retard[run])])
                # Walk forward from the worst sample to the first recovery to zero.
                after = np.flatnonzero(retard[worst:] >= RECOVERED_DEG)
                recovered = int(worst + after[0]) if after.size else retard.size - 1
                lo = max(0, onset - EVENT_HALF_ROWS)
                hi = min(retard.size, onset + EVENT_HALF_ROWS + 1)
                window = slice(lo, hi)
                others = [
                    other for other in KNOCK_KEYS
                    if other != key and np.min(data[other][window]) <= KNOCK_EVENT_DEG
                ]
                span = slice(onset, recovered + 1)
                gears = np.unique(np.rint(data["gear"][span]))
                events.append({
                    "tag": tag,
                    "cylinder": int(key[-1]),
                    "onset_row": onset,
                    "onset_rpm": float(data["rpm"][onset]),
                    "worst_rpm": float(data["rpm"][worst]),
                    "worst_deg": float(retard[worst]),
                    "carry_s": float((recovered - onset) * SAMPLE_S),
                    "recovered": bool(after.size),
                    "spans_upshift": bool(gears.size > 1),
                    "gear": int(np.rint(data["gear"][onset])),
                    "samples": int(run.size),
                    "airmass": float(data["airmass"][onset] * 1000.0),
                    "iat": float(data["iat"][onset]),
                    "ign": float(data["ign"][onset]),
                    "ign_table": float(data["ign_table"][onset]),
                    "co_cylinders": others,
                    # Does retard deepen after onset (ramping) or decay monotonically?
                    "ramped": bool(worst > onset),
                    "indices": run,
                })
    return sorted(events, key=lambda event: event["onset_rpm"])


def print_knock_events(name: str, events: list[dict]) -> None:
    print(f"\n{name} loaded knock events (retard <= {KNOCK_EVENT_DEG:.1f} deg, all gears):")
    if not events:
        print("  none")
        return
    print("  file       g  cyl  onset rpm   worst        carry   upshift  airmass      IAT   ign/table  co-cyl")
    for event in events:
        co = ",".join(str(c) for c in event["co_cylinders"]) or "-"
        carry = f"{event['carry_s']:5.2f}s" + ("" if event["recovered"] else "+")
        print(
            f"  {event['tag']}  {event['gear']}   {event['cylinder']}   "
            f"{event['onset_rpm']:8.0f}  {event['worst_deg']:+5.2f}@{event['worst_rpm']:.0f}  "
            f"{carry}  {'YES' if event['spans_upshift'] else 'no ':>7s}  "
            f"{event['airmass']:6.0f} mg/stk  {event['iat']:4.1f}C  "
            f"{event['ign']:+5.1f}/{event['ign_table']:+5.1f}  {co}"
        )


def summarize_events(name: str, events: list[dict], logs) -> dict:
    """Depth, carry, rate and character, one row per session."""
    loaded_s = sum(float(loaded_mask(data).sum()) * SAMPLE_S for _, data in logs)
    depths = np.asarray([e["worst_deg"] for e in events]) if events else np.empty(0)
    carries = np.asarray([e["carry_s"] for e in events]) if events else np.empty(0)
    summary = {
        "name": name,
        "events": len(events),
        "loaded_s": loaded_s,
        "rate_per_min": len(events) / loaded_s * 60.0 if loaded_s else float("nan"),
        "median_depth": float(np.median(depths)) if depths.size else float("nan"),
        "worst_depth": float(np.min(depths)) if depths.size else float("nan"),
        "median_carry": float(np.median(carries)) if carries.size else float("nan"),
        "max_carry": float(np.max(carries)) if carries.size else float("nan"),
        "upshift_events": sum(1 for e in events if e["spans_upshift"]),
        "multi_cyl": sum(1 for e in events if e["co_cylinders"]),
        "ramped": sum(1 for e in events if e["ramped"]),
        "unrecovered": sum(1 for e in events if not e["recovered"]),
    }
    return summary


def print_summaries(rows: list[dict]) -> None:
    print("\nKnock character, cool-air sessions:")
    print("  session  events  loaded s  events/min  median depth  worst  median carry  max carry  spans upshift  multi-cyl  ramped  unrecovered")
    for row in rows:
        print(
            f"  {row['name']:7s}  {row['events']:6d}  {row['loaded_s']:8.1f}  "
            f"{row['rate_per_min']:10.2f}  {row['median_depth']:+12.2f}  "
            f"{row['worst_depth']:+5.2f}  {row['median_carry']:12.2f}  "
            f"{row['max_carry']:9.2f}  {row['upshift_events']:13d}  "
            f"{row['multi_cyl']:9d}  {row['ramped']:6d}  {row['unrecovered']:11d}"
        )


def band_stats(logs, gear: int) -> list[dict[str, float]]:
    """Pooled per-band means over clean loaded WOT in one gear."""
    pools = {key: [] for key in
             ("put_err", "wg_i", "wg_pd", "wg_pos_base", "wg_pos_final",
              "ign", "ign_table", "iat", "lambda", "lambda_sp", "intake_ff",
              "exh_ff", "turbo", "airmass", "knock_min")}
    out = []
    for lo, hi in BANDS:
        for key in pools:
            pools[key] = []
        for _, data in logs:
            mask = loaded_mask(data, gear) & (data["rpm"] >= lo) & (data["rpm"] < hi)
            if not mask.any():
                continue
            pools["put_err"].append(data["put"][mask] - data["put_sp"][mask])
            for key in ("wg_i", "wg_pd", "wg_pos_base", "wg_pos_final", "ign",
                        "ign_table", "iat", "lambda", "lambda_sp", "intake_ff",
                        "exh_ff", "turbo", "airmass"):
                pools[key].append(data[key][mask])
            pools["knock_min"].append(
                np.asarray([min(data[f"knock_{c}"][mask].min() for c in range(1, 5))])
            )
        if not pools["put_err"]:
            out.append(None)
            continue
        joined = {key: np.concatenate(values) for key, values in pools.items()}
        row = {"n": int(joined["put_err"].size)}
        for key, values in joined.items():
            row[key] = float(np.mean(values))
        row["knock_min"] = float(np.min(joined["knock_min"]))
        row["turbo"] = float(np.max(joined["turbo"]))
        out.append(row)
    return out


def print_band_compare(r18: list, r19: list, gear: int) -> None:
    print(f"\nGear {gear} loaded WOT, R18 cool session vs R19 (pooled per band):")
    print("  band          n18   n19   PUT err 18/19   delta   WG I 18/19    delta   WG base 18/19  delta   WG final 18/19  ign table 18/19  IAT 18/19")
    for (lo, hi), a, b in zip(BANDS, r18, r19):
        if a is None or b is None:
            print(f"  {lo}-{hi}  (insufficient samples)")
            continue
        print(
            f"  {lo}-{hi}  {a['n']:4d}  {b['n']:4d}  "
            f"{a['put_err']:+6.1f}/{b['put_err']:+6.1f}  {b['put_err'] - a['put_err']:+6.1f}  "
            f"{a['wg_i']:+5.1f}/{b['wg_i']:+5.1f}  {b['wg_i'] - a['wg_i']:+6.1f}  "
            f"{a['wg_pos_base']:5.1f}/{b['wg_pos_base']:5.1f}  {b['wg_pos_base'] - a['wg_pos_base']:+5.1f}  "
            f"{a['wg_pos_final']:5.1f}/{b['wg_pos_final']:5.1f}   "
            f"{a['ign_table']:+5.1f}/{b['ign_table']:+5.1f}    "
            f"{a['iat']:4.1f}/{b['iat']:4.1f}"
        )


def redline_stats(logs, gear: int) -> dict[str, float]:
    lo, hi = REDLINE_BAND
    errors, bases, integrals = [], [], []
    for _, data in logs:
        mask = loaded_mask(data, gear) & (data["rpm"] >= lo) & (data["rpm"] < hi)
        if not mask.any():
            continue
        errors.append(data["put"][mask] - data["put_sp"][mask])
        bases.append(data["wg_pos_base"][mask])
        integrals.append(data["wg_i"][mask])
    if not errors:
        return {"n": 0}
    return {
        "n": int(np.concatenate(errors).size),
        "put_err": float(np.mean(np.concatenate(errors))),
        "wg_pos_base": float(np.mean(np.concatenate(bases))),
        "wg_i": float(np.mean(np.concatenate(integrals))),
    }


def power_estimate(tag: str, data: dict[str, np.ndarray]) -> dict | None:
    gear = pull_gear(data)
    mask = loaded_mask(data, gear) & (data["rpm"] <= 6500.0)
    runs = contiguous_runs(mask)
    if not runs:
        return None
    indices = max(runs, key=len)
    if indices.size < 50 or np.ptp(data["rpm"][indices]) < 2500.0:
        return None

    # Reconstruct uniform 40-ms logging time; the absolute Time channel is
    # float32-quantized and unsuitable for a direct speed derivative.
    time = np.arange(data["rpm"].size, dtype=float) * SAMPLE_S
    rear_speed = 0.5 * (data["wheel_rl"] + data["wheel_rr"]) / 3.6
    vehicle_speed = data["vehicle_speed"] / 3.6
    speed = np.where(rear_speed > 1.0, rear_speed, vehicle_speed)
    acceleration = local_slope(time, speed, DERIVATIVE_WINDOW_S)
    density = (data["ambient"] * 1000.0) / (
        AIR_GAS_CONSTANT * (data["ambient_temp"] + 273.15)
    )
    aero_force = 0.5 * density * CD * FRONTAL_AREA_M2 * speed ** 2
    rolling_force = CRR * MASS_KG * GRAVITY
    wheel_force = MASS_KG * MASS_FACTOR * acceleration + aero_force + rolling_force
    wheel_hp = wheel_force * speed * WATTS_TO_HP
    edge = int(round((DERIVATIVE_WINDOW_S / 2.0) / SAMPLE_S))
    peak_indices = indices[edge:-edge] if indices.size > 2 * edge else indices
    return {
        "tag": tag,
        "gear": gear,
        "indices": indices,
        "rpm": data["rpm"][indices],
        "wheel_hp": wheel_hp[indices],
        "peak_wheel_hp": float(np.nanmax(wheel_hp[peak_indices])),
        "peak_crank_hp": float(np.nanmax(wheel_hp[peak_indices]) / DRIVELINE_EFFICIENCY),
        # Calc HP is gear-ratio weighted; trim to the pull's own gear before peaking.
        "peak_calc_hp": float(np.nanmax(data["calc_hp"][indices])),
    }


def print_power(name: str, logs) -> list[dict]:
    results = [r for tag, data in logs if (r := power_estimate(tag, data)) is not None]
    print(f"\n{name} F=ma estimates (trimmed to each pull's own gear):")
    for result in results:
        print(
            f"  {result['tag']} (gear {result['gear']}): "
            f"wheel {result['peak_wheel_hp']:.0f} hp, crank {result['peak_crank_hp']:.0f} hp, "
            f"Calc HP {result['peak_calc_hp']:.0f} hp"
        )
    third = [r for r in results if r["gear"] == 3]
    if third:
        peaks = np.asarray([r["peak_wheel_hp"] for r in third])
        print(f"  3rd-gear wheel mean {peaks.mean():.0f} hp, range {peaks.min():.0f}-{peaks.max():.0f} hp")
    return results


def plot_knock_and_boost(r18_events, r19_events, r18_bands, r19_bands) -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    fig = plt.figure(figsize=(13, 9))
    layout = fig.add_gridspec(2, 2, hspace=0.28, wspace=0.22)

    ax = fig.add_subplot(layout[0, 0])
    for events, colour, label in ((r18_events, "tab:blue", "R18 cool"),
                                  (r19_events, "tab:red", "R19")):
        if events:
            ax.scatter([e["onset_rpm"] for e in events], [e["worst_deg"] for e in events],
                       s=46, alpha=0.8, color=colour, label=label)
    ax.axhline(-1.5, color="0.4", linestyle="--", linewidth=1.0)
    ax.axhline(-3.0, color="0.4", linestyle=":", linewidth=1.0)
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Worst retard (°CRK)", fontweight="bold")
    ax.set_title("Knock event depth vs rpm")
    ax.legend(loc="lower right")
    style_axis(ax)

    ax = fig.add_subplot(layout[0, 1])
    for events, colour, label in ((r18_events, "tab:blue", "R18 cool"),
                                  (r19_events, "tab:red", "R19")):
        if events:
            ax.scatter([e["onset_rpm"] for e in events], [e["carry_s"] for e in events],
                       s=46, alpha=0.8, color=colour, label=label)
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Onset to zero retard (s)", fontweight="bold")
    ax.set_title("Recovery carry")
    ax.legend(loc="upper right")
    style_axis(ax)

    centres = [0.5 * (lo + hi) for lo, hi in BANDS]
    ax = fig.add_subplot(layout[1, 0])
    for bands, colour, label in ((r18_bands, "tab:blue", "R18 cool"),
                                 (r19_bands, "tab:red", "R19")):
        xs = [c for c, row in zip(centres, bands) if row]
        ys = [row["put_err"] for row in bands if row]
        ax.plot(xs, ys, marker="o", color=colour, label=label)
    ax.axhline(0.0, color="0.4", linewidth=1.0)
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("PUT − PUT SP (kPa)", fontweight="bold")
    ax.set_title("3rd-gear boost tracking")
    ax.legend(loc="lower left")
    style_axis(ax)

    ax = fig.add_subplot(layout[1, 1])
    for bands, colour, label in ((r18_bands, "tab:blue", "R18 cool"),
                                 (r19_bands, "tab:red", "R19")):
        xs = [c for c, row in zip(centres, bands) if row]
        ax.plot(xs, [row["wg_i"] for row in bands if row], marker="o",
                color=colour, label=f"{label} WG I")
        ax.plot(xs, [row["wg_pos_base"] for row in bands if row], marker="s",
                linestyle="--", color=colour, label=f"{label} WG base")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Wastegate position (%)", fontweight="bold")
    ax.set_title("Feedforward vs integral")
    ax.set_ylim(0.0, 78.0)
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    style_axis(ax)

    fig.suptitle("MainTune R19 vs R18 cool-air baseline", fontweight="bold")
    fig.savefig(PLOT_DIR / "r19_vs_r18.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    r18 = load_tagged(R18_DIR, R18_TAGS)
    r19 = load_tagged(HERE, R19_TAGS)

    print("Pull gears:")
    print("  R18 cool:", {tag: pull_gear(data) for tag, data in r18})
    print("  R19     :", {tag: pull_gear(data) for tag, data in r19})

    r18_events = knock_events(r18)
    r19_events = knock_events(r19)
    print_knock_events("R18 cool", r18_events)
    print_knock_events("R19", r19_events)
    print_summaries([summarize_events("R18", r18_events, r18),
                     summarize_events("R19", r19_events, r19)])

    r18_bands = band_stats(r18, 3)
    r19_bands = band_stats(r19, 3)
    print_band_compare(r18_bands, r19_bands, 3)

    r19_bands4 = band_stats(r19, 4)
    r18_bands4 = band_stats(r18, 4)
    print_band_compare(r18_bands4, r19_bands4, 4)

    print("\nRedline over-delivery, gear 3 (6200-6500 rpm):")
    for name, logs in (("R18 cool", r18), ("R19", r19)):
        row = redline_stats(logs, 3)
        if row["n"]:
            print(f"  {name:8s}  n={row['n']:4d}  PUT err {row['put_err']:+5.2f} kPa  "
                  f"WG base {row['wg_pos_base']:5.2f}%  WG I {row['wg_i']:+5.2f}%")
        else:
            print(f"  {name:8s}  no samples")

    print_power("R18 cool", r18)
    print_power("R19", r19)

    plot_knock_and_boost(r18_events, r19_events, r18_bands, r19_bands)
    print(f"\nwrote {PLOT_DIR / 'r19_vs_r18.png'}")


if __name__ == "__main__":
    main()
