"""Score R22's three slots — control, reduced-boost, reduced-timing — against each other.

R22 runs one experiment: R20's 4500-5000 rpm knock tracked *cylinder filling*
rather than offset size, so R22 puts the reduced-boost map (slot 4, R20's uncut
timing on ~1.6 psi less boost) and the reduced-timing map (slot 5, R21's cut
timing on the full boost curve) against one control (slot 3) in one session on
one tank. This scores them.

Two things this script must get right:

* **Slot attribution.** No map-slot channel is logged, so each pull's slot comes
  from `slot_attribution` — the boost-curve fit plus the reconstructed ignition
  offset, both read off the flashed bin. The attribution is imported rather than
  restated so the two scripts cannot drift apart.
* **Event definitions.** Every rate here uses R19's `knock_events` and
  `loaded_mask` unchanged (pedal >= 90%, rpm >= 3000, airmass >= 0.9 g/stk,
  TPS >= 60%, all gears), which is what R20 was scored on. Redefining them would
  make the cross-revision comparison meaningless.

One log (`06_55_01`) holds two pulls on *different slots*, so samples are
attributed to the nearest pull window rather than by file.

Run:  Code/.venv/bin/python Logs/BasicsGuide_R22/analyze_r22_slots.py
"""

from __future__ import annotations

import csv
import sys
from math import exp, factorial
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "BasicsGuide_R19"))
sys.path.insert(0, str(HERE))

from analyze_r19_validation import (  # noqa: E402
    CHANNELS, KNOCK_KEYS, SAMPLE_S, knock_events, load, loaded_mask,
)
from slot_attribution import attribute  # noqa: E402

#: Bands, extended below R19's 3500 floor because R20 named 3000-3500 as a
#: pre-existing knock zone that R22 does not address but must not hide.
BANDS = ((3000, 3500), (3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6600))

#: The band the experiment is actually about.
FOCUS_BAND = (4500, 5000)

#: A loaded sample more than this many rows from any attributed pull window is
#: dropped: it belongs to no slot, and guessing which slot it ran is exactly the
#: failure mode R22's REV_LOG warns about.
MAX_ROWS_FROM_PULL = 200

SLOT_LABEL = {
    3: "slot 3 - control (aggressive boost, base timing)",
    4: "slot 4 - reduced-BOOST map (mid boost, R20 uncut timing)",
    5: "slot 5 - reduced-TIMING map (aggressive boost, R21 cut timing)",
}


def poisson_upper_p(observed: int, expected: float) -> float:
    """P(X >= observed) for a Poisson with the given mean."""
    if expected <= 0.0:
        return 1.0 if observed == 0 else 0.0
    return 1.0 - sum(exp(-expected) * expected ** k / factorial(k)
                     for k in range(observed))


def poisson_rate_ci(n: int, t: float, conf: float = 0.95) -> tuple[float, float]:
    """Exact (Garwood) Poisson rate CI in events per minute."""
    alpha = 1.0 - conf

    def cdf(k: int, mu: float) -> float:
        return sum(exp(-mu) * mu ** j / factorial(j) for j in range(k + 1))

    def solve(f, target: float) -> float:
        lo, hi = 0.0, 500.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if f(mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    low = 0.0 if n == 0 else solve(lambda mu: cdf(n - 1, mu), 1.0 - alpha / 2.0)
    high = solve(lambda mu: cdf(n, mu), alpha / 2.0)
    return 60.0 * low / t, 60.0 * high / t


def prior_sessions() -> list[tuple[str, str, int, float]]:
    """R19's and R20's own logs, rescored here with the definitions used above.

    Recomputed from the raw CSVs rather than quoted from their reviews, so the
    cross-revision row is produced by exactly the code that produced R22's.
    """
    sys.path.insert(0, str(HERE.parent / "BasicsGuide_R20"))
    from analyze_r19_validation import R19_TAGS, load_tagged  # noqa: E402
    from analyze_r20_validation import load_r20               # noqa: E402

    out = []
    for label, calib, logs in (
        ("R19 slot 4", "aggressive boost, base timing (= R22 slot 3)",
         load_tagged(HERE.parent / "BasicsGuide_R19", R19_TAGS)),
        ("R20 slot 5", "aggressive boost, R20 uncut timing", load_r20()),
    ):
        exposure = sum(
            float((loaded_mask(d) & (d["rpm"] >= FOCUS_BAND[0])
                   & (d["rpm"] < FOCUS_BAND[1])).sum()) * SAMPLE_S
            for _t, d in logs
        )
        n = sum(1 for e in knock_events(logs)
                if FOCUS_BAND[0] <= e["worst_rpm"] < FOCUS_BAND[1])
        out.append((label, calib, n, exposure))
    return out


def make_plot(band_detail, rows_x) -> None:
    """Two panels: the band sweep by slot, and the cross-revision focus band.

    Both carry exact Poisson intervals, because every rate here rests on 0-6
    events and a bare bar chart of those point estimates would imply a
    precision this session does not have.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots = HERE / "plots"
    plots.mkdir(exist_ok=True)
    fig, (ax0, axI, ax1) = plt.subplots(3, 1, figsize=(11.5, 13.5),
                                        gridspec_kw={"hspace": 0.42})

    colours = {3: "tab:blue", 4: "tab:orange", 5: "tab:red"}
    labels = {3: "slot 3 — control", 4: "slot 4 — reduced boost",
              5: "slot 5 — reduced timing"}
    xs = np.arange(len(BANDS))
    for k, slot in enumerate((3, 4, 5)):
        rates, los, his = [], [], []
        for band in BANDS:
            n, t = band_detail[band][slot]
            r = 60.0 * n / t if t else np.nan
            lo, hi = poisson_rate_ci(n, t) if t else (np.nan, np.nan)
            rates.append(r); los.append(r - lo); his.append(hi - r)
        off = (k - 1) * 0.26
        ax0.errorbar(xs + off, rates, yerr=[los, his], fmt="o", capsize=4,
                     color=colours[slot], label=labels[slot], markersize=6,
                     linewidth=1.6)
    ax0.set_xticks(xs)
    ax0.set_xticklabels([f"{a}-{b}" for a, b in BANDS])
    ax0.set_xlabel("Engine speed band (rpm)", fontweight="bold")
    ax0.set_ylabel("Knock events per loaded WOT minute", fontweight="bold")
    ax0.set_title("R22 three-slot knock rate by band, with exact 95% Poisson intervals\n"
                  "every interval spans every other slot — this session separates nothing")
    ax0.legend(loc="upper right", fontsize=9)
    ax0.grid(True, which="major", alpha=0.35)
    ax0.grid(True, which="minor", alpha=0.15)
    ax0.minorticks_on()

    # -- the same question on the continuous statistic ---------------------- #
    files = files_for_metric()
    pulls = attribute()
    rng = np.random.default_rng(0)

    def rate(vals):
        return (60.0 * sum(v[0] for v in vals) / sum(v[1] for v in vals)
                if vals else np.nan)

    for k, slot in enumerate((3, 4, 5)):
        pts, los, his = [], [], []
        for band in BANDS:
            vals = [v for v in (_retard_integral(files[p.file], p, *band)
                                for p in pulls if p.slot == slot) if v]
            r = rate(vals)
            boot = np.array([rate([vals[i] for i in
                                   rng.integers(0, len(vals), len(vals))])
                             for _ in range(4000)])
            pts.append(r)
            los.append(max(0.0, r - np.percentile(boot, 2.5)))
            his.append(np.percentile(boot, 97.5) - r)
        off = (k - 1) * 0.26
        axI.errorbar(np.arange(len(BANDS)) + off, pts, yerr=[los, his], fmt="o",
                     capsize=4, color=colours[slot], label=labels[slot],
                     markersize=6, linewidth=1.6)
    axI.set_xticks(np.arange(len(BANDS)))
    axI.set_xticklabels([f"{a}-{b}" for a, b in BANDS])
    axI.set_xlabel("Engine speed band (rpm)", fontweight="bold")
    axI.set_ylabel("Retard integral (deg-s per loaded WOT min)", fontweight="bold")
    axI.set_title("The same question on the continuous statistic, all 21 pulls\n"
                  "the two octane slots track each other everywhere")
    axI.legend(loc="upper right", fontsize=9)
    axI.grid(True, which="major", alpha=0.35)
    axI.grid(True, which="minor", alpha=0.15)
    axI.minorticks_on()

    names = [r[0] for r in rows_x]
    rates = [60.0 * r[2] / r[3] for r in rows_x]
    cis = [poisson_rate_ci(r[2], r[3]) for r in rows_x]
    cols = ["0.45", "tab:purple", "tab:blue", "tab:orange", "tab:red"]
    y = np.arange(len(names))
    ax1.errorbar(rates, y, xerr=[[r - c[0] for r, c in zip(rates, cis)],
                                 [c[1] - r for r, c in zip(rates, cis)]],
                 fmt="o", capsize=4, markersize=7, linewidth=1.8,
                 ecolor="0.3", linestyle="none")
    for i, c in enumerate(cols):
        ax1.plot(rates[i], y[i], "o", color=c, markersize=9, zorder=4)
    ax1.set_yticks(y); ax1.set_yticklabels(names)
    ax1.invert_yaxis()
    ax1.set_xlabel("Knock events per loaded WOT minute, 4500–5000 rpm", fontweight="bold")
    ax1.set_title("The band R20 indicted, across sessions\n"
                  "R22's control runs the same calibration as R19's — and lands on R20's rate")
    ax1.grid(True, which="major", alpha=0.35)
    ax1.grid(True, which="minor", alpha=0.15)
    ax1.minorticks_on()

    fig.savefig(plots / "r22_slot_knock_rates.png", dpi=150, bbox_inches="tight")
    print(f"\nwrote {plots / 'r22_slot_knock_rates.png'}")


#: Bootstrap resamples for the pull-level interval. Pull-level (not sample-level)
#: because samples within one pull are strongly correlated, and resampling
#: samples would report an interval far narrower than the data supports.
BOOTSTRAP_N = 20000


def files_for_metric() -> dict:
    return {p.file: load(HERE / f"{p.file}.csv") for p in attribute()}


def _retard_integral(data, p, lo: float, hi: float):
    """Total per-cylinder retard in a band as (degree-seconds, exposure seconds).

    A continuous alternative to counting events. Every rate in the event tables
    above rests on 0-6 discrete events, which throws away the depth and duration
    of each cut; integrating the retard uses every sample instead, so it is the
    more sensitive statistic available from this session.
    """
    rows = np.arange(data["rpm"].size)
    m = (loaded_mask(data)
         & (rows >= p.start_row - 50) & (rows <= p.end_row + 50)
         & (data["rpm"] >= lo) & (data["rpm"] < hi))
    if not m.sum():
        return None
    total = float(np.sum([np.clip(-data[k][m], 0.0, None) for k in KNOCK_KEYS]))
    return total * SAMPLE_S, float(m.sum()) * SAMPLE_S


def slot_contrasts(files) -> None:
    """The three pairwise slot contrasts, over every attributed pull.

    No pull is excluded. Oil temperature climbs 81 -> 111 C over the first nine
    pulls and plateaus thereafter, and the slots are not balanced across that
    warm-up, so it is reported alongside the result as a caveat -- but selecting
    on it would be choosing a subset after seeing the outcome, and the interval
    would then understate how little this session actually pins down.
    """
    rng = np.random.default_rng(0)
    pulls = attribute()

    def rate(vals):
        return (60.0 * sum(v[0] for v in vals) / sum(v[1] for v in vals)
                if vals else float("nan"))

    def contrast(a, b):
        diffs = np.array([
            rate([b[i] for i in rng.integers(0, len(b), len(b))])
            - rate([a[i] for i in rng.integers(0, len(a), len(a))])
            for _ in range(BOOTSTRAP_N)
        ])
        return (rate(b) - rate(a), np.percentile(diffs, 2.5),
                np.percentile(diffs, 97.5), float(np.mean(diffs <= 0)))

    print("\n## Retard integral by slot — every attributed pull\n")
    print("Degree-seconds of per-cylinder retard per loaded WOT minute, with "
          "pull-level bootstrap 95% intervals on each contrast. Note there are "
          "24 tests in this table; no single P below survives a correction for "
          "that, so read the pattern across bands, not any one cell.\n")
    print("| Band (rpm) | s3 control | s4 red-boost | s5 red-timing "
          "| s4 − s3 | s5 − s3 | s5 − s4 |")
    print("|------------|------------|--------------|---------------"
          "|---------|---------|---------|")
    for lo, hi in BANDS + ((3000, 6600),):
        slots = {
            slot: [v for v in (_retard_integral(files[p.file], p, lo, hi)
                               for p in pulls if p.slot == slot) if v]
            for slot in (3, 4, 5)
        }
        if not all(slots.values()):
            continue
        cells = []
        for a, b in ((3, 4), (3, 5), (4, 5)):
            d, lo_ci, hi_ci, pv = contrast(slots[a], slots[b])
            cells.append(f"{d:+.1f} [{lo_ci:+.1f}, {hi_ci:+.1f}] P={pv:.3f}")
        print(f"| {lo}-{hi} | {rate(slots[3]):.2f} | {rate(slots[4]):.2f} "
              f"| {rate(slots[5]):.2f} | " + " | ".join(cells) + " |")

    power_summary()

    print("\n## Oil temperature at each pull start (reported, not selected on)\n")
    line = []
    for p in pulls:
        rows = list(csv.DictReader(
            open(HERE / f"{p.file}.csv", encoding="utf-8-sig")))
        line.append(f"p{p.index}(s{p.slot}) {float(rows[p.start_row]['Oil Temp (°C)']):.0f}C")
    print("  " + ", ".join(line))


def power_summary() -> None:
    """Per-pull peak `Calc HP` and peak airmass by slot.

    `Calc HP` is SimosTools' acceleration-derived, gear-ratio-weighted channel,
    so it is trimmed to in-gear samples first (the gear channel flips before the
    shift lands and those samples read ~50 hp high). Peaks are taken *per pull*
    and then averaged, rather than pooled across every sample in a slot -- a
    pooled maximum rewards whichever slot happened to get more pulls. Peak airmass
    rides along because it measures the boost contrast directly, without going
    through an acceleration model at all.
    """
    pulls = attribute()
    print("\n## Power and filling by slot — per-pull peaks, 3rd gear only\n")
    print("| Slot | Peak HP mean | sd | n | Peak airmass mg/stk |")
    print("|-----|--------------|----|---|---------------------|")
    stash = {}
    for slot in (3, 4, 5):
        hp_peaks, air_peaks = [], []
        for p in (x for x in pulls if x.slot == slot and x.gear == 3):
            rows = list(csv.DictReader(
                open(HERE / f"{p.file}.csv", encoding="utf-8-sig")))
            def chan(name):
                return np.array([float(r[name]) for r in rows])
            gear, pedal = chan("Gear (gear)"), chan("Pedal Pos (%)")
            idx = np.arange(len(rows))
            m = ((idx >= p.start_row) & (idx <= p.end_row)
                 & (np.rint(gear) == 3) & (pedal >= 90.0))
            hp_peaks.append(float(np.percentile(chan("Calc HP (hp)")[m], 99.5)))
            air_peaks.append(float(np.percentile(chan("Airmass (g/stk)")[m] * 1000.0, 99.5)))
        stash[slot] = np.array(hp_peaks)
        a = np.array(hp_peaks)
        print(f"| {slot} | {a.mean():.1f} | {a.std(ddof=1):.2f} | {a.size} "
              f"| {np.mean(air_peaks):.1f} |")

    print("\n| Contrast | Δ Peak HP | se | separation |")
    print("|----------|-----------|----|------------|")
    for a, b in ((3, 4), (3, 5), (4, 5)):
        x, y = stash[a], stash[b]
        se = float(np.sqrt(x.var(ddof=1) / x.size + y.var(ddof=1) / y.size))
        print(f"| slot {b} − slot {a} | {y.mean()-x.mean():+.2f} | {se:.2f} "
              f"| {abs(y.mean()-x.mean())/se:.2f} se |")


def main() -> int:
    pulls = attribute()
    resolved = [p for p in pulls if p.slot is not None]
    unresolved = [p for p in pulls if p.slot is None]
    if unresolved:
        print(f"UNATTRIBUTED pulls (excluded): "
              f"{[p.index for p in unresolved]}")

    # Load each file once, then split its loaded samples between the pulls it
    # holds -- 06_55_01 carries one slot-5 pull and one slot-4 pull.
    by_file: dict[str, dict[str, np.ndarray]] = {}
    for p in resolved:
        if p.file not in by_file:
            by_file[p.file] = load(HERE / f"{p.file}.csv")

    slot_masks: dict[int, list[tuple[str, np.ndarray]]] = {3: [], 4: [], 5: []}
    for name, data in by_file.items():
        here = [p for p in resolved if p.file == name]
        loaded = loaded_mask(data)
        rows = np.arange(data["rpm"].size)
        centres = np.array([(p.start_row + p.end_row) / 2.0 for p in here])
        dist = np.abs(rows[:, None] - centres[None, :])
        nearest = np.argmin(dist, axis=1)
        for i, p in enumerate(here):
            own = loaded & (nearest == i) & (dist[np.arange(rows.size), nearest]
                                             <= MAX_ROWS_FROM_PULL)
            slot_masks[p.slot].append((name, own))

    print("\n## Slot attribution and exposure\n")
    print("| Slot | Pulls | Loaded WOT (s) | Events | Rate /loaded-min | Worst °CRK |")
    print("|-----|-------|----------------|--------|------------------|------------|")
    slot_stats = {}
    for slot in (3, 4, 5):
        idx = [p.index for p in resolved if p.slot == slot]
        exposure = 0.0
        events: list[dict] = []
        for name, own in slot_masks[slot]:
            data = by_file[name]
            exposure += float(own.sum()) * SAMPLE_S
            masked = {k: v.copy() for k, v in data.items()}
            # Blank non-slot samples so knock_events cannot cross into the
            # other slot's pull in the same file.
            for key in KNOCK_KEYS:
                masked[key] = np.where(own, masked[key], 0.0)
            masked["pedal"] = np.where(own, masked["pedal"], 0.0)
            events.extend(knock_events([(name, masked)]))
        worst = min((e["worst_deg"] for e in events), default=0.0)
        rate = 60.0 * len(events) / exposure if exposure else float("nan")
        slot_stats[slot] = (exposure, events, rate)
        print(f"| {slot} | {len(idx)} ({','.join(map(str, idx))}) | {exposure:.1f} "
              f"| {len(events)} | {rate:.1f} | {worst:+.2f} |")

    print("\n## Events per loaded minute, by band\n")
    hdr = "| Band (rpm) | " + " | ".join(f"slot {s}" for s in (3, 4, 5)) \
          + " | " + " | ".join(f"mg/stk s{s}" for s in (3, 4, 5)) + " |"
    print(hdr)
    print("|" + "---|" * (1 + 6))
    band_detail = {}
    for lo, hi in BANDS:
        cells, airs, raw = [], [], {}
        for slot in (3, 4, 5):
            exposure_b, n_b, air_vals = 0.0, 0, []
            for name, own in slot_masks[slot]:
                data = by_file[name]
                inb = own & (data["rpm"] >= lo) & (data["rpm"] < hi)
                exposure_b += float(inb.sum()) * SAMPLE_S
                air_vals.append(data["airmass"][inb] * 1000.0)
            for e in slot_stats[slot][1]:
                if lo <= e["worst_rpm"] < hi:
                    n_b += 1
            rate = 60.0 * n_b / exposure_b if exposure_b else float("nan")
            raw[slot] = (n_b, exposure_b)
            cells.append(f"{rate:.1f} ({n_b}/{exposure_b:.1f}s)")
            allair = np.concatenate(air_vals) if air_vals else np.array([])
            airs.append(f"{allair.mean():.0f}" if allair.size else "-")
        band_detail[(lo, hi)] = raw
        print(f"| {lo}-{hi} | " + " | ".join(cells) + " | " + " | ".join(airs) + " |")

    print(f"\n## The experiment: {FOCUS_BAND[0]}-{FOCUS_BAND[1]} rpm\n")
    n3, e3 = band_detail[FOCUS_BAND][3]
    for slot in (4, 5):
        n, e = band_detail[FOCUS_BAND][slot]
        expected = (n3 / e3 * e) if e3 else float("nan")
        print(f"{SLOT_LABEL[slot]}")
        print(f"  {n} events over {e:.1f}s; control-matched expectation "
              f"{expected:.2f}; Poisson P(X>={n}) = {poisson_upper_p(n, expected):.4f}")

    print("\n## Per-cylinder event counts\n")
    print("| Slot | cyl 1 | cyl 2 | cyl 3 | cyl 4 |")
    print("|-----|-------|-------|-------|-------|")
    for slot in (3, 4, 5):
        counts = [sum(1 for e in slot_stats[slot][1] if e["cylinder"] == c)
                  for c in (1, 2, 3, 4)]
        print(f"| {slot} | " + " | ".join(str(c) for c in counts) + " |")

    print("\n## Every event, by slot\n")
    print("| Slot | Pull file | Cyl | Onset rpm | Worst rpm | Worst °CRK | mg/stk | Gear | Carry s |")
    print("|-----|-----------|-----|-----------|-----------|------------|--------|------|---------|")
    for slot in (3, 4, 5):
        for e in sorted(slot_stats[slot][1], key=lambda x: x["worst_rpm"]):
            print(f"| {slot} | {e['tag'][-8:]} | {e['cylinder']} | {e['onset_rpm']:.0f} "
                  f"| {e['worst_rpm']:.0f} | {e['worst_deg']:+.2f} | {e['airmass']:.0f} "
                  f"| {e['gear']} | {e['carry_s']:.2f} |")

    print("\n## Cross-revision: the 4500-5000 band on identical definitions\n")
    prior = prior_sessions()
    print("| Session / slot | Calibration | Events | Exposure s | ev/min | 95% CI |")
    print("|----------------|-------------|--------|------------|--------|--------|")
    rows_x = list(prior) + [
        (f"R22 slot {s}", SLOT_LABEL[s].split(" - ")[1],
         band_detail[FOCUS_BAND][s][0], band_detail[FOCUS_BAND][s][1])
        for s in (3, 4, 5)
    ]
    for label, calib, n, t in rows_x:
        lo, hi = poisson_rate_ci(n, t)
        print(f"| {label} | {calib} | {n} | {t:.1f} | {60*n/t:.1f} | [{lo:.1f}, {hi:.1f}] |")

    make_plot(band_detail, rows_x)
    slot_contrasts(files_for_metric())

    print("\n## Gear exposure (did WOT carry into 4th?)\n")
    for slot in (3, 4, 5):
        gears: dict[int, float] = {}
        for name, own in slot_masks[slot]:
            g = np.rint(by_file[name]["gear"][own]).astype(int)
            for val in np.unique(g):
                gears[int(val)] = gears.get(int(val), 0.0) + float((g == val).sum()) * SAMPLE_S
        print(f"  slot {slot}: " + ", ".join(f"{k}th {v:.1f}s" for k, v in sorted(gears.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
