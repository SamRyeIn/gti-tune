"""
Evidence plot for the WOT 3→4 upshift overboost in `simostools-2026_08_10-12_03_17`.

The analysis battery's pull segmentation labels this file "gear 2" and its pull
window stops before the 4th-gear segment, so the session's worst boost, airmass,
and fuel-rail numbers do not appear in `analysis_findings.md`. This script plots
that segment directly.

The event: a full-throttle 3→4 upshift at 5544 rpm drops the engine to 3906 rpm —
straight into the flat top of the slot-4 target curve — and boost overshoots to
the `PUT` channel's 300.6 kPa rail while the high-pressure fuel pump saturates.

Usage:
    python3 plot_upshift_overboost.py
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LOG_DIR = Path(__file__).resolve().parent
PLOT_DIR = LOG_DIR / "plots"
LOG = LOG_DIR / "simostools-2026_08_10-12_03_17.csv"

#: The `PUT` channel pins at this exact value for 12 consecutive samples while
#: every neighbouring value is distinct — a hard ceiling, not a plateau.
PUT_RAIL_KPA = 300.6009
AMBIENT_HPA = 1016.0
HPA_PER_PSI = 68.95

CHANNELS = {
    "t": "Time", "rpm": "Engine Speed (rpm)", "gear": "Gear (gear)",
    "pedal": "Pedal Pos (%)", "put": "PUT (kpa)", "put_sp": "PUT SP (kpa)",
    "map": "MAP (kpa)", "map_sp": "MAP SP (kpa)",
    "wg_base": "WG Pos Base (%)", "wg_i": "WG I Value (%)",
    "wg_pd": "WG P-D Value (%)", "wg_fin": "WG Pos Final (%)",
    "hpfp": "HPFP Eff Vol (%)", "lpfp": "LPFP Duty (%)",
    "fp_di": "FP DI (kpa)", "fp_di_sp": "FP DI SP (kpa)",
    "lam": "Lambda (l)", "lam_sp": "Lambda SP (l)",
    "air": "Airmass (g/stk)", "air_sp": "Airmass SP (g/stk)",
}


def load(path):
    """Row-aligned parse — a row is kept only if every channel parses."""
    out = {k: [] for k in CHANNELS}
    for row in csv.DictReader(open(path)):
        try:
            vals = {k: float(row[c]) for k, c in CHANNELS.items()}
        except (ValueError, KeyError, TypeError):
            continue
        for k, v in vals.items():
            out[k].append(v)
    return {k: np.asarray(v) for k, v in out.items()}


def main():
    d = load(LOG)
    # The `Time` channel is quantised to 0.1 s (diffs are only 0.0/0.2/0.3/0.4),
    # so plotting against it stair-steps and hides sub-sample structure. The
    # underlying rate is uniform, so reconstruct time from the sample index.
    raw = d["t"] - d["t"][0]
    dt = raw[-1] / (len(raw) - 1)
    t = np.arange(len(raw)) * dt
    # The upshift plus the 4th-gear pull that follows it.
    seg = (t >= 7.6) & (t <= 9.5)
    ts = t[seg]

    fig, axes = plt.subplots(3, 1, figsize=(11, 11), sharex=True)

    ax = axes[0]
    ax.plot(ts, d["put"][seg], lw=2.0, label="PUT")
    ax.plot(ts, d["put_sp"][seg], lw=1.6, ls="--", label="PUT SP (slot 4)")
    ax.plot(ts, d["map"][seg], lw=1.4, alpha=0.8, label="MAP")
    ax.plot(ts, d["map_sp"][seg], lw=1.2, ls=":", alpha=0.8, label="MAP SP")
    ax.axhline(PUT_RAIL_KPA, color="crimson", lw=1.2, ls="-.",
               label=f"PUT channel rail ({PUT_RAIL_KPA:.1f} kPa)")
    ax.set_ylabel("Pressure (kPa absolute)", fontweight="bold")
    ax.set_title("WOT 3→4 upshift into the slot-4 shelf — boost overshoots to the sensor rail")
    ax.legend(loc="lower right", fontsize=8, ncol=2)

    ax = axes[1]
    ax.plot(ts, d["wg_base"][seg], lw=1.6, label="WG Pos Base (feedforward)")
    ax.plot(ts, d["wg_i"][seg], lw=1.6, label="WG I Value")
    ax.plot(ts, d["wg_pd"][seg], lw=1.6, label="WG P-D Value")
    ax.plot(ts, d["wg_fin"][seg], lw=2.2, color="k", label="WG Pos Final (commanded)")
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_ylabel("Wastegate position (%, higher = more closed)", fontweight="bold")
    ax.legend(loc="upper right", fontsize=8, ncol=2)

    ax = axes[2]
    ax.plot(ts, d["hpfp"][seg], lw=2.0, label="HPFP effective volume (%)")
    ax.plot(ts, d["lpfp"][seg], lw=1.6, label="LPFP duty (%)")
    sag = (d["fp_di"][seg] - d["fp_di_sp"][seg]) / 100.0
    ax.plot(ts, sag, lw=2.0, color="crimson", label="DI rail error (bar)")
    ax.axhline(100, color="gray", lw=0.8, ls=":")
    ax.axhline(-25, color="crimson", lw=1.0, ls="--", label="battery High sag line (-25 bar)")
    ax2 = ax.twinx()
    ax2.plot(ts, d["lam"][seg], lw=1.4, color="seagreen", label="Lambda")
    ax2.plot(ts, d["lam_sp"][seg], lw=1.2, ls="--", color="seagreen", alpha=0.7,
             label="Lambda SP")
    ax2.set_ylabel("Lambda", fontweight="bold", color="seagreen")
    ax2.set_ylim(0.6, 1.3)
    ax.set_ylabel("Pump / rail", fontweight="bold")
    ax.set_xlabel("Time into log (s)", fontweight="bold")
    ax.legend(loc="lower left", fontsize=8)
    ax2.legend(loc="lower right", fontsize=8)

    for a in axes:
        a.grid(True, which="major")
        a.minorticks_on()
        a.grid(True, which="minor", alpha=0.25)

    fig.tight_layout()
    out = PLOT_DIR / "r14_upshift_overboost.png"
    fig.savefig(out, dpi=140)
    print(f"wrote {out}")

    m = seg & (d["gear"] == 4) & (d["pedal"] >= 90)
    print(f"4th-gear WOT segment: n={m.sum()}, "
          f"peak PUT {d['put'][m].max():.1f} kPa "
          f"({(d['put'][m].max() * 10 - AMBIENT_HPA) / HPA_PER_PSI:.1f} psi gauge), "
          f"peak PUT error {(d['put'][m] - d['put_sp'][m]).max():+.1f} kPa, "
          f"peak MAP error {(d['map'][m] - d['map_sp'][m]).max():+.1f} kPa, "
          f"samples at the PUT rail = {(d['put'][m] >= PUT_RAIL_KPA).sum()}, "
          f"peak airmass {d['air'][m].max() * 1000:.0f} mg/stk, "
          f"worst rail sag {((d['fp_di'][m] - d['fp_di_sp'][m]) / 100).min():+.1f} bar")


if __name__ == "__main__":
    main()
