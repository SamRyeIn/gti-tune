# Log Analysis Battery — Implementation Plan

Date: 2026-07-11
Type: feat
Origin: `Docs/brainstorms/2026-07-11-log-analysis-battery-requirements.md`
Depth: Standard (7 units)
Status: completed (2026-07-12) — all 7 units implemented on `feat/log-analysis-battery`; R01/R04 acceptance replay green with no false High findings.

## Summary

Add a `simoscal.analysis` subpackage that runs an identical, enumerable battery
of checks against a `Logs/<Tune>_R<NN>/` folder of SimosTools CSVs and writes a
machine-readable findings file, a rendered summary, an explicit SKIPPED list,
and evidence plots into that folder. Claude consumes the output to write
`log_review.md`; nothing writes or proposes calibration changes. Acceptance is
regression replay against the human-reviewed `Logs/BasicsGuide_R01/` and
`Logs/BasicsGuide_R04/` findings.

## Problem Frame

Log review is currently re-derived per revision by hand: inconsistent coverage,
high token cost, and conclusions that cannot be regression-tested. The
requirements doc scopes v1 to **findings only** — no proposers, no
orchestration, no bin writing — with the tool feeding Claude, and
`log_review.md` remaining the human deliverable.

## Requirements (from origin doc)

- R1 — Identical, enumerable check battery per log folder; printable battery
  list; explicit SKIPPED list with reasons (AE3).
- R2 — PID-list-aware parsing: channel names/units/scaling resolved from
  headers; gear indexing resolved per the header rule, never guessed (AE4).
- R3 — Pull detection with per-pull summary table, including per-pull
  environment context (ambient temp/pressure, IAT at pull start, coolant
  temp, ethanol content) so pulls are comparable across logs and revisions.
- R4 — Calibration-aware checks may compare logs against the flashed bin + XDF.
- R5 — Findings ranked High/Medium/Low with per-finding evidence and plot refs.
- R6 — Deterministic output: identical inputs → identical findings content (AE5).
- R7 — Regression replay reproduces R01/R04 headline findings with no false
  High findings (AE1, AE2).
- R8 (added 2026-07-11, post-brainstorm) — Per-table coverage maps: for each
  primary tuning table, report which cells the log exercised (per-cell hit
  counts), as evidence for findings, input to the next-log request, and the
  future hit-count gate for Layer 2 proposers.
- R9 (added 2026-07-11, post-brainstorm) — Log-quality preflight: before any
  check runs, validate the raw data (sample-rate consistency, time gaps,
  frozen/stuck channels, dropped-frame stretches) and surface problems as
  findings so no downstream conclusion rests on silently corrupt data.

## Key Technical Decisions

| Decision              | Choice                                                              | Rationale                                                                                    |
|-----------------------|---------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| Package layout        | `Code/simoscal/analysis/` subpackage (`log.py`, `pulls.py`, `registry.py`, `checks.py`, `report.py`, `evidence.py`, `__main__.py`) | Existing library is flat modules, but analysis is a cohesive multi-file feature; a subpackage keeps the top level clean while staying inside `simoscal` (brainstorm decision A + C) |
| Channel resolution    | Header-driven: parse `Name (Unit)` columns into canonical channel IDs with unit normalization (e.g. `Airmass (g/stk)` → mg/stk canonical) | The CSV header already carries name + unit; `PIDs/` CSVs inform the canonical map during development but are not a runtime dependency |
| Gear indexing         | Header rule only: `Gear (gear)` = actual, `Gear ()` = logged + 1; any other form → gear unresolved → gear-dependent checks land in SKIPPED with reason | Matches the confirmed profile-dependent rule; fail loud on ambiguity, never guess           |
| Check registry        | Each check is a registry entry: id, title, required/optional canonical channels, threshold constants (data, not code), severity rules, compute fn returning findings | Battery becomes enumerable/auditable; SKIPPED falls out of required-channel matching (R1)   |
| Thresholds            | Seeded from R01/R04 reviews (e.g. lambda lean watch line +0.03, knock recurrence, overshoot bands) and stored on the registry entry | Inspectable, tunable in one place, and printable alongside the battery list                  |
| Findings output       | `analysis_findings.json` (sorted keys, fixed float formatting) + `analysis_findings.md` (rendered summary incl. battery, SKIPPED, pull table) written into the log folder | JSON for tooling/tests, Markdown for humans; fixed formatting gives AE5 determinism         |
| Evidence plots        | matplotlib PNGs to `plots/analysis_<check>_*.png` in the log folder; findings reference plot filenames | Coexists with the per-folder `plot_log_review.py` pattern without replacing it              |
| Bin/XDF location      | Parse the `*.bin.txt` filename (`<box>_<Tune>_R<NN>.bin.txt`) and search `Tunes/<Tune>/<Tune>_out/R<NN>_*/` for the matching bin; explicit override parameter; if unresolved, calibration-aware checks go to SKIPPED | The `.bin.txt` file is empty — the filename is the record; degrading to SKIPPED matches the missing-channel policy |
| Entry point           | `python -m simoscal.analysis <log-folder>` via `analysis/__main__.py`, thin over a public `analyze_folder()` API | Library-first like the rest of `simoscal`; no new CLI framework                              |
| Testing split         | Unit tests on small synthetic CSV fixtures in `Code/tests/fixtures/logs/`; acceptance replay against real `Logs/` folders via `PROJECT_ROOT`, skipping cleanly when absent | Mirrors the existing `conftest.py` pattern (real bin/XDF skip-if-absent); real logs live in the root repo, not the `Code/` repo |

## High-Level Flow

```
Logs/<Tune>_R<NN>/*.csv ──▶ LogSet (canonical channels, units, gear) ──▶ pull detection
                                                                            │
Tunes/.../R<NN>_*/ bin + Code/xdf ──▶ CalFile (optional) ──────────────────▶│
                                                                            ▼
                                                  registry runner (checks + thresholds)
                                                                            │
                     ┌──────────────────────────────────────────────────────┤
                     ▼                          ▼                           ▼
        analysis_findings.json      analysis_findings.md         plots/analysis_*.png
                     └──────────────── Claude writes log_review.md ─────────┘
```

## Implementation Units

### U1. Log loading and channel resolution

- **Goal**: Parse a folder of `simostools-*.csv` files into a `LogSet` of
  time-indexed frames with canonical channel IDs and normalized units, plus a
  log-quality preflight whose results ride along as `LogSet` quality metadata.
- **Requirements**: R2, R9.
- **Dependencies**: none.
- **Files**: `Code/simoscal/analysis/__init__.py`, `Code/simoscal/analysis/log.py`,
  `Code/tests/test_analysis_log.py`, `Code/tests/fixtures/logs/` (synthetic CSVs).
- **Approach**: Header parser splits `Name (Unit)` into canonical ID + unit via
  an explicit channel map (seeded from the R01/R04 headers and `PIDs/` CSVs);
  unit normalizers (g/stk → mg/stk, psi vs kPa kept as logged with canonical
  kPa accessor); gear resolver implements the header rule and returns an
  *unresolved* sentinel otherwise; unknown columns are retained but unmapped
  (reported, not fatal). Fail loud on duplicate/contradictory headers.
  Quality preflight per file: sample-interval statistics and gap detection
  (time jumps beyond a tolerance multiple of the median interval),
  frozen/stuck-channel detection (zero variance over a window where the
  engine state is clearly changing), and non-numeric/dropped-row accounting.
  Preflight never mutates or repairs data — it annotates.
- **Test scenarios**:
  - Happy: R04-style header (`Gear (gear)`, `Airmass (g/stk)`) → actual gear,
    mg/stk airmass.
  - Edge: R01-style `Gear ()` → +1 offset applied.
  - Error: header with `Gear (idx)` → gear unresolved sentinel, no exception at
    load time.
  - Error: two columns mapping to the same canonical channel → loud failure.
  - Quality: synthetic log with a 2 s gap mid-file → gap recorded in quality
    metadata with timestamps.
  - Quality: channel frozen at a constant while rpm sweeps → stuck-channel
    annotation on that channel.
- **Verification**: unit tests pass; loading a real R01 and R04 folder yields
  the expected canonical channel inventory and a clean (or explainable)
  preflight.

### U2. Pull detection and per-pull summary

- **Goal**: Segment WOT pulls from a `LogSet` and compute the per-pull summary
  (gear, rpm span, duration, peaks) matching the existing "Pull Summary"
  section's content, extended with per-pull environment context columns:
  ambient temp/pressure, IAT at pull start, coolant temp, ethanol content.
- **Requirements**: R3.
- **Dependencies**: U1.
- **Files**: `Code/simoscal/analysis/pulls.py`, `Code/tests/test_analysis_pulls.py`.
- **Approach**: Threshold-based segmentation on pedal/load + rpm slope with
  minimum-duration filtering; gear attribution from the resolved gear channel
  (pulls unattributed when gear is unresolved). Detection constants live as
  named module data so they are printable with the battery.
- **Test scenarios**:
  - Happy: synthetic log with two clean 3rd-gear pulls → two segments, correct
    bounds and gear.
  - Edge: pull interrupted by a lift → split or rejected by min-duration, not
    merged.
  - Edge: unresolved gear → pulls detected, gear field marked unresolved.
  - Edge: environment channel absent from the PID list → that column reported
    as unavailable in the pull summary, not blank or zero.
  - Integration: real R04 log → the two actual-3rd-gear WOT pulls the human
    review identified.
- **Verification**: real-log pull count/gears match the R01/R04 review tables.

### U3. Check registry, runner, and findings report

- **Goal**: The framework — registry entry type, runner that executes checks
  whose required channels are present, findings/SKIPPED data model, and
  deterministic JSON + Markdown emitters.
- **Requirements**: R1, R5, R6.
- **Dependencies**: U1, U2.
- **Files**: `Code/simoscal/analysis/registry.py`, `Code/simoscal/analysis/report.py`,
  `Code/tests/test_analysis_registry.py`.
- **Approach**: `Check` dataclass (id, title, required/optional channels,
  thresholds dict, needs_cal flag, compute fn); runner resolves availability
  against the `LogSet` (and `CalFile` presence for `needs_cal`), collects
  `Finding` objects (check id, severity, message, evidence values, pull refs,
  plot refs) and `Skipped` objects (check id, missing channels / reason).
  Emitters produce sorted-key JSON with fixed float formatting and a Markdown
  summary containing the full battery list, thresholds, pull table, findings by
  severity, and SKIPPED.
- **Test scenarios**:
  - Happy: toy registry of two checks, all channels present → both run, JSON +
    md contain both.
  - Edge: check missing one required channel → SKIPPED entry names the check
    and the channel (AE3 shape).
  - Edge: `needs_cal` check with no bin resolved → SKIPPED with reason.
  - Determinism: run twice on identical inputs → byte-identical JSON (AE5).
- **Verification**: emitted files are stable across reruns; battery list is
  printable without running any check.

### U4. The v1 check battery

- **Goal**: Implement the nine check families as registry entries with
  thresholds seeded from the R01/R04 reviews — the eight from the
  requirements doc plus a data-quality family surfacing U1's preflight
  results as findings.
- **Requirements**: R1, R4, R5, R7, R9.
- **Dependencies**: U3.
- **Files**: `Code/simoscal/analysis/checks.py`, `Code/tests/test_analysis_checks.py`.
- **Approach**: Checks — knock retard per cylinder (magnitude, recurrence
  across pulls, load/rpm location); boost tracking (`PUT` vs `PUT SP` error
  bands, overshoot peaks, overboost/limiter events); wastegate duty
  (saturation/headroom, correlation with boost error); lambda (`Lambda` vs
  `Lambda SP`, lean watch line +0.03, transient vs settled discrimination);
  rail pressure (`FP DI` vs `FP DI SP` sag under demand); timing delivered vs
  conditions and interventions; temperatures (IAT rise / heat-soak flag,
  coolant/oil sanity); torque interventions / limiter hits; data quality
  (U1 preflight results rendered as findings — a gap or stuck channel that
  overlaps a pull is at least Medium, since it undermines every other
  finding on that pull). Calibration-aware
  variants (flagged `needs_cal`) compare logged setpoints against the flashed
  tables via `CalFile` — e.g. logged boost setpoint vs `C_PRS_IM_SP_MAX` —
  Maximum requested intake-manifold pressure setpoint ceiling; exact table set
  finalized during implementation against the XDF.
- **Test scenarios** (per family, on synthetic fixtures):
  - Happy: clean pull → no findings above Low.
  - Edge: injected -3.0° knock on one cylinder across two pulls → High knock
    finding with recurrence noted (R01 shape).
  - Edge: +22 kPa boost overshoot pocket → High boost finding with peak value
    (R04 shape).
  - Edge: lambda error +0.023 settled → Medium/OK, below watch line; +0.05 →
    High.
  - Error: check computing on unresolved gear where gear is required → SKIPPED,
    not a wrong-gear finding.
- **Verification**: synthetic-fixture tests pass for every family; each check's
  thresholds appear in the printed battery.

### U5. Evidence plots and the folder entry point

- **Goal**: `analyze_folder()` public API plus `python -m simoscal.analysis`
  wrapper: locate CSVs and the flashed bin, run the battery, write findings
  files and evidence plots into the log folder.
- **Requirements**: R1, R4, R5, R6.
- **Dependencies**: U3, U4.
- **Files**: `Code/simoscal/analysis/evidence.py`,
  `Code/simoscal/analysis/__main__.py`, `Code/tests/test_analysis_folder.py`.
- **Approach**: Bin autolocation from the `*.bin.txt` filename → search
  `Tunes/<Tune>/<Tune>_out/R<NN>_*/` (newest timestamped folder wins; explicit
  bin/xdf override parameters); plots per finding family (time series with
  setpoint overlays, per-pull knock strips, error histograms) written to
  `plots/analysis_*.png` and referenced from findings; reuse `simoscal.plot`
  styling conventions where applicable. Findings written as
  `analysis_findings.json` + `analysis_findings.md`.
- **Test scenarios**:
  - Happy: synthetic folder with CSVs + resolvable bin → all outputs written,
    calibration checks ran.
  - Edge: no `*.bin.txt` / bin not found → run completes, `needs_cal` checks in
    SKIPPED.
  - Edge: empty folder (no CSVs) → loud failure naming the glob.
  - Integration: rerun on same folder → JSON byte-identical, plots overwritten.
- **Verification**: running against a copy of a real log folder produces the
  full output set; SKIPPED behavior matches AE3/AE4.

### U6. Acceptance regression replay and docs

- **Goal**: Encode the R01/R04 ground truth as acceptance tests; document the
  module and its place in the tuning loop.
- **Requirements**: R7 (AE1, AE2), plus doc upkeep.
- **Dependencies**: U5.
- **Files**: `Code/tests/test_acceptance_analysis.py`, `Code/README.md`,
  `SimosTools/index.md` (note pointer), `CLAUDE.md` (one-line loop-step
  addition if warranted).
- **Approach**: Acceptance tests resolve `Logs/BasicsGuide_R01/` and
  `Logs/BasicsGuide_R04/` via `PROJECT_ROOT` and skip cleanly when absent
  (existing conftest pattern). Assert headline reproduction: R01 → High knock
  (repeated -3.0° regions) and High boost overshoot (+18 to +26 kPa pockets);
  R04 → knock resolved (0.0° on all four cylinders in both actual-3rd-gear
  pulls), High boost overshoot (+22.2 kPa, PUT peak 286.4 kPa), lambda
  Medium/OK (max lean ≈ +0.023 under settled WOT). Assert **no false High
  findings**: every High the tool emits on these folders is one the human
  review also called High. Update `Code/README.md` with the module,
  invocation, and output contract; step 5 of the tuning loop gains "run the
  analysis battery first."
- **Test scenarios**: the acceptance assertions above are the scenarios;
  plus skip-if-absent when `Logs/` is missing from a lean checkout.
- **Verification**: acceptance suite green on this machine against the real
  log folders; docs reviewed by Sam.

### U7. Table coverage maps

- **Goal**: For a configurable list of primary tuning tables, compute per-cell
  hit counts from the log (whole-log and WOT-pull-only variants) and emit
  coverage heatmaps + a JSON coverage map alongside the findings.
- **Requirements**: R8; supports R5 (evidence) and feeds the "Next Log
  Request" content of `log_review.md`.
- **Dependencies**: U1, U2, U5 (bin/XDF autolocation and `CalFile` plumbing).
- **Files**: `Code/simoscal/analysis/coverage.py`,
  `Code/tests/test_analysis_coverage.py`; extends `report.py` and
  `evidence.py` outputs.
- **Approach**: ECU-lookup simulation — map each logged sample onto a table's
  axis breakpoints (read from the flashed bin via `CalFile`) and accumulate
  per-cell hit counts. Core design artifact: an explicit **axis-to-channel
  mapping** per covered table (axis variable → canonical log channel + any
  unit conversion), defined as registry-style data. Initial table list:
  `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost pressure actuator setpoint,
  `IP_LAMB_BAS_HPDI` — Basic lambda setpoint grid (HPDI), the primary ignition
  timing grid, and the boost/airmass setpoint tables touched by the tune
  lineage (finalized against the XDF during implementation, same as U4's
  table set). Tables whose axis inputs are not present in the log's channels
  go to SKIPPED with the missing channel named — never a guessed mapping.
  Outputs: `plots/analysis_coverage_<table>.png` heatmaps (hit-count color
  scale, axis breakpoints as ticks) and a `coverage` section in
  `analysis_findings.json`. Keep v1 to raw hit counts;
  intervention-filtered counts (excluding samples during torque
  interventions/limiter activity) are a flagged refinement, not v1.
- **Test scenarios**:
  - Happy: synthetic log sweeping known axis regions of a real table → hit
    counts land in the expected cells, zeros elsewhere.
  - Edge: samples beyond the axis range → accumulate in the edge cells
    (matching ECU clamp behavior), not dropped silently.
  - Edge: covered table whose axis channel is absent from the log → SKIPPED
    entry naming the channel.
  - Edge: no bin resolvable → all coverage entries SKIPPED (consistent with
    `needs_cal` policy).
  - Determinism: rerun → byte-identical coverage JSON.
- **Verification**: coverage heatmaps for a real R04 log visibly match the
  known operating envelope (3rd-gear WOT trajectory), and the WOT-only
  variant is a subset of the whole-log counts.

## Test Strategy (added 2026-07-11, applies across units)

Ranked by confidence bought; the per-unit scenarios above remain, these shape
*how* they are built.

1. **Synthetic fault injection (primary pattern for U4 tests).** Build a small
   fixture-generator module (`Code/tests/fixtures/logs/` + helper) that takes
   a clean real-log excerpt and injects known defects: a -3° knock event on
   one cylinder across two pulls, a +0.05 lambda lean spike under settled
   WOT, a +25 kPa boost overshoot pocket, a 2 s time gap, a frozen
   `FP DI (kpa)` channel. Ground truth is exact by construction — each check
   must fire at the right severity, pull, and location, and **only** there
   (false-alarm coverage, not just miss coverage). Extend the generator with
   each newly discovered failure mode.
2. **Metamorphic invariance tests (no ground truth needed).**
   - Rewrite a `Gear (gear)` log into `Gear ()` form (values -1, header
     changed) → byte-identical findings.
   - Convert `Airmass (g/stk)` header+values to mg/stk → identical findings.
   - Drop a channel → findings are a subset of the original and SKIPPED
     grows; no new findings may appear.
   - Reorder/rename CSV files in the folder → identical findings content.
   - U7: WOT-only coverage counts ⊆ whole-log counts; per-table totals equal
     sample count when all axis channels are present.
3. **Duplicate-log policy (affects U1, bites at U6).** Real folders contain
   both full and trimmed exports of the same capture (e.g. R01's
   `simostools-2026_07_07-22_50_43.csv` and `..._22_50_43_trim.csv`). Naive
   globbing double-counts that pull in summaries, recurrence logic, and
   coverage. Policy: detect overlapping time ranges across files and fail
   loud (or dedup with an explicit note in the report) — never silently
   count twice. Needs a test with a real trim pair.
4. **Golden findings files.** Once R01/R04 replay is validated by human
   review, freeze those `analysis_findings.json` outputs as goldens under
   `Code/tests/fixtures/`; future diffs must be consciously accepted (same
   philosophy as the TunerPro oracle capture).
5. **Nasty-input battery.** Header-only CSV, truncated final row,
   non-numeric cells mid-column, folder mixing two PID profiles.
6. **Assertion style.** Acceptance/replay tests assert on findings *content*
   with tolerances (severity level, peak values within ±1 kPa, recurrence
   counts) — never on message strings.
7. **Blind double-entry (process, not code).** For the first 2–3 post-tool
   log folders, Claude reviews the logs cold before reading tool output,
   then diffs; disagreements become bug fixes or threshold fixtures.

## Scope Boundaries

- No proposers, no orchestration logic, no bin writing (brainstorm decisions).
- `log_review.md` authorship stays with Claude; the tool never writes it.
- Existing per-folder `plot_log_review.py` scripts stay untouched; deep-dive
  plotting remains ad hoc on top of the battery.

### Deferred to Follow-Up Work

- Layer 2 wastegate proposer pilot (`IP_FAC_BPA_SP[0]`/`[1]` — Map for boost
  pressure actuator setpoint) once the battery is trusted; U7's coverage maps
  become its hit-count gate.
- Intervention-filtered coverage counts (excluding samples logged during
  torque interventions / limiter activity) — refinement on U7's raw counts.
- Cross-revision trend reports (comparing findings across R<NN> folders) — a
  natural extension of the JSON output, out of v1.

## Risks & Dependencies

- **Threshold fidelity** — seeded thresholds may over/under-fire vs human
  judgment; mitigated by the no-false-High acceptance gate and thresholds
  living as inspectable registry data.
- **Pull detection brittleness** — DSG shifts and partial lifts can fragment
  pulls; mitigated by validating segment counts against the human-reviewed
  pull tables in U2 before the battery depends on them.
- **Channel-map coverage** — new PID profiles introduce unseen headers; the
  unmapped-but-reported design plus SKIPPED keeps this a visible gap, not a
  silent one.
- **Cross-repo fixtures** — real logs live in the root repo while tests live in
  the `Code/` repo; handled by the established `PROJECT_ROOT` skip-if-absent
  pattern.

## Open Questions

None blocking. Exact calibration-aware table comparisons in U4 are finalized
during implementation against the XDF (deferred to implementation by design).
