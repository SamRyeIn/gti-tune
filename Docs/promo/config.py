"""Canvas, palette, fonts, beat timeline, and real-asset manifest for the promo.

Everything the promo build depends on that is *not* drawing logic lives here, so
the video can be re-pointed at a newer tune revision or a different machine by
editing one file.

The assets are deliberately resolved from the repo's real output folders (newest
tune-run out dir, newest log-analysis plots folder) rather than being copied in
by hand: the promo is meant to show what the library actually produces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------- canvas / time

WIDTH = 1920
HEIGHT = 1080
FPS = 30

PROMO_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROMO_DIR.parents[1]
ASSET_DIR = PROMO_DIR / "assets"
FRAME_DIR = PROMO_DIR / "frames"
OUT_MP4 = PROMO_DIR / "simoscal_promo.mp4"

# ---------------------------------------------------------------------- palette

PALETTE = {
    "bg": (11, 14, 20),           # near-black, slightly blue
    "bg_alt": (18, 23, 32),       # panel fill
    "rule": (44, 54, 70),         # hairlines / borders
    "text": (236, 240, 246),      # primary display text
    "text_dim": (150, 162, 180),  # secondary / captions
    "text_faint": (94, 105, 122), # tertiary / labels
    "accent": (255, 138, 46),     # simoscal orange — boost/heat
    "accent_2": (86, 190, 255),   # cool blue — verification
    "good": (98, 214, 140),       # checks pass
    "warn": (255, 205, 92),       # knock / caution
    "danger": (255, 96, 96),      # limits / flash gate
}

# ------------------------------------------------------------------------ fonts
# Explicit TTF paths: PIL will not resolve font families by name. These are the
# stock macOS faces; swap them here if the build ever moves to another machine.

FONT_DISPLAY = Path("/System/Library/Fonts/SFNS.ttf")
FONT_DISPLAY_ITALIC = Path("/System/Library/Fonts/SFNSItalic.ttf")
FONT_MONO = Path("/System/Library/Fonts/Menlo.ttc")
FONT_FALLBACK = Path("/System/Library/Fonts/Supplemental/Arial.ttf")

# SFNS.ttf is a variable font; PIL renders its default (regular) instance. Bold
# display weight is faked by the compositor via a small stroke width.
STROKE_BOLD = 1.6

# --------------------------------------------------------------------- timeline


@dataclass(frozen=True)
class Beat:
    """One narrative beat of the tuning loop, with its time window in seconds."""

    id: str
    start_s: float
    end_s: float
    title: str

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def start_frame(self) -> int:
        return round(self.start_s * FPS)

    @property
    def end_frame(self) -> int:
        """Exclusive end frame index."""
        return round(self.end_s * FPS)

    @property
    def n_frames(self) -> int:
        return self.end_frame - self.start_frame


# The eight beats of the loop, in narrative order. Beat 5 is the hero.
TIMELINE: tuple[Beat, ...] = (
    Beat("title",    0.0,  6.0,  "Tune a Simos18 ECU. In code."),
    Beat("code",     6.0,  18.0, "Write the calibration"),
    Beat("verify",   18.0, 30.0, "Prove it before it leaves the laptop"),
    Beat("report",   30.0, 42.0, "Read the report"),
    Beat("surface",  42.0, 56.0, "See the change"),
    Beat("flash",    56.0, 62.0, "You flash it"),
    Beat("logs",     62.0, 80.0, "The logs decide"),
    Beat("outro",    80.0, 90.0, "Revise. Verify. Log. Repeat."),
)

BEATS = {b.id: b for b in TIMELINE}


def frame_index(t_s: float) -> int:
    """Global frame index for an absolute timeline time in seconds."""
    return round(t_s * FPS)


def frames_for(beat: Beat | str) -> int:
    """Number of frames a beat owns."""
    b = BEATS[beat] if isinstance(beat, str) else beat
    return b.n_frames


def total_frames() -> int:
    return sum(b.n_frames for b in TIMELINE)


def total_duration_s() -> float:
    return total_frames() / FPS


# ----------------------------------------------------------------- asset lookup

TUNE_DIR = REPO_ROOT / "Tunes" / "TuningBasicsGuide"
TUNE_OUT_ROOT = TUNE_DIR / "TUNE_Basics_Guide_out"
LOGS_ROOT = REPO_ROOT / "Logs"

# The hero table and its supporting cast, named ID + plain-English everywhere.
HERO_TABLE_ID = "IP_FAC_BPA_SP[0]"
HERO_TABLE_DESC = "Map for boost pressure actuator setpoint"
SECOND_TABLE_ID = "IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]"
SECOND_TABLE_DESC = "Basic ignition angle, low port flap, standard"

_REV_RE = re.compile(r"^R(\d+)(?:[_-].*)?$")


def _rev_sort_key(path: Path) -> tuple[int, str]:
    """Sort `R14_20260810-111002` style names by revision number then name."""
    m = _REV_RE.match(path.name)
    if not m:
        m2 = re.search(r"R(\d+)", path.name)
        return (int(m2.group(1)) if m2 else -1, path.name)
    return (int(m.group(1)), path.name)


def newest_tune_out_dir(root: Path = TUNE_OUT_ROOT) -> Path:
    """Newest `R<NN>_<timestamp>/` run folder that contains a report.

    `Test/` subtrees are other-model comparison runs, not part of the tune
    lineage, so they are excluded.
    """
    candidates = [
        d for d in root.glob("R*")
        if d.is_dir() and (d / "report.html").is_file() and "Test" not in d.parts
    ]
    if not candidates:
        raise FileNotFoundError(f"No tune-run output dir with a report.html under {root}")
    return max(candidates, key=_rev_sort_key)


def newest_log_plots_dir(root: Path = LOGS_ROOT) -> Path:
    """Newest `Logs/BasicsGuide_R<NN>/plots/` folder from the analysis battery."""
    candidates = [
        d / "plots" for d in root.glob("BasicsGuide_R*")
        if (d / "plots").is_dir() and any((d / "plots").glob("analysis_*.png"))
    ]
    if not candidates:
        raise FileNotFoundError(f"No Logs/BasicsGuide_R*/plots folder with analysis PNGs under {root}")
    return max(candidates, key=lambda p: _rev_sort_key(p.parent))


@lru_cache(maxsize=1)
def resolve_assets() -> dict[str, Path]:
    """Absolute source paths for every real asset the promo draws from.

    Raises if anything is missing — a promo built from placeholder art would
    misrepresent the tool, so this fails loud rather than degrading.
    """
    out_dir = newest_tune_out_dir()
    compare = out_dir / "compare"
    plots = newest_log_plots_dir()

    assets: dict[str, Path] = {
        "report_html": out_dir / "report.html",
        "report_md": out_dir / "report.md",
        "surface_hero": compare / f"{HERO_TABLE_ID}__compare_surface.png",
        "heatmap_hero": compare / f"{HERO_TABLE_ID}__compare_heatmap.png",
        "surface_ignition": compare / f"{SECOND_TABLE_ID}__compare_surface.png",
        "log_knock": plots / "analysis_knock.png",
        "log_lambda": plots / "analysis_lambda.png",
        "log_rail": plots / "analysis_rail_pressure.png",
        "log_boost": plots / "analysis_boost.png",
        "log_coverage": plots / "analysis_coverage_IP_FAC_BPA_SP_0.png",
        "findings_md": plots.parent / "analysis_findings.md",
        "tune_script": TUNE_DIR / "TUNE_Basics_Guide_R14.py",
    }

    missing = [f"{k}: {v}" for k, v in assets.items() if not v.exists()]
    if missing:
        raise FileNotFoundError(
            "Promo source assets missing:\n  " + "\n  ".join(missing)
        )
    return assets


# Names of the prepared stills the capture step writes into `assets/`.
PREPARED = {
    "report": ASSET_DIR / "report.png",
    "surface_hero": ASSET_DIR / "surface_hero.png",
    "heatmap_hero": ASSET_DIR / "heatmap_hero.png",
    "surface_ignition": ASSET_DIR / "surface_ignition.png",
    "log_knock": ASSET_DIR / "log_knock.png",
    "log_lambda": ASSET_DIR / "log_lambda.png",
    "log_rail": ASSET_DIR / "log_rail.png",
    "log_boost": ASSET_DIR / "log_boost.png",
    "log_coverage": ASSET_DIR / "log_coverage.png",
    "code_snippet": ASSET_DIR / "code_snippet.png",
}

CHROME = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def _describe() -> str:
    lines = [
        f"canvas      : {WIDTH}x{HEIGHT} @ {FPS} fps",
        f"duration    : {total_duration_s():.1f} s / {total_frames()} frames",
        "timeline    :",
    ]
    for b in TIMELINE:
        lines.append(
            f"  {b.id:<8} {b.start_s:5.1f}-{b.end_s:5.1f}s  "
            f"{b.n_frames:5d} frames  frames[{b.start_frame}:{b.end_frame})  {b.title}"
        )
    lines.append("assets      :")
    for k, v in resolve_assets().items():
        lines.append(f"  {k:<17} {v.relative_to(REPO_ROOT)}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_describe())
