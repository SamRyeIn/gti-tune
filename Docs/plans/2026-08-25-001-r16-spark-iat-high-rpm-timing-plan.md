# Plan: R16 Spark IAT correction and high-RPM timing

**Date:** 2026-08-25
**Type:** ECU calibration revision
**Requirements:** `Docs/brainstorms/2026-08-25-r16-spark-iat-requirements.md`
**Current lineage:** R15 (`Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R15.py`)

## Summary

Create R16 as the first `MainTune` revision. It reproduces the tuning guide
author's exact Spark IAT correction and matches the same-car EQT Stage 2 log's
`Ignition Table Output` curve from 5000 rpm upward. R16 inherits every other R15
calibration and patch byte.

The first unflashed R16 draft used a bounded four-cell timing step. Sam
explicitly superseded that draft and directed the final R16 to match the EQT
table-output trace across the 1050, 1200, and 1400 mg/stk rows in all nine
VVL-0 port-flap-low Basic ignition grids. Stock knock detection remains intact.

The script will generate and verify a bin only. Flashing and the final review
gate remain human-only.

## Evidence and scope boundaries

- `knowledge/ecu-tuning-basics.md` § Spark IAT correction contains the
  double-entry-verified 10 × 10 author grid and its source screenshot.
- R15 already contains a partial row-mapped version of
  `IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
  N_32, TIA. Its live axis remains the stock -30, -20.25, -9.75, 0, 30, 40.5,
  50.25, 60, 70.5, and 80.25 °C axis.
- The author axis replaces 70.5 °C with 35.25 °C. That axis is
  `ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA versus
  N_32, TIA: intake-air-temperature axis shared by the Basic and Reference IGA
  correction grids.
- The R14 WOT coverage map places the 6000–6500 rpm operating path primarily in
  the 1200–1400 mg/stk rows of
  `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]` — Basic ignition angle, VVL 0
  port-flap low, intake cam 0 exhaust cam 0. The other eight cam-position grids
  are byte-identical and must receive the same targets.
- The EQT source segment has 132 third-gear WOT samples from 5024–6336 rpm,
  zero retard on all four knock channels, and zero COBB spark reduction. Its
  `Ignition Table Output` channel is the target; `Ignition Timing Final` is not,
  because it includes correction layers that differ between calibrations.
- R15's two verified output bins have the identical SHA-256
  `02f09df6fbe4ef057f47a05a5b52656ca8bdbbfdd587c9e24f0de25d7073207a`.
  Use the REV_LOG-cited `R15_20260810-212341` bin as the R16 byte-audit
  reference.
- `Code/bin/5G0906259L__0002.bin` remains untouched recovery media.
- No `Code/` library change is required. The mapped tables, generic journaled
  writer, absolute ignition-cell writer, final-bin readback, and byte-audit
  gates already exist.

## Fixed calibration decisions

### Exact Spark IAT correction

Use named constants in the R16 script for:

- the existing ten RPM breakpoints from the source table;
- the author IAT axis -30, -20.25, -9.75, 0, 30, 35.25, 40.5, 50.25, 60,
  and 80.25 °C;
- every cell of the author's Basic IGA correction grid.

Write the exact author grid to `IP_IGA_BAS_TEMP_N_32` — Basis for temperature
correction of Basic IGA versus N_32, TIA.

Because the IAT axis is shared, migrate
`IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of Reference IGA
versus N_32, TIA onto the new axis rather than leaving its row values attached
to different temperatures. Interpolate each RPM column from the live pre-R16
axis before moving the axis. A dense before/after physical-curve comparison
must show no more than one encoded IGA step, 0.375°CRK, of deviation. The ideal
unencoded interpolation already measures about 0.181°CRK maximum deviation.

### High-RPM base timing

After the inherited R04 `TIMING` declaration, make a second absolute timing
call with a separate intent. Apply these targets to every table in the nine-map
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position family:

- 5000 rpm / 1050, 1200, and 1400 mg/stk: 1.875°CRK;
- 5500 rpm / 1050, 1200, and 1400 mg/stk: 3.750°CRK;
- 6000 rpm / 1050, 1200, and 1400 mg/stk: 6.000°CRK;
- 6500 rpm / 1050, 1200, and 1400 mg/stk: 8.250°CRK.

Those four encoded RPM anchors are the least-squares fit to all 132 source
samples: 0.188898° RMS error, 0.435° maximum absolute error, and +0.059° mean
bias. Uniform values across the three load rows prevent the falling airmass
trajectory from diluting the RPM curve.

Use `tune.ignition.retard_cells(...)` despite its historical method name: the
verified API sets absolute timing targets and writes all nine cam grids. Do not
use a relative offset because applying a delta twice is not detectable from the
resulting value alone.

Before the call, guard all twelve source cells in all nine grids against their
R15 values. After the call, compare each grid against its pre-call snapshot and
assert that exactly those twelve cells changed. Timing below 5000 rpm and at or
below 900 mg/stk must remain byte-identical to R15.

## Build sequence

1. Confirm the R15 human gate is complete before implementing R16: flashed bin
   identity recorded, logs present, analysis battery run, and
   `Logs/BasicsGuide_R15/log_review.md` authored. If R15 validation finds a fuel,
   boost, or knock regression, stop and revisit these requirements before
   creating a flash candidate.
2. Create `Tunes/MainTune/` and copy R15 to
   `Tunes/MainTune/TUNE_MainTune_R16.py`. Keep the script flat and
   self-contained; do not import another revision script.
3. Update the module header, cumulative revision history, project/output paths,
   revision name, and bin name. The history remains DRAFT revisions first,
   followed by R00 through R16 in order.
4. Continue opening the untouched stock bin, applying the unchanged CBRICK,
   HSL, and switch-patch 29.33 patch set, and declaring the complete inherited
   calibration. Do not open R15 as the edit baseline.
5. Immediately after `tune.apply_basics_sop()`, capture the live old IAT axis
   and Reference IGA grid, validate the source RPM axis, compute the migrated
   Reference grid, then journal writes for the shared IAT axis, exact Basic
   grid, and migrated Reference grid. Give every write a distinct `intent=`.
6. Keep the inherited R04 absolute `TIMING` call unchanged. Follow it with the
   separately journaled twelve-cell EQT table-output target call; this second
   call deliberately supersedes R04 values where the masks overlap.
7. Retain every R15 fueling, limiter, wastegate, boost, slot, traction-control,
   and switch-patch-sanity declaration unchanged.
8. Build revision `R16` to `Tunes/MainTune/MainTune_out/R16_<timestamp>/` as
   `Patched_259L_R16.bin`, passing the verified R15 output as
   `reference_bin=`.

## Implementation units

### U1. Create the self-contained R16 revision script

- **File:** `Tunes/MainTune/TUNE_MainTune_R16.py` (new).
- Copy R15, then update `REPO_ROOT`, `OUT_ROOT`, `OUT_BIN_NAME`, and the R15
  reference path for the new project location.
- Add the R16 cumulative header entry describing the Spark-IAT change and EQT
  table-output fit, including the combined-scope attribution tradeoff.
- Add named IAT-axis, IAT-grid, and high-RPM absolute-target constants near the
  existing ignition inputs. Do not bury calibration values inside write calls.
- Add fail-loud shape, finiteness, axis-order, source-axis, and R15-baseline
  guards before any R16-specific write.
- Keep every ECU table reference in comments, errors, and report intent text in
  `` `ID` — Description `` form.

### U2. Apply and locally verify the exact IAT family

- **File:** `Tunes/MainTune/TUNE_MainTune_R16.py`.
- Read the live old shared IAT axis and both correction grids after the inherited
  SOP has produced the R15-equivalent state.
- Assert that the RPM axis and old IAT axis match the known source geometry.
- Resample the Reference IGA grid column-by-column before changing the shared
  axis. Keep this logic specific to the R16 script; no generic library helper is
  required.
- Journal the shared-axis write as an axis change, then journal the exact Basic
  and migrated Reference grid writes.
- Read the staged values back and assert exact author-axis/Basic-grid encoding,
  Reference-grid shape, and the 0.375°CRK maximum physical-response deviation.

### U3. Apply and locally verify the high-RPM base-timing step

- **File:** `Tunes/MainTune/TUNE_MainTune_R16.py`.
- Snapshot all nine base ignition grids after the inherited R04 timing call.
- Guard the twelve source values and verify the nine grids are identical before
  applying R16.
- Call the absolute ignition writer once with the twelve approved targets and
  an intent naming the EQT source log and `Ignition Table Output` channel.
- Assert that all nine grids now match and that no cell outside the
  twelve-target mask changed relative to the snapshots.

### U4. Build, audit, and review the R16 candidate

- **Files:** generated `Tunes/MainTune/MainTune_out/R16_<timestamp>/` artifacts.
- Run the script with the repository's existing Python environment.
- Require CLEAN `CAL_CRC` and ECM3 checksums, final-bin readback PASS,
  switch-patch sanity PASS, and a CLEAN byte-level audit against R15 with zero
  unexplained bytes.
- Independently decode the finished bin and verify the IAT axis, both IAT grids,
  and twelve timing targets in all nine maps.
- Compare the finished bin against R15 and reject any changed calibration table
  outside the shared IAT axis, the Basic/Reference IAT grids, and the nine base
  ignition grids. Within the nine ignition grids, reject any changed cell
  outside the approved twelve-cell mask.
- Inspect `report.md` and the comparison heatmaps for
  `IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
  N_32, TIA,
  `IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of Reference IGA
  versus N_32, TIA, and all nine
  `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
  port-flap-low cam-position maps.
- Treat every stock-baseline comparison plot as cumulative context. Use the
  journal and R15 byte audit as the authoritative proof of what R16 changed.

### U5. Update lineage and the next-step queue after a verified build

- **Files:** `Tunes/REV_LOG.md`, `Tunes/README_NEXT_STEPS.md`, and
  `Tunes/MainTune/TUNE_MainTune_R16.py`.
- Add R16 to the REV_LOG index and append a rationale-heavy R16 section with the
  exact axis, exact twelve-cell targets, R15 reference hash, changed-byte scope,
  gate results, and CAL-flash eligibility on the already-installed R07 patch
  set.
- Correct the next-step queue's stale statement that the IAT table remained
  fully stock through R15; record that R13–R15 contained the partial SOP
  row-map and R16 completed the author's exact axis/grid.
- Move R16 out of the idea queue only after the verified build exists. Replace
  it with the R16 flash/log protocol and defer any R17 timing increase until
  R16 logs are reviewed.

## Offline validation commands and checks

Run the focused existing library tests before the revision build:

```bash
cd Code
./.venv/bin/pytest tests/test_tune_fueling_ignition.py tests/test_tune_profile.py tests/test_acceptance_tune.py -q
```

Then run the revision from the repository root with the same Python
environment:

```bash
Code/.venv/bin/python Tunes/MainTune/TUNE_MainTune_R16.py
```

The build is acceptable only when all of these hold:

- output bin name is exactly `Patched_259L_R16.bin`;
- the reference-bin SHA-256 matches the recorded R15 hash;
- checksums are CLEAN;
- every journaled table passes final-bin readback;
- switch-patch sanity resolves and decodes all expected tables;
- the R15 byte audit has zero unexplained bytes;
- the exact author IAT axis and Basic grid read back within encoding resolution;
- the Reference IGA physical-response deviation is at most 0.375°CRK;
- all nine base ignition maps contain the twelve absolute R16 targets;
- no timing cell below 5000 rpm or at/below 900 mg/stk changes;
- wastegate, boost, fueling, limiter, slot, traction-control, and knock-detection
  calibration remains identical to R15.

## Human review and on-car validation

R16 remains a starting point, not a finished calibration. A CAL flash is
eligible only after confirming the R07 patch set is already installed and the
R15 validation gate is complete. Sam performs the flash with the recovery image
available and reviews the report and plots first.

Use slot 4 and 92-octane fuel for the first comparable validation session:

1. Make one controlled third-gear pull to redline without stacking back-to-back
   attempts. The EQT-matched table begins at 5000 rpm and includes the known
   cylinder-1 susceptibility around 5500 rpm.
2. If the first pull is clean, make a separate controlled pull that begins or
   operates in the 30–40.5 °C region without deliberately creating unsafe heat
   soak. The Spark-IAT and base-table changes overlap and must be reviewed as a
   combined result.
3. Run the standard analysis battery, write `Logs/MainTune_R16/log_review.md`,
   and compare 5800+ rpm `Ign Table`, `Ign Avg`, `Knock Cyl 1-4`, IAT, lambda,
   DI rail hold, HPFP effective volume, boost tracking, turbo speed, and the
   physics-derived power curve against R14 and R15.

Expected table output follows 1.875 / 3.750 / 6.000 / 8.250° at 5000 / 5500 /
6000 / 6500 rpm respectively, while delivered timing remains subject to IAT and
other corrections. Any recurring knock in the altered band, deeper or
longer cylinder-1 retard, loss of fuel-pressure/lambda control, or protection
that prevents the requested timing from being delivered is a stop/rollback
signal rather than a reason to add more timing.

## Risks and deferred work

- Combining the IAT and base-map changes reduces attribution at high RPM when
  IAT exceeds 30 °C. The two-condition logging protocol is required to recover
  useful separation.
- Moving the shared IAT axis necessarily approximates the Reference IGA curve.
  The dense curve comparison and one-step error ceiling make that loss visible.
- The EQT match adds real combustion risk. Stock knock detection remains
  untouched and cylinder 1 remains the constraint. At Sam's explicit direction,
  R16 supersedes the earlier R04 cells from 5000 rpm upward, including the
  5500-rpm and 1050-mg/stk cells.
- The EQT calibration is not a target map. Its knock channels may reflect
  altered detection thresholds, and its channel definitions are not proven
  identical to SimosTools.
- No midrange timing change, knock-sensor calibration, additional wastegate
  correction, boost increase, or fueling change is authorized by this plan.
- Any further timing increase is deferred until R16 is flashed, logged, and
  reviewed under comparable conditions.
