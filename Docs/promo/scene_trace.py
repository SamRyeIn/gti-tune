#!/usr/bin/env python3
"""The table-walk beat: a tachometer and the ignition map lighting up live.

The rev counter on the right sweeps the real engine speed of the same 3rd-gear
pull the dyno beat plots, and the table on the left highlights the cell the ECU
was reading at that instant. Both are driven off one time index, so they cannot
drift apart.

The lookup is not mimed. Cell attribution uses the nearest-breakpoint rule from
`simoscal.analysis.coverage` — the same convention the log reviews use to answer
"which cells did this log exercise?" — against the breakpoints and values read
out of the newest tune-run bin (`config.newest_tune_out_dir()`, which is not
necessarily the revision currently in the car).

    python3 Docs/promo/scene_trace.py /tmp/trace_preview
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import compositor as C
import config
from compositor import Frame
from hook_data import hook_data

# The table this beat walks: rpm x airmass, the classic tuning grid.
TABLE_ID = config.SECOND_TABLE_ID
TABLE_DESC = config.SECOND_TABLE_DESC
GRID_CACHE = config.ASSET_DIR / "trace_table.npz"

KICKER = "LIVE, OFF THE LOG"

# --- table geometry (left) -------------------------------------------------
GRID_X0, GRID_Y0 = 214, 344
GRID_W, GRID_H = 940, 560

# --- tachometer geometry (right) -------------------------------------------
TACH_CX, TACH_CY = 1545, 620
TACH_R = 268
TACH_MAX_RPM = 8000.0
TACH_REDLINE = 6500.0                 # where the MK7 GTI's red band starts
TACH_START_DEG, TACH_SWEEP_DEG = 150.0, 250.0

# The pull plays across this slice of the beat, leaving a beat and a tail.
PLAY_IN, PLAY_OUT = 0.08, 0.96
TRAIL_FADE_S = 2.4                    # seconds a visited cell stays lit


# --------------------------------------------------------- the real table

def _tuned_bin() -> Path:
    out_dir = config.newest_tune_out_dir()
    bins = sorted(out_dir.glob("*.bin"))
    if not bins:
        raise FileNotFoundError(f"no saved .bin in {out_dir}")
    return bins[0]


def _extract_table() -> dict[str, np.ndarray]:
    """Read the table and its axis breakpoints out of the flashed bin."""
    if str(config.CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(config.CODE_ROOT))
    from simoscal import CalFile, render_table          # noqa: PLC0415 — heavy import

    view = render_table(CalFile.open(config.XDF_PATH, _tuned_bin()).get(TABLE_ID))
    return {
        "x": np.asarray(view.x_labels, dtype=float),    # rpm breakpoints
        "y": np.asarray(view.y_labels, dtype=float),    # airmass breakpoints
        "values": np.asarray(view.values, dtype=float),
    }


@lru_cache(maxsize=1)
def table_grid() -> dict[str, np.ndarray]:
    """The table, cached to `assets/` — the XDF parse costs about 80 s."""
    if GRID_CACHE.is_file():
        with np.load(GRID_CACHE) as z:
            return {k: z[k] for k in ("x", "y", "values")}
    grid = _extract_table()
    GRID_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(GRID_CACHE, **grid)
    return grid


@lru_cache(maxsize=1)
def walk_cells() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`(t, row, col)` — the cell the ECU read at each sample of the pull.

    Nearest breakpoint on each axis, clamping at the edges, exactly as
    `simoscal.analysis.coverage._nearest_index` attributes a sample.
    """
    d = hook_data()
    grid = table_grid()
    rpm = np.asarray(d.trace_rpm, dtype=float)
    airmass = np.asarray(d.trace_airmass, dtype=float)
    col = np.argmin(np.abs(rpm[:, None] - grid["x"][None, :]), axis=1)
    row = np.argmin(np.abs(airmass[:, None] - grid["y"][None, :]), axis=1)
    return np.asarray(d.trace_t, dtype=float), row, col


# ------------------------------------------------------------- table drawing

def _cell_box(row: int, col: int) -> tuple[float, float, float, float]:
    grid = table_grid()
    n_rows, n_cols = grid["values"].shape
    cw, ch = GRID_W / n_cols, GRID_H / n_rows
    x = GRID_X0 + col * cw
    y = GRID_Y0 + row * ch
    return (x, y, x + cw, y + ch)


def _heat(v: float, lo: float, hi: float) -> tuple[int, int, int]:
    """Cell fill by value — a cool slate ramp, deliberately not orange.

    Orange is reserved for what the log actually hit, so the trail reads as
    information rather than competing with the table's own shading.
    """
    t = C.clamp01((v - lo) / (hi - lo)) ** 1.25
    cold, warm = (19, 24, 34), (56, 76, 102)
    return tuple(round(C.lerp(a, b, t)) for a, b in zip(cold, warm))


@lru_cache(maxsize=1)
def _table_base() -> Image.Image:
    """The whole static grid — cells, values, axis labels — rendered once.

    256 cells of text a frame would dominate the render; this is pasted instead
    and only the live highlight is drawn per frame.
    """
    grid = table_grid()
    values = grid["values"]
    n_rows, n_cols = values.shape
    lo, hi = float(values.min()), float(values.max())

    img = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cell_font = C.font(17, mono=True)
    axis_font = C.font(16, mono=True)

    for r in range(n_rows):
        for c in range(n_cols):
            x0, y0, x1, y1 = _cell_box(r, c)
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=_heat(values[r, c], lo, hi),
                           outline=(38, 47, 62), width=1)
            draw.text(((x0 + x1) / 2, (y0 + y1) / 2), f"{values[r, c]:.0f}",
                      font=cell_font, fill=(158, 170, 188), anchor="mm")

    # rpm across the bottom, airmass down the left — every other breakpoint, so
    # the labels stay legible at this cell size.
    for c in range(0, n_cols, 2):
        x0, _, x1, _ = _cell_box(0, c)
        draw.text(((x0 + x1) / 2, GRID_Y0 + GRID_H + 14), f"{grid['x'][c]:.0f}",
                  font=axis_font, fill=(94, 105, 122), anchor="ma")
    for r in range(0, n_rows, 2):
        _, y0, _, y1 = _cell_box(r, 0)
        draw.text((GRID_X0 - 14, (y0 + y1) / 2), f"{grid['y'][r]:.0f}",
                  font=axis_font, fill=(94, 105, 122), anchor="rm")

    draw.text((GRID_X0, GRID_Y0 + GRID_H + 46),
              "engine speed (rpm) across   ·   airmass (mg/stk) down   ·   "
              "cells are ignition advance, degrees",
              font=axis_font, fill=(94, 105, 122), anchor="la")
    return img


def _draw_walk(f: Frame, t_now: float, alpha: float) -> tuple[int, int] | None:
    """Trail of visited cells plus the live one. Returns the live `(row, col)`."""
    t, rows, cols = walk_cells()
    reached = int(np.searchsorted(t, t_now, side="right"))
    if reached <= 0:
        return None

    overlay = Image.new("RGBA", (config.WIDTH, config.HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    seen: dict[tuple[int, int], float] = {}
    for k in range(reached):
        seen[(int(rows[k]), int(cols[k]))] = float(t[k])    # keep the latest visit
    live = (int(rows[reached - 1]), int(cols[reached - 1]))

    for (r, c), t_hit in seen.items():
        if (r, c) == live:
            continue
        age = C.clamp01((t_now - t_hit) / TRAIL_FADE_S)
        a = round(alpha * (170 * (1 - age) + 62))
        x0, y0, x1, y1 = _cell_box(r, c)
        od.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(255, 138, 46, a))
    f.paste(overlay, (0, 0), anchor="topleft")

    # The live cell, drawn solid on top with its value called out bright.
    x0, y0, x1, y1 = _cell_box(*live)
    f.rect((x0 - 3, y0 - 3, x1 + 1, y1 + 1), fill="accent", outline="text", width=3)
    f.text(f"{table_grid()['values'][live]:.0f}", ((x0 + x1) / 2, (y0 + y1) / 2 - 12),
           size=19, mono=True, color=(20, 14, 8), bold=True, align="center", alpha=alpha)
    return live


# -------------------------------------------------------------- tachometer

def _tach_point(radius: float, frac: float) -> tuple[float, float]:
    a = np.radians(TACH_START_DEG + TACH_SWEEP_DEG * frac)
    return (TACH_CX + radius * np.cos(a), TACH_CY + radius * np.sin(a))


def _tach(f: Frame, rpm: float, gear: int, alpha: float) -> None:
    """A MK7-GTI-style rev counter: 0–8, red band from 6500."""
    if alpha <= 0.01:
        return
    dim = tuple(round(c * alpha) for c in config.PALETTE["rule"])
    faint = tuple(round(c * alpha) for c in config.PALETTE["text_faint"])
    hot = tuple(round(c * alpha) for c in config.PALETTE["accent"])
    red = tuple(round(c * alpha) for c in config.PALETTE["danger"])

    box = (TACH_CX - TACH_R, TACH_CY - TACH_R, TACH_CX + TACH_R, TACH_CY + TACH_R)
    f.draw.arc(box, TACH_START_DEG, TACH_START_DEG + TACH_SWEEP_DEG, fill=dim, width=5)
    f.draw.arc(box, TACH_START_DEG + TACH_SWEEP_DEG * (TACH_REDLINE / TACH_MAX_RPM),
               TACH_START_DEG + TACH_SWEEP_DEG, fill=red, width=11)

    for step in range(0, int(TACH_MAX_RPM) + 1, 250):
        major = step % 1000 == 0
        tf = step / TACH_MAX_RPM
        r_out = TACH_R - 20
        r_in = r_out - (30 if major else 14)
        col = (red if step >= TACH_REDLINE else (faint if major else dim))
        f.draw.line([_tach_point(r_in, tf), _tach_point(r_out, tf)],
                    fill=col, width=5 if major else 2)
        if major:
            lx, ly = _tach_point(r_in - 32, tf)
            f.text(str(step // 1000), (lx, ly), size=34,
                   color="danger" if step >= TACH_REDLINE else "text_dim",
                   align="center", valign="middle", bold=True, alpha=alpha)

    frac = C.clamp01(rpm / TACH_MAX_RPM)
    f.draw.line([_tach_point(-44, frac), _tach_point(TACH_R - 52, frac)],
                fill=hot, width=8)
    f.draw.ellipse((TACH_CX - 24, TACH_CY - 24, TACH_CX + 24, TACH_CY + 24),
                   fill=config.PALETTE["bg_alt"], outline=hot, width=5)

    f.text(f"{rpm:,.0f}", (TACH_CX, TACH_CY + 108), size=62, color="text",
           align="center", bold=True, alpha=alpha)
    f.text("rpm", (TACH_CX, TACH_CY + 172), size=26, color="text_faint",
           align="center", tracking=5, alpha=alpha)
    # DSG gear, the way the cluster shows it.
    f.text(f"D{gear}", (TACH_CX, TACH_CY - 132), size=44, color="accent_2",
           align="center", bold=True, tracking=2, alpha=alpha)


# ------------------------------------------------------------------- the beat

def trace_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    d = hook_data()
    appear = C.ease_out(C.sub(t, 0.0, 0.12))

    # One clock drives both halves, so the needle and the cell cannot disagree.
    t_now = C.sub(t, PLAY_IN, PLAY_OUT) * d.trace_duration_s
    rpm_now = float(np.interp(t_now, d.trace_t, d.trace_rpm))
    airmass_now = float(np.interp(t_now, d.trace_t, d.trace_airmass))

    f.text(KICKER, (config.WIDTH - 130, 118), size=29, color="accent", tracking=8,
           bold=True, align="right", alpha=C.clamp01(C.sub(t, 0.0, 0.18) * 1.5))
    f.text(TABLE_ID, (130, 240), size=34, color="text", mono=True, alpha=appear)
    f.text(TABLE_DESC, (130, 288), size=27, color="text_dim", italic=True, alpha=appear)

    if appear > 0.02:
        f.paste(_table_base(), (0, 0), anchor="topleft", alpha=appear)
    live = _draw_walk(f, t_now, appear) if t >= PLAY_IN else None
    _tach(f, rpm_now, d.headline.gear, appear)

    if live is not None:
        grid = table_grid()
        f.text(f"{rpm_now:,.0f} rpm  ×  {airmass_now:,.0f} mg/stk   →   "
               f"{grid['values'][live]:.1f}°",
               (130, config.HEIGHT - 96), size=30, color="text", mono=True,
               alpha=appear)
    f.text(f"{d.headline.rev} · same 3rd-gear pull · nearest-breakpoint lookup",
           (config.WIDTH - 130, config.HEIGHT - 96), size=26, color="text_faint",
           tracking=3, align="right", alpha=C.ease_out(C.sub(t, 0.3, 0.5)))
    f.vignette(0.34)
    return f


def render_beat(writer, beat: config.Beat) -> None:
    writer.begin(beat)
    for i in range(beat.n_frames):
        writer.write(trace_frame(i, beat.n_frames))
    writer.end(beat)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "trace_preview")
    out.mkdir(parents=True, exist_ok=True)
    beat = config.HOOK_BEATS["trace"]
    for at in (0.15, 0.4, 0.7, 1.0):
        idx = round(at * (beat.n_frames - 1))
        trace_frame(idx, beat.n_frames).save(out / f"trace_{int(at * 100):03d}.png")
    print(f"wrote trace stills to {out}")
