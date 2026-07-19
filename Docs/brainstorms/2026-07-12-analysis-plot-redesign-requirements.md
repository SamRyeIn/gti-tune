# Analysis battery plot redesign — requirements

**Date:** 2026-07-12
**Status:** Brainstorm complete, ready for planning
**Follows:** `2026-07-11-log-analysis-battery-requirements.md` (the battery itself)

## Problem

The evidence plots written by `Code/simoscal/analysis/evidence.py` are hard to
read. The plotting style was inherited by accident from a quick ChatGPT-written
review script (`Logs/BasicsGuide_R04/plot_log_review.py`) and carries its core
flaw: **color encodes the pull and only marker size encodes the quantity**, so
on every paired plot the two things being compared are visually identical.
On `analysis_wastegate.png` it is genuinely hard to tell base wastegate
position from final position; the same defect affects PUT vs PUT SP, lambda vs
lambda SP, FP DI vs FP DI SP, and LPFP duty vs HPFP effective volume.

Secondary problems:

- Scatter clouds discard the fact that a pull is a monotonic RPM sweep —
  transient spikes (e.g. the stray points near 4500 rpm) read as noise instead
  of time-localized events on a curve.
- Every plot carries a redundant 4–6 entry legend of "Pull N / SP Pull N"
  pairs.
- There is no whole-log view: nothing shows which sections of the log the
  battery identified as WOT pulls, so pull detection cannot be audited
  visually.

## Goals & success criteria

1. On any paired-quantity plot, a reader can distinguish the two quantities
   (actual vs setpoint, final vs base) at a glance, without studying the
   legend.
2. Excursions/spikes read as departures from a curve, not scatter noise.
3. A new log overview plot makes the detected WOT pull windows visible against
   the whole log, so pull detection is directly auditable.
4. The battery's findings and check logic are unchanged — this is a
   presentation-only change.

**Verification:** rerun `python -m simoscal.analysis Logs/BasicsGuide_R04`,
visually compare the regenerated PNGs against the current set, and confirm the
existing analysis test suite still passes with findings content unchanged
(except plot references).

## Scope

**In:**

- Reformat the six per-check evidence plots vs RPM (`boost`, `knock`,
  `lambda`, `rail_pressure`, `turbo_heat`, `wastegate`). Same parameters,
  new formatting.
- Add a **log overview plot** (one per log CSV) vs time.
- Add an **ignition timing plot** vs RPM: `Ign Table` and `Ign Avg` per pull
  — the timing the engine actually ran, complementing the knock-retard plot.
- Add a **TC activity plot** vs time for the switch-patch slip-based traction
  control (see decision 8). Auto-skips until its channels appear in a log.

**Out:**

- Coverage heatmaps (`analysis_coverage_*.png`) — unchanged.
- Any change to checks, thresholds, pull detection, findings JSON/MD content,
  or `log_review.md` authorship.
- New checks or new logged channels.

## Key decisions

1. **Encoding: lines, quantity = style, pull = color.** Each pull is sorted by
   RPM and drawn as a line. Actual/final quantities are solid lines colored
   per pull; setpoint/base/reference quantities are dashed dark-gray lines.
   The quantity distinction gets the strongest visual encoding; the pull
   distinction stays visible but secondary. Chosen over (a) scatter with
   color = quantity and (b) per-pull small multiples.
2. **Legend shrinks to quantities plus pulls** — e.g. `— Final (Pull 1)`,
   `— Final (Pull 2)`, `╌╌ Base` — never a full cross-product.
3. **Threshold lines stay** as dashed horizontal watch/high lines with their
   existing values.
4. **Lambda plot:** settled-WOT samples emphasized (they drive the check);
   loaded-but-transient samples shown faintly for context.
5. **Overview plot content** (x = time, stacked shared-x panels):
   - Engine speed (rpm) with gear as a step trace
   - Pedal position (%)
   - PUT and PUT SP (kPa)
   - Lambda and Lambda SP
   - Most-retarded-cylinder knock retard (deg)
   - IAT (deg C)
   Detected WOT pull windows are shaded across all panels and labeled
   ("Pull 1", "Pull 2", …).
6. **One overview per log CSV** — time axes from separate logs do not
   concatenate. File naming follows the existing `analysis_<id>.png` pattern.
7. Missing channels degrade gracefully per the existing policy: a panel with
   no data is omitted, never an error.
8. **TC activity plot content** (x = time, stacked shared-x panels). The
   switch-patch SL TC is a slip-based PID controller intervening via ignition
   retard and wastegate (`knowledge/sc8s50-switchpatch-xdf.md`); it has no
   known "TC active" channel, so the plot infers its behavior:
   - Wheel slip = mean(`Wheel Speed FL`, `Wheel Speed FR`) −
     mean(`Wheel Speed RL`, `Wheel Speed RR`) (FWD: front driven). If the
     resolved bin is switch-patched and the `Slip target straight` table
     resolves, draw it as a reference line.
   - Ignition intervention: `Ign Avg` vs `Ign Table`, with min knock retard
     overlaid to separate knock retard from TC retard.
   - Wastegate intervention: `WG Pos Final` vs `WG Pos Base`.
   - `Torque Req` vs `Torque` — the factory TC signature; with
     `Disable OEM TC` = 1 (R07) this drop should disappear, which the plot
     lets us verify.
9. New plots are additive: findings JSON/MD check content is unchanged; the
   ignition and TC plots are standalone evidence plots, not new checks.

## Acceptance examples

- **AE1 — wastegate legibility:** on the regenerated wastegate plot, base and
  final position are separable by line style alone; the legend has at most
  (number of pulls + 1) entries.
- **AE2 — overview audits pull detection:** the overview plot's shaded spans
  exactly match the pulls reported by the battery for
  `Logs/BasicsGuide_R04`, each labeled with its pull index.
- **AE3 — presentation-only:** rerunning the battery on
  `Logs/BasicsGuide_R04` leaves `analysis_findings.json` unchanged except for
  plot filename references.
- **AE4 — spikes legible:** the transient PUT/WG excursions near 4500 rpm in
  the R04 log read as brief departures from the pull's curve.
- **AE5 — TC plot degrades:** on the R04 log (no wheel-speed channels), the
  TC activity plot is skipped without error; on a log carrying the wheel-speed
  channels it renders with whatever panels have data.
- **AE6 — timing plot:** the ignition plot shows `Ign Table` and `Ign Avg`
  per pull vs RPM with the quantity-as-style encoding from decision 1.

## Deferred / out of scope

- 1D coverage heatmap rendering (pre-existing v1 gap, unrelated).
- Interactive (HTML) plots.
- Any restyling of `Tunes/` compare PNGs (`simoscal.plot`) — different module,
  different purpose.

## Outstanding questions

- **Not blocking:** the switch patch may expose its own TC RAM addresses
  (live PID output, live slip target) that would make the TC activity plot
  direct instead of inferred. Nobody has hunted for them yet — worth checking
  upstream switch-patch docs / BinToolz definitions before or after R07
  flashing; the inferred plot works either way.
