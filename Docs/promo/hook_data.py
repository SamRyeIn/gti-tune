#!/usr/bin/env python3
"""Real numbers for the 20-second hook, derived from the logs — never typed in.

The hook puts big figures on screen, so how they are derived matters more than
for any other part of the promo. The rules, and why:

* **Detected WOT pulls only.** Pull windows come from `simoscal.analysis`, the
  same detector the log reviews use — not a max over the whole file.
* **In-gear samples only.** `Calc HP` is acceleration-derived *and*
  gear-ratio-weighted, so the samples where the gear channel has already flipped
  to the next ratio while the engine is still pulling read ~50 hp high. That is a
  pure artifact — it is what drew a spike at the top of the rpm range, and it was
  also setting the quoted peak. Every pull is trimmed to the samples still in its
  attributed gear before anything is peaked, curved, or plotted. See `_in_gear`.
* **3rd gear or higher.** Third is the gear this car's comparable pulls are
  logged in, and the only one with full-range coverage: the R14 2nd-gear windows
  are ~50 samples and do not start until ~3750 rpm. Trimmed, 2nd and 3rd now
  agree to within ~4 hp on the same R14 session (294 vs 298) — before the trim,
  2nd read 372 and 3rd 347, and that gap was the artifact, not the gearing.
* **Smoothed.** A short moving average over the pull kills single-sample spikes;
  the peak of the smoothed trace is the number, not the peak sample.
* **Comparable pulls only, for the revision series.** A revision is charted only
  if it has a 3rd-gear pull that ran to redline. R11's only pulls are 4th gear
  and stop at ~5300 rpm, so its peak is not a peak — it is excluded rather than
  charted low, and `EXCLUDED_REVS` records why.

Everything is cached to `assets/hook_data.json` because loading seven log
folders costs ~20 s. Delete that file to re-derive.

    python3 Docs/promo/hook_data.py     # print what the hook will show
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, asdict
from functools import lru_cache

import numpy as np

import config

CACHE = config.ASSET_DIR / "hook_data.json"
CACHE_SCHEMA = 4        # bump when the cached shape changes; older files re-derive

SMOOTH_N = 5            # samples ≈ 0.2 s at the logs' ~24 Hz
MIN_GEAR = 3            # 2nd-gear Calc HP reads high; 3rd is the comparable gear
REDLINE_RPM = 6000.0    # a pull must reach this to count as a full pull
CURVE_BINS = 64         # rpm bins the drawn-on dyno curve is resampled to

# The revision the hook headlines — the newest tune in the lineage.
HEADLINE_REV = "R14"


@dataclass(frozen=True)
class RevPeak:
    """One revision's best comparable pull."""

    rev: str
    hp: float
    tq: float | None
    boost: float | None
    rpm_max: float
    gear: int
    log: str


@dataclass(frozen=True)
class BoostCurve:
    """One revision's logged gauge boost over the rpm sweep of its best pull.

    Same pull the revision's hp figure comes from, so the boost beat and the
    climb beat are never describing two different runs of the car.
    """

    rev: str
    rpm: list[float]
    psi: list[float]

    @property
    def peak(self) -> float:
        return max(self.psi)


@dataclass(frozen=True)
class HookData:
    revisions: list[RevPeak]        # charted, in revision order
    excluded: list[dict]            # {rev, reason} — kept so the exclusion is visible
    curve_rpm: list[float]          # the headline revision's hp/tq curve
    curve_hp: list[float]
    curve_tq: list[float]
    boost_curves: list[BoostCurve]  # one per charted revision that logged boost
    boost_missing: list[str]        # charted revisions whose logs have no boost
    trace_t: list[float]            # the same pull, sample by sample, for the
    trace_rpm: list[float]          # live table walk: seconds from pull start,
    trace_airmass: list[float]      # engine speed, and airmass (mg/stk)

    @property
    def trace_duration_s(self) -> float:
        return self.trace_t[-1] - self.trace_t[0] if self.trace_t else 0.0

    @property
    def headline(self) -> RevPeak:
        return next(r for r in self.revisions if r.rev == HEADLINE_REV)

    @property
    def baseline(self) -> RevPeak:
        return self.revisions[0]

    @property
    def hp_gain(self) -> float:
        return self.headline.hp - self.baseline.hp


# ---------------------------------------------------------------- log plumbing

def _smooth(a: np.ndarray) -> np.ndarray:
    if a.size < SMOOTH_N:
        return a
    return np.convolve(a, np.ones(SMOOTH_N) / SMOOTH_N, mode="valid")


def _finite(a: np.ndarray | None) -> np.ndarray:
    return np.asarray([]) if a is None else a[np.isfinite(a)]


def _raw_column(path, header: str) -> np.ndarray | None:
    """A CSV column the analysis channel registry does not map (`Calc TQ (nm)`)."""
    with open(path, newline="") as fh:
        reader = csv.reader(fh)
        try:
            head = next(reader)
        except StopIteration:
            return None
        if header not in head:
            return None
        idx = head.index(header)
        out: list[float] = []
        for row in reader:
            try:
                out.append(float(row[idx]))
            except (ValueError, IndexError):
                out.append(np.nan)
    return np.asarray(out, dtype=float)


def _walk(lf, rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """The pull's (time, rpm, airmass) — what the table-walk beat plays back.

    Returns ``None`` if the file lacks a usable clock or airmass, because the
    beat animates a real lookup or it does not run at all.
    """
    rpm = lf.channel("rpm")
    airmass = lf.channel("airmass")
    time = lf.time
    if rpm is None or airmass is None or time is None:
        return None
    t = np.asarray(time[rows], dtype=float)
    r = np.asarray(rpm[rows], dtype=float)
    a = np.asarray(airmass[rows], dtype=float)
    ok = np.isfinite(t) & np.isfinite(r) & np.isfinite(a)
    if ok.sum() < 10:
        return None
    t, r, a = t[ok], r[ok], a[ok]
    return t - t[0], r, a


def _import_analysis():
    if str(config.CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(config.CODE_ROOT))
    from simoscal.analysis.log import load_logset      # noqa: PLC0415 — heavy import
    from simoscal.analysis.pulls import detect_pulls   # noqa: PLC0415
    return load_logset, detect_pulls


def _peak(arr: np.ndarray | None, rows: np.ndarray) -> float | None:
    """Peak of the smoothed trace over the given rows."""
    if arr is None:
        return None
    seg = _finite(arr[rows])
    if seg.size < SMOOTH_N:
        return None
    return float(_smooth(seg).max())


def _in_gear(lf, pull) -> np.ndarray:
    """Row indices of the pull that are still in the gear it was attributed to.

    `Calc HP` is acceleration-derived *and* gear-ratio-weighted, so a sample
    carrying the wrong gear carries the wrong power. The DSG's gear channel
    flips to the next ratio a few samples before the shift actually takes the
    engine down — in R14's best pull, gear reads 4 for eight samples while rpm
    is still climbing to 6276, and `Calc HP` jumps 292 → 348 hp across that
    boundary while longitudinal acceleration is *falling*. Those samples are the
    spike at the top of the rpm range, and they were also setting the headline
    figure, so they are cut before anything is peaked or plotted.

    A pull whose gear is unresolved never gets this far (`_best_pull` requires
    a resolved gear), so there is no guessing here.
    """
    rows = np.arange(pull.start_row, pull.end_row + 1)
    gear = lf.channel("gear")
    if gear is None:
        return rows
    g = np.round(np.asarray(gear[rows], dtype=float))
    return rows[g == pull.gear]


def _best_pull(folder):
    """The highest-hp comparable pull in a log folder, its curve, and its walk."""
    load_logset, detect_pulls = _import_analysis()
    logset = load_logset(folder)
    by_name = {lf.name: lf for lf in logset}

    best = None
    saw_pull = False
    reached_redline = False
    for pull in detect_pulls(logset):
        saw_pull = True
        if not (pull.gear_resolved and pull.gear is not None and pull.gear >= MIN_GEAR):
            continue
        lf = by_name[pull.file]
        rows = _in_gear(lf, pull)
        if rows.size < SMOOTH_N:
            continue
        rpm_col = np.asarray(lf.channel("rpm")[rows], dtype=float)
        rpm_max = float(np.nanmax(rpm_col)) if np.isfinite(rpm_col).any() else 0.0
        # Judged on the in-gear sweep: a pull only counts as full if it ran to
        # redline *before* the shift, not counting the post-flip samples.
        if rpm_max < REDLINE_RPM:
            continue
        reached_redline = True
        hp_col = lf.channel("calc_hp")
        hp = _peak(hp_col, rows)
        if hp is None:
            continue
        if best is None or hp > best[0].hp:
            tq_col = _raw_column(lf.path, "Calc TQ (nm)")
            if tq_col is not None and tq_col.size < lf.n_rows:
                tq_col = None                    # misaligned; drop rather than mis-slice
            peak = RevPeak(
                rev=folder.name.split("_")[-1],
                hp=hp,
                tq=_peak(tq_col, rows),
                boost=_peak(lf.channel("boost"), rows),
                rpm_max=rpm_max,
                gear=pull.gear,
                log=lf.name,
            )
            trace = (
                rpm_col,
                np.asarray(hp_col[rows], dtype=float),
                np.asarray(tq_col[rows], dtype=float) if tq_col is not None else None,
            )
            # The boost curve rides the same rows as the hp figure, so the two
            # beats are always talking about one pull.
            boost_col = lf.channel("boost")
            boost = (None if boost_col is None
                     else _resample(rpm_col, np.asarray(boost_col[rows], dtype=float)))
            best = (peak, trace, _walk(lf, rows), boost)

    if best is None:
        if not saw_pull:
            reason = "no WOT pulls detected"
        elif not reached_redline:
            reason = (f"no gear-{MIN_GEAR}-or-higher pull reaching {REDLINE_RPM:.0f} rpm "
                      f"before its upshift")
        else:
            reason = "no Calc HP channel on the qualifying pulls"
        return None, reason
    return best, None


RPM_BACKSLIDE = 60.0    # rpm a sample may sit below the running max and still count


def _rising(rpm: np.ndarray) -> np.ndarray:
    """Mask of the pull's actual rpm sweep, dropping the post-lift tail.

    The detector already trims most of the shift tail, but the last samples of a
    pull can still fall away as the driver lifts. Sorting those by rpm folds them
    back under the climbing part of the curve and draws a spike at redline, so
    they are dropped: a sample counts only while rpm stays at (or just under) the
    highest rpm seen so far.
    """
    keep = np.ones(rpm.size, dtype=bool)
    running = -np.inf
    for i, r in enumerate(rpm):
        if r >= running - RPM_BACKSLIDE:
            running = max(running, r)
        else:
            keep[i:] = False        # once it falls away, the pull is over
            break
    return keep


def _edge_smooth(a: np.ndarray, width: int = 3) -> np.ndarray:
    """Moving average that repeats the end values instead of padding with zero.

    `np.convolve(..., "same")` pads with zeros, which drags the first and last
    points of a curve toward the axis — on a dyno plot that reads as a cliff at
    redline that the car never did. Padding with the edge value keeps the ends
    honest.
    """
    if a.size < width:
        return a
    pad = width // 2
    return np.convolve(np.pad(a, pad, mode="edge"), np.ones(width) / width, mode="valid")


def _resample(rpm: np.ndarray, vals: np.ndarray) -> tuple[list[float], list[float]] | None:
    """One channel over a pull, on an even rpm grid — the single-series `_curve`.

    Same pipeline as `_curve` (finite mask, rising sweep, sort by rpm, interpolate,
    edge-smooth); kept separate because `_curve` has to carry hp and tq on one
    shared grid while this returns a curve that owns its own rpm range. That
    matters here: every revision's pull starts and ends at a different engine
    speed, and stretching them onto a common grid would invent boost the car
    never made at rpm it never saw.
    """
    ok = np.isfinite(rpm) & np.isfinite(vals)
    rpm, vals = rpm[ok], vals[ok]
    if rpm.size < SMOOTH_N:
        return None
    sweep = _rising(rpm)
    rpm, vals = rpm[sweep], vals[sweep]
    if rpm.size < SMOOTH_N or rpm.max() - rpm.min() < 1.0:
        return None
    order = np.argsort(rpm)
    rpm, vals = rpm[order], vals[order]
    grid = np.linspace(rpm.min(), rpm.max(), CURVE_BINS)
    return grid.tolist(), _edge_smooth(np.interp(grid, rpm, vals)).tolist()


def _curve(trace) -> tuple[list[float], list[float], list[float]]:
    """Resample a pull's hp/tq onto an even rpm grid so the curve draws smoothly."""
    rpm, hp, tq = trace
    ok = np.isfinite(rpm) & np.isfinite(hp)
    rpm, hp = rpm[ok], hp[ok]
    tq = tq[ok] if tq is not None else None

    sweep = _rising(rpm)
    rpm, hp = rpm[sweep], hp[sweep]
    tq = tq[sweep] if tq is not None else None

    order = np.argsort(rpm)
    rpm, hp = rpm[order], hp[order]
    tq = tq[order] if tq is not None else None

    grid = np.linspace(rpm.min(), rpm.max(), CURVE_BINS)
    hp_i = _edge_smooth(np.interp(grid, rpm, hp))
    tq_i = _edge_smooth(np.interp(grid, rpm, tq)) if tq is not None else np.zeros_like(grid)
    return grid.tolist(), hp_i.tolist(), tq_i.tolist()


# -------------------------------------------------------------------- the data

def _derive() -> HookData:
    folders = sorted(config.LOGS_ROOT.glob("BasicsGuide_R*"), key=config._rev_sort_key)
    revisions: list[RevPeak] = []
    excluded: list[dict] = []
    boost_curves: list[BoostCurve] = []
    boost_missing: list[str] = []
    curve: tuple[list[float], list[float], list[float]] | None = None
    walk = None

    for folder in folders:
        best, reason = _best_pull(folder)
        rev = folder.name.split("_")[-1]
        if best is None:
            excluded.append({"rev": rev, "reason": reason})
            continue
        peak, trace, pull_walk, boost = best
        revisions.append(peak)
        # A revision with no boost channel is named, not quietly absent: the
        # boost beat says how many revisions it is drawing.
        if boost is None:
            boost_missing.append(rev)
        else:
            boost_curves.append(BoostCurve(rev=rev, rpm=boost[0], psi=boost[1]))
        if rev == HEADLINE_REV:
            curve = _curve(trace)
            walk = pull_walk

    if not revisions:
        raise SystemExit("no comparable WOT pulls found in any Logs/BasicsGuide_R* folder")
    if curve is None:
        raise SystemExit(
            f"the headline revision {HEADLINE_REV} has no comparable pull "
            f"(excluded: {excluded}) — point HEADLINE_REV at a revision that does"
        )
    if walk is None:
        raise SystemExit(
            f"{HEADLINE_REV}'s pull has no usable time/airmass channels — the "
            "table-walk beat animates a real lookup, so it cannot be faked"
        )
    if len(boost_curves) < 2:
        raise SystemExit(
            f"only {len(boost_curves)} revision(s) logged boost ({boost_missing} did "
            "not) — the boost beat is a comparison and has nothing to compare"
        )
    return HookData(revisions=revisions, excluded=excluded,
                    curve_rpm=curve[0], curve_hp=curve[1], curve_tq=curve[2],
                    boost_curves=boost_curves, boost_missing=boost_missing,
                    trace_t=walk[0].tolist(), trace_rpm=walk[1].tolist(),
                    trace_airmass=walk[2].tolist())


@lru_cache(maxsize=1)
def hook_data() -> HookData:
    """The hook's figures, cached on disk between builds."""
    if CACHE.is_file():
        raw = json.loads(CACHE.read_text())
        if raw.get("schema") == CACHE_SCHEMA:      # a stale cache is re-derived
            return HookData(
                revisions=[RevPeak(**r) for r in raw["revisions"]],
                excluded=raw["excluded"],
                curve_rpm=raw["curve_rpm"], curve_hp=raw["curve_hp"],
                curve_tq=raw["curve_tq"],
                boost_curves=[BoostCurve(**c) for c in raw["boost_curves"]],
                boost_missing=raw["boost_missing"], trace_t=raw["trace_t"],
                trace_rpm=raw["trace_rpm"], trace_airmass=raw["trace_airmass"],
            )
    data = _derive()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(
        {"schema": CACHE_SCHEMA,
         "revisions": [asdict(r) for r in data.revisions], "excluded": data.excluded,
         "curve_rpm": data.curve_rpm, "curve_hp": data.curve_hp, "curve_tq": data.curve_tq,
         "boost_curves": [asdict(c) for c in data.boost_curves],
         "boost_missing": data.boost_missing,
         "trace_t": data.trace_t, "trace_rpm": data.trace_rpm,
         "trace_airmass": data.trace_airmass},
        indent=2))
    return data


if __name__ == "__main__":
    d = hook_data()
    print(f"charted revisions ({len(d.revisions)}):")
    for r in d.revisions:
        tq = "  --  " if r.tq is None else f"{r.tq:6.1f}"
        print(f"  {r.rev:<4} {r.hp:6.1f} hp  {tq} Nm  "
              f"{r.boost or 0:5.1f} psi  to {r.rpm_max:.0f} rpm in gear {r.gear}  [{r.log}]")
    for x in d.excluded:
        print(f"  {x['rev']:<4} EXCLUDED — {x['reason']}")
    print(f"\nheadline : {d.headline.rev}  {d.headline.hp:.0f} hp / "
          f"{d.headline.tq:.0f} Nm / {d.headline.boost:.1f} psi")
    print(f"baseline : {d.baseline.rev}  {d.baseline.hp:.0f} hp")
    print(f"gain     : +{d.hp_gain:.0f} hp")
    print(f"curve    : {len(d.curve_rpm)} points, "
          f"{d.curve_rpm[0]:.0f}-{d.curve_rpm[-1]:.0f} rpm")
    print(f"\nboost curves ({len(d.boost_curves)}):")
    for c in d.boost_curves:
        print(f"  {c.rev:<4} {c.rpm[0]:.0f}-{c.rpm[-1]:.0f} rpm  "
              f"{min(c.psi):5.1f}-{c.peak:5.1f} psi")
    for rev in d.boost_missing:
        print(f"  {rev:<4} NO BOOST CHANNEL — not drawn")
    print(f"walk     : {len(d.trace_t)} samples over {d.trace_duration_s:.1f} s, "
          f"{min(d.trace_rpm):.0f}-{max(d.trace_rpm):.0f} rpm, "
          f"{min(d.trace_airmass):.0f}-{max(d.trace_airmass):.0f} mg/stk")
