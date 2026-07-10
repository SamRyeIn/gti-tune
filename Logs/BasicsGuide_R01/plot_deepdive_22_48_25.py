#!/usr/bin/env python3
"""Deep-dive plots for the longest BasicsGuide_R01 log.

Focus log: simostools-2026_07_07-22_48_25.csv, the long 2nd/3rd/4th WOT
event. Outputs are written under plots/deepdive_22_48_25/.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


LOG_DIR = Path(__file__).resolve().parent
LOG_FILE = LOG_DIR / "simostools-2026_07_07-22_48_25.csv"
PLOT_DIR = LOG_DIR / "plots" / "deepdive_22_48_25"


def actual_gear(row: dict[str, str]) -> int:
    """SimosTools logs this channel zero-based: logged 0 == real 1st gear."""
    return int(round(as_float(row, "Gear ()"))) + 1


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return math.nan


def load_rows() -> list[dict[str, str]]:
    with LOG_FILE.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"No rows found in {LOG_FILE}")
    t0 = as_float(rows[0], "Time")
    for row in rows:
        row["Time Rel (s)"] = f"{as_float(row, 'Time') - t0:.6f}"
    return rows


def col(rows: list[dict[str, str]], key: str) -> list[float]:
    return [as_float(row, key) for row in rows]


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


def gear_changes(rows: list[dict[str, str]]) -> list[tuple[float, int]]:
    changes: list[tuple[float, int]] = []
    last = None
    for row in rows:
        gear = actual_gear(row)
        if last is None:
            last = gear
            continue
        if gear != last:
            changes.append((as_float(row, "Time Rel (s)"), gear))
            last = gear
    return changes


def add_gear_markers(ax, changes: list[tuple[float, int]]) -> None:
    ylim = ax.get_ylim()
    for t, gear in changes:
        ax.axvline(t, color="0.25", linestyle=":", linewidth=0.9, alpha=0.75)
        ax.text(t, ylim[1], f"G{gear}", ha="left", va="top", fontsize=8, color="0.25")
    ax.set_ylim(ylim)


def style_axes(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel(xlabel, fontweight="bold")
    ax.set_ylabel(ylabel, fontweight="bold")
    ax.grid(True, which="major", alpha=0.35)
    ax.grid(True, which="minor", alpha=0.18)
    ax.minorticks_on()


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(PLOT_DIR / name, dpi=180)
    plt.close(fig)


def rows_where(rows: list[dict[str, str]], predicate) -> list[dict[str, str]]:
    return [row for row in rows if predicate(row)]


def scatter_by_gear(ax, rows: list[dict[str, str]], y_func, label_prefix: str = "") -> None:
    cmap = {1: "tab:gray", 2: "tab:blue", 3: "tab:orange", 4: "tab:green"}
    for gear in sorted({actual_gear(row) for row in rows}):
        gear_rows = [row for row in rows if actual_gear(row) == gear]
        ax.scatter(
            [as_float(row, "Engine Speed (rpm)") for row in gear_rows],
            [y_func(row) for row in gear_rows],
            s=14,
            alpha=0.68,
            color=cmap.get(gear, "tab:purple"),
            label=f"{label_prefix}G{gear}",
        )


def plot_run_overview(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(t, col(rows, "Engine Speed (rpm)"), color="tab:blue", label="RPM")
    style_axes(axes[0], "Run Overview: RPM", "Time (s)", "RPM")
    axes[1].plot(t, col(rows, "Vehicle Speed (km/hr)"), color="tab:green", label="Speed")
    style_axes(axes[1], "Vehicle Speed", "Time (s)", "Speed (km/hr)")
    axes[2].step(t, [actual_gear(row) for row in rows], where="post", color="tab:purple", label="Actual Gear")
    style_axes(axes[2], "Actual Gear (Logged Gear + 1)", "Time (s)", "Actual Gear")
    axes[3].plot(t, col(rows, "Pedal Pos (%)"), color="tab:red", label="Pedal")
    axes[3].plot(t, col(rows, "TPS (%)"), color="tab:orange", label="TPS")
    axes[3].axhline(95, color="tab:red", linestyle="--", linewidth=0.8, alpha=0.7)
    style_axes(axes[3], "Driver Demand and Throttle", "Time (s)", "Percent")
    axes[3].legend(loc="best", fontsize=8)
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "01_run_overview.png")


def plot_boost_time(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(t, col(rows, "PUT (kpa)"), label="PUT", color="tab:blue")
    axes[0].plot(t, col(rows, "PUT SP (kpa)"), label="PUT SP", color="tab:orange")
    axes[0].axhline(269, color="0.3", linestyle="--", linewidth=0.9, label="269 kPa reference")
    style_axes(axes[0], "PUT Tracking", "Time (s)", "kPa")
    axes[0].legend(loc="best", fontsize=8)

    err = [put_error(row) for row in rows]
    axes[1].plot(t, err, color="tab:red", label="PUT - PUT SP")
    axes[1].axhline(0, color="0.25", linewidth=0.9)
    axes[1].axhspan(18, 26, color="tab:red", alpha=0.12, label="+18 to +26 kPa finding band")
    style_axes(axes[1], "PUT Overshoot", "Time (s)", "kPa")
    axes[1].legend(loc="best", fontsize=8)

    axes[2].plot(t, col(rows, "Boost (psi)"), color="tab:green", label="Boost")
    axes[2].axhline(24, color="tab:orange", linestyle="--", linewidth=0.8)
    axes[2].axhline(25, color="tab:orange", linestyle="--", linewidth=0.8, label="24-25 psi band")
    axes[2].axhline(26.9, color="tab:red", linestyle="--", linewidth=0.9, label="26.9 psi peak finding")
    style_axes(axes[2], "Boost", "Time (s)", "psi")
    axes[2].legend(loc="best", fontsize=8)
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "02_boost_tracking_time.png")


def plot_boost_rpm(rows: list[dict[str, str]]) -> None:
    loaded = rows_where(rows, is_loaded_wot)
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    scatter_by_gear(axes[0], loaded, lambda row: as_float(row, "Boost (psi)"))
    axes[0].axhline(24, color="tab:orange", linestyle="--", linewidth=0.8)
    axes[0].axhline(25, color="tab:orange", linestyle="--", linewidth=0.8, label="24-25 psi band")
    axes[0].axhline(26.9, color="tab:red", linestyle="--", linewidth=0.9, label="26.9 psi peak")
    style_axes(axes[0], "Boost vs RPM by Gear During Loaded WOT", "Engine Speed (rpm)", "Boost (psi)")
    axes[0].legend(loc="best", fontsize=8)

    scatter_by_gear(axes[1], loaded, put_error)
    axes[1].axhline(0, color="0.25", linewidth=0.9)
    axes[1].axhspan(18, 26, color="tab:red", alpha=0.12, label="+18 to +26 kPa finding band")
    style_axes(axes[1], "PUT Error vs RPM by Gear During Loaded WOT", "Engine Speed (rpm)", "PUT - PUT SP (kPa)")
    axes[1].legend(loc="best", fontsize=8)
    save(fig, "03_boost_vs_rpm_by_gear.png")


def plot_knock_timing(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    for cyl in range(1, 5):
        axes[0].plot(t, col(rows, f"Knock Cyl {cyl} (°)"), label=f"Cyl {cyl}")
    axes[0].axhline(-3, color="tab:red", linestyle="--", linewidth=0.9, label="-3 deg finding")
    style_axes(axes[0], "Per-Cylinder Knock Retard", "Time (s)", "deg")
    axes[0].legend(loc="best", fontsize=8, ncol=3)

    axes[1].plot(t, [min_knock(row) for row in rows], color="tab:red", label="Worst cylinder")
    axes[1].axhline(-3, color="tab:red", linestyle="--", linewidth=0.9)
    style_axes(axes[1], "Worst-Cylinder Knock Retard", "Time (s)", "deg")

    axes[2].plot(t, col(rows, "Ign Avg (°)"), color="tab:purple", label="Ign Avg")
    style_axes(axes[2], "Average Ignition Angle", "Time (s)", "deg")

    axes[3].plot(t, col(rows, "Airmass (mg/stk)"), color="tab:blue", label="Airmass")
    style_axes(axes[3], "Airmass Context", "Time (s)", "mg/stk")
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "04_knock_timing_time.png")


def plot_lambda_transients(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(t, col(rows, "Lambda (l)"), color="tab:blue", label="Lambda")
    axes[0].plot(t, col(rows, "Lambda SP (l)"), color="tab:orange", label="Lambda SP")
    axes[0].set_ylim(0.65, 1.25)
    style_axes(axes[0], "Lambda Tracking", "Time (s)", "Lambda")
    axes[0].legend(loc="best", fontsize=8)

    err = [lambda_error(row) for row in rows]
    axes[1].plot(t, err, color="tab:red", label="Lambda - Lambda SP")
    axes[1].axhline(0, color="0.25", linewidth=0.9)
    axes[1].axhline(0.03, color="tab:orange", linestyle="--", linewidth=0.9, label="+0.03 lean watch")
    axes[1].set_ylim(-0.1, 0.8)
    style_axes(axes[1], "Lambda Error Shows Shift / Torque-Cut Spikes", "Time (s)", "Lambda error")
    axes[1].legend(loc="best", fontsize=8)

    axes[2].plot(t, col(rows, "Torque (Nm)"), color="tab:green", label="Torque")
    axes[2].plot(t, col(rows, "Torque Req (Nm)"), color="tab:purple", label="Torque Req")
    style_axes(axes[2], "Torque Collapse Context", "Time (s)", "Nm")
    axes[2].legend(loc="best", fontsize=8)

    axes[3].plot(t, col(rows, "STFT (%)"), color="tab:blue", label="STFT")
    axes[3].plot(t, col(rows, "LTFT (%)"), color="tab:orange", label="LTFT")
    style_axes(axes[3], "Fuel Trim Context", "Time (s)", "Percent")
    axes[3].legend(loc="best", fontsize=8)
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "05_lambda_transients_time.png")


def plot_fuel_system(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(t, col(rows, "FP DI (bar)"), color="tab:blue", label="FP DI")
    axes[0].plot(t, col(rows, "FP DI SP (bar)"), color="tab:orange", label="FP DI SP")
    style_axes(axes[0], "DI Fuel Pressure", "Time (s)", "bar")
    axes[0].legend(loc="best", fontsize=8)

    axes[1].plot(t, [as_float(row, "FP DI (bar)") - as_float(row, "FP DI SP (bar)") for row in rows], color="tab:red")
    axes[1].axhline(0, color="0.25", linewidth=0.9)
    axes[1].axhline(-10, color="tab:orange", linestyle="--", linewidth=0.9, label="-10 bar watch")
    style_axes(axes[1], "DI Fuel Pressure Error", "Time (s)", "bar")
    axes[1].legend(loc="best", fontsize=8)

    axes[2].plot(t, col(rows, "LPFP Duty (%)"), color="tab:green", label="LPFP Duty")
    axes[2].plot(t, col(rows, "HPFP Eff Vol (%)"), color="tab:purple", label="HPFP Eff Vol")
    axes[2].axhline(85, color="tab:orange", linestyle="--", linewidth=0.9, label="85% watch")
    axes[2].axhline(98, color="tab:red", linestyle="--", linewidth=0.9, label="98% watch")
    style_axes(axes[2], "Fuel System Headroom", "Time (s)", "Percent")
    axes[2].legend(loc="best", fontsize=8)

    axes[3].plot(t, col(rows, "FP MPI (bar)"), color="tab:blue", label="FP MPI")
    axes[3].plot(t, col(rows, "FP MPI SP (bar)"), color="tab:orange", label="FP MPI SP")
    style_axes(axes[3], "MPI Fuel Pressure", "Time (s)", "bar")
    axes[3].legend(loc="best", fontsize=8)
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "06_fuel_system_time.png")


def plot_turbo_heat(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(t, col(rows, "Turbo Speed (rpm)"), color="tab:red", label="Turbo Speed")
    axes[0].axhline(190, color="tab:orange", linestyle="--", linewidth=0.9, label="about 191k observed peak")
    axes[0].axhline(220, color="tab:red", linestyle="--", linewidth=0.9, label="220k revised limit")
    style_axes(axes[0], "Turbo Speed", "Time (s)", "k rpm logged")
    axes[0].legend(loc="best", fontsize=8)

    axes[1].plot(t, col(rows, "Turbo Air Temp (°C)"), color="tab:orange", label="Turbo Air Temp")
    axes[1].axhline(176, color="tab:red", linestyle="--", linewidth=0.9, label="about 176 deg C observed peak")
    style_axes(axes[1], "Turbo Air Temperature", "Time (s)", "deg C")
    axes[1].legend(loc="best", fontsize=8)

    axes[2].plot(t, col(rows, "IAT (°C)"), color="tab:blue", label="IAT")
    axes[2].plot(t, col(rows, "Oil Temp (°C)"), color="tab:green", label="Oil Temp")
    axes[2].plot(t, col(rows, "Coolant Temp (°C)"), color="tab:purple", label="Coolant Temp")
    style_axes(axes[2], "Vehicle Temperature Context", "Time (s)", "deg C")
    axes[2].legend(loc="best", fontsize=8)

    axes[3].plot(t, col(rows, "Wastegate (%)"), color="tab:blue", label="Wastegate")
    axes[3].plot(t, col(rows, "Wastegate SP (%)"), color="tab:orange", label="Wastegate SP")
    style_axes(axes[3], "Wastegate Position Context", "Time (s)", "Percent")
    axes[3].legend(loc="best", fontsize=8)
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "07_turbo_heat_time.png")


def plot_performance(rows: list[dict[str, str]], changes: list[tuple[float, int]]) -> None:
    t = col(rows, "Time Rel (s)")
    fig, axes = plt.subplots(4, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(t, col(rows, "Airmass (mg/stk)"), color="tab:blue", label="Airmass")
    axes[0].axhline(1500, color="tab:red", linestyle="--", linewidth=0.9, label="about 1.50 g/stk finding")
    style_axes(axes[0], "Airmass", "Time (s)", "mg/stk")
    axes[0].legend(loc="best", fontsize=8)

    axes[1].plot(t, col(rows, "Torque (Nm)"), color="tab:green", label="Torque")
    axes[1].plot(t, col(rows, "Torque Req (Nm)"), color="tab:purple", label="Torque Req")
    axes[1].axhline(449, color="tab:red", linestyle="--", linewidth=0.9, label="449 Nm observed peak")
    style_axes(axes[1], "Torque", "Time (s)", "Nm")
    axes[1].legend(loc="best", fontsize=8)

    axes[2].plot(t, col(rows, "Calc HP (hp)"), color="tab:red", label="Calc HP")
    axes[2].plot(t, col(rows, "Calc TQ (nm)"), color="tab:orange", label="Calc TQ")
    style_axes(axes[2], "Calculated Power / Torque Channels", "Time (s)", "Logged units")
    axes[2].legend(loc="best", fontsize=8)

    axes[3].plot(t, col(rows, "Airflow (kg/hr)"), color="tab:blue", label="Airflow")
    style_axes(axes[3], "Airflow", "Time (s)", "kg/hr")
    for ax in axes:
        add_gear_markers(ax, changes)
    save(fig, "08_performance_time.png")


def print_summary(rows: list[dict[str, str]]) -> None:
    loaded = rows_where(rows, is_loaded_wot)
    settled = rows_where(rows, is_settled_wot)
    max_put_row = max(loaded, key=lambda row: as_float(row, "PUT (kpa)"))
    max_boost_row = max(loaded, key=lambda row: as_float(row, "Boost (psi)"))
    max_err_row = max(loaded, key=put_error)
    min_knock_row = min(loaded, key=min_knock)
    max_turbo_row = max(loaded, key=lambda row: as_float(row, "Turbo Speed (rpm)"))
    max_tair_row = max(loaded, key=lambda row: as_float(row, "Turbo Air Temp (°C)"))
    max_airmass_row = max(loaded, key=lambda row: as_float(row, "Airmass (mg/stk)"))
    max_torque_row = max(loaded, key=lambda row: as_float(row, "Torque (Nm)"))
    settled_lam_err = [lambda_error(row) for row in settled]
    print(f"Rows: {len(rows)} total, {len(loaded)} loaded WOT, {len(settled)} settled loaded WOT")
    print(f"Max PUT: {as_float(max_put_row, 'PUT (kpa)'):.1f} kPa at {as_float(max_put_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Max boost: {as_float(max_boost_row, 'Boost (psi)'):.1f} psi at {as_float(max_boost_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Max PUT error: {put_error(max_err_row):.1f} kPa at {as_float(max_err_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Worst knock: {min_knock(min_knock_row):.1f} deg at {as_float(min_knock_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Max turbo speed: {as_float(max_turbo_row, 'Turbo Speed (rpm)'):.1f} logged k rpm at {as_float(max_turbo_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Max turbo air temp: {as_float(max_tair_row, 'Turbo Air Temp (°C)'):.1f} deg C at {as_float(max_tair_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Max airmass: {as_float(max_airmass_row, 'Airmass (mg/stk)'):.0f} mg/stk at {as_float(max_airmass_row, 'Engine Speed (rpm)'):.0f} rpm")
    print(f"Max torque: {as_float(max_torque_row, 'Torque (Nm)'):.0f} Nm at {as_float(max_torque_row, 'Engine Speed (rpm)'):.0f} rpm")
    if settled_lam_err:
        print(f"Settled lambda error: avg {sum(settled_lam_err) / len(settled_lam_err):.3f}, max {max(settled_lam_err):.3f}")


def main() -> None:
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    changes = gear_changes(rows)
    print_summary(rows)
    plot_run_overview(rows, changes)
    plot_boost_time(rows, changes)
    plot_boost_rpm(rows)
    plot_knock_timing(rows, changes)
    plot_lambda_transients(rows, changes)
    plot_fuel_system(rows, changes)
    plot_turbo_heat(rows, changes)
    plot_performance(rows, changes)
    print(f"Wrote deep-dive plots to {PLOT_DIR}")


if __name__ == "__main__":
    main()
