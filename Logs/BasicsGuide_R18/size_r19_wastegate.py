"""
Size the R19 wastegate feedforward closing from the R18 logs.

`log_review.md` Medium — the boost shortfall is confirmed as a carry-over:
`IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure actuator setpoint
under-commands from 5000 rpm up, leaving the closed loop to carry 9.6-13.0 %
integral to hold a 4.9-7.8 kPa shortfall. It reproduces across three sessions
and both thermal conditions, so it is a feedforward gap and not a transient.

This is the same solve as `Logs/BasicsGuide_R14/size_r15_wastegate.py`, run in
the opposite direction. Commanded feedforward position is a bilinear-weighted
sum of table cells, so the position change in an rpm band is
`sum_i (mean weight of cell i in that band) * (delta on cell i)`. This builds
that design matrix from the logged operating points and solves a bounded least
squares. R15 opened cells back toward R07; R19 closes cells back toward stock.

The model is validated before it is used: the bilinear lookup is replayed
against the logged `WG Pos Base (%)` and must agree to better than 0.25 points
RMS, or the script raises. On these logs it agrees to 0.05-0.08.

Bounds and band targets encode the guardrails that matter:

* **Never more closed than stock.** Every candidate cell was *opened* from the
  factory value by R05 and R08; R19 may at most give part of that back. The
  factory calibration is the most closed this cell has ever been, on this or
  any prior revision, so it is the honest ceiling.
* **Never negative.** R19 only closes; opening a cell further is a different
  finding's job.
* **4500-5000 rpm is a hold band, not a shortfall to fix.** HPFP effective
  volume peaks at 94.9-95.9 % there. That band has no fuel headroom to accept
  more airmass, so its target is zero change even though it under-delivers.
* **6000-6500 rpm is a hold band too** — it already runs +1.6/+1.9 kPa *over*
  target. It shares cell (7, 15) with the shortfall bands at high weight, so it
  is weighted up to stop the solver buying 5000-6000 rpm with redline overshoot.

The setpoint is not touched. This moves work from the integral to the
feedforward at a boost target the closed loop is already commanding.

Usage:
    Code/.venv/bin/python Logs/BasicsGuide_R18/size_r19_wastegate.py
"""

import csv
import sys
from pathlib import Path

import numpy as np

LOG_DIR = Path(__file__).resolve().parent
REPO_ROOT = LOG_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT / "Code"))
from simoscal import CalFile, structure_of  # noqa: E402

XDF = REPO_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
STOCK_BIN = REPO_ROOT / "Code" / "bin" / "5G0906259L__0002.bin"
FLASHED_BIN = (REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
               / "R18_20260826-171645" / "Patched_259L_R18.bin")

#: Both R18 sessions. The hot session never reaches the Int 1.25 row; the cool
#: session does, and that is what makes cell (8, 15) separable from the redline
#: band at all. Pooling them is what gives the solve a lever that is not (7, 15).
SESSIONS = {"hot": "simostools-2026_08_27-*.csv",
            "cool": "simostools-2026_08_28-*.csv"}

BANDS = [(3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6600)]
#: Bands whose target is "do not move", with the reason. See the module docstring.
HOLD_BANDS = {(4500, 5000): "HPFP effective volume already 93-96 %",
              (6000, 6600): "already +1.6/+1.9 kPa over target"}
#: Weight multiplier on the hold bands, so the solver protects them rather than
#: trading them away. Same device as R15's REDLINE_BAND_WEIGHT, applied to both.
HOLD_BAND_WEIGHT = 5.0

#: Guide rule used to size R05, R08, and R15: ~0.05 wastegate position per psi.
WG_POS_PER_PSI = 0.05
KPA_PER_PSI = 68.95 / 10.0
#: R08 and R15 both applied ~70 % of the raw rule as a deliberately conservative
#: pass. Same restraint here, and it matters more in this direction: closing the
#: feedforward adds airmass rather than removing it.
CONSERVATISM = 0.70

#: Candidate cells (row = intake flow factor index, col = exhaust flow factor
#: index): every cell carrying non-trivial weight in the 5000-6000 rpm shortfall
#: that R05/R08 opened from stock and so has headroom to give back.
CANDIDATES = [(6, 14), (6, 15), (7, 14), (7, 15), (8, 14), (8, 15)]

#: The replayed lookup must match the logged feedforward this closely, or the
#: design matrix is not describing the ECU and the solve is meaningless.
MODEL_RMS_TOLERANCE = 0.25

CHANNELS = {"rpm": "Engine Speed (rpm)", "pedal": "Pedal Pos (%)",
            "gear": "Gear (gear)", "put": "PUT (kpa)", "put_sp": "PUT SP (kpa)",
            "exh": "Exh Flow Factor ()", "intake": "Intake Flow Fact ()",
            "wg_base": "WG Pos Base (%)", "wg_i": "WG I Value (%)",
            "lift": "Valve Lift Pos ()", "hpfp": "HPFP Eff Vol (%)"}


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


def collect(X, Y, shape, tables):
    """Pooled WOT 3rd-gear samples from both sessions, with the model check."""
    parts = {k: [] for k in ("rpm", "err", "exh", "intake", "wg_i", "hpfp",
                             "wg_base", "lift")}
    for tag, pattern in SESSIONS.items():
        files = sorted(LOG_DIR.glob(pattern))
        if not files:
            raise RuntimeError(f"no logs matched {pattern!r} for session {tag!r}")
        for path in files:
            d = load(path)
            m = (d["pedal"] >= 90) & (d["gear"] == 3) & (d["rpm"] >= 3000)
            if m.sum() < 5:
                continue
            parts["rpm"].append(d["rpm"][m])
            parts["err"].append(d["put"][m] - d["put_sp"][m])
            for k in ("exh", "intake", "wg_i", "hpfp", "wg_base", "lift"):
                parts[k].append(d[k][m])
    data = {k: np.concatenate(v) for k, v in parts.items()}

    predicted = np.empty(len(data["rpm"]))
    for n, (e, i, lift) in enumerate(zip(data["exh"], data["intake"], data["lift"])):
        Z = tables[int(round(lift))]
        xi = np.clip(np.interp(e, X, np.arange(len(X))), 0, len(X) - 1)
        yi = np.clip(np.interp(i, Y, np.arange(len(Y))), 0, len(Y) - 1)
        x0, y0 = int(np.floor(xi)), int(np.floor(yi))
        x1, y1 = min(x0 + 1, len(X) - 1), min(y0 + 1, len(Y) - 1)
        fx, fy = xi - x0, yi - y0
        predicted[n] = 100.0 * (
            Z[y0, x0] * (1 - fx) * (1 - fy) + Z[y0, x1] * fx * (1 - fy)
            + Z[y1, x0] * (1 - fx) * fy + Z[y1, x1] * fx * fy
        )
    residual = predicted - data["wg_base"]
    rms = float(np.sqrt((residual ** 2).mean()))
    print(f"Model check — replayed lookup vs logged `WG Pos Base (%)`: "
          f"mean {residual.mean():+.3f} pts, RMS {rms:.3f}, "
          f"max |{np.abs(residual).max():.2f}| over {len(residual)} samples")
    if rms > MODEL_RMS_TOLERANCE:
        raise RuntimeError(
            f"bilinear lookup does not reproduce the logged feedforward "
            f"(RMS {rms:.3f} > {MODEL_RMS_TOLERANCE}); the design matrix is wrong"
        )
    data["W"] = sample_weights(data["exh"], data["intake"], X, Y, shape)
    return data


def main():
    cal = CalFile.open(str(XDF), str(FLASHED_BIN),
                       structure=structure_of(str(FLASHED_BIN)))
    t0 = cal.get("IP_FAC_BPA_SP[0]")
    X = np.asarray(t0.axis_values("x"), dtype=float).ravel()
    Y = np.asarray(t0.axis_values("y"), dtype=float).ravel()
    Z0 = np.asarray(t0.values, dtype=float)
    Z1 = np.asarray(cal.get("IP_FAC_BPA_SP[1]").values, dtype=float)

    stock = CalFile.open(str(XDF), str(STOCK_BIN),
                         structure=structure_of(str(STOCK_BIN)))
    S0 = np.asarray(stock.get("IP_FAC_BPA_SP[0]").values, dtype=float)

    data = collect(X, Y, Z0.shape, {0: Z0, 1: Z1})
    rpm, err, W = data["rpm"], data["err"], data["W"]

    cells = sorted(CANDIDATES)
    headroom = np.array([S0[r, c] - Z0[r, c] for r, c in cells])
    if np.any(headroom < 0):
        raise RuntimeError("a candidate cell is already more closed than stock")

    A, target, weight = [], [], []
    print("\nMeasured shortfall and the position change it implies "
          "(pooled hot + cool, 3rd-gear WOT):\n")
    print(f"  {'band':<12}{'n':>5}{'err kPa':>9}{'WG I':>7}{'HPFP':>7}"
          f"{'short psi':>11}{'raw need':>10}{'target':>9}  note")
    for lo, hi_rpm in BANDS:
        b = (rpm >= lo) & (rpm < hi_rpm)
        if b.sum() < 5:
            continue
        e = err[b].mean()
        note = HOLD_BANDS.get((lo, hi_rpm), "")
        if note:
            tgt, short_psi, raw = 0.0, 0.0, 0.0
        else:
            short_psi = -e / KPA_PER_PSI
            raw = short_psi * WG_POS_PER_PSI
            tgt = max(raw, 0.0) * CONSERVATISM
        A.append([W[b][:, r, c].mean() for r, c in cells])
        target.append(tgt)
        weight.append(b.sum() * (HOLD_BAND_WEIGHT if note else 1.0))
        print(f"  {str(lo) + '-' + str(hi_rpm):<12}{b.sum():>5}{e:>+9.1f}"
              f"{data['wg_i'][b].mean():>7.1f}{data['hpfp'][b].max():>7.1f}"
              f"{short_psi:>11.2f}{raw:>+10.3f}{tgt:>+9.3f}  {note or 'fix'}")

    A = np.array(A)
    target = np.array(target)
    weight = np.array(weight, dtype=float)
    d = bounded_lsq(A, target, weight / weight.sum(), headroom)

    print("\nSolved cell deltas (bounded at stock — never more closed "
          "than the factory calibration):\n")
    print(f"  {'cell (Int x Exh)':<22}{'R18':>8}{'delta':>9}{'R19':>8}"
          f"{'stock':>9}{'at cap':>8}")
    r19 = {}
    for (r, c), di in zip(cells, d):
        di = round(float(di), 3)
        if di <= 0.0005:
            continue
        r19[(r, c)] = di
        print(f"  Int {Y[r]:.2f} x Exh {X[c]:.2f}      {Z0[r, c]:>8.3f}{di:>+9.3f}"
              f"{Z0[r, c] + di:>8.3f}{S0[r, c]:>9.3f}"
              f"{'  yes' if abs(Z0[r, c] + di - S0[r, c]) < 5e-4 else '   no':>8}")
    if not r19:
        raise RuntimeError("the solve produced no non-trivial delta")

    dvec = np.array([r19.get(cell, 0.0) for cell in cells])
    print("\nSimulated effect over the logged points "
          "(mean commanded feedforward change):\n")
    print(f"  {'band':<12}{'n':>5}{'target':>9}{'achieved':>11}"
          f"{'~psi added':>12}{'resid kPa':>11}")
    kept = [b for b in BANDS if ((rpm >= b[0]) & (rpm < b[1])).sum() >= 5]
    for (lo, hi_rpm), tgt in zip(kept, target):
        b = (rpm >= lo) & (rpm < hi_rpm)
        got = float(np.array([W[b][:, r, c].mean() for r, c in cells]) @ dvec)
        psi = got / WG_POS_PER_PSI
        resid = err[b].mean() + psi * KPA_PER_PSI
        print(f"  {str(lo) + '-' + str(hi_rpm):<12}{b.sum():>5}{tgt:>+9.3f}"
              f"{got:>+11.3f}{psi:>+12.2f}{resid:>+11.1f}")

    print("\nWG_DELTAS_R19 for the revision script (row, col) -> delta:")
    print("    WG_DELTAS_R19 = {")
    for (r, c), di in sorted(r19.items()):
        print(f"        ({r}, {c}): +{di:.3f},   # Int {Y[r]:.2f} x Exh {X[c]:.2f}: "
              f"{Z0[r, c]:.3f} -> {Z0[r, c] + di:.3f} (stock {S0[r, c]:.3f})")
    print("    }")

    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    same = np.array_equal(Z0[rows, cols], Z1[rows, cols])
    print(f"\nVVL0/VVL1 candidate cells currently identical: {same} "
          f"(deltas are applied to both maps regardless, per lineage convention)")


if __name__ == "__main__":
    main()
