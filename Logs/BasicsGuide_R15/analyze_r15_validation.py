"""Validate the R15 wastegate change against R14 and inspect shift edges.

R15 changes only five cells in each of ``IP_FAC_BPA_SP[0]`` / ``[1]`` —
Wastegate Position Feedforward, VVL 0 / VVL 1.  This script:

* verifies those table deltas by reading the R14 and R15 bins;
* compares clean, actual-3rd-gear WOT samples in fixed RPM bands; and
* plots the worst R15 WOT upshift, which the standard pull segmentation omits.

The CSV header is ``Gear (gear)``, so logged gear values are actual gears and
need no offset.

Usage:
    ../../Code/.venv/bin/python analyze_r15_validation.py
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
REPO_ROOT = HERE.parent.parent
PLOT_DIR = HERE / "plots"
sys.path.insert(0, str(REPO_ROOT / "Code"))

from simoscal import CalFile, structure_of  # noqa: E402


XDF = REPO_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
R14_BIN = (
    REPO_ROOT
    / "Tunes"
    / "TuningBasicsGuide"
    / "TUNE_Basics_Guide_out"
    / "R14_20260810-111002"
    / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin"
)
R15_BIN = (
    REPO_ROOT
    / "Tunes"
    / "TuningBasicsGuide"
    / "TUNE_Basics_Guide_out"
    / "R15_20260817-073236"
    / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R15.bin"
)

R14_CLEAN_TAGS = ("12_00_06", "12_02_12", "12_06_23", "12_07_51")
R15_CLEAN_TAGS = ("11_35_28", "11_37_30", "11_41_12", "11_42_33", "11_43_50")
R15_SHIFT_TAG = "11_35_28"
KNOCK_EVENTS = (("11_35_28", 367, "steady 3rd gear"),
                ("11_40_04", 181, "after the WOT 2→3 shift"))
BANDS = ((3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6500))
R15_PREDICTED_ERROR_KPA = np.array((-2.9, -7.2, -4.1, -4.5, -2.0, 1.4))

EXPECTED_R15_DELTAS = {
    (6, 14): 0.020,
    (6, 15): 0.020,
    (7, 14): 0.060,
    (7, 15): 0.010,
    (8, 15): 0.040,
}

CHANNELS = {
    "time": "Time",
    "rpm": "Engine Speed (rpm)",
    "pedal": "Pedal Pos (%)",
    "tps": "TPS (%)",
    "gear": "Gear (gear)",
    "ambient": "Ambient Press (kpa)",
    "put": "PUT (kpa)",
    "put_sp": "PUT SP (kpa)",
    "map": "MAP (kpa)",
    "map_sp": "MAP SP (kpa)",
    "airmass": "Airmass (g/stk)",
    "wg_base": "WG Pos Base (%)",
    "wg_i": "WG I Value (%)",
    "wg_pd": "WG P-D Value (%)",
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
}


def load(path: Path) -> dict[str, np.ndarray]:
    with path.open() as handle:
        rows = list(csv.DictReader(handle))
    return {
        key: np.asarray([float(row[column]) for row in rows], dtype=float)
        for key, column in CHANNELS.items()
    }


def paths_for(folder: Path, tags: tuple[str, ...]) -> list[Path]:
    paths = []
    for tag in tags:
        matches = list(folder.glob(f"simostools-*{tag}.csv"))
        if len(matches) != 1:
            raise RuntimeError(f"expected one log matching {tag}, found {len(matches)}")
        paths.append(matches[0])
    return paths


def combine_clean(folder: Path, tags: tuple[str, ...]) -> dict[str, np.ndarray]:
    logs = [load(path) for path in paths_for(folder, tags)]
    return {key: np.concatenate([log[key] for log in logs]) for key in CHANNELS}


def clean_third_gear_mask(data: dict[str, np.ndarray]) -> np.ndarray:
    return (
        (data["pedal"] >= 90.0)
        & (np.rint(data["gear"]) == 3)
        & (data["rpm"] >= 3000.0)
    )


def band_stats(data: dict[str, np.ndarray]) -> list[dict[str, float]]:
    base = clean_third_gear_mask(data)
    out = []
    for lo, hi in BANDS:
        mask = base & (data["rpm"] >= lo) & (data["rpm"] < hi)
        if mask.sum() < 5:
            raise RuntimeError(f"insufficient clean samples in {lo}-{hi} rpm")
        ambient = float(np.mean(data["ambient"][mask]))
        out.append({
            "n": int(mask.sum()),
            "put_error": float(np.mean(data["put"][mask] - data["put_sp"][mask])),
            "put_error_sd": float(np.std(data["put"][mask] - data["put_sp"][mask])),
            "boost": float((np.mean(data["put"][mask]) - ambient) / 6.89476),
            "boost_sp": float((np.mean(data["put_sp"][mask]) - ambient) / 6.89476),
            "wg_base": float(np.mean(data["wg_base"][mask])),
            "wg_i": float(np.mean(data["wg_i"][mask])),
            "wg_final": float(np.mean(data["wg_final"][mask])),
            "turbo_max": float(np.max(data["turbo"][mask])),
            "hpfp_max": float(np.max(data["hpfp"][mask])),
            "lambda": float(np.mean(data["lambda"][mask])),
            "lambda_sp": float(np.mean(data["lambda_sp"][mask])),
            "ign": float(np.mean(data["ign"][mask])),
            "ign_table": float(np.mean(data["ign_table"][mask])),
            "iat": float(np.mean(data["iat"][mask])),
        })
    return out


def verify_table_deltas() -> None:
    r14 = CalFile.open(str(XDF), str(R14_BIN), structure=structure_of(R14_BIN))
    r15 = CalFile.open(str(XDF), str(R15_BIN), structure=structure_of(R15_BIN))
    symbols = ("IP_FAC_BPA_SP[0]", "IP_FAC_BPA_SP[1]")
    print("Flashed-bin table delta verification:")
    for symbol in symbols:
        before = np.asarray(r14.get(symbol).values, dtype=float)
        after = np.asarray(r15.get(symbol).values, dtype=float)
        delta = after - before
        changed = {tuple(index): float(delta[tuple(index)])
                   for index in np.argwhere(np.abs(delta) > 5e-4)}
        if set(changed) != set(EXPECTED_R15_DELTAS):
            raise AssertionError(f"{symbol}: unexpected changed cells {changed}")
        for index, expected in EXPECTED_R15_DELTAS.items():
            if not np.isclose(changed[index], expected, atol=5e-4):
                raise AssertionError(
                    f"{symbol} {index}: expected {expected:+.3f}, got {changed[index]:+.3f}"
                )
        print(f"  {symbol}: five intended cells, exact within table resolution")


def print_band_table(name: str, stats: list[dict[str, float]]) -> None:
    print(f"\n{name} clean 3rd-gear WOT:")
    print("  band          n  PUT err  boost/target  WG base/final/I  turbo  HPFP  lambda/SP  ign/table  IAT")
    for (lo, hi), row in zip(BANDS, stats):
        print(
            f"  {lo}-{hi}  {row['n']:4d}  {row['put_error']:+6.1f}  "
            f"{row['boost']:4.1f}/{row['boost_sp']:4.1f} psi  "
            f"{row['wg_base']:4.1f}/{row['wg_final']:4.1f}/{row['wg_i']:+4.1f}%  "
            f"{row['turbo_max']:5.0f}k  {row['hpfp_max']:4.1f}%  "
            f"{row['lambda']:.3f}/{row['lambda_sp']:.3f}  "
            f"{row['ign']:+4.1f}/{row['ign_table']:+4.1f}°  {row['iat']:4.1f}°C"
        )


def style_axis(ax: plt.Axes) -> None:
    ax.grid(True, which="major", alpha=0.45)
    ax.minorticks_on()
    ax.grid(True, which="minor", alpha=0.18)


def plot_comparison(r14: list[dict[str, float]], r15: list[dict[str, float]]) -> None:
    x = np.asarray([(lo + hi) / 2 for lo, hi in BANDS])
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), sharex=True)

    ax = axes[0, 0]
    ax.axhline(0.0, color="0.25", lw=1)
    ax.axhline(10.0, color="tab:orange", ls="--", lw=1, label="±10 kPa watch")
    ax.axhline(-10.0, color="tab:orange", ls="--", lw=1)
    ax.plot(x, [row["put_error"] for row in r14], "o-", label="R14 measured")
    ax.plot(x, R15_PREDICTED_ERROR_KPA, "o--", label="R15 predicted")
    ax.plot(x, [row["put_error"] for row in r15], "o-", label="R15 measured")
    ax.set_ylabel("PUT − PUT SP (kPa)", fontweight="bold")
    ax.set_title("Boost tracking")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[0, 1]
    ax.plot(x, [row["wg_base"] for row in r14], "o--", label="R14 base")
    ax.plot(x, [row["wg_base"] for row in r15], "o-", label="R15 base")
    ax.plot(x, [row["wg_final"] for row in r14], "s--", label="R14 final")
    ax.plot(x, [row["wg_final"] for row in r15], "s-", label="R15 final")
    ax.set_ylabel("Wastegate position (%)", fontweight="bold")
    ax.set_title("Feedforward and final command")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[1, 0]
    ax.axhline(0.0, color="0.25", lw=1)
    ax.plot(x, [row["wg_i"] for row in r14], "o--", label="R14 integral")
    ax.plot(x, [row["wg_i"] for row in r15], "o-", label="R15 integral")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("WG integral correction (%)", fontweight="bold")
    ax.set_title("Closed-loop load remaining")
    ax.legend(fontsize=8)
    style_axis(ax)

    ax = axes[1, 1]
    ax.axhline(0.0, color="0.25", lw=1)
    ax.plot(x, [row["ign"] - row["ign_table"] for row in r14], "o--",
            label="R14 delivered − table")
    ax.plot(x, [row["ign"] - row["ign_table"] for row in r15], "o-",
            label="R15 delivered − table")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Ign Avg − Ign Table (°)", fontweight="bold")
    ax.set_title("Non-table timing correction; R15 was ~16 °C hotter")
    ax.legend(fontsize=8)
    style_axis(ax)

    fig.suptitle("R15 validation — clean actual-3rd-gear WOT vs R14", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = PLOT_DIR / "r15_vs_r14_validation.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"\nwrote {out}")


def plot_worst_shift() -> None:
    path = paths_for(HERE, (R15_SHIFT_TAG,))[0]
    data = load(path)
    wot = data["pedal"] >= 90.0
    rpm_drop = np.diff(data["rpm"])
    candidates = np.flatnonzero(wot[1:] & wot[:-1] & (rpm_drop < -300.0)) + 1
    if candidates.size == 0:
        raise RuntimeError("no WOT upshift found")
    shift = int(candidates[0])
    start = max(0, shift - 15)
    end = min(len(data["rpm"]) - 1, shift + 20)
    idx = np.arange(start, end + 1)
    dt = np.median(np.diff(data["time"])[np.diff(data["time"]) > 0])
    if not np.isfinite(dt) or dt <= 0:
        dt = 0.04
    t = (idx - shift) * dt
    ambient = data["ambient"][idx]
    knock = np.min(np.column_stack([data[f"knock_{c}"][idx] for c in range(1, 5)]), axis=1)

    fig, axes = plt.subplots(4, 1, figsize=(12, 12), sharex=True)
    for ax in axes:
        ax.axvline(0.0, color="0.25", ls="--", lw=1)
        style_axis(ax)

    axes[0].plot(t, (data["put"][idx] - ambient) / 6.89476, label="PUT actual")
    axes[0].plot(t, (data["put_sp"][idx] - ambient) / 6.89476, label="PUT SP")
    axes[0].plot(t, (data["map"][idx] - ambient) / 6.89476, label="MAP actual", alpha=0.8)
    axes[0].set_ylabel("Gauge pressure (psi)", fontweight="bold")
    axes[0].set_title("Boost across the WOT 3→4 shift")
    axes[0].legend(fontsize=8)

    axes[1].plot(t, data["wg_base"][idx], label="WG base")
    axes[1].plot(t, data["wg_i"][idx], label="WG I")
    axes[1].plot(t, data["wg_pd"][idx], label="WG P-D")
    axes[1].plot(t, data["wg_final"][idx], label="WG final", lw=2)
    axes[1].set_ylabel("Wastegate command (%)", fontweight="bold")
    axes[1].set_title("Wastegate response")
    axes[1].legend(fontsize=8, ncol=4)

    rail_error_bar = (data["rail"][idx] - data["rail_sp"][idx]) / 100.0
    axes[2].plot(t, rail_error_bar, color="tab:blue", label="DI rail error")
    axes[2].axhline(-10.0, color="tab:orange", ls="--", lw=1)
    axes[2].axhline(-25.0, color="tab:red", ls="--", lw=1)
    axes[2].set_ylabel("DI rail error (bar)", color="tab:blue", fontweight="bold")
    ax2 = axes[2].twinx()
    ax2.plot(t, data["hpfp"][idx], color="tab:red", label="HPFP effective volume")
    ax2.set_ylabel("HPFP effective volume (%)", color="tab:red", fontweight="bold")
    axes[2].set_title("Fuel-pressure response")

    axes[3].plot(t, data["lambda"][idx], label="Lambda")
    axes[3].plot(t, data["lambda_sp"][idx], label="Lambda SP")
    axes[3].set_ylabel("Lambda", fontweight="bold")
    axes[3].set_xlabel("Time from first large RPM fall (s)", fontweight="bold")
    ax3 = axes[3].twinx()
    ax3.plot(t, knock, color="tab:red", label="Most-retarded cylinder")
    ax3.set_ylabel("Knock retard (°)", color="tab:red", fontweight="bold")
    axes[3].set_title("Combustion recovery")
    axes[3].legend(fontsize=8, loc="upper left")

    fig.suptitle(f"R15 worst WOT upshift edge — {path.name}", fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = PLOT_DIR / "r15_worst_upshift.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)

    put_error = data["put"][idx] - data["put_sp"][idx]
    rail_error = (data["rail"][idx] - data["rail_sp"][idx]) / 100.0
    print("\nWorst WOT upshift edge (11_35_28, 3→4):")
    print(f"  peak PUT {np.max(data['put'][idx]):.1f} kPa; peak PUT error {np.max(put_error):+.1f} kPa")
    print(f"  worst DI rail error {np.min(rail_error):+.1f} bar; HPFP max {np.max(data['hpfp'][idx]):.1f}%")
    print(f"  turbo max {np.max(data['turbo'][idx]):.1f} krpm; airmass max {np.max(data['airmass'][idx]) * 1000:.0f} mg/stk")
    print(f"  knock worst {np.min(knock):+.1f}°; torque limiter values {np.unique(data['torque_lim'][idx])}")
    print(f"wrote {out}")


def plot_knock_events() -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex="col")
    for column, (tag, onset, context) in enumerate(KNOCK_EVENTS):
        path = paths_for(HERE, (tag,))[0]
        data = load(path)
        end = onset
        while end + 1 < len(data["rpm"]) and data["pedal"][end + 1] >= 90.0:
            end += 1
        falling = np.flatnonzero(np.diff(data["rpm"][onset:end + 1]) < -300.0)
        if falling.size:
            end = onset + int(falling[0])
        settled = ((data["torque"][onset:end + 1] >= 250.0)
                   & ((data["torque_req"][onset:end + 1]
                       - data["torque"][onset:end + 1]) <= 80.0))
        unsettled = np.flatnonzero(~settled)
        if unsettled.size:
            end = min(end, onset + max(0, int(unsettled[0]) - 1))
        idx = np.arange(max(0, onset - 8), end + 1)
        rpm = data["rpm"][idx]

        ax = axes[0, column]
        for cylinder in range(1, 5):
            ax.plot(rpm, data[f"knock_{cylinder}"][idx],
                    label=f"Cylinder {cylinder}")
        ax.axvline(data["rpm"][onset], color="0.25", ls="--", lw=1)
        ax.axhline(-3.0, color="tab:red", ls="--", lw=1)
        ax.set_ylabel("Knock retard (°)", fontweight="bold")
        ax.set_title(f"{tag}: {context}")
        ax.legend(fontsize=8, ncol=2)
        style_axis(ax)

        ax = axes[1, column]
        ax.plot(rpm, data["ign"][idx], label="Ign Avg")
        ax.plot(rpm, data["ign_table"][idx], label="Ign Table")
        ax.axvline(data["rpm"][onset], color="0.25", ls="--", lw=1)
        ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
        ax.set_ylabel("Ignition advance (°)", fontweight="bold")
        ax.legend(fontsize=8)
        style_axis(ax)

        cylinder = int(np.argmin([data[f"knock_{c}"][onset] for c in range(1, 5)]) + 1)
        print(f"\nKnock event {tag}: cylinder {cylinder}, onset {data['rpm'][onset]:.0f} rpm, "
              f"worst {min(data[f'knock_{cylinder}'][idx]):+.1f}°, "
              f"IAT {data['iat'][onset]:.1f}°C, airmass {data['airmass'][onset] * 1000:.0f} mg/stk, "
              f"PUT error {data['put'][onset] - data['put_sp'][onset]:+.1f} kPa")

    fig.suptitle("R15 loaded-WOT knock events — two pulls, two cylinders, same RPM/load zone",
                 fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = PLOT_DIR / "r15_knock_events.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    verify_table_deltas()
    r14 = band_stats(combine_clean(HERE.parent / "BasicsGuide_R14", R14_CLEAN_TAGS))
    r15 = band_stats(combine_clean(HERE, R15_CLEAN_TAGS))
    print_band_table("R14", r14)
    print_band_table("R15", r15)
    plot_comparison(r14, r15)
    plot_worst_shift()
    plot_knock_events()


if __name__ == "__main__":
    main()
