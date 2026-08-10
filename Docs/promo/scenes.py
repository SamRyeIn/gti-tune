#!/usr/bin/env python3
"""Beats 1–4 and 6–8 of the promo. (Beat 5, the hero surface, is `scene_surface`.)

Each beat exposes `<name>_frame(i, n) -> Frame`, a pure function of the frame
index within the beat, so any single frame can be rendered and eyeballed
without building the video. `render_beat()` drives one over a `FrameWriter`.

Two rules the copy on screen obeys:

* Every ECU table is named **ID + plain-English description** — the same rule
  the rest of this repo follows.
* Numbers shown are read out of the real report / analysis output, not typed in
  from memory. Where a caption is hand-written, a test asserts its figures
  appear in the real source file.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

import compositor as C
import config
from compositor import Frame

MARGIN = 130

# --------------------------------------------------------------- shared copy

WORDMARK = ("simos", "cal")
TAGLINE = "Tune a Simos18 ECU. In code."
CAR_LINE = "2017 VW GTI · DSG · Simos18.1 · box code 5G0906259L_0002"

# AE6: the human-flash boundary, stated outright.
FLASH_HEADLINE = "You flash it. The library never does."
FLASH_SUB = ("simoscal writes a checksum-verified .bin and stops there. "
             "You review it, you put it on the car with SimosTools. "
             "The human is the gate.")

OUTRO_TAGLINE = "Revise. Verify. Log. Repeat."
OUTRO_HONEST = "Every revision is a starting point, not a finished calibration. Only the logs say otherwise."

LOOP_NODES = ("REVISE", "VERIFY", "FLASH", "LOG", "REVIEW")


# ------------------------------------------------------- facts from real files

def _read(key: str) -> str:
    return config.resolve_assets()[key].read_text()


@lru_cache(maxsize=1)
def verification_facts() -> list[tuple[str, str, str]]:
    """`(label, state, detail)` rows lifted out of the real `report.md`.

    Fails loud if the report's shape changes: a promo that claims a gate the
    report does not actually record would misrepresent the tool.
    """
    md = _read("report_md")
    patterns = (
        ("Checksums", r"- Checksums: \*\*(?P<state>\w+)\*\* \((?P<detail>[^)]+)\)"),
        ("Final-bin readback", r"- Final-bin readback: \*\*(?P<state>\w+)\*\* — (?P<detail>[^.]+)\."),
        ("Raw-diff audit", r"- Raw-diff audit vs `[^`]+`: \*\*(?P<state>\w+)\*\* — (?P<detail>[^.]+)\."),
        ("Switch-patch sanity",
         r"post-save verification — (?P<state>\w+) — (?P<detail>[^|]+?),\s*\d+ table\(s\) differ"),
    )
    rows: list[tuple[str, str, str]] = []
    for label, pattern in patterns:
        m = re.search(pattern, md)
        if not m:
            raise SystemExit(
                f"could not read the '{label}' gate out of report.md — the report format "
                "changed; fix the pattern in scenes.verification_facts() rather than "
                "hard-coding numbers."
            )
        rows.append((label, m.group("state"), m.group("detail").strip()))
    return rows


@lru_cache(maxsize=1)
def journal_counts() -> str:
    """The edit-journal tally line, e.g. `153 applied · 2 unchanged · …`."""
    md = _read("report_md")
    m = re.search(r"\*\*applied\*\*: (\d+)\s+\*\*unchanged\*\*: (\d+)\s+"
                  r"\*\*blocked\*\*: (\d+)\s+\*\*skipped\*\*: (\d+)", md)
    if not m:
        raise SystemExit("could not read the edit-journal tally out of report.md")
    applied, unchanged, blocked, skipped = m.groups()
    return f"{applied} applied · {unchanged} unchanged · {blocked} blocked · {skipped} skipped"


# --------------------------------------------------------------- furniture


def chapter(f: Frame, number: str, label: str, title: str, t_in: float = 1.0,
            x: int = MARGIN, y: int = 96, title_size: int = 74) -> int:
    """Beat header: `01 · REVISE` over a headline. Returns the baseline below it."""
    rise = (1 - C.ease_out(t_in)) * 30
    f.text(f"{number} · {label}", (x, y - rise), size=27, color="accent",
           tracking=7, bold=True, alpha=C.clamp01(t_in * 1.4))
    box = f.text(title, (x, y + 48 - rise * 0.6), size=title_size, color="text",
                 bold=True, max_width=config.WIDTH - 2 * x,
                 alpha=C.clamp01((t_in - 0.15) * 1.8))
    return box[3]


def check_mark(f: Frame, xy: tuple[float, float], size: float, t: float,
               color: str = "good", width: int = 6) -> None:
    """A tick that draws itself in over `t` (0..1)."""
    t = C.clamp01(t)
    if t <= 0:
        return
    x, y = xy
    p0 = (x - size * 0.45, y)
    p1 = (x - size * 0.12, y + size * 0.36)
    p2 = (x + size * 0.5, y - size * 0.42)
    col = config.PALETTE[color]
    leg1 = min(t / 0.4, 1.0)
    pts = [p0, (C.lerp(p0[0], p1[0], leg1), C.lerp(p0[1], p1[1], leg1))]
    if t > 0.4:
        leg2 = (t - 0.4) / 0.6
        pts.append((C.lerp(p1[0], p2[0], leg2), C.lerp(p1[1], p2[1], leg2)))
    f.draw.line(pts, fill=col, width=width, joint="curve")


def footer(f: Frame, text: str, alpha: float = 1.0, color: str = "text_faint") -> None:
    f.text(text, (MARGIN, config.HEIGHT - 86), size=28, color=color,
           tracking=4, alpha=alpha)


def _asset(key: str):
    return C.load(config.PREPARED[key])


@lru_cache(maxsize=8)
def _scaled_asset(key: str, width: int, keep: float = 1.0):
    """An asset pre-scaled once to its on-screen width.

    Scenes that pan or hold a still do it by cropping this, so the expensive
    LANCZOS resample happens once instead of on all ~2700 frames.
    """
    img = _asset(key)
    if keep < 1.0:
        img = img.crop((0, 0, img.width, round(img.height * keep)))
    height = round(img.height * width / img.width)
    return img.resize((width, height), C.Image.LANCZOS)


# ------------------------------------------------------------------- beat 1

def title_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()

    # A faint grid — a nod to the calibration tables, kept well under the type.
    grid_a = C.ease_out(C.sub(t, 0.0, 0.6))
    if grid_a > 0:
        step = 96
        col = tuple(round(C.lerp(config.PALETTE["bg"][k], config.PALETTE["rule"][k],
                                 0.55 * grid_a)) for k in range(3))
        for gx in range(0, config.WIDTH + 1, step):
            f.draw.line([(gx, 0), (gx, config.HEIGHT)], fill=col, width=1)
        for gy in range(0, config.HEIGHT + 1, step):
            f.draw.line([(0, gy), (config.WIDTH, gy)], fill=col, width=1)

    mark_t = C.ease_out(C.sub(t, 0.05, 0.45))
    size = 168
    fnt = C.font(size, mono=True)
    w0, w1 = (fnt.getlength(s) for s in WORDMARK)
    x0 = f.cx - (w0 + w1) / 2
    y = f.cy - 150 - (1 - mark_t) * 24
    f.text(WORDMARK[0], (x0, y), size=size, mono=True, color="text", alpha=mark_t)
    f.text(WORDMARK[1], (x0 + w0, y), size=size, mono=True, color="accent", alpha=mark_t)

    rule_t = C.ease_in_out(C.sub(t, 0.3, 0.62))
    if rule_t > 0:
        half = 430 * rule_t
        f.line((f.cx - half, y + size * 1.42), (f.cx + half, y + size * 1.42),
               color="rule", width=3)

    f.text(TAGLINE, (f.cx, y + size * 1.62), size=62, color="text",
           align="center", bold=True, alpha=C.ease_out(C.sub(t, 0.4, 0.7)))
    f.text(CAR_LINE, (f.cx, y + size * 1.62 + 108), size=30, color="text_dim",
           align="center", tracking=4, alpha=C.ease_out(C.sub(t, 0.6, 0.9)))
    f.vignette(0.4)
    return f


# ------------------------------------------------------------------- beat 2

CODE_CALLOUT = ("AIRMASS_CAP_MG = 2000  →  C_M_AIR_CYL_SP_MAX — Maximum allowed "
                "airmass setpoint")
CODE_SUB = ("Physical units in, raw bytes out — 2000 mg/stk goes on the wire as 0.002. "
            "Every call carries its intent.")


def code_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    chapter(f, "01", "REVISE", "Write the calibration, not the hex.",
            t_in=C.sub(t, 0.0, 0.25))

    card = _asset("code_snippet")
    scale = 0.70
    reveal = C.ease_in_out(C.sub(t, 0.12, 0.55))
    top_y = 296
    if reveal > 0:
        head = 0.13                       # window chrome is there from the start
        visible = card.height * (head + (1 - head) * reveal)
        shown = card.crop((0, 0, card.width, max(round(visible), 2)))
        f.card(shown, (f.cx, top_y), scale=scale, anchor="topcenter", radius=16)

        # Highlight the physical-units call once the card has finished drawing.
        hl = C.sub(t, 0.58, 0.72)
        if hl > 0:
            cw, ch = card.width * scale, card.height * scale
            x0 = f.cx - cw / 2
            # The `tune.limits.airmass_cap_mg(...)` block sits in the last third.
            y0 = top_y + ch * 0.70
            y1 = top_y + ch * 0.985
            glow = 0.35 + 0.65 * C.pulse(C.sub(t, 0.58, 1.0))
            f.rect((x0 + 26, y0, x0 + cw - 26, y1), outline=tuple(
                round(C.lerp(config.PALETTE["bg_alt"][k], config.PALETTE["accent"][k], glow))
                for k in range(3)), width=3, radius=10)

    f.text(CODE_CALLOUT, (f.cx, config.HEIGHT - 186), size=34, color="text",
           align="center", max_width=1640, alpha=C.ease_out(C.sub(t, 0.62, 0.78)))
    f.text(CODE_SUB, (f.cx, config.HEIGHT - 124), size=28, color="text_dim",
           align="center", max_width=1500, alpha=C.ease_out(C.sub(t, 0.72, 0.88)))
    return f


# ------------------------------------------------------------------- beat 3

VERIFY_CLOSER = "Checksum-verified. Read back. Byte-audited. Before a cable is plugged in."


def verify_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    chapter(f, "02", "VERIFY", "Prove it before it leaves the laptop.",
            t_in=C.sub(t, 0.0, 0.22))

    rows = verification_facts()
    row_h = 132
    top = 320
    x0, x1 = MARGIN, config.WIDTH - MARGIN
    for k, (label, state, detail) in enumerate(rows):
        appear = C.ease_out(C.sub(t, 0.16 + k * 0.12, 0.34 + k * 0.12))
        if appear <= 0:
            continue
        dx = (1 - appear) * -60
        y = top + k * row_h
        f.rect((x0 + dx, y, x1 + dx, y + row_h - 22), fill="bg_alt", radius=14)
        f.rect((x0 + dx, y, x0 + dx + 7, y + row_h - 22), fill="good", radius=3)
        f.text(label.upper(), (x0 + dx + 44, y + 24), size=24, color="text_faint",
               tracking=4, alpha=appear)
        f.text(state, (x0 + dx + 44, y + 58), size=40, color="good",
               bold=True, alpha=appear)
        f.text(detail, (x0 + dx + 560, y + (row_h - 22) / 2), size=31, color="text_dim",
               valign="middle", max_width=x1 - x0 - 700, alpha=appear)
        check_mark(f, (x1 + dx - 70, y + 52), 44,
                   C.sub(t, 0.26 + k * 0.12, 0.40 + k * 0.12))

    f.text(f"Edit journal: {journal_counts()}", (f.cx, config.HEIGHT - 172), size=30,
           color="text_faint", align="center", alpha=C.ease_out(C.sub(t, 0.7, 0.84)))
    f.text(VERIFY_CLOSER, (f.cx, config.HEIGHT - 116), size=38, color="accent_2",
           align="center", bold=True, alpha=C.ease_out(C.sub(t, 0.76, 0.9)))
    return f


# ------------------------------------------------------------------- beat 4
# The report screenshot is ~1918x6390. The pan holds on the three sections a
# human actually reads before flashing.

REPORT_CARD = (700, 60, 1800, 1020)          # x0, y0, x1, y1 on the canvas
REPORT_STOPS = (
    (0.00, "The flash gate", "Reviewable, not approved — every automated gate passed. You decide."),
    (0.34, "Needs your eyes", "Recipe steps the library refused to apply blind, each with its reason."),
    (0.66, "Changed this flash", "Every table that moved, with before/after curves, heatmaps and surfaces."),
)


def _report_pan_rect(t: float, img_w: int, img_h: int, view_h: float
                     ) -> tuple[float, float, float, float]:
    travel = img_h - view_h
    y0 = C.keyframe(t, [
        (0.00, 0.0), (0.14, 0.0),
        (0.34, travel * 0.34), (0.48, travel * 0.34),
        (0.66, travel * 0.70), (0.80, travel * 0.70),
        (0.95, travel), (1.00, travel),
    ])
    return (0.0, y0, float(img_w), y0 + view_h)


def report_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    cx0, cy0, cx1, cy1 = REPORT_CARD
    card_w, card_h = cx1 - cx0, cy1 - cy0
    img = _scaled_asset("report", card_w)      # pan by cropping, not resampling
    rect = _report_pan_rect(t, img.width, img.height, card_h)
    view = img.crop(tuple(round(v) for v in rect))

    intro = C.ease_out(C.sub(t, 0.0, 0.18))
    f.card(view, (cx0 + (1 - intro) * 80, cy0), anchor="topleft", radius=18,
           alpha=intro)

    chapter(f, "03", "REVIEW", "Every flash\ncomes with\na receipt.",
            t_in=C.sub(t, 0.05, 0.28), title_size=64)

    # The left column tracks whichever section the pan is sitting on.
    for k, (start, heading, blurb) in enumerate(REPORT_STOPS):
        nxt = REPORT_STOPS[k + 1][0] if k + 1 < len(REPORT_STOPS) else 1.01
        a = min(C.sub(t, start, start + 0.06), 1.0 - C.sub(t, nxt - 0.04, nxt))
        if a <= 0:
            continue
        f.text(heading.upper(), (MARGIN, 560), size=28, color="accent",
               tracking=6, bold=True, alpha=a)
        f.text(blurb, (MARGIN, 608), size=34, color="text_dim",
               max_width=cx0 - MARGIN - 90, alpha=a)

    footer(f, "report.html · written every run",
           alpha=C.ease_out(C.sub(t, 0.3, 0.5)))
    return f


# ------------------------------------------------------------------- beat 6

def flash_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    chapter(f, "05", "FLASH", FLASH_HEADLINE, t_in=C.sub(t, 0.0, 0.3), title_size=72)

    # .bin  ->  phone (SimosTools)  ->  ECU. The dot only moves once "you" tap.
    y = 540
    stops = [(430, ".bin", "checksum-verified"), (960, "SimosTools", "you tap flash"),
             (1490, "ECU", "Simos18.1")]
    appear = C.ease_out(C.sub(t, 0.2, 0.5))
    for x, label, sub in stops:
        w, h = 260, 150
        f.rect((x - w / 2, y - h / 2, x + w / 2, y + h / 2), fill="bg_alt",
               outline="rule", width=2, radius=18)
        f.text(label, (x, y - 18), size=40, color="text", align="center",
               bold=True, alpha=appear)
        f.text(sub, (x, y + 34), size=26, color="text_faint", align="center", alpha=appear)

    travel = C.ease_in_out(C.sub(t, 0.45, 0.85))
    for a, b in ((stops[0][0], stops[1][0]), (stops[1][0], stops[2][0])):
        f.line((a + 140, y), (b - 140, y), color="rule", width=3)
    if travel > 0:
        px = C.lerp(stops[0][0] + 140, stops[2][0] - 140, travel)
        f.draw.ellipse([px - 11, y - 11, px + 11, y + 11], fill=config.PALETTE["accent"])

    # The one line that must be on screen: the library never flashes. (AE6)
    f.text(FLASH_SUB, (f.cx, config.HEIGHT - 250), size=36, color="text_dim",
           align="center", max_width=1450, alpha=C.ease_out(C.sub(t, 0.35, 0.6)))
    f.text("simoscal never talks to the car.", (f.cx, config.HEIGHT - 130), size=42,
           color="danger", align="center", bold=True, alpha=C.ease_out(C.sub(t, 0.6, 0.8)))
    return f


# ------------------------------------------------------------------- beat 7
# Captions are short-form restatements of the real analysis-battery findings for
# this revision; `test_scenes.py` asserts every figure quoted here appears in
# `analysis_findings.md`.

LOG_CARDS = (
    # (asset, heading, caption, keep) — `keep` crops a stacked figure to its top
    # panel so it stays readable at 1080p; 1.0 shows the whole plot.
    ("log_knock", "Knock retard",
     "Minor pull to -3.0 deg on one pull — the next revision's timing target.", 1.0),
    ("log_boost", "Boost tracking",
     "PUT overshoots setpoint by +12.3 kPa near 3704 rpm on the spool transient.", 0.332),
    ("log_lambda", "Lambda",
     "Settled-WOT lambda tracks target: max lean +0.028, under the +0.03 watch line.", 1.0),
    ("log_rail", "Rail pressure and pump headroom",
     "Worst DI rail sag -4.9 bar; LPFP duty peaks 80.1%; HPFP eff. volume peaks 97.7%.", 0.52),
)

LOGS_CLOSER = "Findings are evidence, not opinions — every one points at the plot it came from."

LOG_CARD_BOX = (1300, 520)      # max width, max height on the canvas


@lru_cache(maxsize=8)
def _log_card_image(key: str, keep: float):
    """The plot as it appears on screen, resampled once per beat run."""
    max_w, max_h = LOG_CARD_BOX
    src = _asset(key)
    if keep < 1.0:
        src = src.crop((0, 0, src.width, round(src.height * keep)))
    return C.fit(src, max_w=max_w, max_h=max_h)


def logs_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    chapter(f, "06", "LOG", "Then the logs decide.", t_in=C.sub(t, 0.0, 0.12))

    slots = len(LOG_CARDS)
    span = 1.0 / slots
    k = min(int(t / span), slots - 1)
    local = (t - k * span) / span
    key, heading, caption, keep = LOG_CARDS[k]

    fade_in = C.ease_out(C.sub(local, 0.0, 0.18))
    fade_out = 1.0 - C.ease_in(C.sub(local, 0.86, 1.0)) if k < slots - 1 else 1.0
    a = min(fade_in, fade_out)
    slide = (1 - fade_in) * 90 - (1 - fade_out) * 90

    f.card(_log_card_image(key, keep), (f.cx + slide, 720), alpha=a, radius=14)

    f.text(f"{k + 1}/{slots}  ·  {heading.upper()}", (MARGIN, 286), size=27,
           color="accent_2", tracking=5, bold=True, alpha=a)
    f.text(caption, (MARGIN, 330), size=36, color="text", max_width=1560, alpha=a)

    footer(f, LOGS_CLOSER, alpha=C.ease_out(C.sub(t, 0.08, 0.2)))
    return f


# ------------------------------------------------------------------- beat 8

def outro_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()

    cx, cy, r = f.cx, f.cy - 30, 300
    draw_t = C.ease_in_out(C.sub(t, 0.05, 0.62))
    if draw_t > 0:
        f.draw.arc([cx - r, cy - r, cx + r, cy + r], start=-90,
                   end=-90 + 360 * draw_t, fill=config.PALETTE["accent"], width=7)

    closed = C.sub(t, 0.62, 0.74)
    if closed > 0:                                   # the loop visibly closes
        glow = round(C.pulse(closed) * 90)
        col = tuple(min(255, config.PALETTE["accent"][k] + glow) for k in range(3))
        f.draw.arc([cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4],
                   start=-90, end=270, fill=col, width=3)

    for k, name in enumerate(LOOP_NODES):
        frac = k / len(LOOP_NODES)
        node_t = C.ease_out(C.sub(draw_t, frac, frac + 0.12))
        if node_t <= 0:
            continue
        ang = math.radians(-90 + 360 * frac)
        nx, ny = cx + r * math.cos(ang), cy + r * math.sin(ang)
        rad = 13 + 4 * C.pulse(C.sub(draw_t, frac, frac + 0.2))
        f.draw.ellipse([nx - rad, ny - rad, nx + rad, ny + rad],
                       fill=config.PALETTE["bg"], outline=config.PALETTE["accent"], width=5)
        lx = nx + math.cos(ang) * 72
        ly = ny + math.sin(ang) * 72
        align = "center" if abs(math.cos(ang)) < 0.35 else ("left" if math.cos(ang) > 0 else "right")
        f.text(name, (lx, ly), size=30, color="text", align=align, valign="middle",
               tracking=4, bold=True, alpha=node_t)

    mark_t = C.ease_out(C.sub(t, 0.55, 0.78))
    if mark_t > 0:
        size = 92
        fnt = C.font(size, mono=True)
        w0, w1 = (fnt.getlength(s) for s in WORDMARK)
        x0 = cx - (w0 + w1) / 2
        f.text(WORDMARK[0], (x0, cy - size * 0.62), size=size, mono=True,
               color="text", alpha=mark_t)
        f.text(WORDMARK[1], (x0 + w0, cy - size * 0.62), size=size, mono=True,
               color="accent", alpha=mark_t)

    f.text(OUTRO_TAGLINE, (cx, config.HEIGHT - 190), size=56, color="text",
           align="center", bold=True, alpha=C.ease_out(C.sub(t, 0.74, 0.88)))
    f.text(OUTRO_HONEST, (cx, config.HEIGHT - 108), size=28, color="text_dim",
           align="center", max_width=1500, alpha=C.ease_out(C.sub(t, 0.82, 0.94)))
    return f


# --------------------------------------------------------------------- driver

FRAME_BUILDERS = {
    "title": title_frame,
    "code": code_frame,
    "verify": verify_frame,
    "report": report_frame,
    "flash": flash_frame,
    "logs": logs_frame,
    "outro": outro_frame,
}


def render_beat(writer, beat: config.Beat) -> None:
    """Render one beat's frames through the shared writer."""
    build = FRAME_BUILDERS[beat.id]
    writer.begin(beat)
    for i in range(beat.n_frames):
        writer.write(build(i, beat.n_frames))
    writer.end(beat)


def preview(beat_id: str, at: float, dest: Path) -> Path:
    """Render a single frame of a beat (`at` in 0..1) for eyeballing."""
    beat = config.BEATS[beat_id]
    build = FRAME_BUILDERS[beat_id]
    i = round(C.clamp01(at) * (beat.n_frames - 1))
    build(i, beat.n_frames).save(dest)
    return dest


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "preview")
    out.mkdir(parents=True, exist_ok=True)
    for bid in FRAME_BUILDERS:
        for at in (0.35, 0.75, 1.0):
            preview(bid, at, out / f"{bid}_{int(at * 100):03d}.png")
    print(f"previews in {out}")
