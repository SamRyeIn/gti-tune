# R11 switch-patch PUT maps — requirements

**Date:** 2026-07-13  
**Status:** Brainstorm complete, ready for planning  
**Builds on:** R10 and `knowledge/sc8s50-switchpatch-xdf.md`

## Problem

R10 uses `IP_PUT_SP` — Pressure up throttle setpoint as the shared boost-target
curve, then uses the switch-patch **`PUT setpoint`** grids as per-slot ceilings.
That was the right mechanism for R09's two-map experiment, but it leaves the
coarse six-RPM-point shared table responsible for the target shape. R11 should
make the switch patch's denser grids the effective source of each map's boost
shape while retaining a safe, explicit cap for every selectable slot.

## Evidence and decision

R09 on-car logs prove the effective full-load target is:

```
min(`IP_PUT_SP` — Pressure up throttle setpoint, active-slot `PUT setpoint`)
```

Slot 1's `PUT setpoint` cap held its R08 curve while slot 2's default 4000 hPa
grid did not bind; the same R09 bin therefore logged two distinct WOT setpoint
ceilings. The switch-patch table is a ceiling, not an override, and it cannot
raise a target above `IP_PUT_SP` — Pressure up throttle setpoint.

The selected approach is therefore to park `IP_PUT_SP` — Pressure up throttle
setpoint at a non-binding 30 psi gauge-equivalent full-load ceiling, then encode
each intended WOT curve in the active slot's `PUT setpoint` grid. This is not a
30 psi delivery request: every selectable slot must have an explicit lower cap.

Alternatives considered:

- Keep R10's coarse shared curve and use slot caps only for map selection. This
  preserves the present arrangement but gives up the patch grid's shaping
  resolution.
- Treat the switch-patch table as an override. R09's slot-1/slot-2 data rules
  this out.
- Use a high shared ceiling plus explicit per-slot caps. This preserves the
  proven minimum semantics and gives each map the requested independent target
  curve. **Selected.**

## Goals and success criteria

1. The per-slot **`PUT setpoint`** grids, rather than the coarse shared table,
   define the full-load boost shape for all five selectable slots.
2. Slot 1 remains the current R08-style conservative map in slot 1.
3. The existing R10 slot-2 26 psi shelf map moves to slot 3.
4. Slot 2 becomes an intermediate map: it reaches the same peak target as
   slot 1, holds that target through 4400 rpm, then tapers toward redline with
   a shape resembling the current slot-2 map while remaining above slot 1.
5. No selectable slot can receive the parked 30 psi shared ceiling because of
   an omitted, non-binding, or incorrectly shaped per-slot cap.

## Scope

**In:**

- Set the full-load cells of `IP_PUT_SP` — Pressure up throttle setpoint to a flat,
  non-binding 30 psi gauge-equivalent ceiling (approximately 3085 hPa absolute
  using the lineage's 1016 hPa reference conversion). Preserve a safe,
  appropriate part-load treatment; this requirement does not authorize a
  blanket part-load boost increase.
- Use the switch-patch **`PUT setpoint`** grids (12 RPM × 8 load cells) as the
  full-load cap for slots 1–5. The grids are patch-added and have no A2L IDs.
- Re-breakpoint the shared patch **`PUT SP RPM Axis`** as needed to give useful
  resolution through the 3000–6500 rpm operating range. It is editable, but
  it is **one shared axis** for all five slot grids; only the five Z grids are
  independent.
- Write each intended WOT curve to all eight rows until the patch grid's
  unlabelled Y-axis quantity is characterized. This preserves R09's proven
  all-load-row cap behavior rather than assuming which row is full load.
- Keep slot 1's existing R08 target curve in slot 1. At its current reference
  points that is 24.4 / 24.4 / 21.5 / 19.3 / 18.6 / 17.2 psi at
  3000 / 3400 / 4400 / 5000 / 5750 / 6500 rpm.
- Move the *behavior* of the existing slot-2 map to slot 3. This means
  materializing the current R10/R09 slot-2 target in slot 3's `PUT setpoint`
  grid; it must not merely copy slot 2's current non-binding 4000 hPa default.
  The target to preserve is 24.4 / 26.0 / 26.0 / 24.6 / 21.8 / 17.8 psi at
  3000 / 3400 / 4400 / 5000 / 5750 / 6500 rpm.
- Create slot 2 as the intermediate curve described above. Slots 4 and 5
  retain their current R08-style caps unless a later decision explicitly gives
  them another role.
- Treat `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor, fuel, timing, wastegate feedforward, and traction-control settings
  as inherited R10 calibration: this brainstorm does not request changes to
  them.

**Out:**

- Flashing, on-car map-switching operation, and bypassing the human review
  gate.
- Any change to the untouched recovery image
  `Code/bin/5G0906259L__0002.bin`.
- New peak boost above either the parked shared ceiling or the current slot-3
  26 psi request.

## Key map flows

| Selected slot | R11 role | Required WOT behavior |
|---|---|---|
| 1 | Conservative | Retain the current R08-style curve. |
| 2 | Intermediate | Same peak as slot 1; flat through 4400 rpm; then taper above slot 1. |
| 3 | Existing high map | Receive the current R10/R09 slot-2 26 psi shelf curve. |
| 4–5 | Retained safety maps | Keep the current R08-style caps. |

## Acceptance examples

- **AE1 — cap architecture:** readback shows `IP_PUT_SP` — Pressure up throttle
  setpoint parked at the approved high full-load ceiling and every slot's
  `PUT setpoint` grid below it at WOT. The effective target is therefore the
  slot grid, not the shared table.
- **AE2 — map placement:** slot 1's WOT target equals its R10/R08 target; slot
  3 equals the previous R10 slot-2 target; slots 4–5 remain at the R08-style
  target.
- **AE3 — intermediate curve:** slot 2 has the same maximum requested boost as
  slot 1, is flat through 4400 rpm, and is strictly higher than slot 1 at every
  defined post-4400 full-load breakpoint.
- **AE4 — no unsafe fallback:** none of slots 1–5 retains the 4000 hPa default
  or another non-binding grid that could expose the parked shared ceiling.
- **AE5 — revision safety:** the generated bin changes only the intended
  `IP_PUT_SP` — Pressure up throttle setpoint / axis and switch-patch `PUT setpoint`
  / shared-axis data, passes checksum verification, and is visually reviewed
  before any human-performed full flash.

## Safety and validation constraints

R09 reached 208 of 220 krpm turbo speed and 97–98% HPFP effective volume on
the 26 psi shelf. R11 relocates that existing request rather than raising it,
but the high shared baseline means cap verification is a release gate, not a
convenience check. R10's `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient
at turbo charger compressor change also remains a watch item. Log review after
any human-performed full flash must explicitly check turbo speed, rail-pressure
hold, lambda, knock, charge-pressure-ratio limiting, boost tracking, and
top-end P0234 margin.

## Outstanding questions

- **Blocking for implementation:** choose the exact slot-2 post-4400 RPM
  breakpoints and values. The current slot-2 map falls 8.2 psi from 4400 to
  6500 rpm, whereas slot 2 must stay above slot 1 (which ends at 17.2 psi).
  “Similar slope” needs a concrete, smooth curve that satisfies both
  constraints at each new shared-axis breakpoint.
- **Blocking for implementation:** select the final 12-point shared `PUT SP
  RPM Axis`. Because it affects all slots, it must represent the R08 and
  current-26-psi curves without unwanted interpolation changes.
- **Deferred:** characterize the switch-patch `PUT setpoint` Y-axis. It is
  still an identity-scaled, unlabelled raw 0–7 axis; tiling all rows is the
  conservative current behavior.
- **Deferred:** confirm the exact absolute-pressure value to call “30 psi” for
  the revised baseline and document the ambient reference used. The setpoint
  is stored in hPa absolute, so the script must not write gauge psi directly.
