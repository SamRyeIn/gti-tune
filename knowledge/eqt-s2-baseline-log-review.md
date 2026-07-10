---
source: References/20220522_EQTS2_3Gear1.csv, References/Cobb_links.txt
date: 2026-07-06
key_people: none
key_concepts: EQT Stage 2 91 baseline log, WOT 3rd-gear pull, boost overshoot / underdamped boost control, wastegate actuator saturation, P2563 boost-deviation fault, knock/timing headroom, datalog review method
---

# EQT Stage 2 91 — Baseline WOT Log Review

Reference baseline for [[diy-conservative-track-tune]]. Characterizes the **currently-installed** tune from a real datalog so any future DIY calibration can be compared against a known-good starting point. The owner likes this tune but wants a slightly more conservative version for **longevity** and **track** use, and to stop tripping the [[P2563]] EPC fault under sustained WOT.

## The tune under test

From the log's `AP Info` string:

- **ECU reflash:** `EQT - Stage 2 91 v2.52 - LC TC` (Launch Control + Traction Control features)
- **TCM:** `EQT - DSG - IS20 v2.03` (DSG gearbox tune)
- **Turbo:** **IS20** (factory GTI turbo — the ceiling that matters for the [[P2563]] discussion below)
- **Fuel target:** 91 octane (California map). Owner runs **92 octane** (Seattle), i.e. always **≥** the map's design fuel — this is the safe direction and shows up as headroom in the log (see [[Knock and timing]]).
- Vehicle context: [[Simos 18.1]] MQB GTI. (Note the wiki's primary car is a 2017 GTI box `5G0906259L`; confirm this log's car/box code matches before porting numbers.)

## The log

`20220522_EQTS2_3Gear1.csv` — 553 samples, ~80 Hz, 0–12.4 s. A single **wide-open-throttle pull in 3rd gear** (`Current Gear = 3`, `Accel Pedal ≈ 100%`), roughly **t = 0.9 → 7.4 s**, sweeping **~2560 → 6340 rpm**. Cooldown after ~7.5 s.

> **This is a clean street pull — it did NOT trip [[P2563]].** Treat it as the fault-free baseline: boost tracks target (within the overshoot ring), knock = 0, fueling healthy. The P2563 discussion below is an **inference** about a *different, harsher* duty cycle (sustained track running), not something observed in this log.

### Peak numbers (the current tune's aggression)

| Metric | Value | Where |
|---|---|---|
| Peak boost | **28.4 psi** | 3680 rpm (t=2.58) |
| Peak torque (actual, modeled) | **409 ft-lb** | 3680 rpm |
| Peak torque at clutch | 385 ft-lb | 3776 rpm |
| Peak air mass | 1677 mg/stk | 3648 rpm |
| Boost target at redline | ~19 psi | 6336 rpm |
| Max knock retard (any cyl) | **0.0°** | whole pull |
| COBB spark reduction | 0.0° | whole pull |

28+ psi peak on an **IS20** is an aggressive Stage 2 target — near the top of what that frame will flow before it runs out of efficiency and heat-soaks. That single fact ties together both of the owner's complaints below.

## Boost overshoot / oscillation (owner's observation, confirmed)

The oscillation the owner noticed on boost ramp-in is **real and visible in the data**. During spool the closed-loop controller is clearly **underdamped** — it overshoots target, corrects past it, and rings down over ~2 cycles before settling by ~t = 3.0 s:

| t (s) | rpm | Boost | Target | Δ (boost−tgt) | Turbine Actuator Final |
|---|---|---|---|---|---|
| 1.72 | 2976 | 24.6 | 24.3 | **+0.3** (first cross) | 79 |
| 1.80 | 3040 | 25.9 | 24.5 | **+1.4** (overshoot #1) | 66 |
| 1.89 | 3168 | 23.8 | 25.3 | **−1.5** (undershoot) | 90 |
| 2.58 | 3680 | 28.4 | 27.3 | **+1.1** (overshoot #2) | 68 |
| 2.84 | 3872 | 26.3 | 27.3 | **−1.0** (undershoot) | 86 |
| 3.0+ | 4000+ | tracks | tracks | ±0.3 | ~77 (settled) |

Read the **Turbine Actuator Final Value** column: base command sits ~79% but the closed-loop term is slamming it **66 → 90 → 68 → 86%** — big, fast corrections fighting the overshoot. Signature of either (a) a boost-target **ramp rate** demanded faster than the wastegate/turbo can follow smoothly, or (b) boost-control **PID gains** (esp. the proportional/integral term) tuned too hot. See [[ecu-tuning-basics]] → boost control / wastegate flow-factor for where these live in TunerPro.

**Longevity/track relevance:** the ±1–1.5 psi ring and the peak 28.4 psi are the most aggressive part of the map. Softening the target ~1–2 psi and gentling the ramp rate would reduce mechanical/thermal stress on the IS20 with little real-world power loss.

## Knock and timing — plenty of headroom

- **Knock retard = 0.0° on all four cylinders for the entire pull**, and **COBB spark reduction = 0.0°**. The 92-octane-on-a-91-map margin shows up here: the ECU never had to pull timing.
- **Ignition Timing Final** advances cleanly from ~−5° (spool, heavy load) up to ~+6.5° by 6300 rpm — normal load-following behavior, no corrections.
- **Interpretation:** this tune is **not** knock-limited on the owner's fuel. A conservative rewrite has room to keep timing where it is (or nearly), so the conservative changes should target **boost/torque request and ramp rate**, not timing.

## Fueling & pump — healthy

- **AFR tracks setpoint** closely, richening to ~**11.5:1** under peak boost (safe, cooling mixture) and returning to ~14.7 off-load.
- **Rail pressure** holds ~**2900 psi** through the pull — the [[HPFP]] is keeping up; no fuel-supply shortfall.

## Temperatures

ECT 190–201 °F, oil 217–219 °F, **IAT climbs 84 → 102 °F** across the pull (intercooler heat-soak in a long 3rd-gear pull, expected), EGT peaks ~**1726 °F**. Nothing alarming for a single street pull, but the IAT climb previews why **sustained track** running is a different, harsher duty cycle.

## The [[P2563]] EPC fault (track)

[[P2563]] = **"Turbocharger Boost Control Position Sensor A — Range/Performance"** on VAG. On the electronic-wastegate MQB turbos it typically sets when the **commanded actuator position vs. the boost actually achieved deviates beyond a threshold** — i.e. the ECU asks for a boost/position the turbo cannot deliver, the actuator **saturates against its limit**, and the deviation monitor trips → EPC light.

**This log did not throw P2563** — it's a cool street pull. But it shows *why* the fault appears on track, which is the useful part:
1. The map targets an **aggressive 28 psi peak on an IS20**, right at the frame's limit.
2. On this **single street pull** the turbo is cool and just barely makes it — note the actuator already swinging to 66% and boost overshooting, i.e. it has little authority to spare even when everything is cold.
3. On **track**, after minutes of WOT, the turbo and charge air **heat-soak** (IAT already rising 84→102 °F *within this one pull*). A hot turbo makes **less** boost for the same wastegate position, so actual boost falls further below an unchanged aggressive target → position/boost **deviation grows past threshold** → **P2563** → EPC. This log captures the *starting* conditions of that slide, not the fault itself.

**Fix direction (the conservative tune's main job):** lower the boost target — especially the **high-rpm / sustained** region — so the actuator isn't pinned when hot, and/or add a heat-based boost taper. That both removes the deviation fault and reduces the overshoot. Longevity, track reliability, and drivability all point the same way here.

> **Update — corrected by the on-track data in [[eqt-s2-track-log-p2563]]:** the actual track log shows the shortfall happens with **IAT only 82–91 °F**, so the driver is **turbo/exhaust-side heat-soak**, not charge-air (IAT) heat. An intercooler upgrade would *not* fix P2563; a lower/tapered boost target will. See that note for the live capture of the actuator pinned at 100% while boost sits 2–3 psi under target.

## Datalog-review method (from the Cobb references)

From the two Cobb pages in `Cobb_links.txt` ([Engine Monitor List](https://cobbtuning.atlassian.net/wiki/spaces/PRS/pages/222691360/) and [Datalogging Review — VW/Audi](https://cobbtuning.atlassian.net/wiki/spaces/PRS/pages/252674049/)). Note: the detailed MK7 quick-reference threshold tables are gated behind expandable sections and were not retrievable — get them from a logged-in Cobb AccessPort account. General method:

- **Always log the load context first:** RPM, Throttle/ETC angle, Accel Pedal, and **Barometric Pressure** (air density shifts fueling and peak boost — matters for the Seattle-vs-California elevation/weather difference).
- **DI-engine caveat (this car):** fuel-quality problems **don't** show in the data until *prolonged* knock occurs — so always run the map-appropriate (or higher) octane. The owner does (92 ≥ 91).
- **Boost:** watch actual vs **target/setpoint** and overshoot; watch **Press Ratio at Comp.** vs its **SP**; watch **Turbine Actuator base vs final** for how hard closed-loop is working.
- **Knock health:** per-cylinder **Knock Retard** should sit at **0°**; sustained non-zero = pull timing / add fuel / reduce boost. **COBB Spark Reduction** ≠ 0 only during Launch/TC events.
- **Fueling:** **AFR vs AFR Set Point** should track; **Rail Pressure** should hold its setpoint under load.

## Takeaways for the conservative rewrite

1. **This tune is boost/torque-request aggressive, not knock-limited** on 92 octane — so pull **boost target and ramp rate**, keep timing.
2. **Trim ~1–2 psi off peak** (28 → ~26) and **soften the ramp rate** to kill the underdamped overshoot and lower IS20 stress.
3. **Taper the high-rpm / sustained boost target** (and/or add IAT-based taper) so the actuator stops saturating when hot → resolves **[[P2563]]** on track.
4. Re-log an identical **3rd-gear WOT pull** after changes and diff against this baseline (boost trace, actuator swing, knock=0, AFR tracking).

See [[tuning-getting-started]] for the toolchain, [[ecu-tuning-basics]] for the boost/torque/timing tables to edit, and [[simostools-app-guide]] for capturing the comparison log.
