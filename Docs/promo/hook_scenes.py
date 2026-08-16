#!/usr/bin/env python3
"""The short hook: result first, wordmark at both ends.

Hard cuts, one idea — *this is what it makes*. The deep-dive promo (`scenes.py` +
`scene_surface.py`) explains how the library works; this one only shows the
outcome. It opens and closes on the same wordmark clip (`logo_open` and `logo`
are one frame function at one length), so the cut loops.

Like the long cut, every figure on screen is real: the numbers come from
`hook_data`, which derives them from detected WOT pulls in the repo's own logs.
Nothing here is typed in from memory, and the honest caveats (which gear, which
pull, which revisions are comparable) are on screen rather than buried.

    python3 Docs/promo/hook_scenes.py /tmp/hook_preview   # still frames per beat
"""

from __future__ import annotations

import sys
from pathlib import Path

import compositor as C
import config
import scene_boost
import scene_slots
import scene_trace
from compositor import Frame
from hook_data import hook_data

MARGIN = 130

# ---------------------------------------------------------------------- copy

DYNO_KICKER = "ESTIMATED, NOT A DYNO"
CLIMB_KICKER = "SIX REVISIONS"
WORDMARK = ("simos", "cal")
TAGLINE = "Tune a Simos18 ECU. In code."
CLOSER = "Python in. Checksum-verified .bin out. You flash it."

# Said out loud rather than hidden: which pull these numbers come from, and
# what kind of number they are. `Calc HP` / `Calc TQ` are SimosTools *calculated*
# PIDs (address 0xffffffff, like `Calc 1/4mile`) — the app derives them from
# logged acceleration and gear ratio. They are not read off an ECU address and
# they are not a dyno, so nothing on screen may call them measured.
PROVENANCE = "peak of a logged 3rd-gear WOT pull · SimosTools datalog · 2017 VW GTI"


def _kicker(f: Frame, text: str, t_in: float, color: str = "accent") -> None:
    """The small all-caps line every beat opens on."""
    f.text(text, (MARGIN, 118), size=29, color=color, tracking=8, bold=True,
           alpha=C.clamp01(t_in * 1.5))


def _provenance(f: Frame, alpha: float, text: str = PROVENANCE) -> None:
    f.text(text, (MARGIN, config.HEIGHT - 96), size=26, color="text_faint",
           tracking=3, max_width=1200, alpha=alpha)


# -------------------------------------------------------------- beat 1 · dyno

PLOT = (700, 300, 1790, 880)          # left, top, right, bottom of the curve box


def _curve_points(rpm, vals, lo: float, hi: float) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = PLOT
    r_lo, r_hi = rpm[0], rpm[-1]
    return [
        (x0 + (x1 - x0) * (r - r_lo) / (r_hi - r_lo),
         y1 - (y1 - y0) * (v - lo) / (hi - lo))
        for r, v in zip(rpm, vals)
    ]


def _partial(points: list[tuple[float, float]], p: float) -> list[tuple[float, float]]:
    """The first `p` (0..1) of a polyline, interpolating the final segment."""
    p = C.clamp01(p)
    if p <= 0:
        return []
    span = (len(points) - 1) * p
    k = int(span)
    out = points[:k + 1]
    if k < len(points) - 1:
        frac = span - k
        (ax, ay), (bx, by) = points[k], points[k + 1]
        out.append((C.lerp(ax, bx, frac), C.lerp(ay, by, frac)))
    return out


def dyno_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    d = hook_data()
    rpm, hp, tq = d.curve_rpm, d.curve_hp, d.curve_tq

    x0, y0, x1, y1 = PLOT
    hp_hi = max(hp) * 1.12
    tq_hi = max(tq) * 1.12
    appear = C.ease_out(C.sub(t, 0.0, 0.12))
    draw_p = C.ease_in_out(C.sub(t, 0.08, 0.62))

    # Axis furniture first, so the curves sit on top of it.
    if appear > 0.01:
        grid = tuple(round(c * appear) for c in config.PALETTE["rule"])
        for k in range(5):
            gy = y1 - (y1 - y0) * k / 4
            f.draw.line([(x0, gy), (x1, gy)], fill=grid, width=2)
        f.draw.line([(x0, y1), (x1, y1)], fill=grid, width=4)
        for r in (3500, 4500, 5500, 6250):
            if rpm[0] <= r <= rpm[-1]:
                gx = x0 + (x1 - x0) * (r - rpm[0]) / (rpm[-1] - rpm[0])
                f.text(f"{r:,}", (gx, y1 + 18), size=25, color="text_faint",
                       align="center", alpha=appear)
        f.text("RPM", (x1, y1 + 62), size=25, color="text_faint", align="right",
               tracking=5, alpha=appear)

    # Torque sits behind horsepower — same pull, supporting role.
    tq_pts = _partial(_curve_points(rpm, tq, 0.0, tq_hi), draw_p)
    if len(tq_pts) > 1:
        f.draw.line(tq_pts, fill=(58, 128, 172), width=6, joint="curve")
    hp_pts = _partial(_curve_points(rpm, hp, 0.0, hp_hi), draw_p)
    if len(hp_pts) > 1:
        f.draw.line(hp_pts, fill=config.PALETTE["accent"], width=9, joint="curve")
        hx, hy = hp_pts[-1]
        f.draw.ellipse((hx - 11, hy - 11, hx + 11, hy + 11), fill=config.PALETTE["accent"])

    # The counter tracks the drawn part of the curve and lands exactly on the
    # quoted peak: the curve is resampled, so its own max is a hair off the
    # smoothed peak the number comes from.
    drawn_max = max(hp[:max(len(hp_pts), 1)]) if hp_pts else 0.0
    shown = d.headline.hp * (drawn_max / max(hp))
    _kicker(f, DYNO_KICKER, C.sub(t, 0.0, 0.18))
    f.text(f"{shown:.0f}", (MARGIN, 330), size=250, color="text", bold=True, alpha=appear)
    f.text("HP", (MARGIN + 8, 590), size=68, color="accent", bold=True, tracking=10,
           alpha=C.ease_out(C.sub(t, 0.2, 0.4)))

    tq_t = C.ease_out(C.sub(t, 0.58, 0.78))
    if d.headline.tq is not None:
        # Fades in at its real value. The hp counter above is allowed to climb
        # because it tracks the curve's tip; this one has nothing to track.
        f.text(f"{d.headline.tq:.0f}", (MARGIN, 700), size=120,
               color="text", bold=True, alpha=tq_t)
        f.text("Nm", (MARGIN + 6, 830), size=44, color="accent_2", bold=True,
               tracking=8, alpha=tq_t)

    _provenance(f, C.ease_out(C.sub(t, 0.7, 0.9)),
                f"{d.headline.rev} · SimosTools Calc HP — the app's estimate from "
                f"logged acceleration and gear ratio, not a dyno · 3rd-gear WOT "
                f"pull, {rpm[0]:,.0f}–{rpm[-1]:,.0f} rpm · smoothed peak")
    f.vignette(0.38)
    return f


# ------------------------------------------------------------- beat 2 · climb

BAR_BASE_Y = 858
BAR_TOP_Y = 330
BAR_W = 132
BAR_GAP = 46


def climb_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    d = hook_data()
    revs = d.revisions
    hp_hi = max(r.hp for r in revs) * 1.10

    appear = C.ease_out(C.sub(t, 0.0, 0.1))
    _kicker(f, CLIMB_KICKER, C.sub(t, 0.0, 0.16))

    total_w = len(revs) * BAR_W + (len(revs) - 1) * BAR_GAP
    x_left = f.cx - total_w / 2 + 210
    base_frac = revs[0].hp / hp_hi
    base_y = BAR_BASE_Y - (BAR_BASE_Y - BAR_TOP_Y) * base_frac

    for k, rev in enumerate(revs):
        # Bars land one after another; the last one gets the longest hold.
        t_bar = C.ease_out(C.sub(t, 0.10 + k * 0.075, 0.32 + k * 0.075))
        if t_bar <= 0.001:
            continue
        x = x_left + k * (BAR_W + BAR_GAP)
        full_h = (BAR_BASE_Y - BAR_TOP_Y) * (rev.hp / hp_hi)
        h = full_h * t_bar
        top = BAR_BASE_Y - h
        last = k == len(revs) - 1

        # Bars run from zero — no truncated axis. The gain over the first
        # revision is picked out in accent instead.
        f.rect((x, top, x + BAR_W, BAR_BASE_Y), fill="bg_alt", radius=8)
        gain_top = max(top, base_y)
        if base_y > top + 1:
            f.rect((x, top, x + BAR_W, gain_top),
                   fill="accent" if last else (196, 108, 42), radius=8)
        # The real figure rides up with the bar and fades in — never a counting
        # number, which would put hp values on screen the car never made.
        f.text(f"{rev.hp:.0f}", (x + BAR_W / 2, top - 52), size=44,
               color="text" if last else "text_dim", bold=True, align="center",
               alpha=t_bar * t_bar)
        f.text(rev.rev, (x + BAR_W / 2, BAR_BASE_Y + 20), size=30,
               color="accent" if last else "text_faint", align="center",
               tracking=3, bold=last, alpha=t_bar)

    # The first revision's level, so the accent bands read as gain over it.
    rule_t = C.ease_out(C.sub(t, 0.16, 0.34))
    if rule_t > 0:
        f.draw.line([(x_left - 40, base_y), (x_left + total_w * rule_t + 40, base_y)],
                    fill=config.PALETTE["text_faint"], width=3)

    gain_t = C.ease_out(C.sub(t, 0.55, 0.75))
    f.text(f"+{d.hp_gain:.0f}", (MARGIN, 330), size=190, color="accent", bold=True,
           alpha=gain_t)
    f.text("HP", (MARGIN + 6, 540), size=58, color="text", bold=True, tracking=8,
           alpha=gain_t)
    f.text(f"{d.baseline.rev} → {d.headline.rev}", (MARGIN + 6, 630), size=38,
           color="text_dim", tracking=4, alpha=C.ease_out(C.sub(t, 0.66, 0.86)))

    _provenance(f, appear,
                "each bar is that revision's best logged 3rd-gear pull to redline · "
                "SimosTools Calc HP, estimated from acceleration — not a dyno")
    f.vignette(0.34)
    return f


# -------------------------------------------------------------- beat 3 · logo

def logo_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()

    mark_t = C.ease_out(C.sub(t, 0.0, 0.3))
    size = 150
    fnt = C.font(size, mono=True)
    w0, w1 = (fnt.getlength(s) for s in WORDMARK)
    x0 = f.cx - (w0 + w1) / 2
    y = f.cy - 190 - (1 - mark_t) * 22
    f.text(WORDMARK[0], (x0, y), size=size, mono=True, color="text", alpha=mark_t)
    f.text(WORDMARK[1], (x0 + w0, y), size=size, mono=True, color="accent", alpha=mark_t)

    rule_t = C.ease_in_out(C.sub(t, 0.22, 0.5))
    if rule_t > 0:
        half = 440 * rule_t
        f.line((f.cx - half, y + size * 1.36), (f.cx + half, y + size * 1.36),
               color="rule", width=3)

    f.text(TAGLINE, (f.cx, y + size * 1.56), size=66, color="text", align="center",
           bold=True, alpha=C.ease_out(C.sub(t, 0.3, 0.56)))
    f.text(CLOSER, (f.cx, y + size * 1.56 + 112), size=32, color="text_dim",
           align="center", tracking=3, alpha=C.ease_out(C.sub(t, 0.5, 0.75)))
    # Held, not faded — the wordmark is the payoff, and the cut is short enough
    # that people will loop it.
    f.vignette(0.28)
    return f


# ------------------------------------------------------------------- dispatch

FRAME_FUNCS = {
    # The opening and closing beats share one frame function and one length, so
    # the cut opens on the very clip it ends on.
    "logo_open": logo_frame,
    "boost": scene_boost.boost_frame,
    "dyno": dyno_frame,
    "trace": scene_trace.trace_frame,
    "climb": climb_frame,
    "slots": scene_slots.slots_frame,
    "logo": logo_frame,
}


def render_beat(writer, beat: config.Beat) -> None:
    fn = FRAME_FUNCS[beat.id]
    writer.begin(beat)
    for i in range(beat.n_frames):
        writer.write(fn(i, beat.n_frames))
    writer.end(beat)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "hook_preview")
    out.mkdir(parents=True, exist_ok=True)
    for beat in config.HOOK_TIMELINE:
        fn = FRAME_FUNCS[beat.id]
        for at in (0.25, 0.6, 1.0):
            idx = round(at * (beat.n_frames - 1))
            fn(idx, beat.n_frames).save(out / f"{beat.id}_{int(at * 100):03d}.png")
    print(f"wrote still frames for {len(config.HOOK_TIMELINE)} beats to {out}")
