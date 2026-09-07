"""What this car actually does on an upshift — measured, then matched to the maps.

Sam asked what the shift "fart" calibration currently is, before anything is
changed. This answers it two ways and checks one against the other.

**From the bin.** Five tables run the shift torque intervention:

* ``IP_IGA_ADD_MIN_GS_REQ`` — Correction map for IGA_MIN_BAS_TMP in case of
  external request, and ``IP_IGA_ADD_MIN_GS_REQ_SPT`` — the same in Sport mode.
  Per the Funktionsrahmen (`IGSP, TQM - Minimum ignition angle`, fig. 48.7.15)
  these are looked up on ``N_32`` x ``MAF_FG_CYL_IGN_1`` — engine speed by
  airmass per cylinder — while ``LV_GS_DEC_ACT`` is set, and they lower the
  *floor* the ignition angle may be retarded to. They do not command retard by
  themselves; they permit it.
* ``ID_EFF_SCC_SP_MIN`` — Minimum efficiency setpoint for single cylinder
  shut-off in case of gear shift, and ``ID_EFF_SCC_SP_MIN_SPT`` — the same in
  Sport mode. Looked up on ``EFF_SCC_SP_THE`` x ``TRANS_TYP`` (FR § 70.19.2.3).
  A *minimum* on the efficiency setpoint, so a larger number cuts **fewer**
  cylinders.
* ``ID_NR_PAT_SCC`` — SCC pattern depending on SCC efficiency, which turns that
  efficiency into the number of cylinders shut off.

``TRANS_TYP`` is 4 for this car: the FR gives the mapping outright — "Vehicle
has DCT gearbox, TRANS_TYP = 4", with ``LDP_TRANS_TYP`` = DCT 4, MT_4x4 3, MT 2,
CVT 1, AT 0. So row 4 is the row that matters and the other four are dead.

**From the logs.** Every ``Logs/*/simostools-*.csv`` this car has produced, 121
sessions, is scanned for upshifts and the ignition trace around each one is
measured: how deep ``Ign Avg`` goes, for how long, and at what rpm and airmass.
The gear channel's indexing is decided by its header, per the project rule.

The two halves are then put on the same axes. The map value is *not* the
predicted floor — the ECU adds it to ``IGA_MIN_BAS_TMP``, which is not logged —
so the comparison is of shape and of which of the two maps, D or Sport, the
measured depth follows. That is the only way to tell from a log which drive mode
was selected, since the mode itself is not a channel.

Pooling 121 sessions across R01-R22 is only legitimate if the shift calibration
never moved, so that is asserted rather than assumed: all five tables are
compared byte-for-byte against the stock bin and the run fails if any differs.

Run:  Code/.venv/bin/python Logs/shift_fart_characterization/characterize_shift_fart.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from simoscal import CalFile, structure_of

HERE = Path(__file__).resolve().parent
LOGS = HERE.parent
REPO_ROOT = LOGS.parent

XDF = REPO_ROOT / "Code" / "xdf" / "SC8S50.V1.0.xdf"
#: The primary XDF does not define the drive-mode gating constants; the full
#: definition does, and they decide whether the Sport tables are reachable.
XDF_ALL = REPO_ROOT / "Code" / "xdf" / "SC8S50.ALL.xdf"
STOCK_BIN = REPO_ROOT / "Code" / "bin" / "5G0906259L__0002.bin"
FLASHED_BIN = (REPO_ROOT / "Tunes" / "MainTune" / "MainTune_out"
               / "R22_20260901-060746" / "Patched_259L_R22.bin")

MEDIA = REPO_ROOT / "knowledge" / "media" / "dsg-shift-fart-calibration"

#: The shift-intervention tables, by ID.
GS_D = "IP_IGA_ADD_MIN_GS_REQ"
GS_S = "IP_IGA_ADD_MIN_GS_REQ_SPT"
SCC_D = "ID_EFF_SCC_SP_MIN"
SCC_S = "ID_EFF_SCC_SP_MIN_SPT"
SCC_PATTERN = "ID_NR_PAT_SCC"
TABLES = (GS_D, GS_S, SCC_D, SCC_S, SCC_PATTERN)

#: FR: "Vehicle has DCT gearbox, TRANS_TYP = 4". This car is a DQ250 DSG.
TRANS_TYP_DCT = 4

#: `LF_DRIV_MOD` bit layout, from the title of
#: `CLF_STATE_N_MAX_CTL_DRIV_MOD` in the XDF.
DRIVE_MODES = ("NORMAL", "EFFICIENCY", "ICE", "SPORT", "OFFROAD", "SPORT+")

#: Which constant gates which Sport table. The retard maps and the SCC maps
#: are selected by *different* conditions, which is the whole point of
#: reading them: one of the two Sport tables can be live while the other is
#: unreachable.
GATES = {
    "CLF_DRIV_MOD_CONF_SPT_ACT": ("bitmask", "drive modes that select "
                                  f"{GS_S}"),
    "LC_IGA_ADD_MIN_GS_ACT_SPT": ("flag", f"{GS_S} path enabled at all"),
    "CLF_EFF_SCC_SP_DRIV_MOD": ("bitmask", "drive modes that select "
                                f"{SCC_S}"),
    "LC_EFF_SCC_SP_MIN_SPT_KD": ("flag", f"kickdown selects {SCC_S}"),
}

GEAR_ACTUAL = "Gear (gear)"
GEAR_ZERO_INDEXED = "Gear ()"

#: Seconds after the gear channel flips in which the intervention is looked for.
#: The DSG flips the channel several samples before the shift actually lands, so
#: the window opens at the flip and has to be long enough to contain the event.
WINDOW_S = 1.5
#: Seconds before the flip used as the un-intervened reference.
BASELINE_S = 0.6
#: A shift counts as intervened when `Ign Avg` drops at least this far below its
#: pre-flip baseline. Ordinary timing movement over 1.5 s is far smaller.
INTERVENTION_CRK = 8.0


def _column(header, *names):
    return next((n for n in names if n in header), None)


def load(path: Path) -> dict[str, np.ndarray] | None:
    """One log as float arrays, or ``None`` when it cannot answer the question."""
    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return None
    header = rows[0].keys()

    def col(name: str) -> np.ndarray:
        return np.asarray([float(r[name] or "nan") for r in rows], dtype=float)

    wanted = {
        "time": _column(header, "Time"),
        "rpm": _column(header, "Engine Speed (rpm)"),
        "airmass": _column(header, "Airmass (g/stk)"),
        "ign": _column(header, "Ign Avg (°)"),
        "ign_table": _column(header, "Ign Table (°)"),
        "pedal": _column(header, "Pedal Pos (%)"),
        "boost": _column(header, "Boost (psi)"),
        "fuel": _column(header, "Fuel Flow (mg/stk)"),
        "lambda": _column(header, "Lambda (l)"),
    }
    if any(v is None for v in wanted.values()):
        return None
    out = {key: col(name) for key, name in wanted.items()}

    # Gear: the header decides whether an offset is owed. Refused rather than
    # guessed — a silent wrong gear misattributes every shift in the session.
    if GEAR_ACTUAL in header:
        out["gear"] = col(GEAR_ACTUAL)
    elif GEAR_ZERO_INDEXED in header:
        out["gear"] = col(GEAR_ZERO_INDEXED) + 1.0
    else:
        raise RuntimeError(f"{path.name}: no recognised gear column")
    return out


def bilinear(table, x_axis, y_axis, x, y) -> float:
    """The ECU's own lookup: interpolate on both axes, clamp outside them."""
    xi = float(np.clip(np.interp(x, x_axis, np.arange(len(x_axis))),
                       0, len(x_axis) - 1))
    yi = float(np.clip(np.interp(y, y_axis, np.arange(len(y_axis))),
                       0, len(y_axis) - 1))
    c0, r0 = int(np.floor(xi)), int(np.floor(yi))
    c1, r1 = min(c0 + 1, len(x_axis) - 1), min(r0 + 1, len(y_axis) - 1)
    fx, fy = xi - c0, yi - r0
    return float(
        table[r0, c0] * (1 - fx) * (1 - fy) + table[r0, c1] * fx * (1 - fy)
        + table[r1, c0] * (1 - fx) * fy + table[r1, c1] * fx * fy
    )


def read_gating() -> dict:
    """The constants that decide whether the Sport tables are reachable.

    Reading these is not optional detail. `ID_EFF_SCC_SP_MIN_SPT` is selected by
    ``(LF_DRIV_MOD AND CLF_EFF_SCC_SP_DRIV_MOD) OR (LV_KD AND
    LC_EFF_SCC_SP_MIN_SPT_KD)`` (FR § 70.19.2.3, fig. 70.19.7), so if both
    constants are zero the Sport SCC table is dead calibration no matter which
    drive mode is selected — and the cylinder cut, which is the half of the
    intervention that decides the noise, is the D-mode table always.

    Caveat kept deliberately: that figure also carries a ``SEL_PSN_MSK``
    (selector-lever position) term, and the constant behind it,
    ``CLF_SEL_PSN_SCC_GS_PRMS_SPT``, is not defined in either XDF for this box
    code. So "both gates read zero" is what is proven here, not "no path
    exists".
    """
    cal = CalFile.open(str(XDF_ALL), str(FLASHED_BIN),
                       structure=structure_of(FLASHED_BIN))
    out = {}
    for name, (kind, meaning) in GATES.items():
        raw = int(np.asarray(cal.get(name).values, dtype=float).ravel()[0])
        modes = [DRIVE_MODES[i] for i in range(len(DRIVE_MODES))
                 if raw >> i & 1] if kind == "bitmask" else []
        out[name] = {"raw": raw, "kind": kind, "meaning": meaning,
                     "modes": modes}
    return out


def read_calibration() -> dict:
    """The five tables off the flashed bin, proven identical to stock."""
    flashed = CalFile.open(str(XDF), str(FLASHED_BIN),
                           structure=structure_of(FLASHED_BIN))
    stock = CalFile.open(str(XDF), str(STOCK_BIN),
                         structure=structure_of(STOCK_BIN))
    cal = {}
    for name in TABLES:
        view = flashed.get(name)
        values = np.asarray(view.values, dtype=float)
        reference = np.asarray(stock.get(name).values, dtype=float)
        delta = float(np.max(np.abs(values - reference)))
        if delta != 0.0:
            raise RuntimeError(
                f"{name} differs from stock by {delta} on {FLASHED_BIN.name}. "
                "The sessions pooled here span R01-R22 and are only one "
                "population while this table never moved."
            )
        entry = {"values": values,
                 "x": np.asarray(view.axis_values("x"), dtype=float).ravel()}
        try:
            entry["y"] = np.asarray(view.axis_values("y"), dtype=float).ravel()
        except Exception:
            entry["y"] = np.array([np.nan])
        cal[name] = entry
    return cal


def upshift_events(path: Path, cal: dict) -> list[dict]:
    """Every upshift in one log, with the ignition intervention measured."""
    data = load(path)
    if data is None:
        return []
    t, gear, ign = data["time"], data["gear"], data["ign"]
    flips = np.flatnonzero(np.diff(gear) > 0)
    events = []
    for i in flips:
        after = t >= t[i]
        window = after & (t <= t[i] + WINDOW_S)
        before = (t >= t[i] - BASELINE_S) & (t <= t[i])
        if window.sum() < 5 or before.sum() < 5:
            continue
        baseline = float(np.nanmedian(ign[before]))
        w = np.flatnonzero(window)
        k = int(w[np.nanargmin(ign[w])])
        depth = baseline - float(ign[k])
        if not np.isfinite(depth) or depth < INTERVENTION_CRK:
            continue
        airmass_mg = float(data["airmass"][k]) * 1000.0
        rpm = float(data["rpm"][k])
        below = w[ign[w] < baseline - INTERVENTION_CRK]
        fuel_before = float(np.nanmedian(data["fuel"][before]))
        fuel_ratio = (float(data["fuel"][k]) / fuel_before
                      if fuel_before > 1.0 else float("nan"))
        events.append({
            "session": path.parent.name,
            "log": path.name,
            "from_gear": float(gear[i]),
            "to_gear": float(gear[i + 1]),
            "t": float(t[k]),
            "rpm": rpm,
            "airmass_mg": airmass_mg,
            "pedal": float(data["pedal"][k]),
            "boost": float(data["boost"][k]),
            "baseline_crk": baseline,
            "min_ign_crk": float(ign[k]),
            "depth_crk": depth,
            "duration_s": float(t[below[-1]] - t[below[0]]) if below.size else 0.0,
            "fuel_before_mg": fuel_before,
            "fuel_at_min_mg": float(data["fuel"][k]),
            "fuel_ratio": fuel_ratio,
            "cyl_cut_est": 4.0 * (1.0 - fuel_ratio),
            "lambda_peak": float(np.nanmax(data["lambda"][w])),
            "map_d_crk": bilinear(cal[GS_D]["values"], cal[GS_D]["x"],
                                  cal[GS_D]["y"], rpm, airmass_mg),
            "map_sport_crk": bilinear(cal[GS_S]["values"], cal[GS_S]["x"],
                                      cal[GS_S]["y"], rpm, airmass_mg),
        })
    return events


def collect(cal: dict) -> list[dict]:
    events = []
    for path in sorted(LOGS.glob("*/simostools-*.csv")):
        events.extend(upshift_events(path, cal))
    return events


def cylinders_cut(cal: dict, efficiency: float) -> float:
    """`ID_NR_PAT_SCC` read as the pattern the efficiency setpoint selects."""
    pattern = cal[SCC_PATTERN]
    return float(np.interp(efficiency, pattern["x"], pattern["values"].ravel()))


def _grid(ax, title, xlabel, ylabel):
    ax.set_title(title)
    ax.set_xlabel(xlabel, fontweight="bold")
    ax.set_ylabel(ylabel, fontweight="bold")
    ax.grid(True, which="major", alpha=0.35)
    ax.grid(True, which="minor", alpha=0.15)
    ax.minorticks_on()


def figure(cal: dict, events: list[dict]) -> Path:
    rpm = np.array([e["rpm"] for e in events])
    airmass = np.array([e["airmass_mg"] for e in events])
    floor = np.array([e["min_ign_crk"] for e in events])
    pedal = np.array([e["pedal"] for e in events])
    ratio = np.array([e["fuel_ratio"] for e in events])
    lam = np.array([e["lambda_peak"] for e in events])

    fig = plt.figure(figsize=(17, 12))
    grid = fig.add_gridspec(2, 3, hspace=0.34, wspace=0.30)

    # Panels 1-2: the two retard maps, with every logged shift on top.
    for col, (name, label) in enumerate(
            ((GS_D, "D mode"), (GS_S, "Sport mode"))):
        ax = fig.add_subplot(grid[0, col])
        table = cal[name]
        mesh = ax.pcolormesh(table["x"], table["y"], table["values"],
                             cmap="viridis", shading="nearest", vmin=-21, vmax=0)
        fig.colorbar(mesh, ax=ax, label="floor offset (°CRK)")
        ax.scatter(rpm, airmass, s=18, c="white", edgecolors="black",
                   linewidths=0.5, zorder=3,
                   label=f"{len(events)} logged upshifts")
        _grid(ax, f"{name}\n{label} — how far the shift may retard",
              "engine speed (rpm)", "airmass (mg/stk)")
        ax.legend(loc="upper left", fontsize=8)

    # Panel 3: how deep the timing actually goes, against load.
    ax = fig.add_subplot(grid[0, 2])
    sc = ax.scatter(airmass, floor, c=pedal, cmap="plasma", s=26,
                    vmin=0, vmax=100)
    fig.colorbar(sc, ax=ax, label="pedal (%)")
    ax.axhline(0.0, color="black", lw=1)
    _grid(ax, "The retard is already deep everywhere\n"
              "one point per upshift, colour is pedal",
          "airmass at the minimum (mg/stk)", "minimum Ign Avg (°CRK)")

    # Panel 4: the cut — the half of the intervention that decides the noise.
    ax = fig.add_subplot(grid[1, 0])
    sc = ax.scatter(pedal, ratio, c=floor, cmap="coolwarm_r", s=30)
    fig.colorbar(sc, ax=ax, label="minimum Ign Avg (°CRK)")
    for cut, style in ((1, ":"), (2, "-."), (3, "--")):
        ax.axhline(1.0 - cut / 4.0, color="black", ls=style, lw=1.2)
        ax.text(2, 1.0 - cut / 4.0 + 0.015, f"{cut} of 4 cylinders cut",
                fontsize=8)
    ax.set_ylim(-0.05, 2.0)
    _grid(ax, "Fuel kept through the retard\n"
              "a lifted pedal keeps it; a WOT shift loses it",
          "pedal at the intervention (%)", "fuel flow / pre-shift fuel flow (-)")

    # Panel 5: the SCC floor, the thing that decides how many cylinders fire.
    ax = fig.add_subplot(grid[1, 1])
    d_floor = float(cal[SCC_D]["values"][TRANS_TYP_DCT].max())
    s_floor = float(cal[SCC_S]["values"][TRANS_TYP_DCT].max())
    pattern = cal[SCC_PATTERN]
    order = np.argsort(pattern["x"])
    ax.plot(pattern["x"][order], pattern["values"].ravel()[order],
            lw=2.5, marker="o", label=SCC_PATTERN)
    for value, label, colour in ((d_floor, "D mode floor", "tab:blue"),
                                 (s_floor, "Sport floor", "tab:red")):
        ax.axvline(value, color=colour, ls="--", lw=1.8,
                   label=f"{label} = {value:.2f} → "
                         f"{cylinders_cut(cal, value):.1f} cyl cut")
    _grid(ax, f"Cylinder cut permitted on the DCT row\n"
              f"(TRANS_TYP={TRANS_TYP_DCT}) — a HIGHER floor cuts FEWER",
          "efficiency setpoint for single cylinder shut-off (-)",
          "cylinders shut off")
    ax.legend(loc="upper right", fontsize=8)

    # Panel 6: the two maps on the row the logged shifts actually sit on.
    ax = fig.add_subplot(grid[1, 2])
    row = int(np.argmin(np.abs(cal[GS_D]["y"] - np.median(airmass))))
    row_mg = cal[GS_D]["y"][row]
    ax.plot(cal[GS_D]["x"], cal[GS_D]["values"][row], lw=2.5, marker="o",
            label=f"{GS_D} (D)")
    ax.plot(cal[GS_S]["x"], cal[GS_S]["values"][row], lw=2.5, marker="s",
            ls="--", label=f"{GS_S} (Sport)")
    _grid(ax, f"Both retard maps on the {row_mg:.0f} mg/stk row\n"
              "the median row the logged upshifts land on",
          "engine speed (rpm)", "floor offset (°CRK)")
    ax.legend(loc="lower left", fontsize=8)

    wot = pedal >= 90.0
    full_cut = int(np.sum(ratio[wot] == 0.0))
    fig.suptitle(
        "The DSG shift intervention as this car is calibrated today — stock on "
        f"every bin R01-R22, measured over {len(events)} upshifts in "
        f"{len({e['log'] for e in events})} logs, read from {FLASHED_BIN.name}\n"
        f"Timing is not the missing ingredient: the retard already reaches "
        f"{floor.min():.1f} °CRK. The fuel is — {full_cut} of "
        f"{int(wot.sum())} WOT shifts cut it completely (lambda off the top of "
        f"the logged range), while {int(np.sum(ratio[~wot] >= 0.5))} of "
        f"{int((~wot).sum())} part-throttle shifts keep theirs",
        fontsize=12)
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / "shift-fart-characterization.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def trace_figure(events: list[dict]) -> Path:
    """The two regimes side by side, in the time domain.

    Left: the deepest part-throttle intervention — timing dumped with the fuel
    still flowing, which is combustion arriving in the exhaust. Right: the
    deepest WOT one — the same timing, but the fuel gone and lambda through the
    roof, which is air arriving in the exhaust.
    """
    part = max((e for e in events if e["pedal"] < 60),
               key=lambda e: e["depth_crk"])
    # A WOT shift that cut the fuel outright, which is what 59 of the 79
    # WOT interventions in this population do — not one of the partial ones.
    wot = max((e for e in events
               if e["pedal"] >= 90 and e["fuel_ratio"] == 0.0),
              key=lambda e: e["depth_crk"])

    fig, axes = plt.subplots(3, 2, figsize=(15, 10), sharex="col")
    for col, (event, label) in enumerate(
            ((part, "part throttle"), (wot, "wide-open throttle"))):
        data = load(LOGS / event["session"] / event["log"])
        t = data["time"]
        window = (t >= event["t"] - 1.2) & (t <= event["t"] + 1.2)
        rel = t[window] - event["t"]

        ax = axes[0, col]
        ax.plot(rel, data["ign"][window], lw=2, label="Ign Avg")
        ax.plot(rel, data["ign_table"][window], lw=1.5, ls="--",
                label="Ign Table")
        ax.axhline(0, color="black", lw=1)
        _grid(ax, f"{label} — {event['session']}, "
                  f"{event['from_gear']:.0f}→{event['to_gear']:.0f} at "
                  f"{event['pedal']:.0f} % pedal",
              "", "ignition angle (°CRK)")
        ax.legend(loc="lower left", fontsize=8)

        ax = axes[1, col]
        ax.plot(rel, data["fuel"][window], lw=2, color="tab:red",
                label="Fuel Flow")
        _grid(ax, "", "", "fuel flow (mg/stk)")
        twin = ax.twinx()
        twin.plot(rel, data["lambda"][window], color="tab:blue", lw=1.5)
        twin.set_ylabel("lambda", fontweight="bold", color="tab:blue")
        ax.legend(loc="lower left", fontsize=8)

        ax = axes[2, col]
        ax.plot(rel, data["rpm"][window], lw=2, color="tab:green")
        _grid(ax, "", "seconds from the minimum ignition angle",
              "engine speed (rpm)")
        twin = ax.twinx()
        twin.step(rel, data["gear"][window], where="post", color="tab:gray",
                  lw=1.5)
        twin.set_ylabel("gear", fontweight="bold")

    fig.suptitle("Same retard, opposite exhaust event — fuel is what separates "
                 "a fart from a hiss", fontsize=13)
    fig.tight_layout()
    MEDIA.mkdir(parents=True, exist_ok=True)
    out = MEDIA / "shift-fart-two-regimes.png"
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    cal = read_calibration()
    gates = read_gating()
    events = collect(cal)
    if not events:
        raise RuntimeError("no intervened upshifts found")

    depth = np.array([e["depth_crk"] for e in events])
    floor = np.array([e["min_ign_crk"] for e in events])
    duration = np.array([e["duration_s"] for e in events])
    pedal = np.array([e["pedal"] for e in events])
    airmass = np.array([e["airmass_mg"] for e in events])
    ratio = np.array([e["fuel_ratio"] for e in events])
    lam = np.array([e["lambda_peak"] for e in events])
    wot = pedal >= 90.0

    d_floor = float(cal[SCC_D]["values"][TRANS_TYP_DCT].max())
    s_floor = float(cal[SCC_S]["values"][TRANS_TYP_DCT].max())

    print(f"{len(events)} intervened upshifts in "
          f"{len({e['log'] for e in events})} logs "
          f"({int(wot.sum())} at pedal >= 90 %)\n")
    print("  --- what the ignition does ---")
    print(f"  minimum Ign Avg   median {np.median(floor):7.2f}  "
          f"p05 {np.percentile(floor, 5):7.2f}  min {floor.min():7.2f} CRK")
    print(f"  retard depth      median {np.median(depth):7.2f}  "
          f"p95 {np.percentile(depth, 95):7.2f}  max {depth.max():7.2f} CRK")
    print(f"  time below floor  median {np.median(duration):7.3f}  "
          f"max {duration.max():7.3f} s")
    print(f"  airmass at event  median {np.median(airmass):7.0f} mg/stk\n")
    print("  --- what the fuel does (this is the part that makes noise) ---")
    for label, sel in (("WOT   (pedal >= 90 %)", wot),
                       ("part  (pedal <  90 %)", ~wot)):
        print(f"  {label}  n={int(sel.sum()):3d}  fuel kept "
              f"{np.nanmedian(ratio[sel]):5.0%}  "
              f"~{4 * (1 - np.nanmedian(ratio[sel])):4.1f} cylinders cut  "
              f"peak lambda {np.nanmedian(lam[sel]):5.2f}")
    print()
    print("  --- what the calibration permits ---")
    print(f"  {GS_D} (D)      min {cal[GS_D]['values'].min():7.3f} CRK")
    print(f"  {GS_S} (Sport)  min {cal[GS_S]['values'].min():7.3f} CRK")
    print(f"  {SCC_D}[DCT] = {d_floor:.4f} -> "
          f"{cylinders_cut(cal, d_floor):.2f} cylinders cut")
    print(f"  {SCC_S}[DCT] = {s_floor:.4f} -> "
          f"{cylinders_cut(cal, s_floor):.2f} cylinders cut")
    print()
    print("  --- and whether the Sport tables are reachable at all ---")
    for name, gate in gates.items():
        if gate["kind"] == "bitmask":
            state = ", ".join(gate["modes"]) if gate["modes"] else "NO MODE"
        else:
            state = "enabled" if gate["raw"] else "DISABLED"
        print(f"  {name:28s} = {gate['raw']:3d}  0b{gate['raw']:08b}  "
              f"{state:14s}  ({gate['meaning']})")
    scc_reachable = (bool(gates["CLF_EFF_SCC_SP_DRIV_MOD"]["raw"])
                     or bool(gates["LC_EFF_SCC_SP_MIN_SPT_KD"]["raw"]))
    print(f"\n  => {SCC_S} is "
          f"{'reachable' if scc_reachable else 'UNREACHABLE by both gates read '
             'here: the cylinder cut is the D-mode table in every drive mode'}")

    events_csv = HERE / "shift_events.csv"
    with events_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(events[0]))
        writer.writeheader()
        writer.writerows(events)

    print(f"\nwrote {events_csv.relative_to(REPO_ROOT)}")
    print(f"wrote {figure(cal, events).relative_to(REPO_ROOT)}")
    print(f"wrote {trace_figure(events).relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
