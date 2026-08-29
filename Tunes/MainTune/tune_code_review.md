# Code review — `TUNE_MainTune_R19.py`

Reviewed 2026-08-29. Findings are ordered by priority. This is a review of the
script and its verification evidence; it is not approval to flash the generated
calibration.

## Findings

### P1 — High — The intake-axis re-breakpoint changes feedforward in logged non-WOT states

**Location:** `TUNE_MainTune_R19.py:726-764`, especially the call at lines
749-758, and `TUNE_MainTune_R19.py:820-871`.

`_apply_r19_wastegate()` claims that moving
`ldp_fac_2_ip_fac_bpa_sp` — Intake flow factor axis for the boost-pressure
actuator setpoint maps changes no commanded position anywhere this engine is
logged to run. The guard does not establish that claim. `_logged_operating_points()`
keeps only samples with at least 90% pedal, actual 3rd gear, and at least 3000
rpm. The domain call also declares preservation only through intake flow factor
1.21 and exhaust flow factor 0.65–1.46.

Replaying the axis move by itself over every valid flow-factor row in the same
18 R18 CSVs found 34 logged samples whose modeled feedforward changed by more
than 0.1 actuator-position points and 28 that changed by more than 1 point. The
largest change was 9.414 points. A clearly control-relevant example is
`simostools-2026_08_28-12_14_04.csv:303`: 6557 rpm, 53.0% pedal, exhaust flow
factor 1.120, intake flow factor 1.515, and logged `WG Pos Base` 44.659%; the
re-breakpoint changes the modeled base command by −6.079 points. The current
guard excludes that row and therefore passes.

This means the edit to `IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure
actuator setpoint is not merely a no-op geometry change plus two sized WOT cell
deltas. It also makes an unreviewed change during throttle lift or part-throttle
transition, where the logs show a nonzero base command. That can change boost
decay or transient actuator behavior, and it contradicts the safety rationale
presented to the human reviewer.

Before treating R19 as flash-reviewable, either preserve and verify the complete
reachable flow-factor envelope, remove the axis move, or establish with explicit
ECU control-state evidence that these excluded samples do not consume this
feedforward map. Add a regression check over all relevant logged states, not only
the WOT subset.

### P2 — Medium — The generated human-review summary describes an obsolete three-cell calibration

**Location:** `TUNE_MainTune_R19.py:424-435`, compared with
`TUNE_MainTune_R19.py:305-314` and `TUNE_MainTune_R19.py:789-799`.

`SUMMARY` says R19 closes three cells: 0.90 × 1.00 by +0.010, 1.05 × 1.40 by
+0.004, and 1.25 × 1.40 by +0.060, recovering about 0.3 psi. The executable
calibration instead re-breakpoints the intake axis and closes two cells: row 6,
column 14 by +0.010 and row 8, column 15 by +0.066. The function docstring at
line 733 also still calls this a three-cell close.

The authoritative generated `report.md` repeats `SUMMARY`, so its overview
misstates the bytes whose comparison plots and journal the human must review.
The detailed journal and the later R19 revision-log text describe the two-cell
version, leaving the review packet internally contradictory. This does not alter
the bin, but it undermines the human review gate and the project's traceability
promise.

Update all R19 prose to the two-cell, re-breakpointed design and regenerate the
candidate and report. The regenerated report should be checked against the
journal before recording its hash as authoritative.

### P2 — Medium — The logged-point safety gate has no fixed input provenance

**Location:** `TUNE_MainTune_R19.py:851-871`.

The gate reads every future `simostools-*.csv` under `Logs/BasicsGuide_R18`,
silently skips rows with missing or malformed fields, and accepts any result
with at least 2000 WOT points. It does not pin the 18 expected file names or
hashes, require both sessions, require exactly the stated 2537 points, or report
which files and rows were rejected.

Consequently, adding, replacing, or partially corrupting files in this human
drop zone can change the safety evidence without changing the revision script.
The gate can still pass on a different data set from the one named in the
revision rationale. Although the current output bytes do not depend on these
points, the build's permission to proceed does, so this is a reproducibility and
verification-integrity defect.

Use an explicit input manifest with file hashes and expected accepted-row counts,
and fail with the file and row number on parse errors. If the log-derived check
is intentionally advisory, remove it from the build-blocking safety argument and
state that boundary clearly.

## Open questions and assumptions

- I assume `IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure actuator setpoint
  remains behaviorally relevant in the cited lift and part-throttle samples. The
  nonzero logged `WG Pos Base` supports that inference, but a documented ECU
  mode transition could disprove it. The current script neither checks nor cites
  such a transition.
- The paired knock and wastegate changes, and the shallower
  `IP_IGA_DEC_KNK` — Spark retard at recognised knocking response to real knock,
  are treated as intentional user-authorized calibration choices. Their in-car
  safety still requires the higher-attention logging gate already recorded for
  R19.
- The existing comparison PNGs were not treated as human flash approval. The
  automated checks prove attribution and readback, not safe vehicle behavior.

## Verification performed

| Check                                       | Result                                                                                  |
| ------------------------------------------- | --------------------------------------------------------------------------------------- |
| Python syntax compile                       | PASS                                                                                    |
| Current-source `declare()` execution        | PASS; 181 journal entries, 143 tables touched                                           |
| Wastegate-domain focused tests              | PASS; 66 passed                                                                         |
| Complete `simoscal` test suite              | PASS; 1,195 passed after rerunning the network-dependent wheel test with network access |
| Saved R19 checksum gates                    | CLEAN; CAL_CRC and ECM3                                                                 |
| Saved R19 final-bin readback                | PASS; 143 tables                                                                        |
| Saved R19 raw byte audit against R18        | CLEAN; 152 changed bytes, all attributed, 0 unexplained                                 |
| Recovery-image SHA-256                      | PASS; `d61a6e297b3ac1d25f60ec8cb3bb504ff47f2db603a960a56e6a6e34074ad69b`                |
| R18 reference SHA-256                       | PASS; `b3bf96a47e0c6ab704401c09e36939b24eebdd76472ae080f9fd435205cb9bfd`                |
| Existing R19 candidate SHA-256              | `70d4da677f2f623bb6293ae9cb3f90873a16fd3b7dc199d5ff78b844db2047f5`                      |
| Isolated re-breakpoint replay, all R18 rows | FAIL; up to 9.414 actuator-position points of unreported non-WOT movement               |

## Summary

The checksum, readback, and byte-attribution machinery is working, and the
declared knock-table writes are strongly guarded. R19 nevertheless should not be
treated as ready for its human flash review while the P1 feedforward-envelope
finding remains unresolved. After that behavior is corrected or justified, the
summary/report inconsistency and log-input provenance should be fixed and a new
authoritative candidate generated.
