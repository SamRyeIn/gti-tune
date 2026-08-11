#!/usr/bin/env python3
"""Real numbers for the 20-second hook, derived from the logs — never typed in.

The hook puts big figures on screen, so how they are derived matters more than
for any other part of the promo. The rules, and why:

* **Detected WOT pulls only.** Pull windows come from `simoscal.analysis`, the
  same detector the log reviews use — not a max over the whole file.
* **3rd gear or higher.** SimosTools' `Calc HP (hp)` is acceleration-derived, so
  a 2nd-gear pull reads high: the same R14 log shows 372 hp in 2nd and 347 hp in
  3rd. Third is the comparable gear, so third is what gets quoted.
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
class HookData:
    revisions: list[RevPeak]        # charted, in revision order
    excluded: list[dict]            # {rev, reason} — kept so the exclusion is visible
    curve_rpm: list[float]          # the headline revision's hp/tq curve
    curve_hp: list[float]
    curve_tq: list[float]

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


def _import_analysis():
    if str(config.CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(config.CODE_ROOT))
    from simoscal.analysis.log import load_logset      # noqa: PLC0415 — heavy import
    from simoscal.analysis.pulls import detect_pulls   # noqa: PLC0415
    return load_logset, detect_pulls


def _peak(arr: np.ndarray | None, lo: int, hi: int) -> float | None:
    """Peak of the smoothed trace over rows `lo..hi` inclusive."""
    if arr is None:
        return None
    seg = _finite(arr[lo:hi + 1])
    if seg.size < SMOOTH_N:
        return None
    return float(_smooth(seg).max())


def _best_pull(folder):
    """The highest-hp comparable pull in a log folder, plus its (rpm, hp, tq)."""
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
        if pull.rpm_max < REDLINE_RPM:
            continue
        reached_redline = True
        lf = by_name[pull.file]
        hp_col = lf.channel("calc_hp")
        hp = _peak(hp_col, pull.start_row, pull.end_row)
        if hp is None:
            continue
        if best is None or hp > best[0].hp:
            tq_col = _raw_column(lf.path, "Calc TQ (nm)")
            if tq_col is not None and tq_col.size < lf.n_rows:
                tq_col = None                    # misaligned; drop rather than mis-slice
            peak = RevPeak(
                rev=folder.name.split("_")[-1],
                hp=hp,
                tq=_peak(tq_col, pull.start_row, pull.end_row),
                boost=_peak(lf.channel("boost"), pull.start_row, pull.end_row),
                rpm_max=pull.rpm_max,
                gear=pull.gear,
                log=lf.name,
            )
            sl = slice(pull.start_row, pull.end_row + 1)
            trace = (
                np.asarray(lf.channel("rpm")[sl], dtype=float),
                np.asarray(hp_col[sl], dtype=float),
                np.asarray(tq_col[sl], dtype=float) if tq_col is not None else None,
            )
            best = (peak, trace)

    if best is None:
        if not saw_pull:
            reason = "no WOT pulls detected"
        elif not reached_redline:
            reason = f"no gear-{MIN_GEAR}-or-higher pull reaching {REDLINE_RPM:.0f} rpm"
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
    curve: tuple[list[float], list[float], list[float]] | None = None

    for folder in folders:
        best, reason = _best_pull(folder)
        rev = folder.name.split("_")[-1]
        if best is None:
            excluded.append({"rev": rev, "reason": reason})
            continue
        peak, trace = best
        revisions.append(peak)
        if rev == HEADLINE_REV:
            curve = _curve(trace)

    if not revisions:
        raise SystemExit("no comparable WOT pulls found in any Logs/BasicsGuide_R* folder")
    if curve is None:
        raise SystemExit(
            f"the headline revision {HEADLINE_REV} has no comparable pull "
            f"(excluded: {excluded}) — point HEADLINE_REV at a revision that does"
        )
    return HookData(revisions=revisions, excluded=excluded,
                    curve_rpm=curve[0], curve_hp=curve[1], curve_tq=curve[2])


@lru_cache(maxsize=1)
def hook_data() -> HookData:
    """The hook's figures, cached on disk between builds."""
    if CACHE.is_file():
        raw = json.loads(CACHE.read_text())
        return HookData(
            revisions=[RevPeak(**r) for r in raw["revisions"]],
            excluded=raw["excluded"],
            curve_rpm=raw["curve_rpm"], curve_hp=raw["curve_hp"], curve_tq=raw["curve_tq"],
        )
    data = _derive()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(
        {"revisions": [asdict(r) for r in data.revisions], "excluded": data.excluded,
         "curve_rpm": data.curve_rpm, "curve_hp": data.curve_hp, "curve_tq": data.curve_tq},
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
