"""
Size the R15 wastegate feedforward walk-back from the R14 logs.

`log_review.md` Medium 2: slot 4 under-delivers up to 1.5 psi at 4000–4500 rpm
while `WG I Value` climbs to +17.8 %, i.e. `IP_FAC_BPA_SP[0]` / `[1]` — Wastegate
Position Feedforward, VVL 0 / VVL 1 are too open at high flow for the R14 slot-4
target. The cells carrying that shortfall are exactly the six R08 lowered, so
R15 walks part of R08 back.

The sizing is a *linear* problem and is solved as one rather than guessed:
commanded feedforward position is a bilinear-weighted sum of table cells, so the
position change in an rpm band is `sum_i (mean weight of cell i in that band) *
(delta on cell i)`. This builds that design matrix from the logged operating
points and solves a bounded least squares for the deltas.

Bounds encode the two guardrails that matter:

* **Never above the R07 value** — R08's own deltas are the upper bound, so R15
  can at most undo R08 in a cell, never invent a more-closed feedforward than
  this lineage has ever run.
* **Never negative** — R15 only walks back; opening a cell further is a
  different finding's job.

The Int 0.75 rows are excluded entirely: they carry the upshift-spike load
(High 1), which cannot be sized from a railed sensor.

Usage:
    python3 size_r15_wastegate.py
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

#: Clean 3rd-gear pulls only — no TC intervention, no mixed-gear content.
CLEAN = ["12_00_06", "12_02_12", "12_06_23", "12_07_51"]
BANDS = [(3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6500)]

#: Guide rule used to size R05 and R08: ~0.05 wastegate position per psi.
WG_POS_PER_PSI = 0.05
HPA_PER_PSI = 68.95
KPA_PER_PSI = HPA_PER_PSI / 10.0
#: R08 applied ~70 % of the raw rule as a deliberately conservative second pass.
#: The same restraint applies here, and harder — this direction adds airmass to a
#: fuel system already at 96-98 % HPFP effective volume.
CONSERVATISM = 0.70

#: 6000-6500 rpm already tracks at -1.0 kPa, and it shares the Int 1.05/1.25 x
#: Exh 1.40 cells with 5000-6000, which does not. Weighting the on-target band
#: up keeps the solver from pushing a correct band into overshoot to buy a little
#: more elsewhere: it costs ~1.4 kPa across 4500-5500 and halves the predicted
#: redline overshoot (+3.0 -> +1.5 kPa). Don't disturb what is already right.
REDLINE_BAND_WEIGHT = 5.0
REDLINE_RPM = 6000

#: Candidate cells (row = intake flow factor index, col = exhaust). Exactly the
#: six R08 lowered; the value is R08's delta magnitude = the R07 headroom.
R08_DELTAS = {(6, 14): 0.02, (6, 15): 0.02,
              (7, 14): 0.06, (7, 15): 0.04,
              (8, 14): 0.06, (8, 15): 0.04}

CHANNELS = {"rpm": "Engine Speed (rpm)", "pedal": "Pedal Pos (%)",
            "gear": "Gear (gear)", "put": "PUT (kpa)", "put_sp": "PUT SP (kpa)",
            "exh": "Exh Flow Factor ()", "intake": "Intake Flow Fact ()"}


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


def sample_weights(exh, intake, X, Y, shape):
    """Per-sample bilinear weight of every cell — the ECU's own lookup, unrolled."""
    W = np.zeros((len(exh),) + shape)
    for n, (e, i) in enumerate(zip(exh, intake)):
        xi = np.clip(np.interp(e, X, np.arange(len(X))), 0, len(X) - 1)
        yi = np.clip(np.interp(i, Y, np.arange(len(Y))), 0, len(Y) - 1)
        x0, y0 = int(np.floor(xi)), int(np.floor(yi))
        x1, y1 = min(x0 + 1, len(X) - 1), min(y0 + 1, len(Y) - 1)
        fx, fy = xi - x0, yi - y0
        W[n, y0, x0] += (1 - fx) * (1 - fy)
        W[n, y0, x1] += fx * (1 - fy)
        W[n, y1, x0] += (1 - fx) * fy
        W[n, y1, x1] += fx * fy
    return W


def bounded_lsq(A, t, w, hi, iters=200000, step=0.5):
    """min sum_b w_b (A d - t)_b^2  s.t.  0 <= d <= hi. Projected gradient."""
    d = np.zeros(A.shape[1])
    Aw = A * w[:, None]
    for _ in range(iters):
        grad = 2 * Aw.T @ (A @ d - t)
        d = np.clip(d - step * grad, 0.0, hi)
    return d


def main():
    cal = CalFile.open(str(XDF), str(FLASHED_BIN))
    t0 = cal.get("IP_FAC_BPA_SP[0]")
    X = np.asarray(t0.axis_values("x"), dtype=float).ravel()
    Y = np.asarray(t0.axis_values("y"), dtype=float).ravel()
    Z0 = np.asarray(t0.values, dtype=float)
    Z1 = np.asarray(cal.get("IP_FAC_BPA_SP[1]").values, dtype=float)

    rpm, err, exh, intake = [], [], [], []
    for tag in CLEAN:
        d = load(next(LOG_DIR.glob(f"simostools-*{tag}.csv")))
        m = (d["pedal"] >= 90) & (d["gear"] == 3) & (d["rpm"] >= 3000)
        rpm.append(d["rpm"][m])
        err.append(d["put"][m] - d["put_sp"][m])
        exh.append(d["exh"][m])
        intake.append(d["intake"][m])
    rpm, err = np.concatenate(rpm), np.concatenate(err)
    exh, intake = np.concatenate(exh), np.concatenate(intake)
    W = sample_weights(exh, intake, X, Y, Z0.shape)

    cells = sorted(R08_DELTAS)
    hi = np.array([R08_DELTAS[c] for c in cells])

    A, target, counts = [], [], []
    print("Measured shortfall and the position change it implies:\n")
    print(f"  {'band':<12}{'n':>5}{'err kPa':>10}{'short psi':>11}{'raw need':>10}{'target':>9}")
    for lo, hi_rpm in BANDS:
        b = (rpm >= lo) & (rpm < hi_rpm)
        if b.sum() < 5:
            continue
        e = err[b].mean()
        short_psi = -e / KPA_PER_PSI
        raw = short_psi * WG_POS_PER_PSI
        tgt = raw * CONSERVATISM
        A.append([W[b][:, r, c].mean() for r, c in cells])
        target.append(tgt)
        counts.append(b.sum() * (REDLINE_BAND_WEIGHT if lo >= REDLINE_RPM else 1.0))
        print(f"  {str(lo) + '-' + str(hi_rpm):<12}{b.sum():>5}{e:>+10.1f}"
              f"{short_psi:>11.2f}{raw:>+10.3f}{tgt:>+9.3f}")

    A = np.array(A)
    target = np.array(target)
    counts = np.array(counts, dtype=float)
    d = bounded_lsq(A, target, counts / counts.sum(), hi)

    print("\nSolved cell deltas (bounded at the R07 value — never more closed than R07):\n")
    print(f"  {'cell (Int x Exh)':<20}{'now':>8}{'delta':>9}{'R15':>8}{'R07 cap':>10}{'at cap':>8}")
    r15 = {}
    for (r, c), di in zip(cells, d):
        di = round(float(di), 3)
        if di <= 0.0005:
            continue
        r15[(r, c)] = di
        cap = Z0[r, c] + R08_DELTAS[(r, c)]
        print(f"  Int {Y[r]:.2f} x Exh {X[c]:.2f}    {Z0[r, c]:>8.3f}{di:>+9.3f}"
              f"{Z0[r, c] + di:>8.3f}{cap:>10.3f}{'  yes' if abs(Z0[r, c] + di - cap) < 1e-9 else '   no':>8}")

    dvec = np.array([r15.get(c, 0.0) for c in cells])
    print("\nSimulated effect over the logged points (mean commanded position change):\n")
    print(f"  {'band':<12}{'n':>5}{'target':>9}{'achieved':>11}{'~psi back':>11}{'resid kPa':>11}")
    for (lo, hi_rpm), tgt in zip([b for b in BANDS
                                  if ((rpm >= b[0]) & (rpm < b[1])).sum() >= 5], target):
        b = (rpm >= lo) & (rpm < hi_rpm)
        got = float(np.array([W[b][:, r, c].mean() for r, c in cells]) @ dvec)
        psi_back = got / WG_POS_PER_PSI
        resid = err[b].mean() + psi_back * KPA_PER_PSI
        print(f"  {str(lo) + '-' + str(hi_rpm):<12}{b.sum():>5}{tgt:>+9.3f}{got:>+11.3f}"
              f"{psi_back:>+11.2f}{resid:>+11.1f}")

    print("\nWG_DELTAS_R15 for the revision script (row, col) -> delta:")
    print("    WG_DELTAS_R15 = {")
    for (r, c), di in sorted(r15.items()):
        print(f"        ({r}, {c}): +{di:.3f},   # Int {Y[r]:.2f} x Exh {X[c]:.2f}: "
              f"{Z0[r, c]:.3f} -> {Z0[r, c] + di:.3f}")
    print("    }")

    same = np.array_equal(Z0[[r for r, _ in cells], [c for _, c in cells]],
                          Z1[[r for r, _ in cells], [c for _, c in cells]])
    print(f"\nVVL0/VVL1 candidate cells currently identical: {same} "
          f"(deltas are applied to both maps regardless, per lineage convention)")


if __name__ == "__main__":
    main()
