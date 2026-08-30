# MainTune R19 log review

**Session:** 2026-08-30 10:26–10:36, 8 CSVs, cool air (16.5 °C ambient, 101.9 kPa)
**Review:** 2026-08-30
**Calibration named by every CSV:** `Patched_259L_R19.bin`
**Candidate used for calibration-aware checks:**
`Tunes/MainTune/MainTune_out/R19_20260830-074033/Patched_259L_R19.bin`
(SHA-256 `70d4da67…db2047f5`; all four R19 output folders hold this same byte-identical bin)
**Baseline:** the 2026-08-28 cool-air R18 session only (19.5 °C). The 2026-08-27
hot R18 session is not a matched-air control and is excluded from every comparison.

**Verdict: R19 did what it was built to do, on all five gate measurements, and
one of them came out better than predicted. Keep it. But the event rate rose
about 8× as the design predicted it might, and the residual 3rd-gear boost
shortfall is now shown to be sweep-rate lag rather than a feedforward deficit —
so the obvious next move (more feedforward) is the wrong one.**

> [!warning] This revision was flashed with its review gate open
> `Tunes/REV_LOG.md` § R19 records that the human review gate **did not pass**,
> because `Tunes/MainTune/tune_code_review.md` P1 was open against the
> intake-axis re-breakpoint. The R18 review also closed with "do not follow it
> with a knock-protection revision." R19 was flashed and driven anyway. Nothing
> in this session came out dangerous, and the findings below partly answer P1 —
> but the gate was bypassed, and that is a process fact worth recording, not a
> retroactive approval.

---

## Provenance and data quality

Every CSV uses `Gear (gear)`, so the logged gear is the actual gear and no offset
was applied. As in R17 and R18, the folder carries no human-dropped flashed-bin
text record, so the CSVs prove the filename but cannot independently prove the
flashed file's SHA-256.

The deterministic battery parsed **8 files / 8 pulls** with the calibration
resolved and **no checks skipped**. Re-run it with:

```
Code/.venv/bin/python -m simoscal.analysis Logs/BasicsGuide_R19 \
  --bin Tunes/MainTune/MainTune_out/R19_20260830-074033/Patched_259L_R19.bin \
  --xdf Code/xdf/SC8S50.V1.0.xdf
```

Both `--bin` and `--xdf` are required; without them the two boost checks and all
five coverage maps skip.

Cross-revision work is in `analyze_r19_validation.py` (gate measurements 1–5,
power, `plots/r19_vs_r18.png`) and `probe_r19.py` (tip-in, knock simultaneity,
base-timing identity, lambda, `plots/r19_tip_in.png`). Both import their shared
physics and helpers from `../BasicsGuide_R18/analyze_r18_validation.py`.

Six pulls were 3rd gear; **two pulls (10:28:58 and 10:34:08) held WOT through the
upshift into 4th**, which is what the R19 gate asked for and what R18 never
supplied — R18's cool session had only 4 and 2 samples in the 5000–5500 and
5500–6000 bands in 4th, against 125 and 150 here. Every 4th-gear number below is
new information.

---

## The check R19 had to pass first: base timing untouched

**Bin-level, not inferred.** All **51** `IP_IGA_BAS_*` — Basic ignition angle
tables are byte-for-byte identical between the R18 and R19 candidates. The only
tables that differ are the three R19 declared:

| Table                                                            | Max change |
|-------------------------------------------------------------------|------------|
| `IP_IGA_DEC_KNK` — Spark retard at recognised knocking             | 1.500 °CRK |
| `IP_IGA_INC_KNK` — Spark advance step during knock recovery        | 0.375 °CRK |
| `IP_DLY_INC_FAST_KNK` — Delay before the fast knock-recovery step  | 12.0       |
| `IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure actuator setpoint | 0.13104 |

R19 did **not** stack a timing change onto a knock change. The `Ign Table`
channel does show up to +0.34° of drift on a matched rpm × airmass grid, but
that is within-cell operating-point distribution (cam phasing, interpolation),
not a table difference — the bin comparison is the authority and it is clean.

---

## Gate measurement 1 — recovery carry: **large improvement**

| | R18 cool | R19 |
|---|---|---|
| Median onset → zero retard | 3.88 s | **0.86 s** |
| Longest carry | 3.88 s | 0.96 s |
| Events still spanning an upshift | 0 of 1 | 1 of 10 |
| Events never recovering inside the pull | 0 | 0 |

The carry is **4.5× shorter** and every single event recovers to zero inside the
same pull. The one event that still spans an upshift is at 6158 rpm, 0.80 s from
onset to zero — it crosses the shift because the shift arrives, not because the
cut is holding. R18's single event held −3.00° for nearly four seconds; nothing
in R19 comes close to that. This is the clearest success of the revision.

Evidence: `plots/r19_vs_r18.png`, top-right panel.

## Gate measurement 2 — cut depth: **exactly as designed**

Every one of the ten R19 events bottoms at **−1.50 °CRK**. Not one goes deeper.
R18's event was −3.00. The intended halving landed precisely, with no
accumulation past a single step and no approach to the untouched
`IP_IGA_MAX_KNK` — Maximum knock retard floor.

Evidence: `plots/r19_vs_r18.png`, top-left panel — two flat lines, one per revision.

## Gate measurement 3 — event rate and character: **rate up ~8×, character intact**

| | R18 cool | R19 |
|---|---|---|
| Loaded events | 1 | 10 |
| Loaded WOT time | 55.2 s | 69.6 s |
| Events per loaded minute | 1.09 | **8.63** |
| Ramping (retard deepening after onset) | 0 | **0** |
| Unrecovered | 0 | **0** |
| Multi-cylinder clusters | 0 | 2 (4 events) |

The rate rise is the predicted cost and it is at the high end of what the gate
called readable. The character checks are the ones that matter, and they hold:
**no event ramps, none accumulates, none fails to recover, and no event exceeds
one −1.50° step.** That is a knock loop tapping the boundary and stepping back,
which is what a shallower, faster-recovering response is supposed to look like.

The two multi-cylinder clusters need naming rather than waving away. Both are at
tip-in (3025→3114 rpm, cylinders 4 then 1, 0.08 s apart; and 3112→3149 rpm,
cylinders 2 then 1, 0.04 s apart). They are **sequential, not simultaneous** —
one cylinder then its neighbour a combustion event or two later, which is
knock propagating through the firing order, not the broadband
all-cylinders-at-once signature the stop-signal list names. R18's zero
multi-cylinder count is over a single event, so it is not a baseline that can
carry weight.

**The new low-rpm cluster is genuinely new and is not yet explained.** R18's cool
session had nothing below 4827 rpm; R19 has four events at 3025–3149 rpm. Three
candidate mechanisms, tested:

- *Tip-in boost overshoot* — **not supported.** Peak tip-in overshoot did rise
  (mean +5.7 → +9.2 kPa, worst +10.3 → +11.5), but `plots/r19_tip_in.png` shows
  all four onsets sit at **−5 to −10 kPa PUT error, still spooling**, upstream of
  where the overshoot peak occurs at 3150–3300 rpm. The overshoot arrives after
  the knock, not before it.
- *The wastegate feedforward reaching down into the tip-in region* — **not
  supported.** At matched intake × exhaust flow-factor cells the feedforward is
  unmoved there (+0.73 and −0.35 points at intake FF 0.2–0.6). See the
  measurement-4 table.
- *More load arriving earlier* — **partly supported but confounded.** At
  3000–3200 rpm R19 carries 1283 vs 1195 mg/stk mean airmass, 241.8 vs 227.7 kPa
  PUT, and 390 vs 366 Nm. But R19's IAT there is 3.7 °C cooler and the flow-factor
  distributions differ, so this is as consistent with a harder, cleaner tip-in by
  the driver as with anything in the calibration.

With four events across two of eight pulls, the honest read is **a watch item
with a specific next test**, not a finding. It is not a stop signal: depth is one
step, recovery is under a second, and cylinders go sequentially.

## Gate measurement 4 — boost tracking at 5000–6000 rpm: **the command reaches the flap**

This was the outcome the revision was designed to distinguish, and it is settled.

3rd gear, pooled per band, R18 cool → R19:

| Band      | PUT err        | Δ     | WG I         | Δ     | WG Pos Base  | Δ     |
|-----------|----------------|-------|--------------|-------|--------------|-------|
| 3500–4000 | −0.9 → +0.1    | +1.0  | +1.0 → +0.7  | −0.3  | 68.4 → 68.7  | +0.3  |
| 4000–4500 | −3.3 → −2.4    | +0.9  | +2.3 → +1.4  | −1.0  | 62.5 → 62.4  | −0.1  |
| 4500–5000 | −5.4 → −5.9    | −0.4  | +4.9 → +4.2  | −0.7  | 55.4 → 56.5  | +1.1  |
| 5000–5500 | −7.8 → −5.1    | **+2.8** | +9.6 → +7.9  | −1.6  | 52.7 → 58.0  | **+5.3** |
| 5500–6000 | −4.9 → −3.4    | **+1.5** | +13.0 → +11.6 | −1.4  | 52.7 → 58.3  | **+5.6** |
| 6000–6500 | +1.5 → +0.7    | −0.7  | +14.8 → +12.7 | −2.1  | 56.7 → 56.6  | −0.1  |

The gate's failure mode — "PUT error and integral both stay put, the command is
not reaching the flap" — **did not happen.** The feedforward gained 5.3–5.6
position points exactly where it was aimed, the integral gave back 1.4–1.6
points, and PUT error improved 2.8 and 1.5 kPa. The remaining shortfall is
calibration-addressable, not mechanical.

Two caveats on the size of it. The feedforward gained **5.3–5.6 points against an
intended ~2.5** — more than twice the design intent — and it bought only 1.5–2.8
of the predicted 3.5 kPa per band. So the map moved harder than expected and the
boost responded softer than expected. Both errors are in the replay model, not
in the car.

**The re-breakpoint is confirmed clean over everything this session visited.** At
matched flow-factor cells across all 7,275 logged rows, the only cells that moved
are the intended ones:

| Intake FF | Exh FF  | n18 | n19 | Base R18 | Base R19 | Δ |
|-----------|---------|-----|-----|----------|----------|-------|
| 1.1–1.2   | 1.4–1.6 | 367 | 540 | 52.70    | 58.46    | **+5.75** |
| 1.1–1.2   | 1.2–1.4 |  62 | 148 | 52.77    | 57.98    | **+5.21** |
| 1.0–1.1   | 1.4–1.6 |  58 |  51 | 53.68    | 55.21    | +1.53 |
| 1.0–1.1   | 1.2–1.4 | 189 | 252 | 54.93    | 55.92    | +0.98 |
| every other cell with ≥20 samples in both | | | | | | **≤ ±0.85** |

That is a direct in-car answer to part of code-review P1: over the states this
session actually visited, the axis move is a no-op outside the target region plus
a ~1-point skirt. **It does not close P1.** P1's cited counterexample is a
6557 rpm, 53%-pedal lift at intake FF 1.515, and R19's session contains no such
sample — its six high-intake-FF rows are all 4400–4625 rpm upshift lifts, and in
five of the six the final command is 0.00% (the base value is not consumed at
all). P1 is **untested here, not disproven.**

## Gate measurement 5 — redline over-delivery: **went the other way**

| | R18 cool | R19 | Predicted R19 |
|---|---|---|---|
| PUT error, 3rd gear, 6200–6500 rpm | +3.76 kPa | **+0.63 kPa** | ≈ +2.4 kPa |
| WG Pos Base there | 59.11% | 57.60% | — |
| WG I there | +14.60% | +12.89% | — |

Over-delivery did not grow to +2.4 — it **fell to +0.63**, and the R18 baseline
was +3.76, not the +1.7 the prediction started from. The gate said "anything
materially beyond +2.4 means the re-breakpoint behaved differently in the car
than in the replay." It came in below, not beyond, so there is no safety concern
here — but the replay's redline prediction was wrong in both its baseline and its
direction, which is the same modelling gap that showed up in measurement 4. Treat
the replay as a sanity check on sign and blast radius, not as a quantitative
predictor. (n=42 R19 samples vs 100 R18; R19's IAT is 2.7 °C cooler.)

---

## Findings the R19 gate did not ask for

### High — the residual 3rd-gear shortfall is sweep-rate lag, not missing feedforward

The two 4th-gear pulls make this separable for the first time. At 5000–6000 rpm:

| Gear | Median rpm sweep | Mean PUT error | Mean WG I |
|------|------------------|----------------|-----------|
| 3    | 500 rpm/s        | −4.20 kPa      | ≈ +9.8%   |
| 4    | 188 rpm/s        | **−0.38 kPa**  | ≈ +13.2%  |

Same calibration, same rpm, same air. 2.7× the sweep rate costs 3.8 kPa. In 4th
the loop has time to wind the integral in and lands on setpoint; in 3rd it does
not. **Adding more feedforward to close the 3rd-gear gap would over-boost 4th
gear, where the error is already zero.** The steady-state deficit is real and
still worth about 13 points of integral — that is a feedforward problem — but the
*3rd-gear-specific* extra is a dynamics problem and needs a different lever
(integral gain or ramp-rate, not the position map).

This reframes the R19 → R20 idea queue. Note it in `Tunes/README_NEXT_STEPS.md`
before the next revision is written.

### Medium — the analysis battery's High lambda finding is the upshift fuel cut

The battery flags "settled-WOT lambda runs lean by +0.068." Every lean sample
above +0.05 in every pull is λ = 2.000 (sensor rail) against a setpoint that
flips to 0.800, at 4600–4800 rpm, in gear 4 — the DSG upshift fuel cut. **The
R18 cool session shows the identical artifact in 4 of its 8 pulls** (λ = 2.000,
SP 0.800, 4543–4764 rpm, gear 4). Excluding those samples, R19's settled loaded
lambda error is +0.001 to +0.016 across all eight pulls. Not a fuelling problem,
and not a change from R18.

### Low — everything else is unchanged or better

- **Knock retard, battery view:** clean, worst 0.0° inside the battery's own
  loaded-WOT window (the ten events sit outside its airmass/TPS gate).
- **Fuel:** worst DI rail sag −9.5 bar, LPFP peak 79.0%, HPFP effective volume
  peak 98.5%. HPFP at 98.5% is the tightest number in the session and is worth
  keeping an eye on, but it is not new.
- **Heat and turbo:** turbo peak 204 krpm (limit watch 220), IAT peak 33 °C,
  coolant 102 °C, oil 113 °C. Cool session, comfortable margins.
- **Ceilings:** peak demanded manifold setpoint 310.0 kPa against
  `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold pressure setpoint;
  logged PUT-minus-ambient peaks 1886 hPa against the 2700 hPa
  `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold, so
  814 hPa of P0234 margin.
- **No torque-limiter activity, no misfires.**

### Power

3rd-gear F=ma wheel estimates, trimmed to each pull's own gear:

| | R18 cool | R19 |
|---|---|---|
| Mean | 251 hp | **256 hp** |
| Range | 243–259 hp | 252–259 hp |
| Pulls | 8 | 6 |

About +5 hp and, more usefully, a much tighter spread — R18's 16 hp band
collapses to 7 hp. Some of that is the 2.6 °C cooler air. R19 is not a power
revision and this is consistent with "no power lost, boost slightly better held."

---

## What to do next

1. **Record the gate bypass.** Update `Tunes/REV_LOG.md` § R19 so the lineage
   shows R19 was flashed and logged with the review gate open, pointing here.
2. **Close or retire code-review P1 with data.** It needs one log this session
   cannot provide: a deliberate part-throttle / lift sweep that visits intake
   flow factor 1.4–1.6 at 5500–6600 rpm with a *nonzero* `WG Pos Final`. Ten
   seconds of rolling part-throttle at high rpm would do it.
3. **Do not add wastegate feedforward for the 3rd-gear gap.** See the High
   finding. If the 5000–6000 rpm shortfall is worth another pass, the lever is
   the closed-loop dynamics, and the 4th-gear data is the control that proves
   whether a change helped or just over-boosted the slow case.
4. **Watch the low-rpm knock cluster on the next session.** If 3000–3200 rpm
   events repeat at the same rate in a third cool session, they are real and
   deserve their own investigation; if they do not, they were this session.
5. **Keep the per-cylinder knock-sensor channels in the logging list**, and drop
   a `*.bin.txt` record of the flashed file into the log folder — three
   revisions running, the folder cannot prove what was flashed beyond a filename.

R19 is **validated on its own terms and worth keeping.** It remains
**revision 19 — a starting point, not a finished calibration.**

---

## Addendum (2026-08-30) — which base ignition map the ECU is actually on at WOT

Asked for by the R20 plan, whose per-slot `Spark modifier` guard caps
**delivered** timing (base + modifier) and so needs the operative base map. Run
`find_operative_ign_map.py` in this folder to reproduce everything below.

**Answer: `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle map,
low port-flap position, standard valve lift** (`ignition_base_vvl0_i*_e*` in the
`SC8S50` profile; `[0][0]` is uniqueid `0x426ec`). The cam-node index does not
matter — see below.

Three of the four family axes are settled without fitting anything:

| Axis            | How it is settled                     | WOT value                       |
|-----------------|---------------------------------------|---------------------------------|
| Port flap H/L   | `Port Flap Pos (%)` logged channel    | **0.00%** in 1795 of 1795 → `PORT_L` |
| Valve lift      | `Valve Lift Pos ()` logged channel    | **0** in 1733 of 1795 (96.5%) → `STND` |
| Cam nodes `[i][e]` | direct comparison of the nine grids | **all nine byte-identical**     |

The cam-node result is the useful one. The ECU interpolates *between* the nine
cam-phasing maps rather than selecting one, so the honest answer could have been
a blend of several — but on this bin all nine are the same grid, so intake and
exhaust cam position cannot change delivered base timing at all. The guard needs
no cam state.

**The fit confirms it.** Simulating the ECU's bilinear lookup on that map at
each WOT sample's (rpm, airmass) reproduces the logged `Ign Table` channel to
**mean −0.007°, rms 0.184°, p95 |error| 0.186°** over 1733 standard-lift
samples. By rpm band above 1150 mg/stk the agreement is within 0.01° almost
everywhere:

| rpm band  | n   | logged | map lookup | diff   |
|-----------|-----|--------|------------|--------|
| 2900–3200 | 33  | −6.73  | −6.97      | +0.246 |
| 3400–3700 | 89  | −6.48  | −6.49      | +0.012 |
| 3900–4200 | 104 | −4.49  | −4.48      | −0.009 |
| 4400–4700 | 236 | −3.57  | −3.57      | +0.001 |
| 4900–5200 | 183 | −1.90  | −1.91      | +0.006 |
| 5400–5700 | 201 | +0.80  | +0.80      | −0.001 |
| 5900–6200 | 206 | +2.01  | +2.01      | +0.008 |
| 6300–6700 | 33  | +3.17  | +3.10      | +0.066 |

The 62 `LFT_1` samples are the control: scored against the same `STND` map they
miss by **−3.05° mean, 3.50° rms**. A wrong map in this family does not fit, so
the standard-lift agreement is not an artifact of a flat map or a loose metric.

Two consequences for R20:

- The map's **1400 mg/stk row reads −7.50, −6.75, −4.50, −3.75, −2.25, +0.75,
  +1.88, +3.38 °CRK across 3000–6500 rpm**, which is exactly the slot-4
  delivered row the R20 brainstorm and plan assumed. That assumption is now
  measured rather than carried.
- `Ign Table` is the **base-table output**, not final commanded timing — that is
  why it matches a pure table lookup with no knock or temperature term. It stays
  the right channel for confirming a `Spark modifier` offset landed.
