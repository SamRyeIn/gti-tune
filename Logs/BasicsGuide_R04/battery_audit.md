# Battery audit — independent review vs `simoscal.analysis` on Logs/BasicsGuide_R04

**Method.** A blind review of `simostools-2026_07_08-22_10_57.csv` was computed straight
from the raw CSV (numpy, scripts in the session scratchpad) *before* opening
`analysis_findings.{json,md}` or `plots/`. The battery output was then compared
point-by-point, and every disputed claim was re-verified against the raw data.
Gear header is `Gear (gear)` → actual gear, no offset (battery agrees: gear mode
`actual`). All numbers below are reproducible from the CSV.

## 1. Independent (blind) findings

Log: 2028 rows, 81.1 s, 25 Hz, no gaps. Two WOT pulls (pedal > 80 %), both with a
3→4 upshift (6674 / 6312 rpm).

| #  | Severity    | Finding                                                                                                                                                                                                        |
|----|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| F1 | Medium-High | Boost overshoot in **two zones**: spool spike +19.3 / +22.2 kPa at 3224–3447 rpm (~0.25 s each) AND sustained top-end +10…+17 kPa for ~1 s at 6048–6483 rpm with the WG integral clamped at −29.5 %.            |
| F2 | Medium      | `Torque Lim ()` = 64 on 246 WOT samples (3102–5821 rpm), coinciding with Ign Avg pulled to −6…−8.6° at 3105–3344 rpm while knock = 0 — a torque-model intervention, not knock.                                  |
| F3 | Medium      | All four knock channels + Knock Avg are bit-identical 0.00 on every sample. Face value: the R04 overlay worked (R01 logs showed −3.0°). But a whole-log constant warrants a PID-liveness check before crediting. |
| F4 | Medium-Low  | HPFP Eff Vol peaks 93.8 % / 95.8 %; DI rail dips −650 kPa below the 20 001 kPa SP (~3 %) above 6600 rpm. Little fueling headroom left.                                                                          |
| F5 | Low / info  | Lambda healthy: SP clamps at exactly 0.800 (R03 floors active), actual tracks rich of SP (WOT min 0.775). The lambda→2.0 "lean" samples are the upshift fuel cut (Inj PW DI = 0, negative torque) — benign.     |
| F6 | Low / info  | `Turbo Speed (rpm)` max 183.6 — the header unit is wrong; the channel is krpm (≈183 600 rpm).                                                                                                                    |
| F7 | Info        | Airmass 1.48 g/stk vs SP 1.60 — setpoint unmet, consistent with F1/F2. Not clamped by `C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint (< 2.0 ceiling).                                                   |
| —  | Clean       | Temps (coolant 97.7, oil 107, IAT 29.3 °C), misfires 0, STFT ±7 %, battery ≥ 14.0 V, DV 0 % at top end.                                                                                                          |

Also notable: PUT max 286.4 kPa at 101.3 kPa ambient = **1851 hPa differential — above
the stock 1800 hPa** `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overpressure upstream throttle
threshold for turbocharger overpressure diagnosis (P0234). This log is direct evidence
for the R06 raise to 2700.

## 2. Where the battery is right (verified agreements)

| Battery finding                                            | Verdict                                                                                        |
|------------------------------------------------------------|------------------------------------------------------------------------------------------------|
| Boost High: +22.2 kPa peak near 3328 rpm (pull 2)          | ✓ Matches F1's spool spike (my window 3279–3447 rpm, peak +22.2).                              |
| Knock clean 0.0                                            | ✓ Numerically correct (see improvement #4 on the missing liveness caveat).                     |
| Lambda: settled-WOT max lean +0.023, below watch           | ✓ Matches F5. The `settled_torque_min_nm=250` mask correctly suppresses shift-cut artifacts — good design; a naive check would have false-flagged lambda 2.0. |
| Rail pressure: sag −6.5 bar, LPFP 79.9 %, HPFP 95.8 %      | ✓ Exact match with my numbers.                                                                 |
| Turbo/temps OK, turbo 184 krpm                             | ✓ Matches; the krpm interpretation resolves F6 correctly.                                      |
| Torque limiter code 64 surfaced                            | ✓ Present (246–241 samples; see improvement #3 — it stops one step short of the story).        |
| Data quality: 0 gaps, 40 ms, gear mode actual, 2 pulls     | ✓ Pull row ranges match my independently-detected windows.                                     |
| Pull summary / environment context / coverage maps         | ✓ Valuable context I did not produce; numbers spot-checked correct.                            |

## 3. Where the battery is wrong or short (each re-verified in the raw data)

### 3.1 Wastegate finding is incorrect (Medium finding, wrong causality) — worst defect
Battery: *"final wastegate command saturates at 100.0 % while boost still overshoots —
little closed-loop headroom to pull boost down."*
Raw data: **zero samples** have WG Pos Final ≥ 99 % while PUT−SP > +10 kPa. WG hits 100 %
only during spool (PUT −122…−11 kPa **under** SP — normal gate-closed spooling) and
off-throttle. During the actual top-end overshoot (rpm > 5800, err > +5) WG Final is
28–56 %. The code (`checks.py` `_check_wastegate`) takes per-log maxima of two separate
things (any-pull saturation, any-pull overshoot) and asserts co-occurrence. Direction is
also inverted: 100 % = closed, so saturation *at closed* limits boost-raising, not
boost-cutting. Meanwhile the real closed-loop-headroom signal — `WG I Value (%)` integral
clamped at −29.5 % during the overshoot — is in the log and unused by any check.

### 3.2 Boost check reports only the global peak, hiding the actionable zone
The message names a single peak (+22.2 kPa, 3328 rpm). The sustained top-end zone
(mean +10…+12, peak +17 kPa for ~1 s at 6048–6483 rpm) — the zone R05's overlay targeted,
and the one where the controller is out of authority — never appears in the finding text
or evidence, even though the check's own description promises "overshoot bands and
peaks" and its own plot shows both zones clearly. A 0.25 s transient spike and a 1 s
saturated ridge are different problems; severity-by-instantaneous-peak ranks them
backwards.

### 3.3 Timing + torque-limiter checks each hold half of one story, and the timing text misdirects
Timing says "cross-reference the knock finding for local pull-back" — but knock is 0.0;
knock cannot explain the −9.4° floor. The explanation is in the battery's *other*
finding: the code-64 torque-limiter windows coincide exactly with the −6…−8.6° pull at
3105–3344 rpm (and with the spool overboost spike). Neither finding links to the other.
Also the timing envelope max (+4.5°) is not reproducible from obvious masks (WOT &
torque > 250 Nm gives −9.4…+9.4°; raw pull rows give max +13.5°) and the mask used is not
stated in the message or evidence.

### 3.4 `boost_cal` has a 10× unit error and checks the wrong quantity
Message: "peak 285.4 kPa stays under the `C_PRS_IM_SP_MAX` ceiling 350000.0 kPa (margin
349714.6 kPa)". The symbol stores **hPa** (350000 hPa = 35000 kPa), so the printed
ceiling and margin are 10× off and labeled with the wrong unit. Conceptually it compares
logged *actual* MAP against a *setpoint* ceiling (the registry even declares `put_sp`
required while the code reads `map`/`put`) — the meaningful question is how close the
demanded setpoint runs to its clamp.

### 3.5 Knock "clean" carries no liveness caveat
All knock channels are constant 0.00 across 2028 samples (nunique = 1; LTFT, Eth,
Cruise likewise constant). The frozen-channel preflight deliberately checks only
`_DYNAMIC_CHANNELS` (rpm, airmass, put, …) — correct as designed — but the knock check
then credits "clean" with no note that the channel never moved at all, on the very
revision whose overlay is being validated. One dead PID would look identical to success.

### 3.6 Missed cal-aware check: the P0234 threshold this log actually crossed
PUT−ambient hit 1851 hPa vs the stock 1800 hPa `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` —
Overpressure upstream throttle threshold (the R04 bin still had stock). A `needs_cal`
check comparing logged PUT−ambient against this table would have produced the single
most decision-relevant calibration finding available in this log (it motivated R06).

## 4. Concrete improvement recommendations (ranked)

1. **Fix `_check_wastegate` co-occurrence** — evaluate saturation and overshoot on the
   same samples (e.g. any sample with WG ≥ 99 % AND PUT−SP ≥ watch), and split the two
   real findings: (a) saturation-while-under-SP = spool authority info; (b) overshoot
   with `wg_i` at its clamp = closed-loop out of authority (use `WG I Value (%)` /
   `WG P-D Value (%)`, already in the log, currently unused).
2. **Zone/band the boost check** — report contiguous regions above the watch line with
   rpm span, duration, mean and peak error (transient spike vs sustained ridge), and
   weight severity by duration-above-watch, not instantaneous peak alone.
3. **Correlate torque-limiter windows** — when `torque_lim` ≠ 0 during settled WOT,
   report overlap with timing retard and boost error (all channels already parsed); in
   the timing finding, only point at knock when knock is actually nonzero, and state the
   sample mask (and put it in evidence) so the envelope numbers are reproducible.
4. **Add a constant-channel caveat to knock** — when every knock sample is exactly 0.00
   across a log containing WOT pulls, append "channel never deviated from 0.00 — verify
   PID liveness after any PID-list change" instead of an unqualified "clean".
5. **Fix `_check_boost_cal` units and quantity** — convert the symbol's hPa to kPa
   (or print hPa), compare the *setpoint* peak (`put_sp`/`map_sp`) against the ceiling,
   and align the registry's declared channels with what the code reads.
6. **Add a P0234 cal-aware check** — logged max(PUT − ambient) vs
   `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overpressure upstream throttle threshold, with
   margin in hPa.
7. Minor: pull-summary `Gear` column should list all gears in the pull (both pulls shift
   3→4) or trim pulls at the shift; consider an HPFP watch nearer 95 % (two pulls at
   93.8 / 95.8 % read as "OK" against the 98 % line); note the krpm normalization of
   `Turbo Speed (rpm)` somewhere user-visible since the CSV header unit is wrong.

## 5. Bottom line

The battery's numbers are trustworthy (every agreed value matched the raw data exactly),
pull detection and data-quality preflight are solid, and the lambda shift-cut masking is
genuinely good design. Its weaknesses are *cross-channel reasoning*: the one finding that
asserted causality across channels (wastegate) is factually wrong on this log, the two
halves of the torque-intervention story sit in separate findings, and the single
calibration-aware check has a unit bug while the most valuable cal comparison (P0234) is
missing. Items 1–5 are correctness fixes; 6 is the highest-value new check.
