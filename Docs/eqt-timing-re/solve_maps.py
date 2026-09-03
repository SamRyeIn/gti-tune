"""
Stage 2: invert the logged `Ignition Table Output` channel back into the
`IP_IGA_BAS_IVVT_VVL_PORT_L` -- Basic Ignition Angle map cells.

Two nested selection problems, both scored on SESSION-held-out data (whole
recordings withheld, never random rows -- consecutive log rows are ~30-45 Hz
samples of the same operating point, so a random split leaks and flatters the
score by roughly an order of magnitude):

  1. REGIME. The base ignition maps are only the whole story where no other ECU
     path is adding to the angle. Fitting all 111 k samples lands at ~2.0 degCRK
     held out and will not go lower for any model tried -- adding the 3x3 cam
     blend, an f(RPM, IAT) correction, or a port-flap state split each moved it
     by <3%. Restricting to high load collapses it to ~0.25-0.48 degCRK, i.e.
     inside the store's own 0.375 deg quantization. Part-throttle samples carry
     contributions this channel set cannot observe (combustion-mode corrections
     `IP_IGA_BAS_CMB_MOD_COR` -- Basic ignition angle correction for different
     combustion modes, and torque-intervention paths), so the recoverable
     regime is the boosted / high-load one. That is also the only regime the
     tune's dyno curve depends on.

  2. MODEL. With the regime fixed, whether the 3x3 intake/exhaust cam-indexed
     map stack earns its parameters over a single surface per valve-lift state.

Selection rule, stated up front so it cannot be chosen after seeing the answer:
among configurations whose held-out RMSE clears RMSE_TARGET, take the one that
constrains the most VVL 0 grid cells; break ties on RMSE.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from scipy.sparse import linalg as spla, vstack, hstack, csr_matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecu_lookup as E                                    # noqa: E402

sys.path.insert(0, "/Users/sam/SimosTools/Code")
from simoscal import CalFile, SC8S50_STRUCTURE            # noqa: E402

# ---------------------------------------------------------------- user inputs

OUT_DIR = "/Users/sam/SimosTools/Docs/eqt-timing-re"
SAMPLES = os.path.join(OUT_DIR, "samples.parquet")
STOCK_BIN = "/Users/sam/SimosTools/Code/bin/5G0906259L__0002.bin"
XDF = "/Users/sam/SimosTools/Code/xdf/SC8S50.V1.0.xdf"

REF_TABLE = "IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]"      # axis donor
RMSE_TARGET = 0.75                                        # degCRK == 2 LSB
# A cell counts as constrained at this much total interpolation weight. Set
# from data, not taste: below ~40 the fit-free node cross-check
# (`node_check_*.csv`) disagrees with the reconstruction by more than the
# store's own 0.375 deg LSB, because a thin row lets the smoothness prior, not
# the logs, decide the value -- and then bleeds that error into its neighbours.
MIN_CELL_WEIGHT = 40.0

LAM_SMOOTH = 0.35     # second-difference penalty on each map
LAM_AGREE = 0.60      # penalty on the 9 cam maps of a group disagreeing

# Whole sessions withheld from every fit: one track session, one street session,
# one single-pull log -- so the holdout spans all three recording styles.
HOLDOUT_SESSIONS = [
    "Documents/Cars/GTI/Cobb/Logs/Track/20220920 Ridge/20220920_Ridge_Session3.csv",
    "Documents/Cars/GTI/Cobb/Logs/20220830_EQTS2_1.csv",
    "Documents/Cars/GTI/Cobb/Logs/20220522_EQTS2_3Gear1.csv",
]

# Candidate operating regimes, widest envelope first.
REGIMES = {
    "all samples":            lambda d: np.ones(len(d), bool),
    "relmap > -2 psi":        lambda d: d.relmap_psi.to_numpy() > -2,
    "in boost (relmap > 0)":  lambda d: d.relmap_psi.to_numpy() > 0,
    "airmass > 450 mg/stk":   lambda d: d.maf.to_numpy() > 450,
    "airmass > 600 mg/stk":   lambda d: d.maf.to_numpy() > 600,
    "pedal > 70%":            lambda d: d.pedal.to_numpy() > 70,
    "pedal > 90% (WOT)":      lambda d: d.pedal.to_numpy() > 90,
}

# Cam support-point candidates. The phaser positions at which map indices 0/1/2
# are exact are not exposed in the XDF, so they are scanned over the observed
# phaser travel. `None` is the single-surface (no cam blend) hypothesis.
CAM_CONFIGS = [None,
               ((-34, -17, 0), (-23, -11, 1)),
               ((-34, -6, 24), (-23, -11, 1)),
               ((-24, 0, 24), (-12, -6, 1)),
               ((0, 12, 24), (-12, -6, 1)),
               ((-34, -17, 0), (-12, -6, 1))]


def load():
    d = pd.read_parquet(SAMPLES)
    d = d[d.pedal.notna() & d.relmap_psi.notna()].reset_index(drop=True)
    d["holdout"] = d.src.isin(HOLDOUT_SESSIONS)
    return d


def axes():
    cal = CalFile.open(XDF, STOCK_BIN, structure=SC8S50_STRUCTURE)
    t = cal.get(REF_TABLE)
    return (cal,
            np.asarray(t.axis_values("x"), dtype=float).ravel(),
            np.asarray(t.axis_values("y"), dtype=float).ravel())


def build(d, x_axis, y_axis, cams):
    """Design matrix + regularizer for one (regime subset, cam config)."""
    sup_in, sup_ex = cams if cams else (None, None)
    A, per_group, n_maps = E.design_matrix(
        x_axis, y_axis, d.rpm.to_numpy(), d.maf.to_numpy(),
        d.cam_in.to_numpy(), d.cam_ex.to_numpy(),
        d.vls.to_numpy().astype(int), 2, sup_in, sup_ex)
    reg = E.smoothness_operator(2, n_maps, LAM_SMOOTH,
                                LAM_AGREE if n_maps > 1 else 0.0)
    return A, reg, n_maps


def solve(A, y, reg):
    M = vstack([A, reg]).tocsr()
    rhs = np.concatenate([y, np.zeros(reg.shape[0])])
    return spla.lsmr(M, rhs, atol=1e-9, btol=1e-9, maxiter=1500)[0]


def score(d, x_axis, y_axis, cams):
    tr, te = d[~d.holdout], d[d.holdout]
    if len(tr) < 1500 or len(te) < 300:
        return None
    A, reg, n_maps = build(tr, x_axis, y_axis, cams)
    theta = solve(A, tr.iga_tab.to_numpy(), reg)
    A_te, _, _ = build(te, x_axis, y_axis, cams)
    r_tr = A @ theta - tr.iga_tab.to_numpy()
    r_te = A_te @ theta - te.iga_tab.to_numpy()
    w = np.asarray(A.sum(axis=0)).ravel() >= MIN_CELL_WEIGHT
    per = n_maps * E.NX * E.NY
    return dict(cams=cams, n_maps=n_maps, n_par=int(A.shape[1]),
                n_train=len(tr), n_hold=len(te),
                rmse_train=float(np.sqrt((r_tr ** 2).mean())),
                rmse_hold=float(np.sqrt((r_te ** 2).mean())),
                mae_hold=float(np.abs(r_te).mean()),
                cov_vvl0_pct=100 * float(w[:per].reshape(n_maps, 256).any(0).mean()),
                cov_vvl1_pct=100 * float(w[per:].reshape(n_maps, 256).any(0).mean()))


def main():
    d = load()
    cal, x_axis, y_axis = axes()
    print(f"samples {len(d)}   train {int((~d.holdout).sum())}   holdout {int(d.holdout.sum())}")
    print(f"rpm axis     {np.round(x_axis, 0)}")
    print(f"airmass axis {np.round(y_axis, 0)}\n")

    rows = []
    for rname, sel in REGIMES.items():
        sub = d[sel(d)]
        for cams in CAM_CONFIGS:
            r = score(sub, x_axis, y_axis, cams)
            if r is None:
                continue
            r["regime"] = rname
            r["n_regime"] = len(sub)
            rows.append(r)
            print(f"{rname:24s} cams={str(cams):34s} hold {r['rmse_hold']:.3f}  "
                  f"train {r['rmse_train']:.3f}  covVVL0 {r['cov_vvl0_pct']:.0f}%")

    ok = [r for r in rows if r["rmse_hold"] <= RMSE_TARGET]
    if not ok:
        print("\nNO configuration cleared the target; falling back to lowest RMSE")
        best = min(rows, key=lambda r: r["rmse_hold"])
    else:
        best = max(ok, key=lambda r: (round(r["cov_vvl0_pct"], 1), -r["rmse_hold"]))
    print(f"\nSELECTED  regime={best['regime']!r}  cams={best['cams']}  "
          f"holdout RMSE {best['rmse_hold']:.3f}  VVL0 coverage {best['cov_vvl0_pct']:.0f}%")

    json.dump({"rmse_target": RMSE_TARGET, "min_cell_weight": MIN_CELL_WEIGHT,
               "holdout_sessions": HOLDOUT_SESSIONS,
               "selection_rule": "among configs with holdout RMSE <= target, "
                                 "maximise constrained VVL0 grid cells; tie-break on RMSE",
               "selected": {k: str(v) if k == "cams" else v for k, v in best.items()},
               "ladder": [{k: str(v) if k == "cams" else v for k, v in r.items()} for r in rows]},
              open(os.path.join(OUT_DIR, "model_selection.json"), "w"), indent=1)
    print("wrote model_selection.json")


if __name__ == "__main__":
    main()
