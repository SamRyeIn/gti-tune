---
source: References/20250816_Pacific_Track_Log6.csv
date: 2026-07-06
key_people: none
key_concepts: on-track EQT S2 log, boost deviation with actuator saturated, P2563 root cause, turbo/exhaust heat-soak vs charge-air (IAT), sustained target-vs-capability gap, mild cyl-1 knock, oil/EGT thermal limits
---

# EQT Stage 2 91 — On-Track Log & P2563 Root Cause

Companion to the clean-street [[eqt-s2-baseline-log-review]]. Same tune (`EQT - Stage 2 91 v2.52 - LC TC`, IS20, DSG), but a **full track session at Pacific Raceways** — the harsh duty cycle that actually surfaces the problems. This is the "fault-present" counterpart to the baseline's "fault-free" pull, and it **changes the leading P2563 hypothesis**. Feeds [[diy-conservative-track-tune]].

## The log

`20250816_Pacific_Track_Log6.csv` — 14000 samples, ~80 Hz, **0–415 s** (~7 min continuous session with multiple WOT stretches, up/downshifts, braking zones). Ambient ~68 °F, baro ~14–15 psi (near sea level).

## Headline finding — the [[P2563]] mechanism, caught live

Start at **t = 239 s** as flagged. Around it (and across most of the session's WOT stretches) the pattern is unmistakable:

> **The turbine actuator sits pinned at 100% (wastegate fully commanded shut, i.e. "give me everything") while actual boost stays 2–3 psi BELOW target for seconds at a time.** The ECU is asking for boost the IS20 cannot deliver, and it knows it — the actuator has no authority left.

Representative slice around t=239 (4th gear, WOT, `Turbine Act. Final = 100%` throughout):

| t (s) | rpm | Boost | Target | Δ | Actuator Final |
|---|---|---|---|---|---|
| 239.10 | 4512 | 17.0 | 27.3 | **−10.3** | 100 |
| 239.42 | 4288 | 21.4 | 27.4 | **−6.0** | 100 |
| 239.90 | 4416 | 25.1 | 27.4 | **−2.3** | 99 |
| 240.50 | 4576 | 25.0 | 27.1 | **−2.1** | 100 |
| 241.10 | 4736 | 24.4 | 26.4 | **−2.0** | 100 |
| 242.50 | 5024 | 22.7 | 25.0 | **−2.3** | 100 |

(The t≈239.0 upshift also shows ignition yanked to **−13 to −15°** — that's the **DSG 3→4 torque-cut intervention**, `Knock Retard = 0`, not knock. Don't confuse it with a knock event.)

**Across the whole session:** ~**40 s of cumulative WOT time** where boost was already built (>18 psi), the actuator was pinned ≥99%, and actual boost still fell **>1.5 psi short of target** (avg **−3.1 psi**, worst genuine sustained **−9.3 psi**). That much time spent with commanded-vs-achieved boost deviating past threshold is exactly what sets **[[P2563]]** ("Turbo Boost Control Position — Range/Performance") → EPC light. The log captures the condition even if it doesn't record the DTC itself.

## Revision to the earlier hypothesis (important)

The baseline note guessed P2563 came mainly from **charge-air (IAT) heat-soak**. **The track data says that's not the primary driver:**

- During the shortfall stretches **IAT was only 82–91 °F** — the intercooler was keeping up fine (cool 68 °F ambient helps). Post-intercooler charge-air heat is **not** the bottleneck here.
- Yet the turbo still couldn't hit target. So the real gap is **turbo/exhaust-side**: after back-to-back WOT the **turbo and exhaust are heat-soaked** (EGT peaking **1814 °F** vs 1726 in the baseline; coolant to **223 °F**, oil to **257 °F**), which lowers the IS20's efficiency and boost capability — while the **map still commands an aggressive 25–27 psi**. Hot turbo + aggressive target = actuator pinned, boost short, deviation fault.

Net: **P2563 is a target-vs-capability gap**, worsened by turbo/exhaust heat, **not** an intercooler/IAT problem. **An upgraded intercooler would not fix it.** Lowering and tapering the boost target will.

## Other findings

### Mild knock — cylinder 1 only, at high EGT (~t=143)
A brief real knock event: **Knock Retard Cyl 1 = 1.9°** for ~1 s around **t=143** at ~4500 rpm, **EGT ~1800 °F**. Cylinders 2–4 stayed at 0. AFR was still rich (~11.6 target). So it's not a fueling-lean event — it's **cyl-1 running hot** under sustained load (common weak cylinder on these). Minor, but it's the one spot where the 92-octane margin was consumed, and it correlates with peak exhaust temp. Worth watching after any timing changes.

### Thermal limits reached
| | Peak | When | Note |
|---|---|---|---|
| EGT | **1814 °F** | t=247.8 | Hot — at/above the ~1800 °F caution zone for this engine |
| Oil | **257 °F** | t=401 (session end) | Hot; climbs steadily — a real longevity flag for track |
| Coolant | 223 °F | — | Warm |
| DSG temp | 230 °F | — | Getting toward DSG heat-management thresholds |
| IAT | 82–91 °F under load | — | Fine (133 °F reading at t=0 is pre-drive soak, ignore) |

`COBB Spark Reduction = 0` all session (no launch/TC events on track, as expected). Rail pressure held its setpoint under load.

## Implications for [[diy-conservative-track-tune]]

The two logs now triangulate the fix cleanly:

1. **The tune is boost/torque-request aggressive, not knock-limited** (confirmed again — only one mild cyl-1 event all session). So pull **boost target**, keep timing.
2. **Target a boost curve the IS20 can actually hold when hot.** In the 4300–5200 rpm band the turbo delivered ~22–25 psi at 100% actuator on track — so a target around **~23–24 psi** there (vs the current 25–27) would keep the actuator **off its stop** with authority to spare, killing the deviation and the [[P2563]] EPC light. Little real-world power lost since the turbo wasn't making the extra anyway.
3. **Add a high-rpm / sustained taper** (and optionally an EGT- or coolant-based pullback) so late-session heat-soak doesn't push the actuator back into saturation.
4. This also fixes the **spool overshoot** from the baseline (a lower, gentler target rings less).
5. Keep an eye on **cyl-1 knock** and **oil/EGT temps** — thermal, not tune-limited, but a conservative map that asks for less boost also makes less heat.

## Verify / reproduce

Every figure is traceable in the CSV: t=239 table rows, the ~40 s deficit tally (filter `Accel>90 & Turbine Act. Final≥99 & Boost>18 & (Boost−Target)<−1.5`), the t=143 cyl-1 knock, and the temp peaks. Re-run the same query on a **future conservative-tune track log** and the pinned-actuator deficit time should collapse toward zero — that's the pass/fail test for whether P2563 is solved.

See [[eqt-s2-baseline-log-review]] for the clean baseline, [[ecu-tuning-basics]] for the boost-target/wastegate tables to edit, and [[simostools-app-guide]] for capturing the comparison log.
