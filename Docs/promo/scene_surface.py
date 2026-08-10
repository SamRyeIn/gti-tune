#!/usr/bin/env python3
"""Beat 5 — the hero: `IP_FAC_BPA_SP[0]` turning in 3D, stock morphing to tuned.

Two paths, and the module records which one ran so the build log (and the QA
step) knows what shipped:

* **rotation** (preferred) — the table's real grid is read out of the stock bin
  and the R14 tuned bin with `simoscal`, then re-plotted as a matplotlib 3D
  surface sweeping azimuth, morphing stock -> tuned mid-beat. True rotation,
  true numbers.
* **parallax** (fallback) — if `simoscal` or either bin is unreachable, a slow
  push-in on the real `*_compare_surface.png` the tune run already wrote.

Either way the surface on screen is the real calibration; the fallback just
cannot turn it.
"""

from __future__ import annotations

import sys
from functools import lru_cache

import numpy as np
from PIL import Image

import compositor as C
import config
from compositor import Frame
from scenes import MARGIN, chapter, footer

# Which path this build used: None until first asked, then "rotation"/"parallax".
SURFACE_PATH: str | None = None

TABLE_ID = config.HERO_TABLE_ID
TABLE_DESC = config.HERO_TABLE_DESC
X_AXIS_LABEL = "x · ldp_fac_1_ip_fac_bpa_sp (-)"
Y_AXIS_LABEL = "y · ldp_fac_2_ip_fac_bpa_sp (-)"

HEADLINE = "See the change, not a diff."
STOCK_BADGE = "STOCK  ·  5G0906259L_0002"
TUNED_BADGE = "TUNED  ·  BasicsGuide R14"

GRID_CACHE = config.ASSET_DIR / "hero_surface.npz"

# Kept inside the arc where the ridge stays readable — past about -110 deg the
# surface goes edge-on and the relief disappears.
AZIM_START, AZIM_END = -168.0, -118.0
ELEV = 30.0
MORPH_IN, MORPH_OUT = 0.34, 0.60
FIG_PX = (1250, 860)


# ------------------------------------------------------------- the real grids

def _tuned_bin() -> "config.Path":
    out_dir = config.newest_tune_out_dir()
    bins = sorted(out_dir.glob("*.bin"))
    if not bins:
        raise FileNotFoundError(f"no saved .bin in {out_dir}")
    return bins[0]


def _extract_grids() -> dict[str, np.ndarray]:
    """Read the hero table out of the stock and tuned bins via `simoscal`.

    Parsing the XDF takes ~40 s, so the result is cached to `assets/` and the
    build only pays it once.
    """
    if str(config.CODE_ROOT) not in sys.path:
        sys.path.insert(0, str(config.CODE_ROOT))
    from simoscal import CalFile, render_table   # noqa: PLC0415 — optional dependency

    stock = render_table(CalFile.open(config.XDF_PATH, config.STOCK_BIN).get(TABLE_ID))
    tuned = render_table(CalFile.open(config.XDF_PATH, _tuned_bin()).get(TABLE_ID))
    return {
        "x": np.asarray(stock.x_labels, dtype=float),
        "y": np.asarray(stock.y_labels, dtype=float),
        "stock": np.asarray(stock.values, dtype=float),
        "tuned": np.asarray(tuned.values, dtype=float),
    }


@lru_cache(maxsize=1)
def hero_grids() -> dict[str, np.ndarray] | None:
    """The real before/after grids, or None if the rotation path is unreachable."""
    global SURFACE_PATH
    try:
        if GRID_CACHE.is_file():
            with np.load(GRID_CACHE) as z:
                grids = {k: z[k] for k in ("x", "y", "stock", "tuned")}
        else:
            grids = _extract_grids()
            GRID_CACHE.parent.mkdir(parents=True, exist_ok=True)
            np.savez(GRID_CACHE, **grids)
    except Exception as exc:                      # noqa: BLE001 — any failure -> fallback
        print(f"[surface] real-rotation path unavailable ({exc.__class__.__name__}: {exc});"
              " falling back to parallax on the compare PNG")
        SURFACE_PATH = "parallax"
        return None
    SURFACE_PATH = "rotation"
    return grids


def delta_caption() -> str:
    """An honest one-liner about how much of the map actually moved."""
    grids = hero_grids()
    if grids is None:
        return f"{TABLE_ID} — {TABLE_DESC}"
    d = grids["tuned"] - grids["stock"]
    moved = int(np.count_nonzero(np.abs(d) > 1e-9))
    return (f"{moved} of {d.size} cells moved · biggest step "
            f"{np.abs(d).max():+.2f} · stock vs BasicsGuide R14")


# ------------------------------------------------------------- the 3D surface

def _make_figure():
    from matplotlib.figure import Figure           # noqa: PLC0415 — heavy import
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(FIG_PX[0] / 100, FIG_PX[1] / 100), dpi=100)
    FigureCanvasAgg(fig)
    fig.patch.set_alpha(0.0)
    return fig


def _style_axes(ax) -> None:
    """Make the 3D axes read on a near-black canvas."""
    dim = "#7b879b"
    ax.set_facecolor("none")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((1.0, 1.0, 1.0, 0.025))
        axis.line.set_color(dim)
        try:                                        # grid colour lives in a private dict
            axis._axinfo["grid"]["color"] = (1.0, 1.0, 1.0, 0.10)
        except (AttributeError, KeyError, TypeError):
            pass
    from matplotlib.ticker import MaxNLocator     # noqa: PLC0415 — heavy import
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_major_locator(MaxNLocator(5))     # fewer glyphs = faster draw
    ax.tick_params(colors=dim, labelsize=9)
    ax.set_xlabel(X_AXIS_LABEL, color=dim, fontsize=10, labelpad=10)
    ax.set_ylabel(Y_AXIS_LABEL, color=dim, fontsize=10, labelpad=10)
    ax.set_zlabel("setpoint (-)", color=dim, fontsize=10, labelpad=8, fontweight="bold")


@lru_cache(maxsize=1)
def _figure_and_axes():
    """One styled figure reused for every frame — rebuilding it costs ~0.5 s."""
    fig = _make_figure()
    ax = fig.add_subplot(projection="3d")
    _style_axes(ax)
    return fig, ax


def render_surface(azim: float, morph: float) -> Image.Image:
    """One frame of the rotating surface as an RGBA image (transparent ground).

    Deterministic in `(azim, morph)`; the figure it draws into is reused.
    """
    grids = hero_grids()
    assert grids is not None, "render_surface called without the real grids"
    x, y = grids["x"], grids["y"]
    z = grids["stock"] + (grids["tuned"] - grids["stock"]) * C.clamp01(morph)
    xx, yy = np.meshgrid(x, y)

    fig, ax = _figure_and_axes()
    for artist in list(ax.collections):
        artist.remove()
    lo = float(min(grids["stock"].min(), grids["tuned"].min()))
    hi = float(max(grids["stock"].max(), grids["tuned"].max()))
    ax.plot_surface(xx, yy, z, cmap="inferno", vmin=lo, vmax=hi,
                    edgecolor=(0, 0, 0, 0.35), linewidth=0.3, antialiased=True)
    ax.set_zlim(lo, hi)
    ax.view_init(elev=ELEV, azim=azim)
    ax.set_box_aspect((1, 1, 0.62))
    # `tight_layout` costs a whole extra draw pass on a 3D axes (~0.5 s a frame
    # over 420 frames); the plot box is fixed here instead.
    ax.set_position((0.02, 0.02, 0.96, 0.96))

    fig.canvas.draw()
    return Image.frombytes("RGBA", fig.canvas.get_width_height(),
                           bytes(fig.canvas.buffer_rgba()))


# ------------------------------------------------------------------- the beat

def surface_frame(i: int, n: int) -> Frame:
    t = i / max(n - 1, 1)
    f = Frame()
    chapter(f, "04", "SEE THE CHANGE", HEADLINE, t_in=C.sub(t, 0.0, 0.18))

    grids = hero_grids()
    appear = C.ease_out(C.sub(t, 0.06, 0.28))
    morph = C.ease_in_out(C.sub(t, MORPH_IN, MORPH_OUT))

    if grids is not None:
        azim = C.lerp(AZIM_START, AZIM_END, C.ease_in_out(t))
        f.paste(render_surface(azim, morph), (f.cx + 190, 630), alpha=appear)
    else:
        # Parallax fallback: a slow push-in and drift on the real compare surface.
        # The inset always exceeds the drift, so the crop stays inside the image.
        img = C.load(config.PREPARED["surface_hero"])
        zoom = C.ease_in_out(t)
        w, h = img.width, img.height
        inset = 0.028 + 0.042 * zoom
        drift = h * 0.025 * (zoom - 0.5)
        rect = (w * inset, h * inset + drift, w * (1 - inset), h * (1 - inset) + drift)
        out_w = 1500
        view = C.ken_burns(img, 0.0, rect, rect,
                           (out_w, round(out_w * (rect[3] - rect[1]) / (rect[2] - rect[0]))))
        f.card(view, (f.cx, 660), alpha=appear)

    # The table, named the way this repo always names tables.
    f.text(TABLE_ID, (MARGIN, 300), size=44, color="text", mono=True, alpha=appear)
    f.text(TABLE_DESC, (MARGIN, 356), size=32, color="text_dim", italic=True,
           max_width=560, alpha=appear)

    badge_t = C.sub(t, MORPH_IN, MORPH_OUT)
    f.text(STOCK_BADGE, (MARGIN, 470), size=27, color="text_faint", tracking=4,
           alpha=appear * (1 - badge_t))
    f.text(TUNED_BADGE, (MARGIN, 470), size=27, color="accent", tracking=4,
           bold=True, alpha=appear * badge_t)

    f.text(delta_caption(), (MARGIN, 540), size=29, color="text_dim",
           max_width=560, alpha=C.ease_out(C.sub(t, 0.62, 0.76)))
    footer(f, "compare surfaces are written for every table that moves",
           alpha=C.ease_out(C.sub(t, 0.2, 0.4)))
    return f


def render_beat(writer, beat: config.Beat) -> None:
    writer.begin(beat)
    for i in range(beat.n_frames):
        writer.write(surface_frame(i, beat.n_frames))
    writer.end(beat)


if __name__ == "__main__":
    from pathlib import Path

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "preview")
    out.mkdir(parents=True, exist_ok=True)
    beat = config.BEATS["surface"]
    for at in (0.1, 0.45, 0.8, 1.0):
        i = round(at * (beat.n_frames - 1))
        surface_frame(i, beat.n_frames).save(out / f"surface_{int(at * 100):03d}.png")
    print(f"surface path: {SURFACE_PATH} — previews in {out}")
