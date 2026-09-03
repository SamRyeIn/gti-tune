"""
Stage 5: what the Cobb logs actually say about EQT's knock behaviour and
fuelling -- the evidence for whether EQT bought its timing advance by
desensitising knock detection, or by running richer.

This exists because the first version of
`knowledge/eqt-s2-timing-reverse-engineering.md` claimed the
`Knock Retard Cylinder N` channels read "identically zero across all 111 k EQT
samples". That was wrong, and wrong in an instructive way: it was measured on
the 10 sessions the map reconstruction used, which are the only sessions
carrying `Air Mass IM Per Stroke`. Knock retard is logged far more widely than
airmass is, so the reconstruction's channel filter had silently thrown away
most of the knock evidence -- including every deep event.

Three things are computed here, each over the widest corpus that supports it:

  1. **Corpus scope.** Every Cobb CSV under `~/Documents/Cars/GTI`, INCLUDING
     the gzipped track logs in `Cobb/Logs/Track/tmp/*.csv.gz` that a plain
     `*.csv` glob misses. Only knock + pedal + manifold pressure + rpm are
     required, so this is a much larger sample than the map fit used. File
     Files are deduplicated by SHA-256 of their decompressed bytes before any
     sample is counted: the backup folders and the gzipped `tmp/` copies hold
     byte-identical repeats of the same recordings, and counting them twice
     would inflate both the sample total and any rate computed from it.

  2. **Per-tune knock at WOT in boost**, keyed off the `Reflash:` field of the
     `AP Info` column. This is the controlled comparison: same car, same ECU,
     same logging channel, different tuner's calibration. `Stage0 v302` is
     Cobb's stock-power map and acts as the reference.

  3. **EQT vs R22 fuelling**, per rpm bin at WOT in boost. R22 comes from the
     SimosTools logs, which report `Lambda` directly; Cobb reports `AFR`, which
     is converted with a gasoline stoichiometric ratio of 14.7. The two logging
     systems are NOT interchangeable for knock *event rate* -- R22's knock
     control was itself modified from R19 onward, so detection sensitivity
     differs -- but the lambda comparison is clean, being commanded fuelling.
"""

import collections
import csv
import glob
import gzip
import hashlib
import io
import os
import re

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- user inputs

OUT_DIR = "/Users/sam/SimosTools/Docs/eqt-timing-re"
COBB_LOG_ROOT = os.path.expanduser("~/Documents/Cars/GTI")
R22_LOG_GLOB = "/Users/sam/SimosTools/Logs/BasicsGuide_R22/simostools-*.csv"

STOICH_AFR = 14.7          # gasoline, for Cobb AFR -> lambda
PEDAL_WOT_PCT = 90.0       # pedal threshold defining WOT
RPM_BINS = [3000, 3500, 4000, 4500, 5000, 5500, 6000, 6600]

KR_COLS = [f"Knock Retard Cylinder {i} (Degrees)" for i in range(1, 5)]
COBB_REQUIRED = KR_COLS + [
    "Accel Pedal Position (%)",
    "Relative Manifold Pressure (psi)",
    "Engine Speed (RPM)",
]

PER_TUNE_CSV = os.path.join(OUT_DIR, "knock_by_tune.csv")
RETARD_HIST_CSV = os.path.join(OUT_DIR, "knock_retard_histogram.csv")
FUELLING_CSV = os.path.join(OUT_DIR, "fuelling_eqt_vs_r22.csv")


def _open(path):
    """Cobb logs are plain CSV; the track `tmp/` copies are gzipped."""
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), errors="replace")
    return open(path, newline="", errors="replace")


def scan_cobb_logs():
    """Per-tune WOT in-boost knock samples across every Cobb log on disk."""
    files = sorted(
        glob.glob(os.path.join(COBB_LOG_ROOT, "**", "*.csv"), recursive=True)
        + glob.glob(os.path.join(COBB_LOG_ROOT, "**", "*.csv.gz"), recursive=True)
    )
    acc = collections.defaultdict(
        lambda: {"files": 0, "retard": [], "lambda": [], "rpm": []}
    )
    seen_digests = set()
    for path in files:
        try:
            with (gzip.open(path, "rb") if path.endswith(".gz") else open(path, "rb")) as raw:
                digest = hashlib.sha256(raw.read()).hexdigest()
        except OSError:
            continue
        if digest in seen_digests:
            continue                      # byte-identical repeat of a file already counted
        seen_digests.add(digest)
        try:
            fh = _open(path)
        except OSError:
            continue
        with fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            if not all(c in cols for c in COBB_REQUIRED):
                continue
            ap_info = next((c for c in cols if c.startswith("AP Info")), "")
            match = re.search(r"Reflash:\s*([^\]]*?)\.ptm", ap_info)
            tune = match.group(1).strip() if match else "unknown"
            has_afr = "AFR (AFR)" in cols
            acc[tune]["files"] += 1
            for row in reader:
                try:
                    pedal = float(row["Accel Pedal Position (%)"])
                    relmap = float(row["Relative Manifold Pressure (psi)"])
                    if not (pedal > PEDAL_WOT_PCT and relmap > 0):
                        continue
                    deepest = min(float(row[c]) for c in KR_COLS)
                    rpm = float(row["Engine Speed (RPM)"])
                except (TypeError, ValueError):
                    continue
                acc[tune]["retard"].append(deepest)
                acc[tune]["rpm"].append(rpm)
                if has_afr:
                    try:
                        acc[tune]["lambda"].append(float(row["AFR (AFR)"]) / STOICH_AFR)
                    except (TypeError, ValueError):
                        pass
    return acc


def load_r22():
    """R22 SimosTools logs, WOT in boost."""
    frames = []
    for path in sorted(glob.glob(R22_LOG_GLOB)):
        frames.append(pd.read_csv(path, low_memory=False))
    df = pd.concat(frames, ignore_index=True)
    for col in ("Pedal Pos (%)", "Boost (psi)", "Engine Speed (rpm)", "Lambda (l)",
                "Lambda SP (l)", "Airmass (g/stk)", "IAT (°C)"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    knock = df[[f"Knock Cyl {i} (°)" for i in range(1, 5)]].apply(
        pd.to_numeric, errors="coerce")
    df["deepest_knock"] = knock.min(axis=1)
    return df[(df["Pedal Pos (%)"] > PEDAL_WOT_PCT) & (df["Boost (psi)"] > 0)]


def main():
    acc = scan_cobb_logs()

    # -- 1. per-tune summary -------------------------------------------------
    rows = []
    for tune, d in sorted(acc.items(), key=lambda kv: -len(kv[1]["retard"])):
        retard = np.asarray(d["retard"])
        if retard.size == 0:
            continue
        rows.append({
            "tune": tune,
            "unique_files": d["files"],
            "wot_in_boost_samples": retard.size,
            "median_lambda": np.median(d["lambda"]) if d["lambda"] else np.nan,
            "knock_pct_of_wot": 100.0 * (retard < 0).mean(),
            "deepest_retard_deg": retard.min(),
            "samples_deeper_than_3deg": int((retard <= -3.0).sum()),
        })
    per_tune = pd.DataFrame(rows)
    per_tune.to_csv(PER_TUNE_CSV, index=False)
    print("\n=== WOT in boost, per tune (same car, same logging channel) ===")
    print(per_tune.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # -- 2. EQT retard histogram --------------------------------------------
    eqt_key = next((t for t in acc if t.startswith("EQT - Stage 2 91")), None)
    hist = pd.DataFrame()
    if eqt_key:
        retard = np.asarray(acc[eqt_key]["retard"])
        counts = collections.Counter(np.round(retard[retard < 0], 3))
        hist = pd.DataFrame(
            {"retard_deg": sorted(counts), "lsb": [v / 0.375 for v in sorted(counts)],
             "n_samples": [counts[v] for v in sorted(counts)]})
        hist.to_csv(RETARD_HIST_CSV, index=False)
        print(f"\n=== {eqt_key}: knock-retard histogram (WOT in boost) ===")
        print(hist.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    # -- 3. fuelling, EQT vs R22, per rpm bin --------------------------------
    r22 = load_r22()
    eqt_rpm = np.asarray(acc[eqt_key]["rpm"]) if eqt_key else np.array([])
    eqt_ret = np.asarray(acc[eqt_key]["retard"]) if eqt_key else np.array([])
    eqt_lam = np.asarray(acc[eqt_key]["lambda"]) if eqt_key else np.array([])
    # lambda is only present on the subset of files carrying AFR; rebuild that
    # subset's rpm alignment by rescanning is unnecessary -- report lambda only
    # where the arrays line up, otherwise leave NaN.
    lam_aligned = eqt_lam if eqt_lam.size == eqt_rpm.size else None

    rows = []
    for lo, hi in zip(RPM_BINS[:-1], RPM_BINS[1:]):
        e = (eqt_rpm >= lo) & (eqt_rpm < hi)
        r = (r22["Engine Speed (rpm)"] >= lo) & (r22["Engine Speed (rpm)"] < hi)
        if e.sum() < 20 or r.sum() < 20:
            continue
        rows.append({
            "rpm_lo": lo, "rpm_hi": hi,
            "eqt_n": int(e.sum()),
            "eqt_lambda": np.median(lam_aligned[e]) if lam_aligned is not None else np.nan,
            "eqt_knock_pct": 100.0 * (eqt_ret[e] < 0).mean(),
            "eqt_deepest": eqt_ret[e].min(),
            "r22_n": int(r.sum()),
            "r22_lambda": r22.loc[r, "Lambda (l)"].median(),
            "r22_lambda_sp": r22.loc[r, "Lambda SP (l)"].median(),
            "r22_knock_pct": 100.0 * (r22.loc[r, "deepest_knock"] < 0).mean(),
            "r22_deepest": r22.loc[r, "deepest_knock"].min(),
        })
    fuelling = pd.DataFrame(rows)
    fuelling.to_csv(FUELLING_CSV, index=False)
    print("\n=== Fuelling and knock by rpm bin, WOT in boost ===")
    print(fuelling.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nR22 overall WOT median lambda: {r22['Lambda (l)'].median():.3f} "
          f"(setpoint {r22['Lambda SP (l)'].median():.3f})")
    print(f"wrote {PER_TUNE_CSV}\n      {RETARD_HIST_CSV}\n      {FUELLING_CSV}")


if __name__ == "__main__":
    main()
