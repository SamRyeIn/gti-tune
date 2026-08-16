# simoscal promo video — requirements

**Date:** 2026-07-25
**Status:** requirements complete → ready for `/ce-plan`
**Type:** creative / media deliverable (not a code feature)

## Problem

`simoscal` produces genuinely striking visual outputs — 3D surface compares, a
polished HTML per-revision report, and a whole battery of log-analysis plots —
but they only ever live in output folders on disk. There's no single artifact
that shows off what the library does and how good the outputs look. We want a
fun, sharable promo video that puts those visuals front and center.

## Goals & Success Criteria

- A **real `.mp4` file**, ~90 seconds, 1920×1080 (16:9), that plays anywhere.
- Showcases simoscal's workflow and — above all — its **visual outputs**.
- Uses the project's **real, actual outputs** (real plots, real report), not
  mocked-up fakes. It should be honest about what the tool produces.
- Reads as an **enthusiast flex**: credible to someone who tunes Simos ECUs,
  real terminology on screen, a little swagger.
- Success = Sam watches it and it looks cool and accurately represents the tool;
  it's shareable to the tuning community as-is (music optional, added later).

## Scope

**In:**
- Rendered `.mp4`, 1920×1080, ~90s, ~30fps, H.264, no audio track baked in
  (leave room for Sam to add music).
- **On-screen text only** — kinetic captions / overlays carry the message. No
  voiceover (no natural VO track available).
- Narrative = **the tuning loop**: revise → verify → report → diff → flash →
  log → review → iterate, with the loop visibly closing at the end.
- Frames generated with the **existing Python stack** (matplotlib / PIL in
  `Code/.venv313`), stitched with **ffmpeg 8.0.1** (confirmed installed).

**Out (explicitly):**
- No interactive / HTML deliverable (that path was considered and rejected in
  favor of a true video file).
- No voiceover / TTS narration.
- No baked-in music (Sam adds it post-hoc if desired).
- No live screen-recording of the terminal or the actual app — motion is
  designed/animated, not captured.
- Not a tutorial. It's a promo, not a how-to; correctness of on-screen code is
  "plausible and real-ish," not a runnable transcript.

## Hero visuals (ranked)

Priority order, from the brainstorm:

1. **3D surface compare plots** — the "wow" shot. Real examples exist, e.g.
   `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_out/R08_.../compare/IP_FAC_BPA_SP[0]__compare_surface.png`
   (`IP_FAC_BPA_SP[0]` — Map for boost pressure actuator setpoint / wastegate).
2. **The HTML report** — `report.html` (latest: `R14_20260720-222812/report.html`).
   Shows the polished, professional per-revision report.
3. **Log-analysis plots** — the analysis battery output in
   `Logs/BasicsGuide_R09/plots/`: `analysis_knock.png`, `analysis_lambda.png`,
   `analysis_rail_pressure.png`, `analysis_overview_*.png`,
   `analysis_coverage_*.png`, `analysis_tc_activity_*.png`. Proves the loop
   closes with real drive data.

**Supporting (use if they fit, not required):** before/after compare **heatmaps**
(`*__compare_heatmap.png`), the interactive **boost-curve** page
(`slot_boost_curves.html`), a **code snippet** of the `simoscal.tune` API.

## Key flow — scene arc (~90s)

Rough beat sheet; timings are targets, tunable in planning. Each beat is a "what
appears on screen," not a shot-implementation spec.

| #  | ~Time     | Beat                          | On-screen visual                                                                 | Caption idea                              |
|----|-----------|-------------------------------|----------------------------------------------------------------------------------|-------------------------------------------|
| 1  | 0:00–0:06 | Cold open / title             | simoscal wordmark + tagline on dark; subtle GTI / Simos motif                    | "Tune a Simos18 ECU. In code."            |
| 2  | 0:06–0:18 | Revise — edit tables in code  | `simoscal.tune` snippet types in; a physical-units call highlights               | "Edit tables in physical units."          |
| 3  | 0:18–0:30 | Verify — checksum + audit     | Verification lines resolve; ✓ checksums corrected + independently verified       | "Checksum-verified. Every byte traceable." |
| 4  | 0:30–0:42 | Report — the HTML report      | `report.html` scrolls / pans; tables + embedded plots glide by                   | "A full report, every revision."          |
| 5  | 0:42–0:56 | Diff — the 3D surface (HERO)  | before/after 3D surface tilts/rotates; delta reveals; heatmap wipe optional      | "See exactly what changed."               |
| 6  | 0:56–1:02 | Flash — handoff to the car    | brief stylized "flash to car" beat (app/phone motif); not a real recording       | "You flash it. The library never does."   |
| 7  | 1:02–1:20 | Review — log-analysis (HERO)  | knock / lambda / boost-tracking / rail-pressure plots slide in from real logs    | "Then the logs prove it out."             |
| 8  | 1:20–1:30 | Loop closes / outro           | beats compress into a ring that closes; wordmark returns                          | "Revise. Verify. Log. Repeat."            |

## Acceptance Examples

- **AE1** — Output is a single `.mp4`, 1920×1080, ~85–95s, that plays in QuickTime
  and a browser with no external assets.
- **AE2** — The video contains at least one **real** 3D surface compare, the
  **real** `report.html` content, and at least three **real** log-analysis plots
  (knock, lambda, and one of boost-tracking/rail-pressure), all sourced from
  actual output folders in the repo.
- **AE3** — Every on-screen ECU parameter is named correctly (ID + plain-English
  per project convention where a label is shown), e.g. `IP_FAC_BPA_SP[0]` — Map
  for boost pressure actuator setpoint.
- **AE4** — The 8 beats appear in tuning-loop order and the "loop closes"
  visually at the end.
- **AE5** — No audio track is baked in; the file is ready for Sam to drop music
  over. On-screen text is legible at 1080p (and still readable scaled to 720p).
- **AE6** — Nothing on screen misrepresents the tool: the library never flashes
  (beat 6 makes the human-flash boundary explicit), and shown outputs are the
  tool's real outputs.

## Key Decisions

- **Real .mp4 over HTML artifact** — Sam wants an actual shareable video file;
  ffmpeg + the existing matplotlib/PIL stack make it feasible without new deps.
- **Tuning-loop narrative** over feature montage — a coherent "this is how it
  works" story lands better with enthusiasts than a rule-of-cool reel.
- **On-screen text, no VO** — no natural voiceover available; captions carry it.
- **Real assets, not mockups** — authenticity is a stated goal; pull frames from
  actual `*_out/` and `Logs/` folders.
- **Enthusiast-flex tone**, 16:9 landscape (README/YouTube friendly), music
  deferred to Sam.

## Deferred / Out of Scope

- Vertical (9:16) or square cut for social feeds — could be a later re-render.
- Voiceover / TTS pass.
- An interactive HTML version alongside the video.
- Baked-in licensed music / sound design.

## Outstanding Questions (for planning, non-blocking)

- Which **specific** revision(s) to source the hero 3D surface and report from —
  R14 is latest; R08 has clean `IP_FAC_BPA_SP` surfaces. Pick during planning.
- Rendering approach for the report scroll (screenshot the HTML via headless
  browser vs. rebuild the panel in matplotlib) — an implementation choice for
  `/ce-plan`.
- Exact color/type treatment and any GTI/Simos visual motif — design detail.
