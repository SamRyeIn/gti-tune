"""Price the VP Octanium dose: the same calibration on plain 92 versus dosed.

Every revision since R20 has assumed the octane dose is worth its cost, and no
session had ever measured it -- R20's own logs are entirely octane-map, so they
compare a dosed offset map against a *plain-92* base map and confound the fuel
with the timing. The comparison that isolates the fuel already existed in the
archive and simply had not been run:

* **plain 92, base timing** -- the whole R19 session (R20 introduced the dose).
* **dosed, base timing** -- R22's slot 3 pulls.

Those two are the *same calibration*. `slot_attribution` verifies R22 slot 3's
`PUT setpoint` -- map slot boost cap is byte-identical to R20 slot 4's and its
`Spark modifier` -- map slot ignition offset grid is all-zero, and the knock
fast-loop (`IP_IGA_DEC_KNK` -- Spark retard at recognised knocking) has been
unchanged since R19, so the retard integral is comparable across the two.

This script also fingerprints the R19 and R20 sessions by reconstructed ignition
offset, which is how "R20 contains no base-timing control" is established rather
than assumed.

**Read the null carefully.** Base timing is not knock-limited over most of the
range -- plain-92 retard sits at 1-7 deg-s/min outside the 3000-3500 zone -- so
octane has little room to show a benefit here. A null means the dose does nothing
for the map that is driven every day; it does not prove the dose does nothing on
the offset maps, which is the case it was bought for. That case cannot be tested
safely: slot 5 on plain 92 is a known-knock configuration this project forbids.

Run:  Code/.venv/bin/python Logs/BasicsGuide_R22/analyze_octane_value.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LOGS = HERE.parent
sys.path.insert(0, str(LOGS / "BasicsGuide_R19"))
sys.path.insert(0, str(HERE))

from analyze_r19_validation import (  # noqa: E402
    R19_TAGS, SAMPLE_S, load, load_tagged, loaded_mask,
)
from slot_attribution import attribute  # noqa: E402

KNOCK_KEYS = ("knock_1", "knock_2", "knock_3", "knock_4")

BANDS = ((3000, 3500), (3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6600), (3000, 6600))

#: Window used to fingerprint a log's slot by delivered ignition offset: high
#: enough in rpm and load that the `Spark modifier` rows are actually in play.
FINGERPRINT_RPM = (4700, 5800)
FINGERPRINT_AIRMASS_MIN = 1.35   # g/stk

#: Below this reconstructed offset a log is base timing; at or above it, an
#: octane map. The two populations are separated by ~3 deg, so the exact
#: threshold does not matter.
BASE_TIMING_MAX_DEG = 0.5

BOOTSTRAP_N = 20000


def fingerprint(folder: Path) -> list[tuple[str, float, int]]:
    """Reconstructed ignition offset per log, for classifying a whole session."""
    out = []
    for path in sorted(folder.glob("simostools-*.csv")):
        d = load(path)
        m = (loaded_mask(d)
             & (d["rpm"] >= FINGERPRINT_RPM[0]) & (d["rpm"] < FINGERPRINT_RPM[1])
             & (d["airmass"] >= FINGERPRINT_AIRMASS_MIN))
        if m.sum() < 5:
            out.append((path.name[-12:-4], float("nan"), int(m.sum())))
            continue
        knock = np.nanmin(np.vstack([d[k] for k in KNOCK_KEYS]), axis=0)
        offset = float(np.median((d["ign"] - d["ign_table"] - knock)[m]))
        out.append((path.name[-12:-4], offset, int(m.sum())))
    return out


def _integral(data, window, lo: float, hi: float):
    m = loaded_mask(data) & (data["rpm"] >= lo) & (data["rpm"] < hi)
    if window is not None:
        rows = np.arange(data["rpm"].size)
        m = m & (rows >= window[0]) & (rows <= window[1])
    if not m.sum():
        return None
    total = float(np.sum([np.clip(-data[k][m], 0.0, None) for k in KNOCK_KEYS]))
    return total * SAMPLE_S, float(m.sum()) * SAMPLE_S


def _peak(folder: str, name: str, window) -> tuple[float, float] | None:
    rows = list(csv.DictReader(
        open(LOGS / folder / name, encoding="utf-8-sig")))
    chan = lambda c: np.array([float(r[c]) for r in rows])
    idx = np.arange(len(rows))
    m = ((np.rint(chan("Gear (gear)")) == 3) & (chan("Pedal Pos (%)") >= 90.0)
         & (chan("Engine Speed (rpm)") > 3000.0))
    if window is not None:
        m &= (idx >= window[0]) & (idx <= window[1])
    if m.sum() < 20:
        return None
    return (float(np.percentile(chan("Calc HP (hp)")[m], 99.5)),
            float(np.percentile(chan("Airmass (g/stk)")[m] * 1000.0, 99.5)))


def main() -> int:
    print("## Session fingerprints — which map each log actually ran\n")
    for folder in ("BasicsGuide_R19", "BasicsGuide_R20"):
        print(f"  {folder}:")
        for tag, offset, n in fingerprint(LOGS / folder):
            if not np.isfinite(offset):
                print(f"    {tag}  (too few loaded samples)")
                continue
            kind = ("BASE timing" if offset < BASE_TIMING_MAX_DEG else "OCTANE map")
            print(f"    {tag}  offset {offset:+.2f} deg  n={n:3d}  -> {kind}")
    print("\n  R20 holds no base-timing control, so the dosed base-timing slot is\n"
          "  R22 slot 3 alone.\n")

    plain = [(f"R19/{tag}", d, None)
             for tag, d in load_tagged(LOGS / "BasicsGuide_R19", R19_TAGS)]
    dosed = [(f"R22/p{p.index}",
              load(HERE / f"{p.file}.csv"),
              (p.start_row - 50, p.end_row + 50))
             for p in attribute() if p.slot == 3]

    rng = np.random.default_rng(0)

    def rate(vals):
        return (60.0 * sum(v[0] for v in vals) / sum(v[1] for v in vals)
                if vals else float("nan"))

    print("## Knock — base-timing calibration, plain 92 vs dosed\n")
    print("Degree-seconds of per-cylinder retard per loaded WOT minute.\n")
    print("| Band (rpm) | plain 92 | dosed | dosed − plain | 95% CI | P(dosed worse) |")
    print("|------------|----------|-------|---------------|--------|----------------|")
    for lo, hi in BANDS:
        a = [v for v in (_integral(d, w, lo, hi) for _n, d, w in plain) if v]
        b = [v for v in (_integral(d, w, lo, hi) for _n, d, w in dosed) if v]
        if not (a and b):
            continue
        diffs = np.array([
            rate([b[i] for i in rng.integers(0, len(b), len(b))])
            - rate([a[i] for i in rng.integers(0, len(a), len(a))])
            for _ in range(BOOTSTRAP_N)
        ])
        print(f"| {lo}-{hi} | {rate(a):.2f} | {rate(b):.2f} | "
              f"{rate(b) - rate(a):+.2f} | [{np.percentile(diffs, 2.5):+.2f}, "
              f"{np.percentile(diffs, 97.5):+.2f}] | {np.mean(diffs > 0):.3f} |")

    print("\n## Power and conditions\n")
    rows = []
    for label, folder, entries in (
        ("plain 92 (R19)", "BasicsGuide_R19",
         [(f"simostools-{'2026_08_28'}-{t}.csv", None) for t in R19_TAGS]),
        ("dosed (R22 slot 3)", "BasicsGuide_R22",
         [(f"{p.file}.csv", (p.start_row, p.end_row))
          for p in attribute() if p.slot == 3]),
    ):
        peaks = []
        for name, window in entries:
            path = LOGS / folder / name
            if not path.exists():                      # R19 filenames carry a date
                matches = list((LOGS / folder).glob(f"simostools-*{name[-12:-4]}.csv"))
                if not matches:
                    continue
                name = matches[0].name
            got = _peak(folder, name, window)
            if got:
                peaks.append(got)
        hp = np.array([p[0] for p in peaks])
        air = np.array([p[1] for p in peaks])
        rows.append((label, hp, air))
        print(f"  {label}: peak HP {hp.mean():.1f} ± {hp.std(ddof=1):.2f} "
              f"(n={hp.size}) | peak airmass {air.mean():.0f} mg/stk")
    (_l0, h0, _a0), (_l1, h1, _a1) = rows
    se = float(np.sqrt(h0.var(ddof=1) / h0.size + h1.var(ddof=1) / h1.size))
    print(f"  difference: {h1.mean() - h0.mean():+.2f} hp (se {se:.2f}) "
          f"-> {abs(h1.mean() - h0.mean()) / se:.2f} se")

    for label, folder, entries in (
        ("plain 92 (R19)", "BasicsGuide_R19", plain),
        ("dosed (R22 slot 3)", "BasicsGuide_R22", dosed),
    ):
        iat, amb, exposure = [], [], 0.0
        for _n, d, w in entries:
            m = loaded_mask(d)
            if w is not None:
                r = np.arange(d["rpm"].size)
                m = m & (r >= w[0]) & (r <= w[1])
            iat.append(d["iat"][m]); amb.append(d["ambient_temp"][m])
            exposure += float(m.sum()) * SAMPLE_S
        print(f"  {label}: {len(entries)} pulls, {exposure:.1f}s loaded WOT | "
              f"IAT {np.concatenate(iat).mean():.1f} C | "
              f"ambient {np.concatenate(amb).mean():.1f} C")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
