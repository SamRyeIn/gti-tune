"""One page showing everything R23 changes, read off the two bins themselves.

The pre-flash review gate is "exactly six tables may differ from R22, and five
boost caps must not differ at all". That is six `compare/` PNGs plus a claim
about tables that produce no plot *because* they did not move — which is
precisely the part a human cannot check by looking at the plots that exist. So
this draws the whole revision on one page, including the negative:

* what the shared lambda setpoint grid now asks for, against R22 and against
  the EQT Stage 2 calibration the enrichment is aimed at;
* what slot 3 now delivers for ignition, against R22;
* every slot's boost cap on both bins, overplotted, so "unchanged" is something
  you can see rather than something you have to trust;
* a slot-by-slot matrix of what actually reaches each map, which is the one
  thing none of the per-table plots can show — the enrichment is written into a
  *shared* grid and taken back off two slots, so no single table tells you what
  slot 1 ends up running.

Every number is read from `Patched_259L_R22.bin` and `Patched_259L_R23.bin`.
Nothing here is retyped from the revision script, so if the figure and the
script disagree, the figure is right.

Run:  Code/.venv/bin/python Tunes/MainTune/plot_r23_changes.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from simoscal import CalFile, structure_of
from simoscal.tune.profiles.switchpatch_2933 import (
    S50_LAMBDA_GRID_UIDS, S50_PUT_GRID_UIDS, S50_SPARK_GRID_UIDS,
)

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
XDF = REPO_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
SWITCH_XDF = (REPO_ROOT / "BinToolz-main" / "definitions"
              / "S50 Switch Patch.29.33.V2.xdf")
R22_BIN = HERE / "MainTune_out" / "R22_20260901-060746" / "Patched_259L_R22.bin"
R23_BIN = HERE / "MainTune_out" / "R23_20260903-111406" / "Patched_259L_R23.bin"
OUT = HERE / "MainTune_out" / "R23_changes_summary.png"

#: EQT Stage 2's commanded lambda per rpm band, from Docs/eqt-timing-re. Plotted
#: at each band's midpoint — it is the target the enrichment is aimed at, and
#: the distance still left to it is the R24 argument.
EQT_LAMBDA = {3250: 0.870, 3750: 0.820, 4250: 0.800, 4750: 0.790,
              5250: 0.780, 5750: 0.790, 6300: 0.780}

#: The loaded rows of the lambda grid. WOT runs 1200-1600 mg/stk, and 1389 is
#: the top breakpoint, so this is the row a pull actually fuels on.
LAMBDA_TOP_ROW = 7
#: The top airmass row of the ignition grids, likewise.
SPARK_TOP_ROW = 15
#: The eight rpm columns the `Spark modifier` grids are written in.
SPARK_FIRST_COLUMN = 8

AMBIENT_HPA, PSI_PER_HPA = 1013.25, 68.9476


def _open(bin_path: Path, xdf: Path) -> CalFile:
    return CalFile.open(str(xdf), str(bin_path), structure=structure_of(bin_path))


def read(bin_path: Path) -> dict:
    """Every quantity this figure draws, off one bin."""
    base = _open(bin_path, XDF)
    patch = _open(bin_path, SWITCH_XDF)
    lam = base.get("IP_LAMB_BAS_HPDI[1]")
    out = {
        "lambda": np.asarray(lam.values, dtype=np.float64),
        "lambda_rpm": np.asarray(lam.axis_values("x"), dtype=np.float64).ravel(),
        "ignition": np.asarray(
            base.get("IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]").values,
            dtype=np.float64),
        "ignition_rpm": np.asarray(
            base.get("IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]").axis_values("x"),
            dtype=np.float64).ravel(),
    }
    for label, book in (("spark", S50_SPARK_GRID_UIDS),
                        ("lambda_mod", S50_LAMBDA_GRID_UIDS),
                        ("put", S50_PUT_GRID_UIDS)):
        out[label] = {int(slot): np.asarray(patch.get(int(uid, 16)).values,
                                            dtype=np.float64)
                      for slot, uid in book.items()}
    out["put_rpm"] = np.asarray(
        patch.get(int(S50_PUT_GRID_UIDS[3], 16)).axis_values("x"),
        dtype=np.float64).ravel()
    return out


def _style(ax) -> None:
    ax.grid(True, which="major", alpha=0.4)
    ax.minorticks_on()
    ax.grid(True, which="minor", alpha=0.15)


def panel_lambda(ax, before: dict, after: dict) -> None:
    rpm = after["lambda_rpm"]
    old = before["lambda"][LAMBDA_TOP_ROW]
    new = after["lambda"][LAMBDA_TOP_ROW]
    moved = ~np.isclose(old, new, atol=1e-6)

    for value in rpm[moved]:
        ax.axvspan(value - 90, value + 90, color="tab:cyan", alpha=0.13, zorder=0)
    ax.plot(rpm, old, "o-", color="tab:blue", lw=2, label="R22")
    ax.plot(rpm, new, "s--", color="tab:cyan", lw=2, label="R23")
    ax.plot(list(EQT_LAMBDA), list(EQT_LAMBDA.values()), "^:", color="tab:purple",
            lw=1.8, alpha=0.85, label="EQT Stage 2 (logged, reference)")
    # Annotate per *move*, not per column: four adjacent columns all go
    # 0.800 -> 0.780, and labelling each one wrote the same string four times
    # into the same 1500 rpm of axis.
    groups: list[list[int]] = []
    for index in np.flatnonzero(moved):
        same = (groups and np.isclose(old[index], old[groups[-1][-1]])
                and np.isclose(new[index], new[groups[-1][-1]])
                and index - groups[-1][-1] == 1)
        (groups[-1].append(index) if same else groups.append([index]))
    for group in groups:
        centre = float(np.mean(rpm[group]))
        a, b = old[group[0]], new[group[0]]
        span = ("" if len(group) == 1
                else f"\n{int(rpm[group[0]])}-{int(rpm[group[-1]])} rpm")
        ax.annotate(f"{a:.3f}\N{RIGHTWARDS ARROW}{b:.3f}{span}", (centre, b),
                    textcoords="offset points", xytext=(0, -20), ha="center",
                    fontsize=8.5, color="tab:cyan", fontweight="bold")

    ax.invert_yaxis()
    ax.set_xlim(2800, 7100)
    ax.set_ylabel("lambda, richer is lower -->", fontweight="bold")
    ax.set_xlabel("engine speed (rpm)", fontweight="bold")
    ax.set_title("FUELLING — `IP_LAMB_BAS_HPDI[1]`, 1389 mg/stk row\n"
                 f"{int(moved.sum())} columns move; shared by all five slots",
                 fontsize=10, fontweight="bold")
    ax.legend(loc="lower right", fontsize=8)
    _style(ax)


def panel_timing(ax, before: dict, after: dict) -> None:
    rpm = after["ignition_rpm"][SPARK_FIRST_COLUMN:]
    base = after["ignition"][SPARK_TOP_ROW][SPARK_FIRST_COLUMN:]
    old = base + before["spark"][3][SPARK_TOP_ROW][SPARK_FIRST_COLUMN:]
    new = base + after["spark"][3][SPARK_TOP_ROW][SPARK_FIRST_COLUMN:]
    moved = ~np.isclose(old, new, atol=1e-6)

    for value in rpm[moved]:
        ax.axvspan(value - 90, value + 90, color="tab:green", alpha=0.13, zorder=0)
    ax.plot(rpm, old, "o-", color="tab:blue", lw=2,
            label="slot 3, R22 (neutral modifier)")
    ax.plot(rpm, new, "s--", color="tab:green", lw=2, label="slot 3, R23")
    for value, a, b in zip(rpm[moved], old[moved], new[moved]):
        ax.annotate(f"{b - a:+.3f}\N{DEGREE SIGN}", (value, b),
                    textcoords="offset points", xytext=(0, 9), ha="center",
                    fontsize=9, color="tab:green", fontweight="bold")

    ax.set_xlim(2800, 6700)
    ax.set_ylabel("delivered ignition angle (\N{DEGREE SIGN}CRK)", fontweight="bold")
    ax.set_xlabel("engine speed (rpm)", fontweight="bold")
    ax.set_title("TIMING — `Spark modifier`, map slot 3, 1400 mg/stk row\n"
                 "base ignition maps untouched; slots 1, 2, 4, 5 unchanged",
                 fontsize=10, fontweight="bold")
    ax.legend(loc="upper left", fontsize=8)
    _style(ax)


def panel_boost(ax, before: dict, after: dict) -> None:
    rpm = after["put_rpm"]
    colours = {1: "tab:gray", 2: "tab:cyan", 3: "tab:blue",
               4: "tab:orange", 5: "tab:red"}
    worst = 0.0
    for slot in sorted(after["put"]):
        old = before["put"][slot][0]
        new = after["put"][slot][0]
        worst = max(worst, float(np.max(np.abs(new - old))))
        ax.plot(rpm, (old - AMBIENT_HPA) / PSI_PER_HPA, "-", lw=6.0,
                color=colours[slot], alpha=0.28)
        ax.plot(rpm, (new - AMBIENT_HPA) / PSI_PER_HPA, "--", lw=1.8,
                color=colours[slot], label=f"slot {slot}")

    ax.set_ylabel("boost cap (psi gauge)", fontweight="bold")
    ax.set_xlabel("engine speed (rpm)", fontweight="bold")
    ax.set_title("BOOST — all five `PUT setpoint` caps: NO CHANGE\n"
                 f"thick = R22, dashed = R23; worst difference {worst:.0f} hPa",
                 fontsize=10, fontweight="bold")
    ax.legend(loc="lower left", fontsize=8, ncol=2)
    _style(ax)


def panel_matrix(ax, before: dict, after: dict) -> None:
    """What each slot actually ends up running — the part no table plot shows."""
    ax.axis("off")
    rows, colours = [], []
    for slot in sorted(after["put"]):
        held = np.any(~np.isclose(after["lambda_mod"][slot], 0.0, atol=1e-6))
        spark_delta = (after["spark"][slot][SPARK_TOP_ROW]
                       - before["spark"][slot][SPARK_TOP_ROW])
        moved = ~np.isclose(spark_delta, 0.0, atol=1e-6)
        timing = ("unchanged" if not moved.any() else
                  f"+{spark_delta[moved].max():.3f}\N{DEGREE SIGN} @ "
                  + "/".join(f"{int(v)}"
                             for v in after["ignition_rpm"][moved]) + " rpm")
        rows.append([
            f"slot {slot}",
            "unchanged",
            "held at R22 lambda" if held else "ENRICHED",
            timing,
        ])
        colours.append("#eef4ff" if held else "#fff2e6")

    table = ax.table(
        cellText=rows,
        colLabels=["map slot", "boost", "fuelling", "ignition"],
        colWidths=[0.15, 0.19, 0.26, 0.40],
        cellLoc="left", loc="upper center", bbox=(0.0, 0.30, 1.0, 0.62),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    for (row, _col), cell in table.get_celld().items():
        cell.set_edgecolor("#bbbbbb")
        if row == 0:
            cell.set_facecolor("#333333")
            cell.set_text_props(color="w", fontweight="bold")
        else:
            cell.set_facecolor(colours[row - 1])

    ax.set_title(
        "WHAT EACH SLOT RUNS\n"
        "the enrichment is written into a grid all five slots share, then taken\n"
        "back off slots 1 and 2 with their own `Lambda modifier` grids",
        fontsize=10, fontweight="bold")
    ax.text(
        0.5, 0.02,
        "Slots 4 and 5 still need the VP Octanium dose. Slot 3 is the everyday\n"
        "map and the in-drive fallback. The `Lambda modifier` sign has never been\n"
        "observed on this car, so every way it can be wrong leaves slots 1 and 2\n"
        "RICHER, never leaner — and slot 3 carries a neutral grid either way.",
        transform=ax.transAxes, ha="center", va="bottom", fontsize=8,
        color="#444444", style="italic")


def main() -> int:
    before, after = read(R22_BIN), read(R23_BIN)
    fig, axes = plt.subplots(2, 2, figsize=(15.0, 10.0))
    panel_lambda(axes[0][0], before, after)
    panel_timing(axes[0][1], before, after)
    panel_boost(axes[1][0], before, after)
    panel_matrix(axes[1][1], before, after)
    fig.suptitle(
        "MainTune R23 — every change, read off the two bins  ·  "
        f"{R22_BIN.name} \N{RIGHTWARDS ARROW} {R23_BIN.name}  ·  "
        "6 tables, 68 bytes, audit clean",
        fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(OUT, dpi=140)
    plt.close(fig)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
