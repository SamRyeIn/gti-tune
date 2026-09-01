"""Does R20's knock cluster early in the drive, as un-mixed octane booster would?

R20's slot 5 is calibrated for a dosed tank: pump 92 AKI plus VP Octanium
Unleaded at 10-11 oz per 10 US gallons. If the dose had not fully mixed when
the session started, the early pulls would be running on effectively lower
octane than the late ones, and the knock the R20 session recorded would be
front-loaded and then fade as the mixed fuel reached the rail.

This script tests that ordering directly. For every in-gear WOT window it
measures knock severity three ways - retard area (deg CRK x seconds, summed
over the four cylinders), the fraction of samples with any cylinder retarding,
and the worst single-cylinder retard - and ranks each against minutes into the
drive. Oil temperature is carried alongside as the competing explanation, since
it climbs monotonically through the session and would mimic a time trend.

Pulls that do not reach 6000 rpm are partial and are excluded from the trend:
a pull that ends at 4500 rpm cannot record the top-end knock the full pulls can,
so counting it as "clean" would bias the comparison toward whichever end of the
session those partials happen to fall.

Every input log uses ``Gear (gear)``, so the logged value is the actual gear and
needs no offset.

Usage:
    ../../Code/.venv/bin/python analyze_r20_knock_timeline.py
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PLOT_DIR = HERE / "plots"

KNOCK_CH = [f"Knock Cyl {i} (°)" for i in (1, 2, 3, 4)]
SAMPLE_DT_S = 0.04

#: In-gear WOT window: the pull's own gear, throttle open, and loaded enough
#: that the top two airmass rows of the `Spark modifier` grid are in play.
PULL_GEAR = 3
TPS_MIN_PCT = 60.0
AIRMASS_MIN_MG = 900.0

#: A pull below this peak rpm never reached the top-end knock zone.
FULL_PULL_RPM = 6000.0

#: Session start, for the minutes-into-drive axis: the first log's timestamp.
SESSION_START_S = 7 * 3600 + 51 * 60 + 22


def rank_corr(a, b):
    """Spearman rank correlation. scipy is not in this project's venv."""
    a = pd.Series(a).rank()
    b = pd.Series(b).rank()
    return float(np.corrcoef(a, b)[0, 1])


def minutes_into_drive(stem):
    """`07_57_32` -> minutes after the session's first log."""
    h, m, s = (int(p) for p in stem.split("_"))
    return (h * 3600 + m * 60 + s - SESSION_START_S) / 60.0


def load_pulls():
    rows = []
    for path in sorted(glob.glob(str(HERE / "simostools-*.csv"))):
        frame = pd.read_csv(path)
        frame.columns = [c.strip() for c in frame.columns]
        window = frame[
            (frame["Gear (gear)"] == PULL_GEAR)
            & (frame["TPS (%)"] >= TPS_MIN_PCT)
            & (frame["Airmass (g/stk)"] * 1000.0 >= AIRMASS_MIN_MG)
        ]
        if len(window) < 20:
            continue
        retard = window[KNOCK_CH].clip(upper=0.0)
        event = (retard < -0.01).any(axis=1)
        stem = os.path.basename(path)[-12:-4]
        rows.append(
            {
                "log": stem,
                "min": minutes_into_drive(stem),
                "samples": len(window),
                "rpm_max": float(window["Engine Speed (rpm)"].max()),
                "area_deg_s": float(-retard.values.sum() * SAMPLE_DT_S),
                "event_pct": float(event.mean() * 100.0),
                "worst_deg": float(retard.values.min()),
                "knock_rpm_lo": float(window.loc[event, "Engine Speed (rpm)"].min())
                if event.any()
                else np.nan,
                "knock_rpm_hi": float(window.loc[event, "Engine Speed (rpm)"].max())
                if event.any()
                else np.nan,
                "oil_c": float(window["Oil Temp (°C)"].max()),
                "coolant_c": float(window["Coolant Temp (°C)"].max()),
                "iat_c": float(window["IAT (°C)"].mean()),
            }
        )
    table = pd.DataFrame(rows)
    table["full_pull"] = table["rpm_max"] >= FULL_PULL_RPM
    return table


def report(table):
    pd.set_option("display.width", 220)
    print("All in-gear WOT windows:\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:8.2f}"))

    full = table[table["full_pull"]].reset_index(drop=True)
    print(f"\nFull pulls only (peak rpm >= {FULL_PULL_RPM:.0f}), n={len(full)}")
    print("\nRank correlation vs minutes into drive:")
    for col in ("area_deg_s", "event_pct", "worst_deg", "oil_c"):
        print(f"  {col:>10}  {rank_corr(full['min'], full[col]):+.3f}")
    print("\nRank correlation, knock area vs the competing explanations:")
    for col in ("oil_c", "coolant_c", "iat_c"):
        print(f"  {col:>10}  {rank_corr(full['area_deg_s'], full[col]):+.3f}")

    print("\nThirds of the full-pull sequence:")
    thirds = [("first", full.iloc[:3]), ("middle", full.iloc[3:6]), ("last", full.iloc[6:])]
    for label, part in thirds:
        print(
            f"  {label:>6}: area={part['area_deg_s'].mean():5.2f} deg*s  "
            f"events={part['event_pct'].mean():5.1f}%  "
            f"worst={part['worst_deg'].min():5.2f} deg"
        )
    return full


def plot(table, full):
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

    ax = axes[0]
    partial = table[~table["full_pull"]]
    ax.plot(full["min"], full["area_deg_s"], "o-", color="#b2182b", lw=2, ms=8,
            label="knock retard area (full pulls)")
    ax.plot(partial["min"], partial["area_deg_s"], "o", color="#b2182b", ms=8,
            mfc="none", label="partial pull (< 6000 rpm, excluded from trend)")
    ax.set_ylabel("Knock retard area (°CRK · s)", fontweight="bold")
    ax.grid(True, which="both", alpha=0.35)
    ax.minorticks_on()
    rho = rank_corr(full["min"], full["area_deg_s"])
    ax.set_title(
        "R20 knock severity does not fade through the session\n"
        f"rank correlation with time = {rho:+.3f} over {len(full)} full pulls "
        "— no early-drive clustering",
        fontweight="bold",
    )

    twin = ax.twinx()
    twin.plot(table["min"], table["oil_c"], "s--", color="#2166ac", lw=1.5, ms=5,
              label="oil temp")
    twin.set_ylabel("Oil temp (°C)", fontweight="bold", color="#2166ac")
    twin.tick_params(axis="y", colors="#2166ac")
    lines = ax.get_lines() + twin.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], loc="upper right", fontsize=9)

    ax = axes[1]
    for _, row in table.iterrows():
        if np.isnan(row["knock_rpm_lo"]):
            ax.plot(row["min"], np.nan)
            continue
        ax.vlines(row["min"], row["knock_rpm_lo"], row["knock_rpm_hi"],
                  color="#b2182b", lw=6, alpha=0.75)
    clean = table[table["knock_rpm_lo"].isna()]
    ax.plot(clean["min"], np.full(len(clean), 3000.0), "v", color="#4d9221", ms=9,
            label="pull with zero retard")
    ax.set_xlabel("Minutes into the drive", fontweight="bold")
    ax.set_ylabel("Engine speed of knock events (rpm)", fontweight="bold")
    ax.set_ylim(2800, 6600)
    ax.grid(True, which="both", alpha=0.35)
    ax.minorticks_on()
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title("Knock events do not sit at a consistent engine speed", fontweight="bold")

    fig.tight_layout()
    PLOT_DIR.mkdir(exist_ok=True)
    out = PLOT_DIR / "r20_knock_timeline.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    data = load_pulls()
    plot(data, report(data))
