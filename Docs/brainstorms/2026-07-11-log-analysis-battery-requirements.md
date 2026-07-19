# Log Analysis Battery — Requirements

Date: 2026-07-11
Status: Brainstorm complete, ready for planning

## Problem

Every tune revision's log review is currently re-derived from scratch by Claude
reading raw SimosTools CSVs. This has three costs:

- **Inconsistency** — different revisions get slightly different scrutiny; a
  check run on R01 may be silently absent from R04's review.
- **Token cost / speed** — each review burns substantial Claude context on
  deterministic signal processing (binning, thresholding, plotting).
- **Unverifiable analysis** — conclusions come from one-off reasoning that
  cannot be regression-tested or audited later.

Explicitly **not** the problem being solved: autonomy. The goal is a rigorous,
cheap, auditable analysis layer inside the existing human-in-the-loop tuning
cycle — not a self-driving tuner.

## Goals & Success Criteria

1. Every log folder gets the **identical, enumerable battery of checks** —
   the tool can print exactly what it checks, and what it skipped and why.
2. Claude's per-review work shifts from *computing* findings to *judging*
   them — cross-revision context, causal interpretation, next-revision calls.
3. Findings are reproducible: rerunning the tool on the same inputs yields
   the same findings file, testable in CI.
4. **Regression replay passes**: run against the existing
   `Logs/BasicsGuide_R01/` and `Logs/BasicsGuide_R04/` folders, the tool
   independently reproduces the human-reviewed headline findings (knock
   events, boost-tracking error, wastegate-duty story) with no false
   High-severity findings.

## Scope

### In scope (v1)

- A `simoscal.analysis` module: point it at a `Logs/<Tune>_R<NN>/` folder,
  it emits a machine-readable findings file plus evidence plots into that
  folder.
- **PID-list-aware log parsing** — channel names, units, and scaling resolved
  via the `PIDs/` CSVs; gear indexing resolved per the profile-dependent rule
  (`Gear ()` = zero-indexed, `Gear (gear)` = actual), never assumed.
- **Pull detection** — segment WOT pulls, identify gear, produce a per-pull
  summary table (the machine version of the existing "Pull Summary" section)
  including per-pull environment context (ambient temp/pressure, IAT at pull
  start, coolant temp, ethanol content) so pulls are comparable across logs.
- **Log-quality preflight** (added 2026-07-11 after planning began) — validate
  raw data before any check runs: sample-rate consistency, time gaps,
  frozen/stuck channels, dropped rows. Problems surface as findings; the
  preflight annotates, never repairs.
- **Declarative check registry** — each check declares required channels,
  compute logic, thresholds, and severity rules. The runner executes every
  check whose channels are present and emits an explicit SKIPPED list for the
  rest. Adding a check is one registry entry.
- **Calibration-aware checks** — checks may read the flashed bin + XDF (via
  existing `simoscal` machinery) to compare logged behavior against the
  calibration actually on the car (e.g. logged boost vs the flashed setpoint
  tables).
- The v1 check battery, derived from the R01/R04 human reviews:
  - Knock retard per cylinder vs load/rpm; recurrence across pulls.
  - Boost tracking: setpoint vs actual error, overshoot, limiter/overboost
    events.
  - Wastegate duty: saturation, headroom, correlation with boost error.
  - Lambda: setpoint vs actual, lean excursions under load.
  - Rail pressure: setpoint tracking, sag under demand.
  - Timing: actual advance delivered vs conditions; interventions.
  - Temperatures: IAT rise / heat-soak flags, coolant/oil sanity.
  - Torque interventions / limiter hits.
- Findings ranked High/Medium/Low with per-finding evidence (values, pull,
  timestamps, plot references).
- **Table coverage maps** (added 2026-07-11 after planning began) — per-cell
  hit counts for the primary tuning tables via ECU-lookup simulation over the
  log: qualifies findings and table edits against actual data density, feeds
  the "next log request", and pre-builds the hit-count gate Layer 2 proposers
  will need. Tables whose axis inputs aren't logged are SKIPPED, never
  guessed.

### Out of scope (v1)

- **Proposers** — no computed table corrections of any kind. The tool reports
  findings; changes are decided in the revise step as today.
- **Orchestration** — no logic that reconciles findings into a tune strategy;
  that remains Claude + Sam.
- **Any bin writing or flashing** — unchanged safety model; the tool is
  read-only with respect to calibrations.
- Replacing `log_review.md` — see Key Decisions.

## Key Flow

1. Sam drops SimosTools CSVs into `Logs/<Tune>_R<NN>/` (as today).
2. Tool is run against the folder (plus the flashed bin + XDF for
   calibration-aware checks).
3. Tool writes findings file (machine-readable) + evidence plots + SKIPPED
   list into the folder.
4. Claude reads the findings and writes `log_review.md` around them — adding
   judgment, cross-revision context, and next-revision implications.
   `log_review.md` remains the human deliverable; Sam reviews as today.

## Acceptance Examples

- **AE1** — Run on `Logs/BasicsGuide_R01/`: reproduces that review's headline
  safety and boost-tracking findings; no false High findings.
- **AE2** — Run on `Logs/BasicsGuide_R04/`: reproduces the ignition-validation
  review's findings, including the wastegate/flow-factor observations.
- **AE3** — Run on a log whose PID list lacks rail-pressure channels: all
  other checks run; output contains an explicit SKIPPED entry naming the
  rail-pressure check and the missing channels.
- **AE4** — Run on a log where gear indexing cannot be resolved from the
  header/PID list: the tool fails loud on gear-dependent checks rather than
  guessing an offset.
- **AE5** — Rerun on identical inputs: byte-identical findings content
  (plots may differ in metadata only).

## Key Decisions

| Decision                | Choice                                        | Why                                                                                     |
|-------------------------|-----------------------------------------------|-----------------------------------------------------------------------------------------|
| Driver                  | Consistency, cost, verifiability — not autonomy | Sam confirmed; shapes v1 as instrumentation, not autotune                              |
| V1 scope                | Findings only, no proposers                   | Trust the analysis layer first; proposers are a later, separately-validated layer        |
| Output role             | Feeds Claude; `log_review.md` stays the deliverable | Keeps narrative judgment and cross-revision context in the human doc              |
| Missing channels        | Run what's possible + explicit SKIPPED list   | Real logs vary by profile; fail loud only on ambiguity (gear indexing, units) — never guess |
| Architecture            | `simoscal.analysis` + declarative check registry (A + C) | Calibration-aware checks need the library anyway; registry makes the battery enumerable and auditable |
| Validation              | Regression replay vs R01/R04 human reviews    | Existing reviewed logs are ground truth; also becomes the permanent test fixture set     |

## Deferred / Future Layers

- **Layer 2 — per-domain proposers**: damped, hit-count-gated table
  corrections output as proposed deltas + evidence. Pilot: wastegate
  feedforward via `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost pressure actuator
  setpoint. Fueling next; timing last and pull-only (never auto-advance).
- **Layer 3 — orchestration**: intentionally never automated; holistic
  reconciliation stays with Claude + Sam.

## Outstanding Questions (non-blocking, resolve in planning)

- Findings file format (likely JSON + a rendered Markdown summary) and
  whether plots reuse/replace the per-folder `plot_log_review.py` pattern.
- Exact thresholds/severity rules per check — seed from the R01/R04 reviews'
  implicit thresholds; make them registry data so they're inspectable.
- How the tool locates the flashed bin for a log folder (the `*.bin.txt`
  record exists; convention needs pinning down).
