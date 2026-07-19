# Plan: R11 switch-patch PUT maps

**Date:** 2026-07-13  
**Type:** ECU calibration revision  
**Requirements:** `Docs/brainstorms/2026-07-13-r11-switch-patch-put-revision-requirements.md`  
**Current lineage:** R10 (`Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R10.py`)

## Summary

Create R11 as a new, deterministic revision script. It will retain the R10
calibration and patches, park the full-load row of `IP_PUT_SP` — Pressure up
throttle setpoint at a non-binding 30 psi gauge-equivalent ceiling, and make
all five patch-added **`PUT setpoint`** grids explicit lower caps. The resulting
slot roles are: R08-style curve in slots 1, 4, and 5; an approved intermediate
curve in slot 2; and the former R10 slot-2 26 psi shelf in slot 3.

The script will generate and verify a bin only. A human must visually review the
report and plots before a full flash; flashing itself is out of scope.

## Evidence and scope boundaries

- R09 logs prove that the active patch **`PUT setpoint`** grid caps the shared
  `IP_PUT_SP` — Pressure up throttle setpoint through `min()` semantics. It is
  not an override and cannot command above the shared table.
- The five patch grids have distinct Z-data at `0x7D41A`, `0x7D4DA`, `0x7D59A`,
  `0x7D65A`, and `0x7D71A`, but share the patch-added **`PUT SP RPM Axis`** at
  `0x7D7DC`. Its associated **`PUT SP RPM Axis Header`** at `0x7D7DA` must
  remain 12.
- R10's `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor shape, TC flags, fueling, ignition, and wastegate-feedforward
  calibration are inherited unchanged.
- `Code/` requires no library change. The R11 script remains a consumer of the
  established `simoscal`/BinToolz adapter pipeline; its nested worktree is not
  to be modified for this revision.
- `Code/bin/5G0906259L__0002.bin` remains read-only recovery media.

## Open calibration decisions required before implementation

The implementation mechanics are settled, but two values must be approved
before a script is written:

1. The exact 12-point shared **`PUT SP RPM Axis`**. It must be strictly
   increasing, retain meaningful coverage of 3000–6500 rpm, and support the
   established R08 and 26 psi reference curves without unintended
   interpolation changes.
2. The slot-2 full-load hPa curve on that axis. It must equal slot 1's maximum,
   remain flat through 4400 rpm, and be strictly above slot 1 at every later
   breakpoint. It cannot simply reuse the R10 slot-2 8.2 psi fall from 4400 to
   6500 rpm, because that would finish below slot 1's 17.2 psi target.

This plan intentionally does not invent either calibration. Once approved, the
two lists become named constants and all verification derives from them.

## Technical design

### R11 target configuration

Define a compact, reviewable configuration block in the R11 script:

- `R11_SHARED_CEILING_HPA`: 30 psi gauge converted once to hPa absolute using
  the lineage's documented `1016 hPa` reference and `68.95 hPa/psi`
  conversion (approximately 3085 hPa).
- `R11_SLOT_RPM_AXIS`: the approved 12-point RPM list for the patch-added
  **`PUT SP RPM Axis`**.
- `R11_SLOT_CURVES_HPA`: a slot-number → 12-cell full-load curve mapping.
  Slots 1, 4, and 5 derive by interpolation from the known R08 reference;
  slot 3 derives from the R10/R09 26 psi reference; slot 2 uses the newly
  approved intermediate values.

Validate the configuration before any bin write: exactly 12, strictly
increasing RPM values; five 12-cell finite curves; all caps positive and below
the shared ceiling; and explicit slot-2 predicates for peak, 4400-rpm plateau,
and post-4400 separation from slot 1. The checks must reject rather than clamp
or silently reshape an invalid curve.

### Build sequence

Start from stock exactly as R10 does: apply the three known `.btp` patches,
then run the R06 calibration pipeline and R08 wastegate overlay. Do not use a
previous generated bin as an input.

On the SC8S50 XDF stage, replace R09's 26 psi helper with an R11-specific
helper. It will verify the expected R08 baseline, retain R09's private
`ldp_n_ip_put_sp` RPM-axis layout `[3000, 3400, 4400, 5000, 5750, 6500]`,
preserve the three part-load rows byte-for-byte, and set only the full-load row
of `IP_PUT_SP` — Pressure up throttle setpoint to the flat R11 shared ceiling.
Then apply the unchanged R10 `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient
at turbo charger compressor helper.

After the no-checksum stage save, open the BinToolz S50 switch-patch XDF and:

1. Verify all five `PUT setpoint` grids start in their as-patched 4000 hPa
   default state, have shape 8 × 12, and share the expected pre-R11 axis.
2. Verify the `PUT SP RPM Axis Header` still decodes to 12, then write and
   read back the approved shared `PUT SP RPM Axis`.
3. Tile each slot's 12-cell curve across all eight rows of its grid. This is
   deliberate because the patch grid's Y-axis remains uncharacterized; it
   ensures the cap applies regardless of its raw row selection while sitting
   above the untouched part-load base.
4. Read all five grids back in memory, ensure every row equals that slot's
   curve, and ensure no grid remains at the dangerous non-binding default.
5. Write TC flags in the established final save, with checksum correction once.

The report must describe the map migration semantically: slot 3 receives the
old slot-2 **target curve**, not a copied 4000 hPa default table.

## Implementation units

### U1. Create the R11 revision script and target guards

- **Files:** `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R11.py` (new).
- Copy R10's cumulative header, imports, patch pipeline, R06/R08/R10 helper
  reuse, output naming convention, and final fail-loud exit structure; add the
  R11 entry to its revision history.
- Add the approved configuration block and pure validation helper described in
  Technical design. Keep gauge psi display conversion separate from stored hPa
  values.
- Replace R09's base-reshape call and `R09_SLOT_CAP_UIDS` writer with
  R11-specific global-ceiling and five-slot writer helpers. Do not call an R09
  helper merely to overwrite its result, because that would create misleading
  report outcomes and unnecessarily couple R11 to an intermediate 26 psi base.
- Ensure every ECU calibration reference in report strings and comments uses
  both ID and plain-English description. Patch-added entries have no A2L ID, so
  refer to their table title plus their fixed XDF address where useful.

### U2. Produce a reviewable R11 report and curve visualization

- **Files:** `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R11.py` (new).
- Adapt R09's boost-curve PNG into an R11 plot containing the parked shared
  ceiling and all five effective slot targets. Label slot 1, intermediate slot
  2, high slot 3, and retained slots 4–5 distinctly; plot stored hPa-derived
  gauge psi for human review only.
- The report must include the shared and patch axes, a per-slot hPa/psi table,
  all five grid UIDs, confirmation that every grid is tiled across eight rows,
  expected/actual readback, checksum state, patch confinement, and existing TC
  state.
- Keep `compare_tables()` output scoped to actual R11 changes. The changing
  patch RPM axis cannot use an axis-mismatched table composite; the dedicated
  curve plot is the review artifact for it.

### U3. Add R11 lineage documentation

- **Files:** `Tunes/TuningBasicsGuide/REV_LOG.md`,
  `Tunes/TuningBasicsGuide/README_NEXT_STEPS.md`.
- Add the R11 row and a full rationale-heavy R11 section to `REV_LOG.md` only
  after a verified R11 generation. Record the final approved slot-2 curve and
  shared-axis values, the `min()` evidence, exact table/axis changes, readback,
  checksum proof, and full-flash-only note.
- Retire or replace the provisional R11 section in `README_NEXT_STEPS.md` once
  it is represented in `REV_LOG.md`; leave later ideas there rather than making
  the scratchpad a second change log.

### U4. Run offline verification and prepare the human review gate

- **Files:** generated `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_out/R11_<timestamp>/`
  artifacts only; no source-library files.
- Run the new script against the untouched stock bin. It must produce the
  timestamped bin, `report.md`, and R11 curve/comparison assets.
- Verify `CAL_CRC` and ECM3 are clean, switch-patch sanity resolves/decodes,
  and all ten inherited TC flags are still `1`.
- Compare R11 against the known R10 reference with both XDF views. Expected
  SC8S50 changes are the full-load cells of `IP_PUT_SP` — Pressure up throttle
  setpoint only; expected switch-patch changes are the **`PUT SP RPM Axis`**
  plus the five **`PUT setpoint`** grids. Any additional changed table, an
  `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor difference, a part-load shared-table change, or a changed TC flag
  is a hard stop.
- Independently inspect raw-byte ranges and account for all table/axis writes
  plus the corrected `CAL_CRC`; do not accept unexplained diffs.
- Conduct the human review of `report.md` and all curve assets. The script
  never flashes; any vehicle flash must be a full flash performed by Sam with
  the recovery image and charger available.

## Acceptance checks

| Requirement | Offline proof |
|---|---|
| Shared table is a non-binding ceiling | Full-load `IP_PUT_SP` — Pressure up throttle setpoint readback is flat at the approved hPa value; part-load rows are byte-identical to R10. |
| Five explicit slot caps | Each 8 × 12 grid reads back as eight identical rows of its approved curve, and every curve is below the shared ceiling. |
| Slot placement | Slot 1/4/5 match resampled R08; slot 3 matches resampled former R10 slot-2; slot 2 passes its approved plateau and separation predicates. |
| Axis safety | `PUT SP RPM Axis` readback equals the approved strictly increasing list; its header remains 12; every grid reports the same axis. |
| Scope control | XDF table compare and raw diff match the declared R11 table/axis set plus checksums only. |
| Flash readiness | Checksums clean, switch-patch sanity plausible, report and curve review complete; flashing remains a human full-flash action. |

## Risks and deferred work

- A flat 30 psi shared full-load row is safe only if every slot cap binds. The
  five-grid readback and no-default-cap guards are mandatory release gates.
- The unlabelled patch Y-axis remains unverified. Tiling all rows is the
  conservative R09-proven behavior, but its physical interpretation is deferred
  to a dedicated characterization task.
- The R10 26 psi request already carried narrow turbo-speed and HPFP headroom
  in R09 data (208/220 krpm and 97–98% effective volume). R11 relocates this
  request rather than increasing it; post-flash logs must still review turbo
  speed, rail pressure, lambda, knock, charge-pressure-ratio limiting, boost
  tracking, and P0234 margin before another tuning decision.
- No library tests are planned because this is a self-contained consumer
  revision. The script's assertions, dual-XDF comparison, raw-diff accounting,
  and visual artifacts are its proportional verification suite.
