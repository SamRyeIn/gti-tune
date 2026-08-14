#!/usr/bin/env python3
"""The map-switch beat: all five slot boost curves, drawn as the revs climb.

The BinToolz 5-slot map switch gives the car five selectable boost targets on a
steering-wheel switch. Each slot owns its own `PUT setpoint` grid — the boost
target upstream of the throttle — and the effective target is the minimum of that
grid and the shared base `IP_PUT_SP` — Pressure up throttle setpoint, which the
lineage parks non-binding, so in practice the selected slot *is* the target.

Two things this beat has to be honest about:

* **The curves are read out of the flashed bin**, not retyped from the revision
  script: the same five uniqueid-addressed grids the tune wrote, out of the
  newest tune-run output `.bin`. If the tune changes them, this beat changes.
* **The ECU stores absolute pressure in hPa.** What a driver calls "boost" is
  gauge pressure, so every value is converted against standard sea-level
  ambient — `psi_gauge = (hPa_abs - 1013.25) / 68.9476` — and the beat says on
  screen that it is doing so. At altitude the same target is more gauge boost;
  quoting one number without the reference would be quoting nothing.

The draw is an rpm sweep: a vertical rpm cursor travels the axis and each curve
is revealed up to it, so the five targets separate in front of you exactly where
they separate in the calibration.

    python3 Docs/promo/scene_slots.py /tmp/slots_preview
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

import compositor as C
import config
from compositor import Frame

CACHE = config.ASSET_DIR / "slot_curves.npz"

KICKER = "FIVE MAPS, ONE SWITCH"

#: Standard sea-level ambient and the psi conversion the ECU's hPa store needs.
SEA_LEVEL_HPA = 1013.25
HPA_PER_PSI = 68.9476

#: Plot box: left, top, right, bottom. The right edge stops well short of the
#: canvas to leave a gutter for the curve labels, which ride each line's tip.
PLOT = (620, 330, 1500, 890)
LABEL_X = PLOT[2] + 26
LABEL_GAP = 44                        # min vertical spacing between two labels

#: Per-slot styling. The labels name what the slot is for, not what it is worth
#: — the psi figure is drawn from the data, so it can never disagree with it.
SLOT_STYLE = {
    1: ("STOCK", (122, 138, 160), 6),
    2: ("CONSERVATIVE", (86, 190, 255), 6),
    3: ("INTERMEDIATE", (98, 214, 140), 6),
    4: ("AGGRESSIVE", (255, 138, 46), 9),
    5: ("VALET", (255, 96, 96), 6),
}

PLAY_IN, PLAY_OUT = 0.10, 0.80        # the rpm sweep's window inside the beat


def psi_gauge(hpa: np.ndarray | float) -> np.ndarray | float:
    """Absolute hPa as the ECU stores it -> psi gauge at sea level."""
    return (np.asarray(hpa, dtype=float) - SEA_LEVEL_HPA) / HPA_PER_PSI


# --------------------------------------------------------------- the real data

def _tuned_bin() -> Path:
    out_dir = config.newest_tune_out_dir()
    bins = sorted(out_dir.glob("*.bin"))
    if not bins:
        raise FileNotFoundError(f"no saved .bin in {out_dir}")
    return bins[0]


def _bin_rev() -> str:
    """The revision tag of the bin the curves came from, e.g. `R15`.

    Named rather than called "flashed": the newest tune-run output is not
    necessarily the revision in the car, and the caption should not imply it is.
    """
    return config.newest_tune_out_dir().name.split("_")[0]


def _extract_curves() -> dict[str, np.ndarray]:
    """Read the shared rpm axis and all five slot grids out of the flashed bin.

    The patch-added tables carry no A2L symbol and all five share the title
    ``PUT setpoint``, so they are addressed by uniqueid — the profile in
    `simoscal.tune.profiles.switchpatch_2933` is the source of those ids rather
    than a second copy of them here.
    """
    if str(config.CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(config.CODE_ROOT))
    from simoscal import CalFile                              # noqa: PLC0415 — heavy
    from simoscal.tune.profiles.switchpatch_2933 import (     # noqa: PLC0415
        SLOTS, SWITCH_PATCH_2933, slot_names,
    )

    cal = CalFile.open(config.SWITCH_XDF, _tuned_bin())
    axis = np.asarray(
        cal.get(SWITCH_PATCH_2933["slot_put_rpm_axis"].key).values, dtype=float).ravel()

    out = {"rpm": axis}
    for slot, name in zip(SLOTS, slot_names("put_setpoint")):
        grid = np.asarray(cal.get(SWITCH_PATCH_2933[name].key).values, dtype=float)
        # The lineage tiles one curve across all eight uncharacterized Y rows.
        # If a future revision ever stops tiling, that is worth failing on
        # rather than quietly plotting row 0 as if it were the whole story.
        if not np.allclose(grid, grid[0], rtol=0, atol=0.5):
            raise SystemExit(
                f"slot {slot}'s PUT setpoint grid is not tiled across its rows — "
                "this beat plots one curve per slot and cannot represent that"
            )
        out[f"slot{slot}"] = grid[0]
    return out


@lru_cache(maxsize=1)
def slot_curves() -> dict[str, np.ndarray]:
    """`{rpm, slot1..slot5}` in raw hPa absolute, cached to `assets/`."""
    if CACHE.is_file():
        with np.load(CACHE) as z:
            return {k: z[k] for k in z.files}
    curves = _extract_curves()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(CACHE, **curves)
    return curves


def slot_summary() -> list[tuple[int, str, float, float]]:
    """`(slot, label, peak psi, psi at the top of the axis)` for every slot."""
    c = slot_curves()
    return [
        (slot, SLOT_STYLE[slot][0],
         float(psi_gauge(c[f"slot{slot}"]).max()),
         float(psi_gauge(c[f"slot{slot}"])[-1]))
        for slot in sorted(SLOT_STYLE)
    ]


# ------------------------------------------------------------------- geometry

def _y_range() -> tuple[float, float]:
    """psi bounds of the plot, padded and rounded to whole psi."""
    c = slot_curves()
    vals = np.concatenate([psi_gauge(c[f"slot{s}"]) for s in SLOT_STYLE])
    return float(np.floor(vals.min() - 1.5)), float(np.ceil(vals.max() + 1.5))


def _xy(rpm: float, psi: float) -> tuple[float, float]:
    x0, y0, x1, y1 = PLOT
    c = slot_curves()
    r_lo, r_hi = float(c["rpm"][0]), float(c["rpm"][-1])
    lo, hi = _y_range()
    return (x0 + (x1 - x0) * (rpm - r_lo) / (r_hi - r_lo),
            y1 - (y1 - y0) * (psi - lo) / (hi - lo))


def _points(slot: int, rpm_now: float) -> list[tuple[float, float]]:
    """The slot's curve up to `rpm_now`, interpolated at the cursor itself."""
    c = slot_curves()
    rpm, psi = c["rpm"], psi_gauge(c[f"slot{slot}"])
    pts = [_xy(r, p) for r, p in zip(rpm, psi) if r <= rpm_now]
    if rpm[0] <= rpm_now <= rpm[-1]:
        pts.append(_xy(rpm_now, float(np.interp(rpm_now, rpm, psi))))
    return pts


def _spread(ys: dict[int, float]) -> dict[int, float]:
    """Nudge label rows apart without reordering them.

    Three of the five slots share a value at low rpm, so their labels would land
    on the same pixel row and stack into mush. Pushing them apart keeps every
    slot readable while the curves are still on top of each other, and costs
    nothing once they separate.
    """
    out = dict(ys)
    prev = -1e9
    for slot in sorted(out, key=lambda s: out[s]):
        out[slot] = max(out[slot], prev + LABEL_GAP)
        prev = out[slot]
    overflow = max(out.values()) - PLOT[3]
    if overflow > 0:
        for slot in out:
            out[slot] -= overflow
    return out


# ----------------------------------------------------------------- the beat

def _axes(f: Frame, alpha: float) -> None:
    x0, y0, x1, y1 = PLOT
    c = slot_curves()
    lo, hi = _y_range()
    grid = tuple(round(v * alpha) for v in config.PALETTE["rule"])

    step = 2 if hi - lo <= 22 else 4
    ticks = np.arange(np.ceil(lo / step) * step, hi + 1e-9, step)
    for psi in ticks:
        _, gy = _xy(c["rpm"][0], float(psi))
        f.draw.line([(x0, gy), (x1, gy)], fill=grid, width=2)
        # The unit rides the top tick rather than sitting in its own label,
        # which would collide with the travelling rpm readout.
        text = f"{psi:.0f} psi" if psi == ticks[-1] else f"{psi:.0f}"
        f.text(text, (x0 - 18, gy), size=25, color="text_faint",
               align="right", valign="middle", alpha=alpha)
    f.draw.line([(x0, y1), (x1, y1)], fill=grid, width=4)

    for r in (3000, 4000, 5000, 6000, 6500):
        if c["rpm"][0] <= r <= c["rpm"][-1]:
            gx, _ = _xy(r, lo)
            f.text(f"{r:,}", (gx, y1 + 18), size=25, color="text_faint",
                   align="center", alpha=alpha)
    f.text("RPM", (x1, y1 + 60), size=25, color="text_faint", align="right",
           tracking=5, alpha=alpha)


def slots_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    c = slot_curves()
    r_lo, r_hi = float(c["rpm"][0]), float(c["rpm"][-1])

    appear = C.ease_out(C.sub(t, 0.0, 0.12))
    sweep = C.ease_in_out(C.sub(t, PLAY_IN, PLAY_OUT))
    rpm_now = C.lerp(r_lo, r_hi, sweep)

    _axes(f, appear)

    # The rpm cursor, behind the curves so it never cuts across a line.
    if sweep > 0.001:
        cx, _ = _xy(rpm_now, 0.0)
        f.draw.line([(cx, PLOT[1] - 10), (cx, PLOT[3])],
                    fill=tuple(round(v * appear) for v in config.PALETTE["rule"]), width=3)
        f.text(f"{rpm_now:,.0f}", (cx, PLOT[1] - 46), size=28, color="text_dim",
               align="center", alpha=appear)

    tips: dict[int, tuple[float, float]] = {}
    for slot, (_, color, width) in SLOT_STYLE.items():
        pts = _points(slot, rpm_now)
        if len(pts) < 2:
            continue
        dim = tuple(round(v * appear) for v in color)
        f.draw.line(pts, fill=dim, width=width, joint="curve")
        hx, hy = pts[-1]
        f.draw.ellipse((hx - 8, hy - 8, hx + 8, hy + 8), fill=dim)
        tips[slot] = (hx, hy)

    # Labels live in the gutter, each on its own row, carrying that slot's live
    # value at the cursor — so which trace is which never depends on a legend
    # key, and the numbers on screen are the ones being drawn.
    if tips:
        rows = _spread({s: y for s, (_, y) in tips.items()})
        for slot, (hx, hy) in tips.items():
            label, color, _ = SLOT_STYLE[slot]
            ly = rows[slot]
            # A short connector only where the label had to be nudged off its
            # line. Running one back to the curve tip would read as the curve
            # carrying on past the cursor, which it does not.
            if abs(ly - hy) > 14:
                faint = tuple(round(v * appear * 0.55) for v in color)
                f.draw.line([(max(hx + 10, LABEL_X - 64), hy), (LABEL_X - 12, ly)],
                            fill=faint, width=2)
            psi_now = float(np.interp(rpm_now, c["rpm"], psi_gauge(c[f"slot{slot}"])))
            f.text(f"{slot}  {label}", (LABEL_X, ly - 2), size=26, color=color,
                   valign="middle", bold=slot == 4, alpha=appear)
            f.text(f"{psi_now:.1f}", (config.WIDTH - 118, ly - 2), size=26,
                   color=color, align="right", valign="middle", bold=slot == 4,
                   alpha=appear)

    _kicker_and_copy(f, t, appear)
    f.vignette(0.36)
    return f


def _kicker_and_copy(f: Frame, t: float, appear: float) -> None:
    margin = 130
    f.text(KICKER, (margin, 118), size=29, color="accent", tracking=8, bold=True,
           alpha=C.clamp01(C.sub(t, 0.0, 0.18) * 1.5))
    f.text("PUT setpoint", (margin, 300), size=42, color="text", mono=True, alpha=appear)
    f.text("Boost target upstream of the throttle — one grid per map slot, "
           "selectable on the wheel.",
           (margin, 360), size=27, color="text_dim", italic=True, max_width=400,
           alpha=appear)

    # The spread between the softest and hardest slot, taken from the data.
    peaks = {slot: peak for slot, _, peak, _ in slot_summary()}
    gain_t = C.ease_out(C.sub(t, 0.45, 0.68))
    f.text(f"+{peaks[4] - peaks[1]:.1f}", (margin, 520), size=150, color="accent",
           bold=True, alpha=gain_t)
    f.text("PSI", (margin + 6, 690), size=46, color="text", bold=True, tracking=8,
           alpha=gain_t)
    f.text("stock slot → aggressive,\nat peak", (margin + 6, 762), size=26,
           color="text_dim", tracking=2, alpha=C.ease_out(C.sub(t, 0.55, 0.78)))

    f.text(f"the five slot grids read out of the {_bin_rev()} tune bin · "
           f"absolute hPa converted at sea level ({SEA_LEVEL_HPA:.0f} hPa)",
           (margin, config.HEIGHT - 96), size=26, color="text_faint", tracking=3,
           alpha=C.ease_out(C.sub(t, 0.25, 0.5)))


def render_beat(writer, beat: config.Beat) -> None:
    writer.begin(beat)
    for i in range(beat.n_frames):
        writer.write(slots_frame(i, beat.n_frames))
    writer.end(beat)


if __name__ == "__main__":
    for slot, label, peak, top in slot_summary():
        print(f"  slot {slot}  {label:<13} peak {peak:5.1f} psi   "
              f"{top:5.1f} psi at redline")
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "slots_preview")
    out.mkdir(parents=True, exist_ok=True)
    beat = config.HOOK_BEATS["slots"]
    for at in (0.2, 0.45, 0.7, 1.0):
        idx = round(at * (beat.n_frames - 1))
        slots_frame(idx, beat.n_frames).save(out / f"slots_{int(at * 100):03d}.png")
    print(f"wrote slot stills to {out}")
