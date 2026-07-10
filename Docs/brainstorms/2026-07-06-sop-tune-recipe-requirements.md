# SOP Tune Recipe — Requirements

## Problem

`ecu-tuning-basics.md` (ingested from `Docs/3. ECU Tuning - Basics.docx`) documents
a manual TunerPro SOP for turning a stock Simos18 SC8S50 bin into a tuned one:
torque request, TTA/ATT airflow, boost curve, wastegate, timing, lambda, and a
long list of limiter moves. Applying it by hand in TunerPro is what the guide
assumes, but the repo already has `simoscal` (Code/), a Python library that can
read/edit/write the same bin in physical units with safety guards (minimal-diff,
range warnings, checksum verify, float-bug guard). There's no bridge yet between
"the guide's instructions" and "a modified `.bin` produced via `simoscal`."

## Goal

Produce a scripted recipe that applies the guide's concrete, log-independent
instructions to the stock `bin/5G0906259L__0002.bin` (via `xdf/SC8S50.V1.0.xdf`)
using `simoscal`, yielding a tuned `.bin` that is *similar in shape* to the
tune the guide describes for its example bin — plus a report of what was
changed, skipped, or needs manual follow-up.

## Success Criteria

- Running the recipe against the stock bin produces a `.bin` with every
  in-scope table (below) written to the guide's literal example values, using
  `simoscal`'s normal edit path (so all existing safety guards — range
  warnings, float-bug guard, minimal-diff — apply unchanged).
- A written report enumerates, per table: applied / skipped-vague /
  skipped-log-dependent / guarded-and-skipped (e.g. overboost already >2700),
  each with the guide section it came from.
- The output bin passes `verify_checksums()` cleanly after
  `save(correct_checksums=True)`.
- Before/after visuals (reusing Phase 3 `compare_tables`/`compare_bins`) exist
  for every changed table, sufficient for a human review gate — this recipe
  does not replace the "human review gate before every flash" the README
  already requires.
- Nothing is flashed by this recipe; it stops at a saved, verified, reviewable
  `.bin`, matching the rest of the library's scope boundary.

## Scope

**In — sections applied with literal example values from the guide:**

| Guide section | Table(s) | Treatment |
|---|---|---|
| Torque request | Maximum Torque at Clutch (all gears) | Apply literal curve (320→440→275 Nm) |
| Torque → Airflow (TTA) | TTA tables, all port-flap/VVL variants | **Approximate build-out**: extend each table's existing near-linear torque→airmass relationship above 400 Nm (not a copy of the author's specific row edits, which are tied to their own bin's row layout) |
| Airflow → Torque (ATT) | ATT tables | Same proportional build-out, kept consistent with TTA per the guide's DSG-clutch-clamping rationale |
| Boost control | PUT setpoint (Option 2, preferred) | Apply literal boost curve (last-row 2698.97 hPa curve) |
| Boost control | Max PR table | Flatten to 2.80 (moves it out of the way per Option 2) |
| Boost control | Torque-tune selector | Set to 1 |
| Timing | Basic Ignition Angle, VVL 0, Intake 0 / Exhaust 0 | Apply literal table |
| Fueling | 3 fueling-influence tables | Set to 0.80 |
| Fueling | Heavy-throttle table | Set to 70–75 across |
| Fueling | 2 "must be 1" tables | Set to 1 |
| Fueling | Lambda curve (HPDI + MPI, both made identical) | Apply literal table |
| Cooling | Cylinder head temp setpoint | Cut 5 from every cell over 90 |
| Limiters | Compressor temp maps | → 300 |
| Limiters | Turbo shaft speed limiter (both) | → 220,000 |
| Limiters | Overboost limit | → 2700, **guarded**: read current value first, only write if ≤2700, else skip + warn (never lower a value already >2700, per the guide's TunerPro-bug note) |
| Limiters | Charge air pressure too high | → 3000 |
| Limiters | Max requested pressure | → 350,000 |
| Limiters | Max allowed airmass | → 2000 (relies on `simoscal`'s existing float-bug guard/entry handling, not new logic) |
| Limiters | 2× max intake air tables | → 2000 |
| Limiters | Speed limiter (4× overall max velocity tables) | → 257.49 kph |

**In — applied to the stock, non-ethanol, non-V30/LB6, IS20 hardware path**
(matches this car per `index.md`).

**Out of scope for this recipe (explicitly skipped, not guessed):**
- **Wastegate flow-factor tables** — the guide's method is inherently
  datalog-driven (read PUT-vs-target deviation from a real log, adjust that
  region). Left at stock. Reported as "needs manual/log-driven follow-up."
- **Torque-request pedal-feel tables** (DSG hi/lo-speed) — guide shows an
  example screenshot, not a literal starting table. Left at stock, reported
  as skipped-vague.
- **Spark IAT correction** — guide gives qualitative preference only ("don't
  pull until 40°C"), no concrete table. Left at stock, reported as
  skipped-vague.
- **Vague/screenshot-only limiter entries** — "Max reference indicated engine
  torque" (no number given) and any "misc → 1000/800 as noted" tables not
  individually named in text. Left at stock, reported as
  "needs manual value — see guide," never guessed.
- **V30 (18.2 arch) and LB6 variant tables** — skipped entirely, no symbol
  lookup attempted; out of scope for the 259L/SC8S50 baseline.
- **Ethanol / Flex Fuel section** — this car has no ethanol sensor and isn't
  running flex fuel; section skipped entirely.
- **DSG "sharts" (gearshift fart)** — cosmetic/optional, not requested for
  this car; skipped entirely.
- **Pops & bangs (impulse combustion)** — guide's own verdict is "don't";
  skipped entirely.
- **Flashing** — out of scope for `simoscal` generally; this recipe stops at
  a saved, checksum-verified `.bin`.

## Key Flows

1. Operator runs the recipe against the stock bin + XDF.
2. Recipe walks each in-scope table, applies the literal value/curve via the
   normal `simoscal` edit path (`set`/`set_cell`), respecting existing range
   warnings and the float-bug guard.
3. Guarded edits (currently just Overboost limit) read-before-write and skip
   with a warning if the guard condition isn't met.
4. Recipe calls `cal.save(..., correct_checksums=True)` and
   `verify_checksums()`.
5. Recipe emits a report: applied tables (with old→new values), skipped
   tables (with reason: vague / log-dependent / guarded), and generates
   before/after comparison PNGs for every applied table via the existing
   Phase 3 comparison functions.
6. Operator reviews the report + PNGs, then hands the bin to
   SimosTools/VW_Flash to flash — outside this recipe, per the library's
   existing safety posture.

## Acceptance Examples

- **AE1** — Running the recipe against the stock bin produces a bin where
  every table in the "In" list above matches the guide's literal value/curve
  exactly (in physical units), and every table in the "Out of scope" list is
  byte-identical to stock.
- **AE2** — If the stock bin's Overboost limit is already >2700, the recipe
  leaves it untouched and the report lists it as guarded-and-skipped, not
  applied.
- **AE3** — The output bin's `verify_checksums()` reports clean (not stale)
  after `save(correct_checksums=True)`.
- **AE4** — The report accounts for every table named in the "In" and "Out of
  scope" lists above — nothing silently falls through uncategorized.
- **AE5** — Comparison PNGs exist for every table actually changed from
  stock, generated via the existing Phase 3 `compare_tables`/`compare_bins`
  path (no new plotting logic).

## Key Decisions

1. **Scripted recipe, not a general config-driven tool** — this targets the
   guide's own example values for this specific car/bin, not a parametrized
   "derive a tune from a target boost curve" system. A more general tool is
   explicitly deferred.
2. **Literal absolute values, not deltas-from-stock** — write the guide's
   documented numbers directly; simplest and matches how the guide itself is
   written. Accepted risk: minor mismatch if this bin's axis breakpoints
   differ slightly from the guide's example bin (surfaced via the report/PNGs
   at the human review gate, not silently).
2b. **TTA/ATT is the one exception** — since the guide gives no complete
   literal table for TTA/ATT (only narrative edits tied to the author's own
   row layout), the recipe approximates a proportional build-out above 400 Nm
   from this bin's own near-linear torque↔airmass relationship, rather than
   copying literal cell values that don't apply here.
3. **Never guess a missing number** — any guide instruction without an
   unambiguous number (vague "move out of the way," screenshot-only "misc"
   tables, V30/LB6 variant tables) is skipped and reported, never
   approximated. Keeps with the repo's existing "fail loud, never silently
   alter values" safety posture ([[simostools-safety-stakes]]).
4. **Reuses existing safety/report machinery** — no new checksum, float-bug,
   or range-warning logic; the recipe is a sequence of calls into the
   existing `simoscal` API plus a report layer, consistent with how Phase 2
   (export) and Phase 3 (visualization) were built on top of Phase 1.
5. **Stock IS20, no ethanol, no DSG farts, no pops & bangs** — matches this
   car's actual configuration per `index.md`/EQT baseline logs; other
   hardware/fuel branches in the guide are out of scope for this recipe (a
   different car/config would need a different recipe or a parametrized
   variant, deferred).

## Deferred / Out of Scope

- General config-driven derivation of TTA/ATT/lambda/limiters from an
  arbitrary target boost curve (see Key Decision 1).
- Wastegate flow-factor tuning automation from a real datalog (would need a
  log-ingestion path this repo doesn't have yet — candidate for the
  datalog-driven Phase 4 already called out in `Code/README.md`).
- Any IS38, V30, LB6, ethanol, DSG-fart, or pops-and-bangs variant of this
  recipe.
- Flashing the output bin (always out of scope for `simoscal`).

## Outstanding Questions

None blocking. One deferred note: the guide's per-table example values are
from *an* example bin, not proven byte-identical to `5G0906259L__0002.bin`'s
factory calibration — the human review gate (comparison PNGs + checksum
verify) is the intended catch for any resulting mismatch, not a pre-flight
validation step in this recipe.
