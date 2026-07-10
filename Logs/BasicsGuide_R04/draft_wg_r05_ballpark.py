#!/usr/bin/env python3
"""Draft R05 wastegate feedforward edits from the BasicsGuide_R04 log.

Reads the two wastegate feedforward tables (`IP_FAC_BPA_SP[0]` / `[1]` —
Wastegate Position Feedforward VVL 0/1) from the flashed R04 bin, applies
ballpark cell + axis edits targeting the two PUT-overshoot regions identified
in the R04 log, and writes both edited tables to a CSV for review BEFORE any
bin is written or the R05 tune script is built.

Tables: 10 rows (Int FF, Y) x 16 cols (Exh FF, X). Cells = WG position
(1 = closed, 0 = open). Overboost -> lower cells (open WG more).

Regions from the R04 log (two 3rd-gear WOT pulls):
  A — spool spike, ~3000-3500 rpm: Exh 0.75-0.91 x Int 0.62-0.78,
      PUT error +11 to +22 kPa. Feedforward commands WG nearly closed right as
      boost crosses target; PID P/D reacts but can't catch the transient.
  B — top-end persistent, ~6000-6500 rpm: Exh 1.08-1.33 x Int 0.97-1.07,
      PUT error +10 to +16 kPa sustained. Exh FF 1.33 exceeds the stock last
      X column (1.25) so it clamps; WG integral saturates at its -27.5% floor.

Ballpark edits (this draft):
  Axis: bump last X breakpoint 1.25 -> 1.40 so logged Exh FF 1.33 interpolates
        between the 1.00 and 1.40 columns instead of clamping at 1.25.
  Cells A (spool corner, Exh 0.75-0.90 x Int 0.60-0.90): lower ~0.08-0.12.
  Cells B (top-end, Exh 1.00 & 1.40 x Int 0.90-1.50): lower ~0.05-0.10,
          heavier toward the high-Exh / high-Int corner where overshoot grows.
  Blend: neighbors around A and B get ~half the delta to avoid WG cliffs.
  VVL 0 / VVL 1: same delta pattern applied to both (the guide says apply
          changes to both; their existing small low-row differences preserved).

This is a draft for review, not a saved bin. No checksums, no flash.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from simoscal import CalFile

LOG_DIR = Path(__file__).resolve().parent
CODE_ROOT = LOG_DIR.parents[1]
XDF_PATH = CODE_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
BIN_PATH = (
    CODE_ROOT
    / "Tunes" / "TuningBasicsGuide" / "TUNE_Basics_Guide_out"
    / "R04_20260708-211257" / "5G0906259L_0002_BasicsGuide_R04.bin"
)
OUT_CSV = LOG_DIR / "wg_tables_r05_ballpark.csv"

WG_SYMBOLS = ("IP_FAC_BPA_SP[0]", "IP_FAC_BPA_SP[1]")
WG_TITLE = "Wastegate Position Feedforward"

# Edited X axis (Exh FF). Stock last breakpoint 1.25 -> 1.40 so logged Exh FF
# 1.33 interpolates between the 1.00 and 1.40 columns instead of clamping.
EDITED_X = np.array([
    0.0, 0.25, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60,
    0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 1.00, 1.40,
])
# Y axis (Int FF) left stock.
STOCK_Y = np.array([0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50])


def _apply_ballpark(stock: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (edited_cells, delta) for one WG table.

    stock is (10, 16) with Y=Int FF rows, X=Exh FF cols. Lowers cells in the
    two overboost regions and blends neighbors. Returns edited values + the
    signed delta vs stock.
    """
    edited = np.array(stock, dtype=np.float64, copy=True)

    # Column index map for the edited X axis (same count/order as stock).
    # 0:.00 1:.25 2:.35 3:.40 4:.45 5:.50 6:.55 7:.60 8:.65 9:.70
    # 10:.75 11:.80 12:.85 13:.90 14:1.00 15:1.40(was 1.25)
    # Row index map (Int FF):
    # 0:.00 1:.15 2:.30 3:.45 4:.60 5:.75 6:.90 7:1.05 8:1.25 9:1.50

    # Region A — spool corner. Exh 0.75-0.90 (cols 10-13) x Int 0.60-0.90 (rows 4-6).
    # PUT error +11 to +22 kPa -> ~0.08-0.12 lower (guide: ~0.05 per 1 psi / ~7 kPa).
    A_delta = {
        (4, 10): -0.09, (4, 11): -0.09, (4, 12): -0.09, (4, 13): -0.09,
        (5, 10): -0.09, (5, 11): -0.09, (5, 12): -0.09, (5, 13): -0.09,
        (6, 10): -0.08, (6, 11): -0.08, (6, 12): -0.08, (6, 13): -0.08,
    }

    # Region B — top-end. Exh 1.00 (col 14) and 1.40 (col 15) x Int 0.90-1.50 (rows 6-9).
    # PUT error +10 to +16 kPa sustained, WG integral saturating. Lower ~0.05-0.10,
    # heavier at the far corner. Col 15 (was 1.25, now 1.40) also drops because it
    # now represents higher flow.
    B_delta = {
        (6, 14): -0.05, (6, 15): -0.065,
        (7, 14): -0.055, (7, 15): -0.07,
        (8, 14): -0.045, (8, 15): -0.06,
        (9, 14): -0.035, (9, 15): -0.04,
    }

    # Blend neighbors (~half delta) to avoid WG-position cliffs.
    blend = {
        # Below Region A (Int 0.45, row 3) at Exh 0.75-0.90.
        (3, 10): -0.03, (3, 11): -0.03, (3, 12): -0.03, (3, 13): -0.03,
        # Below Region B (Int 0.75, row 5) at Exh 1.00 & 1.40.
        (5, 14): -0.03, (5, 15): -0.035,
        # Left of Region A (Exh 0.70, col 9) at Int 0.60-0.90.
        (4, 9): -0.035, (5, 9): -0.035, (6, 9): -0.03,
    }

    all_deltas = {**A_delta, **B_delta, **blend}
    for (r, c), d in all_deltas.items():
        edited[r, c] += d
        # Clamp at physical floor (WG fully open = 0).
        edited[r, c] = max(edited[r, c], 0.0)

    delta = edited - np.array(stock, dtype=np.float64)
    return edited, delta


def _fmt_row(label, values) -> list:
    out = [f"{label:.2f}"]
    out.extend(f"{v:.3f}" for v in values)
    return out


def write_csv(tables: dict[str, dict], path: Path) -> None:
    """Write both edited WG tables + deltas to one stacked, labeled CSV."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow([
            "Draft R05 wastegate feedforward edits — ballpark from BasicsGuide_R04 log",
        ])
        w.writerow([
            "Tables: IP_FAC_BPA_SP[0]/[1] — Wastegate Position Feedforward VVL 0/1",
        ])
        w.writerow([
            "Cells = WG position (1=closed, 0=open). Overboost -> lower (open WG).",
        ])
        w.writerow([
            "X axis re-breakpoint: last column 1.25 -> 1.40 (logged Exh FF 1.33",
            "interpolates 1.00<->1.40 instead of clamping at 1.25).",
        ])
        w.writerow([])
        for sym, data in tables.items():
            w.writerow([f"### {sym} — {WG_TITLE}"])
            w.writerow(["axis_x (Exh FF) edited:", *[f"{x:.2f}" for x in data["x"]]])
            w.writerow(["axis_y (Int FF) stock:", *[f"{y:.2f}" for y in data["y"]]])
            w.writerow([])
            w.writerow(["EDITED CELLS — Y(Int)\\\\X(Exh)", *[f"{x:.2f}" for x in data["x"]]])
            for i, y in enumerate(data["y"]):
                w.writerow(_fmt_row(float(y), data["edited"][i]))
            w.writerow([])
            w.writerow(["DELTA vs R04 (edited - stock)"])
            w.writerow(["Y(Int)\\\\X(Exh)", *[f"{x:.2f}" for x in data["x"]]])
            for i, y in enumerate(data["y"]):
                row = [f"{float(y):.2f}"]
                row.extend(f"{d:+.3f}" for d in data["delta"][i])
                w.writerow(row)
            w.writerow([])


def main() -> None:
    cal = CalFile.open(XDF_PATH, BIN_PATH)
    tables: dict[str, dict] = {}
    for sym in WG_SYMBOLS:
        view = cal.get(sym)
        x = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
        y = np.asarray(view.axis_values("y"), dtype=np.float64).ravel()
        stock = np.array(view.values, dtype=np.float64)
        edited, delta = _apply_ballpark(stock)
        tables[sym] = {"x": EDITED_X, "y": STOCK_Y, "stock": stock, "edited": edited, "delta": delta}

    write_csv(tables, OUT_CSV)

    # Console summary: confirm the two tables' edits match, and print the
    # max delta per region so the ballpark is reviewable at a glance.
    print(f"Wrote {OUT_CSV}")
    for sym, data in tables.items():
        d = data["delta"]
        nz = np.argwhere(np.abs(d) > 1e-9)
        print(f"\n{sym}: {len(nz)} cells changed, max delta {d.min():+.3f}")
        # Report the two target regions explicitly.
        a_cols = slice(10, 14)
        b_cols = slice(14, 16)
        print(f"  Region A (Exh 0.75-0.90 x Int 0.60-0.90): "
              f"delta range [{d[4:7, a_cols].min():+.3f}, {d[4:7, a_cols].max():+.3f}]")
        print(f"  Region B (Exh 1.00-1.40 x Int 0.90-1.50): "
              f"delta range [{d[6:10, b_cols].min():+.3f}, {d[6:10, b_cols].max():+.3f}]")
    # Sanity: the same delta pattern should apply to both tables.
    if np.allclose(tables[WG_SYMBOLS[0]]["delta"], tables[WG_SYMBOLS[1]]["delta"]):
        print("\nVVL 0 and VVL 1 received identical deltas (guide: apply to both).")
    else:
        print("\nWARNING: VVL 0 / VVL 1 deltas differ — review.")


if __name__ == "__main__":
    main()
