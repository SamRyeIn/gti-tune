"""Print the aggressive-slot knock picture and write its CSVs and plots.

Answers the three questions an R23 aggressive slot has to be sized against:

1. **Where does this curve knock?** Event rate by rpm band and by airmass bin,
   pooled across every base-timing session that ran it, with exact Poisson
   intervals — most bins rest on single-digit counts and a bare rate would imply
   a precision this data does not have.
2. **What is it being fuelled with there?** Commanded `Lambda SP` per band
   against the EQT Stage 2 calibration's, whose 111k-sample logs are the only
   evidence in this project that ties knock to fuelling rather than to timing.
3. **What would enrichment cost?** `HPFP Eff Vol` — high-pressure fuel pump
   effective volume per band, which is the binding constraint on going richer.

**One residual worth knowing about before reading the lambda panel.** Replaying
`IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda setpoint grid reproduces the logged
`Lambda SP` to a median 0.001 lambda over the whole population, but not evenly:
at **4500-5000 rpm the logged command runs about 0.020 richer than the grid
alone**, and about 0.009 richer at 5000-5500. It is not the axis running off its
top breakpoint — 61 % of loaded samples do exceed 1389 mg/stk, and testing clamp
against extrapolation there says the ECU **clamps** (median absolute error
0.00103 against 0.00830) — and it is not the full-load enrichment maps, which
this calibration holds at 1.000, nor the minimum-lambda floors, which cannot
force a richer mixture. Some other path enriches those two bands and it is not
yet identified.

Two consequences. The figure's R23 curve is therefore the **logged** channel
scaled by the grid's own ratio, never the replayed value, so a band the grid
does not touch shows no change instead of showing the residual. And the real gap
to EQT Stage 2 at 4500-5000 is *smaller* than the grid implies, which only
strengthens the conclusion that fuelling has nothing left to give in that band.

Run:  Code/.venv/bin/python Logs/aggressive_slot_lineage/report.py
"""

from __future__ import annotations

import csv
from math import exp, factorial
from pathlib import Path

import numpy as np

from lineage import (
    AIR_BINS, BANDS, HERE, REPO_ROOT, channel_profile, collect, events,
    exposure, loaded_mask,
)

EQT_FUELLING = REPO_ROOT / "Docs" / "eqt-timing-re" / "fuelling_eqt_vs_r22.csv"
PLOT_DIR = HERE / "plots"

#: What R23 actually wrote into the base lambda grid, so the figure's "R23"
#: curve is the shipped calibration and not a restatement of it.
R23_ENRICHMENT = {3008: 0.930, 5504: 0.780, 5984: 0.780,
                  6496: 0.780, 7008: 0.780}


def poisson_ci(n: int, seconds: float, conf: float = 0.95) -> tuple[float, float]:
    """Exact (Garwood) Poisson rate interval, in events per minute."""
    if seconds <= 0.0:
        return float("nan"), float("nan")
    alpha = 1.0 - conf

    def cdf(k: int, mu: float) -> float:
        return sum(exp(-mu) * mu ** j / factorial(j) for j in range(k + 1))

    def solve(f, target: float) -> float:
        lo, hi = 0.0, 1000.0
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            lo, hi = (mid, hi) if f(mid) > target else (lo, mid)
        return 0.5 * (lo + hi)

    low = 0.0 if n == 0 else solve(lambda mu: cdf(n - 1, mu), 1.0 - alpha / 2.0)
    high = solve(lambda mu: cdf(n, mu), alpha / 2.0)
    return 60.0 * low / seconds, 60.0 * high / seconds


def eqt_lambda() -> dict[tuple[int, int], float]:
    """EQT Stage 2's median commanded lambda per rpm band."""
    with EQT_FUELLING.open(encoding="utf-8") as handle:
        return {(int(r["rpm_lo"]), int(r["rpm_hi"])): float(r["eqt_lambda"])
                for r in csv.DictReader(handle)}


def evidence_plot(band_rate, lam, hpfp, air_p, eqt, r23_lambda,
                  r23_hpfp) -> Path:
    """One figure: where the knock is, what it is fuelled with, what the pump has.

    Three panels sharing the rpm axis, because the whole R23 argument is that
    those three curves line up — the worst knock band is also the leanest
    relative to EQT and the one with pump headroom left, and the second-worst has
    neither. Read top to bottom it is the case for enriching 3000-3500 and
    spending 3500-4500 on timing.

    Knock rates carry exact Poisson intervals: every band rests on 0-10 events
    and a bare bar chart would imply a precision seven sessions cannot give.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    centres = [0.5 * (lo + hi) for lo, hi in BANDS]
    fig, axes = plt.subplots(3, 1, figsize=(9.5, 10.5), sharex=True)

    ax = axes[0]
    rates = [band_rate[b][2] for b in BANDS]
    lo_err = [max(0.0, band_rate[b][2] - band_rate[b][3]) for b in BANDS]
    hi_err = [max(0.0, band_rate[b][4] - band_rate[b][2]) for b in BANDS]
    ax.errorbar(centres, rates, yerr=[lo_err, hi_err], fmt="o-", color="tab:red",
                capsize=4, lw=2, label="knock events per loaded minute")
    for band, rate in zip(BANDS, rates):
        n = band_rate[band][0]
        ax.annotate(f"{n} ev", (0.5 * (band[0] + band[1]), rate),
                    textcoords="offset points", xytext=(0, 10), ha="center",
                    fontsize=8, color="tab:red")
    ax.axvspan(3000, 3500, color="tab:red", alpha=0.10)
    ax.axvspan(4500, 5000, color="tab:red", alpha=0.10)
    ax.axvspan(3500, 4500, color="tab:green", alpha=0.10)
    ax.set_ylabel("events / loaded min", fontweight="bold")
    ax.set_title("Aggressive ~26 psi slot: 51 pump-92 logs, R09-R19, base timing\n"
                 "knock is in two bands, and the band between them is silent",
                 fontsize=11)
    ax.legend(loc="upper right", fontsize=9)

    ax = axes[1]
    ax.plot(centres, [lam[b][0] for b in BANDS], "o-", color="tab:blue", lw=2,
            label="R22 commanded `Lambda SP`, as logged")
    ax.plot(centres, [r23_lambda[b] for b in BANDS], "s--", color="tab:cyan",
            lw=2, label="R23 predicted (logged x the grid's own ratio)")
    ax.plot(centres, [eqt.get(b, float("nan")) for b in BANDS], "^-",
            color="tab:purple", lw=2, label="EQT Stage 2, logged")
    ax.axvspan(3000, 3500, color="tab:red", alpha=0.10)
    ax.axvspan(4500, 5000, color="tab:red", alpha=0.10)
    ax.invert_yaxis()
    ax.set_ylabel("lambda, richer is lower -->", fontweight="bold")
    # Lower right: the axis is inverted, so the curves crowd the top-right.
    ax.legend(loc="lower right", fontsize=9)

    ax = axes[2]
    ax.plot(centres, [hpfp[b][0] for b in BANDS], "o-", color="tab:orange",
            lw=2, label="`HPFP Eff Vol` median, R22")
    ax.plot(centres, [hpfp[b][1] for b in BANDS], "o:", color="tab:orange",
            lw=1.5, alpha=0.7, label="p95, R22")
    ax.plot(centres, [r23_hpfp[b] for b in BANDS], "s--", color="tab:brown",
            lw=2, label="median, R23 predicted")
    ax.axhline(100.0, color="k", ls="--", lw=1)
    ax.annotate("pump on its stop — enrichment stops arriving",
                (centres[0], 100.0), textcoords="offset points",
                xytext=(0, -14), fontsize=8)
    ax.axvspan(3000, 3500, color="tab:red", alpha=0.10)
    ax.axvspan(4500, 5000, color="tab:red", alpha=0.10)
    ax.set_ylabel("HPFP effective volume (%)", fontweight="bold")
    ax.set_xlabel("engine speed (rpm)", fontweight="bold")
    ax.legend(loc="lower left", fontsize=9)

    for ax in axes:
        ax.grid(True, which="major", alpha=0.4)
        ax.minorticks_on()
        ax.grid(True, which="minor", alpha=0.15)

    fig.tight_layout()
    out = PLOT_DIR / "aggressive_slot_evidence.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def main() -> int:
    kept, dropped = collect()
    pump = [s for s in kept if s.fuel == "plain 92"]
    dosed = [s for s in kept if s.fuel == "dosed"]

    print("AGGRESSIVE ~26 psi SLOT — every base-timing log, by revision")
    print(f"{'rev':>4} {'logs':>5} {'loaded s':>9} {'cap peak':>9} "
          f"{'offset':>7}  fuel")
    for revision in sorted({s.revision for s in kept}):
        group = [s for s in kept if s.revision == revision]
        peaks = {round(s.put_peak_hpa) for s in group}
        offs = [s.offset_deg for s in group if np.isfinite(s.offset_deg)]
        print(f"  R{revision:<2} {len(group):>5} {sum(s.loaded_s for s in group):>9.1f} "
              f"{min(peaks):>5}-{max(peaks):<3} "
              f"{(np.median(offs) if offs else float('nan')):>+7.2f}  "
              f"{group[0].fuel}")
    print(f"  total: {len(kept)} logs, "
          f"{sum(s.loaded_s for s in kept):.1f} loaded s "
          f"({len(pump)} plain 92, {len(dosed)} dosed)")

    print(f"\nExcluded ({len(dropped)} logs) — reasons, deduplicated:")
    reasons: dict[str, list[str]] = {}
    for revision, tag, why in dropped:
        key = why.split(" — ")[-1] if "—" in why else why
        reasons.setdefault(key, []).append(f"R{revision}")
    for why, who in sorted(reasons.items()):
        counts = {r: who.count(r) for r in sorted(set(who), key=lambda x: int(x[1:]))}
        print(f"  {len(who):>3}  {why}  "
              f"({', '.join(f'{r}x{n}' for r, n in counts.items())})")

    ev = events(pump)
    ev_dosed = events(dosed)
    print(f"\nKNOCK BY RPM BAND — pump 92, base timing, aggressive curve "
          f"({len(pump)} logs)")
    print(f"{'band':>12} {'events':>7} {'loaded s':>9} {'per min':>8} "
          f"{'95% CI':>16} {'deepest':>8} {'median air':>11}")
    band_rate = {}
    for lo, hi in BANDS:
        inside = [e for e in ev if lo <= e["worst_rpm"] < hi]
        secs = exposure(pump, lo, hi)
        rate = 60.0 * len(inside) / secs if secs else float("nan")
        low, high = poisson_ci(len(inside), secs)
        deepest = min((e["worst_deg"] for e in inside), default=float("nan"))
        air = np.median([e["airmass"] for e in inside]) if inside else float("nan")
        band_rate[(lo, hi)] = (len(inside), secs, rate, low, high)
        print(f"  {lo:>5}-{hi:<5} {len(inside):>7} {secs:>9.1f} {rate:>8.2f} "
              f"  [{low:>5.2f},{high:>6.2f}] {deepest:>8.2f} {air:>11.0f}")

    print(f"\nKNOCK BY AIRMASS — the same events, binned on the base ignition "
          f"grid's own top rows")
    print(f"{'mg/stk':>12} {'events':>7} {'loaded s':>9} {'per min':>8} "
          f"{'median rpm':>11} {'deepest':>8}")
    for lo, hi in AIR_BINS:
        inside = [e for e in ev if lo <= e["airmass"] < hi]
        secs = sum(exposure([s], b[0], b[1], air=(lo, hi))
                   for s in pump for b in ((3000, 6600),))
        rate = 60.0 * len(inside) / secs if secs else float("nan")
        rpm = np.median([e["worst_rpm"] for e in inside]) if inside else float("nan")
        deepest = min((e["worst_deg"] for e in inside), default=float("nan"))
        print(f"  {lo:>5}-{hi:<5} {len(inside):>7} {secs:>9.1f} {rate:>8.2f} "
              f"{rpm:>11.0f} {deepest:>8.2f}")

    lam = channel_profile(pump, "lambda_sp")
    hpfp = channel_profile(pump, "hpfp")
    air_p = channel_profile(pump, "airmass")
    ign_p = channel_profile(pump, "ign_table")
    eqt = eqt_lambda()
    print("\nFUELLING AND PUMP HEADROOM — pump 92 aggressive-curve loaded WOT")
    print(f"{'band':>12} {'Lambda SP':>10} {'EQT':>7} {'gap':>7} "
          f"{'HPFP med':>9} {'HPFP p95':>9} {'airmass':>9} {'Ign Table':>10}")
    for band in BANDS:
        l_med = lam[band][0]
        e_lam = eqt.get(band, float("nan"))
        print(f"  {band[0]:>5}-{band[1]:<5} {l_med:>10.3f} {e_lam:>7.3f} "
              f"{l_med - e_lam:>+7.3f} {hpfp[band][0]:>9.1f} {hpfp[band][1]:>9.1f} "
              f"{air_p[band][0] * 1000.0:>9.0f} {ign_p[band][0]:>+10.2f}")

    if ev_dosed:
        print(f"\nDOSED CONTROL (R22 slot 3, {len(dosed)} logs) — same curve, "
              f"same base timing, VP Octanium tank")
        for lo, hi in BANDS:
            inside = [e for e in ev_dosed if lo <= e["worst_rpm"] < hi]
            secs = exposure(dosed, lo, hi)
            rate = 60.0 * len(inside) / secs if secs else float("nan")
            print(f"  {lo:>5}-{hi:<5} {len(inside):>3} events, {secs:>5.1f} s, "
                  f"{rate:>6.2f}/min")

    PLOT_DIR.mkdir(exist_ok=True)
    with (HERE / "aggressive_slot_events.csv").open("w", newline="",
                                                    encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list((ev + ev_dosed)[0]))
        writer.writeheader()
        writer.writerows(ev + ev_dosed)

    with (HERE / "aggressive_slot_bands.csv").open("w", newline="",
                                                   encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rpm_lo", "rpm_hi", "events", "loaded_s", "per_min",
                         "ci_lo", "ci_hi", "lambda_sp", "eqt_lambda",
                         "hpfp_med", "hpfp_p95", "airmass_mg", "ign_table"])
        for band in BANDS:
            n, secs, rate, low, high = band_rate[band]
            writer.writerow([band[0], band[1], n, f"{secs:.2f}", f"{rate:.3f}",
                             f"{low:.3f}", f"{high:.3f}", f"{lam[band][0]:.4f}",
                             f"{eqt.get(band, float('nan')):.4f}",
                             f"{hpfp[band][0]:.2f}", f"{hpfp[band][1]:.2f}",
                             f"{air_p[band][0] * 1000.0:.0f}",
                             f"{ign_p[band][0]:.3f}"])
    # The R23 curves, recomputed here rather than quoted, so the figure cannot
    # drift from what `size_r23.py` sized and the revision script wrote.
    from size_r23 import (apply_candidate, base_grid, lookup,
                          FULL_LOAD_LAMBDA_MAX)
    grid, rpm_axis, load_axis = base_grid()
    r23_grid = apply_candidate(grid, rpm_axis, R23_ENRICHMENT)
    r23_lambda, r23_hpfp = {}, {}
    for lo, hi in BANDS:
        rpm, load, logged, pumped = [], [], [], []
        for s_ in pump:
            if "lambda_sp" not in s_.data or "hpfp" not in s_.data:
                continue
            m = (loaded_mask(s_.data) & (s_.data["rpm"] >= lo)
                 & (s_.data["rpm"] < hi)
                 & (s_.data["lambda_sp"] <= FULL_LOAD_LAMBDA_MAX))
            rpm.append(s_.data["rpm"][m])
            load.append(s_.data["airmass"][m] * 1000.0)
            logged.append(s_.data["lambda_sp"][m])
            pumped.append(s_.data["hpfp"][m])
        rpm = np.concatenate(rpm); load = np.concatenate(load)
        pumped = np.concatenate(pumped)
        keep = (np.isfinite(rpm) & np.isfinite(load) & np.isfinite(pumped)
                & np.isfinite(np.concatenate(logged)))
        was = lookup(grid, rpm_axis, load_axis, rpm[keep], load[keep])
        now = lookup(r23_grid, rpm_axis, load_axis, rpm[keep], load[keep])
        # Apply the grid's **ratio** to the logged channel rather than plotting
        # the replayed value directly. The replay reproduces the logged
        # setpoint to 0.001 lambda over the population as a whole, but it runs
        # about 0.020 lean of the log at 4500-5000 rpm and 0.009 at 5000-5500
        # (see the module docstring). Plotting a replayed R23 against a logged
        # R22 turned that residual into a fake leanout in a band R23 does not
        # touch at all. A ratio cancels it: where the grid is unchanged the
        # ratio is exactly 1 and the two curves coincide, which is the claim
        # the figure is there to make.
        logged_lambda = np.concatenate(logged)[keep]
        r23_lambda[(lo, hi)] = float(np.median(logged_lambda * (now / was)))
        r23_hpfp[(lo, hi)] = float(np.median(pumped[keep] * (was / now)))

    plot = evidence_plot(band_rate, lam, hpfp, air_p, eqt, r23_lambda, r23_hpfp)
    print(f"\nWrote {HERE / 'aggressive_slot_events.csv'}")
    print(f"Wrote {HERE / 'aggressive_slot_bands.csv'}")
    print(f"Wrote {plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
