#!/usr/bin/env python3
"""The 20-second hook: result first, library named last.

Five beats, hard-cut, one idea — *this is what it makes*. The deep-dive promo
(`scenes.py` + `scene_surface.py`) explains how the library works; this one only
shows the outcome and puts a name to it at the very end.

Like the long cut, every figure on screen is real: the numbers come from
`hook_data`, which derives them from detected WOT pulls in the repo's own logs.
Nothing here is typed in from memory, and the honest caveats (which gear, which
pull, which revisions are comparable) are on screen rather than buried.

    python3 Docs/promo/hook_scenes.py /tmp/hook_preview   # still frames per beat
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import compositor as C
import config
import scene_surface
import scene_trace
from compositor import Frame
from hook_data import hook_data

MARGIN = 130

# ---------------------------------------------------------------------- copy

BOOST_LABEL = "PEAK BOOST"
DYNO_KICKER = "MEASURED, NOT MODELLED"
CLIMB_KICKER = "SIX REVISIONS"
MAP_KICKER = "ONE TABLE MOVED"
WORDMARK = ("simos", "cal")
TAGLINE = "Tune a Simos18 ECU. In code."
CLOSER = "Python in. Checksum-verified .bin out. You flash it."

# Said out loud rather than hidden: which pull these numbers come from.
PROVENANCE = "peak of a logged 3rd-gear WOT pull · SimosTools datalog · 2017 VW GTI"


def _kicker(f: Frame, text: str, t_in: float, color: str = "accent") -> None:
    """The small all-caps line every beat opens on."""
    f.text(text, (MARGIN, 118), size=29, color=color, tracking=8, bold=True,
           alpha=C.clamp01(t_in * 1.5))


def _provenance(f: Frame, alpha: float, text: str = PROVENANCE) -> None:
    f.text(text, (MARGIN, config.HEIGHT - 96), size=26, color="text_faint",
           tracking=3, alpha=alpha)


# ------------------------------------------------------------- beat 1 · boost

GAUGE_MAX_PSI = 30.0
GAUGE_START_DEG, GAUGE_SWEEP_DEG = 135.0, 270.0
GAUGE_R = 268


def _gauge_point(cx: float, cy: float, radius: float, frac: float) -> tuple[float, float]:
    a = math.radians(GAUGE_START_DEG + GAUGE_SWEEP_DEG * frac)
    return (cx + radius * math.cos(a), cy + radius * math.sin(a))


def _gauge(f: Frame, cx: float, cy: float, value: float, alpha: float) -> None:
    """A boost dial reading `value` psi, drawn straight onto the frame."""
    if alpha <= 0.01:
        return
    dim = tuple(round(c * alpha) for c in config.PALETTE["rule"])
    faint = tuple(round(c * alpha) for c in config.PALETTE["text_faint"])
    hot = tuple(round(c * alpha) for c in config.PALETTE["accent"])

    box = (cx - GAUGE_R, cy - GAUGE_R, cx + GAUGE_R, cy + GAUGE_R)
    f.draw.arc(box, GAUGE_START_DEG, GAUGE_START_DEG + GAUGE_SWEEP_DEG, fill=dim, width=6)

    # The travelled arc, in accent — the dial "fills" as the needle sweeps.
    frac = C.clamp01(value / GAUGE_MAX_PSI)
    if frac > 0.002:
        f.draw.arc(box, GAUGE_START_DEG, GAUGE_START_DEG + GAUGE_SWEEP_DEG * frac,
                   fill=hot, width=14)

    for psi in range(0, int(GAUGE_MAX_PSI) + 1):
        major = psi % 5 == 0
        tf = psi / GAUGE_MAX_PSI
        r_out = GAUGE_R - 22
        r_in = r_out - (34 if major else 16)
        f.draw.line([_gauge_point(cx, cy, r_in, tf), _gauge_point(cx, cy, r_out, tf)],
                    fill=faint if major else dim, width=5 if major else 3)
        if major:
            lx, ly = _gauge_point(cx, cy, r_in - 34, tf)
            f.text(str(psi), (lx, ly), size=27, color="text_faint", align="center",
                   valign="middle", alpha=alpha)

    # Needle, with a counterweight tail so it reads as an instrument.
    tip = _gauge_point(cx, cy, GAUGE_R - 58, frac)
    tail = _gauge_point(cx, cy, -46, frac)
    f.draw.line([tail, tip], fill=hot, width=9)
    f.draw.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=dim, outline=hot, width=6)


def boost_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    d = hook_data()
    peak_psi = d.headline.boost or 0.0

    appear = C.ease_out(C.sub(t, 0.0, 0.14))
    # A touch of overshoot so the needle settles rather than stopping dead.
    swing = C.keyframe(t, [(0.06, 0.0), (0.46, 1.045), (0.60, 0.992), (0.70, 1.0)],
                       ease=C.ease_out)
    value = peak_psi * C.clamp01(swing)

    cx, cy = f.cx + 320, f.cy + 30
    _gauge(f, cx, cy, value, appear)

    _kicker(f, BOOST_LABEL, C.sub(t, 0.0, 0.2))
    f.text(f"{value:.1f}", (MARGIN, f.cy - 40), size=250, color="text", bold=True,
           valign="middle", alpha=appear)
    f.text("PSI", (MARGIN + 6, f.cy + 120), size=64, color="accent", bold=True,
           tracking=10, alpha=C.ease_out(C.sub(t, 0.25, 0.45)))
    _provenance(f, C.ease_out(C.sub(t, 0.55, 0.8)))
    f.vignette(0.42)
    return f


# -------------------------------------------------------------- beat 2 · dyno

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
                f"{d.headline.rev} · 3rd-gear WOT pull · "
                f"{rpm[0]:,.0f}–{rpm[-1]:,.0f} rpm · smoothed peak")
    f.vignette(0.38)
    return f


# ------------------------------------------------------------- beat 3 · climb

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
                "each bar is that revision's best logged 3rd-gear pull to redline")
    f.vignette(0.34)
    return f


# --------------------------------------------------------------- beat 4 · map

MAP_AZIM_START, MAP_AZIM_END = -172.0, -124.0


def map_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    grids = scene_surface.hero_grids()

    appear = C.ease_out(C.sub(t, 0.0, 0.14))
    morph = C.ease_in_out(C.sub(t, 0.22, 0.62))

    if grids is not None:
        azim = C.lerp(MAP_AZIM_START, MAP_AZIM_END, C.ease_in_out(t))
        # Scaled up from the deep dive's framing: this beat only gets 4 seconds,
        # so the relief has to read at a glance.
        f.paste(scene_surface.render_surface(azim, morph), (f.cx + 300, f.cy + 40),
                scale=1.24, alpha=appear)
    else:
        img = C.load(config.PREPARED["surface_hero"])
        zoom = C.ease_in_out(t)
        w, h = img.width, img.height
        inset = 0.03 + 0.04 * zoom
        rect = (w * inset, h * inset, w * (1 - inset), h * (1 - inset))
        out_w = 1180
        view = C.ken_burns(img, 0.0, rect, rect,
                           (out_w, round(out_w * (rect[3] - rect[1]) / (rect[2] - rect[0]))))
        f.card(view, (f.cx + 250, f.cy + 60), alpha=appear)

    _kicker(f, MAP_KICKER, C.sub(t, 0.0, 0.18))
    f.text(config.HERO_TABLE_ID, (MARGIN, 300), size=42, color="text", mono=True,
           alpha=appear)
    f.text(config.HERO_TABLE_DESC, (MARGIN, 356), size=31, color="text_dim",
           italic=True, max_width=520, alpha=appear)

    badge = C.sub(t, 0.22, 0.62)
    f.text("STOCK", (MARGIN, 470), size=34, color="text_faint", tracking=6,
           bold=True, alpha=appear * (1 - badge))
    f.text("TUNED", (MARGIN, 470), size=34, color="accent", tracking=6,
           bold=True, alpha=appear * badge)

    f.text(scene_surface.delta_caption(), (MARGIN, 560), size=28, color="text_dim",
           max_width=520, alpha=C.ease_out(C.sub(t, 0.6, 0.8)))
    f.vignette(0.4)
    return f


# -------------------------------------------------------------- beat 5 · logo

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
    "boost": boost_frame,
    "dyno": dyno_frame,
    "trace": scene_trace.trace_frame,
    "climb": climb_frame,
    "map": map_frame,
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
