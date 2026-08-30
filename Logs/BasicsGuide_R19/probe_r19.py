"""Follow-up probes for the R19 review: tip-in overshoot, knock simultaneity,
base-timing identity at matched operating points, and the lean lambda excursion.

Usage:
    ../../Code/.venv/bin/python probe_r19.py
"""
from __future__ import annotations

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from analyze_r19_validation import (
    HERE, PLOT_DIR, R18_DIR, R18_TAGS, R19_TAGS, SAMPLE_S, KNOCK_KEYS,
    knock_events, load_tagged, loaded_mask, contiguous_runs, pull_gear, style_axis,
)


def tip_in(logs, name):
    """Peak PUT overshoot in the first second of each loaded run below 3500 rpm."""
    print(f"\n{name} tip-in overshoot (first loaded run, rpm < 3500):")
    peaks = []
    for tag, data in logs:
        runs = contiguous_runs(loaded_mask(data))
        runs = [r for r in runs if r.size > 20]
        if not runs:
            continue
        run = max(runs, key=len)
        early = run[data["rpm"][run] < 3500.0]
        if early.size < 3:
            continue
        err = data["put"][early] - data["put_sp"][early]
        peaks.append(float(err.max()))
        print(f"  {tag}: peak +{err.max():5.1f} kPa @ {data['rpm'][early][err.argmax()]:.0f} rpm, "
              f"mean {err.mean():+5.1f}, n={early.size}")
    if peaks:
        print(f"  peak mean +{np.mean(peaks):.1f} kPa, worst +{np.max(peaks):.1f} kPa")


def simultaneity(logs, name):
    """How close in time are the co-cylinder retards flagged as multi-cylinder?"""
    print(f"\n{name} per-cylinder onset spacing inside multi-cylinder clusters:")
    for tag, data in logs:
        loaded = loaded_mask(data)
        onsets = []
        for key in KNOCK_KEYS:
            for run in contiguous_runs(loaded & (data[key] <= -1.0), 10):
                onsets.append((int(run[0]), int(key[-1]), float(data[key][run].min())))
        onsets.sort()
        for i in range(len(onsets) - 1):
            gap_rows = onsets[i + 1][0] - onsets[i][0]
            if gap_rows <= 25:
                print(f"  {tag}: cyl {onsets[i][1]} @row {onsets[i][0]} "
                      f"({onsets[i][2]:+.2f}) then cyl {onsets[i+1][1]} "
                      f"+{gap_rows * SAMPLE_S:.2f}s ({onsets[i+1][2]:+.2f}), "
                      f"rpm {data['rpm'][onsets[i][0]]:.0f}->{data['rpm'][onsets[i+1][0]]:.0f}")


def timing_identity(r18, r19):
    """Compare Ign Table on a matched rpm x airmass grid; R19 must be identical."""
    print("\nIgn Table on matched rpm x airmass cells (gear 3 loaded WOT):")
    print("  rpm band   airmass band   n18   n19   table18  table19   delta")
    rpm_edges = [(3500, 4000), (4000, 4500), (4500, 5000),
                 (5000, 5500), (5500, 6000), (6000, 6500)]
    am_edges = [(1.2, 1.4), (1.4, 1.5), (1.5, 1.7)]
    worst = 0.0
    for lo, hi in rpm_edges:
        for alo, ahi in am_edges:
            vals = []
            for logs in (r18, r19):
                pool = []
                for _, data in logs:
                    m = (loaded_mask(data, 3) & (data["rpm"] >= lo) & (data["rpm"] < hi)
                         & (data["airmass"] >= alo) & (data["airmass"] < ahi))
                    if m.any():
                        pool.append(data["ign_table"][m])
                vals.append(np.concatenate(pool) if pool else np.empty(0))
            if vals[0].size < 5 or vals[1].size < 5:
                continue
            delta = float(vals[1].mean() - vals[0].mean())
            worst = max(worst, abs(delta))
            print(f"  {lo}-{hi}  {alo:.1f}-{ahi:.1f} g/stk  {vals[0].size:4d}  {vals[1].size:4d}  "
                  f"{vals[0].mean():+7.2f}  {vals[1].mean():+7.2f}  {delta:+6.2f}")
    print(f"  worst matched-cell Ign Table delta: {worst:+.2f} deg")


def lambda_probe(logs, name):
    """Settled loaded-WOT lambda error, and the worst lean excursion in context."""
    print(f"\n{name} settled loaded-WOT lambda (torque >= 250 Nm):")
    for tag, data in logs:
        m = loaded_mask(data) & (data["torque"] >= 250.0)
        if m.sum() < 10:
            continue
        err = data["lambda"][m] - data["lambda_sp"][m]
        i = int(np.argmax(err))
        rows = np.flatnonzero(m)
        print(f"  {tag}: mean {err.mean():+.4f}  worst {err.max():+.4f} @ "
              f"{data['rpm'][rows[i]]:.0f} rpm, lam {data['lambda'][rows[i]]:.3f} vs SP "
              f"{data['lambda_sp'][rows[i]]:.3f}, gear {data['gear'][rows[i]]:.0f}, "
              f"n_lean>0.05 = {(err > 0.05).sum()}")


def plot_tip_in(r18, r19) -> None:
    """Tip-in PUT error vs rpm below 3500, with the low-rpm knock onsets marked."""
    PLOT_DIR.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharey=True)
    for ax, (name, logs, colour) in zip(axes, (("R18 cool", r18, "tab:blue"),
                                               ("R19", r19, "tab:red"))):
        for tag, data in logs:
            runs = [r for r in contiguous_runs(loaded_mask(data)) if r.size > 20]
            if not runs:
                continue
            run = max(runs, key=len)
            early = run[data["rpm"][run] < 3500.0]
            if early.size < 3:
                continue
            ax.plot(data["rpm"][early], data["put"][early] - data["put_sp"][early],
                    color=colour, alpha=0.7, linewidth=1.4)
        onsets = [e for e in knock_events(logs) if e["onset_rpm"] < 3500.0]
        if onsets:
            ax.scatter([e["onset_rpm"] for e in onsets], [0.0] * len(onsets),
                       marker="v", s=90, color="black", zorder=5,
                       label=f"knock onset (n={len(onsets)})")
            ax.legend(loc="lower right")
        ax.axhline(0.0, color="0.4", linewidth=1.0)
        ax.set_title(f"{name} tip-in")
        ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
        style_axis(ax)
    axes[0].set_ylabel("PUT − PUT SP (kPa)", fontweight="bold")
    fig.suptitle("Tip-in boost overshoot and the new low-rpm knock cluster",
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "r19_tip_in.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    r18 = load_tagged(R18_DIR, R18_TAGS)
    r19 = load_tagged(HERE, R19_TAGS)
    tip_in(r18, "R18 cool")
    tip_in(r19, "R19")
    simultaneity(r18, "R18 cool")
    simultaneity(r19, "R19")
    timing_identity(r18, r19)
    lambda_probe(r18, "R18 cool")
    lambda_probe(r19, "R19")
    plot_tip_in(r18, r19)
    print(f"\nwrote {PLOT_DIR / 'r19_tip_in.png'}")


if __name__ == "__main__":
    main()
