# simoscal promo video — implementation plan

**Date:** 2026-07-25
**Type:** feat (media deliverable)
**Origin:** `Docs/brainstorms/2026-07-25-simoscal-promo-video-requirements.md`
**Status:** completed 2026-08-10 — built at `Docs/promo/`, output
`Docs/promo/simoscal_promo.mp4` (1920×1080, 90.0 s, H.264/yuv420p, no audio)
**Depth:** Standard (6 units)

## Outcome (2026-08-10)

All six units shipped; 96 tests green (`python3 -m pytest Docs/promo/tests -q`).
Decisions taken during implementation:

- **U1** — log plots resolve to the newest `Logs/BasicsGuide_R*/plots`
  (`R14`), not the plan's hard-coded `R09`; R14 logs landed after the plan was
  written and match the R14 report the promo shows.
- **U5 open question resolved: the real-rotation path.** `simoscal` reads
  `IP_FAC_BPA_SP[0]` — Map for boost pressure actuator setpoint out of the stock
  bin and the R14 tuned bin, and the beat re-plots it sweeping −168° → −118°
  azimuth while the mesh morphs stock → tuned (18 of 160 cells move, biggest
  step +0.15). The parallax fallback is implemented and tested but unused here.
  The R14 `compare/` surface for this table was *not* usable as the hero — R14
  changed only the per-slot PUT grids, so its before/after Δ is flat.
- **U6 deviation: frames are piped to ffmpeg as raw RGB** rather than written as
  numbered PNGs. PNG encoding cost ~0.5 s a frame (≈25 min of pure I/O over
  2700 frames); `--frames` still writes the numbered PNGs when they are wanted.
  All frame accounting (gap/overlap detection) is unchanged.
- Engine caching (text rasterisation, shadow/vignette masks, pre-scaled report,
  one reused matplotlib figure) took the render from ~26 min to ~2400 s wall on
  a machine under load average 15.

## Summary

Build a ~90s, 1920×1080 `.mp4` promo for `simoscal` that tells the tuning-loop
story and showcases the tool's real visual outputs (hero: 3D surface compare,
the HTML report, log-analysis plots). Frames are composited in Python with
Pillow (mixed media + kinetic text + transitions), the report is captured with
headless Google Chrome, and the frame sequence is encoded to H.264 with ffmpeg.
No new dependencies — everything used is already installed.

## Problem Frame

simoscal's outputs are striking but live only in output folders. We want a
single shareable video that makes the workflow and those visuals legible to a
tuning-enthusiast audience. Deliverable is a true video file, not an interactive
page (decided in brainstorm). On-screen text only, no voiceover, no baked audio.

## Requirements (from origin doc)

- Real `.mp4`, 1920×1080 (16:9), ~85–95s, ~30fps, H.264, **no baked audio**.
- Uses **real** outputs: ≥1 real 3D surface compare, the real `report.html`
  content, ≥3 real log-analysis plots (knock, lambda, + boost/rail). (AE1, AE2)
- **On-screen text only**; enthusiast-flex tone; correct ECU parameter naming
  (ID + plain-English where a label is shown). (AE3, AE5)
- **Tuning-loop narrative**, 8 beats in order, loop visibly closes. (AE4)
- Nothing misrepresents the tool; the library never flashes — beat 6 makes the
  human-flash boundary explicit. (AE6)

## Key Technical Decisions

1. **Pillow frame-compositor + ffmpeg stitch**, not matplotlib
   `FuncAnimation`-to-mp4. A promo needs mixed media (PNGs + text + transitions +
   pan/zoom) composited per frame; PIL canvases → numbered PNGs → `ffmpeg
   -framerate 30` is the flexible, debuggable path. Verified stack: Pillow
   12.3.0, ffmpeg 8.0.1.
2. **Report captured via headless Google Chrome** `--headless --disable-gpu
   --screenshot` against `file://…/report.html` at a tall window size. Verified
   working this session (350 KB PNG, relative `compare/` PNGs resolve). No
   playwright/wkhtmltoimage needed. Then animate with a vertical Ken Burns pan.
3. **Hero 3D surface = real azimuth rotation if reachable, else parallax
   fallback.** Preferred: re-render the actual table's surface from data via
   matplotlib 3D sweeping azimuth (true rotation = the "wow" shot). Fallback if
   re-plotting from data isn't cheaply reachable: slow parallax zoom/tilt on the
   existing static `IP_FAC_BPA_SP[0]__compare_surface.png`. Either way the asset
   is real. (Decide in U5 after checking simoscal's surface-plot reachability.)
4. **Real assets resolved via a manifest + copied into `assets/`.** A config
   resolves "newest R14 out dir" and the `Logs/BasicsGuide_R09/plots` set once,
   copies chosen stills into `Docs/promo/assets/` so the build is reproducible
   and decoupled from later folder churn.
5. **Output & project home:** `Docs/promo/` (matches repo's Docs-owned Claude
   artifacts). Final at `Docs/promo/simoscal_promo.mp4`, H.264 `yuv420p`, no
   audio stream. `frames/` gitignored.
6. **Fonts:** SF (`/System/Library/Fonts/SFNS.ttf`) for display text, Menlo
   (`/System/Library/Fonts/Menlo.ttc`) for the code scene — both confirmed
   present. Font paths live in config so they're swappable.

## High-Level Technical Design

```
config (canvas, fps, palette, fonts, timeline, asset manifest)
        │
        ▼
assets/  ── report.png (headless Chrome)  ── hero surface PNG(s)
        ── log-analysis PNGs             ── code-snippet PNG (rendered)
        │
        ▼
compositor  (PIL canvas; text, image paste w/ alpha+scale, easing,
             transitions: fade/wipe/slide, Ken Burns pan/zoom)
        │
        ▼
scenes[8]  (each: build_frames(t0..t1) -> writes frame_#####.png)
        │
        ▼
build_promo.py  ── renders all frames ── ffmpeg encode ── simoscal_promo.mp4
```

Timeline (targets, tunable): 1 title 0–6s · 2 code edit 6–18 · 3 verify 18–30 ·
4 report scroll 30–42 · 5 hero surface 42–56 · 6 flash handoff 56–62 ·
7 log review 62–80 · 8 loop-closes outro 80–90.

## Implementation Units

### U1. Project scaffold + config + asset manifest

**Goal:** Stand up `Docs/promo/` with a single config module holding canvas
constants, palette, font paths, the beat timeline, and a manifest that resolves
real source assets.
**Requirements:** AE1, AE2 (foundation).
**Dependencies:** none.
**Files:** `Docs/promo/config.py` (create), `Docs/promo/__init__.py` (create),
`Docs/promo/.gitignore` (create — ignore `frames/`, `assets/`, `*.mp4`),
`Docs/promo/README.md` (create — how to build).
**Approach:** Constants: `WIDTH=1920, HEIGHT=1080, FPS=30`. Palette dict
(dark bg, accent, text tiers) + font path constants. `TIMELINE` = ordered list
of `(scene_id, start_s, end_s)`. `resolve_assets()` returns absolute source
paths: newest `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_out/R*/report.html`,
its `compare/IP_FAC_BPA_SP[0]__compare_surface.png` +
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]__compare_surface.png`, and the
`Logs/BasicsGuide_R09/plots/analysis_{knock,lambda,rail_pressure,overview_*}.png`
set. `frame_index(t)` and `frames_for(scene)` helpers.
**Test scenarios:**
- Happy: `resolve_assets()` returns paths that all exist (assert `os.path.exists`
  on each) → passes against current repo state.
- Edge: newest-dir resolver picks the lexicographically/mtime-latest `R*` dir,
  not `Test/` subdirs → excludes `.../Test/**`.
- Config: `frames_for` over the full timeline sums to ~2550–2850 frames
  (85–95s × 30fps).
**Verification:** Importing `config` prints resolved asset paths, all existing;
frame math matches the ~90s target.

### U2. Asset capture & preparation

**Goal:** Produce normalized source stills in `Docs/promo/assets/`: the report
screenshot, curated hero surface(s), log plots, and a rendered code-snippet
image.
**Requirements:** AE2, AE3.
**Dependencies:** U1.
**Files:** `Docs/promo/capture_assets.py` (create),
`Docs/promo/assets/` (generated output dir).
**Approach:** (a) **Report:** subprocess to
`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --headless
--disable-gpu --hide-scrollbars --window-size=1400,<tall> --screenshot=assets/report.png
file://<report.html>` (pattern proven this session). (b) **Surfaces / log
plots:** copy the manifest PNGs into `assets/`, optionally trim whitespace via
PIL. (c) **Code snippet:** render a real `simoscal.tune` snippet (physical-units
call with `intent=`) to `assets/code_snippet.png` using PIL + Menlo with simple
token coloring — content sourced from
`Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R14.py` so it's real. Every ECU label
drawn keeps ID + plain-English (AE3).
**Test scenarios:**
- Happy: after run, `assets/report.png`, `assets/surface_bpa.png`,
  `assets/log_knock.png`, `assets/log_lambda.png`, `assets/code_snippet.png`
  all exist and are non-trivial size (>10 KB).
- Edge: report capture height large enough that the "Changed this flash" section
  is present (assert PNG height > 2500 px).
- Error: if Chrome binary path missing, fail loud with a clear message (no silent
  fallback to a blank frame).
**Verification:** Open `assets/` — the report screenshot shows the flash-gate
banner + verification cards; code snippet is legible and real.

### U3. Frame compositor core

**Goal:** A reusable, tested compositing engine the scenes call.
**Requirements:** underpins AE4, AE5 (legibility).
**Dependencies:** U1.
**Files:** `Docs/promo/compositor.py` (create),
`Docs/promo/tests/test_compositor.py` (create).
**Approach:** `Frame` wraps a PIL `Image` (RGB, canvas size, bg from palette).
Primitives: `paste(img, xy, scale, alpha)`; `text(s, xy, font, size, color,
align, max_width)` with wrap/fit; `ken_burns(img, t01, start_rect, end_rect)`
returning a cropped/scaled view for a vertical/zoom pan; easing (`ease_in_out`,
`linear`, `ease_out`); transitions `fade(a,b,t01)`, `wipe(a,b,t01,dir)`,
`slide_in(img,t01,dir)`. Deterministic given `(scene, frame_i)`.
**Test scenarios:**
- Happy: `ease_in_out(0)=0`, `(1)=1`, monotonic on a 0..1 sweep.
- Happy: a `Frame` rendered with one `paste` + one `text` is the configured size,
  mode RGB.
- Edge: `text` with `max_width` wraps rather than overflowing the canvas
  (rendered text bbox width ≤ max_width).
- Edge: `ken_burns(t=0)` returns `start_rect` crop, `t=1` returns `end_rect`
  crop, both resized to canvas.
**Verification:** `pytest Docs/promo/tests/` green; a scratch call writes one
sample composited PNG that looks correct.

### U4. Scene builders — 7 of the 8 beats

**Goal:** Implement beats 1–4 and 6–8 (all but the hero surface) as functions
that emit numbered frames over their time windows.
**Requirements:** AE3, AE4, AE5, AE6.
**Dependencies:** U2, U3.
**Files:** `Docs/promo/scenes.py` (create).
**Approach:** One function per beat, each `render(writer, t0, t1)` using the
compositor: **1 title** (wordmark + "Tune a Simos18 ECU. In code."); **2 code
edit** (`code_snippet.png` typing/reveal + highlight a physical-units call);
**3 verify** (checksum/audit lines resolve to ✓, caption "Checksum-verified.
Every byte traceable."); **4 report scroll** (`report.png` vertical Ken Burns,
pausing on the verification cards); **6 flash handoff** (stylized phone/app
motif, caption "You flash it. The library never does." — satisfies AE6, no real
recording); **7 log review** (montage: `log_knock` → `log_lambda` →
`rail_pressure` slide/fade in, caption "Then the logs prove it out."); **8 outro**
(beats compress into a ring that closes; wordmark; "Revise. Verify. Log.
Repeat."). All on-screen ECU labels use ID + plain-English.
**Test scenarios:**
- Happy: each scene writes exactly `frames_for(scene)` PNGs at canvas size into a
  temp dir.
- Edge: report-scroll first frame shows the banner region, last frame shows the
  "Changed this flash" region (pan actually traverses).
- Integration: beat 6 frame text contains the human-flash line (AE6) — assert the
  caption string is drawn.
- Edge: no scene writes outside its `[t0,t1)` frame index range (no overwrite of
  a neighbor's frames).
**Verification:** Rendering these 7 scenes fills their frame ranges; spot-checked
PNGs match the beat intent.

### U5. Hero 3D surface scene (beat 5)

**Goal:** The showcase beat — a real 3D surface that moves.
**Requirements:** AE2 (real surface), AE4.
**Dependencies:** U2, U3.
**Files:** `Docs/promo/scene_surface.py` (create).
**Approach:** First attempt **real rotation**: locate simoscal's surface-plot
routine (in the xdf-visualization module used to make `*_compare_surface.png`);
if a table's grid data is cheaply reachable, render `IP_FAC_BPA_SP[0]` — Map for
boost pressure actuator setpoint as a matplotlib 3D surface across a ~30°
azimuth sweep (~360 frames for ~12s), before→after morph optional, exported as
frames. **Fallback** (decision recorded if re-plot isn't cheap): parallax
zoom/tilt Ken Burns on the static `surface_bpa.png`. Label kept as full ID +
description.
**Test scenarios:**
- Happy (real path): sweep renders N frames at canvas size, azimuth strictly
  increasing across the sweep.
- Happy (fallback): parallax path renders N frames, crop rect changes each frame.
- Edge: exactly one path executes; a module-level flag records which, logged at
  build time so the QA step knows what shipped.
- Correctness: on-frame label reads `IP_FAC_BPA_SP[0]` — Map for boost pressure
  actuator setpoint (AE2/AE3).
**Verification:** The surface beat visibly moves and is recognizably the real
wastegate boost-actuator map.

### U6. Render orchestration + ffmpeg encode + QA

**Goal:** One entry point renders all scenes → frames → mp4, then self-checks.
**Requirements:** AE1, AE4, AE5, AE6.
**Dependencies:** U4, U5.
**Files:** `Docs/promo/build_promo.py` (create),
`Docs/promo/README.md` (update — run + QA steps).
**Approach:** Clear/create `frames/`; iterate `TIMELINE` dispatching to scene
builders with a shared frame writer (global monotonic index); assert total frame
count == expected; call `ffmpeg -y -framerate 30 -i frames/frame_%05d.png
-c:v libx264 -pix_fmt yuv420p -movflags +faststart Docs/promo/simoscal_promo.mp4`
(no `-i` audio, so no audio stream). Then QA via `ffprobe`: duration in 85–95s,
1920×1080, has video / no audio stream.
**Test scenarios:**
- Happy: full build produces `simoscal_promo.mp4`; `ffprobe` reports
  1920×1080, ~85–95s, `nb_streams=1` (video only). (AE1, AE5)
- Integration: frame count written == sum of `frames_for` over all 8 beats; a
  gap/overlap in indices fails loud before encode. (AE4)
- Edge: re-running the build overwrites cleanly (no stale frames leak into the
  encode).
- Manual: plays in QuickTime and a browser; text legible at 1080p and at 720p
  downscale. (AE5)
**Verification:** `Docs/promo/simoscal_promo.mp4` exists, probes to spec, plays,
and walks the 8 beats in order with the loop closing — ready for Sam to add music.

## Scope Boundaries

**In:** the 6 units above → one landscape mp4 from real assets, on-screen text
only, no audio.
**Out:** vertical/square re-cuts, voiceover/TTS, baked music, interactive HTML
version, real screen-recording. (All deferred per origin doc.)

### Deferred to Follow-Up Work
- A `--vertical` render mode reusing the compositor for a 9:16 social cut.
- A music bed + beat-synced cuts (needs an audio asset from Sam).

## Open Questions (non-blocking)

- **U5 real-rotation reachability** — resolved during U5: is simoscal's surface
  plot callable on raw table data cheaply, or do we take the parallax fallback?
  Either satisfies AE2.
- **Report source revision** — default to newest R14 out dir (today's
  `R14_20260810-111002`); revisit only if a cleaner report lands first.

## Risks & Dependencies

- **Render time:** ~2700 frames of PIL compositing + a matplotlib 3D sweep —
  minutes, not seconds. Acceptable for a one-off; keep scenes independently
  re-renderable to avoid full rebuilds while iterating.
- **Font rendering:** PIL needs explicit TTF paths; SFNS/Menlo confirmed present
  and pinned in config (Risk if run on another machine — documented in README).
- **Chrome headless flakiness:** benign macOS `task_policy` stderr noise is not a
  failure; U2 keys success off the output PNG existing + size, not exit chatter.
- **Report screenshot legibility when panned:** mitigated by capturing at high
  width (1400px) and pausing the pan on dense regions.

## Sources & Research (this session)

- Verified installed: ffmpeg 8.0.1, Pillow 12.3.0, matplotlib 3.11.1, Google
  Chrome.app; fonts SFNS.ttf, Menlo.ttc, Arial.ttf.
- Proven: headless Chrome screenshot of `report.html` (relative `compare/` PNGs
  resolve; report shows flash-gate banner, verification cards, per-slot boost
  curves + surfaces — a strong hero asset by itself).
- Real assets located: newest report at
  `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_out/R14_20260810-111002/`;
  hero surfaces in its `compare/`; log plots in `Logs/BasicsGuide_R09/plots/`.
- No new deps required (no playwright/imageio/moviepy).
