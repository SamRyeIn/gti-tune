#!/usr/bin/env python3
"""The boost beat: every revision's logged boost curve, drawn as the revs climb.

Six revisions of the same car, same gear, same channel — `Boost (psi)`, gauge
pressure straight off the SimosTools datalog. An rpm cursor sweeps the axis and
each revision's curve is revealed up to it, so the family of curves separates in
front of you exactly where the calibration changed: spool on the left, target on
the right.

What this beat is careful about:

* **Measured, not targeted.** These are logged curves — what the car actually
  made. The slots beat plots the *target* grids out of the bin; this one plots
  the outcome, and the two are deliberately different things.
* **One pull per revision, and it is the same pull** the hp figure comes from
  (`hook_data` derives both off the same in-gear rows), so this beat and the
  climb beat can never be describing two different runs.
* **Only the rpm window every pull is on boost in.** The pulls begin and end
  wherever the driver floored it and shifted — 2654 to 3246 rpm at the bottom,
  6194 to 6765 at the top. Drawn over their own ranges, the near-vertical left
  edge of each curve is just *where that pull started*, and the newest revision
  reads as spooling late when nothing of the sort happened. `curves()` clips that
  away twice over; the beat states the window it ends up with, and every figure on
  screen is computed from the clipped curves, so a number can never disagree with
  the line it sits next to.

    python3 Docs/promo/scene_boost.py /tmp/boost_preview
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

import compositor as C
import config
from compositor import Frame
from hook_data import HEADLINE_REV, BoostCurve, hook_data

KICKER = "LOGGED BOOST"
MARGIN = 130

#: Plot box, matched to the slots beat so the two graph beats read as one system:
#: copy down the left, curves in the middle, labels in the right-hand gutter.
PLOT = (620, 330, 1500, 890)
LABEL_X = PLOT[2] + 26
LABEL_GAP = 44

PLAY_IN, PLAY_OUT = 0.10, 0.82        # the rpm sweep's window inside the beat

#: Where the newest and the first revision sit in the palette. Everything between
#: them is a slate ramp: the identity of a curve comes from the label riding its
#: tip, never from remembering a colour, so the middle of the lineage only has to
#: read as "the path between the two".
COLOR_NEWEST = config.PALETTE["accent"]        # orange — the revision in the car
COLOR_BASELINE = config.PALETTE["accent_2"]    # blue — where the lineage started
RAMP_LO, RAMP_HI = (74, 88, 108), (156, 168, 186)


#: A shared window narrower than this is not worth drawing as a comparison.
MIN_SHARED_SPAN_RPM = 1500.0

#: "On boost" — comfortably under every revision's peak, comfortably over the
#: spool ramp. Used only to find where each pull finished spooling.
ON_BOOST_PSI = 20.0


@lru_cache(maxsize=1)
def curves() -> tuple[BoostCurve, ...]:
    """Every revision's boost curve, over the window all of them are comparable in.

    Two clips, and the second is the one that matters. The obvious window — the
    latest start to the earliest end — is still not a comparison: a pull floored
    at 3246 rpm is at 0.5 psi there while a pull floored at 2686 rpm is already
    making 24, so the newest revision would draw a spool ramp against five
    flat-topped curves and read as the worst of them. So the left edge moves to
    where the *last* pull to come on boost got there, and from that point on all
    six are doing the same thing: holding a boost target at wide-open throttle.

    Resampling onto one grid is safe inside this window and only inside it: every
    sample is interpolated strictly within a range that revision was logged over.
    Nothing is extrapolated.
    """
    cs = hook_data().boost_curves
    lo = max(c.rpm[0] for c in cs)
    hi = min(c.rpm[-1] for c in cs)
    for c in cs:
        spooled = [r for r, p in zip(c.rpm, c.psi) if p >= ON_BOOST_PSI]
        if spooled:                     # a revision that never gets there is drawn as-is
            lo = max(lo, spooled[0])
    if hi - lo < MIN_SHARED_SPAN_RPM:
        raise SystemExit(
            f"the {len(cs)} boost pulls are only comparable over {hi - lo:.0f} rpm "
            f"({lo:.0f}-{hi:.0f}) — too narrow to draw; re-log or drop a revision"
        )
    grid = np.linspace(lo, hi, len(cs[0].rpm))
    return tuple(BoostCurve(rev=c.rev, rpm=grid.tolist(),
                            psi=np.interp(grid, c.rpm, c.psi).tolist()) for c in cs)


def _style(k: int, n: int) -> tuple[tuple[int, int, int], int]:
    """`(colour, line width)` for the k-th revision of n, oldest first."""
    if k == n - 1:
        return COLOR_NEWEST, 9
    if k == 0:
        return COLOR_BASELINE, 6
    # Older revisions get brighter as they approach the newest, so the eye reads
    # the stack bottom-to-top as history even before it reads the labels.
    f = (k - 1) / max(n - 3, 1)
    return tuple(round(C.lerp(a, b, f)) for a, b in zip(RAMP_LO, RAMP_HI)), 4


# ------------------------------------------------------------------- geometry

def _x_range() -> tuple[float, float]:
    """The shared window — every clipped curve is on the same grid."""
    rpm = curves()[0].rpm
    return rpm[0], rpm[-1]


def _y_range() -> tuple[float, float]:
    """psi bounds — from zero, because a boost curve starting off-axis lies."""
    return 0.0, float(np.ceil(max(c.peak for c in curves()) + 1.0))


def _xy(rpm: float, psi: float) -> tuple[float, float]:
    x0, y0, x1, y1 = PLOT
    r_lo, r_hi = _x_range()
    lo, hi = _y_range()
    return (x0 + (x1 - x0) * (rpm - r_lo) / (r_hi - r_lo),
            y1 - (y1 - y0) * (psi - lo) / (hi - lo))


def _points(curve: BoostCurve, rpm_now: float) -> list[tuple[float, float]]:
    """The curve up to `rpm_now`, interpolated at the cursor itself."""
    pts = [_xy(r, p) for r, p in zip(curve.rpm, curve.psi) if r <= rpm_now]
    if curve.rpm[0] <= rpm_now <= curve.rpm[-1]:
        pts.append(_xy(rpm_now, float(np.interp(rpm_now, curve.rpm, curve.psi))))
    return pts


def _value_at(curve: BoostCurve, rpm_now: float) -> float:
    """The psi at the cursor — the point this curve's line currently stops on."""
    return float(np.interp(rpm_now, curve.rpm, curve.psi))


def _peak_so_far(curve: BoostCurve, rpm_now: float) -> float:
    drawn = [p for r, p in zip(curve.rpm, curve.psi) if r <= rpm_now]
    return max(drawn) if drawn else 0.0


# ----------------------------------------------------------------- the beat

def _axes(f: Frame, alpha: float) -> None:
    x0, y0, x1, y1 = PLOT
    r_lo, r_hi = _x_range()
    lo, hi = _y_range()
    grid = tuple(round(v * alpha) for v in config.PALETTE["rule"])

    ticks = np.arange(lo, hi + 1e-9, 5.0)
    for psi in ticks:
        _, gy = _xy(r_lo, float(psi))
        f.draw.line([(x0, gy), (x1, gy)], fill=grid, width=2)
        text = f"{psi:.0f} psi" if psi == ticks[-1] else f"{psi:.0f}"
        f.text(text, (x0 - 18, gy), size=25, color="text_faint",
               align="right", valign="middle", alpha=alpha)
    f.draw.line([(x0, y1), (x1, y1)], fill=grid, width=4)

    for r in range(3000, 7001, 1000):
        if r_lo <= r <= r_hi:
            gx, _ = _xy(r, lo)
            f.text(f"{r:,}", (gx, y1 + 18), size=25, color="text_faint",
                   align="center", alpha=alpha)
    f.text("RPM", (x1, y1 + 60), size=25, color="text_faint", align="right",
           tracking=5, alpha=alpha)


def boost_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    cs = curves()
    r_lo, r_hi = _x_range()

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

    tips: dict[str, tuple[float, float]] = {}
    for k, curve in enumerate(cs):
        color, width = _style(k, len(cs))
        pts = _points(curve, rpm_now)
        if len(pts) < 2:
            continue
        dim = tuple(round(v * appear) for v in color)
        f.draw.line(pts, fill=dim, width=width, joint="curve")
        hx, hy = pts[-1]
        f.draw.ellipse((hx - 8, hy - 8, hx + 8, hy + 8), fill=dim)
        tips[curve.rev] = (hx, hy)

    # Labels ride the gutter, each on its own row, carrying that revision's value
    # at the point its line currently stops — so which trace is which never
    # depends on a legend key, and the numbers are the ones being drawn.
    if tips:
        rows = C.spread_rows({rev: y for rev, (_, y) in tips.items()}, LABEL_GAP, PLOT[3])
        by_rev = {c.rev: (k, c) for k, c in enumerate(cs)}
        for rev, (hx, hy) in tips.items():
            k, curve = by_rev[rev]
            color, _ = _style(k, len(cs))
            newest = rev == cs[-1].rev
            ly = rows[rev]
            # A short connector only where the label had to be nudged off its
            # line — running one back to the tip would read as the curve
            # carrying on past the cursor, which it does not.
            if abs(ly - hy) > 14:
                faint = tuple(round(v * appear * 0.55) for v in color)
                f.draw.line([(max(hx + 10, LABEL_X - 64), hy), (LABEL_X - 12, ly)],
                            fill=faint, width=2)
            f.text(rev, (LABEL_X, ly - 2), size=26, color=color, valign="middle",
                   bold=newest, alpha=appear)
            f.text(f"{_value_at(curve, rpm_now):.1f}", (config.WIDTH - 118, ly - 2),
                   size=26, color=color, align="right", valign="middle",
                   bold=newest, alpha=appear)

    _copy(f, t, appear, rpm_now)
    f.vignette(0.36)
    return f


def _copy(f: Frame, t: float, appear: float, rpm_now: float) -> None:
    cs = curves()
    # The clipped curve, never `hook_data`'s raw one: every figure in this column
    # has to be the figure of the line actually on screen.
    head = next((c for c in cs if c.rev == HEADLINE_REV), cs[-1])

    f.text(KICKER, (MARGIN, 118), size=29, color="accent", tracking=8, bold=True,
           alpha=C.clamp01(C.sub(t, 0.0, 0.18) * 1.5))
    f.text("Boost (psi)", (MARGIN, 300), size=42, color="text", mono=True, alpha=appear)
    f.text("Gauge boost pressure, logged. Not a target, not a model — what the "
           "car made on the road.",
           (MARGIN, 360), size=27, color="text_dim", italic=True, max_width=400,
           alpha=appear)

    # Tracks the highest point of the newest curve drawn so far, so it climbs
    # with the sweep and lands exactly on that curve's own peak.
    f.text(f"{_peak_so_far(head, rpm_now):.1f}", (MARGIN, 520), size=150,
           color="accent", bold=True, alpha=appear)
    f.text("PSI", (MARGIN + 6, 690), size=46, color="text", bold=True, tracking=8,
           alpha=C.ease_out(C.sub(t, 0.2, 0.4)))
    f.text(f"{head.rev} peak, so far", (MARGIN + 6, 762), size=26, color="text_dim",
           tracking=2, alpha=C.ease_out(C.sub(t, 0.25, 0.45)))

    # The spread across the lineage, at its real figure, once both ends are drawn.
    gain = head.peak - cs[0].peak
    f.text(f"{gain:+.1f} psi peak, {cs[0].rev} → {head.rev}", (MARGIN, 830), size=30,
           color="text", tracking=2, alpha=C.ease_out(C.sub(t, 0.72, 0.9)))

    r_lo, r_hi = _x_range()
    f.text(f"{len(cs)} revisions · each its best logged 3rd-gear WOT pull, in-gear "
           f"samples only · {r_lo:,.0f}–{r_hi:,.0f} rpm, the window every pull is "
           f"on boost in",
           (MARGIN, config.HEIGHT - 96), size=26, color="text_faint", tracking=3,
           max_width=1200, alpha=C.ease_out(C.sub(t, 0.25, 0.5)))


def render_beat(writer, beat: config.Beat) -> None:
    writer.begin(beat)
    for i in range(beat.n_frames):
        writer.write(boost_frame(i, beat.n_frames))
    writer.end(beat)


if __name__ == "__main__":
    cs = curves()
    for k, c in enumerate(cs):
        color, _ = _style(k, len(cs))
        print(f"  {c.rev:<4} {c.rpm[0]:.0f}-{c.rpm[-1]:.0f} rpm   peak {c.peak:5.1f} psi"
              f"   rgb{color}")
    for rev in hook_data().boost_missing:
        print(f"  {rev:<4} NO BOOST CHANNEL — not drawn")
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "boost_preview")
    out.mkdir(parents=True, exist_ok=True)
    beat = config.HOOK_BEATS["boost"]
    for at in (0.2, 0.45, 0.7, 1.0):
        idx = round(at * (beat.n_frames - 1))
        boost_frame(idx, beat.n_frames).save(out / f"boost_{int(at * 100):03d}.png")
    print(f"wrote boost stills to {out}")
