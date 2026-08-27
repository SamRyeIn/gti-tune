---
date: 2026-08-27
type: backtest
revision: R10
profile: SC8S50
---

# R10 back-test — comparison

Bundle: `bundle.json` · Reply: `reply.json` · Replay: `replay.md`

## The reconstruction

| | |
|---|---|
| Session bin | `5G0906259L_0002_BasicsGuide_R09.bin` |
| Logs in the bundle | `Logs/BasicsGuide_R09` — 15 CSV, the largest case |
| Journal | empty |
| Sandbox audit | clean — no tool call named a path outside the sandbox |

Added beyond the plan's three cases, because R10's actual change was
torque-limiter driven and the battery *has* a `torque_limiter` check — making it
the one case whose motivating evidence should reach the bundle intact.

## What R10 actually did

Reshaped `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
compressor to 1.70 @ 1000 rpm and a flat 3.1 from 2000–7000 rpm, to clear the
code-128 torque-limiter cap that was trimming the R09 26 psi shelf.

## What Claude recommended

One record: `IP_PUT_SP` — Pressure up throttle setpoint, cells `[3,1]` and
`[3,2]` (3400 and 4400 rpm on the WOT row) set from 2809.0 to **2715.0 hPa**.
Risk **safety-relevant**, confidence **medium**, with a gradeable prediction.

## Replay

`{'queued': 1, 'dropped': 0, 'malformed': 0, 'total': 1}`. Journal unchanged.

## Buckets

| Bucket | Count | Entries |
|---------|-------|---------|
| Agrees  | 0     | — |
| Refused | 0     | — |
| Novel   | **1** | rec-1 |
| Wrong   | 0     | — |
| **Total** | **1** | |

## The result that matters: same constraint, opposite direction

Both Sam and the answering side identified `IP_PQ_CHA_MAX` — Maximum allowed
pressure quotient at turbo charger compressor as the binding constraint, and
both read it correctly: it holds a flat **2.80**, and the logged peak is
294.117 / 101.663 = **2.893**, over the ceiling.

They then went opposite ways.

| | Move | Premise |
|---|------|---------|
| **Sam (actual)** | raise the ceiling to 3.1 | 2.80 is factory conservatism; on an IS20 with an upgraded intercooler the hardware carries 3.1, and the ceiling was *trimming* the intended boost |
| **Claude** | lower the request to 2715 hPa | the calibration declares 2.80; achieved pressure exceeding a stated ceiling is the thing to correct |

Neither is a misreading. The difference is **what the ceiling is for**, and
nothing in the bundle settles it.

> [!important] The bundle carries no statement of the tuner's goal
> The prompt every case is answered under is *"I flashed this calibration and
> drove it; these are the logs from that session. What should the next revision
> change?"* — with no goal attached. Absent one, the answering side defaults to
> **bringing the car back inside its own declared limits**, which here is the
> exact inverse of the lineage's purpose.
>
> This is partly the rig's doing and should not be over-read. `backtest.py` uses
> a deliberately neutral prompt, because a per-revision prompt would be *"a
> prompt written knowing the answer."* In the real app the person types their
> own note, and "I want more midrange boost, the hardware is an IS20 with an
> upgraded intercooler" would plausibly produce different advice. What the case
> proves is that the **goal is load-bearing**, not that the answering side is
> wrong.

### Why it is Novel rather than Wrong

The recommendation is the conservative direction, it is evidenced, and its
supporting numbers are real: HPFP effective volume 98.1 %, DI rail sag −9.4 bar,
LPFP duty 87.7 %, turbo speed 208.06 krpm against `C_N_TCHA_MAX` — Maximum turbo
charger speed of 220.0 krpm (94.6 %), knock −3.0° at 4217 rpm in the same band.
Its own closing line is *"the whole car is running near several ceilings at once
on the highest pulls, which is the main reason the one change I do recommend
takes pressure out rather than putting it in."*

Accepting it would have cost power, not hardware. It does not belong in
**Wrong**, which is reserved for a change that would have passed the guards and
been a mistake.

## It found the torque limiter, and declined to act on it

The battery's top finding is a repeatable 6060–6442 rpm overshoot ridge (mean
+19.6, peak +24.6 kPa). The reply worked out that **nothing in the boost maps
owns it**: at the peak, PUT is 219.59 kPa, implying a setpoint near 195.0 kPa —
below base `IP_PUT_SP` (≈230 kPa interpolated at 6344 rpm) and below every patch
slot grid (≈222 kPa). It then named the cause:

> Something outside the boost maps is pulling the request down at the top of the
> pull — the torque-limiter finding shows source code 128 active for 385 samples
> with timing at −10.9 deg — and the turbo cannot dump pressure as fast as the
> request falls. Lowering a boost target that is already not the binding
> quantity would spend a flash and change nothing.

That is the same code-128 limiter R10 was written to clear, found independently
from the logs. The gap is not detection — it is the step from *"a limiter is
capping this"* to *"and here is the table that raises the limiter."* The
answering guide's own anti-pattern list warns against moving a limit you cannot
show is binding; here the limiter demonstrably **was** binding, and the guide
offers no matching rule for that case.

## Two other findings

**It detected that the session mixed map slots** — a data-quality problem the
battery never reported. Pulls 9 and 12 ran the base map (setpoint ≥ 280.59 kPa,
which no patch slot can supply); pulls 3, 6 and 7 must have run a lower
patch-shaped target, because pull 7's peak error of +18.32 kPa against a pull
maximum of 280.469 kPa would require an achieved 299.2 kPa if the base row had
been in force — above the pull's own maximum, so impossible. It scoped its edit
to the base map and asked for one slot per session next time.

**Three of four sessions converged on the same lambda cells; two declined.**
R10 wrote out the edit it *would* have made — `IP_LAMB_BAS[1]` at 3008 rpm,
rows 1100/1200/1389 mg/stk stepped from 1.00/0.98/0.95 to 0.975/0.955/0.925 —
and then refused it on three grounds: the three basic grids are numerically
identical so an edit is a one-in-three chance of hitting the live one; the lean
error is measured-versus-commanded and at 98.1 % HPFP the cause may be delivery;
and with no coverage it cannot say which airmass row was visited. R14 declined
the same signature for the same delivery reason. **R16 made almost exactly that
edit** (0.97/0.95/0.93/0.90 on the same column).

So the *analysis* is highly reproducible across blind sessions — same table,
same cells, near-identical values — while the *risk threshold* is not. That is
a much better-characterised variance than a bare bucket count would show, and it
is the finding stage 2 should be argued from.

## Verdict for the stage-2 gate

**1 Novel, 0 Wrong, 0 Refused.** The strongest single demonstration in the
back-test that the answering side reasons correctly about this calibration — and
the clearest evidence that the bundle must carry the tuner's goal, since without
one a sound analysis produced advice pointing away from the lineage's intent.
