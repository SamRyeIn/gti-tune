"""
Compare 3rd-gear WOT acceleration between two SimosTools logs (map slot 1 vs map slot 2).

Usage:
    python3 compare_3rd_gear_accel.py

Finds the contiguous 3rd-gear, high-pedal (WOT) window in each log, and reports
time-to-cover the common overlapping speed range using Vehicle Speed (km/h) vs Time.
"""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LOG_DIR = Path(__file__).parent
PLOT_DIR = LOG_DIR / "plots"
LOG_SLOT1 = LOG_DIR / "simostools-2026_07_12-22_31_27.csv"  # map slot 1
LOG_SLOT2 = LOG_DIR / "simostools-2026_07_12-22_41_31.csv"  # map slot 2

PEDAL_WOT_THRESHOLD = 90.0  # %
GEAR_TARGET = 3.0


def load_rows(path):
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def find_3rd_gear_wot_window(rows):
    """Return list of (time, speed) rows for the longest contiguous 3rd-gear WOT run."""
    runs = []
    current = []
    for row in rows:
        try:
            gear = float(row["Gear (gear)"])
            pedal = float(row["Pedal Pos (%)"])
            t = float(row["Time"])
            speed = float(row["Vehicle Speed (km/h)"])
        except (ValueError, KeyError):
            if current:
                runs.append(current)
                current = []
            continue

        if gear == GEAR_TARGET and pedal >= PEDAL_WOT_THRESHOLD:
            current.append((t, speed))
        else:
            if current:
                runs.append(current)
                current = []
    if current:
        runs.append(current)

    if not runs:
        return []
    return max(runs, key=len)


def summarize(label, window):
    if len(window) < 2:
        print(f"{label}: no valid 3rd-gear WOT window found")
        return None
    t0, s0 = window[0]
    t1, s1 = window[-1]
    duration = t1 - t0
    speed_gain = s1 - s0
    print(f"{label}:")
    print(f"  samples:        {len(window)}")
    print(f"  time window:    {t0:.2f}s -> {t1:.2f}s  (duration {duration:.2f}s)")
    print(f"  speed window:   {s0:.1f} -> {s1:.1f} km/h  (delta {speed_gain:.1f} km/h)")
    print(f"  avg accel:      {speed_gain / duration:.2f} km/h per s")
    return {"t0": t0, "t1": t1, "s0": s0, "s1": s1, "window": window}


def time_to_reach(window, target_speed):
    """Interpolate time at which window crosses target_speed (assumes monotonic increase)."""
    for (t_a, s_a), (t_b, s_b) in zip(window, window[1:]):
        if s_a <= target_speed <= s_b:
            if s_b == s_a:
                return t_a
            frac = (target_speed - s_a) / (s_b - s_a)
            return t_a + frac * (t_b - t_a)
    return None


def plot_comparison(summary1, summary2):
    PLOT_DIR.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(9, 6))

    for summary, label, color in (
        (summary1, "Map slot 1 (22:31:27)", "tab:blue"),
        (summary2, "Map slot 2 (22:41:31)", "tab:orange"),
    ):
        t0 = summary["t0"]
        t_rel = [t - t0 for t, _ in summary["window"]]
        speed = [s for _, s in summary["window"]]
        ax.plot(t_rel, speed, label=label, color=color, linewidth=2)

    ax.set_xlabel("Time since pull start (s)", fontweight="bold")
    ax.set_ylabel("Vehicle Speed (km/h)", fontweight="bold")
    ax.set_title("3rd Gear WOT Pull Comparison: Map Slot 1 vs Map Slot 2")
    ax.grid(True, which="major")
    ax.grid(True, which="minor", alpha=0.3)
    ax.minorticks_on()
    ax.legend(loc="lower right")

    fig.tight_layout()
    out_path = PLOT_DIR / "analysis_3rd_gear_accel_comparison.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\nPlot saved to: {out_path}")


def main():
    rows1 = load_rows(LOG_SLOT1)
    rows2 = load_rows(LOG_SLOT2)

    window1 = find_3rd_gear_wot_window(rows1)
    window2 = find_3rd_gear_wot_window(rows2)

    print(f"Map slot 1: {LOG_SLOT1.name}")
    summary1 = summarize("  Map slot 1", window1)
    print()
    print(f"Map slot 2: {LOG_SLOT2.name}")
    summary2 = summarize("  Map slot 2", window2)

    if not summary1 or not summary2:
        print("\nCannot compare -- missing a valid window in one or both logs.")
        return

    plot_comparison(summary1, summary2)

    lo = max(summary1["s0"], summary2["s0"])
    hi = min(summary1["s1"], summary2["s1"])

    print(f"\nCommon overlapping speed range: {lo:.1f} -> {hi:.1f} km/h")
    if lo >= hi:
        print("No overlapping speed range to compare directly.")
        return

    t1_lo = time_to_reach(summary1["window"], lo)
    t1_hi = time_to_reach(summary1["window"], hi)
    t2_lo = time_to_reach(summary2["window"], lo)
    t2_hi = time_to_reach(summary2["window"], hi)

    dur1 = t1_hi - t1_lo
    dur2 = t2_hi - t2_lo

    print(f"\nTime to cover {lo:.1f}-{hi:.1f} km/h:")
    print(f"  Map slot 1: {dur1:.3f} s")
    print(f"  Map slot 2: {dur2:.3f} s")
    diff = dur2 - dur1
    faster = "Map slot 1" if dur1 < dur2 else "Map slot 2"
    print(f"  Delta:      {diff:+.3f} s (slot2 - slot1) -> {faster} is faster by {abs(diff):.3f} s")


if __name__ == "__main__":
    main()
