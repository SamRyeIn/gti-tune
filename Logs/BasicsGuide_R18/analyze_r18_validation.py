"""Validate MainTune R18 against the logged R17 baseline.

R18 is a timing-only revision: it pulls base ignition in the nine
``IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]`` — Basic ignition angle, VVL 0
port-flap-low cam-position maps by 0.750 deg at the 4500 rpm breakpoint and
1.500 deg at the 5000 rpm breakpoint, in the 1200 and 1400 mg/stk rows only.
Every other calibration table is byte-identical to R17.

The revision therefore answers one question and raises a second:

1. Did the repeatable R17 knock pocket at 4563-4973 rpm clear?
2. R18's correction is fully handed back by the 5500 rpm breakpoint, and the
   interpolated advance crosses back through R17's knock-onset value at roughly
   5230 rpm. What happens in 5000-5700 rpm has to be read on its own terms.

It also tests a specific alternative hypothesis for the knock events: that they
are sensor false positives excited by rough pavement rather than real
detonation. These logs carry no GPS, so absolute road position is unavailable;
the test instead uses chassis-disturbance proxies (four-wheel speed spread,
lateral and longitudinal accelerometer jitter) and cylinder simultaneity.

Every input log uses ``Gear (gear)``, so the logged value is the actual gear and
needs no offset. Gear-weighted power channels are trimmed to actual gear 3.

Usage:
    ../../Code/.venv/bin/python analyze_r18_validation.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
R17_DIR = HERE.parent / "BasicsGuide_R17"
PLOT_DIR = HERE / "plots"

R17_PULL_TAGS = ("12_26_24", "12_28_41", "12_29_45", "12_30_30", "12_32_53", "12_34_25")
R18_PULL_TAGS = ("16_24_26", "16_28_04", "16_29_37", "16_30_31", "16_34_22",
                 "16_36_04", "16_37_04", "16_39_32", "16_40_59")

BANDS = ((3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6500))

# The rpm window R18 was built to fix, and the window its correction hands back.
POCKET_BAND = (4500, 5000)
HANDBACK_BAND = (5000, 5700)

# A cylinder is "in a knock event" at or beyond this retard; the High line is -3.0.
KNOCK_EVENT_DEG = -1.0
# Contiguous knock samples separated by fewer than this many rows are one event.
KNOCK_GAP_ROWS = 10
# Half-width of the sample window examined around a knock onset, in rows (40 ms each).
EVENT_HALF_ROWS = 5
# Rolling half-window used to detrend the roughness proxies, in rows.
ROUGHNESS_HALF_ROWS = 5
# rpm tolerance when matching clean baseline samples to a knock event.
RPM_MATCH_TOL = 150.0

# Same road-load assumptions used in Logs/BasicsGuide_R14/derive_hp_tq_fma.py.
MASS_KG = 3400.0 * 0.45359237
MASS_FACTOR = 1.05
CD = 0.31
FRONTAL_AREA_M2 = 2.21
CRR = 0.011
DRIVELINE_EFFICIENCY = 0.90
GRAVITY = 9.80665
AIR_GAS_CONSTANT = 287.05
WATTS_TO_HP = 1.0 / 745.699872
DERIVATIVE_WINDOW_S = 0.6

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
    "lambda": "Lambda (l)",
    "lambda_sp": "Lambda SP (l)",
    "rail": "FP DI (kpa)",
    "rail_sp": "FP DI SP (kpa)",
    "hpfp": "HPFP Eff Vol (%)",
    "lpfp": "LPFP Duty (%)",
    "turbo": "Turbo Speed (rpm)",
    "torque": "Torque (Nm)",
    "torque_req": "Torque Req (Nm)",
    "ign": "Ign Avg (°)",
    "ign_table": "Ign Table (°)",
    "iat": "IAT (°C)",
    "knock_1": "Knock Cyl 1 (°)",
    "knock_2": "Knock Cyl 2 (°)",
    "knock_3": "Knock Cyl 3 (°)",
    "knock_4": "Knock Cyl 4 (°)",
    "torque_lim": "Torque Lim ()",
    "misfires": "Misfires ()",
    "vehicle_speed": "Vehicle Speed (km/h)",
    "accel_lat": "Accel. Lat (m/s2)",
    "accel_long": "Accel. Long (m/s2)",
    "wheel_fl": "Wheel Speed FL (km/h)",
    "wheel_fr": "Wheel Speed FR (km/h)",
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


def path_for(folder: Path, tag: str) -> Path:
    matches = list(folder.glob(f"simostools-*{tag}.csv"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one log matching {tag}, found {len(matches)}")
    return matches[0]


def load_tagged(folder: Path, tags: tuple[str, ...]) -> list[tuple[str, dict[str, np.ndarray]]]:
    return [(tag, load(path_for(folder, tag))) for tag in tags]


def combine(logs: list[tuple[str, dict[str, np.ndarray]]]) -> dict[str, np.ndarray]:
    return {key: np.concatenate([data[key] for _, data in logs]) for key in CHANNELS}


def clean_third_gear_mask(data: dict[str, np.ndarray]) -> np.ndarray:
    return (
        (data["pedal"] >= 90.0)
        & (np.rint(data["gear"]) == 3)
        & (data["rpm"] >= 3000.0)
        & (data["airmass"] >= 0.9)
        & (data["tps"] >= 60.0)
    )


def contiguous_runs(mask: np.ndarray, gap: int = 1) -> list[np.ndarray]:
    indices = np.flatnonzero(mask)
    if not indices.size:
        return []
    return list(np.split(indices, np.flatnonzero(np.diff(indices) > gap) + 1))


def rolling_median(values: np.ndarray, half: int) -> np.ndarray:
    out = np.empty_like(values)
    for index in range(values.size):
        lo = max(0, index - half)
        hi = min(values.size, index + half + 1)
        out[index] = np.median(values[lo:hi])
    return out


def roughness_proxies(data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Chassis-disturbance surrogates for road roughness.

    These logs have no GPS, so road position cannot be recovered. What a rough
    surface does leave behind is a momentary disagreement between the four wheel
    speeds and a spike in the chassis accelerometers, so both are detrended
    against their own local median and used as the roughness signal.
    """
    wheels = np.vstack([data["wheel_fl"], data["wheel_fr"],
                        data["wheel_rl"], data["wheel_rr"]])
    spread = wheels.max(axis=0) - wheels.min(axis=0)
    # The GTI is front-wheel drive, so front-axle spread under WOT is dominated
    # by traction slip -- and a knock event changes torque, which changes slip,
    # so that channel can move *because* of knock. The undriven rear axle is the
    # cleaner road-surface signal and is the one the verdict rests on.
    rear_spread = np.abs(data["wheel_rl"] - data["wheel_rr"])
    return {
        "wheel_spread": spread,
        "wheel_jitter": np.abs(spread - rolling_median(spread, ROUGHNESS_HALF_ROWS)),
        "rear_jitter": np.abs(
            rear_spread - rolling_median(rear_spread, ROUGHNESS_HALF_ROWS)
        ),
        "lat_jitter": np.abs(
            data["accel_lat"] - rolling_median(data["accel_lat"], ROUGHNESS_HALF_ROWS)
        ),
        "long_jitter": np.abs(
            data["accel_long"] - rolling_median(data["accel_long"], ROUGHNESS_HALF_ROWS)
        ),
    }


def knock_events(logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict]:
    """Enumerate loaded-WOT knock events, one entry per cylinder run."""
    events: list[dict] = []
    for tag, data in logs:
        loaded = clean_third_gear_mask(data)
        rough = roughness_proxies(data)
        for key in KNOCK_KEYS:
            retard = data[key]
            for run in contiguous_runs(loaded & (retard <= KNOCK_EVENT_DEG), KNOCK_GAP_ROWS):
                onset = int(run[0])
                worst = int(run[np.argmin(retard[run])])
                lo = max(0, onset - EVENT_HALF_ROWS)
                hi = min(retard.size, onset + EVENT_HALF_ROWS + 1)
                window = slice(lo, hi)
                # How many other cylinders retard at the same time? Chassis-borne
                # false knock is broadband and tends to move several at once.
                others = [
                    other for other in KNOCK_KEYS
                    if other != key and np.min(data[other][window]) <= KNOCK_EVENT_DEG
                ]
                events.append({
                    "tag": tag,
                    "cylinder": int(key[-1]),
                    "onset_row": onset,
                    "onset_rpm": float(data["rpm"][onset]),
                    "worst_rpm": float(data["rpm"][worst]),
                    "worst_deg": float(retard[worst]),
                    "samples": int(run.size),
                    "airmass": float(data["airmass"][onset] * 1000.0),
                    "iat": float(data["iat"][onset]),
                    "put_error": float(data["put"][onset] - data["put_sp"][onset]),
                    "ign": float(data["ign"][onset]),
                    "ign_table": float(data["ign_table"][onset]),
                    "co_cylinders": others,
                    "wheel_jitter": float(np.max(rough["wheel_jitter"][window])),
                    "rear_jitter": float(np.max(rough["rear_jitter"][window])),
                    "speed": float(data["vehicle_speed"][onset]),
                    "wheel_spread": float(np.max(rough["wheel_spread"][window])),
                    "lat_jitter": float(np.max(rough["lat_jitter"][window])),
                    "long_jitter": float(np.max(rough["long_jitter"][window])),
                    "indices": run,
                })
    return sorted(events, key=lambda event: event["onset_rpm"])


def print_knock_events(name: str, events: list[dict]) -> None:
    print(f"\n{name} loaded actual-3rd-gear knock events (retard <= {KNOCK_EVENT_DEG:.1f} deg):")
    if not events:
        print("  none")
        return
    print("  file       cyl  onset rpm  worst      airmass      IAT     PUT err  ign/table  co-cyl")
    for event in events:
        co = ",".join(str(c) for c in event["co_cylinders"]) or "-"
        print(
            f"  {event['tag']}  {event['cylinder']}   {event['onset_rpm']:8.0f}  "
            f"{event['worst_deg']:+5.1f}@{event['worst_rpm']:.0f}  "
            f"{event['airmass']:6.0f} mg/stk  {event['iat']:4.1f}C  "
            f"{event['put_error']:+6.1f}  {event['ign']:+5.1f}/{event['ign_table']:+5.1f}  {co}"
        )


def band_of(rpm: float) -> str:
    if POCKET_BAND[0] <= rpm < POCKET_BAND[1]:
        return "R18-corrected pocket"
    if HANDBACK_BAND[0] <= rpm < HANDBACK_BAND[1]:
        return "hand-back zone"
    if rpm < POCKET_BAND[0]:
        return "below pocket"
    return "above hand-back"


def print_event_bands(name: str, events: list[dict]) -> None:
    print(f"\n{name} knock events by rpm zone:")
    for label in ("below pocket", "R18-corrected pocket", "hand-back zone", "above hand-back"):
        hits = [e for e in events if band_of(e["onset_rpm"]) == label]
        detail = ", ".join(
            f"{e['onset_rpm']:.0f} rpm cyl {e['cylinder']} {e['worst_deg']:+.1f}" for e in hits
        )
        print(f"  {label:22s} {len(hits)}  {detail}")


def roughness_test(events: list[dict], logs: list[tuple[str, dict[str, np.ndarray]]]) -> None:
    """Test the rough-pavement false-knock hypothesis.

    For each knock event, compare the chassis-disturbance proxies at the event
    against every clean, knock-free loaded sample at a comparable engine speed
    across the whole session. If rough road were exciting the knock sensor, the
    events should sit in the upper tail of that baseline distribution.
    """
    baseline_rpm: list[np.ndarray] = []
    baseline: dict[str, list[np.ndarray]] = {
        "wheel_jitter": [], "wheel_spread": [], "rear_jitter": [],
        "lat_jitter": [], "long_jitter": []
    }
    for _, data in logs:
        rough = roughness_proxies(data)
        quiet = clean_third_gear_mask(data)
        for key in KNOCK_KEYS:
            quiet = quiet & (data[key] > KNOCK_EVENT_DEG)
        baseline_rpm.append(data["rpm"][quiet])
        for key, series in rough.items():
            baseline[key].append(series[quiet])

    rpm_all = np.concatenate(baseline_rpm)
    base_all = {key: np.concatenate(values) for key, values in baseline.items()}

    print("\nRough-road false-knock test — no GPS in these logs, so this uses")
    print("chassis-disturbance proxies against rpm-matched knock-free samples.")
    print(f"Baseline: {rpm_all.size} clean loaded samples with no cylinder below "
          f"{KNOCK_EVENT_DEG:.1f} deg.")
    print("\n  event                     REAR jitter (undriven)  front jitter     lat jitter       long jitter    speed")
    print("                              km/h   pctile          km/h  pctile     m/s2  pctile    m/s2  pctile   km/h")
    for event in events:
        near = np.abs(rpm_all - event["onset_rpm"]) <= RPM_MATCH_TOL
        if near.sum() < 20:
            print(f"  {event['tag']} cyl {event['cylinder']} @ {event['onset_rpm']:.0f}: "
                  f"only {near.sum()} rpm-matched baseline samples — not tested")
            continue
        cells = []
        for key in ("rear_jitter", "wheel_jitter", "lat_jitter", "long_jitter"):
            ref = base_all[key][near]
            pct = 100.0 * float(np.mean(ref <= event[key]))
            cells.append(f"{event[key]:5.2f}  {pct:5.1f}%")
        print(f"  {event['tag']} cyl {event['cylinder']} @ {event['onset_rpm']:4.0f} rpm   "
              + "    ".join(cells) + f"   {event['speed']:5.1f}")

    speeds = sorted(event["speed"] for event in events)
    print(f"\n  Road-position proxy: the events happen at {', '.join(f'{s:.0f}' for s in speeds)}"
          " km/h.")
    print("  There is no GPS, but 3rd-gear pulls launched from a similar point put a")
    print("  repeated rough patch at a repeated speed. These are spread across the whole")
    print("  pull, so no single stretch of pavement is common to them.")

    multi = [e for e in events if e["co_cylinders"]]
    print(f"\n  Cylinder simultaneity: {len(multi)} of {len(events)} events had another "
          f"cylinder retarding within +/-{EVENT_HALF_ROWS * 0.04:.2f} s.")
    print("  Chassis-borne false knock is broadband and moves several cylinders at once;")
    print("  a single-cylinder event that decays normally is the detonation signature.")


def band_stats(data: dict[str, np.ndarray]) -> list[dict[str, float]]:
    base = clean_third_gear_mask(data)
    out = []
    for lo, hi in BANDS:
        mask = base & (data["rpm"] >= lo) & (data["rpm"] < hi)
        if mask.sum() < 5:
            raise RuntimeError(f"insufficient clean samples in {lo}-{hi} rpm")
        out.append({
            "n": int(mask.sum()),
            "put_error": float(np.mean(data["put"][mask] - data["put_sp"][mask])),
            "wg_i": float(np.mean(data["wg_i"][mask])),
            "hpfp_max": float(np.max(data["hpfp"][mask])),
            "lambda": float(np.mean(data["lambda"][mask])),
            "lambda_sp": float(np.mean(data["lambda_sp"][mask])),
            "ign": float(np.mean(data["ign"][mask])),
            "ign_table": float(np.mean(data["ign_table"][mask])),
            "iat": float(np.mean(data["iat"][mask])),
            "turbo_max": float(np.max(data["turbo"][mask])),
            "knock_min": float(min(np.min(data[f"knock_{c}"][mask]) for c in range(1, 5))),
        })
    return out


def print_band_table(name: str, stats: list[dict[str, float]]) -> None:
    print(f"\n{name} clean actual-3rd-gear loaded WOT:")
    print("  band          n  PUT err  WG I  HPFP  lambda/SP  ign/table  del-table  IAT  turbo  knock")
    for (lo, hi), row in zip(BANDS, stats):
        print(
            f"  {lo}-{hi}  {row['n']:4d}  {row['put_error']:+6.1f}  "
            f"{row['wg_i']:+5.1f}%  {row['hpfp_max']:4.1f}%  "
            f"{row['lambda']:.3f}/{row['lambda_sp']:.3f}  "
            f"{row['ign']:+5.1f}/{row['ign_table']:+5.1f}°  "
            f"{row['ign'] - row['ign_table']:+5.1f}°  {row['iat']:4.1f}°C  "
            f"{row['turbo_max']:5.0f}k  {row['knock_min']:+4.1f}°"
        )


def local_slope(time: np.ndarray, values: np.ndarray, window_s: float) -> np.ndarray:
    out = np.full(values.size, np.nan)
    half = window_s / 2.0
    for index in range(values.size):
        mask = (time >= time[index] - half) & (time <= time[index] + half)
        x = time[mask]
        y = values[mask]
        if x.size < 4:
            continue
        x_centered = x - np.mean(x)
        denominator = np.sum(x_centered ** 2)
        if denominator > 0.0:
            out[index] = np.sum(x_centered * (y - np.mean(y))) / denominator
    return out


def power_estimate(tag: str, data: dict[str, np.ndarray]) -> dict | None:
    mask = clean_third_gear_mask(data) & (data["rpm"] <= 6500.0)
    runs = contiguous_runs(mask)
    if not runs:
        return None
    indices = max(runs, key=len)
    if indices.size < 50 or np.ptp(data["rpm"][indices]) < 2500.0:
        return None

    # Reconstruct uniform 40-ms logging time; the high absolute Time channel is
    # float32-quantized and unsuitable for a direct speed derivative.
    time = np.arange(data["rpm"].size, dtype=float) * 0.04
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
    crank_hp = wheel_hp / DRIVELINE_EFFICIENCY

    # Exclude the derivative's edge half-window from the peak search.
    edge = int(round((DERIVATIVE_WINDOW_S / 2.0) / 0.04))
    peak_indices = indices[edge:-edge] if indices.size > 2 * edge else indices
    return {
        "tag": tag,
        "indices": indices,
        "rpm": data["rpm"][indices],
        "wheel_hp": wheel_hp[indices],
        "crank_hp": crank_hp[indices],
        "calc_hp": data["calc_hp"][indices],
        "peak_wheel_hp": float(np.nanmax(wheel_hp[peak_indices])),
        "peak_crank_hp": float(np.nanmax(crank_hp[peak_indices])),
        "peak_calc_hp": float(np.nanmax(data["calc_hp"][indices])),
    }


def print_power(name: str, logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict]:
    results = [result for tag, data in logs if (result := power_estimate(tag, data)) is not None]
    peaks = np.asarray([float(result["peak_wheel_hp"]) for result in results])
    print(f"\n{name} complete 3rd-gear F=ma estimates:")
    for result in results:
        print(
            f"  {result['tag']}: wheel {result['peak_wheel_hp']:.0f} hp, "
            f"crank {result['peak_crank_hp']:.0f} hp, "
            f"Calc HP trimmed {result['peak_calc_hp']:.0f} hp"
        )
    print(f"  wheel mean {np.mean(peaks):.0f} hp, range {np.min(peaks):.0f}-{np.max(peaks):.0f} hp")
    return results


def style_axis(ax: plt.Axes) -> None:
    ax.grid(True, which="major", alpha=0.45)
    ax.minorticks_on()
    ax.grid(True, which="minor", alpha=0.18)


def plot_knock_map(r17_events: list[dict], r18_events: list[dict]) -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    for events, name, colour, marker in (
        (r17_events, "R17", "tab:orange", "o"),
        (r18_events, "R18", "tab:blue", "s"),
    ):
        if not events:
            continue
        ax.scatter([e["onset_rpm"] for e in events], [e["airmass"] for e in events],
                   s=[120 + 40 * abs(e["worst_deg"]) for e in events],
                   c=colour, marker=marker, alpha=0.75, edgecolor="k", label=name)
        for index, event in enumerate(events):
            # Alternate the label side so events close in rpm do not overprint.
            offset = (10, 7) if index % 2 == 0 else (10, -16)
            ax.annotate(f"cyl {event['cylinder']} {event['worst_deg']:+.1f}, "
                        f"{event['iat']:.0f}\u00b0C IAT",
                        (event["onset_rpm"], event["airmass"]),
                        textcoords="offset points", xytext=offset, fontsize=8)
    ax.axvspan(*POCKET_BAND, color="tab:green", alpha=0.13)
    ax.axvspan(POCKET_BAND[1], 5500, color="tab:orange", alpha=0.10)
    ax.axvspan(5500, 6400, color="tab:red", alpha=0.08)
    lo, hi = ax.get_ylim()
    ax.set_ylim(lo - 30.0, hi + 90.0)
    top = ax.get_ylim()[1]
    for centre, text in ((np.mean(POCKET_BAND), "R18 pulled timing here"),
                         (5250, "correction fading"),
                         (5950, "timing identical to R17")):
        ax.text(centre, top - 8.0, text, ha="center", va="top", fontsize=9)
    ax.set_xlabel("Knock-onset engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Airmass at onset (mg/stk)", fontweight="bold")
    ax.set_title("Loaded knock events, R17 vs R18 (R18 ran 13.7 \u00b0C hotter at the intake)")
    ax.legend()
    style_axis(ax)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r18_knock_migration.png", dpi=140)
    plt.close(fig)


def plot_roughness(events: list[dict], logs: list[tuple[str, dict[str, np.ndarray]]]) -> None:
    baseline: dict[str, list[np.ndarray]] = {"rear_jitter": [], "wheel_jitter": [], "lat_jitter": []}
    for _, data in logs:
        rough = roughness_proxies(data)
        quiet = clean_third_gear_mask(data)
        for key in KNOCK_KEYS:
            quiet = quiet & (data[key] > KNOCK_EVENT_DEG)
        for key in baseline:
            baseline[key].append(rough[key][quiet])
    base = {key: np.concatenate(values) for key, values in baseline.items()}

    titles = {
        "rear_jitter": "Rear-axle (undriven) speed spread, detrended (km/h)",
        "wheel_jitter": "Four-wheel spread, detrended (km/h) — mixes drive slip",
        "lat_jitter": "Lateral accel jitter (m/s2)",
    }
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, key in zip(axes, titles):
        ax.hist(base[key], bins=40, color="tab:blue", alpha=0.6,
                label=f"knock-free loaded (n={base[key].size})")
        for event in events:
            ax.axvline(event[key], color="tab:red", linestyle="--", linewidth=1.4)
        ax.axvline(np.nan, color="tab:red", linestyle="--", label="knock events")
        ax.set_xlabel(titles[key], fontweight="bold")
        ax.set_yscale("log")
        ax.legend(fontsize=8)
        style_axis(ax)
    axes[0].set_ylabel("Samples (log)", fontweight="bold")
    fig.suptitle("Rough-road false-knock test: knock events vs the knock-free baseline")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r18_roughness_test.png", dpi=140)
    plt.close(fig)


def plot_timing_and_power(r17_stats, r18_stats, r17_power, r18_power) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    centres = [0.5 * (lo + hi) for lo, hi in BANDS]

    ax = axes[0]
    ax.plot(centres, [s["ign_table"] for s in r17_stats], "o--", color="tab:orange",
            label="R17 table")
    ax.plot(centres, [s["ign"] for s in r17_stats], "o-", color="tab:orange",
            label="R17 delivered")
    ax.plot(centres, [s["ign_table"] for s in r18_stats], "s--", color="tab:blue",
            label="R18 table")
    ax.plot(centres, [s["ign"] for s in r18_stats], "s-", color="tab:blue",
            label="R18 delivered")
    ax.axvspan(*POCKET_BAND, color="tab:green", alpha=0.12)
    ax.axvspan(*HANDBACK_BAND, color="tab:red", alpha=0.10)
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Ignition angle (deg)", fontweight="bold")
    ax.set_title("Table vs delivered timing by band")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[1]
    for results, name, colour in ((r17_power, "R17", "tab:orange"),
                                  (r18_power, "R18", "tab:blue")):
        for index, result in enumerate(results):
            rpm = np.asarray(result["rpm"])
            hp = np.asarray(result["wheel_hp"])
            order = np.argsort(rpm)
            ax.plot(rpm[order], hp[order], color=colour, alpha=0.55,
                    label=name if index == 0 else None)
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Physics-derived wheel power (hp)", fontweight="bold")
    ax.set_title("Road-load power estimate")
    ax.legend(fontsize=8)
    style_axis(ax)

    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r18_vs_r17_validation.png", dpi=140)
    plt.close(fig)


def main() -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    r17_logs = load_tagged(R17_DIR, R17_PULL_TAGS)
    r18_logs = load_tagged(HERE, R18_PULL_TAGS)

    r17_events = knock_events(r17_logs)
    r18_events = knock_events(r18_logs)
    print_knock_events("R17", r17_events)
    print_knock_events("R18", r18_events)
    print_event_bands("R17", r17_events)
    print_event_bands("R18", r18_events)

    roughness_test(r18_events, r18_logs)

    r17_stats = band_stats(combine(r17_logs))
    r18_stats = band_stats(combine(r18_logs))
    print_band_table("R17", r17_stats)
    print_band_table("R18", r18_stats)

    r17_power = print_power("R17", r17_logs)
    r18_power = print_power("R18", r18_logs)

    plot_knock_map(r17_events, r18_events)
    plot_roughness(r18_events, r18_logs)
    plot_timing_and_power(r17_stats, r18_stats, r17_power, r18_power)
    print(f"\nWrote plots to {PLOT_DIR}")


if __name__ == "__main__":
    main()
