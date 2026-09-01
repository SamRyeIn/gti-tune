"""Plot delivered WOT ignition timing on map slot 4 against map slot 5.

The nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle maps
are shared by every slot, so neither one on its own shows what a slot commands.
What a slot delivers is **base + that slot's `Spark modifier` grid**, and R20 is
the first revision where those two sums differ.

So this composes the sum for each slot and hands the pair to the library's own
`compare_tables`, giving the same three-panel curves composite every build
report uses — A is slot 4, B is slot 5, and the delta panel is the R20 modifier
map, read back off the flashed bin rather than restated from the script.

Run from anywhere:

    Code/.venv/bin/python Tunes/MainTune/plot_r20_slot_timing.py

Writes into the R20 run folder's own `compare_slots/`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from simoscal import CalFile, structure_of
from matplotlib.figure import Figure

from simoscal.plot import RenderedTable, compare_tables, render_table
from simoscal.tune.profiles.switchpatch_2933 import S50_SPARK_GRID_UIDS


REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_ROOT = REPO_ROOT / "Code"

XDF_PATH = CODE_ROOT / "xdf" / "SC8S50.V1.0.xdf"
SWITCH_XDF = (REPO_ROOT / "BinToolz-main" / "definitions"
              / "S50 Switch Patch.29.33.V2.xdf")
R20_RUN = REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out" / "R20_20260831-062648"
R20_BIN = R20_RUN / "Patched_259L_R20.bin"
OUT_DIR = R20_RUN / "compare_slots"

#: The operative WOT base ignition map — low port flap, standard lift, cam node
#: [0][0]. Established in `Logs/BasicsGuide_R19/find_operative_ign_map.py`: port
#: flap is 0.00 % in 1795/1795 logged samples and valve lift 0 in 96.5 %, and all
#: nine cam-node grids are byte-identical, so this one grid is what the engine
#: runs on at WOT.
BASE_MAP = "IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]"

EVERYDAY_SLOT, BOOSTER_SLOT = 4, 5

#: The two airmass rows R20 writes — the only rows where the slots differ, and
#: the ones WOT actually runs on (a pull reaches ~1600 mg/stk, above the grid's
#: 1400 top breakpoint, and the two rows are written identically so the surface
#: is flat going into it).
WOT_ROWS = (14, 15)
#: The first rpm breakpoint R20 touches, and where the WOT detail plot starts.
WOT_FIRST_COLUMN = 8


def _slot_delivered(
    base: np.ndarray, patch_cal: CalFile, slot: int
) -> np.ndarray:
    """Base timing plus one slot's additive `Spark modifier` grid.

    The modifier is additive in °CRK onto whichever base map the ECU is on —
    see `knowledge/sc8s50-switchpatch-xdf.md` § Per-slot `Spark modifier`
    semantics for the evidence.
    """
    view = patch_cal.get(int(S50_SPARK_GRID_UIDS[slot], 16))
    modifier = np.asarray(view.values, dtype=np.float64)
    if modifier.shape != base.shape:
        raise RuntimeError(
            f"`Spark modifier` — map slot {slot} ignition offset is "
            f"{modifier.shape}, not the base map's {base.shape}; these grids "
            "are supposed to share the base map's own axis tables"
        )
    return base + modifier


def _plot_wot_rows(
    shape: RenderedTable, everyday: np.ndarray, booster: np.ndarray
) -> Path:
    """The WOT band on its own axes — the composite squashes it flat.

    `compare_tables` gives all three panels the same Y limits so their shapes
    can be compared directly, which is right for the whole map and wrong for
    this change: the offset is at most 3.75 °CRK against a map spanning 58, so
    the delta panel reads as a flat line at zero. Fourteen of the sixteen curves
    are identical between the slots anyway. This plots only what differs.
    """
    rpm = np.asarray(shape.x_labels, dtype=np.float64)[WOT_FIRST_COLUMN:]
    fig = Figure(figsize=(9.0, 5.0))
    ax = fig.add_subplot(1, 1, 1)
    # One colour per airmass row so a slot-4/slot-5 pair reads as a pair; the
    # dashed line is always the everyday slot.
    row_colors = {14: "tab:orange", 15: "tab:red"}
    for row in WOT_ROWS:
        load = shape.y_labels[row]
        color = row_colors[row]
        ax.plot(rpm, everyday[row][WOT_FIRST_COLUMN:], marker="o", markersize=4,
                linewidth=1.4, color=color, linestyle="--", alpha=0.55,
                label=f"slot {EVERYDAY_SLOT} — {load:g} mg/stk")
        ax.plot(rpm, booster[row][WOT_FIRST_COLUMN:], marker="o", markersize=4,
                linewidth=1.9, color=color,
                label=f"slot {BOOSTER_SLOT} — {load:g} mg/stk")
    for column, rpm_value in enumerate(rpm):
        offset = booster[15][WOT_FIRST_COLUMN + column] - everyday[15][WOT_FIRST_COLUMN + column]
        ax.annotate(f"{offset:+.3f}",
                    (rpm_value, booster[15][WOT_FIRST_COLUMN + column]),
                    textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8, color="tab:red")
    ax.axhline(0.0, color="0.6", linewidth=0.8)
    ax.set_xlabel("rpm", fontweight="bold")
    ax.set_ylabel(shape.units or "", fontweight="bold")
    ax.set_title(f"R20 delivered WOT timing — map slot {EVERYDAY_SLOT} vs map "
                 f"slot {BOOSTER_SLOT}\n{BASE_MAP} + per-slot `Spark modifier`",
                 fontsize=10)
    ax.minorticks_on()
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = OUT_DIR / "R20 delivered WOT timing — slot 4 vs slot 5.png"
    fig.savefig(path, dpi=200)
    return path


def main() -> None:
    if not R20_BIN.is_file():
        raise SystemExit(f"Missing the R20 bin: {R20_BIN}")

    base_cal = CalFile.open(
        str(XDF_PATH), str(R20_BIN), structure=structure_of(R20_BIN)
    )
    patch_cal = CalFile.open(
        str(SWITCH_XDF), str(R20_BIN), structure=structure_of(R20_BIN)
    )

    base_view = base_cal.get(BASE_MAP)
    shape = render_table(base_view)
    base = np.asarray(base_view.values, dtype=np.float64)

    everyday = _slot_delivered(base, patch_cal, EVERYDAY_SLOT)
    booster = _slot_delivered(base, patch_cal, BOOSTER_SLOT)

    # The composite takes its heading from A alone, so both tables carry the
    # same pair of labels — "map slot 4" over a slot-4-vs-slot-5 comparison
    # reads like the wrong plot. The title doubles as the file stem, so it
    # stays short enough to be a filename.
    heading = f"{BASE_MAP} + per-slot `Spark modifier`"
    subtitle = (f"R20 delivered timing — map slot {EVERYDAY_SLOT} (A) vs "
                f"map slot {BOOSTER_SLOT} (B)")

    def as_table(values: np.ndarray, slot: int) -> RenderedTable:
        return RenderedTable(
            symbol=heading,
            title=subtitle,
            units=shape.units,
            categories=(),
            x_labels=shape.x_labels,
            y_labels=shape.y_labels,
            x_units=shape.x_units,
            y_units=shape.y_units,
            values=values,
        )

    written = compare_tables(
        as_table(everyday, EVERYDAY_SLOT),
        as_table(booster, BOOSTER_SLOT),
        OUT_DIR,
        surface=False,
        a_bin_name=f"{R20_BIN.name} — map slot {EVERYDAY_SLOT} (everyday)",
        b_bin_name=f"{R20_BIN.name} — map slot {BOOSTER_SLOT} (octane-boosted)",
    )

    written = list(written) + [_plot_wot_rows(shape, everyday, booster)]

    delta = booster - everyday
    print(f"Base map: {BASE_MAP}")
    print(f"Slot {EVERYDAY_SLOT} vs slot {BOOSTER_SLOT}: "
          f"{int(np.count_nonzero(delta))} of {delta.size} cells differ, "
          f"{delta.min():+.3f} to {delta.max():+.3f} °CRK")
    rpm = np.asarray(shape.x_labels, dtype=np.float64)
    for row, label in ((14, shape.y_labels[14]), (15, shape.y_labels[15])):
        print(f"  {label:g} mg/stk delivered, slot {BOOSTER_SLOT}: "
              + ", ".join(f"{r:g}:{v:+.3f}"
                          for r, v in zip(rpm[8:], booster[row][8:])))
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
