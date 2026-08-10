# simoscal promo video

A ~90 s, 1920×1080 H.264 promo for the `simoscal` library, built from the
library's **real** outputs — the tune report, the before/after compare surfaces,
and the log-analysis plots. On-screen text only; no voiceover, no baked audio
(so a music bed can be dropped on later).

Plan: `Docs/plans/2026-07-25-001-feat-simoscal-promo-video-plan.md`.
Origin: `Docs/brainstorms/2026-07-25-simoscal-promo-video-requirements.md`.

## Build

```bash
python3 Docs/promo/capture_assets.py    # 1. gather + prepare real stills
python3 Docs/promo/build_promo.py       # 2. render frames, encode, QA
```

Output: `Docs/promo/simoscal_promo.mp4`. Intermediates (`frames/`, `assets/`,
the `.mp4`) are gitignored — the scripts plus the real output folders are the
record.

Useful while iterating:

```bash
python3 Docs/promo/build_promo.py --only logs   # one beat -> preview_logs.mp4
python3 Docs/promo/build_promo.py --frames      # keep numbered PNGs in frames/
python3 Docs/promo/scenes.py out/               # still frames of every beat
python3 Docs/promo/scene_surface.py out/        # stills of the hero beat
python3 -m pytest Docs/promo/tests -q           # ~90 s
```

Frames are piped to ffmpeg as raw RGB by default; `--frames` writes numbered
PNGs instead (inspectable, but far slower). A full build took ~40 min on a
heavily loaded machine (~2400 s of render for 2700 frames); the hero surface
beat is the most expensive at ~1.6 s a frame.

## What the build proves

`build_promo.py` will not produce a file it cannot vouch for:

- every prepared asset must exist before rendering starts;
- `FrameWriter` fails if a beat renders the wrong number of frames or writes
  outside its window, so a gap or overlap stops the build before the encode;
- the encoded file is probed with `ffprobe` and checked for 1920×1080, H.264 /
  `yuv420p`, the exact expected frame count, a duration inside 85–95 s, and a
  **single stream** — no audio is ever encoded (`-an`);
- the hero beat prints which path it took (`rotation` = the real table
  re-plotted from the bins, `parallax` = fallback on the compare PNG).

Copy on screen is held to the same standard: the verification numbers and the
edit-journal tally are parsed out of the real `report.md`, the code card is
lifted verbatim from `TUNE_Basics_Guide_R14.py`, and a test asserts every figure
quoted in a log caption appears in `analysis_findings.md`.

## Files

| File                | Role                                                            |
|---------------------|-----------------------------------------------------------------|
| `config.py`         | Canvas, palette, fonts, 8-beat timeline, real-asset manifest    |
| `capture_assets.py` | Headless-Chrome report shot, plot prep, code-snippet render     |
| `compositor.py`     | PIL frame engine: paste, text, Ken Burns, easings, transitions  |
| `scenes.py`         | Beats 1–4 and 6–8                                               |
| `scene_surface.py`  | Beat 5 — the hero 3D surface                                    |
| `build_promo.py`    | Renders all beats → frames → ffmpeg → mp4, then self-checks     |
| `tests/`            | `python3 -m pytest Docs/promo/tests -q`                         |

## Timeline

```
1 title    0–6s    2 code    6–18s   3 verify  18–30s   4 report 30–42s
5 surface  42–56s  6 flash  56–62s   7 logs    62–80s   8 outro  80–90s
```

## Requirements

- macOS with `/Applications/Google Chrome.app` (headless report screenshot).
- `ffmpeg` + `ffprobe` on `PATH` (Homebrew).
- Python: Pillow, matplotlib, numpy (already used by `simoscal`).
- Fonts: `/System/Library/Fonts/SFNS.ttf` and `Menlo.ttc`. On a non-macOS
  machine, repoint `FONT_DISPLAY` / `FONT_MONO` in `config.py`.

Assets resolve automatically to the **newest** tune-run out dir under
`Tunes/TuningBasicsGuide/TUNE_Basics_Guide_out/` (excluding `Test/`) and the
newest `Logs/BasicsGuide_R*/plots/`. Nothing is faked: if a source asset is
missing the build fails loud rather than substituting placeholder art.
