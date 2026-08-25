# R16 Spark IAT correction and high-RPM timing — requirements

**Date:** 2026-08-25
**Status:** Implemented; timing scope amended by explicit operator decision after the first unflashed build
**Builds on:** R15 and `knowledge/ecu-tuning-basics.md` § Spark IAT correction

## Problem

R15 does not hold the tuning guide author's exact Spark IAT correction even
though its SOP report describes an IAT row-map. The current calibration zeroes
the cold rows and installs the author's rows at 40.50, 50.25, 60.00, and
80.25 °C, but it retains the stock intake-air-temperature breakpoint axis and
the stock 70.50 °C row.

The author's calibration instead inserts a 35.25 °C breakpoint and removes the
70.50 °C breakpoint. R16 finishes that calibration exactly and matches the
same-car EQT Stage 2 log's base-table output from 5000 rpm upward.

## Evidence and decision

The authoritative source is the double-entry-verified table and linked source
screenshot in `knowledge/ecu-tuning-basics.md` § Spark IAT correction. The live
R15 bin confirms that `IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction
of Basic IGA versus N_32, TIA currently contains only the row-mapped partial
version.

The selected approach is a combined R16:

- Install the author's exact breakpoint axis and complete Basic IGA correction
  grid.
- Preserve the existing Reference IGA temperature-correction behavior as
  closely as the new shared breakpoint geometry permits.
- Match the EQT log's encoded `Ignition Table Output` curve at 5000, 5500, 6000,
  and 6500 rpm across the 1050, 1200, and 1400 mg/stk rows of all nine VVL-0
  port-flap-low Basic ignition-angle grids.
- Make no other base ignition-angle, boost, wastegate, fueling,
  knock-detection, or switch-slot changes.

The first unflashed R16 draft used the EQT log as directional evidence only.
Sam explicitly superseded that draft and directed R16 to copy the log's table
output, not its correction-dependent final timing. Stock knock detection remains
intact.

## Goals and success criteria

1. R16 reproduces the author's complete Spark IAT correction table, including
   its 35.25 °C breakpoint.
2. Timing is not added below 30 °C, and no timing is pulled through the
   35.25 °C row.
3. The correction begins between 35.25 and 40.50 °C and reaches the author's
   stated rows at 40.50, 50.25, 60.00, and 80.25 °C.
4. The shared-axis change does not silently reinterpret the Reference IGA
   correction as the Basic IGA correction.
5. R16 fits the EQT table-output trace from 5000–6336 rpm within one encoded
   0.375°CRK step RMS while keeping the nine maps mutually identical.
6. Every calibration behavior outside the IAT family and the twelve approved
   timing cells per cam grid remains identical to R15.

## Scope

**In:**

- `ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA versus
  N_32, TIA: intake-air-temperature axis shared by the Basic and Reference IGA
  correction grids.
- `IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
  N_32, TIA: exact values from `knowledge/ecu-tuning-basics.md` § Spark IAT
  correction.
- `IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of Reference IGA
  versus N_32, TIA: only the representation required by the shared-axis change.
  Its existing physical correction behavior must be preserved as closely as
  the new breakpoint geometry permits and compared explicitly before approval.
- The nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle,
  VVL 0 port-flap-low cam-position maps: set the 1050, 1200, and 1400 mg/stk
  rows to 1.875° at 5000 rpm, 3.750° at 5500 rpm, 6.000° at 6000 rpm, and
  8.250° at 6500 rpm.
- The R16 revision-lineage transition into `Tunes/MainTune/`, with the output
  bin named `Patched_259L_R16.bin` as already established in project guidance.

**Out:**

- Any attempt to copy EQT's knock-detection strategy or target its
  correction-dependent `Ignition Timing Final` channel.
- Any base-timing edit below 5000 rpm, at or below 900 mg/stk, or outside the
  twelve approved cells per cam grid.
- Any change to `IP_FAC_BPA_SP[0]` / `[1]` — Wastegate Position Feedforward,
  VVL 0 / VVL 1.
- Boost targets, slot assignments, lambda targets, fuel-system limits, torque
  limits, and knock-detection tables.
- Flashing the ECU or bypassing the human report and plot review gate.
- Any modification of `Code/bin/5G0906259L__0002.bin`.

## Acceptance examples

- **AE1 — exact axis:** final-bin readback of
  `ldpm_tia_iga_cor_sel` — Basis for temperature correction of IGA versus
  N_32, TIA contains -30.00, -20.25, -9.75, 0.00, 30.00, 35.25, 40.50,
  50.25, 60.00, and 80.25 °C in strictly increasing order.
- **AE2 — exact Basic grid:** final-bin readback of
  `IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
  N_32, TIA matches every value in the double-entry-verified author table within
  the calibration's encoding resolution.
- **AE3 — bounded warm-IAT effect:** at 35.25 °C the Basic correction is 0°CRK
  across the RPM axis; at 40.50 °C it matches the author's first negative row.
- **AE4 — Reference preservation:** a before/after physical-value comparison of
  `IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of Reference IGA
  versus N_32, TIA demonstrates that the shared-axis migration preserved its
  prior response as closely as the new breakpoints allow. Any unavoidable
  deviation is quantified for human review.
- **AE5 — revision isolation:** the byte-level audit against the verified R15
  bin attributes every changed byte to the shared IAT axis, the two affected
  IGA temperature-correction grids, the twelve approved cells in each of the
  nine base ignition grids, or stored checksums. Unexplained bytes are zero.
- **AE6 — absolute EQT targets:** final-bin readback shows 1.875 / 3.750 /
  6.000 / 8.250°CRK at 5000 / 5500 / 6000 / 6500 rpm respectively in the
  1050, 1200, and 1400 mg/stk rows of all nine
  `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
  port-flap-low cam-position maps.
- **AE7 — bounded cell scope:** no base-ignition cell below 5000 rpm or at/below
  900 mg/stk changes, and each of the nine maps changes exactly twelve cells.
- **AE8 — inherited calibration:** readback or table comparison confirms the
  R15 wastegate feedforward maps, boost-slot ladder, fueling, and
  knock-detection calibration are identical to R15.
- **AE9 — build gates:** checksums, final-bin readback, coherence checks,
  switch-patch sanity, and the byte-level audit all pass before the output is
  eligible for human review.

## Validation after the human-performed flash

R15 must be flashed, logged, and reviewed before R16 enters the car so the two
revisions remain attributable. R16 validation should include comparable
third-gear pulls with intake-air temperature recorded.

A pull that remains at or below 30 °C does not exercise the changed IAT region,
but a clean pull through 6000–6500 rpm does exercise the base-timing change. At
least one controlled pull should begin or operate in the 30–40.5 °C region
without deliberately creating unsafe heat soak, and at least one should reach
redline in gear. Review delivered timing, `Knock Cyl 1-4`, IAT, lambda,
rail-pressure hold, boost tracking, and turbo speed. Cylinder 1 remains the
known constraint.

## Deferred work

- Further timing increases require R16 validation logs; stock knock detection
  remains retained.
- The known 3500–4500 rpm timing gap is not an R16 target. That region combines
  higher EQT load and boost with this engine's known thin knock margin.

## Outstanding questions

- **Blocking for implementation:** none. The source table, scope, exclusions,
  and success criteria are decided.
- **Blocking before human flash:** complete the R15 flash, log, and review gate.
- **Deferred:** decide whether R17 continues high-RPM timing only after R16's
  knock, delivered-timing, and physics-derived power results are reviewed.
