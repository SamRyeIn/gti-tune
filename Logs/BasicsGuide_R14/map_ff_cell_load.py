"""
Map which `IP_FAC_BPA_SP` — Wastegate Position Feedforward cells each R14 finding
actually loads.

Two findings in `log_review.md` want the wastegate moved in opposite directions:
the upshift overboost (High 1) wants cells more open, the steady-state shortfall
(Medium 2) wants them more closed. Whether those are the *same* cells decides
whether the fixes conflict — and the table is indexed on exhaust/intake flow
factor, not rpm, so it cannot be answered by looking at rpm bands.

This accumulates the bilinear interpolation weight each table cell receives over
each finding's samples (the same lookup the ECU runs, verified against logged
`WG Pos Base` in `verify_slot_identity.py`'s sibling check), then reports the
overlap.

Usage:
    python3 map_ff_cell_load.py
"""

import csv
import sys
from pathlib import Path

import numpy as np

LOG_DIR = Path(__file__).resolve().parent
REPO_ROOT = LOG_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "Code"))
from simoscal import CalFile  # noqa: E402

XDF = REPO_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
FLASHED_BIN = (REPO_ROOT / "Tunes" / "TuningBasicsGuide" / "TUNE_Basics_Guide_out"
               / "R14_20260810-111002"
               / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin")

#: The file holding the WOT 3→4 upshift overboost.
UPSHIFT_LOG = "simostools-2026_08_10-12_03_17.csv"
#: Clean 3rd-gear pulls, free of TC intervention and mixed-gear content.
CLEAN = ["12_00_06", "12_02_12", "12_06_23", "12_07_51"]

CHANNELS = {
    "rpm": "Engine Speed (rpm)", "pedal": "Pedal Pos (%)", "gear": "Gear (gear)",
    "put": "PUT (kpa)", "put_sp": "PUT SP (kpa)",
    "exh": "Exh Flow Factor ()", "intake": "Intake Flow Fact ()",
}


def load(path):
    out = {k: [] for k in CHANNELS}
    for row in csv.DictReader(open(path)):
        try:
            vals = {k: float(row[c]) for k, c in CHANNELS.items()}
        except (ValueError, KeyError, TypeError):
            continue
        for k, v in vals.items():
            out[k].append(v)
    return {k: np.asarray(v) for k, v in out.items()}


def cell_weights(exh, intake, X, Y, shape):
    """Bilinear weight each cell receives, summed over samples and normalised."""
    W = np.zeros(shape)
    for e, i in zip(exh, intake):
        xi = np.clip(np.interp(e, X, np.arange(len(X))), 0, len(X) - 1)
        yi = np.clip(np.interp(i, Y, np.arange(len(Y))), 0, len(Y) - 1)
        x0, y0 = int(np.floor(xi)), int(np.floor(yi))
        x1, y1 = min(x0 + 1, len(X) - 1), min(y0 + 1, len(Y) - 1)
        fx, fy = xi - x0, yi - y0
        W[y0, x0] += (1 - fx) * (1 - fy)
        W[y0, x1] += fx * (1 - fy)
        W[y1, x0] += (1 - fx) * fy
        W[y1, x1] += fx * fy
    return W / W.sum()


def report(name, W, X, Y, Z, n_top=6):
    print(f"\n{name}")
    order = np.dstack(np.unravel_index(np.argsort(-W, axis=None), W.shape))[0]
    for r, c in order[:n_top]:
        print(f"   Int {Y[r]:.2f} x Exh {X[c]:.2f}  (row {r:>2}, col {c:>2})  "
              f"weight {W[r, c] * 100:5.1f}%   current cell {Z[r, c]:.3f}")


def main():
    cal = CalFile.open(str(XDF), str(FLASHED_BIN))
    t = cal.get("IP_FAC_BPA_SP[0]")
    X = np.asarray(t.axis_values("x"), dtype=float).ravel()
    Y = np.asarray(t.axis_values("y"), dtype=float).ravel()
    Z = np.asarray(t.values, dtype=float)

    d = load(LOG_DIR / UPSHIFT_LOG)
    spike = (d["gear"] == 4) & (d["pedal"] >= 90) & ((d["put"] - d["put_sp"]) > 10)
    W_spike = cell_weights(d["exh"][spike], d["intake"][spike], X, Y, Z.shape)

    exh, intake = [], []
    for tag in CLEAN:
        dd = load(next(LOG_DIR.glob(f"simostools-*{tag}.csv")))
        w = ((dd["pedal"] >= 90) & (dd["gear"] == 3)
             & (dd["rpm"] >= 3500) & (dd["rpm"] < 5500))
        exh.append(dd["exh"][w])
        intake.append(dd["intake"][w])
    n_steady = sum(len(a) for a in exh)
    W_steady = cell_weights(np.concatenate(exh), np.concatenate(intake), X, Y, Z.shape)

    report(f"Cells the UPSHIFT SPIKE loads, n={spike.sum()} (want lower / more open):",
           W_spike, X, Y, Z)
    report(f"Cells the STEADY-STATE SHORTFALL loads, n={n_steady} (want higher / more closed):",
           W_steady, X, Y, Z)

    overlap = np.minimum(W_spike, W_steady).sum()
    print(f"\nShared-cell overlap: {overlap * 100:.1f}% of each population's table load.")
    print("Low overlap means the two fixes are largely separable — the intake flow "
          "factor row is the discriminator, as it was in R08.")


if __name__ == "__main__":
    main()
