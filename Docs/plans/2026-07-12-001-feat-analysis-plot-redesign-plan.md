# Plan: Analysis battery plot redesign

**Date:** 2026-07-12
**Type:** feat
**Requirements:** `Docs/brainstorms/2026-07-12-analysis-plot-redesign-requirements.md`
**Code repo:** all source changes land in the nested `simoscal` repo under `Code/`

## Summary

Redesign the evidence plots written by the log-analysis battery
(`Code/simoscal/analysis/evidence.py`) around one encoding rule — **quantity =
line style, pull = color** — and add three new plots: an ignition timing plot
vs RPM, a per-log overview plot vs time with detected WOT pull windows shaded,
and a switch-patch TC activity plot vs time that auto-skips until wheel-speed
channels appear in a log. Presentation-only: no check, threshold, or findings
content changes.

## Problem frame

The current plots color by pull and distinguish paired quantities (actual vs
setpoint, final vs base) only by marker size, making them near-unreadable
(see requirements doc §Problem). Scatter also hides the fact that a pull is a
monotonic RPM sweep. There is no whole-log view auditing pull detection, no
plot of the ignition timing the engine actually ran, and nothing to observe
the switch-patch slip-based TC once R07 is flashed.

## Requirements traced

From the requirements doc: decisions D1–D9 (encoding, legends, thresholds,
lambda emphasis, overview content, one-overview-per-CSV, graceful degradation,
TC plot content, additive-only) and acceptance examples AE1–AE6.

## Key technical decisions

1. **One shared line helper replaces `_scatter_pulls`.** All per-check plots
   funnel through `_scatter_pulls` today; replace it with a `_pull_lines`
   helper that, per pull, masks + sorts samples by RPM and draws a line.
   Primary quantity: solid, `_CYCLE` color per pull. Reference quantity
   (setpoint/base/table): dashed dark gray (`"0.35"`), one legend entry total
   (label deduplicated), drawn per pull so each sweep keeps its own curve.
   Secondary-actual quantities sharing a panel (HPFP vs LPFP): dash-dot gray.
   (D1, D2)
2. **Legend = quantities + pulls, never the cross-product** — e.g.
   `Final (Pull 1)`, `Final (Pull 2)`, `Base`. (D2)
3. **New plots are standalone plotters, not checks.** They join the existing
   plotter registry keyed `ignition`, `tc_activity`, and `overview:<log-stem>`
   (one per `LogFile`). `_attach_plot_refs` matches on check ids, so findings
   JSON/MD content is untouched automatically. (D9)
4. **Overview x-axis is the logged `time` channel**; pull windows shade all
   panels via the pull's `start_row`/`end_row` mapped through the file's time
   array, labeled `Pull <index>` (the pull's global 1-based index). Stacked
   shared-x panels: rpm + gear (gear as step on a twin y-axis), pedal,
   PUT + PUT SP, lambda + lambda SP, min knock retard (reusing the existing
   min-knock reduction), IAT. A panel with no data is omitted. (D5, D6, D7)
5. **TC activity plot** (x = time, per file, panels omitted when data absent;
   whole plot skipped when no wheel-speed channels — slip is the defining
   panel): wheel slip = mean(`wheel_fl`, `wheel_fr`) − mean(`wheel_rl`,
   `wheel_rr`); `ign_avg` vs `ign_table` with min knock overlaid; `wg_pos_final`
   vs `wg_pos_base`; `torque_req` vs `torque`. (D8)
6. **Slip-target reference line deferred.** Resolving `Slip target straight`
   needs a switch-patch XDF, which does not load under `simoscal` (per
   `Docs/plans/2026-07-11-001-feat-r07-patched-bin-switchpatch-tc-plan.md`).
   Recorded under Deferred, not silently dropped.
7. **Four new channel specs** in `CHANNEL_SPECS`: `wheel_fl`, `wheel_fr`,
   `wheel_rl`, `wheel_rr` — header names `Wheel Speed FL/FR/RL/RR`, canonical
   km/h, accepting `km/h` and `km/hr`, mirroring `vehicle_speed`.
8. **Style stays in-module:** headless `matplotlib.figure.Figure` object API
   only (no pyplot), existing `_style` (bold labels, major+minor grid),
   existing `_DPI`, threshold watch/high dashed lines unchanged. (D3)
9. **Lambda plot:** settled samples as solid lines; loaded-but-transient
   samples as a faint low-alpha scatter for context (transients are genuinely
   non-curve-like, so scatter is correct there). (D4)

## Implementation units

### U1. Wheel-speed channels and synthetic-log support

- **Goal:** the log loader recognizes the four wheel-speed columns; the test
  synthlog can emit them.
- **Requirements:** D8 (TC plot inputs), AE5.
- **Dependencies:** none.
- **Files:** `Code/simoscal/analysis/log.py`, `Code/tests/synthlog.py`,
  `Code/tests/test_analysis_log.py`.
- **Approach:** add the four `ChannelSpec` entries per decision 7. Extend
  `synthlog.clean_pull_columns` (or a wrapper) with an opt-in flag that adds
  wheel-speed columns modeling a mild front-slip event mid-pull, so the TC
  plot has something visible to draw in tests.
- **Test scenarios:**
  - Happy path: a CSV with `Wheel Speed FL (km/h)` etc. loads with all four
    canonical ids present and values unscaled.
  - Edge: `km/hr` unit spelling maps with factor 1.0.
  - Error path: an unrecognized wheel-speed unit lands in
    `unit_unrecognized`/unmapped, never guessed (existing policy).
- **Verification:** loader tests pass; a synthetic log with wheel speeds
  round-trips through `load_logset` with the new channels present.

### U2. Line-encoding restyle of the six per-check plots

- **Goal:** AE1/AE4 — paired quantities separable by style; sweeps read as
  curves.
- **Requirements:** D1–D4.
- **Dependencies:** none (parallel with U1).
- **Files:** `Code/simoscal/analysis/evidence.py`,
  `Code/tests/test_analysis_folder.py`.
- **Approach:** implement `_pull_lines` per decision 1; rewrite `_plot_boost`,
  `_plot_knock`, `_plot_lambda`, `_plot_rail`, `_plot_turbo`,
  `_plot_wastegate` on top of it. Lambda gains the faint transient scatter
  (decision 9). Error panels (PUT overshoot, DI error) become per-pull lines
  around the zero line. Legends per decision 2; threshold lines unchanged.
- **Test scenarios:**
  - Happy path: synthetic two-pull folder produces all six PNGs; each plotter
    returns True.
  - Edge: a pull whose reference channel is absent (no `wg_pos_base`) still
    draws the primary quantity alone.
  - Edge: single-sample masks (all-but-one sample masked out) do not crash a
    line draw.
  - Integration: fired findings still carry `plots/analysis_<check>.png`
    plot_refs (existing test keeps passing).
- **Verification:** regenerated `analysis_wastegate.png` on
  `Logs/BasicsGuide_R04` shows base vs final separable by style with a
  ≤ (pulls + 1)-entry legend (AE1, human-eyeball); test suite green.

### U3. Ignition timing plot

- **Goal:** AE6 — the timing the engine ran, vs RPM.
- **Requirements:** scope item 3.
- **Dependencies:** U2 (`_pull_lines`).
- **Files:** `Code/simoscal/analysis/evidence.py`,
  `Code/tests/test_analysis_folder.py`.
- **Approach:** new plotter keyed `ignition` → `analysis_ignition.png`:
  `ign_avg` solid per pull, `ign_table` dashed gray reference, loaded-WOT
  mask, vs RPM. Registered alongside the check plotters; not tied to a check,
  so no plot_refs.
- **Test scenarios:**
  - Happy path: synthetic log carrying `Ign Avg (°)`/`Ign Table (°)` produces
    the PNG.
  - Edge: log without ignition channels → plotter returns False, no file,
    no error.
- **Verification:** PNG regenerates on `Logs/BasicsGuide_R04` (its PID list
  logs both channels); findings JSON unchanged (AE3).

### U4. Log overview plot with pull windows

- **Goal:** AE2 — whole-log view auditing pull detection.
- **Requirements:** D5, D6, D7.
- **Dependencies:** U2 (style helpers only).
- **Files:** `Code/simoscal/analysis/evidence.py`,
  `Code/tests/test_analysis_folder.py`.
- **Approach:** per decision 4. One figure per `LogFile`, keyed
  `overview:<log-stem>` → `analysis_overview_<log-stem>.png` (stem passed
  through the existing `_sanitize`). Whole-log traces (not pull-masked);
  actual/setpoint pairs use the U2 encoding; pull spans shaded with a single
  low-alpha color and labeled once per pull on the top panel.
- **Test scenarios:**
  - Happy path: two-pull synthetic file → one overview PNG; shaded spans
    equal `detect_pulls` output (assert via the plotter's computed spans,
    e.g. factored span-computation helper).
  - Edge: file with no time channel → overview for that file skipped, others
    still drawn.
  - Edge: folder with two CSVs → two overview PNGs.
  - Edge: log with zero detected pulls still renders traces, just no shading.
- **Verification:** overview PNG for `Logs/BasicsGuide_R04` shows both pulls
  shaded exactly where the findings' pull table says they are (AE2).

### U5. TC activity plot

- **Goal:** AE5 — observe the switch-patch slip-based TC (and the absence of
  OEM TC intervention) once R07 logs exist.
- **Requirements:** D8.
- **Dependencies:** U1 (wheel-speed channels), U4 (time-axis/span helpers).
- **Files:** `Code/simoscal/analysis/evidence.py`,
  `Code/tests/test_analysis_folder.py`.
- **Approach:** per decision 5. Keyed `tc_activity:<log-stem>` (per file,
  like the overview) → `analysis_tc_activity_<log-stem>.png`; pull windows
  shaded for context. Skip the file entirely when no wheel-speed channel is
  present.
- **Test scenarios:**
  - Happy path: synthetic log with wheel speeds (U1 flag) → PNG with slip
    panel; slip computed as front-mean minus rear-mean.
  - Edge: R04-style log (no wheel speeds) → no file, no error (AE5).
  - Edge: wheel speeds present but `ign_table` absent → ignition panel
    omitted, plot still drawn.
- **Verification:** on the current R04 folder the plot is absent; on a
  synthetic wheel-speed log it renders; suite green.

### U6. Regenerate R04 artifacts and update docs

- **Goal:** ship the redesign against real data and keep docs truthful.
- **Requirements:** AE1–AE6, D9.
- **Dependencies:** U1–U5.
- **Files:** `Logs/BasicsGuide_R04/` (regenerated `analysis_findings.*`,
  `plots/*.png`), `Code/README.md` (analysis section: new plot list),
  `Code/simoscal/analysis/evidence.py` (module docstring plot inventory).
- **Approach:** rerun the battery on `Logs/BasicsGuide_R04`; confirm findings
  JSON is unchanged except plot references (AE3); visually review every
  regenerated PNG against the old set; stale old-name PNGs from the ChatGPT
  script are left alone (they are separate files, not battery outputs).
- **Test scenarios:** none — behavioral coverage lives in U1–U5; this unit is
  regeneration plus docs.
- **Verification:** full `Code/tests` suite green; AE1–AE4 confirmed by
  eyeball on the regenerated R04 plots; `analysis_findings.json` diff shows
  only plot-reference changes.

## Scope boundaries

Per the requirements doc: coverage heatmaps, check/threshold logic, pull
detection, `log_review.md` authorship, and `Tunes/` compare-PNG styling are
all untouched.

### Deferred to follow-up work

- Slip-target reference line on the TC plot (needs a `simoscal`-loadable
  switch-patch definition or a BinToolz-XDF bridge — see decision 6).
- Hunting for live TC RAM addresses (PID output, live slip target) in
  upstream switch-patch docs; would upgrade the TC plot from inferred to
  direct.
- 1D coverage heatmap rendering (pre-existing v1 gap).

## Risks & dependencies

- **Line plots of masked data can connect across mask holes**, drawing false
  bridges. Mitigation: `_pull_lines` splits each pull's masked samples into
  contiguous runs and draws one segment per run (this is the one subtle bit
  of U2).
- **RPM-sorted lines can double back** on a pull with flare/shift noise;
  sorting by RPM (not row order) makes the curve single-valued and is the
  chosen behavior — noted so the implementer doesn't "fix" it back.
- **Per-file plot keys** (`overview:<stem>`) are new to `plot_paths`
  consumers; only tests consume the dict today, but U4 should grep for other
  consumers before changing the key shape.
