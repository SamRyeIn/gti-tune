"""
Verify which switch-patch map slot each R14 WOT pull was driven on.

R14's only calibration change was the per-slot `PUT setpoint` — boost target
grid for map slot N (patch-added, addressed by uniqueid) reorder: slots
1 stock / 2 conservative / 3 intermediate / 4 aggressive, slot 5 valet. The
SimosTools log carries no active-slot channel, so slot identity is recovered
from the data: under the R09-proven min() semantics the logged
`PUT SP` — Pressure up throttle setpoint at full load IS the active slot's
curve, so matching logged PUT SP against the five curves read off the flashed
bin identifies the slot.

Reads the five curves live from the flashed bin (never transcribed), finds each
log's WOT window, and scores every pull against every slot.

Usage:
    python3 verify_slot_identity.py
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LOG_DIR = Path(__file__).resolve().parent
PLOT_DIR = LOG_DIR / "plots"
REPO_ROOT = LOG_DIR.parent.parent
BINTOOLZ = REPO_ROOT / "BinToolz-main"

sys.path.insert(0, str(REPO_ROOT / "Code"))
from simoscal import CalFile  # noqa: E402

#: The flashed R14 bin, named by this folder's `*.bin.txt` record.
FLASHED_BIN = (REPO_ROOT / "Tunes" / "TuningBasicsGuide" / "TUNE_Basics_Guide_out"
               / "R14_20260810-111002"
               / "CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin")
SWITCH_XDF = BINTOOLZ / "definitions" / "S50 Switch Patch.29.33.V2.xdf"

#: Per-slot `PUT setpoint` grid uniqueids and the shared RPM axis (verified
#: bindings, per simoscal/tune/profiles/switchpatch_2933.py).
SLOT_PUT_GRID_UIDS = {1: "0x7d41a", 2: "0x7d4da", 3: "0x7d59a",
                      4: "0x7d65a", 5: "0x7d71a"}
SLOT_RPM_AXIS_UID = "0x7d7dc"
SLOT_LABELS = {1: "stock (~21.6 psi)", 2: "conservative (~24.5 psi)",
               3: "intermediate (~24.5 psi held)", 4: "aggressive (~26 psi)",
               5: "valet (~10 psi)"}

PEDAL_WOT_THRESHOLD = 90.0   # %
RPM_MIN_FOR_MATCH = 3000.0   # slot axis starts here; below it the ECU clamps
AMBIENT_HPA = 1016.0         # documented reference (REV_LOG R09)
HPA_PER_PSI = 68.95


def read_slot_curves():
    """Full-load slot curves + shared rpm axis, read live off the flashed bin."""
    cal = CalFile.open(str(SWITCH_XDF), str(FLASHED_BIN))
    axis = np.asarray(cal.get(SLOT_RPM_AXIS_UID).values, dtype=np.float64).ravel()
    curves = {}
    for slot, uid in SLOT_PUT_GRID_UIDS.items():
        grid = np.asarray(cal.get(uid).values, dtype=np.float64)
        # The patch Y axis is uncharacterized, so the lineage tiles one curve
        # across all eight rows; assert that before taking a single row.
        assert np.allclose(grid, grid[0], atol=1.0), f"slot {slot} grid is not tiled"
        curves[slot] = grid[0]
    return axis, curves


def load_rows(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def wot_window(rows):
    """Longest contiguous WOT run, as (rpm, put_sp, put) arrays."""
    runs, current = [], []
    for row in rows:
        try:
            pedal = float(row["Pedal Pos (%)"])
            rpm = float(row["Engine Speed (rpm)"])
            put_sp = float(row["PUT SP (kpa)"])
            put = float(row["PUT (kpa)"])
        except (ValueError, KeyError):
            continue
        if pedal >= PEDAL_WOT_THRESHOLD:
            current.append((rpm, put_sp, put))
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)
    if not runs:
        return None
    best = max(runs, key=len)
    arr = np.asarray(best, dtype=np.float64)
    return arr[:, 0], arr[:, 1], arr[:, 2]


def score_against_slots(rpm, put_sp_kpa, axis, curves):
    """RMS error (hPa) of logged PUT SP against each slot curve, above 3000 rpm."""
    mask = rpm >= RPM_MIN_FOR_MATCH
    if mask.sum() < 5:
        return {}, 0
    r, sp_hpa = rpm[mask], put_sp_kpa[mask] * 10.0
    scores = {}
    for slot, curve in curves.items():
        expected = np.interp(r, axis, curve)
        scores[slot] = float(np.sqrt(np.mean((sp_hpa - expected) ** 2)))
    return scores, int(mask.sum())


def main():
    axis, curves = read_slot_curves()

    print("Slot curves read off the flashed bin (hPa absolute / psi gauge):")
    print("  rpm axis: " + ", ".join(f"{v:.0f}" for v in axis))
    for slot, curve in curves.items():
        psi = (curve - AMBIENT_HPA) / HPA_PER_PSI
        print(f"  slot {slot} {SLOT_LABELS[slot]:<32} "
              f"peak {curve.max():.0f} hPa ({psi.max():.1f} psi)")

    logs = sorted(LOG_DIR.glob("simostools-*.csv"))
    print(f"\nPer-log slot match (RMS of logged PUT SP vs each slot curve, hPa):")
    header = "  " + "file".ljust(32) + "n   " + "".join(
        f"slot{s}".rjust(9) for s in sorted(curves)) + "   best"
    print(header)

    matched = []
    for path in logs:
        win = wot_window(load_rows(path))
        if win is None:
            print(f"  {path.stem[:32]:<32} — no WOT window")
            continue
        rpm, put_sp, put = win
        scores, n = score_against_slots(rpm, put_sp, axis, curves)
        if not scores:
            print(f"  {path.stem[:32]:<32} — WOT window below {RPM_MIN_FOR_MATCH:.0f} rpm")
            continue
        best = min(scores, key=scores.get)
        runner = sorted(scores.values())[1]
        print(f"  {path.stem[:32]:<32} {n:<4d}"
              + "".join(f"{scores[s]:9.0f}" for s in sorted(scores))
              + f"   slot {best} ({runner / scores[best]:.1f}x next)")
        matched.append((path, rpm, put_sp, put, best))

    # Evidence plot: logged PUT SP over the five calibrated slot curves.
    fig, ax = plt.subplots(figsize=(10, 6.5))
    for slot, curve in curves.items():
        psi = (curve - AMBIENT_HPA) / HPA_PER_PSI
        ax.plot(axis, psi, marker="o", lw=2.2 if slot == 4 else 1.4,
                alpha=1.0 if slot == 4 else 0.55,
                label=f"slot {slot} — {SLOT_LABELS[slot]}")
    for path, rpm, put_sp, put, best in matched:
        m = rpm >= RPM_MIN_FOR_MATCH
        ax.scatter(rpm[m], (put_sp[m] * 10.0 - AMBIENT_HPA) / HPA_PER_PSI,
                   s=8, color="k", alpha=0.35, zorder=5)
    ax.scatter([], [], s=8, color="k", alpha=0.5, label="logged PUT SP (all WOT pulls)")
    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Boost target (psi gauge)", fontweight="bold")
    ax.set_title("R14 slot identity — logged PUT SP vs the five calibrated slot curves")
    ax.grid(True, which="major")
    ax.minorticks_on()
    ax.grid(True, which="minor", alpha=0.25)
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    out = PLOT_DIR / "r14_slot_identity.png"
    fig.savefig(out, dpi=140)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
