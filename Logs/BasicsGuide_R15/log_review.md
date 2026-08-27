# BasicsGuide_R15 Log Review

Living review document for the R15 flash, logged as
`CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R15.bin`. All seven CSV headers carry
that exact calibration tag. Reading the flashed R14 and R15 bins confirms the
R15 delta is exactly the intended five cells in each of
`IP_FAC_BPA_SP[0]` / `IP_FAC_BPA_SP[1]` — Wastegate Position Feedforward,
VVL 0 / VVL 1; every other calibration table is unchanged by design.

## 2026-08-25: R15 validation review — slot 4

Analysis battery:
`Code/.venv/bin/python -m simoscal.analysis Logs/BasicsGuide_R15` — seven
files, six detected pulls, calibration resolved, all checks ran, **no skips**.
The deterministic output contains five Medium and four Low findings, with no
High findings. See `analysis_findings.md`, `analysis_findings.json`, and
`plots/analysis_*.png`.

The folder initially lacked its required `*.bin.txt` record. Adding the flashed
filename allowed the calibration-aware checks and all five coverage maps to
resolve. Follow-up analysis is reproducible with
`analyze_r15_validation.py`; it writes:

- `plots/r15_vs_r14_validation.png` — clean actual-3rd-gear R14→R15 comparison.
- `plots/r15_worst_upshift.png` — the worst shift edge omitted by pull segmentation.
- `plots/r15_knock_events.png` — both loaded-WOT knock events, including the
  post-shift event omitted by pull segmentation.

### Reviewed files

| File (simostools-2026_08_25-…) | Rows | WOT n | Gears at WOT | RPM at WOT | Notes                                                   |
|--------------------------------|------|-------|--------------|------------|---------------------------------------------------------|
| 11_20_54                       | 1202 | —     | —            | —          | Road operation; no WOT pull.                            |
| 11_35_28                       | 699  | 181   | 3, 4         | 2964–6078  | Full 3rd; cylinder-1 knock; worst 3→4 shift edge.       |
| 11_37_30                       | 548  | 199   | 3            | 2801–6522  | Full clean 3rd; brief lean reading during initial spool.|
| 11_40_04                       | 834  | 175   | 2, 3         | 3350–6703  | Full 2nd→3rd; cylinder-2 knock after shift recovery.    |
| 11_41_12                       | 878  | 196   | 3, 4         | 3281–6475  | Full clean 3rd into a 3→4 shift.                        |
| 11_42_33                       | 490  | 190   | 3, 4         | 3052–6442  | Full clean 3rd into a 3→4 shift.                        |
| 11_43_50                       | 528  | 165   | 3, 4         | 3728–6574  | High-rpm 3rd into a short 3→4 shift.                    |

Gear note: the header is `Gear (gear)` = actual gear numbering, **no offset**.
Any performance comparison is trimmed to rows whose rounded gear equals the
pull's attributed gear, so the DSG's early gear-channel flip cannot inflate
`Calc HP` or `Calc TQ`.

Data quality is good: 39–40 ms sampling, zero gaps, no stuck safety channels,
zero misfires, and `Torque Lim` = 0 for all 1,106 WOT samples. Ambient was
21.8–24.8 °C at 101.2–101.3 kPa. IAT reached 47 °C, coolant 101 °C, and oil
113 °C. This was a materially hotter validation than R14.

---

## Headline: R15 works and should stand; do not close the wastegate further

The five-cell walk-back in `IP_FAC_BPA_SP[0]` / `IP_FAC_BPA_SP[1]` —
Wastegate Position Feedforward does what it was sized to do. Clean 3rd-gear
tracking improved throughout the shelf and taper, the wastegate integral burden
fell, and steady fuel-pressure headroom improved despite substantially hotter
conditions.

| RPM band  | R14 error | R15 predicted | R15 measured | WG I, R14→R15 | HPFP max, R14→R15 |
| --------- | --------- | ------------- | ------------ | ------------- | ----------------- |
| 3500–4000 | −5.5 kPa  | −2.9 kPa      | −1.8 kPa     | +0.7→+0.9 %   | 96.8→95.3 %       |
| 4000–4500 | −10.4 kPa | −7.2 kPa      | −4.2 kPa     | +3.5→+2.8 %   | 97.7→95.0 %       |
| 4500–5000 | −6.5 kPa  | −4.1 kPa      | −2.2 kPa     | +6.5→+4.8 %   | 96.1→95.0 %       |
| 5000–5500 | −7.9 kPa  | −4.5 kPa      | −6.2 kPa     | +11.5→+8.0 %  | 94.0→90.5 %       |
| 5500–6000 | −5.5 kPa  | −2.0 kPa      | −3.2 kPa     | +15.4→+11.9 % | 83.4→80.2 %       |
| 6000–6500 | −1.0 kPa  | +1.4 kPa      | +3.0 kPa     | +17.8→+12.5 % | 74.5→72.4 %       |

The 4000–4500 rpm shortfall improved from 1.5 psi to 0.6 psi. The result crosses
to a mild 0.4 psi over-target mean at 6000–6500 rpm, but +3.0 kPa is well below
the +10 kPa watch line and the worst settled redline event is a brief +11.2 kPa
for 0.08 s. The closed loop still carries +12.5 % integral near redline, but it
is down 5.3 points from R14 and final command remains around 72 %, with ample
actuator authority.

R15 therefore meets its purpose. A further feedforward closure would trade the
remaining modest mid-taper shortfall for more redline and shift overshoot. Hold
the wastegate maps here.

Evidence: `plots/r15_vs_r14_validation.png` and
`plots/analysis_wastegate.png`.

---

## Medium 1 — two −3.0° knock events recur in the same 4600–4750 rpm load zone

The battery reports only the first event because its pull segmentation ends the
2nd-gear pull at the 2→3 shift and does not create a second pull for the
post-shift 3rd-gear segment. Manual review finds two genuine loaded-WOT events:

| File     | Context                   | Cylinder | Onset | IAT     | Airmass     | PUT error | Ign Avg / table |
| -------- | ------------------------- | -------- | ----- | ------- | ----------- | --------- | --------------- |
| 11_35_28 | Steady 3rd gear           | 1        | 4596  | 41.4 °C | 1465 mg/stk | −1.5 kPa  | −5.25 / −3.38°  |
| 11_40_04 | Recovered after 2→3 shift | 2        | 4751  | 41.8 °C | 1464 mg/stk | −2.5 kPa  | −4.88 / −3.00°  |

Each event steps once to −3.0° and then decays toward zero; neither shows
repeated fresh knock at high rpm. Cylinders 3 and 4 remain clean. The shared
RPM, load, IAT, and approximately −1.9° delivered-versus-table correction make
this a local warm/high-load susceptibility, not a random redline event. R15 did
not change timing, so this is a condition exposed by the hotter session rather
than a regression caused by its wastegate-table edit.

Decision: do not add base timing in the 4500–5000 rpm zone. Any future IAT
correction change that removes retard around 42 °C must preserve margin here and
be validated specifically through this band.

Evidence: `plots/r15_knock_events.png`.

---

## Medium 2 — the worst WOT 3→4 shift is improved from R14, but still consumes fuel headroom

In `11_35_28`, the engine enters the 3→4 shift carrying about +15 % wastegate
integral. The gate closes to 100 % through the torque cut, boost rebuilds to
294.6 kPa absolute, and the high-pressure fuel system briefly approaches its
limit:

| Quantity                   | R14 worst shift | R15 worst shift |
|----------------------------|-----------------|-----------------|
| Peak `PUT`                 | ≥300.6 kPa      | 294.6 kPa       |
| Peak `PUT` − setpoint      | +19.7 kPa       | +13.7 kPa       |
| Peak gauge boost           | ≥28.9 psi       | 28.0 psi        |
| HPFP effective volume      | 100.0 %         | 99.0 %          |
| Worst DI rail error        | −26.2 bar       | −16.3 bar       |
| Peak airmass               | 1692 mg/stk     | 1574 mg/stk     |
| Turbo speed                | —               | 205 krpm        |
| Torque-limiter activity    | none            | none            |

Unlike R14, `PUT` does not rail, the overshoot remains below the +20 kPa High
line, and rail error remains above the −25 bar High line. Lambda shows the
normal fuel-cut excursion during the torque interruption, then recovers rich of
target; it does not run lean while boost rebuilds. This is a material
improvement, but 99 % HPFP effective volume and −16.3 bar leave little margin
for more boost through an ordinary WOT shift.

Decision: no additional boost or wastegate closure until this shift edge is
re-logged under any future airflow-increasing change.

Evidence: `plots/r15_worst_upshift.png`.

---

## Medium 3 — turbo speed reaches 213 krpm in 2nd gear

The session peak is 213 krpm against the working 220 krpm ceiling, leaving only
7 krpm or about 3 % margin. That peak belongs to the fast 2nd-gear pull in
`11_40_04`; clean 3rd-gear pulls peak at 207 krpm. R14 peaked at 205 krpm.
There is no limiter activity or sustained boost overshoot at the peak, but the
margin is narrow enough that further boost is not justified.

---

## Low — lambda, steady fuel pressure, and limiters remain controlled

- The battery's +0.0415 settled-lambda watch comes from the initial spool of
  `11_37_30`: two raw samples over 0.08 s read +0.072 and +0.037 while `PUT`
  was still 33→23 kPa below target and the lambda target was moving rapidly.
  It immediately reverses rich. Every 500-rpm clean-pull band averages within
  0.005 of target, including 0.801 / 0.800 at 6000–6500 rpm. This is a spool
  transition, not evidence for a fuel-table change.
- Normal clean-pull DI rail error stays within −8.6 bar. HPFP effective volume
  peaks at 95.3 %, improved from R14's 97.7 %, while LPFP duty peaks at 82.8 %.
  The high-pressure side remains the constraint, but it holds in steady state.
- `Torque Lim` remains 0 throughout WOT. Peak measured compressor pressure
  quotient is 2.88 against the 3.1 cap in `IP_PQ_CHA_MAX` — Maximum allowed
  pressure quotient at turbo charger compressor.
- `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold
  retains at least 801 hPa margin to the P0234 threshold in detected pulls.
- Zero misfires; ethanol 0.0 %; LTFT remains approximately +0.8 %.

---

## Timing and performance context for the next revision

R15's clean 3rd-gear samples averaged about 16 °C hotter at the intake than R14.
Delivered timing consequently sat well below the unchanged table request:

| RPM band  | R15 Ign Avg | R15 Ign Table | Delivered − table | Mean IAT |
|-----------|-------------|---------------|-------------------|----------|
| 3500–4000 | −10.1°      | −7.7°         | −2.4°             | 43.0 °C  |
| 4000–4500 | −6.8°       | −5.3°         | −1.5°             | 42.3 °C  |
| 4500–5000 | −4.4°       | −3.0°         | −1.4°             | 41.3 °C  |
| 5000–5500 | −3.2°       | −1.2°         | −2.0°             | 40.5 °C  |
| 5500–6000 | −1.1°       | +0.7°         | −1.8°             | 39.9 °C  |
| 6000–6500 | +1.2°       | +2.6°         | −1.4°             | 39.6 °C  |

The same F=ma method used in the R14 review, with actual-gear trimming, estimates
R15's five full 3rd-gear pulls at 227–235 wheel hp (mean 230) versus R14's three
full clean pulls at 244–254 wheel hp (mean 249). This is a road estimate, not a
dyno comparison, and the sessions are not back-to-back. Still, its direction
matches the logged timing loss while boost and lambda remain on target.

Decision for the next revision: R15's wastegate change stands. The logs support
evaluating the Spark IAT correction independently, but they do **not** support
stacking a base-timing advance into the same revision. In particular, preserve
the 4500–5000 rpm margin where both fresh knock events began; log the IAT-only
effect before considering a separate high-RPM base-timing change.

Evidence: `plots/r15_vs_r14_validation.png` and
`plots/analysis_ignition.png`.
