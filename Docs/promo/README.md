# simoscal promo videos

Two 1920×1080 H.264 cuts of the same story, sharing one engine. Both are built
from the library's **real** outputs: the deep dive from the tune report and the
before/after compare surfaces, the hook from the tune bins and the datalogs
themselves. On-screen text only; no voiceover, no baked audio (so a music bed can
be dropped on later).

| Cut           | File                   | Length | What it does                                              |
|---------------|------------------------|--------|-----------------------------------------------------------|
| **Hook**      | `simoscal_hook.mp4`    | 31 s   | Result first. Six revisions of logged boost, dyno, the live table walk, the climb, the five slots — opening and closing on the wordmark. |
| **Deep dive** | `simoscal_promo.mp4`   | 90 s   | The whole loop: write → verify → report → flash → log.    |

The hook is the one to lead with; the deep dive is where someone goes next.

Plan: `Docs/plans/2026-07-25-001-feat-simoscal-promo-video-plan.md`.
Origin: `Docs/brainstorms/2026-07-25-simoscal-promo-video-requirements.md`.

## Build

```bash
python3 Docs/promo/capture_assets.py    # 1. gather + prepare real stills
python3 Docs/promo/build_hook.py        # 2a. the 31 s hook   (~10 s)
python3 Docs/promo/build_promo.py       # 2b. the 90 s cut    (~40 min)
```

`capture_assets.py` is only needed for the deep dive — the hook draws every beat
itself, out of the logs and the tune bin. Intermediates (`frames/`,
`frames_hook/`, `assets/`, the `.mp4`s) are gitignored — the scripts plus the
real output folders are the record.

Useful while iterating:

```bash
python3 Docs/promo/hook_data.py                 # print the hook's real figures
python3 Docs/promo/hook_scenes.py out/          # stills of every hook beat
python3 Docs/promo/scene_trace.py out/          # stills of the table-walk beat
python3 Docs/promo/scene_boost.py out/          # stills of the boost beat, + its window
python3 Docs/promo/build_hook.py --only dyno    # one beat -> preview_hook_dyno.mp4
python3 Docs/promo/build_promo.py --only logs   # one beat -> preview_logs.mp4
python3 Docs/promo/build_promo.py --frames      # keep numbered PNGs in frames/
python3 Docs/promo/scenes.py out/               # still frames of every beat
python3 Docs/promo/scene_surface.py out/        # stills of the hero beat
python3 -m pytest Docs/promo/tests -q           # ~3 s, 96 tests
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

`build_hook.py` runs the same encode, probe, and frame-count gates against its
own duration window (derived from `HOOK_TIMELINE`, so a re-cut moves the gate
with it), and prints which revisions were excluded from the chart.

## Where the hook's numbers come from

The hook puts big figures on screen, so `hook_data.py` derives them under rules
worth stating (it prints all of this when run directly):

- **Detected WOT pulls only** — pull windows come from `simoscal.analysis`, the
  same detector the log reviews use, not a max over the whole file.
- **In-gear samples only.** `Calc HP (hp)` is acceleration-derived *and*
  gear-ratio-weighted, and the DSG's gear channel flips to the next ratio a few
  samples before the shift actually pulls the engine down. Those samples read
  ~50 hp high: in R14's best pull `Calc HP` jumps 292 → 348 while longitudinal
  acceleration is *falling*. Every pull is trimmed to the samples still in its
  attributed gear, which is what removed the spike at the top of the dyno curve.
  Raw, that pull peaked at 347 hp; trimmed, **298 hp** — and the whole series
  moves with it (see below).
- **3rd gear or higher.** Third is the gear the comparable pulls are logged in
  and the only one with full-range coverage. Trimmed, 2nd and 3rd agree to ~4 hp
  (294 vs 298); the old "372 in 2nd vs 347 in 3rd" gap was the artifact above,
  not the gearing.
- **Smoothed.** A ~0.2 s moving average over the pull; the peak of the smoothed
  trace is the number, not the peak sample.
- **Comparable pulls only** in the revision chart: a revision is charted only if
  it has a 3rd-gear-or-higher pull that ran past 6000 rpm *before its upshift*.
  R11 is excluded on that rule — its only pulls are 4th gear and stop at
  ~5300 rpm, so its peak is not a peak. The build prints the exclusion and its
  reason every time.
- **Bars run from zero.** No truncated axis; the gain over the first revision is
  picked out in accent instead.
- **No counting numbers that aren't anchored.** Values fade in at their real
  figure. The one number that climbs is the hp counter on the dyno beat, which
  tracks the tip of the curve being drawn.

As charted, the series is R01 275 → R04 295 → R07 297 → R08 299 → R09 308 →
R14 298 hp — a climb overall, but **not monotonic**: R09 is the highest logged
figure, and R14 sits 10 hp under it. The beat is framed as "+23 hp, R01 → R14"
rather than "faster every revision", because the latter is not true.

Those figures are all lower than the ones this cut originally shipped with
(R01 275 → R14 347, "+72 hp"). The difference is the in-gear trim: R01's best
pull happened not to contain a gear flip while every later revision's did, so the
old series was comparing a clean number against contaminated ones and most of the
"gain" was the artifact. +23 hp over six revisions on 92 octane at altitude is
the honest figure.

## Files

| File                | Role                                                            |
|---------------------|-----------------------------------------------------------------|
| `config.py`         | Canvas, palette, fonts, **both** timelines, real-asset manifest |
| `compositor.py`     | PIL frame engine: paste, text, Ken Burns, easings, transitions  |
| `capture_assets.py` | Headless-Chrome report shot, plot prep, code-snippet render     |
| `scenes.py`         | Deep dive, beats 1–4 and 6–8                                    |
| `scene_surface.py`  | The hero 3D surface — the deep dive's beat 5                    |
| `build_promo.py`    | Deep dive: all beats → frames → ffmpeg → mp4, then self-checks  |
| `hook_data.py`      | The hook's figures + pull trace, derived from the real logs     |
| `hook_scenes.py`    | The hook's dyno/climb/logo beats, and the dispatch for all seven |
| `scene_trace.py`    | The tach + live table-walk beat                                 |
| `scene_boost.py`    | Six revisions of logged boost vs rpm, swept                     |
| `scene_slots.py`    | The five map-switch slot boost curves, read out of the tune bin |
| `build_hook.py`     | Hook: render → ffmpeg → mp4, sharing the deep dive's QA gates   |
| `tests/`            | `python3 -m pytest Docs/promo/tests -q`                         |

## Timelines

Deep dive — 90 s:

```
1 title    0–6s    2 code    6–18s   3 verify  18–30s   4 report 30–42s
5 surface  42–56s  6 flash  56–62s   7 logs    62–80s   8 outro  80–90s
```

Hook — 31 s, hard cuts, no crossfades:

```
1 logo_open  0–3s    2 boost  3–8s    3 dyno   8–13s   4 trace  13–18s
5 climb     18–23s   6 slots 23–28s   7 logo  28–31s
```

Beats 1 and 7 are the **same clip**: same length, same frame function
(`hook_scenes.logo_frame`), so the cut opens on the wordmark it closes on and
loops seamlessly. `config.HOOK_BOOKENDS` names the pair.

Beat 2 (`scene_boost.py`) puts all six revisions' **logged** boost on one graph —
the `Boost (psi)` channel of the same pull each revision's hp figure comes from,
so this beat and beat 5 can never be describing different runs. It is the
measured counterpart to beat 6: outcome here, target there.

The comparison only holds inside a window, and finding it is most of the beat.
Pulls start and end wherever the driver floored it and shifted (2654–3246 rpm at
the bottom, 6194–6765 at the top), so drawn over their own ranges the steep left
edge of each curve is just *where that pull started* — and R14, floored 560 rpm
later than R01, draws a spool ramp against five flat-topped curves and reads as
the worst of the six when it is the best. So `curves()` clips twice: to the range
they all cover, then forward again to where the last pull to come on boost got
there (`ON_BOOST_PSI`). What survives is 3527–6194 rpm, where all six are doing
the same thing — holding a target at wide-open throttle — and the beat prints
that window on screen. Every figure in the left column is computed from the
clipped curves, so the headline psi and the `+psi` spread always agree with the
lines beside them; `MIN_SHARED_SPAN_RPM` fails the build rather than drawing a
window too narrow to mean anything. The y-axis runs from zero: these curves sit
within ~3 psi of each other and a cropped axis would turn that into a chasm.

Beat 6 (`scene_slots.py`) draws all five map-switch slots — the per-slot
`PUT setpoint` boost-target grids read by uniqueid out of the newest tune-run
`.bin`, not retyped from the revision script. The rpm cursor sweeps the shared
slot axis and each curve is revealed up to it, carrying its live value. The ECU
stores absolute hPa, so every value is converted to psi *gauge* at standard
sea-level ambient (1013.25 hPa) and the beat says so on screen — the same target
is more gauge boost at altitude, so the reference has to be stated.

Beat 4 (`scene_trace.py`) is the live one: a MK7-style rev counter on the right
sweeping the real engine speed of the same 3rd-gear pull the dyno beat plots,
and `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]` — Basic ignition angle, low port
flap, standard on the left, with the cell the ECU was reading lit up as the
needle climbs. Both halves run off one time index so they cannot drift apart,
and cell attribution uses the nearest-breakpoint rule from
`simoscal.analysis.coverage` against breakpoints read out of the flashed R14
bin. Orange in that table means "the log hit this cell" — the table's own
shading is deliberately a cool ramp so the two never get confused.

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
