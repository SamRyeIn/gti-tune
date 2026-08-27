---
date: 2026-08-27
type: backtest
revision: R16
profile: SC8S50
---

# R16 back-test — comparison

Bundle: `bundle.json` · Reply: `reply.json` · Replay: `replay.md`

## The reconstruction

| | |
|---|---|
| Session bin | `CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R15.bin` |
| Logs in the bundle | `Logs/BasicsGuide_R15` — 7 CSV, 6 detected pulls |
| Journal | empty |
| Sandbox audit | clean — no tool call named a path outside the sandbox |

> [!warning] Caveat carried from the case definition
> R16 was never flashed — R17 superseded it as a candidate, removing the EQT
> high-rpm advance this case grades against. So `actual` is what the next
> revision was *authored* to be, not what the car ran, and the timing half of it
> was later judged wrong by Sam himself. A recommendation that declines to add
> high-rpm advance is not automatically in the **Wrong** bucket.

## What R16 actually did

First MainTune revision. Laid in the exact guide-author Spark IAT axis/grid,
migrated the Reference IGA correction onto the shared axis without changing its
curve, and wrote the EQT Stage 2 log's 5000-rpm-up `Ignition Table Output` curve
across the 1050/1200/1400 mg/stk rows of all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low maps.

## What Claude recommended

**Three records, all lambda.** The first non-empty reply of the back-test.

| ID | Table | Change |
|----|-------|--------|
| rec-1 | `IP_LAMB_BAS[1]` — Basic lambda setpoint grid | cells `[4,3] [5,3] [6,3] [7,3]` → `0.97, 0.95, 0.93, 0.90` |
| rec-2 | `IP_LAMB_BAS_HPDI[1]` — Basic HPDI lambda setpoint grid (direct injection) | same cells, same values |
| rec-3 | `IP_LAMB_BAS_MPI[1]` — Basic MPI lambda setpoint grid (port injection) | same cells, same values |

All three routed via the generic `edit` op, risk **safety-relevant**, confidence
**medium**, each carrying a gradeable prediction.

## Replay

`{'queued': 3, 'dropped': 0, 'malformed': 0, 'total': 3}` — every record passed
the guards. Journal unchanged at 0 entries. Quantization was negligible:
max |error| 2.93 × 10⁻⁵ lambda on rec-1, 3.91 × 10⁻⁴ on rec-2 and rec-3.

> [!note] This case also found a bug in the rig
> `replay` crashed on `_preview_lines` — `head()` formatted a 2D table's preview
> rows as scalars and raised `TypeError: unsupported format string passed to
> tuple.__format__`. R14 and R15 never reached it because they queued nothing.
> Fixed by flattening nested rows before the head.

## Buckets

| Bucket | Count | Entries |
|---------|-------|---------|
| Agrees  | 0     | — |
| Refused | 0     | — |
| Novel   | **3** | rec-1, rec-2, rec-3 |
| Wrong   | 0     | — |
| **Total** | **3** | |

### Why Novel and not Wrong

The direction and the sizing both hold up:

- **Nothing becomes richer than this calibration already runs at the same
  airmass.** Each cell takes its own row's existing value at the *next* rpm
  breakpoint (3488 rpm), which is the answering guide's best-bounded sizing
  method: the destination is a value the car has already run.
- **The 0.80 floor does not clip it.** The new values are 0.90–0.97, well above
  `C_LAMB_BAS_COR_MIN` — Minimal value for lambda setpoint at 0.79999. The reply
  checked this explicitly and noted the floor would have to come down first for
  any future enrichment past 0.80 — the same trap the R15 session identified.
- **Fuel headroom was checked, not assumed.** HPFP effective volume peaked
  95.29 %; it computed the implied demand at the new targets as ≈91 % and said
  outright that the change is *"sized to stay inside demand the car has already
  met rather than sized to the full gap."*
- Enriching is the thermally conservative direction, and the evidence is a real
  Medium finding (+0.0415 settled-WOT lean at 3076 rpm, above the +0.03 watch
  line).

### The reservation worth recording

The **R14 session saw the same signature and declined it.** There it was +0.049
lean at 3081 rpm, and that reply argued it was probably *delivery* rather than
setpoint — that enriching the setpoint grid to chase a delivery shortfall would
be *"recommending against the symptom's table rather than the cause's,"* the
anti-pattern the guide names by name. Here, at 95.29 % HPFP, the same
delivery-versus-setpoint question is live and is answered the other way.

Both readings are defensible and the R16 one does more work to justify itself.
But two blind sessions reaching opposite conclusions from the same signature is
a **reproducibility** finding, not a correctness one, and it belongs in the
stage-2 decision.

## What it declined, and one gap that matters

It left timing alone — the half of R16 that R17 later removed — for a reason
that names a real bundle gap:

> Pulling timing on one non-recurring event over-reacts to a single sample, and
> I cannot tell from the bundle which of the nine cam-position ignition tables
> was active at that point.

The lineage's own answer to that is *edit all nine* — which is exactly what R16
did. The bundle offers no way to learn that, and the answering guide does not
say it. This is the same class of gap as the switch-patch slot (which it again
had to reconstruct numerically, identifying slot 4 by matching peak PUT minus
overshoot to 2809.0 hPa and ruling out slots 1, 2, 3 and 5 by name).

It also flagged what it called *"the real risk in the file"* — turbo speed at
213.47 krpm against `C_N_TCHA_MAX_SP` — Maximum turbo charger speed setpoint of
220.00 krpm, i.e. 97 % — and declined to act because the `turbo_heat` finding
carries no `pull_refs` and no rpm, so it could not say which cells to trim. It
specifically refused to lower the protection setpoint, on the grounds that this
*"would cut boost through the protection path rather than through the target."*
That is correct and is exactly the reasoning `C_PRS_IM_SP_LIM`'s history in this
repo says is easy to get wrong.

## Verdict for the stage-2 gate

The first case to produce bucket evidence: **3 Novel, 0 Wrong, 0 Refused**. All
three passed the guards, all three carried gradeable predictions (G6), and the
change is bounded by values the calibration already runs. It also confirms the
answering side is capable of a sized, defensible edit when the bundle happens to
carry evidence it can act on — which strengthens rather than weakens the reading
that R14 and R15's empty replies were about the bundle, not the model.
