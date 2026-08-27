---
date: 2026-08-27
type: backtest
revision: R15
profile: SC8S50
---

# R15 back-test — comparison

Bundle: `bundle.json` · Reply: `reply.json` · Replay: `replay.md`

## The reconstruction

| | |
|---|---|
| Session bin | `CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin` |
| Logs in the bundle | `Logs/BasicsGuide_R14` — 8 CSV, 5 detected pulls |
| Journal | empty |
| Sandbox audit | clean — no tool call named a path outside the sandbox |

No caveat: this is the cleanest of the three cases. The logs were recorded on
exactly the bin the session opens, and the revision that followed was a
log-driven calibration change.

## What R15 actually did

Walked back five cells of `IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure
actuator setpoint (wastegate position feedforward, VVL 0 / VVL 1) toward their
R07 values, every cell bounded at its R07 level, to close the measured
4000–4500 rpm boost shortfall the wastegate integral was carrying.

## What Claude recommended

**Nothing.** `recommendations: []`, with a 7,023-character `summary`.

## Buckets

| Bucket | Count | Entries |
|---------|-------|---------|
| Agrees  | 0     | — |
| Refused | 0     | — |
| Novel   | 0     | — |
| Wrong   | 0     | — |
| **Total recommendations** | **0** | |

Replay counts: `{'queued': 0, 'dropped': 0, 'malformed': 0, 'total': 0}`.
Journal unchanged at 0 entries.

## Reading the null result — this is the case that diagnoses the courier

R15 is the case built to be winnable: a real log-driven calibration change, with
the logs that motivated it in the bundle. It came back empty, and the reason is
specific and fixable.

### The answerer found the right table and could not size it

From the reply, unprompted:

> The table that owns that behaviour is `IP_FAC_BPA_SP[1]` — Map for boost
> pressure actuator setpoint, VVL 1 (wastegate position feedforward), but its
> axes are exhaust flow factor × intake flow factor and neither channel appears
> anywhere in this bundle, so I cannot show which cells were visited or size a
> trim from evidence rather than from feel.

That is **the exact table Sam edited**, named from the log behaviour, and set
down for a stated reason: the bundle carries no channel on either of that
table's two axes, so `coverage` cannot say which cells the car visited. The
answering guide requires evidence pointing at something in the bundle, and there
was none to point at. The refusal follows from the guide correctly.

### But the shortfall itself was never in the bundle at all

This is the deeper problem, and it is not the answerer's.

`simoscal.analysis`'s `boost` check is **overshoot-only**. `_overshoot_zones`
reports contiguous regions where PUT exceeds setpoint; there is no undershoot,
shortfall or deficit check anywhere in the battery — `grep -rn
"undershoot\|shortfall\|deficit"` over `Code/simoscal/analysis/` returns
nothing. So the 4000–4500 rpm boost shortfall that motivated the whole of R15
**is not a finding in the bundle**, and the answerer had no way to see it as
anything other than the absence of a problem.

The raw signature was present and unreported: the `wastegate` check's own
evidence carries `max_wg_final_pct: 99.9985` — the gate driven fully closed —
and that check's docstring already knows what that means (*"WG hit 100% only
while under setpoint during spool"*). The number reaches the bundle. The finding
does not.

> [!important] The single highest-value fix this back-test found
> Add a boost-shortfall check to the battery. Until one exists, the courier
> cannot reproduce a change of R15's kind, no matter how good the answering
> side is — the evidence is filtered out one layer upstream of the model.

### Everything else it said was defensible

- **Knock**: a single −3.0° event at 5545 rpm in pull 4 only, `recurrence_pulls`
  empty, on the hottest and fourth-consecutive pull (coolant 100.2 °C vs 96.2
  and 90.9). Called heat soak, declined to act, asked for a cooled-down repeat.
- **Fuel as the binding constraint**: HPFP effective volume peaked 97.7 %, and
  it computed that moving `IP_LAMB_BAS[1]` — Basic lambda setpoint grid from
  0.800 to 0.75 needs ≈7 % more fuel, i.e. ≈104 % of what the pump delivered.
  It then used that to argue against adding boost in the next revision — *"there
  is no fuel behind it."* That is a correct and non-obvious cross-domain
  inference.
- **Lambda floors**: noticed `IP_LAMB_TUR_OHP_MIN` — Minimum lambda for turbo
  charger overheating prevention at 0.7998 and `C_LAMB_BAS_COR_MIN` — Minimal
  value for lambda setpoint at 0.79999 are leaner than the 0.72–0.75 the brief
  gives as stock, flagged that they must come down in the same revision that
  ever richens `IP_LAMB_BAS[1]` or the enrichment gets clipped — and declined to
  move them alone because they do not currently bind. Correct on all three
  counts.

## Verdict for the stage-2 gate

Contributes **no bucket evidence**, and identifies why: a missing battery check,
not a missing model capability. The answerer reached the right table by the
right reasoning and stopped one step short of the edit for a reason the bundle
made unanswerable.
