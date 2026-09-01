"""Plot every map slot's boost cap against engine speed, read off the R22 bin.

R22 reordered the slot ladder by **fuel requirement** rather than by boost, and
that reorder is hard to hold in your head from the REV_LOG table alone: two
slots swapped curves, two slots now share one curve exactly, and the pair that
matters for the experiment differs by only ~1.6 psi. This draws the ladder.

Every curve is read off the flashed candidate bin's own `PUT setpoint` — map
slot boost cap grid rather than restated from the revision script, so the plot
is evidence about the bin and not a redrawing of the author's intent. The grids
are 8 x 12 with an uncharacterized Y axis and the lineage tiles one rpm curve
across all eight rows; that row-uniformity is asserted here, because a grid that
was not uniform would have no single curve to plot.

Two panels, because they answer two different questions:

* the ladder — all five slots, coloured by whether the slot is safe on pump 92
  or requires the VP Octanium dose;
* the experiment — how far the reduced-boost arm (slot 4) sits under the
  reduced-timing arm (slot 5), which is the only difference between them
  besides two columns of ignition timing.

Run from anywhere:

    Code/.venv/bin/python Tunes/MainTune/plot_r22_slot_boost.py

Writes into the R22 run folder's own `compare_slots/`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from simoscal import CalFile, structure_of
from simoscal.tune.profiles.switchpatch_2933 import S50_PUT_GRID_UIDS
from simoscal.tune.units import AMBIENT_HPA, psi_from_hpa


REPO_ROOT = Path(__file__).resolve().parents[2]
SWITCH_XDF = (REPO_ROOT / "BinToolz-main" / "definitions"
              / "S50 Switch Patch.29.33.V2.xdf")
R22_RUN = (REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
           / "R22_20260901-060746")
R22_BIN = R22_RUN / "Patched_259L_R22.bin"
OUT_DIR = R22_RUN / "compare_slots"

CONTROL_SLOT, MID_BOOSTER_SLOT, BOOSTER_SLOT = 3, 4, 5

#: One entry per slot: display label, colour, line style, line width, z-order.
#: Pump-safe slots are cool-toned and the two dosed-tank slots are warm, so the
#: fuel boundary R22 built the ladder around is visible before you read a word.
#: Two pairs of slots share a curve over part of the range — slots 3 and 5
#: everywhere, and slots 1 and 2 at 4400 rpm and above — so in each pair the
#: slot that *changed* in R22 is drawn dashed on top of the other's solid line
#: rather than hiding underneath it.
SLOT_STYLE = {
    1: ("slot 1 — \"stock\" · ~21.6 psi below 4400 rpm, then slot 2's curve "
        "(17.2 psi at redline) · pump 92", "0.25", (0, (4, 3)), 1.8, 6),
    2: ("slot 2 — conservative · pump 92", "tab:cyan", "-", 1.6, 2),
    3: (f"slot {CONTROL_SLOT} — aggressive · pump 92 · CONTROL + fallback",
        "tab:blue", "-", 2.6, 3),
    4: (f"slot {MID_BOOSTER_SLOT} — mid + R20 timing · DOSED · reduced-boost arm",
        "tab:orange", "-", 2.6, 4),
    5: (f"slot {BOOSTER_SLOT} — aggressive + R21 timing · DOSED · "
        "reduced-timing arm (same curve as slot 3)",
        "tab:red", "--", 2.2, 5),
}


#: Where each slot's peak-value label is drawn, as (breakpoint index, dx, dy) in
#: points. Several slots share a peak breakpoint — slots 2 and 4 both top out at
#: 3000 rpm, slots 3 and 5 at 3400 — so placing every label at argmax would
#: stack them on top of each other. Each is moved to a breakpoint where its own
#: curve is unobstructed instead; the value printed is that breakpoint's, which
#: for a flat-topped curve is still the peak.
PEAK_LABEL_AT = {
    1: (3, 0, 10),        # peaks at 3800 rpm, then follows slot 2 down
    2: (0, -14, 10),      # peaks at 3000 rpm, shared with slot 4
    3: (2, 0, 10),        # peaks at 3400 rpm, under slot 5's dashed line
    4: (4, 0, -18),       # flat 3000-4400; labelled at 4400, below the curve
    5: (2, 0, -18),       # same peak as slot 3, moved below it
}


def _slot_curve(cal: CalFile, slot: int) -> tuple[np.ndarray, np.ndarray]:
    """One slot's boost cap as (rpm, hPa absolute), with row-uniformity checked."""
    view = cal.get(int(S50_PUT_GRID_UIDS[slot], 16))
    grid = np.asarray(view.values, dtype=np.float64)
    rpm = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
    if grid.ndim != 2 or grid.shape[1] != rpm.size:
        raise RuntimeError(
            f"`PUT setpoint` — map slot {slot} boost cap is {grid.shape} "
            f"against a {rpm.size}-point rpm axis"
        )
    if not np.all(grid == grid[0]):
        raise RuntimeError(
            f"`PUT setpoint` — map slot {slot} boost cap is not uniform across "
            "its eight Y rows, so it has no single curve to plot"
        )
    return rpm, grid[0].copy()


def _plot(rpm: np.ndarray, curves: dict[int, np.ndarray]) -> Path:
    fig = Figure(figsize=(11.0, 8.4))
    top, bottom = fig.subplots(
        2, 1, sharex=True, height_ratios=(2.5, 1.0),
        gridspec_kw={"hspace": 0.12},
    )

    # -- the ladder ---------------------------------------------------------- #
    # Shade the gap between the two octane arms first, so it reads as the
    # background the curves sit on rather than another series.
    top.fill_between(
        rpm, psi_from_hpa(curves[MID_BOOSTER_SLOT]),
        psi_from_hpa(curves[BOOSTER_SLOT]),
        color="tab:orange", alpha=0.10, zorder=1,
        label=f"the experiment: slot {MID_BOOSTER_SLOT} vs slot {BOOSTER_SLOT}",
    )
    for slot in sorted(curves):
        label, color, style, width, z = SLOT_STYLE[slot]
        top.plot(rpm, psi_from_hpa(curves[slot]), marker="o", markersize=4,
                 linewidth=width, color=color, linestyle=style, zorder=z,
                 label=label)
        # Slots 2 and 4 both peak at 3000 rpm and slots 3 and 5 both at 3400,
        # so the peak label is placed at a per-slot breakpoint chosen to keep
        # the four annotations apart rather than at argmax for every slot.
        index, dx, dy = PEAK_LABEL_AT[slot]
        top.annotate(f"{psi_from_hpa(curves[slot])[index]:.1f} psi",
                     (rpm[index], psi_from_hpa(curves[slot])[index]),
                     textcoords="offset points", xytext=(dx, dy),
                     ha="center", fontsize=8, color=color, fontweight="bold")

    # Headroom under the lowest curve so the legend sits in empty space rather
    # than on top of slot 2 where it runs down to 17.2 psi.
    low = min(float(psi_from_hpa(c).min()) for c in curves.values())
    high = max(float(psi_from_hpa(c).max()) for c in curves.values())
    top.set_ylim(low - 0.30 * (high - low), high + 0.06 * (high - low))
    top.set_ylabel("Boost cap (psi gauge)", fontweight="bold")
    top.set_title(
        "R22 map slot boost caps — `PUT setpoint` — map slot boost cap, read "
        f"off {R22_BIN.name}\n"
        "Slots 1-3 are safe on pump 92; slots 4 and 5 require the VP Octanium "
        "dose. The effective target is min(base ceiling, slot grid).",
        fontsize=10)
    top.minorticks_on()
    top.grid(True, which="both", alpha=0.3)
    top.legend(fontsize=8, loc="lower left", framealpha=0.92)

    # Absolute pressure on the right, since the tables themselves store hPa.
    mirror = top.secondary_yaxis(
        "right",
        functions=(lambda p: p * 68.9476 + AMBIENT_HPA,
                   lambda h: (h - AMBIENT_HPA) / 68.9476),
    )
    mirror.set_ylabel("hPa absolute (as stored)", fontweight="bold")
    mirror.minorticks_on()

    # -- the experiment ------------------------------------------------------ #
    gap_hpa = curves[BOOSTER_SLOT] - curves[MID_BOOSTER_SLOT]
    gap_psi = gap_hpa / 68.9476
    bottom.fill_between(rpm, 0.0, gap_psi, color="tab:orange", alpha=0.18)
    bottom.plot(rpm, gap_psi, marker="o", markersize=4, linewidth=2.0,
                color="tab:orange")
    for x, psi, hpa in zip(rpm, gap_psi, gap_hpa):
        bottom.annotate(f"{hpa:.0f}", (x, psi), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=8,
                        color="tab:orange")
    # The knock band R20's logs indicted, and the reason the gap is sized here.
    bottom.axvspan(4400.0, 5000.0, color="tab:red", alpha=0.10)
    # Along the floor, where the delta curve and its hPa annotations are not.
    bottom.annotate("4400-5000 rpm — the band R20 knocked in",
                    (4700.0, 0.0), ha="center", va="bottom",
                    fontsize=8, color="tab:red",
                    textcoords="offset points", xytext=(0, 6))
    bottom.axhline(0.0, color="0.6", linewidth=0.8)
    bottom.set_xlabel("Engine speed (rpm)", fontweight="bold")
    bottom.set_ylabel(f"slot {BOOSTER_SLOT} − slot {MID_BOOSTER_SLOT}\n"
                      "(psi; hPa annotated)", fontweight="bold")
    bottom.minorticks_on()
    bottom.grid(True, which="both", alpha=0.3)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "R22 map slot boost caps.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    return path


def main() -> None:
    if not R22_BIN.is_file():
        raise SystemExit(f"Missing the R22 bin: {R22_BIN}")

    cal = CalFile.open(
        str(SWITCH_XDF), str(R22_BIN), structure=structure_of(R22_BIN)
    )
    rpm_axis = None
    curves: dict[int, np.ndarray] = {}
    for slot in sorted(SLOT_STYLE):
        rpm, curve = _slot_curve(cal, slot)
        if rpm_axis is None:
            rpm_axis = rpm
        elif not np.array_equal(rpm, rpm_axis):
            raise RuntimeError(
                f"map slot {slot} is on a different rpm axis from slot 1; the "
                "five slot grids are supposed to share one axis table"
            )
        curves[slot] = curve

    print(f"Read off {R22_BIN}")
    header = "  rpm  " + "".join(f"{r:>7.0f}" for r in rpm_axis)
    print(header)
    for slot, curve in curves.items():
        print(f"slot {slot} " + "".join(f"{v:>7.0f}" for v in curve)
              + f"   peak {psi_from_hpa(curve).max():5.2f} psi")
    gap = curves[BOOSTER_SLOT] - curves[MID_BOOSTER_SLOT]
    print(f"slot {BOOSTER_SLOT} − slot {MID_BOOSTER_SLOT}: "
          f"{gap.min():.0f} to {gap.max():.0f} hPa "
          f"({gap.max() / 68.9476:.2f} psi maximum)")
    print(f"wrote {_plot(rpm_axis, curves)}")


if __name__ == "__main__":
    main()
