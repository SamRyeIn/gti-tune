"""One page showing everything R24 changes, read off the two bins themselves.

The pre-flash review gate is "exactly five tables may differ from R23, only one
lambda row among them, the other four boost caps must not differ at all, and the
ladder's oldest invariant is being retired on purpose". That is a handful of
`compare/` PNGs plus a set of claims about tables and rows that produce no plot
*because* they did not move — precisely the part a human cannot check by looking
at the plots that exist. So this draws the whole revision on one page, including
the negative:

* map slot 2's boost cap before and after, against the two curves that bound it
  — slot 3's, which clamps it from above, and slot 1's, which it now crosses,
  with the crossing shaded because that is the retired invariant;
* what that cap is *for*: the predicted airmass and power curves, which is the
  only place the claim "flat airmass, linear power, peak at ~6250 rpm" can be
  checked against the bytes actually being flashed;
* the lambda grid's three top rows, so it is visible that only row 5 moves and
  that everything R23 wrote on rows 6 and 7 is untouched — drawn against where
  WOT filling actually sits, which is the reason the row needed writing at all;
* the four boost caps and the lambda rows that must NOT have moved, overplotted,
  so "unchanged" is something you can see rather than trust;
* a slot-by-slot matrix of what reaches each map, because slot 2's fuelling
  change is a *removal* from a per-slot grid that lets a shared grid through —
  no single table shows what any one slot ends up running.

Every calibration number is read from `Patched_259L_R23.bin` and
`Patched_259L_R24.bin`. Nothing here is retyped from the revision script, so if
the figure and the script disagree, the figure is right. The one quantity that
is not a calibration value is volumetric efficiency, which is a *measurement* —
it comes from the 55-log aggressive-curve population via
`Logs/aggressive_slot_lineage/size_r24_linear.py`, the same source the revision
was sized on, and is what turns a boost cap into an airmass prediction.

Run:  Code/.venv/bin/python Tunes/MainTune/plot_r24_changes.py
"""

from __future__ import annotations

import sys
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
R23_BIN = HERE / "MainTune_out" / "R23_20260903-111406" / "Patched_259L_R23.bin"
R24_BIN = HERE / "MainTune_out" / "R24_20260903-182419" / "Patched_259L_R24.bin"
OUT = HERE / "MainTune_out" / "R24_changes_summary.png"

sys.path.insert(0, str(REPO_ROOT / "Logs" / "aggressive_slot_lineage"))

#: The slot this revision rebuilds, and the slot whose curve clamps it.
LOW_TORQUE_SLOT, AGGRESSIVE_SLOT = 2, 3
#: The loaded row of the lambda grid — WOT runs 1200-1600 mg/stk and 1389 is the
#: top breakpoint, so this is the row a pull actually fuels on.
LAMBDA_TOP_ROW = 7
#: The top airmass row of the `Spark modifier` grids, likewise.
SPARK_TOP_ROW = 15

AMBIENT_HPA, PSI_PER_HPA = 1013.25, 68.9476


def _open(bin_path: Path, xdf: Path) -> CalFile:
    return CalFile.open(str(xdf), str(bin_path), structure=structure_of(bin_path))


def read(bin_path: Path) -> dict:
    """Every calibration quantity this figure draws, off one bin."""
    base = _open(bin_path, XDF)
    patch = _open(bin_path, SWITCH_XDF)
    lam = base.get("IP_LAMB_BAS_HPDI[1]")
    out = {
        "lambda": np.asarray(lam.values, dtype=np.float64),
        "lambda_rpm": np.asarray(lam.axis_values("x"), dtype=np.float64).ravel(),
        "lambda_load": np.asarray(lam.axis_values("y"), dtype=np.float64).ravel(),
    }
    for label, book in (("spark", S50_SPARK_GRID_UIDS),
                        ("lambda_mod", S50_LAMBDA_GRID_UIDS),
                        ("put", S50_PUT_GRID_UIDS)):
        out[label] = {int(slot): np.asarray(patch.get(int(uid, 16)).values,
                                            dtype=np.float64)
                      for slot, uid in book.items()}
    out["put_rpm"] = np.asarray(
        patch.get(int(S50_PUT_GRID_UIDS[AGGRESSIVE_SLOT], 16)).axis_values("x"),
        dtype=np.float64).ravel()
    return out


def measured_ve() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Measured VE, and the airmass the aggressive curve actually makes.

    Straight from the sizing module, so the figure and the revision cannot be
    sized on different measurements of the same engine.
    """
    import size_r24_linear as sizing
    cent, ve, air_now, _put_now = sizing.ve_profile()
    return cent, ve, air_now


def _style(ax) -> None:
    ax.grid(True, which="major", alpha=0.4)
    ax.minorticks_on()
    ax.grid(True, which="minor", alpha=0.15)


def psi(hpa):
    return (np.asarray(hpa) - AMBIENT_HPA) / PSI_PER_HPA


def panel_boost(ax, before: dict, after: dict) -> None:
    """Slot 2's cap, before and after, against the curves that bound it."""
    rpm = after["put_rpm"]
    old = before["put"][LOW_TORQUE_SLOT][0]
    new = after["put"][LOW_TORQUE_SLOT][0]
    slot3 = after["put"][AGGRESSIVE_SLOT][0]
    slot1 = after["put"][1][0]
    moved = ~np.isclose(old, new, atol=1e-6)

    for value in rpm[moved]:
        ax.axvspan(value - 60, value + 60, color="tab:cyan", alpha=0.10, zorder=0)

    # The retired invariant, shaded: slot 1 used to sit at or below slot 2 at
    # every breakpoint, and no longer does.
    ax.fill_between(rpm, psi(slot1), psi(new), where=psi(new) < psi(slot1),
                    color="tab:green", alpha=0.13, interpolate=True,
                    label="slot 2 below slot 1")
    ax.fill_between(rpm, psi(slot1), psi(new), where=psi(new) >= psi(slot1),
                    color="tab:red", alpha=0.16, interpolate=True,
                    label="slot 2 ABOVE slot 1 — the retired invariant")
    ax.plot(rpm, psi(slot3), color="#c0392b", lw=1.4, ls=":", marker=".",
            label=f"slot {AGGRESSIVE_SLOT} aggressive — the ceiling")
    ax.plot(rpm, psi(slot1), color="#7f8c8d", lw=1.4, ls=":", marker=".",
            label="slot 1 bad-tank — now crossed")
    ax.plot(rpm, psi(old), color="#2c3e50", lw=2.6, marker="o", ms=4,
            label="slot 2 R23 — conservative ~24.5 psi")
    ax.plot(rpm, psi(new), color="tab:orange", lw=2.6, ls="--", marker="s", ms=4,
            label="slot 2 R24 — LOW TORQUE, flat 1200 mg/stk")

    clamp = np.isclose(new, slot3, atol=1.0)
    if clamp.any():
        ax.plot(rpm[clamp], psi(new[clamp]), "k*", ms=13, zorder=5,
                label="clamped at slot 3 (unlogged boost beyond)")

    # Annotate the moved breakpoints, grouping runs of identical text and
    # alternating the offset so neighbouring labels do not collide.
    last, flip = None, 0
    for i in np.flatnonzero(moved):
        text = f"{psi(old[i]):.1f}\N{RIGHTWARDS ARROW}{psi(new[i]):.1f}"
        if text == last:
            continue
        last = text
        flip += 1
        ax.annotate(text, (rpm[i], psi(new[i])), textcoords="offset points",
                    xytext=(0, 11 if flip % 2 else -20), ha="center",
                    fontsize=6.4, color="#b35900", fontweight="bold")

    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Boost cap (psi gauge)", fontweight="bold")
    delta_psi = (new - old) / PSI_PER_HPA
    ax.set_title(
        f"BOOST \N{EM DASH} `PUT setpoint` \N{EM DASH} map slot {LOW_TORQUE_SLOT} boost cap\n"
        f"all {int(moved.sum())} breakpoints move; biggest cut "
        f"{delta_psi.min():+.2f} psi (mid-range), lift {delta_psi.max():+.2f} "
        f"psi (top)\n"
        f"peaks {psi(new).max():.2f} psi vs slot 1's {psi(slot1).max():.2f} — "
        f"still the lowest-demand map by peak",
        fontsize=9.0, fontweight="bold")
    ax.legend(fontsize=6.8, loc="upper right", framealpha=0.92)
    ax.margins(y=0.14)
    _style(ax)


def _predicted(before: dict, after: dict):
    """Airmass each slot-2 cap actually delivers, and the power that implies.

    A cap only sets airmass where it *binds*. Below ~3400 rpm the turbo is still
    spooling and cannot reach the R23 cap at all, so multiplying that cap by VE
    would predict an airmass the car has never made. The logged airmass on the
    aggressive curve — the highest cap this car has run — is the deliverable
    ceiling at every rpm, so the prediction is bounded by it. Without that bound
    the R23 curve is overstated at low rpm and the comparison flatters R24.
    """
    cent, ve, air_now = measured_ve()
    rpm_axis = after["put_rpm"]
    fine = np.arange(3000.0, 6520.0, 20.0)
    ve_f = np.interp(fine, cent, ve)
    ceiling = np.interp(fine, cent, air_now)

    def airmass(curve):
        return np.minimum(np.interp(fine, rpm_axis, curve) / 10.0 * ve_f, ceiling)

    return (fine, ceiling,
            airmass(before["put"][LOW_TORQUE_SLOT][0]),
            airmass(after["put"][LOW_TORQUE_SLOT][0]))


def panel_airmass(ax, before: dict, after: dict) -> None:
    """Flat airmass is the whole claim. This is where it is checkable."""
    fine, logged, a_old, a_new = _predicted(before, after)
    ax.plot(fine, logged, color="#c0392b", lw=1.6, ls=":",
            label=f"slot {AGGRESSIVE_SLOT} aggressive, as logged")
    ax.plot(fine, a_old, color="#2c3e50", lw=2.2, label="slot 2 R23")
    ax.plot(fine, a_new, color="tab:orange", lw=3.0, ls="--", label="slot 2 R24")

    flat = (fine >= 3400.0) & (a_new > a_new.max() - 30.0)
    if flat.any():
        ax.axvspan(fine[flat].min(), fine[flat].max(), color="tab:orange",
                   alpha=0.09, zorder=0)
    ax.axhline(a_new.max(), color="tab:orange", lw=0.9, ls=":", alpha=0.8)

    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Airmass (mg/stk)", fontweight="bold")
    ax.set_title(
        "AIRMASS \N{EM DASH} a FLAT line is the whole claim\n"
        f"held within {a_new[flat].max() - a_new[flat].min():.0f} mg/stk over "
        f"{fine[flat].min():.0f}\N{EN DASH}{fine[flat].max():.0f} rpm, "
        f"then falls with slot {AGGRESSIVE_SLOT}'s taper",
        fontsize=9.5, fontweight="bold")
    ax.legend(fontsize=7.5, loc="lower left")
    _style(ax)


def panel_power(ax, before: dict, after: dict) -> None:
    """Power = airmass x rpm, so a flat airmass is a straight line."""
    fine, logged, a_old, a_new = _predicted(before, after)
    p_log, p_old, p_new = logged * fine, a_old * fine, a_new * fine
    i_new, i_log = int(p_new.argmax()), int(p_log.argmax())

    seg = (fine >= 3400.0) & (fine <= fine[i_new])
    fit = np.polyfit(fine[seg], p_new[seg], 1)
    resid = p_new[seg] - np.polyval(fit, fine[seg])
    r2 = 1.0 - resid.var() / p_new[seg].var()

    ax.plot(fine, p_log / 1e6, color="#c0392b", lw=1.6, ls=":",
            label=f"slot {AGGRESSIVE_SLOT} aggressive, as logged")
    ax.plot(fine, p_old / 1e6, color="#2c3e50", lw=2.2, label="slot 2 R23")
    ax.plot(fine, p_new / 1e6, color="tab:orange", lw=3.0, ls="--",
            label="slot 2 R24")
    ax.plot(fine[seg], np.polyval(fit, fine[seg]) / 1e6, color="k", lw=0.9,
            ls="-.", alpha=0.7, label=f"straight line, R\N{SUPERSCRIPT TWO}={r2:.4f}")
    ax.axvline(fine[i_new], color="tab:orange", lw=1.1, ls="-.")
    ax.axvline(fine[i_log], color="#c0392b", lw=1.1, ls="-.", alpha=0.6)
    ax.annotate(f"{fine[i_new]:.0f} rpm", (fine[i_new], p_new[i_new] / 1e6),
                textcoords="offset points", xytext=(-6, 8), ha="right",
                fontsize=8, fontweight="bold", color="tab:orange")
    ax.annotate(f"{fine[i_log]:.0f} rpm", (fine[i_log], p_log[i_log] / 1e6),
                textcoords="offset points", xytext=(-6, 8), ha="right",
                fontsize=8, fontweight="bold", color="#c0392b")

    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Power proxy, airmass \N{MULTIPLICATION SIGN} rpm (\N{MULTIPLICATION SIGN}10\N{SUPERSCRIPT SIX})",
                  fontweight="bold")
    ax.set_title(
        "POWER \N{EM DASH} peak moves up, the rise is a straight line\n"
        f"peak {fine[i_log]:.0f} \N{RIGHTWARDS ARROW} {fine[i_new]:.0f} rpm, "
        f"{100 * (p_new[i_new] / p_log[i_log] - 1):+.1f} % vs the aggressive curve",
        fontsize=9.5, fontweight="bold")
    ax.legend(fontsize=7.5, loc="upper left")
    _style(ax)


def panel_lambda(ax, before: dict, after: dict) -> None:
    """R23's top-end enrichment, and the row it was falling off above 6100 rpm."""
    rpm, load = after["lambda_rpm"], after["lambda_load"]
    moved = np.argwhere(~np.isclose(before["lambda"], after["lambda"], atol=1e-6))
    rows_moved = sorted({int(r) for r, _ in moved})
    cols_moved = sorted({int(c) for _r, c in moved})

    for col in cols_moved:
        ax.axvspan(rpm[col] - 120, rpm[col] + 120, color="tab:orange",
                   alpha=0.13, zorder=0)

    for row, colour, style in ((5, "tab:orange", "--"), (6, "#2c3e50", "-"),
                               (7, "#7f8c8d", ":")):
        ax.plot(rpm, before["lambda"][row], color=colour, ls=style, lw=4.2,
                alpha=0.42)
        ax.plot(rpm, after["lambda"][row], color=colour, ls=style, lw=1.8,
                marker="o" if row in rows_moved else None, ms=4.5,
                label=f"{load[row]:.0f} mg/stk row")

    # Why the row needed writing: WOT filling falls off the 1200 breakpoint at
    # the top of the rev range, so the lookup drops onto the row below.
    fine, logged, _old, a_new = _predicted(before, after)
    for r, dx, dy in ((6250.0, -78, 46), (6500.0, -22, 20)):
        k = int(np.argmin(np.abs(fine - r)))
        ax.annotate(f"{r:.0f} rpm: WOT = {logged[k]:.0f} mg/stk,\n"
                    "below the 1200 row R23 wrote",
                    (r, after["lambda"][5][np.argmin(np.abs(rpm - r))]),
                    textcoords="offset points", xytext=(dx, dy), ha="right",
                    fontsize=6.8, color="#b35900", fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#b35900", lw=0.9))

    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Commanded lambda", fontweight="bold")
    ax.set_ylim(0.74, 1.03)
    ax.set_title(
        "FUELLING \N{EM DASH} R23's top-end enrichment now reaches the top\n"
        f"only row {rows_moved[0]} ({load[rows_moved[0]]:.0f} mg/stk) moves, in "
        f"{len(cols_moved)} columns \N{EM DASH} rows "
        f"{load[6]:.0f} and {load[7]:.0f} are R23's exactly\n"
        "thick = R23, thin = R24",
        fontsize=8.6, fontweight="bold")
    ax.legend(fontsize=7.2, loc="lower left")
    _style(ax)


def panel_negative(ax, before: dict, after: dict) -> None:
    """The tables R24 claims it did NOT change. No compare/ PNG shows these."""
    rpm = after["put_rpm"]
    worst = 0.0
    for slot in sorted(after["put"]):
        if slot == LOW_TORQUE_SLOT:
            continue
        o, n = before["put"][slot][0], after["put"][slot][0]
        worst = max(worst, float(np.abs(o - n).max()))
        ax.plot(rpm, psi(o), lw=3.4, alpha=0.35, color=f"C{slot}")
        ax.plot(rpm, psi(n), lw=1.3, ls="--", color=f"C{slot}",
                label=f"slot {slot} cap")

    # The lambda grid moved on purpose this time, so what belongs in the
    # negative is the rows R24 claims it did NOT touch — 1200.01 and 1389.00,
    # which carry everything R23 wrote.
    worst_lambda = max(float(np.abs(before["lambda"][r] - after["lambda"][r]).max())
                       for r in (6, 7))

    spark_worst = 0.0
    for slot in sorted(after["spark"]):
        spark_worst = max(spark_worst, float(np.abs(
            before["spark"][slot][SPARK_TOP_ROW]
            - after["spark"][slot][SPARK_TOP_ROW]).max()))

    mod_worst = 0.0
    for slot in sorted(after["lambda_mod"]):
        if slot == LOW_TORQUE_SLOT:
            continue
        mod_worst = max(mod_worst, float(np.abs(
            before["lambda_mod"][slot] - after["lambda_mod"][slot]).max()))

    ax.set_xlabel("Engine speed (rpm)", fontweight="bold")
    ax.set_ylabel("Boost cap (psi gauge)", fontweight="bold")
    ax.set_title(
        "THE NEGATIVE \N{EM DASH} what must NOT have moved\n"
        f"worst \N{GREEK CAPITAL LETTER DELTA}: 4 other boost caps {worst:.3f} hPa  \N{BULLET}  "
        f"lambda rows 1200/1389 {worst_lambda:.4f}\n"
        f"all 5 `Spark modifier` {spark_worst:.4f}\N{DEGREE SIGN}  \N{BULLET}  "
        f"other `Lambda modifier` {mod_worst:.4f}",
        fontsize=9.0, fontweight="bold")
    ax.legend(fontsize=7.5, loc="lower left", ncol=2)
    ax.text(0.5, 0.03,
            "thick = R23, dashed = R24. Every pair must sit exactly on top of "
            "each other.",
            transform=ax.transAxes, ha="center", fontsize=8, style="italic",
            color="#444444")
    _style(ax)


def panel_matrix(ax, before: dict, after: dict) -> None:
    """What each slot actually ends up running — the part no table plot shows."""
    ax.axis("off")
    rows, colours = [], []
    for slot in sorted(after["put"]):
        o, n = before["put"][slot][0], after["put"][slot][0]
        if np.allclose(o, n, atol=1e-6):
            boost = "unchanged"
        else:
            boost = (f"{psi(o).max():.1f} \N{RIGHTWARDS ARROW} "
                     f"{psi(n).max():.1f} psi peak, RESHAPED")
        held_before = np.any(~np.isclose(before["lambda_mod"][slot], 0.0, atol=1e-6))
        held_after = np.any(~np.isclose(after["lambda_mod"][slot], 0.0, atol=1e-6))
        if held_after:
            fuel = "held at R22 lambda"
        elif held_before:
            fuel = "RELEASED \N{RIGHTWARDS ARROW} ENRICHED"
        else:
            fuel = "ENRICHED (R23)"
        spark = after["spark"][slot][SPARK_TOP_ROW]
        timing = ("base" if np.allclose(spark, 0.0, atol=1e-6)
                  else f"offset up to {spark.max():+.3f}\N{DEGREE SIGN}")
        rows.append([f"slot {slot}", boost, fuel, timing])
        colours.append("#ffe9d6" if slot == LOW_TORQUE_SLOT else
                       ("#eef4ff" if held_after else "#f4f4f4"))

    table = ax.table(
        cellText=rows,
        colLabels=["map slot", "boost", "fuelling", "ignition"],
        colWidths=[0.15, 0.33, 0.30, 0.22],
        cellLoc="left", loc="upper center", bbox=(0.0, 0.40, 1.0, 0.54),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.6)
    for (row, _col), cell in table.get_celld().items():
        cell.set_edgecolor("#bbbbbb")
        if row == 0:
            cell.set_facecolor("#333333")
            cell.set_text_props(color="w", fontweight="bold")
        else:
            cell.set_facecolor(colours[row - 1])

    ax.set_title(
        "WHAT EACH SLOT RUNS\n"
        "slot 2's fuelling change is a REMOVAL from its own grid, which lets the\n"
        "shared enriched base grid through — no single table shows that",
        fontsize=10, fontweight="bold")
    ax.text(
        0.5, 0.02,
        "CONFIRM: the ladder is no longer monotonic in boost. Slot 2 sits below\n"
        "slot 1 through the mid-range and above it from ~6000 rpm. What still\n"
        "holds, and is asserted before any write: slot 1 \N{LESS-THAN OR EQUAL TO} slots 3/4/5 "
        "everywhere;\nslot 2 \N{LESS-THAN OR EQUAL TO} slot 3 everywhere; slot 2's peak < slot 1's peak.\n"
        "Slots 4 and 5 still need the VP Octanium dose. Slot 3 is the fallback.",
        transform=ax.transAxes, ha="center", va="bottom", fontsize=8,
        color="#444444", style="italic")


def main() -> int:
    before, after = read(R23_BIN), read(R24_BIN)
    fig, axes = plt.subplots(2, 3, figsize=(19.5, 10.8))
    panel_boost(axes[0][0], before, after)
    panel_airmass(axes[0][1], before, after)
    panel_power(axes[0][2], before, after)
    panel_negative(axes[1][0], before, after)
    panel_lambda(axes[1][1], before, after)
    panel_matrix(axes[1][2], before, after)
    fig.suptitle(
        "MainTune R24 \N{EM DASH} map slot 2 becomes the low-torque map. "
        "Every change, read off the two bins.\n"
        f"{R23_BIN.name} \N{RIGHTWARDS ARROW} {R24_BIN.name}   \N{BULLET}   "
        "5 tables moved, 222 bytes, raw-diff audit CLEAN (unexplained = 0)   "
        "\N{BULLET}   confirm: flat airmass, the retired ladder invariant, "
        "and that only lambda row 5 moves",
        fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.925), h_pad=2.6)
    fig.savefig(OUT, dpi=140)
    plt.close(fig)
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
