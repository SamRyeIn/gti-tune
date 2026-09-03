"""
Stage 1 of the EQT Stage 2 base-timing reverse-engineering pipeline.

Scans every Cobb Accessport datalog on disk, identifies which ones were recorded
on the target tune AND carry the channel set needed to invert the ECU's base
ignition lookup, deduplicates them by content hash, and emits:

  log_inventory.csv  - one row per candidate CSV, INCLUDED / EXCLUDED + reason
  samples.parquet    - the concatenated, filtered sample table

The channel we are inverting is `Ignition Table Output (Degrees)`, which is the
ECU's blended output of the base ignition angle maps

    `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]`  -- Basic Ignition Angle,
        VVL 0, low port-flap position, intake cam index i, exhaust cam index e
        (f(RPM, airmass), 16x16, uint8, deg = (raw - 95) / 2.666667)

read BEFORE knock control subtracts anything (`Knock Retard Cylinder N`) and
before the Accessport's own `COBB Spark Reduction` intervenes.

Read-only on every source log.
"""

import csv
import hashlib
import os
import re
import sys

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- user inputs

LOG_ROOTS = [
    "/Users/sam/Documents/Cars/GTI/Cobb/Logs",
    "/Users/sam/SimosTools/References",
]
OUT_DIR = "/Users/sam/SimosTools/Docs/eqt-timing-re"

TARGET_TUNE = "EQT - Stage 2 91 v2.52 - LC TC"
BASELINE_TUNE = "Stage0 v302"

# Channels the inversion cannot proceed without.
CH_RPM = "Engine Speed (RPM)"
CH_IGA_TAB = "Ignition Table Output (Degrees)"
CH_IGA_FIN = "Ignition Timing Final (Degrees)"
CH_MAF = "Air Mass IM Per Stroke (mg/stk)"
CH_MAF_SP = "Air Mass Per Stroke SP (mg/stk)"
CH_CAM_IN = "Intake Cam Position (Degrees)"
CH_CAM_EX = "Exhaust Cam Position (Degrees)"
CH_VLS = "Valve Lift State  (-)"
CH_PED = "Accel Pedal Position (%)"
CH_IAT = "IAT (F)"
CH_TCO = "Coolant Temp. (F)"
CH_AFR = "AFR (AFR)"
CH_AFR_SP = "AFR Set Point (AFR)"
CH_GEAR = "Current Gear (-)"
CH_TIME = "Time (sec)"
CH_COBB_RED = "COBB Spark Reduction (Degrees)"
CH_KR = [f"Knock Retard Cylinder {i} (Degrees)" for i in (1, 2, 3, 4)]
CH_BOOST = "Boost Press. (psi)"
CH_RELMAP = "Relative Manifold Pressure (psi)"
CH_AMB_P = "Ambient Pressure (psi)"

REQUIRED = [CH_RPM, CH_IGA_TAB, CH_MAF, CH_CAM_IN, CH_CAM_EX, CH_VLS, CH_PED]
OPTIONAL = [CH_IGA_FIN, CH_MAF_SP, CH_IAT, CH_TCO, CH_AFR, CH_AFR_SP, CH_GEAR,
            CH_TIME, CH_COBB_RED, CH_BOOST, CH_RELMAP, CH_AMB_P] + CH_KR

# Physical plausibility gates. A sample outside any of these is dropped as a
# transport glitch rather than trusted -- the Accessport drops frames.
RPM_MIN, RPM_MAX = 400.0, 7200.0
MAF_MIN, MAF_MAX = 30.0, 2778.0        # 2778 = top of the XDF airmass axis
IGA_MIN, IGA_MAX = -35.625, 60.0       # the uint8 store's full physical range
CAM_IN_MIN, CAM_IN_MAX = -60.0, 60.0
CAM_EX_MIN, CAM_EX_MAX = -60.0, 60.0


def header_of(path):
    with open(path, errors="replace") as fh:
        line = fh.readline()
    if not line.strip():
        return []
    return next(csv.reader([line.rstrip("\n")]))


def tune_of(cols):
    ap = next((c for c in cols if c.startswith("AP Info")), "")
    m = re.search(r"Reflash:\s*(.*?)\.ptm", ap)
    return m.group(1).strip() if m else "(no AP Info)"


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def discover():
    out = []
    for root in LOG_ROOTS:
        for dirpath, _, names in os.walk(root):
            for n in names:
                if n.lower().endswith(".csv"):
                    out.append(os.path.join(dirpath, n))
    return sorted(out)


def row_signatures(path, cols):
    """A set of per-row fingerprints, used to detect a log that is a split part
    (or re-export) of another log rather than an independent recording. Byte
    hashing does not catch these: `Session1.csv` and its `_Part1`/`_Part2`
    halves hold the same samples in different files."""
    use = [c for c in (CH_TIME, CH_RPM, CH_IGA_TAB, CH_MAF, CH_CAM_IN) if c in cols]
    df = pd.read_csv(path, usecols=use, low_memory=False)
    key = df.astype(str).agg("|".join, axis=1)
    return set(pd.util.hash_pandas_object(key, index=False).to_numpy().tolist())


def build_inventory():
    rows = []
    seen_hash = {}
    for path in discover():
        cols = header_of(path)
        rec = {
            "path": path,
            "size_mb": round(os.path.getsize(path) / 1e6, 3),
            "n_cols": len(cols),
            "tune": tune_of(cols) if cols else "(unreadable)",
            "has_ign": CH_IGA_TAB in cols,
            "has_airmass": CH_MAF in cols,
            "has_cams": CH_CAM_IN in cols and CH_CAM_EX in cols,
            "has_vls": CH_VLS in cols,
            "has_pedal": CH_PED in cols,
            "sha256": "",
            "status": "",
            "reason": "",
        }
        missing = [c for c in REQUIRED if c not in cols]
        if rec["tune"] not in (TARGET_TUNE, BASELINE_TUNE):
            rec["status"], rec["reason"] = "EXCLUDED", f"tune is {rec['tune']!r}, not the target"
        elif missing:
            rec["status"] = "EXCLUDED"
            rec["reason"] = "missing channel(s): " + "; ".join(missing)
        else:
            rec["sha256"] = file_hash(path)
            first = seen_hash.get(rec["sha256"])
            if first is not None:
                rec["status"] = "EXCLUDED"
                rec["reason"] = f"byte-identical duplicate of {first}"
            else:
                seen_hash[rec["sha256"]] = path
                role = "target" if rec["tune"] == TARGET_TUNE else "baseline"
                rec["status"] = "INCLUDED"
                rec["reason"] = f"full channel set, unique content, {role} tune"
        rows.append(rec)
    inv = pd.DataFrame(rows)

    # Second dedup pass: content-level containment. Keep the longest recording
    # first; drop any later log whose samples are already >= 99% covered by the
    # ones kept, which is what a split part or a re-export looks like.
    cand = inv[inv["status"] == "INCLUDED"].copy()
    sigs = {p: row_signatures(p, header_of(p)) for p in cand["path"]}
    cand["n_sig"] = cand["path"].map(lambda p: len(sigs[p]))
    kept_union, kept_paths = set(), []
    for path in cand.sort_values("n_sig", ascending=False)["path"]:
        sig = sigs[path]
        covered = len(sig & kept_union) / max(len(sig), 1)
        if covered >= 0.99 and kept_paths:
            owner = max(kept_paths, key=lambda q: len(sigs[q] & sig))
            inv.loc[inv["path"] == path, "status"] = "EXCLUDED"
            inv.loc[inv["path"] == path, "reason"] = (
                f"{covered:.1%} of its samples already present in {os.path.basename(owner)}"
                " (split part / re-export of the same recording)")
        else:
            kept_union |= sig
            kept_paths.append(path)
    inv["n_unique_samples"] = inv["path"].map(lambda p: len(sigs.get(p, ())) or "")
    return inv


def _num(df, col):
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def load_one(path):
    cols = header_of(path)
    use = [c for c in REQUIRED + OPTIONAL if c in cols]
    df = pd.read_csv(path, usecols=use, low_memory=False)
    out = pd.DataFrame(index=df.index)
    out["rpm"] = _num(df, CH_RPM)
    out["iga_tab"] = _num(df, CH_IGA_TAB)
    out["iga_fin"] = _num(df, CH_IGA_FIN)
    out["maf"] = _num(df, CH_MAF)
    out["maf_sp"] = _num(df, CH_MAF_SP)
    out["cam_in"] = _num(df, CH_CAM_IN)
    out["cam_ex"] = _num(df, CH_CAM_EX)
    out["vls"] = _num(df, CH_VLS)
    out["pedal"] = _num(df, CH_PED)
    out["iat_f"] = _num(df, CH_IAT)
    out["tco_f"] = _num(df, CH_TCO)
    out["afr"] = _num(df, CH_AFR)
    out["afr_sp"] = _num(df, CH_AFR_SP)
    out["gear"] = _num(df, CH_GEAR)
    out["t"] = _num(df, CH_TIME)
    out["cobb_red"] = _num(df, CH_COBB_RED)
    out["boost_psi"] = _num(df, CH_BOOST)
    out["relmap_psi"] = _num(df, CH_RELMAP)
    out["amb_psi"] = _num(df, CH_AMB_P)
    kr = pd.concat([_num(df, c) for c in CH_KR], axis=1)
    out["kr_max"] = kr.max(axis=1) if kr.shape[1] else np.nan
    out["iat_c"] = (out["iat_f"] - 32.0) * 5.0 / 9.0
    out["tco_c"] = (out["tco_f"] - 32.0) * 5.0 / 9.0
    out["src"] = os.path.relpath(path, "/Users/sam")
    return out


def clean(df):
    """Drop transport glitches. Returns (kept, reject_reason_counts)."""
    reasons = {}

    def gate(mask, name):
        reasons[name] = int((~mask).sum())
        return mask

    ok = gate(df[["rpm", "iga_tab", "maf", "cam_in", "cam_ex", "vls"]].notna().all(axis=1),
              "null in a required channel")
    ok &= gate(df["rpm"].between(RPM_MIN, RPM_MAX), "rpm out of range")
    ok &= gate(df["maf"].between(MAF_MIN, MAF_MAX), "airmass out of range")
    ok &= gate(df["iga_tab"].between(IGA_MIN, IGA_MAX), "iga_tab outside uint8 store range")
    ok &= gate(df["cam_in"].between(CAM_IN_MIN, CAM_IN_MAX), "intake cam out of range")
    ok &= gate(df["cam_ex"].between(CAM_EX_MIN, CAM_EX_MAX), "exhaust cam out of range")
    return df[ok].copy(), reasons


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    inv = build_inventory()
    inv_path = os.path.join(OUT_DIR, "log_inventory.csv")
    inv.to_csv(inv_path, index=False)

    inc = inv[inv["status"] == "INCLUDED"]
    print(f"inventory: {len(inv)} candidate CSVs -> {len(inc)} INCLUDED")
    print(inv.groupby(["status", "tune"]).size().to_string())
    print(f"\n  target-tune INCLUDED  : {(inc['tune'] == TARGET_TUNE).sum()}")
    print(f"  baseline-tune INCLUDED: {(inc['tune'] == BASELINE_TUNE).sum()}")

    frames = []
    for path, tune in zip(inc["path"], inc["tune"]):
        d = load_one(path)
        d["tune"] = tune
        frames.append(d)
        print(f"  read {len(d):8d} rows  {os.path.relpath(path, '/Users/sam')}")
    raw = pd.concat(frames, ignore_index=True)

    kept, reasons = clean(raw)
    print(f"\nraw rows {len(raw)} -> clean {len(kept)}  ({len(raw)-len(kept)} dropped)")
    for k, v in reasons.items():
        if v:
            print(f"  {v:8d}  {k}")
    print("\nby tune:")
    print(kept.groupby("tune").size().to_string())

    out = os.path.join(OUT_DIR, "samples.parquet")
    kept.to_parquet(out, index=False)
    print(f"\nwrote {out}  ({os.path.getsize(out)/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
