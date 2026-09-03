"""Attribute each R22 pull to the map slot it was driven on.

R22's three-slot experiment only means anything if every pull is tied to the slot
that produced it, and **SimosTools logs no map-slot channel**. So the slot has to
be recovered from the calibration's own fingerprints, in two stages:

1. **Boost.** `PUT SP (kpa)` is the slot's `PUT setpoint` — map slot boost cap
   read straight back out of the ECU, so it is the map itself and not a control
   outcome. Fitting a pull's logged setpoint against each slot's curve — read off
   the flashed R22 bin, never retyped — separates slot 4 (mid, ~24.4 psi) from
   slots 3 and 5 (aggressive, ~26.0 psi). Slots 1 and 2 fall out the same way.
2. **Timing.** Slots 3 and 5 share one boost curve exactly, so boost cannot tell
   them apart. Their `Spark modifier` — map slot ignition offset differs by up to
   +3.750 CRK on the top two airmass rows, which lands in `Ign Table` — the
   table-derived ignition angle before knock correction. Comparing that channel
   across the aggressive-curve pulls at matched rpm and load splits the control
   from the reduced-timing map.

Fails loud rather than guessing: a pull whose boost fit does not clearly prefer
one curve is reported UNRESOLVED, not assigned.

Run:  Code/.venv/bin/python Logs/BasicsGuide_R22/slot_attribution.py
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from simoscal import CalFile, structure_of
from simoscal.analysis import load_logset, detect_pulls
from simoscal.tune.profiles.switchpatch_2933 import (
    S50_PUT_GRID_UIDS, S50_SPARK_GRID_UIDS,
)
from simoscal.tune.units import AMBIENT_HPA, psi_from_hpa

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = Path(__file__).resolve().parent
SWITCH_XDF = (REPO_ROOT / "BinToolz-main" / "definitions"
              / "S50 Switch Patch.29.33.V2.xdf")
R22_BIN = (REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
           / "R22_20260901-060746" / "Patched_259L_R22.bin")

#: A pull is attributed only if the best-fitting slot curve beats the runner-up
#: by this margin in RMS hPa. The two closest distinguishable curves (slot 4 vs
#: slot 5) are 110-123 hPa apart across the knock band, so a 25 hPa separation
#: is a wide gate that still refuses a genuinely ambiguous fit.
FIT_MARGIN_HPA = 25.0

#: Setpoint samples are only informative where the slot cap is actually binding.
#: Below this rpm the ECU is still ramping onto the cap and every slot agrees.
FIT_RPM_MIN = 3200.0

#: Loaded-WOT gate for the ignition comparison: the `Spark modifier` grid writes
#: only the top two airmass rows, so the offset appears in `Ign Table` only when
#: filling is up there.
IGN_LOADED_MIN = 1350.0

#: An offset at or below this is the neutral 0.000 grid — the control slot.
ZERO_OFFSET_MAX_DEG = 0.5
#: An offset at or above this is a live modifier grid — an octane slot. The gap
#: between the two is deliberate: a peak landing inside it is UNRESOLVED, not
#: rounded to the nearer side.
LIVE_OFFSET_MIN_DEG = 1.0

#: rpm bins for the ignition comparison, centred on the columns where the two
#: octane shapes differ (4000/4500) plus the shared apex as a control.
IGN_BINS = ((3800, 4200), (4200, 4700), (4700, 5300), (5300, 5800), (5800, 6300))


def slot_put_curve(cal: CalFile, slot: int) -> tuple[np.ndarray, np.ndarray]:
    """One slot's boost cap as (rpm, hPa absolute); row-uniformity asserted."""
    view = cal.get(int(S50_PUT_GRID_UIDS[slot], 16))
    grid = np.asarray(view.values, dtype=np.float64)
    rpm = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
    if grid.ndim != 2 or grid.shape[1] != rpm.size:
        raise RuntimeError(f"slot {slot} PUT grid {grid.shape} vs {rpm.size} rpm")
    if not np.all(grid == grid[0]):
        raise RuntimeError(f"slot {slot} PUT grid is not row-uniform")
    return rpm, grid[0].copy()


def slot_spark_top_row(cal: CalFile, slot: int) -> tuple[np.ndarray, np.ndarray]:
    """One slot's ignition offset along rpm, taken from the top airmass row."""
    view = cal.get(int(S50_SPARK_GRID_UIDS[slot], 16))
    grid = np.asarray(view.values, dtype=np.float64)
    rpm = np.asarray(view.axis_values("x"), dtype=np.float64).ravel()
    return rpm, grid[-1].copy()


@dataclass(frozen=True)
class SlotPull:
    """One detected pull with the map slot it was driven on (``None`` = unresolved)."""

    index: int
    file: str
    start_row: int
    end_row: int
    gear: int | None
    slot: int | None
    boost_slot: int          # best-fitting boost curve
    boost_margin_hpa: float  # how far the runner-up curve fit worse
    offsets: dict[str, float]  # median reconstructed ignition offset per rpm bin


def _load_curves(cal: CalFile):
    put_rpm, curves, sparks = None, {}, {}
    for slot in sorted(S50_PUT_GRID_UIDS):
        r, c = slot_put_curve(cal, int(slot))
        put_rpm = r if put_rpm is None else put_rpm
        curves[int(slot)] = c
    for slot in sorted(S50_SPARK_GRID_UIDS):
        _, row = slot_spark_top_row(cal, int(slot))
        sparks[int(slot)] = row
    return put_rpm, curves, sparks


def attribute() -> list[SlotPull]:
    """Attribute every pull in this folder to a map slot, or to ``None``.

    Stage 1 fits the logged `PUT SP` against each slot's boost cap. That alone
    resolves slot 4 (and would resolve slots 1 and 2), but slots 3 and 5 share
    one curve exactly. Stage 2 reconstructs the delivered ignition offset —
    ``Ign Avg - Ign Table + worst per-cylinder knock retard``, since `Ign Table`
    is the base map lookup and carries no slot modifier — and splits the
    aggressive-curve pulls on whether that offset is zero.
    """
    cal = CalFile.open(str(SWITCH_XDF), str(R22_BIN),
                       structure=structure_of(R22_BIN))
    put_rpm, curves, sparks = _load_curves(cal)

    logset = load_logset(LOG_DIR)
    by_name = {lf.name: lf for lf in logset}
    out: list[SlotPull] = []
    for p in detect_pulls(logset):
        lf = by_name[p.file]
        lo, hi = p.start_row, p.end_row
        g = lambda cid: lf.channel(cid)[lo:hi + 1]
        rpm, put_sp = g("rpm"), g("put_sp") * 10.0            # kPa -> hPa
        ign_tbl, ign_avg = g("ign_table"), g("ign_avg")
        air = g("airmass") * 1000.0                            # g -> mg/stk
        knock = np.nanmin(np.vstack([g(f"knock_{i}") for i in (1, 2, 3, 4)]), axis=0)

        m = np.isfinite(rpm) & np.isfinite(put_sp) & (rpm >= FIT_RPM_MIN)
        fits = {s: float(np.sqrt(np.mean((put_sp[m] - np.interp(rpm[m], put_rpm, c)) ** 2)))
                for s, c in curves.items()}
        order = sorted(fits, key=fits.get)
        boost_slot, margin = order[0], fits[order[1]] - fits[order[0]]

        offset = ign_avg - ign_tbl - knock   # knock_* are signed retard (<= 0)
        offsets = {}
        for a, b in IGN_BINS:
            sel = (rpm >= a) & (rpm < b) & (air >= IGN_LOADED_MIN) & np.isfinite(offset)
            offsets[f"{a}-{b}"] = float(np.median(offset[sel])) if sel.sum() >= 4 else float("nan")

        slot: int | None = None
        if margin >= FIT_MARGIN_HPA:
            # The boost fit is unambiguous. It can only land on a slot whose
            # curve is unique, which in R22 means 1, 2 or 4.
            slot = boost_slot
        else:
            # Slots 3 and 5 share a curve; the ignition offset separates them.
            live = [v for v in offsets.values() if np.isfinite(v)]
            if live:
                peak = max(live)
                if peak <= ZERO_OFFSET_MAX_DEG:
                    slot = 3
                elif peak >= LIVE_OFFSET_MIN_DEG:
                    slot = 5
        out.append(SlotPull(p.index, p.file, lo, hi, p.gear, slot, boost_slot,
                            margin, offsets))
    return out


def main() -> int:
    cal = CalFile.open(str(SWITCH_XDF), str(R22_BIN),
                       structure=structure_of(R22_BIN))
    put_rpm, curves, sparks = _load_curves(cal)

    print("Slot boost caps read off", R22_BIN.name, "(hPa absolute)")
    print("  rpm    " + "".join(f"{v:>7.0f}" for v in put_rpm))
    for slot in sorted(curves):
        print(f"  slot {slot} " + "".join(f"{v:>7.0f}" for v in curves[slot])
              + f"   peak {psi_from_hpa(curves[slot].max()):.2f} psi")
    print("\nSlot ignition offsets, top airmass row (deg CRK, 3000-6500 rpm)")
    for slot in sorted(sparks):
        print(f"  slot {slot} " + "".join(f"{v:>7.3f}" for v in sparks[slot][8:]))

    pulls = attribute()
    bins = list(pulls[0].offsets)
    print("\nAttribution")
    print(f"{'pull':>4} {'file':>9} {'gear':>4} {'boost fit':>10} {'margin':>7} "
          + "".join(f"{b:>11}" for b in bins) + "   SLOT")
    for sp in pulls:
        print(f"{sp.index:>4} {sp.file[-8:]:>9} {sp.gear:>4} {'slot '+str(sp.boost_slot):>10} "
              f"{sp.boost_margin_hpa:>7.0f} "
              + "".join(f"{sp.offsets[b]:>11.2f}" if np.isfinite(sp.offsets[b])
                        else f"{'-':>11}" for b in bins)
              + f"   {sp.slot if sp.slot else 'UNRESOLVED'}")
    for slot in (1, 2, 3, 4, 5):
        idx = [sp.index for sp in pulls if sp.slot == slot]
        if idx:
            print(f"  slot {slot}: {len(idx)} pulls -> {idx}")
    bad = [sp.index for sp in pulls if sp.slot is None]
    print(f"  UNRESOLVED: {bad}" if bad else "  all pulls attributed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
