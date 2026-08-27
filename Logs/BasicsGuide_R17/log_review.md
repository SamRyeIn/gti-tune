# MainTune R17 log review

**Session:** 2026-08-26  
**Review:** 2026-08-26  
**Calibration named by every CSV:** `Patched_259L_R17.bin`  
**Authoritative candidate used for calibration-aware checks:**
`Tunes/MainTune/MainTune_out/R17_20260826-120335/Patched_259L_R17.bin`  
**Verdict:** R17 validates the Spark-IAT/guide-timing combination over most of
the pull, but it should not remain unchanged for further WOT work. Three
separate pulls repeat loaded knock in one narrow 4563–4973 rpm zone. Pull base
timing locally in that zone; do not change knock sensitivity or stack a boost,
wastegate, or fueling change into the same revision.

## Provenance and data quality

All seven CSVs use `Gear (gear)`, so their logged gear is the actual gear and no
offset was applied. Every file's metadata names `Patched_259L_R17.bin`; the
session began about 23 minutes after the authoritative R17 build completed. The
folder does not contain a human-dropped flashed-bin text record, so the CSVs
prove the filename but cannot independently prove the flashed file's SHA-256.

The deterministic battery parsed 3233 rows across seven files, found six
actual-3rd-gear pulls, resolved the calibration, ran all 11 checks with none
skipped, and found no gaps or stuck channels. `12_28_19` contains no qualifying
third-gear WOT pull; the other six files each contain a full sweep. Manual work
uses only rows where the logged gear remains 3 before quoting `Calc HP` or the
physics-derived power estimate.

Battery output: `analysis_findings.md`. Reproducible manual validation:
`analyze_r17_validation.py`.

---

## High — repeatable loaded knock clusters at 4563–4973 rpm

The battery reports one −3.0° event because it only elevates recurrence when the
same cylinder repeats. Manual review finds three settled, high-airmass events in
the same narrow engine-speed zone across three different pulls and two
cylinders, plus one separate spool event:

| File     | Cylinder | Onset rpm | Worst retard | IAT     | Airmass     | PUT error | Ign Avg / table |
| -------- | -------- | --------- | ------------ | ------- | ----------- | --------- | --------------- |
| 12_26_24 | 1        | 4830      | −3.0°        | 23.2 °C | 1508 mg/stk | −5.8 kPa  | −2.2 / −1.5°    |
| 12_29_45 | 4        | 4563      | −3.0°        | 25.1 °C | 1511 mg/stk | −3.6 kPa  | −3.4 / −2.6°    |
| 12_32_53 | 4        | 4973      | −3.0°        | 25.3 °C | 1480 mg/stk | −9.3 kPa  | −1.5 / −0.7°    |
| 12_30_30 | 1        | 3380      | −2.6°        | 33.3 °C | 1237 mg/stk | −43.1 kPa | −6.4 / −6.0°    |

Each row is one initial event followed by the ECU's normal correction decay; it
is not a count of repeated fresh detections throughout the pull. No pull has a
simultaneous multi-cylinder event, and two of the six full pulls remain clean.
Even so, three settled events within 410 rpm are not the source guide's
"sporadic, one cylinder, no rhyme or reason" case. They meet its other test:
consistent knock in a specific rpm range should be addressed by pulling timing
in that range. See `knowledge/ecu-tuning-not-the-basics.md` § Timing and knock
control.

This is also the exact validation risk recorded before the flash. R17 removed
R04's protection from the prior high-airmass knock region in all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps. At the cool 23–25 °C IAT of the three settled
events, the Spark-IAT family contributes little or no protective retard. R17's
mean delivered-minus-table correction is only −0.3 to −0.4° from 4000–5500 rpm,
compared with −1.4 to −2.0° in the much hotter R15 session.

Decision: make the next revision timing-only. Start from the R04-proven local
cells around 4500–5000 rpm and 1200–1400 mg/stk, apply the same smooth change to
all nine base maps, and validate it before changing another domain. Leave
`IP_KNKS_GAIN_PRE[0..3]` — Knock pre-window gain for cylinders 1–4,
`IP_IGA_DEC_KNK` — Spark retard at recognised knocking, and
`IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock
is detected unchanged so the factory protection continues to report and control
real events.

Evidence: `plots/r17_knock_events.png` and `plots/r17_vs_r15_validation.png`.

---

## Medium — four 3→4 shifts clear the old overboost question, but fuel headroom varies

Four pulls continue through the logged 3→4 transition and land around
4395–4472 rpm. All four keep boost below the +10 kPa watch line, resolving the
R14/R15 question about whether a shift into the boost shelf inherently
overboosts:

| File     | Landing rpm | Peak PUT | Peak PUT error | DI rail error | HPFP max | Pre-shift WG I |
| -------- | ----------- | -------- | -------------- | ------------- | -------- | -------------- |
| 12_26_24 | 4419        | 284.4 kPa| +4.7 kPa       | −24.5 bar     | 97.9 %   | +14.3 %        |
| 12_30_30 | 4440        | 285.1 kPa| +7.2 kPa       | −17.2 bar     | 98.7 %   | +16.2 %        |
| 12_32_53 | 4472        | 282.6 kPa| +7.0 kPa       | −7.7 bar      | 97.2 %   | +14.9 %        |
| 12_34_25 | 4395        | 288.0 kPa| +9.3 kPa       | −8.3 bar      | 99.2 %   | +16.9 %        |

The worst rail response, −24.5 bar, stops just above the battery's −25 bar High
line, while a different shift reaches 99.2 % HPFP effective volume. Lambda's
large lean readings during the torque interruption are fuel-cut transients and
recover to target as combustion returns. The result removes the case for a
wastegate/overboost correction but reinforces the existing no-more-boost
decision: shift fuel headroom is not consistent enough to spend.

Evidence: `plots/r17_worst_upshift.png`.

---

## Low — the battery's lambda High is a spool-target transition, not steady lean operation

The battery median-smooths a +0.057 lambda error at 3112 rpm in `12_28_41` and
labels it High. The raw event is one 0.04-second sample at 0.984 actual versus
0.904 requested while PUT remains 53.5 kPa below target. A second pull has a
two-sample, 0.08-second event at 0.974 versus 0.904 while PUT is 35.3 kPa below
target. DI rail pressure is 1.3–1.6 bar above request at both events, and lambda
immediately crosses rich as boost and the rapidly moving target converge.

Across fixed 500-rpm loaded bands, R17 mean lambda error stays between −0.006
and +0.003. The 6000–6500 rpm band averages 0.801 actual versus 0.800 requested.
This does not support changing `IP_LAMB_BAS_HPDI[1]` — Basic lambda setpoint
grid, HPDI (direct injection), or any lambda floor.

Evidence: `plots/r17_lambda_event.png` and `plots/analysis_lambda.png`.

---

## Low — boost, steady fuel pressure, turbo speed, and limiters remain controlled

- Mean PUT error stays between −7.8 and −0.1 kPa in every 500-rpm band. The
  battery's +12.3 kPa maximum is a one-sample spool transient; no sustained
  overboost zone appears.
- During clean third-gear operation, worst DI rail error is −4.6 bar, HPFP
  effective volume peaks at 97.2 %, and LPFP duty peaks at 81.9 %. The shifts
  above remain the fuel-system edge case.
- Turbo speed peaks at 205 krpm against the 220 krpm working ceiling. Peak
  pressure quotient is approximately 2.88 against the 3.1 cap in
  `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor.
- Logged PUT-minus-ambient retains 795 hPa margin to
  `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold.
- `Torque Lim` remains 0 throughout loaded WOT. Misfires remain 0.

---

## Timing and performance context

R17's six full pulls are internally consistent, but the comparison with R15 is
not back-to-back: R17 averages roughly 15 °C cooler at the intake. The timing
change and cooler air move in the same direction, so their individual shares
cannot be separated from these logs.

| RPM band  | R15 table | R17 table | R15 delivered | R17 delivered | R17 delivered − table |
| --------- | --------- | --------- | ------------- | ------------- | --------------------- |
| 3500–4000 | −7.7°     | −5.7°     | −10.1°        | −6.6°         | −0.9°                 |
| 4000–4500 | −5.3°     | −3.8°     | −6.8°         | −4.0°         | −0.3°                 |
| 4500–5000 | −3.0°     | −1.8°     | −4.4°         | −2.1°         | −0.3°                 |
| 5000–5500 | −1.2°     | +0.0°     | −3.2°         | −0.4°         | −0.4°                 |
| 5500–6000 | +0.7°     | +1.3°     | −1.1°         | +0.7°         | −0.6°                 |
| 6000–6500 | +2.6°     | +2.3°     | +1.2°         | +1.8°         | −0.5°                 |

Using the same actual-gear-trimmed F=ma road method as the R14/R15 reviews, R17
estimates 244–257 wheel hp across six pulls, mean 252 wheel hp. R15 estimated
227–235, mean 230 wheel hp. Trimmed `Calc HP` reaches 299–307 hp in R17 versus
287–300 hp in R15. The roughly 22-wheel-hp directional gain is credible because
all six R17 curves move together, but it is a road estimate under cooler
conditions, not a dyno-isolated timing delta.

The performance gain does not overrule the knock evidence. Preserve the clean
parts of the guide surface and correct the repeatable 4500–5000 rpm pocket.

Evidence: `plots/r17_vs_r15_power.png` and
`plots/r17_vs_r15_validation.png`.

---

## Next-revision gate

R17 has enough evidence to unblock a narrowly scoped R18 timing correction, not
a broader calibration change:

1. Pull base timing smoothly in the 4500–5000 rpm / 1200–1400 mg/stk region in
   all nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle,
   VVL 0 port-flap-low cam-position maps.
2. Keep the R17 Spark-IAT family, boost, wastegate, lambda, pump, limiter, and
   knock-control calibrations byte-identical so the next logs isolate the local
   timing correction.
3. ~~Re-log one controlled actual-3rd-gear pass through 4300–5200 rpm first.
   Only continue to a redline pass if that zone is clean.~~ **Superseded
   2026-08-27 during the R18 script review.** This step was more conservative
   than the evidence above supports: three isolated, settled, single-cylinder
   −3.0° events that decayed normally, on two different cylinders, in two of six
   pulls, with `IP_KNKS_GAIN_PRE[0..3]` — Knock pre-window gain for cylinders
   1–4 and the knock-correction calibrations at stock, alongside misfires 0,
   `Torque Lim` 0, lambda holding 0.80 under load, and turbo speed 205 of
   220 krpm. That is factory knock control working as designed, not an
   engine-damage signature, and it does not warrant holding the car short of
   redline. Validate R18 with normal full actual-3rd-gear pulls to redline; the
   stop/rollback signals are a change in character — simultaneous
   multi-cylinder retard, retard that ramps instead of decaying, or loss of
   lambda or fuel-pressure control — not the recurrence of a settled
   single-cylinder event.

Until that correction is built and human-reviewed, do not use R17 for more WOT
validation. R16 remains superseded and must not be substituted; it requested
still more high-rpm base timing.
