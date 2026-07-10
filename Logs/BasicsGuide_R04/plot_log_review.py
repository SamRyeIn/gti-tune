#!/usr/bin/env python3
"""Generate evidence plots for the BasicsGuide_R04 log review.

This R04 log uses actual gear numbering (`3` = 3rd gear), airmass in g/stk,
fuel pressure in kPa, and no turbo-air-temp channel. The plots normalize those
differences so the review can be compared against the R01 findings.
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


def airmass_mg(row: dict[str, str]) -> float:
    if "Airmass (mg/stk)" in row:
        return as_float(row, "Airmass (mg/stk)")
    if "Airmass (g/stk)" in row:
        return as_float(row, "Airmass (g/stk)") * 1000.0
    return math.nan


def actual_gear(row: dict[str, str]) -> float:
    # R04 PID list logs actual gear directly; R01's zero-indexed note does not apply here.
    return as_float(row, "Gear (gear)")


def min_knock(row: dict[str, str]) -> float:
    return min(
        as_float(row, "Knock Cyl 1 (°)"),
        as_float(row, "Knock Cyl 2 (°)"),
        as_float(row, "Knock Cyl 3 (°)"),
        as_float(row, "Knock Cyl 4 (°)"),
    )


def put_error(row: dict[str, str]) -> float:
    return as_float(row, "PUT (kpa)") - as_float(row, "PUT SP (kpa)")


def lambda_error(row: dict[str, str]) -> float:
    return as_float(row, "Lambda (l)") - as_float(row, "Lambda SP (l)")


def fp_di_bar(row: dict[str, str]) -> float:
    if "FP DI (bar)" in row:
        return as_float(row, "FP DI (bar)")
    return as_float(row, "FP DI (kpa)") / 100.0


def fp_di_sp_bar(row: dict[str, str]) -> float:
    if "FP DI SP (bar)" in row:
        return as_float(row, "FP DI SP (bar)")
    return as_float(row, "FP DI SP (kpa)") / 100.0


def is_wot(row: dict[str, str]) -> bool:
    return (
        actual_gear(row) == 3.0
        and as_float(row, "Pedal Pos (%)") >= 95.0
        and as_float(row, "TPS (%)") >= 60.0
        and as_float(row, "Engine Speed (rpm)") >= 2500.0
    )


def is_loaded_wot(row: dict[str, str]) -> bool:
    return is_wot(row) and airmass_mg(row) >= 900.0


def is_settled_wot(row: dict[str, str]) -> bool:
    torque = as_float(row, "Torque (Nm)")
    torque_req = as_float(row, "Torque Req (Nm)")
    return is_loaded_wot(row) and torque >= 250.0 and (torque_req - torque) <= 120.0


def assign_pull_labels(logs: list[dict[str, object]]) -> None:
    """Label contiguous loaded-WOT segments as Pull 1, Pull 2, etc."""
    pull_number = 0
    for log in logs:
        rows = log["rows"]  # type: ignore[index]
        current: list[dict[str, str]] = []
        previous_idx: int | None = None

        for idx, row in enumerate(rows):
            if not is_loaded_wot(row):
                continue
            if previous_idx is None or idx <= previous_idx + 2:
                current.append(row)
            else:
                pull_number += 1
                for pull_row in current:
                    pull_row["__pull_label"] = f"Pull {pull_number}"
                current = [row]
            previous_idx = idx

        if current:
            pull_number += 1
            for pull_row in current:
                pull_row["__pull_label"] = f"Pull {pull_number}"


def rows_matching(logs: list[dict[str, object]], predicate) -> list[tuple[dict[str, object], dict[str, str]]]:
    points: list[tuple[dict[str, object], dict[str, str]]] = []
    for log in logs:
        for row in log["rows"]:  # type: ignore[index]
            if predicate(row):
                points.append((log, row))
    return points


def scatter_by_log(ax, logs, y_func, predicate=is_loaded_wot, marker_size=12) -> None:
    cmap = plt.get_cmap("tab10")
    color_by_pull = {
        "Pull 1": cmap(0),
        "Pull 2": cmap(1),
        "Pull 3": cmap(2),
        "Pull 4": cmap(3),
    }
    plotted_labels: set[str] = set()
    for idx, log in enumerate(logs):
        rows = [row for row in log["rows"] if predicate(row)]  # type: ignore[index]
        if not rows:
            continue
        labels = sorted({row.get("__pull_label", str(log["name"])) for row in rows})
        for label in labels:
            label_rows = [row for row in rows if row.get("__pull_label", str(log["name"])) == label]
            x = [as_float(row, "Engine Speed (rpm)") for row in label_rows]
            y = [y_func(row) for row in label_rows]
            ax.scatter(
                x,
                y,
                s=marker_size,
                alpha=0.68,
                color=color_by_pull.get(label, cmap((idx + len(plotted_labels)) % 10)),
                label=label if label not in plotted_labels else None,
            )
            plotted_labels.add(label)


def annotate_max(ax, points, y_func, label: str, y_offset: float = 0.0) -> None:
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


def style_axes(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(xlabel, fontweight="bold")
    ax.set_ylabel(ylabel, fontweight="bold")
    ax.grid(True, which="major", alpha=0.35)
    ax.grid(True, which="minor", alpha=0.18)
    ax.minorticks_on()


def save(fig, filename: str) -> None:
    fig.tight_layout()
    fig.savefig(PLOT_DIR / filename, dpi=180)
    plt.close(fig)


def plot_boost_overshoot(logs) -> None:
    points = rows_matching(logs, is_loaded_wot)
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "PUT (kpa)"))
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "PUT SP (kpa)"), marker_size=7)
    style_axes(axes[0], "PUT Actual and Target During 3rd-Gear Loaded WOT", "Engine Speed (rpm)", "PUT / PUT SP (kPa)")

    scatter_by_log(axes[1], logs, put_error)
    axes[1].axhline(0.0, color="0.25", linewidth=0.9)
    axes[1].axhline(10.0, color="tab:orange", linestyle="--", linewidth=0.9, label="+10 kPa watch line")
    axes[1].axhline(20.0, color="tab:red", linestyle="--", linewidth=0.9, label="+20 kPa high overshoot")
    annotate_max(axes[1], points, put_error, "max +{value:.1f} kPa at {rpm:.0f} rpm", 2.0)
    style_axes(axes[1], "PUT Overshoot During 3rd-Gear Loaded WOT", "Engine Speed (rpm)", "PUT - PUT SP (kPa)")
    axes[1].legend(loc="best", fontsize=8)
    save(fig, "boost_overshoot.png")


def plot_knock_retard(logs) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    scatter_by_log(ax, logs, min_knock)
    ax.axhline(0.0, color="0.25", linewidth=0.9)
    ax.axhline(-1.5, color="tab:orange", linestyle="--", linewidth=0.9, label="-1.5 deg watch line")
    ax.axhline(-3.0, color="tab:red", linestyle="--", linewidth=1.1, label="-3.0 deg R01 finding")
    style_axes(ax, "Minimum Per-Cylinder Knock Retard During 3rd-Gear Loaded WOT", "Engine Speed (rpm)", "Most Retarded Cylinder (deg)")
    ax.legend(loc="best", fontsize=8)
    save(fig, "knock_retard.png")


def plot_lambda_fueling(logs) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    settled = rows_matching(logs, is_settled_wot)
    transient = rows_matching(logs, lambda row: is_loaded_wot(row) and not is_settled_wot(row))
    for ax in axes:
        ax.axhline(0.0, color="0.25", linewidth=0.9)
        ax.axhline(0.03, color="tab:orange", linestyle="--", linewidth=0.9, label="+0.03 lean watch line")
    axes[0].scatter([as_float(row, "Engine Speed (rpm)") for _, row in settled], [lambda_error(row) for _, row in settled], s=12, alpha=0.65, label="Settled loaded WOT")
    axes[0].scatter([as_float(row, "Engine Speed (rpm)") for _, row in transient], [lambda_error(row) for _, row in transient], s=12, alpha=0.45, color="tab:red", label="Transient / ramp")
    style_axes(axes[0], "Lambda Error During Loaded WOT", "Engine Speed (rpm)", "Lambda - Lambda SP")
    axes[0].legend(loc="best", fontsize=8)
    axes[1].scatter([as_float(row, "Engine Speed (rpm)") for _, row in settled], [as_float(row, "Lambda (l)") for _, row in settled], s=12, alpha=0.65, label="Lambda actual")
    axes[1].scatter([as_float(row, "Engine Speed (rpm)") for _, row in settled], [as_float(row, "Lambda SP (l)") for _, row in settled], s=8, alpha=0.65, label="Lambda target")
    style_axes(axes[1], "Settled Loaded WOT Lambda Tracks Target", "Engine Speed (rpm)", "Lambda")
    axes[1].legend(loc="best", fontsize=8)
    save(fig, "lambda_fueling.png")


def plot_fuel_pressure(logs) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, fp_di_bar)
    scatter_by_log(axes[0], logs, fp_di_sp_bar, marker_size=7)
    style_axes(axes[0], "DI Fuel Pressure Tracks Setpoint", "Engine Speed (rpm)", "DI Pressure (bar)")
    scatter_by_log(axes[1], logs, lambda row: fp_di_bar(row) - fp_di_sp_bar(row))
    axes[1].axhline(0.0, color="0.25", linewidth=0.9)
    axes[1].axhline(-10.0, color="tab:orange", linestyle="--", linewidth=0.9, label="-10 bar watch line")
    style_axes(axes[1], "DI Fuel Pressure Error", "Engine Speed (rpm)", "FP DI - FP DI SP (bar)")
    axes[1].legend(loc="best", fontsize=8)
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "LPFP Duty (%)"))
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "HPFP Eff Vol (%)"), marker_size=7)
    axes[2].axhline(85.0, color="tab:orange", linestyle="--", linewidth=0.9, label="85% LPFP watch")
    axes[2].axhline(98.0, color="tab:red", linestyle="--", linewidth=0.9, label="98% HPFP watch")
    style_axes(axes[2], "Fuel System Duty / Effective Volume", "Engine Speed (rpm)", "Percent")
    axes[2].legend(loc="best", fontsize=8)
    save(fig, "fuel_pressure.png")


def plot_turbo_temps(logs) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "Turbo Speed (rpm)"))
    axes[0].axhline(190.0, color="tab:orange", linestyle="--", linewidth=0.9, label="190 krpm watch")
    axes[0].axhline(220.0, color="tab:red", linestyle="--", linewidth=0.9, label="220 krpm revised limit")
    style_axes(axes[0], "Turbo Speed During Loaded WOT", "Engine Speed (rpm)", "Turbo Speed (k rpm logged)")
    axes[0].legend(loc="best", fontsize=8)
    scatter_by_log(axes[1], logs, lambda row: as_float(row, "IAT (°C)"))
    style_axes(axes[1], "Intake Air Temperature During Loaded WOT", "Engine Speed (rpm)", "IAT (deg C)")
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "Oil Temp (°C)"))
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "Trans Temp (°C)"), marker_size=7)
    style_axes(axes[2], "Oil and Transmission Temperature", "Engine Speed (rpm)", "Temperature (deg C)")
    axes[2].legend(loc="best", fontsize=8)
    save(fig, "turbo_temps.png")


def plot_wastegate(logs) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "WG Pos Base (%)"))
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "WG Pos Final (%)"), marker_size=7)
    style_axes(axes[0], "Wastegate Base and Final Position", "Engine Speed (rpm)", "WG Position (%)")
    axes[0].legend(loc="best", fontsize=8)
    scatter_by_log(axes[1], logs, lambda row: as_float(row, "WG I Value (%)"))
    scatter_by_log(axes[1], logs, lambda row: as_float(row, "WG P-D Value (%)"), marker_size=7)
    axes[1].axhline(0.0, color="0.25", linewidth=0.9)
    style_axes(axes[1], "Wastegate Closed-Loop Correction", "Engine Speed (rpm)", "Correction (%)")
    axes[1].legend(loc="best", fontsize=8)
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "WG Flow Des (kg/hr)"))
    style_axes(axes[2], "Desired Wastegate Flow", "Engine Speed (rpm)", "WG Flow Des (kg/hr)")
    save(fig, "wastegate_control.png")


def plot_flow_factors(logs) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "Intake Flow Fact ()"))
    scatter_by_log(axes[0], logs, lambda row: as_float(row, "Exh Flow Factor ()"), marker_size=7)
    style_axes(axes[0], "Wastegate Flow Factors During Loaded WOT", "Engine Speed (rpm)", "Flow Factor")
    axes[0].legend(loc="best", fontsize=8)
    scatter_by_log(axes[1], logs, put_error)
    axes[1].axhline(0.0, color="0.25", linewidth=0.9)
    style_axes(axes[1], "PUT Error for Flow-Factor Cell Selection", "Engine Speed (rpm)", "PUT - PUT SP (kPa)")
    save(fig, "flow_factors.png")


def plot_performance(logs) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    scatter_by_log(axes[0], logs, airmass_mg)
    style_axes(axes[0], "Airmass During Loaded WOT", "Engine Speed (rpm)", "Airmass (mg/stk)")
    scatter_by_log(axes[1], logs, lambda row: as_float(row, "Torque (Nm)"))
    scatter_by_log(axes[1], logs, lambda row: as_float(row, "Torque Req (Nm)"), marker_size=7)
    style_axes(axes[1], "Torque Actual and Requested", "Engine Speed (rpm)", "Torque (Nm)")
    axes[1].legend(loc="best", fontsize=8)
    scatter_by_log(axes[2], logs, lambda row: as_float(row, "Calc HP (hp)"))
    style_axes(axes[2], "Calculated Power", "Engine Speed (rpm)", "Power (hp)")
    save(fig, "performance_summary.png")


def main() -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    logs = load_logs()
    assign_pull_labels(logs)
    plot_boost_overshoot(logs)
    plot_knock_retard(logs)
    plot_lambda_fueling(logs)
    plot_fuel_pressure(logs)
    plot_turbo_temps(logs)
    plot_wastegate(logs)
    plot_flow_factors(logs)
    plot_performance(logs)
    print(f"Wrote plots to {PLOT_DIR}")


if __name__ == "__main__":
    main()
