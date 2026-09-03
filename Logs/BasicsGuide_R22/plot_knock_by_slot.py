"""Most-retarded-cylinder traces, one panel per slot, on shared axes.

The battery's `plots/analysis_knock.png` overlays all 21 R22 pulls in one axes,
which shows that knock happened but not *which map* it happened on -- and the map
is the whole question. This splits the same trace by attributed slot and adds the
plain-92 baseline, on shared limits so the panels can be read against each other:

    top row     base timing, fuel varies   -- R19 plain 92 | R22 slot 3 dosed
    bottom row  dosed, timing varies       -- R22 slot 4   | R22 slot 5

So the top row prices the octane dose (same calibration, different fuel) and the
bottom row prices the two octane offsets against the control directly above them.

R19 predates the dose (R20 introduced it) and runs the calibration
`slot_attribution` verifies is byte-identical to R22 slot 3's, which is what makes
the top row a fuel comparison rather than a calibration one.

Run:  Code/.venv/bin/python Logs/BasicsGuide_R22/plot_knock_by_slot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
LOGS = HERE.parent
sys.path.insert(0, str(LOGS / "BasicsGuide_R19"))
sys.path.insert(0, str(HERE))

from analyze_r19_validation import (  # noqa: E402
    R19_TAGS, SAMPLE_S, load, load_tagged, loaded_mask,
)
from slot_attribution import attribute  # noqa: E402

KNOCK_KEYS = ("knock_1", "knock_2", "knock_3", "knock_4")
WATCH_DEG, HIGH_DEG = -1.5, -3.0

#: Shared limits. Fixed rather than auto-scaled: panels drawn on different axes
#: would invite exactly the comparison this figure exists to make, while quietly
#: rescaling the thing being compared.
XLIM = (2900, 6700)
YLIM = (-5.0, 0.35)


def series(data, window):
    """(rpm, most-retarded cylinder) over loaded WOT, gaps left as NaN."""
    m = loaded_mask(data)
    if window is not None:
        rows = np.arange(data["rpm"].size)
        m = m & (rows >= window[0]) & (rows <= window[1])
    worst = np.nanmin(np.vstack([data[k] for k in KNOCK_KEYS]), axis=0)
    rpm = np.where(m, data["rpm"], np.nan)
    return rpm[m], worst[m], float(m.sum()) * SAMPLE_S


def collect():
    """The four panels, in draw order."""
    pulls = attribute()
    r22 = {p.file: load(HERE / f"{p.file}.csv") for p in pulls}

    plain = [(f"{tag}", d, None)
             for tag, d in load_tagged(LOGS / "BasicsGuide_R19", R19_TAGS)]
    panels = [
        ("R19 — plain 92, base timing\n(slot 4 then; the same map as R22 slot 3)",
         plain, "tab:green"),
    ]
    for slot, title, colour in (
        (3, "R22 slot 3 — DOSED, base timing\n(the control)", "tab:blue"),
        (4, "R22 slot 4 — DOSED, R20 uncut offset\n(reduced-boost map, ~24.4 psi)",
         "tab:orange"),
        (5, "R22 slot 5 — DOSED, R21 cut offset\n(reduced-timing map, ~26.0 psi)",
         "tab:red"),
    ):
        entries = [(f"p{p.index}", r22[p.file], (p.start_row - 50, p.end_row + 50))
                   for p in pulls if p.slot == slot]
        panels.append((title, entries, colour))
    return panels


def main() -> int:
    panels = collect()
    fig, axes = plt.subplots(2, 2, figsize=(15.0, 10.0), sharex=True, sharey=True,
                             gridspec_kw={"hspace": 0.30, "wspace": 0.08})

    for ax, (title, entries, colour) in zip(axes.ravel(), panels):
        exposure, worst_all = 0.0, 0.0
        for _name, data, window in entries:
            rpm, worst, secs = series(data, window)
            exposure += secs
            if worst.size:
                worst_all = min(worst_all, float(np.min(worst)))
            order = np.argsort(rpm)
            ax.plot(rpm[order], worst[order], color=colour, linewidth=1.0,
                    alpha=0.55, solid_joinstyle="round")
        # Retard integral over all four cylinders, matching the review's metric
        # (the traces show only the worst cylinder; the number sums all four).
        tot = 0.0
        for _name, data, window in entries:
            m = loaded_mask(data)
            if window is not None:
                rows = np.arange(data["rpm"].size)
                m = m & (rows >= window[0]) & (rows <= window[1])
            tot += float(np.sum([np.clip(-data[k][m], 0.0, None)
                                 for k in KNOCK_KEYS])) * SAMPLE_S
        rate = 60.0 * tot / exposure if exposure else float("nan")

        ax.axhline(0.0, color="0.2", linewidth=0.9)
        ax.axhline(WATCH_DEG, color="darkorange", linestyle="--", linewidth=1.1)
        ax.axhline(HIGH_DEG, color="firebrick", linestyle="--", linewidth=1.1)
        ax.set_xlim(*XLIM); ax.set_ylim(*YLIM)
        ax.set_title(title, fontsize=10.5, fontweight="bold")
        ax.grid(True, which="major", alpha=0.35)
        ax.grid(True, which="minor", alpha=0.15)
        ax.minorticks_on()
        ax.text(0.985, 0.045,
                f"{len(entries)} pulls · {exposure:.1f} s loaded WOT\n"
                f"worst {worst_all:+.2f}° · {rate:.1f} deg-s/min",
                transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                          edgecolor="0.7", alpha=0.9))

    for ax in axes[1]:
        ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    for ax in axes[:, 0]:
        ax.set_ylabel("Knock retard, most-retarded cylinder (deg)",
                      fontweight="bold")
    axes[0, 0].plot([], [], color="darkorange", linestyle="--", label="−1.5° watch")
    axes[0, 0].plot([], [], color="firebrick", linestyle="--", label="−3.0° high")
    axes[0, 0].legend(loc="lower left", fontsize=9)

    fig.suptitle("Knock retard by map and by fuel — shared axes\n"
                 "top row: same calibration, plain 92 vs dosed   ·   "
                 "bottom row: the two dosed octane slots",
                 fontsize=13, fontweight="bold")
    fig.subplots_adjust(top=0.87)
    out = HERE / "plots" / "r22_knock_by_slot.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
