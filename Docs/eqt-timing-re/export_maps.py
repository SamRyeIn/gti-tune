"""
Stage 3: refit the winning model, write the recovered maps, and score them.

Reads the ladder written by `solve_maps.py`, picks the winning rung, then:

  1. refits on the training sessions and reports held-out accuracy,
  2. refits on ALL sessions to produce the delivered maps,
  3. writes one CSV per recovered map on the true 16x16 XDF axes, with cells
     the logs never constrained written as empty (UNCONSTRAINED), never as an
     interpolated guess,
  4. writes the matching per-cell sample-weight CSVs,
  5. writes the delta against the stock 5G0906259L calibration,
  6. draws the evidence plots.

Coverage rule: a cell counts as CONSTRAINED when the total bilinear x cam
weight the logs put on it reaches MIN_CELL_WEIGHT. Below that the fitted value
is the smoothness prior talking, not the data, and is withheld.
"""

import json
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                            # noqa: E402
from matplotlib.colors import TwoSlopeNorm                 # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ecu_lookup as E                                     # noqa: E402
import solve_maps as S                                     # noqa: E402

OUT_DIR = S.OUT_DIR
MAP_DIR = os.path.join(OUT_DIR, "maps")
PLOT_DIR = os.path.join(OUT_DIR, "plots")

MIN_CELL_WEIGHT = S.MIN_CELL_WEIGHT   # total interpolation weight a cell needs
GROUP_NAME = {0: "VVL0_STND", 1: "VVL1_LFT_1"}
STOCK_SYMBOL = {0: "IP_IGA_BAS_IVVT_VVL_PORT_L[STND][{i}][{e}]",
                1: "IP_IGA_BAS_IVVT_VVL_PORT_L[LFT_1][{i}][{e}]"}


def cell_weights(d, x_axis, y_axis, cams):
    """Total design weight landing on each parameter -- the coverage measure."""
    A, _, _ = S.build(d, x_axis, y_axis, cams)
    return np.asarray(A.sum(axis=0)).ravel(), A


def unpack(theta, n_maps):
    per_group = n_maps * E.NX * E.NY
    out = {}
    for g in range(2):
        for m in range(n_maps):
            lo = g * per_group + m * E.NX * E.NY
            out[(g, m // 3, m % 3)] = theta[lo:lo + E.NX * E.NY].reshape(E.NY, E.NX)
    return out


def heat(ax, M, x_axis, y_axis, title, cmap="viridis", norm=None):
    im = ax.imshow(M, origin="upper", aspect="auto", cmap=cmap, norm=norm)
    ax.set_xticks(range(E.NX)); ax.set_xticklabels([f"{v:.0f}" for v in x_axis], rotation=90, fontsize=6)
    ax.set_yticks(range(E.NY)); ax.set_yticklabels([f"{v:.0f}" for v in y_axis], fontsize=6)
    ax.set_xlabel("RPM", fontweight="bold", fontsize=8)
    ax.set_ylabel("Airmass (mg/stk)", fontweight="bold", fontsize=8)
    ax.set_title(title, fontsize=9)
    return im


# Note: fitting only the well-covered columns and dropping the rest was tried
# and is worse -- node-check RMSE 0.73 -> 1.51 degCRK. The under-covered cells
# are not just noise to be excised: they carry the smoothness prior that holds
# the *edge* of the covered region in place. Fit every cell, report only the
# covered ones.


def node_check(d, x_axis, y_axis, rec, vls, min_n=15):
    """Fit-free audit: samples landing essentially ON a grid node must read the
    cell's own value, because bilinear interpolation at a node is the identity.
    Comparing the logged median there against the reconstruction tests the maps
    without going through the least-squares model at all."""
    v = d[d.vls == vls]
    rows = []
    for yi, yv in enumerate(y_axis):
        for xi, xv in enumerate(x_axis):
            if not np.isfinite(rec[yi, xi]):
                continue
            m = v[(v.rpm.sub(xv).abs() < 0.02 * xv) & (v.maf.sub(yv).abs() < 0.03 * yv)]
            if len(m) < min_n:
                continue
            med = float(m.iga_tab.median())
            err = med - rec[yi, xi]
            rows.append(dict(rpm=round(float(xv)), airmass=round(float(yv)), n_samples=len(m),
                             logged_median=round(med, 3), recovered=round(float(rec[yi, xi]), 3),
                             error=round(err, 3),
                             # The Accessport writes this channel rounded to 2 dp, so an
                             # exact 1-LSB (0.375) match reads back as 0.38. Allow for that.
                             agrees_within_1_lsb=bool(abs(err) <= E.LSB_DEG + 0.01)))
    return pd.DataFrame(rows)


def main():
    os.makedirs(MAP_DIR, exist_ok=True)
    os.makedirs(PLOT_DIR, exist_ok=True)

    sel = json.load(open(os.path.join(OUT_DIR, "model_selection.json")))
    best = sel["selected"]
    cams = None if best["cams"] in ("None", None) else eval(best["cams"])
    regime = best["regime"]
    print(f"selected regime={regime!r}  cams={cams}  holdout RMSE {best['rmse_hold']:.3f}")

    d_all = S.load()
    cal, x_axis, y_axis = S.axes()
    d = d_all[S.REGIMES[regime](d_all)].reset_index(drop=True)
    tr, te = d[~d.holdout], d[d.holdout]

    # --- (1) accuracy on the withheld sessions ----------------------------
    # Cells are judged constrained by the FULL regime data, so the holdout fit
    # and the delivered fit report on the same cell set.
    w_all, A_all = cell_weights(d, x_axis, y_axis, cams)
    covered = w_all >= MIN_CELL_WEIGHT

    A_tr, reg_tr, n_maps = S.build(tr, x_axis, y_axis, cams)
    theta_tr = S.solve(A_tr, tr.iga_tab.to_numpy(), reg_tr)
    A_te, _, _ = S.build(te, x_axis, y_axis, cams)
    pred_te = A_te @ theta_tr
    resid = pred_te - te.iga_tab.to_numpy()

    # Restrict to held-out samples whose interpolation lands wholly on cells the
    # logs actually constrain -- the goal's bar is about constrained cells.
    off = np.asarray(A_te.multiply(~covered).sum(axis=1)).ravel()
    on_cov = off < 0.02
    rmse_all = float(np.sqrt((resid ** 2).mean()))
    rmse_cov = float(np.sqrt((resid[on_cov] ** 2).mean()))
    print(f"holdout n={len(te)}  RMSE(all) {rmse_all:.3f}  "
          f"RMSE(constrained cells, n={int(on_cov.sum())}) {rmse_cov:.3f} degCRK")

    # --- (2) delivered maps: refit on every session in the regime ---------
    A, reg, _ = S.build(d, x_axis, y_axis, cams)
    theta_full = S.solve(A, d.iga_tab.to_numpy(), reg)
    maps = unpack(theta_full, n_maps)
    wmaps = unpack(w_all, n_maps)

    # --- (3,4,5) write the CSVs -------------------------------------------
    stats = {}
    for (g, i, e), M in sorted(maps.items()):
        W = wmaps[(g, i, e)]
        mask = (W >= MIN_CELL_WEIGHT) & np.isfinite(M)
        Mq = np.where(mask, E.quantize(M), np.nan)
        name = f"{GROUP_NAME[g]}_intake{i}_exhaust{e}" if n_maps > 1 else GROUP_NAME[g]
        sym = STOCK_SYMBOL[g].format(i=i, e=e)
        idx = [f"{v:.0f}" for v in y_axis]; col = [f"{v:.0f}" for v in x_axis]
        pd.DataFrame(Mq, index=idx, columns=col).to_csv(f"{MAP_DIR}/recovered_{name}.csv")
        pd.DataFrame(np.round(W, 2), index=idx, columns=col).to_csv(f"{MAP_DIR}/coverage_{name}.csv")
        D = np.where(mask, Mq - cal.get(sym).values, np.nan)
        pd.DataFrame(D, index=idx, columns=col).to_csv(f"{MAP_DIR}/delta_vs_stock_{name}.csv")
        stats[(g, i, e)] = dict(
            map=name, symbol=sym, coverage_pct=round(100 * float(mask.mean()), 1),
            n_cells_constrained=int(mask.sum()),
            delta_min=None if not mask.any() else round(float(np.nanmin(D)), 3),
            delta_max=None if not mask.any() else round(float(np.nanmax(D)), 3),
            delta_mean=None if not mask.any() else round(float(np.nanmean(D)), 3))
    rows = list(stats.values())
    if n_maps == 1:
        rows = [v for k, v in stats.items() if k[1] == 0 and k[2] == 0]
    pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "recovered_map_summary.csv"), index=False)

    union0 = np.zeros((E.NY, E.NX), bool)
    union1 = np.zeros((E.NY, E.NX), bool)
    for k, W in wmaps.items():
        (union0 if k[0] == 0 else union1)[:] |= (W >= MIN_CELL_WEIGHT)
    cov0, cov1 = 100 * float(union0.mean()), 100 * float(union1.mean())
    print(f"grid coverage: VVL 0 {cov0:.1f}%   VVL 1 {cov1:.1f}%   "
          f"({int(union0.sum())} / 256 and {int(union1.sum())} / 256 cells)")

    json.dump(dict(regime=regime, cams=str(cams), n_maps=int(n_maps),
                   rmse_holdout_all=rmse_all, rmse_holdout_constrained=rmse_cov,
                   mae_holdout=float(np.abs(resid).mean()),
                   rmse_target=S.RMSE_TARGET, lsb_deg=E.LSB_DEG,
                   n_holdout=int(len(te)), n_holdout_constrained=int(on_cov.sum()),
                   n_train=int(len(tr)), n_regime=int(len(d)), n_all_logs=int(len(d_all)),
                   min_cell_weight=MIN_CELL_WEIGHT,
                   grid_coverage_vvl0_pct=round(cov0, 1),
                   grid_coverage_vvl1_pct=round(cov1, 1),
                   n_cells_vvl0=int(union0.sum()), n_cells_vvl1=int(union1.sum()),
                   holdout_sessions=S.HOLDOUT_SESSIONS),
              open(os.path.join(OUT_DIR, "validation.json"), "w"), indent=1)

    # --- (6) fit-free per-cell audit --------------------------------------
    checks = {}
    for g, tag in GROUP_NAME.items():
        Mg = maps[(g, 0, 0)]
        recg = np.where((wmaps[(g, 0, 0)] >= MIN_CELL_WEIGHT) & np.isfinite(Mg),
                        E.quantize(Mg), np.nan)
        nc = node_check(d, x_axis, y_axis, recg, g)
        nc.to_csv(f"{MAP_DIR}/node_check_{tag}.csv", index=False)
        checks[tag] = nc
        if len(nc):
            print(f"  node check {tag}: {len(nc)} nodes, "
                  f"{int(nc.agrees_within_1_lsb.sum())} within 1 LSB, "
                  f"RMSE {np.sqrt((nc.error ** 2).mean()):.3f}, max |err| {nc.error.abs().max():.3f}")
    nc0 = checks[GROUP_NAME[0]]
    val = json.load(open(os.path.join(OUT_DIR, "validation.json")))
    val["node_check_vvl0"] = dict(
        n_nodes=int(len(nc0)),
        n_within_1_lsb=int(nc0.agrees_within_1_lsb.sum()) if len(nc0) else 0,
        rmse=round(float(np.sqrt((nc0.error ** 2).mean())), 4) if len(nc0) else None,
        max_abs_error=round(float(nc0.error.abs().max()), 4) if len(nc0) else None)
    json.dump(val, open(os.path.join(OUT_DIR, "validation.json"), "w"), indent=1)

    plots(maps, wmaps, cal, x_axis, y_axis, te, pred_te, resid, sel["ladder"], d, union0, n_maps, checks)
    print("wrote maps/, plots/, validation.json, recovered_map_summary.csv")


def plots(maps, wmaps, cal, x_axis, y_axis, te, pred_te, resid, ladder, d, union0, n_maps, checks):
    SYM_L = "IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]"
    key = (0, 0, 0)
    W = wmaps[key]
    mask = W >= MIN_CELL_WEIGHT
    M = np.where(mask, E.quantize(maps[key]), np.nan)
    stock = cal.get(SYM_L).values

    # 1 -- recovered vs stock vs delta, the operative VVL 0 surface
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    vmin = float(min(np.nanmin(M), stock.min())); vmax = float(max(np.nanmax(M), stock.max()))
    im0 = heat(axes[0], stock, x_axis, y_axis, "Stock 5G0906259L_0002", norm=plt.Normalize(vmin, vmax))
    fig.colorbar(im0, ax=axes[0], label="\u00b0CRK")
    im1 = heat(axes[1], M, x_axis, y_axis, "Recovered EQT Stage 2 91 v2.52", norm=plt.Normalize(vmin, vmax))
    fig.colorbar(im1, ax=axes[1], label="\u00b0CRK")
    D = M - stock
    lim = float(np.nanmax(np.abs(D))) or 1.0
    im2 = heat(axes[2], D, x_axis, y_axis, "EQT \u2212 stock", cmap="RdBu_r",
               norm=TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim))
    fig.colorbar(im2, ax=axes[2], label="\u0394\u00b0CRK")
    fig.suptitle("IP_IGA_BAS_IVVT_VVL_PORT_L[STND] \u2014 Basic Ignition Angle, VVL 0, low port flap\n"
                 "white = UNCONSTRAINED (the logs never visit that cell)", fontsize=11)
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/01_recovered_vs_stock.png", dpi=140); plt.close(fig)

    # 2 -- coverage / confidence map
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    im = heat(axes[0], np.log10(np.maximum(W, 0.1)), x_axis, y_axis,
              f"VVL 0 \u2014 {100*mask.mean():.0f}% of cells constrained", cmap="magma")
    fig.colorbar(im, ax=axes[0], label="log10 total interpolation weight")
    W1 = wmaps[(1, 0, 0)]
    im = heat(axes[1], np.log10(np.maximum(W1, 0.1)), x_axis, y_axis,
              f"VVL 1 \u2014 {100*(W1>=MIN_CELL_WEIGHT).mean():.0f}% of cells constrained", cmap="magma")
    fig.colorbar(im, ax=axes[1], label="log10 total interpolation weight")
    fig.suptitle(f"Per-cell log coverage (a cell counts as constrained at weight \u2265 {MIN_CELL_WEIGHT})",
                 fontsize=11)
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/02_coverage.png", dpi=140); plt.close(fig)

    # 3 -- holdout validation
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].hexbin(te.iga_tab, pred_te, gridsize=60, cmap="viridis", bins="log")
    lo, hi = float(te.iga_tab.min()), float(te.iga_tab.max())
    axes[0].plot([lo, hi], [lo, hi], "r--", lw=1)
    axes[0].set_xlabel("Logged Ignition Table Output (\u00b0CRK)", fontweight="bold")
    axes[0].set_ylabel("Reconstructed (\u00b0CRK)", fontweight="bold")
    axes[0].set_title(f"Held-out sessions, n={len(te)}")
    axes[0].grid(True); axes[0].grid(which="minor")
    axes[1].hist(resid, bins=120, color="#3b6ea5")
    axes[1].axvline(0, color="k", lw=0.8)
    for v in (-E.LSB_DEG, E.LSB_DEG):
        axes[1].axvline(v, color="r", ls="--", lw=0.9)
    axes[1].set_xlabel("Reconstruction \u2212 logged (\u00b0CRK)", fontweight="bold")
    axes[1].set_ylabel("Samples", fontweight="bold")
    axes[1].set_title(f"RMSE {np.sqrt((resid**2).mean()):.3f}\u00b0   "
                      f"(red = \u00b11 LSB = \u00b1{E.LSB_DEG:.3f}\u00b0)")
    axes[1].grid(True); axes[1].grid(which="minor")
    fig.suptitle("Holdout validation \u2014 three whole sessions withheld from the fit", fontsize=11)
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/03_holdout_validation.png", dpi=140); plt.close(fig)

    # 4 -- the WOT timing curve
    wot = d[(d.pedal > 90) & (d.vls == 0)]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.scatter(wot.rpm, wot.iga_tab, s=5, alpha=0.2, color="#c44",
               label=f"EQT logged, WOT + VVL 0 (n={len(wot)})")
    rr = np.linspace(2000, 6500, 300)
    Mf = np.where(mask, E.quantize(maps[key]), np.nan).ravel()
    st = stock.ravel()
    for mafv, ls in ((900, "-"), (1200, "--"), (1400, ":")):
        cs, ws = E.bilinear_terms(x_axis, y_axis, rr, np.full_like(rr, float(mafv)))
        ax.plot(rr, (st[cs] * ws).sum(1), ls, color="0.25", lw=1.5,
                label=f"stock @ {mafv} mg/stk")
        ax.plot(rr, (Mf[cs] * ws).sum(1), ls, color="#0a8f5a", lw=2.2,
                label=f"recovered EQT @ {mafv} mg/stk")
    ax.set_xlabel("Engine speed (RPM)", fontweight="bold")
    ax.set_ylabel("Base ignition angle (\u00b0CRK)", fontweight="bold")
    ax.set_title("Base timing at high load \u2014 EQT Stage 2 91 v2.52 vs stock 5G0906259L_0002")
    ax.grid(True); ax.grid(which="minor"); ax.legend(fontsize=8, ncol=2)
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/04_wot_timing_curve.png", dpi=140); plt.close(fig)

    # 5 -- regime / model selection ladder
    fig, ax = plt.subplots(figsize=(12, 5.5))
    lab = [f"{r['regime']}\n{'no cams' if r['cams'] in ('None', None) else 'cam 3x3'}" for r in ladder]
    cols = ["#c0392b" if r["rmse_hold"] > S.RMSE_TARGET else "#3b6ea5" for r in ladder]
    ax.bar(range(len(ladder)), [r["rmse_hold"] for r in ladder], color=cols)
    ax.axhline(S.RMSE_TARGET, color="r", ls="--", label=f"target {S.RMSE_TARGET}\u00b0 (2 LSB)")
    ax.axhline(E.LSB_DEG, color="orange", ls=":", label=f"1 LSB quantization floor ({E.LSB_DEG:.3f}\u00b0)")
    ax.set_xticks(range(len(ladder))); ax.set_xticklabels(lab, rotation=90, fontsize=5)
    ax.set_ylabel("Held-out RMSE (\u00b0CRK)", fontweight="bold")
    ax.set_title("Regime and model selection \u2014 every fit scored on withheld sessions")
    ax.grid(True); ax.grid(which="minor"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/05_model_selection.png", dpi=140); plt.close(fig)

    # 6 -- where the logs live on the map grid
    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.scatter(d.rpm, d.maf, s=1, alpha=0.10, color="#356")
    for v in x_axis: ax.axvline(v, color="k", lw=0.4, alpha=0.3)
    for v in y_axis: ax.axhline(v, color="k", lw=0.4, alpha=0.3)
    ax.set_xlabel("Engine speed (RPM)", fontweight="bold")
    ax.set_ylabel("Airmass (mg/stk)", fontweight="bold")
    ax.set_title(f"Where the {len(d)} in-regime samples fall on the 16\u00d716 map grid "
                 f"(VVL 0 coverage {100*union0.mean():.0f}%)")
    ax.grid(True); ax.grid(which="minor")
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/06_sample_grid_coverage.png", dpi=140); plt.close(fig)

    # 7 -- fit-free node cross-check
    nc = checks[GROUP_NAME[0]]
    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    ok = nc[nc.agrees_within_1_lsb]; bad = nc[~nc.agrees_within_1_lsb]
    ax.scatter(ok.recovered, ok.logged_median, s=38, color="#0a8f5a",
               label=f"agrees within 1 LSB (n={len(ok)})")
    ax.scatter(bad.recovered, bad.logged_median, s=44, color="#c0392b", marker="x",
               label=f"disagrees (n={len(bad)})")
    lim = [float(nc.recovered.min()) - 1, float(nc.recovered.max()) + 1]
    ax.plot(lim, lim, "k--", lw=1)
    ax.fill_between(lim, [v - E.LSB_DEG for v in lim], [v + E.LSB_DEG for v in lim],
                    color="k", alpha=0.10, label="\u00b11 LSB band")
    for _, r in bad.iterrows():
        ax.annotate(f"{r.rpm:.0f} rpm / {r.airmass:.0f} mg", (r.recovered, r.logged_median),
                    fontsize=7, xytext=(5, -9), textcoords="offset points")
    ax.set_xlabel("Recovered cell value (\u00b0CRK)", fontweight="bold")
    ax.set_ylabel("Median logged Ignition Table Output at that node (\u00b0CRK)", fontweight="bold")
    ax.set_title("Fit-free audit \u2014 reconstruction vs a direct read at each grid node\n"
                 "(VVL 0; bilinear interpolation at a node is the identity, so these must match)")
    ax.grid(True); ax.grid(which="minor"); ax.legend()
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/07_node_cross_check.png", dpi=140); plt.close(fig)


if __name__ == "__main__":
    main()
