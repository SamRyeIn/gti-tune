# simoscal promo videos

Two 1920×1080 H.264 cuts of the same story, sharing one engine. Both are built
from the library's **real** outputs — the tune report, the before/after compare
surfaces, the log-analysis plots, and the datalogs themselves. On-screen text
only; no voiceover, no baked audio (so a music bed can be dropped on later).

| Cut           | File                   | Length | What it does                                              |
|---------------|------------------------|--------|-----------------------------------------------------------|
| **Hook**      | `simoscal_hook.mp4`    | 20 s   | Result first. Boost, dyno, the climb, the map, the name.  |
| **Deep dive** | `simoscal_promo.mp4`   | 90 s   | The whole loop: write → verify → report → flash → log.    |

The hook is the one to lead with; the deep dive is where someone goes next.

Plan: `Docs/plans/2026-07-25-001-feat-simoscal-promo-video-plan.md`.
Origin: `Docs/brainstorms/2026-07-25-simoscal-promo-video-requirements.md`.

## Build

```bash
python3 Docs/promo/capture_assets.py    # 1. gather + prepare real stills
python3 Docs/promo/build_hook.py        # 2a. the 20 s hook   (~15 s)
python3 Docs/promo/build_promo.py       # 2b. the 90 s cut    (~40 min)
```

`capture_assets.py` is only needed for the deep dive; the hook draws everything
itself apart from the 3D surface, which it shares. Intermediates (`frames/`,
`frames_hook/`, `assets/`, the `.mp4`s) are gitignored — the scripts plus the
real output folders are the record.

Useful while iterating:

```bash
python3 Docs/promo/hook_data.py                 # print the hook's real figures
python3 Docs/promo/hook_scenes.py out/          # stills of every hook beat
python3 Docs/promo/build_hook.py --only dyno    # one beat -> preview_hook_dyno.mp4
python3 Docs/promo/build_promo.py --only logs   # one beat -> preview_logs.mp4
python3 Docs/promo/build_promo.py --frames      # keep numbered PNGs in frames/
python3 Docs/promo/scenes.py out/               # still frames of every beat
python3 Docs/promo/scene_surface.py out/        # stills of the hero beat
python3 -m pytest Docs/promo/tests -q           # ~90 s (covers the 90 s cut)
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

`build_hook.py` runs the same encode, probe, and frame-count gates against a
18–22 s window, and prints which revisions were excluded from the chart.

## Where the hook's numbers come from

The hook puts big figures on screen, so `hook_data.py` derives them under rules
worth stating (it prints all of this when run directly):

- **Detected WOT pulls only** — pull windows come from `simoscal.analysis`, the
  same detector the log reviews use, not a max over the whole file.
- **3rd gear or higher.** SimosTools' `Calc HP (hp)` is acceleration-derived, so
  a lower gear reads high — the same R14 log shows **372 hp in 2nd and 347 hp in
  3rd**. Third is the comparable gear, so third is what gets quoted.
- **Smoothed.** A ~0.2 s moving average over the pull; the peak of the smoothed
  trace is the number, not the peak sample.
- **Comparable pulls only** in the revision chart: a revision is charted only if
  it has a 3rd-gear-or-higher pull that ran past 6000 rpm. R11 is excluded on
  that rule — its only pulls are 4th gear and stop at ~5300 rpm, so its peak is
  not a peak. The build prints the exclusion and its reason every time.
- **Bars run from zero.** No truncated axis; the gain over the first revision is
  picked out in accent instead.
- **No counting numbers that aren't anchored.** Values fade in at their real
  figure. The one number that climbs is the hp counter on the dyno beat, which
  tracks the tip of the curve being drawn.

As charted, the series is R01 275 → R04 338 → R07 342 → R08 345 → R09 358 →
R14 347 hp — a climb overall, but **not monotonic**: R09 is the highest logged
figure, and R14 sits 11 hp under it. The beat is framed as "+72 hp, R01 → R14"
rather than "faster every revision", because the latter is not true.

## Files

| File                | Role                                                            |
|---------------------|-----------------------------------------------------------------|
| `config.py`         | Canvas, palette, fonts, **both** timelines, real-asset manifest |
| `compositor.py`     | PIL frame engine: paste, text, Ken Burns, easings, transitions  |
| `capture_assets.py` | Headless-Chrome report shot, plot prep, code-snippet render     |
| `scenes.py`         | Deep dive, beats 1–4 and 6–8                                    |
| `scene_surface.py`  | The hero 3D surface — used by both cuts                         |
| `build_promo.py`    | Deep dive: all beats → frames → ffmpeg → mp4, then self-checks  |
| `hook_data.py`      | The hook's figures, derived from the real logs (see above)      |
| `hook_scenes.py`    | The hook's five beats                                           |
| `build_hook.py`     | Hook: render → ffmpeg → mp4, sharing the deep dive's QA gates   |
| `tests/`            | `python3 -m pytest Docs/promo/tests -q`                         |

## Timelines

Deep dive — 90 s:

```
1 title    0–6s    2 code    6–18s   3 verify  18–30s   4 report 30–42s
5 surface  42–56s  6 flash  56–62s   7 logs    62–80s   8 outro  80–90s
```

Hook — 20 s, hard cuts, no crossfades:

```
1 boost  0–3s   2 dyno  3–8s   3 climb  8–13s   4 map  13–17s   5 logo  17–20s
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
