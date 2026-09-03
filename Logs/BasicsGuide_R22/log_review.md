# R22 log review — the three-slot octane experiment

**Flashed:** `Patched_259L_R22.bin` (log header `R2.12:2026_9_1:Patched_259L_R22.bin`).
**Session:** 2026-09-01, 06:34–07:02, 21 logs / 21 detected pulls, 20 in 3rd gear
and one partial in 2nd. Ambient 14.6 °C / 100.8 kPa, IAT mean 25.5 °C — within
0.4 °C and 0.4 kPa of the R20 session, so R20 is a fair comparison throughout.

**Verdict: the calibration delivered exactly what R22 designed, and the
experiment came back null. The two octane slots are indistinguishable from each
other in every band and over the whole range.** Slot 4 (reduced boost, R20's
uncut timing) and slot 5 (full boost, R21's cut timing) sit within
0.2 deg-s/min of each other across 3000–6600 rpm. R22 does **not** resolve
whether cylinder filling or offset size is the binding variable, and the reason
is exposure, not design: the control got 4 pulls against slot 4's 9 and slot 5's 8.

What the session *does* establish is smaller but solid, and three pieces of it
cut against the octane program as it stands:

- **The dose itself shows no measurable value on the everyday map.** R22 slot 3
  is the first dosed base-timing slot ever logged, and against R19's plain-92 runs
  of the identical calibration it is no better on knock (+3.19 deg-s/min, CI
  spanning zero) and no better on power (−2.31 hp, 1.15 se). This is the first
  direct evidence on the booster in the lineage.
- The 4500–5000 rpm band R20 indicted knocks just as hard on **base timing**.
  R20's headline does not replicate.
- The band where both slots separate from the control is **5000–5500** — the band
  R20 called clean — and they separate *together*, by equal amounts, in the one
  place their modifiers are byte-identical. That points at the offset itself, not
  at boost.

Taken together: the booster's entire return is the ~6 hp slot 5 makes over the
control, bought with more knock than the control. Whether that is worth dosing
every tank is now a decision to take deliberately, not an assumption to inherit.

## Which pull ran which slot — unambiguous

`REV_LOG` § R22 flagged mis-attribution as "the single most likely way to misread
the next log folder". In the event it was not close: two independent fingerprints
agree on all 21 pulls, with wide margins and no unresolved cases.

1. **Boost curve.** `PUT SP` — Pressure up throttle setpoint is the slot's
   `PUT setpoint` — map slot boost cap read straight back out of the ECU, so it
   is the map, not a control outcome. Fitting each pull's logged setpoint against
   the five slot curves *read off the flashed bin* gives **RMS 6–7 hPa on the
   right curve against 90–110 hPa on every wrong one** — better than an order of
   magnitude of separation. That isolates slot 4 on its own.
2. **Ignition offset.** Slots 3 and 5 share one boost curve exactly, so boost
   cannot separate them. `Ign Table` — the base ignition map lookup carries **no**
   slot modifier (it is identical on all 21 pulls); the offset appears only in
   `Ign Avg` — delivered ignition angle. Reconstructing
   `Ign Avg − Ign Table + worst per-cylinder retard` recovers the
   `Spark modifier` — map slot ignition offset grid to within a quantisation step:
   the control reads 0.00 ± 0.4° in every rpm bin while both octane slots read
   +1.5 to +3.4°. Nothing lands in between.

| Slot                                                   | Slot | Pulls                         | Loaded WOT |
| ----------------------------------------------------- | ---- | ----------------------------- | ---------- |
| Control — aggressive boost, base timing               | 3    | 10, 11, 12, 13                | 28.2 s     |
| Reduced-**boost** slot — mid boost, R20's uncut timing | 4    | 5, 6, 7, 8, 9, 16, 17, 18, 21 | 58.5 s     |
| Reduced-**timing** slot — full boost, R21's cut timing | 5    | 1, 2, 3, 4, 14, 15, 19, 20    | 50.1 s     |

Checked against the bins rather than taken from `REV_LOG`: R22 slot 3's boost cap
is **byte-identical** to R20 slot 4's (`2698, 2754, 2808, 2808, 2808, 2760, 2711,
2609, 2519, 2426, 2335, 2243` hPa on both), and its `Spark modifier` grid is
all-zero across every cell — so the control really is the calibration R14 through
R20 were scored against, with a genuinely neutral modifier. Both octane grids
write the **1200.01 and 1400.00 mg/stk** rows identically, so any sample between
those two loads receives the full declared offset; below 1200 it tapers to zero
at the unwritten 1049.99 row.

Attribution is automated in `slot_attribution.py` and re-derived by
`analyze_r22_slots.py`, so it cannot drift. **Still record the slot per pull next
time** — the reconstruction worked, but it is a dependency on the bin being
available and on the slots differing in something loggable, and neither is
guaranteed for a future revision.

### The slots delivered exactly what R22 designed

Measured over loaded WOT at 4500–5000 rpm, the band the experiment targets:

| Slot                   | PUT SP    | PUT   | Airmass     | Delivered ignition | vs control        |
| --------------------- | --------- | ----- | ----------- | ------------------ | ----------------- |
| slot 3 control        | 276.3 kPa | 269.8 | 1497 mg/stk | −3.68°             | —                 |
| slot 4 reduced boost  | 264.6 kPa | 260.5 | 1442 mg/stk | −0.60°             | −11.7 kPa, +3.08° |
| slot 5 reduced timing | 276.0 kPa | 268.2 | 1490 mg/stk | −1.22°             | −0.3 kPa, +2.46°  |

The designed contrast was 123 hPa at 5000 rpm; 117 hPa was delivered. Slot 5's
boost matches the control to 0.3 kPa. **The calibration did what the script said
it would** — this is the bin verification only logs can provide.

## Findings

### High — the experiment is null: slot 4 and slot 5 are indistinguishable

Scored on **degree-seconds of per-cylinder retard per loaded WOT minute**, a
continuous statistic that uses every sample. Event counting — the metric R19/R20
were scored on — cannot resolve this session at all (see below); the integral is
the more sensitive statistic available, and it still does not separate the slots.

All 21 attributed pulls, no exclusions, pull-level bootstrap 95% intervals:

| Band (rpm)    | s3 control | s4 red-boost | s5 red-timing | s4 − s3                       | s5 − s3                     | s5 − s4                         |
| ------------- | ---------- | ------------ | ------------- | ----------------------------- | --------------------------- | ------------------------------- |
| 3000–3500     | 29.57      | 57.05        | 25.00         | +27.5 [−32.5, +100.2] P=0.215 | −4.6 [−36.1, +32.2] P=0.590 | −32.0 [−101.7, +25.5] P=0.824   |
| 3500–4000     | 0.00       | 23.33        | 4.88          | +23.3 [+0.0, +65.1] P=0.105   | +4.9 [+1.0, +10.1] P=0.024  | −18.5 [−60.9, +7.2] P=0.769     |
| 4000–4500     | 0.00       | 9.56         | 12.18         | +9.6 [+0.0, +28.4] P=0.348    | +12.2 [+0.5, +28.8] P=0.023 | +2.6 [−20.6, +25.6] P=0.382     |
| 4500–5000     | 23.94      | 19.05        | 28.62         | −4.9 [−42.5, +30.1] P=0.635   | +4.7 [−34.8, +39.3] P=0.423 | +9.6 [−26.8, +44.4] P=0.289     |
| 5000–5500     | 2.92       | 19.70        | 24.48         | +16.8 [−0.4, +37.3] P=0.029   | +21.6 [+0.6, +45.4] P=0.024 | +4.8 [−24.6, +34.8] P=0.372     |
| 5500–6000     | 13.34      | 3.77         | 14.24         | −9.6 [−35.8, +6.6] P=0.691    | +0.9 [−26.5, +22.8] P=0.457 | +10.5 [−1.4, +23.1] P=0.045     |
| 6000–6600     | 6.77       | 3.78         | 10.97         | −3.0 [−16.3, +9.3] P=0.678    | +4.2 [−12.7, +21.8] P=0.310 | +7.2 [−6.9, +22.6] P=0.168      |
| **3000–6600** | **11.03**  | **17.13**    | **17.33**     | +6.1 [−7.4, +21.2] P=0.212    | +6.3 [−6.0, +18.7] P=0.168  | **+0.2 [−16.2, +15.0] P=0.476** |

There are 24 tests in that table and nothing in it survives a correction for
that, so read the pattern rather than any single cell. The pattern is:

- **Slot 4 and slot 5 track each other.** Over the full range they differ by +0.2 with an
  interval spanning ±15 — the experiment's central contrast is as close to a flat
  null as the data can express. No band separates them; the closest is
  5500–6000 at P=0.045, one cell out of twenty-four.
- **Both octane slots sit modestly above the control**, by +6.1 and +6.3, neither
  significant. The boost cut did not buy a measurable margin, and neither did the
  timing cut.
- **Where both octane slots do rise above the control together is 5000–5500** (+16.8 and
  +21.6, P=0.029 / 0.024) — see the next finding.

So R22 does not tell you whether to cut boost or cut timing. It tells you that
1.6 psi and R21's two-column timing cut are both too small to show up against
this much session noise with this little control exposure.

Evidence: `plots/r22_slot_knock_rates.png` (middle panel), `analyze_r22_slots.py`.

**Caveat, reported not acted on.** Oil temperature climbs 81 → 111 °C over pulls
1–9 and plateaus at 110–112 °C thereafter, and the slots are not balanced across
that warm-up: all four of slot 5's early pulls are warm-up pulls. Restricting to
the plateau would change the numbers substantially, but that is choosing a subset
after seeing the outcome, so the table above uses every pull. The honest reading
is that thermal state is one more uncontrolled source of the noise this session
could not see through — a reason to interleave from a fully warmed start next
time, not a reason to re-slice this data.

### High — R20's 4500–5000 finding does not replicate

Rescoring R19, R20 and R22 on identical definitions (R19's `knock_events` and
`loaded_mask`, unchanged, recomputed from each session's raw logs rather than
quoted from its review) in the band R20 indicted:

| Session / slot | Calibration                            | Events | Exposure | ev/min | exact 95% CI |
| -------------- | -------------------------------------- | ------ | -------- | ------ | ------------ |
| R19 slot 4     | aggressive boost, base timing          | 1      | 14.2 s   | 4.2    | [0.1, 23.5]  |
| R20 slot 5     | aggressive boost, R20 uncut timing     | 6      | 13.1 s   | 27.5   | [10.1, 59.9] |
| R22 slot 3     | **the same calibration as R19 slot 4** | 2      | 5.0 s    | 24.0   | [2.9, 86.7]  |
| R22 slot 4     | mid boost, R20 uncut timing            | 2      | 9.8 s    | 12.2   | [1.5, 44.1]  |
| R22 slot 5     | aggressive boost, R21 cut timing       | 3      | 7.8 s    | 23.1   | [4.8, 67.4]  |

R20's High finding was that 4500–5000 rpm went 4.2 → 27.5 ev/min, "Poisson
p ≈ 0.0006". That p-value treats R19's 4.2 as a *known* rate when it was
estimated from a single event. **R22's control runs the identical calibration and
lands at 24.0 ev/min** — statistically indistinguishable from R20's supposedly
regressed slot 5, in near-identical ambient conditions. On the retard integral
the same band shows no slot-versus-control difference at all (−4.9 and +4.7).

The band knocks on base timing. It is a property of this engine on this boost
curve, not something R20's modifier introduced — which means **R21 was designed
against an artifact.** Nothing was damaged, since R21 was never flashed, but the
method lesson is worth keeping: do not act on a Poisson comparison against a
control estimated from one event.

### Medium — the modifier does add knock, one band higher than R20 thought

5000–5500 rpm is the only band where both slots rise above the control by similar
amounts (+16.8 and +21.6 deg-s/min, P=0.029 / 0.024), and it is the band where
their `Spark modifier` grids are **byte-identical** (+3.750 at 5000, +2.250 at
5500). Two independently attributed slots agreeing, in the one place they are the
same calibration, is a more credible signal than either P-value alone — the boost
difference between them is irrelevant there, so what is left is the offset.

R20 read this band as clean: "the +3.750 °CRK apex at 5000 rpm logged zero
events" and improved on R19. R22 says the opposite, with the neutral control R20
never ran. If any part of the octane offset is to be trimmed, the evidence points
at the 5000–5500 apex rather than the 4500–5000 shoulder R21 cut.

Treat this as a lead, not a conclusion: 1 event on the control against 3 across
the slots, and it does not survive a multiple-comparison correction either.

### High — the octane dose shows no measurable value on the map that is actually driven

R22 is the first session in this lineage that makes the octane booster itself
testable, and the test had never been run. Every revision since R20 has assumed
the VP Octanium dose is worth its cost; R20's own logs cannot check that, because
**all ten of its usable logs are octane-map pulls** (fingerprinted at +3.00 to
+3.75° reconstructed offset) — so R20 compared a *dosed offset* map against a
*plain-92 base* map and confounded the fuel with the timing.

The comparison that isolates the fuel was already in the archive:

- **plain 92, base timing** — the whole R19 session, 8 pulls, 69.6 s loaded WOT.
  R20 introduced the dose, so R19 predates it.
- **dosed, base timing** — R22 slot 3, 4 pulls, 28.2 s.

These are the *same calibration*: slot 3's boost cap is byte-identical to R20
slot 4's, its `Spark modifier` grid is all-zero, and the knock fast-loop
(`IP_IGA_DEC_KNK` — Spark retard at recognised knocking) has not moved since R19.

| Band (rpm)    | plain 92 | dosed     | dosed − plain | 95% CI           | P(dosed worse) |
| ------------- | -------- | --------- | ------------- | ---------------- | -------------- |
| 3000–3500     | 36.74    | 29.57     | −7.17         | [−56.40, +40.10] | 0.380          |
| 3500–4000     | 1.35     | 0.00      | −1.35         | [−3.35, +0.00]   | 0.000          |
| 4000–4500     | 4.26     | 0.00      | −4.26         | [−12.99, +0.00]  | 0.000          |
| 4500–5000     | 5.07     | 23.94     | +18.87        | [−4.51, +51.31]  | 0.931          |
| 5000–5500     | 6.12     | 2.92      | −3.19         | [−12.48, +5.51]  | 0.370          |
| 5500–6000     | 6.76     | 13.34     | +6.58         | [−13.40, +33.63] | 0.646          |
| 6000–6600     | 5.85     | 6.77      | +0.91         | [−14.42, +14.44] | 0.535          |
| **3000–6600** | **7.84** | **11.03** | **+3.19**     | [−5.55, +12.05]  | 0.767          |

Power is null too: 307.9 ± 2.93 hp plain against 305.6 ± 3.45 dosed — −2.31 hp at
1.15 se — on matched peak filling (1573 vs 1577 mg/stk). Conditions were
comparable and if anything favoured the dosed session (ambient 14.3 vs 16.5 °C,
IAT within 0.1 °C), an advantage it did not convert.

**Read the null carefully.** Base timing is not knock-limited over most of the
range — plain-92 retard sits at 1.3–6.8 deg-s/min outside the 3000–3500 zone,
near the floor — and octane cannot buy margin where margin is not binding. So
this shows the dose does **nothing for the everyday map**; it does not prove the
dose does nothing on the offset maps, which is the case it was bought for.

That case cannot be settled safely. The direct test is slot 5 dosed versus slot 5
on plain 92, and `REV_LOG` § R20 forbids exactly that: "Selecting slot 5 on plain
92 will knock. Accepted knowingly… the control is discipline, not calibration."
There is no experiment left that is both decisive and safe.

So the booster's whole return is downstream of the offset maps, and this session
priced those: **+5.98 hp on slot 5 (2.89 se), while knocking more than the
control.** ~2% for dosing every tank, a two-tier ladder, and the standing
discipline of never selecting slots 4–5 on a bad tank. That is an economics
decision rather than a data one, and R22's reorder already made slot 3 the
everyday map and the in-drive fallback — so dropping slots 4–5 costs nothing
structural.

Evidence: `analyze_octane_value.py`, which also fingerprints the R19 and R20
sessions so "R20 holds no base-timing control" is established rather than assumed;
and `plots/r22_knock_by_slot.png`, whose top row is this comparison drawn on shared
axes — the plain-92 and dosed base-timing panels are visually interchangeable,
and **neither ever passes −1.50 °CRK**. The bottom row is the price of the
offsets: both dosed octane slots breach it, slot 4 to −4.50° and slot 5 to −2.25°,
at roughly double the base-timing retard rate (17.1 and 17.3 against 7.8 and 11.0
deg-s/min). The only configurations in this comparison that go beyond one
detected event's worth of retard are the two the booster was bought to enable.

### Medium — the deepest retard in the lineage, and a mechanism for the 3000–3500 zone

Pull 7 (`06_44_56`, slot 4) reaches **−4.50 °CRK on cylinder 4** at 3156 rpm and
holds it for 1.6 s before decaying. That is twice R20's worst (−2.25) and the
deepest cut recorded in this lineage. It is unambiguously real knock, not a
sensor artifact: cylinder 4 alone, ramping 0 → −1.50 → −3.00 → −4.50 in
successive samples, holding, then decaying, while cylinders 1–3 stay clean and
`knks_thd[3]` — the cylinder-4 knock threshold rises 1.56 → 1.70 V with it.

More usefully, **every** 3000–3500 rpm event in the session — all nine, across
all three slots — sits between 3026 and 3156 rpm, and the intake **valve-lift
1 → 0 transition** occurs at 3052–3104 rpm on every single pull. The event
cluster and the lift changeover are the same feature. Pull 7's event begins at
3058 rpm, in the same sample the lift flips, at the session's peak filling
(1571 mg/stk, 26.0 psi).

R20's review recorded a 6.376 °CRK ignition-model outlier at 3057 rpm in a
"combustion-mode 2 / valve-lift 0 transition" and set it aside as outside steady
WOT. Same rpm, same transition. The 3000–3500 zone that both prior reviews called
"pre-existing" and "never addressed" now has a named candidate mechanism — a
filling/timing mismatch across the intake lift profile switch — and it is the
highest-retard zone in the session on every slot.

### Medium — this session cannot support event-rate conclusions

Every event rate above rests on 0–6 events. Resolving a 2× rate difference at
these rates needs roughly 25 control events, which is ~60 s of in-band exposure
per slot — about 49 pulls per slot, not achievable in one session per band.

Two design fixes for R23, in order of value:

1. **Budget the control.** It got 4 pulls against 9 and 8. The control is the
   comparison every slot is measured against; it should get *at least* as many
   pulls as any slot, not the fewest.
2. **Score on the retard integral, not event counts**, and pre-declare the bands.
   The integral kept the depth and duration of each cut and was still barely
   enough; the event count discards both.

### Medium — the wastegate feedforward still under-commands, on all three slots

The known open P1 against R19's intake-axis re-breakpoint is unchanged and
present on every slot. Over 3700–6100 rpm loaded WOT:

| Slot    | Mean PUT error | Worst  | WG I mean | `wg_pos_final` − `wg_pos_base` |
| ------ | -------------- | ------ | --------- | ------------------------------ |
| slot 3 | −4.26 kPa      | −36.14 | 7.98%     | +14.05 pts                     |
| slot 4 | −3.68 kPa      | −53.50 | 4.93%     | +10.44 pts                     |
| slot 5 | −5.26 kPa      | −40.88 | 7.48%     | +14.98 pts                     |

The closed loop is carrying 10–15 points that the position feedforward
(`IP_FAC_BPA_SP` — Map for boost pressure actuator setpoint) is leaving on the
table, exactly as the analysis battery reports. Slot 4 carries less because it
asks for less. This applies equally to all three slots so it does not bias the
experiment, but it remains unresolved and still owes the part-throttle high-rpm
log that `tune_code_review.md` asked for.

### Low — the battery's High lambda finding is a sensor rail, not a fueling problem

`analysis_findings.md` reports "settled-WOT lambda runs lean by +0.074". Tested:
the excursions are samples where `Lambda` pegs at exactly **2.000** — the
channel's rail — and `Lambda SP` simultaneously jumps to 1.000. Both channels
rail in the same samples, at the same 4600–5030 rpm window, at the same ~2% rate
in all three slots. It is a logging artifact around the enrichment setpoint
handover, not a lean event; a genuine λ 2.0 at 1300 mg/stk would not pass
unremarked by anything else in the log.

Excluding samples with λ > 1.5, settled WOT fueling is essentially exact:

| Slot    | Mean λ error | p99     | n    |
| ------ | ------------ | ------- | ---- |
| slot 3 | +0.0007      | +0.0202 | 628  |
| slot 4 | +0.0018      | +0.0299 | 1281 |
| slot 5 | +0.0007      | +0.0227 | 1097 |

WOT enrichment targets 0.80–0.85 through the range, as designed. Fuel system has
headroom: worst DI rail sag −10.1 bar, LPFP peak 80.7%, HPFP effective volume
peak 97.0%.

### Low — the boost cut costs no power, and the timing offset makes some

**What `Calc HP` actually is.** Two parts, and only one of them is verified here.

*Verified against these logs:* `Calc TQ × rpm / Calc HP = 7127.0` with sd
**0.000** across every sample — so the two channels are one quantity, and the
torque is referred to **engine** rpm (7127 being the Nm·rpm→hp constant). And the
power itself is **acceleration-derived from the `Accel. Long` accelerometer
channel**: `Calc HP ≈ k · Accel. Long · v` fits with an implied effective mass of
1941 ± 233 kg in 3rd gear — the right magnitude for this car plus its rotating
inertia — while the same fit against a differentiated `Vehicle Speed` does not
work at all (cv 0.63), and no rpm-derivative form fits. `Calc HP` also drops to
exactly 0.0 through a gear change.

*Not verified here:* the "gear-ratio weighted" half, which this project's
`CLAUDE.md` records from earlier work. The implied `k` does move with gear (2037 /
1941 / 2643 kg in 2nd / 3rd / 4th), which is consistent with a ratio term — but
the 4th-gear samples are dominated by the post-flip, pre-shift window that *is*
the documented artifact, so that test cannot separate "ratio in the formula" from
"artifact contamination". Treat the gear-ratio claim as inherited, not
established.

None of this threatens the comparison below, because all three slots are compared
**in 3rd gear, in-gear trimmed, interleaved on the same road in one session** — so
whatever constant the formula carries is common to all three and cancels. Absolute
values are indicative only; this is not a dyno figure.

Per-pull peak (99.5th percentile of in-gear samples per the gear-flip rule),
3rd-gear pulls only, then averaged across pulls — not pooled across all samples,
which would favour whichever slot got more pulls:

| Slot                   | Peak HP mean | sd   | n   | Peak airmass  |
| --------------------- | ------------ | ---- | --- | ------------- |
| slot 3 control        | 305.6        | 3.43 | 4   | 1577.4 mg/stk |
| slot 4 reduced boost  | 306.5        | 2.00 | 8   | 1529.8 mg/stk |
| slot 5 reduced timing | 311.6        | 3.26 | 8   | 1578.7 mg/stk |

| Contrast        | Δ Peak HP | se   | separation |
| --------------- | --------- | ---- | ---------- |
| slot 4 − slot 3 | +0.94     | 1.86 | 0.51 se    |
| slot 5 − slot 3 | +5.98     | 2.07 | 2.89 se    |
| slot 5 − slot 4 | +5.04     | 1.35 | 3.73 se    |

Two results, and unlike the knock comparison both are cleanly resolved:

- **Slot 4 is power-neutral against the control** — +0.94 hp at 0.51 se, i.e.
  indistinguishable — while running **48 mg/stk (3%) less peak filling.** The
  boost cut removed 3% of the air and the added timing gave the work back. That
  is a real efficiency gain, independent of anything the knock analysis could or
  could not resolve.
- **Slot 5 is genuinely ~5–6 hp up on both**, at 2.9 and 3.7 se. Against the
  control it runs identical boost and identical peak airmass (1578.7 vs 1577.4),
  so that gain is the ignition offset alone.

Airmass corroborates the boost attribution independently of `Calc HP`: slots 3
and 5 land within 1.3 mg/stk of each other, slot 4 sits 48 below. That is the
designed contrast showing up in cylinder filling, which is the quantity the whole
experiment is about.

## Against R22's own logging gate

`REV_LOG` § R22 asked for: interleaved slot 3/4/5 pulls ✅ (interleaved, but
control-light at 4 pulls); one dosed tank ✅ (`Eth Content` 0.0% throughout, one
continuous session); WOT held into 4th ⚠️ (3.1 / 5.9 / 4.2 s of 4th-gear loaded
WOT per slot — present but thin, and 6000–6600 remains the least-resolved band);
per-cylinder knock channels ✅; folder ✅ (named `BasicsGuide_R22` rather than
`MainTune_R22`, matching the R17–R20 convention); **selected slot recorded per
pull ❌** — it was not, and had to be reconstructed. The reconstruction was
decisive, but recording it costs nothing.

The gate's real failure is not on that list: **the control was under-exposed**,
and no gate item asked for balance across slots. Add one.

## Feeding R23

1. **Re-run the same experiment with a balanced design** before drawing any
   conclusion about boost versus timing. Equal pulls per slot with the control
   first among equals, interleaved from a fully warmed start, scored on the
   retard integral. R22's calibration is fine as-is for this — it needs a better
   session, not a new bin.
2. **If you want one lever now, the 5000–5500 apex is the better-evidenced
   target** than R21's 4500–5000 shoulder. Both slots knock there against the
   control with identical modifiers.
3. **Take on 3000–3500 rpm at the valve-lift transition.** Highest retard zone in
   every session, the lineage's deepest cut (−4.50°), locked to the 3052–3104 rpm
   lift changeover, and never addressed by any revision.
4. The queued R23 items — raising the 6000 rpm modifier toward +3.000 °CRK and
   writing the 1049.97 mg/stk row — are **not** supported by this session.
   6000–6600 is the least-resolved band here (thin 4th-gear exposure on every
   slot). Leave the top end alone until it has been logged properly.
5. **Decide whether the octane program continues at all**, before spending another
   revision on it. On present evidence the dose buys nothing on the everyday map
   and ~6 hp on slot 5 at a knock cost, and no safe experiment can improve on
   that answer. Every other item in this list is cheaper if the answer is "stop".
6. **Do not treat R21 as vindicated or refuted.** Its premise was an artifact
   (see the second finding), and R22 could not measure its effect. It should be
   re-derived, not revived.

## Reproducing this review

```
Code/.venv/bin/python -m simoscal.analysis Logs/BasicsGuide_R22   # battery
Code/.venv/bin/python Logs/BasicsGuide_R22/slot_attribution.py    # which slot ran when
Code/.venv/bin/python Logs/BasicsGuide_R22/analyze_r22_slots.py    # the experiment
Code/.venv/bin/python Logs/BasicsGuide_R22/analyze_octane_value.py # plain 92 vs dosed
Code/.venv/bin/python Logs/BasicsGuide_R22/plot_knock_by_slot.py    # the 2x2 knock figure
```

`slot_attribution.py` reads the slot curves off
`Tunes/MainTune/MainTune_out/R22_20260901-060746/Patched_259L_R22.bin`; retarget
`R22_BIN` if that run folder is rebuilt. `analyze_r22_slots.py` imports R19's
`knock_events` and `loaded_mask` unchanged, so its event rates are directly
comparable to the R19 and R20 reviews, and it rescores both of those sessions
from their own raw logs rather than quoting their published numbers.

Tool output this review is built on: `analysis_findings.md`,
`analysis_findings.json`, `plots/`.
