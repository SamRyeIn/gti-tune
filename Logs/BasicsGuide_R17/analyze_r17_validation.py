"""Validate MainTune R17 against the logged R15 baseline.

R17 restores the tuning-guide base-ignition table while retaining R16's exact
Spark-IAT family. This script compares clean actual-3rd-gear WOT samples against
R15, enumerates lambda and knock events that need manual interpretation, and
computes the same road-load F=ma power estimate used in the R14/R15 reviews.

Every input log uses ``Gear (gear)``, so the logged value is the actual gear and
needs no offset. Gear-weighted power channels are trimmed to actual gear 3.

Usage:
    ../../Code/.venv/bin/python analyze_r17_validation.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
R15_DIR = HERE.parent / "BasicsGuide_R15"
PLOT_DIR = HERE / "plots"

R15_CLEAN_TAGS = ("11_35_28", "11_37_30", "11_41_12", "11_42_33", "11_43_50")
R17_PULL_TAGS = ("12_26_24", "12_28_41", "12_29_45", "12_30_30", "12_32_53", "12_34_25")
BANDS = ((3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6500))

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
    "wg_base": "WG Pos Base (%)",
    "wg_i": "WG I Value (%)",
    "wg_final": "WG Pos Final (%)",
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
    "wheel_rl": "Wheel Speed RL (km/h)",
    "wheel_rr": "Wheel Speed RR (km/h)",
    "calc_hp": "Calc HP (hp)",
}


def load(path: Path) -> dict[str, np.ndarray]:
    with path.open() as handle:
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
    return {
        key: np.concatenate([data[key] for _, data in logs])
        for key in CHANNELS
    }


def clean_third_gear_mask(data: dict[str, np.ndarray]) -> np.ndarray:
    return (
        (data["pedal"] >= 90.0)
        & (np.rint(data["gear"]) == 3)
        & (data["rpm"] >= 3000.0)
        & (data["airmass"] >= 0.9)
        & (data["tps"] >= 60.0)
    )


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


def contiguous_runs(mask: np.ndarray) -> list[np.ndarray]:
    indices = np.flatnonzero(mask)
    if not indices.size:
        return []
    return list(np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1))


def lambda_events(logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict[str, float | str | np.ndarray]]:
    events: list[dict[str, float | str | np.ndarray]] = []
    print("\nSettled loaded-WOT lambda excursions above +0.03:")
    for tag, data in logs:
        error = data["lambda"] - data["lambda_sp"]
        settled = (
            clean_third_gear_mask(data)
            & (data["torque"] >= 250.0)
            & ((data["torque_req"] - data["torque"]) <= 80.0)
            & (data["lambda"] < 1.3)
            & (data["lambda_sp"] < 0.98)
        )
        for run in contiguous_runs(settled & (error > 0.03)):
            peak = int(run[np.argmax(error[run])])
            duration = 0.04 * len(run)
            event = {
                "tag": tag,
                "indices": run,
                "peak": peak,
                "duration": duration,
                "rpm": float(data["rpm"][peak]),
                "error": float(error[peak]),
                "lambda": float(data["lambda"][peak]),
                "lambda_sp": float(data["lambda_sp"][peak]),
                "torque": float(data["torque"][peak]),
                "airmass": float(data["airmass"][peak] * 1000.0),
                "put_error": float(data["put"][peak] - data["put_sp"][peak]),
                "rail_error": float((data["rail"][peak] - data["rail_sp"][peak]) / 100.0),
            }
            events.append(event)
            print(
                f"  {tag} rows {run[0]}-{run[-1]}: {duration:.2f} s, "
                f"peak +{event['error']:.3f} at {event['rpm']:.0f} rpm; "
                f"lambda {event['lambda']:.3f}/{event['lambda_sp']:.3f}, "
                f"torque {event['torque']:.0f} Nm, airmass {event['airmass']:.0f} mg/stk, "
                f"PUT err {event['put_error']:+.1f} kPa, rail err {event['rail_error']:+.1f} bar"
            )
    return events


def knock_events(logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict[str, float | int | str | np.ndarray]]:
    events: list[dict[str, float | int | str | np.ndarray]] = []
    print("\nLoaded-WOT knock episodes reaching at least −1.5°:")
    for tag, data in logs:
        loaded = clean_third_gear_mask(data)
        for cylinder in range(1, 5):
            values = data[f"knock_{cylinder}"]
            active = loaded & (values < -0.1)
            for run in contiguous_runs(active):
                if np.min(values[run]) > -1.5:
                    continue
                peak = int(run[np.argmin(values[run])])
                event = {
                    "tag": tag,
                    "indices": run,
                    "peak": peak,
                    "cylinder": cylinder,
                    "rpm": float(data["rpm"][peak]),
                    "onset_rpm": float(data["rpm"][run[0]]),
                    "knock": float(values[peak]),
                    "iat": float(data["iat"][peak]),
                    "airmass": float(data["airmass"][peak] * 1000.0),
                    "put_error": float(data["put"][peak] - data["put_sp"][peak]),
                    "ign": float(data["ign"][peak]),
                    "ign_table": float(data["ign_table"][peak]),
                }
                events.append(event)
                print(
                    f"  {tag} cyl {cylinder}, rows {run[0]}-{run[-1]}: "
                    f"onset {event['onset_rpm']:.0f} rpm, worst {event['knock']:+.1f}° "
                    f"at {event['rpm']:.0f} rpm, "
                    f"IAT {event['iat']:.1f}°C, airmass {event['airmass']:.0f} mg/stk, "
                    f"PUT err {event['put_error']:+.1f} kPa, "
                    f"Ign Avg/table {event['ign']:+.1f}/{event['ign_table']:+.1f}°"
                )
    return events


def upshift_events(logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict[str, float | int | str | np.ndarray]]:
    events: list[dict[str, float | int | str | np.ndarray]] = []
    print("\nWOT 3→4 upshift edges:")
    for tag, data in logs:
        transitions = np.flatnonzero(
            (np.rint(data["gear"][:-1]) == 3)
            & (np.rint(data["gear"][1:]) == 4)
            & (data["pedal"][1:] >= 90.0)
        ) + 1
        for shift in transitions:
            window = np.arange(max(0, shift - 15), min(data["rpm"].size, shift + 31))
            loaded = window[(data["pedal"][window] >= 90.0) & (data["put_sp"][window] > 200.0)]
            if not loaded.size:
                continue
            rail_error = (data["rail"][loaded] - data["rail_sp"][loaded]) / 100.0
            event = {
                "tag": tag,
                "shift": int(shift),
                "indices": window,
                "loaded": loaded,
                "landing_rpm": float(np.min(data["rpm"][loaded])),
                "put_peak": float(np.max(data["put"][loaded])),
                "put_error": float(np.max(data["put"][loaded] - data["put_sp"][loaded])),
                "rail_error": float(np.min(rail_error)),
                "hpfp": float(np.max(data["hpfp"][loaded])),
                "airmass": float(np.max(data["airmass"][loaded]) * 1000.0),
                "turbo": float(np.max(data["turbo"][loaded])),
                "pre_wg_i": float(data["wg_i"][shift - 1]),
            }
            events.append(event)
            print(
                f"  {tag}: lands {event['landing_rpm']:.0f} rpm, peak PUT {event['put_peak']:.1f} kPa, "
                f"PUT err {event['put_error']:+.1f} kPa, rail err {event['rail_error']:+.1f} bar, "
                f"HPFP {event['hpfp']:.1f}%, airmass {event['airmass']:.0f} mg/stk, "
                f"turbo {event['turbo']:.0f} krpm, pre-shift WG I {event['pre_wg_i']:+.1f}%"
            )
    return events


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


def power_estimate(tag: str, data: dict[str, np.ndarray]) -> dict[str, float | str | np.ndarray] | None:
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


def print_power(name: str, logs: list[tuple[str, dict[str, np.ndarray]]]) -> list[dict[str, float | str | np.ndarray]]:
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


def plot_comparison(r15: list[dict[str, float]], r17: list[dict[str, float]]) -> None:
    x = np.asarray([(lo + hi) / 2 for lo, hi in BANDS])
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)

    ax = axes[0, 0]
    ax.plot(x, [row["ign_table"] for row in r15], "o--", label="R15 table")
    ax.plot(x, [row["ign_table"] for row in r17], "o-", label="R17 table")
    ax.plot(x, [row["ign"] for row in r15], "s--", label="R15 delivered")
    ax.plot(x, [row["ign"] for row in r17], "s-", label="R17 delivered")
    ax.set_ylabel("Ignition angle (°)", fontweight="bold")
    ax.set_title("Requested and delivered timing")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[0, 1]
    ax.axhline(0.0, color="0.25", lw=1)
    ax.plot(x, [row["ign"] - row["ign_table"] for row in r15], "o--", label="R15")
    ax.plot(x, [row["ign"] - row["ign_table"] for row in r17], "o-", label="R17")
    ax.set_ylabel("Ign Avg − Ign Table (°)", fontweight="bold")
    ax.set_title("Non-table timing correction")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[1, 0]
    ax.axhline(0.0, color="0.25", lw=1)
    ax.axhline(10.0, color="tab:orange", ls="--", lw=1)
    ax.axhline(-10.0, color="tab:orange", ls="--", lw=1)
    ax.plot(x, [row["put_error"] for row in r15], "o--", label="R15")
    ax.plot(x, [row["put_error"] for row in r17], "o-", label="R17")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("PUT − PUT SP (kPa)", fontweight="bold")
    ax.set_title("Boost tracking")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[1, 1]
    ax.axhline(0.0, color="0.25", lw=1)
    ax.plot(x, [row["lambda"] - row["lambda_sp"] for row in r15], "o--", label="R15")
    ax.plot(x, [row["lambda"] - row["lambda_sp"] for row in r17], "o-", label="R17")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Lambda − lambda setpoint", fontweight="bold")
    ax.set_title("Mean lambda tracking")
    ax.legend(fontsize=8)
    style_axis(ax)

    fig.suptitle("R17 validation — clean actual-3rd-gear loaded WOT vs R15", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    output = PLOT_DIR / "r17_vs_r15_validation.png"
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f"wrote {output}")


def plot_events(
    logs: list[tuple[str, dict[str, np.ndarray]]],
    lambda_rows: list[dict[str, float | str | np.ndarray]],
    knock_rows: list[dict[str, float | int | str | np.ndarray]],
    upshift_rows: list[dict[str, float | int | str | np.ndarray]],
) -> None:
    data_by_tag = dict(logs)

    if lambda_rows:
        event = max(lambda_rows, key=lambda row: float(row["error"]))
        data = data_by_tag[str(event["tag"])]
        peak = int(event["peak"])
        indices = np.arange(max(0, peak - 15), min(data["rpm"].size, peak + 31))
        time = (indices - peak) * 0.04
        fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
        axes[0].plot(time, data["lambda"][indices], label="Lambda")
        axes[0].plot(time, data["lambda_sp"][indices], label="Lambda SP")
        axes[0].set_ylabel("Lambda", fontweight="bold")
        axes[0].legend()
        axes[1].plot(time, data["torque"][indices], label="Torque")
        axes[1].plot(time, data["torque_req"][indices], label="Torque requested")
        axes[1].set_ylabel("Torque (Nm)", fontweight="bold")
        axes[1].legend()
        axes[2].plot(time, data["put"][indices] - data["put_sp"][indices], label="PUT error")
        axes[2].plot(time, (data["rail"][indices] - data["rail_sp"][indices]) / 100.0,
                     label="DI rail error")
        axes[2].set_ylabel("Pressure error", fontweight="bold")
        axes[2].set_xlabel("Time from peak lambda error (s)", fontweight="bold")
        axes[2].legend()
        for ax in axes:
            ax.axvline(0.0, color="0.25", ls="--", lw=1)
            style_axis(ax)
        fig.suptitle(f"R17 worst lambda excursion — {event['tag']}", fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        output = PLOT_DIR / "r17_lambda_event.png"
        fig.savefig(output, dpi=150)
        plt.close(fig)
        print(f"wrote {output}")

    if upshift_rows:
        event = min(upshift_rows, key=lambda row: float(row["rail_error"]))
        data = data_by_tag[str(event["tag"])]
        shift = int(event["shift"])
        indices = np.asarray(event["indices"], dtype=int)
        time = (indices - shift) * 0.04
        min_knock = np.min(
            np.column_stack([data[f"knock_{c}"][indices] for c in range(1, 5)]), axis=1
        )
        fig, axes = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
        axes[0].plot(time, data["put"][indices], label="PUT")
        axes[0].plot(time, data["put_sp"][indices], label="PUT SP")
        axes[0].set_ylabel("Absolute pressure (kPa)", fontweight="bold")
        axes[0].legend()
        axes[1].plot(time, data["wg_base"][indices], label="WG base")
        axes[1].plot(time, data["wg_i"][indices], label="WG I")
        axes[1].plot(time, data["wg_final"][indices], label="WG final")
        axes[1].set_ylabel("Wastegate command (%)", fontweight="bold")
        axes[1].legend(ncol=3)
        axes[2].plot(time, (data["rail"][indices] - data["rail_sp"][indices]) / 100.0,
                     label="DI rail error")
        axes[2].plot(time, data["hpfp"][indices], label="HPFP effective volume")
        axes[2].set_ylabel("Fuel-system response", fontweight="bold")
        axes[2].legend()
        axes[3].plot(time, data["lambda"][indices], label="Lambda")
        axes[3].plot(time, data["lambda_sp"][indices], label="Lambda SP")
        axes[3].plot(time, min_knock, label="Most-retarded cylinder")
        axes[3].set_ylabel("Combustion response", fontweight="bold")
        axes[3].set_xlabel("Time from logged 3→4 gear transition (s)", fontweight="bold")
        axes[3].legend(ncol=3)
        for ax in axes:
            ax.axvline(0.0, color="0.25", ls="--", lw=1)
            style_axis(ax)
        fig.suptitle(f"R17 worst-fuel-headroom WOT 3→4 shift — {event['tag']}", fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        output = PLOT_DIR / "r17_worst_upshift.png"
        fig.savefig(output, dpi=150)
        plt.close(fig)
        print(f"wrote {output}")

    if knock_rows:
        fig, axes = plt.subplots(len(knock_rows), 1, figsize=(11, 3.4 * len(knock_rows)), squeeze=False)
        for ax, event in zip(axes[:, 0], knock_rows):
            data = data_by_tag[str(event["tag"])]
            peak = int(event["peak"])
            indices = np.arange(max(0, peak - 12), min(data["rpm"].size, peak + 35))
            for cylinder in range(1, 5):
                ax.plot(data["rpm"][indices], data[f"knock_{cylinder}"][indices],
                        label=f"Cylinder {cylinder}")
            ax.axvline(data["rpm"][peak], color="0.25", ls="--", lw=1)
            ax.axhline(-3.0, color="tab:red", ls="--", lw=1)
            ax.set_ylabel("Knock retard (°)", fontweight="bold")
            ax.set_title(f"{event['tag']} — cylinder {event['cylinder']} event")
            ax.legend(fontsize=8, ncol=4)
            style_axis(ax)
        axes[-1, 0].set_xlabel("Engine speed (rpm)", fontweight="bold")
        fig.suptitle("R17 loaded-WOT knock episodes", fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.96))
        output = PLOT_DIR / "r17_knock_events.png"
        fig.savefig(output, dpi=150)
        plt.close(fig)
        print(f"wrote {output}")


def plot_power(r15: list[dict[str, float | str | np.ndarray]],
               r17: list[dict[str, float | str | np.ndarray]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 6), sharey=True)
    for ax, name, results in zip(axes, ("R15", "R17"), (r15, r17)):
        for result in results:
            rpm = np.asarray(result["rpm"])
            hp = np.asarray(result["wheel_hp"])
            order = np.argsort(rpm)
            ax.plot(rpm[order], hp[order], label=str(result["tag"]))
        ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
        ax.set_title(name)
        ax.legend(fontsize=8)
        style_axis(ax)
    axes[0].set_ylabel("Physics-derived wheel power (hp)", fontweight="bold")
    fig.suptitle("R17 vs R15 road-load F=ma estimate — actual gear 3 only", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    output = PLOT_DIR / "r17_vs_r15_power.png"
    fig.savefig(output, dpi=150)
    plt.close(fig)
    print(f"wrote {output}")


def print_session_summary(logs: list[tuple[str, dict[str, np.ndarray]]]) -> None:
    print("\nPer-file WOT summary:")
    for tag, data in logs:
        mask = clean_third_gear_mask(data)
        if not np.any(mask):
            print(f"  {tag}: no clean loaded actual-3rd-gear WOT samples")
            continue
        min_knock = min(float(np.min(data[f"knock_{c}"][mask])) for c in range(1, 5))
        print(
            f"  {tag}: {np.sum(mask)} rows, {np.min(data['rpm'][mask]):.0f}-{np.max(data['rpm'][mask]):.0f} rpm, "
            f"IAT {np.min(data['iat'][mask]):.1f}-{np.max(data['iat'][mask]):.1f}°C, "
            f"knock {min_knock:+.1f}°, turbo {np.max(data['turbo'][mask]):.0f} krpm, "
            f"HPFP {np.max(data['hpfp'][mask]):.1f}%, LPFP {np.max(data['lpfp'][mask]):.1f}%, "
            f"rail error {np.min((data['rail'][mask] - data['rail_sp'][mask]) / 100.0):+.1f} bar, "
            f"misfires {np.max(data['misfires'][mask]):.0f}, torque-limiter values "
            f"{np.unique(data['torque_lim'][mask])}"
        )


def main() -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    r15_logs = load_tagged(R15_DIR, R15_CLEAN_TAGS)
    r17_logs = load_tagged(HERE, R17_PULL_TAGS)
    print_session_summary(r17_logs)
    r15_stats = band_stats(combine(r15_logs))
    r17_stats = band_stats(combine(r17_logs))
    print_band_table("R15", r15_stats)
    print_band_table("R17", r17_stats)
    lambda_rows = lambda_events(r17_logs)
    knock_rows = knock_events(r17_logs)
    upshift_rows = upshift_events(r17_logs)
    r15_power = print_power("R15", r15_logs)
    r17_power = print_power("R17", r17_logs)
    plot_comparison(r15_stats, r17_stats)
    plot_events(r17_logs, lambda_rows, knock_rows, upshift_rows)
    plot_power(r15_power, r17_power)


if __name__ == "__main__":
    main()
