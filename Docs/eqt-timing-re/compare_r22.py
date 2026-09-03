"""
Stage 4: put the recovered EQT Stage 2 base timing next to what R22 actually
delivers, per map slot.

R22's timing is delivered in two layers, and both have to be added up before any
comparison means anything:

  1. the nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` -- Basic Ignition Angle,
     VVL 0, low port flap maps, which are **shared by all five map slots**; and
  2. the switch patch's per-slot `Spark modifier` grid, an **additive** offset in
     the same units on the same two axes (rpm `0x3CE5A`, airmass `0x3CDBC`).

So delivered(slot) = base + modifier(slot). Slots 1-3 carry a neutral modifier
and therefore all run the same base timing; slots 4 and 5 are the octane slots.

Everything is compared as a delta against the same stock reference
`5G0906259L_0002` the EQT reconstruction is quoted against, and every comparison
is masked to the 58 cells the logs actually constrain -- see
`knowledge/eqt-s2-timing-reverse-engineering.md`.
"""

import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                            # noqa: E402
from matplotlib.colors import TwoSlopeNorm                 # noqa: E402

sys.path.insert(0, "/Users/sam/SimosTools/Code")
from simoscal import CalFile, SC8S50_STRUCTURE             # noqa: E402

# ---------------------------------------------------------------- user inputs

OUT_DIR = "/Users/sam/SimosTools/Docs/eqt-timing-re"
PLOT_DIR = os.path.join(OUT_DIR, "plots")
MAP_DIR = os.path.join(OUT_DIR, "maps")

XDF_PATH = "/Users/sam/SimosTools/Code/xdf/SC8S50.V1.0.xdf"
SWITCH_XDF = "/Users/sam/SimosTools/BinToolz-main/definitions/S50 Switch Patch.29.33.V2.xdf"
STOCK_BIN = "/Users/sam/SimosTools/Code/bin/5G0906259L__0002.bin"
R22_BIN = ("/Users/sam/SimosTools/Tunes/MainTune/MainTune_out/"
           "R22_20260901-060746/Patched_259L_R22.bin")

RECOVERED_EQT = os.path.join(MAP_DIR, "recovered_VVL0_STND.csv")
BASE_TABLE = "IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]"

#: Per-slot `Spark modifier` grids, by XDF uniqueid. Slot assignment read from
#: each table's CATEGORYMEM (0xF7 = Map Slot 1 ... 0xF3 = Map Slot 5) and
#: cross-checked against `Tunes/REV_LOG.md` § R20, which names slot 5 as 0x7d31a.
SLOT_MODIFIER = {1: 0x7CF1A, 2: 0x7D01A, 3: 0x7D11A, 4: 0x7D21A, 5: 0x7D31A}


def main():
    stock = CalFile.open(XDF_PATH, STOCK_BIN, structure=SC8S50_STRUCTURE)
    r22 = CalFile.open(XDF_PATH, R22_BIN, structure=SC8S50_STRUCTURE)
    r22sw = CalFile.open(SWITCH_XDF, R22_BIN, structure=SC8S50_STRUCTURE)

    t = stock.get(BASE_TABLE)
    x = np.asarray(t.axis_values("x"), dtype=float).ravel()
    y = np.asarray(t.axis_values("y"), dtype=float).ravel()
    idx = [f"{v:.0f}" for v in y]
    col = [f"{v:.0f}" for v in x]

    s_base = stock.get(BASE_TABLE).values
    r_base = r22.get(BASE_TABLE).values

    # Every one of the nine cam-indexed maps must still agree, or "the base" is
    # not a single surface and this comparison is not well posed.
    for i in range(3):
        for e in range(3):
            other = r22.get(f"IP_IGA_BAS_IVVT_VVL_PORT_L[STND][{i}][{e}]").values
            assert np.array_equal(r_base, other), f"R22 cam map [{i}][{e}] differs from [0][0]"

    mods = {s: r22sw.get(uid).values for s, uid in SLOT_MODIFIER.items()}
    for s, m in mods.items():
        print(f"slot {s} Spark modifier: {int((m != 0).sum()):3d} non-neutral cells, "
              f"range {m.min():+.3f} .. {m.max():+.3f} degCRK")

    eqt = pd.read_csv(RECOVERED_EQT, index_col=0).to_numpy()
    mask = np.isfinite(eqt)
    print(f"\ncomparing on the {int(mask.sum())} cells the EQT logs constrain")

    # Everything as a delta against the same stock reference.
    d_eqt = np.where(mask, eqt - s_base, np.nan)
    deltas = {"EQT S2 91 v2.52": d_eqt,
              "R22 slots 1-3 (base)": np.where(mask, r_base - s_base, np.nan)}
    for s in (4, 5):
        deltas[f"R22 slot {s}"] = np.where(mask, (r_base + mods[s]) - s_base, np.nan)

    rows = []
    for name, D in deltas.items():
        v = D[mask]
        rows.append(dict(calibration=name,
                         mean=round(float(np.mean(v)), 3),
                         min=round(float(np.min(v)), 3),
                         max=round(float(np.max(v)), 3),
                         cells_advanced=int((v > 0.1).sum()),
                         cells_stock=int((np.abs(v) <= 0.1).sum()),
                         cells_retarded=int((v < -0.1).sum())))
    summary = pd.DataFrame(rows)
    print("\n=== delta vs stock, over the constrained cells ===")
    print(summary.to_string(index=False))

    # Gap: how much timing EQT runs that R22 does not, per slot.
    gaps = []
    for s, label in ((None, "R22 slots 1-3 (base)"), (4, "R22 slot 4"), (5, "R22 slot 5")):
        G = d_eqt - deltas[label]
        v = G[mask]
        gaps.append(dict(slot=label,
                         mean_gap=round(float(np.mean(v)), 3),
                         max_eqt_ahead=round(float(np.max(v)), 3),
                         max_r22_ahead=round(float(np.min(v)), 3),
                         cells_eqt_ahead=int((v > 0.1).sum()),
                         cells_r22_ahead=int((v < -0.1).sum())))
        pd.DataFrame(G, index=idx, columns=col).to_csv(
            f"{MAP_DIR}/gap_eqt_minus_{label.replace(' ', '_').replace('-', '')}.csv")
    gapdf = pd.DataFrame(gaps)
    print("\n=== EQT minus R22 (positive = EQT runs more advance) ===")
    print(gapdf.to_string(index=False))

    summary.to_csv(f"{OUT_DIR}/r22_comparison_summary.csv", index=False)
    gapdf.to_csv(f"{OUT_DIR}/r22_gap_summary.csv", index=False)

    plots(deltas, mask, x, y, idx, col, r_base, s_base, mods)
    print("\nwrote r22_comparison_summary.csv, r22_gap_summary.csv, maps/gap_*.csv, plots/08,09")
    return deltas, mask, idx, col


def plots(deltas, mask, x, y, idx, col, r_base, s_base, mods):
    names = list(deltas)
    lim = max(abs(np.nanmin([np.nanmin(d) for d in deltas.values()])),
              abs(np.nanmax([np.nanmax(d) for d in deltas.values()])))
    fig, axes = plt.subplots(1, 4, figsize=(21, 5.2))
    for ax, n in zip(axes, names):
        im = ax.imshow(deltas[n], origin="upper", aspect="auto", cmap="RdBu_r",
                       norm=TwoSlopeNorm(vcenter=0, vmin=-lim, vmax=lim))
        ax.set_xticks(range(16)); ax.set_xticklabels(col, rotation=90, fontsize=6)
        ax.set_yticks(range(16)); ax.set_yticklabels(idx, fontsize=6)
        ax.set_xlabel("RPM", fontweight="bold", fontsize=8)
        ax.set_ylabel("Airmass (mg/stk)", fontweight="bold", fontsize=8)
        ax.set_title(f"{n}\nmean {np.nanmean(deltas[n]):+.2f}°", fontsize=9)
    fig.colorbar(im, ax=axes, label="Δ°CRK vs stock 5G0906259L_0002", shrink=0.85)
    fig.suptitle("Base ignition timing vs stock — recovered EQT Stage 2 against R22's slots\n"
                 "(same 58 cells throughout; red = advanced, blue = retarded)", fontsize=12)
    fig.savefig(f"{PLOT_DIR}/08_eqt_vs_r22_delta.png", dpi=140, bbox_inches="tight"); plt.close(fig)

    # Delivered angle vs rpm at the load rows that matter
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    eqt_abs = pd.read_csv(RECOVERED_EQT, index_col=0).to_numpy()
    for ax, row_mg in zip(axes, (900, 1200, 1400)):
        r = list(y).index(min(y, key=lambda v: abs(v - row_mg)))
        ok = np.isfinite(eqt_abs[r])
        ax.plot(x[ok], s_base[r][ok], "o--", color="0.35", lw=1.4, label="stock")
        ax.plot(x[ok], r_base[r][ok], "s-", color="#c0392b", lw=1.8, label="R22 slots 1-3")
        ax.plot(x[ok], (r_base + mods[4])[r][ok], "^-", color="#e67e22", lw=1.8, label="R22 slot 4")
        ax.plot(x[ok], (r_base + mods[5])[r][ok], "v-", color="#8e44ad", lw=1.8, label="R22 slot 5")
        ax.plot(x[ok], eqt_abs[r][ok], "D-", color="#0a8f5a", lw=2.4, label="EQT S2 91 (recovered)")
        ax.set_title(f"{row_mg:.0f} mg/stk", fontsize=10)
        ax.set_xlabel("Engine speed (RPM)", fontweight="bold")
        ax.grid(True); ax.grid(which="minor")
    axes[0].set_ylabel("Base ignition angle (°CRK)", fontweight="bold")
    axes[0].legend(fontsize=8)
    fig.suptitle("Delivered base timing by load row — EQT Stage 2 91 vs every R22 slot", fontsize=12)
    fig.tight_layout(); fig.savefig(f"{PLOT_DIR}/09_eqt_vs_r22_rows.png", dpi=140); plt.close(fig)


if __name__ == "__main__":
    main()
