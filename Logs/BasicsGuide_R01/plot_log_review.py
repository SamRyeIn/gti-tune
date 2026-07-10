#!/usr/bin/env python3
"""Generate evidence plots for the BasicsGuide_R01 log review.

The script intentionally uses only the Python standard library plus matplotlib so
it can run in the SimosTools workspace without a pandas dependency.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


LOG_DIR = Path(__file__).resolve().parent
PLOT_DIR = LOG_DIR / "plots"

CSV_GLOB = "simostools-*.csv"


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return math.nan


def load_logs() -> list[dict[str, object]]:
    logs: list[dict[str, object]] = []
    for path in sorted(LOG_DIR.glob(CSV_GLOB)):
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        logs.append({"path": path, "name": path.stem.replace("simostools-", ""), "rows": rows})
    if not logs:
        raise FileNotFoundError(f"No {CSV_GLOB} files found under {LOG_DIR}")
    return logs


def is_wot(row: dict[str, str]) -> bool:
    return (
        as_float(row, "Pedal Pos (%)") >= 95.0
        and as_float(row, "TPS (%)") >= 60.0
        and as_float(row, "Engine Speed (rpm)") >= 2500.0
    )


def is_loaded_wot(row: dict[str, str]) -> bool:
    return is_wot(row) and as_float(row, "Airmass (mg/stk)") >= 900.0


def is_settled_wot(row: dict[str, str]) -> bool:
    torque = as_float(row, "Torque (Nm)")
    torque_req = as_float(row, "Torque Req (Nm)")
    return is_loaded_wot(row) and torque >= 250.0 and (torque_req - torque) <= 120.0


def rows_matching(logs: list[dict[str, object]], predicate) -> list[tuple[dict[str, object], dict[str, str]]]:
    points: list[tuple[dict[str, object], dict[str, str]]] = []
    for log in logs:
        for row in log["rows"]:  # type: ignore[index]
            if predicate(row):
                points.append((log, row))
    return points


def values(points, key: str) -> list[float]:
    return [as_float(row, key) for _, row in points if not math.isnan(as_float(row, key))]


def scatter_by_log(ax, logs, y_func, predicate=is_loaded_wot, marker_size=12):
    cmap = plt.get_cmap("tab10")
    for idx, log in enumerate(logs):
        rows = [row for row in log["rows"] if predicate(row)]  # type: ignore[index]
        if not rows:
            continue
        x = [as_float(row, "Engine Speed (rpm)") for row in rows]
        y = [y_func(row) for row in rows]
        ax.scatter(x, y, s=marker_size, alpha=0.68, color=cmap(idx % 10), label=log["name"])


def annotate_max(ax, points, y_func, label: str, y_offset: float = 0.0):
    valid = [(log, row, y_func(row)) for log, row in points if not math.isnan(y_func(row))]
    if not valid:
        return
    log, row, y = max(valid, key=lambda item: item[2])
    rpm = as_float(row, "Engine Speed (rpm)")
    ax.annotate(
        label.format(value=y, rpm=rpm, log=log["name"]),
        xy=(rpm, y),
        xytext=(rpm + 120.0, y + y_offset),
        arrowprops={"arrowstyle": "->", "linewidth": 0.8},
        fontsize=8,
    )


def style_axes(ax, title: str, xlabel: str, ylabel: str):
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(xlabel, fontweight="bold")
    ax.set_ylabel(ylabel, fontweight="bold")
    ax.grid(True, which="major", alpha=0.35)
    ax.grid(True, which="minor", alpha=0.18)
    ax.minorticks_on()


def save(fig, filename: str):
    fig.tight_layout()
    fig.savefig(PLOT_DIR / filename, dpi=180)
    plt.close(fig)


def plot_boost_overshoot(logs):
    points = rows_matching(logs, is_loaded_wot)
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    scatter_by_log(axes[0], logs, lambda row: as_float(row, "PUT (kpa)"))
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "PUT SP (kpa)"), marker_size=7)
    axes[0].axhline(269.0, color="0.25", linestyle="--", linewidth=0.9, label="269 kPa reference")
    style_axes(axes[0], "PUT Actual and Target During Loaded WOT", "Engine Speed (rpm)", "PUT / PUT SP (kPa)")

    scatter_by_log(axes[1], logs, lambda row: as_float(row, "PUT (kpa)") - as_float(row, "PUT SP (kpa)"))
    axes[1].axhspan(18.0, 26.0, color="tab:red", alpha=0.12, label="+18 to +26 kPa finding band")
    axes[1].axhline(0.0, color="0.25", linewidth=0.9)
    axes[1].axhline(10.0, color="tab:orange", linestyle="--", linewidth=0.9, label="+10 kPa watch line")
    annotate_max(
        axes[1],
        points,
        lambda row: as_float(row, "PUT (kpa)") - as_float(row, "PUT SP (kpa)"),
        "max +{value:.1f} kPa at {rpm:.0f} rpm",
        2.0,
    )
    style_axes(axes[1], "PUT Overshoot During Loaded WOT", "Engine Speed (rpm)", "PUT - PUT SP (kPa)")
    axes[1].legend(loc="best", fontsize=8)
    save(fig, "boost_overshoot.png")


def plot_knock_retard(logs):
    fig, ax = plt.subplots(figsize=(11, 5.8))

    def min_knock(row):
        return min(
            as_float(row, "Knock Cyl 1 (deg)") if "Knock Cyl 1 (deg)" in row else as_float(row, "Knock Cyl 1 (°)"),
            as_float(row, "Knock Cyl 2 (deg)") if "Knock Cyl 2 (deg)" in row else as_float(row, "Knock Cyl 2 (°)"),
            as_float(row, "Knock Cyl 3 (deg)") if "Knock Cyl 3 (deg)" in row else as_float(row, "Knock Cyl 3 (°)"),
            as_float(row, "Knock Cyl 4 (deg)") if "Knock Cyl 4 (deg)" in row else as_float(row, "Knock Cyl 4 (°)"),
        )

    scatter_by_log(ax, logs, min_knock)
    ax.axhline(0.0, color="0.25", linewidth=0.9)
    ax.axhline(-3.0, color="tab:red", linestyle="--", linewidth=1.1, label="-3.0 deg finding")
    style_axes(ax, "Minimum Per-Cylinder Knock Retard During Loaded WOT", "Engine Speed (rpm)", "Most Retarded Cylinder (deg)")
    ax.legend(loc="best", fontsize=8)
    save(fig, "knock_retard.png")


def plot_lambda_fueling(logs):
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    settled = rows_matching(logs, is_settled_wot)
    transient = rows_matching(logs, lambda row: is_loaded_wot(row) and not is_settled_wot(row))

    for ax in axes:
        ax.axhline(0.0, color="0.25", linewidth=0.9)
        ax.axhline(0.03, color="tab:orange", linestyle="--", linewidth=0.9, label="+0.03 lean watch line")

    axes[0].scatter(
        values(settled, "Engine Speed (rpm)"),
        [as_float(row, "Lambda (l)") - as_float(row, "Lambda SP (l)") for _, row in settled],
        s=12,
        alpha=0.65,
        label="Settled loaded WOT",
    )
    axes[0].scatter(
        values(transient, "Engine Speed (rpm)"),
        [as_float(row, "Lambda (l)") - as_float(row, "Lambda SP (l)") for _, row in transient],
        s=12,
        alpha=0.45,
        color="tab:red",
        label="Shift / torque-cut transient",
    )
    style_axes(axes[0], "Lambda Error Separates Settled WOT From Transients", "Engine Speed (rpm)", "Lambda - Lambda SP")
    axes[0].set_ylim(-0.08, 0.45)
    axes[0].legend(loc="best", fontsize=8)

    axes[1].scatter(
        [as_float(row, "Engine Speed (rpm)") for _, row in settled],
        [as_float(row, "Lambda (l)") for _, row in settled],
        s=12,
        alpha=0.65,
        label="Lambda actual",
    )
    axes[1].scatter(
        [as_float(row, "Engine Speed (rpm)") for _, row in settled],
        [as_float(row, "Lambda SP (l)") for _, row in settled],
        s=8,
        alpha=0.65,
        label="Lambda target",
    )
    style_axes(axes[1], "Settled Loaded WOT Lambda Tracks Target", "Engine Speed (rpm)", "Lambda")
    axes[1].legend(loc="best", fontsize=8)
    save(fig, "lambda_fueling.png")


def plot_fuel_pressure(logs):
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "FP DI (bar)"))
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "FP DI SP (bar)"), marker_size=7)
    style_axes(axes[0], "DI Fuel Pressure Tracks Setpoint", "Engine Speed (rpm)", "DI Pressure (bar)")

    scatter_by_log(axes[1], logs, lambda row: as_float(row, "FP DI (bar)") - as_float(row, "FP DI SP (bar)"))
    axes[1].axhline(0.0, color="0.25", linewidth=0.9)
    axes[1].axhline(-10.0, color="tab:orange", linestyle="--", linewidth=0.9, label="-10 bar watch line")
    style_axes(axes[1], "DI Fuel Pressure Error", "Engine Speed (rpm)", "FP DI - FP DI SP (bar)")
    axes[1].legend(loc="best", fontsize=8)

    scatter_by_log(axes[2], logs, lambda row: as_float(row, "LPFP Duty (%)"))
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "HPFP Eff Vol (%)"), marker_size=7)
    axes[2].axhline(85.0, color="tab:orange", linestyle="--", linewidth=0.9, label="85% watch line")
    axes[2].axhline(98.0, color="tab:red", linestyle="--", linewidth=0.9, label="98% watch line")
    style_axes(axes[2], "Fuel System Duty / Effective Volume", "Engine Speed (rpm)", "Percent")
    axes[2].legend(loc="best", fontsize=8)
    save(fig, "fuel_pressure.png")


def plot_turbo_temps(logs):
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "Turbo Speed (rpm)"))
    axes[0].axhline(220.0, color="tab:red", linestyle="--", linewidth=0.9, label="220k revised limit")
    axes[0].axhline(190.0, color="tab:orange", linestyle="--", linewidth=0.9, label="about 191k observed peak")
    style_axes(axes[0], "Turbo Speed During Loaded WOT", "Engine Speed (rpm)", "Turbo Speed (k rpm logged)")
    axes[0].legend(loc="best", fontsize=8)

    scatter_by_log(axes[1], logs, lambda row: as_float(row, "Turbo Air Temp (°C)"))
    axes[1].axhline(176.0, color="tab:orange", linestyle="--", linewidth=0.9, label="about 176 deg C observed peak")
    style_axes(axes[1], "Turbo Air Temperature During Loaded WOT", "Engine Speed (rpm)", "Turbo Air Temp (deg C)")
    axes[1].legend(loc="best", fontsize=8)

    scatter_by_log(axes[2], logs, lambda row: as_float(row, "IAT (°C)"))
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "Oil Temp (°C)"), marker_size=7)
    style_axes(axes[2], "IAT and Oil Temperature Context", "Engine Speed (rpm)", "Temperature (deg C)")
    save(fig, "turbo_temps.png")


def plot_performance_summary(logs):
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "Boost (psi)"))
    axes[0].axhline(24.0, color="tab:green", linestyle="--", linewidth=0.9, label="24-25 psi typical band")
    axes[0].axhline(25.0, color="tab:green", linestyle="--", linewidth=0.9)
    axes[0].axhline(26.9, color="tab:red", linestyle="--", linewidth=0.9, label="26.9 psi observed peak")
    style_axes(axes[0], "Boost Performance", "Engine Speed (rpm)", "Boost (psi)")
    axes[0].legend(loc="best", fontsize=8)

    scatter_by_log(axes[1], logs, lambda row: as_float(row, "Airmass (mg/stk)"))
    axes[1].axhline(1500.0, color="tab:red", linestyle="--", linewidth=0.9, label="about 1.50 g/stk observed peak")
    style_axes(axes[1], "Airmass Performance", "Engine Speed (rpm)", "Airmass (mg/stk)")
    axes[1].legend(loc="best", fontsize=8)

    scatter_by_log(axes[2], logs, lambda row: as_float(row, "Torque (Nm)"))
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "Torque Req (Nm)"), marker_size=7)
    axes[2].axhline(449.0, color="tab:red", linestyle="--", linewidth=0.9, label="449 Nm observed peak")
    style_axes(axes[2], "Reported Torque Performance", "Engine Speed (rpm)", "Torque (Nm)")
    axes[2].legend(loc="best", fontsize=8)
    save(fig, "performance_summary.png")


def main() -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    logs = load_logs()
    plot_boost_overshoot(logs)
    plot_knock_retard(logs)
    plot_lambda_fueling(logs)
    plot_fuel_pressure(logs)
    plot_turbo_temps(logs)
    plot_performance_summary(logs)
    print(f"Wrote plots to {PLOT_DIR}")


if __name__ == "__main__":
    main()
