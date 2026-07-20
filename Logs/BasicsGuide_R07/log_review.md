# BasicsGuide_R07 Log Review

Living review document for `5G0906259L_0002_BasicsGuide_R07.bin` flash logs. R07 is the R06 calibration on a **patched bin** (CBRICK + HSL + 5-slot switch patch) with the switch-patch traction control enabled on all five slots. The initial patch installation required a full flash; later matching-patch tune updates are CAL-flash eligible.

## 2026-07-12: R07 Validation Review (boost tracking + first TC-active logs)

Analysis battery: `python -m simoscal.analysis Logs/BasicsGuide_R07 --bin <R07 bin>` — all 11 checks ran (cal resolved), no skips. See `analysis_findings.md` / `.json` and `plots/analysis_*.png`.

### Reviewed Files

| File                                  | Gear   | Notes                                                        |
|---------------------------------------|--------|--------------------------------------------------------------|
| `simostools-2026_07_12-16_02_51.csv`  | 3rd    | Clean WOT pull 2654–6434 rpm.                                |
| `simostools-2026_07_12-16_04_31.csv`  | 2nd    | WOT pull; spool-transient overshoot, kept out of FF tuning.  |
| `simostools-2026_07_12-16_05_57.csv`  | 3rd    | Clean WOT pull 2527–5515 rpm.                                |
| `simostools-2026_07_12-16_07_36.csv`  | 3rd    | Clean WOT pull 2598–6462 rpm; one −3.0° knock event.         |
| `simostools-2026_07_12-16_10_06.csv`  | —      | Short fragment, no full pull.                                |
| `simostools-2026_07_12-16_10_19.csv`  | 2nd    | **TC-contaminated** — excluded from calibration conclusions. |

Gear note: these logs use `Gear (gear)` = actual gear numbering; no offset applied.

### Main Findings

High — Boost tracking (top end): Needs revision → **drives R08.** The three clean 3rd-gear pulls track PUT within about ±5 kPa from 3300–5800 rpm (the R05 wastegate feedforward overlay resolved the R04 mid-range overshoot), but above ~5800 rpm a sustained overshoot remains: mean +8.5 kPa, max +15.1 kPa, worst in the 6200–6700 rpm band at +10.6 kPa mean. The wastegate integral only works down to about −16% (headroom, not saturated — feedforward is short, the loop is slow). Key structural finding: the flow-factor trajectory is a hysteresis loop — Exh flow factor peaks ~1.33 at 5200–5800 rpm (tracking good there, −2.4 kPa) and falls back to ~1.10 by 6200–6700 rpm (worst overshoot), so the good and bad regions overlap in Exh-flow space and are separated by the **intake** flow factor row instead (worst band at Int ~1.04, i.e. 93% weight on the Int 1.05 row).

High — Lambda (pull 5 only): **Attributed to TC, not fueling.** The battery's settled-WOT lean finding (+0.064) comes entirely from the TC-contaminated 2nd-gear pull; the lean tails sit on TC torque-cut/recovery transients at ~5700 and ~6300 rpm. The three clean 3rd-gear pulls hold lambda within about ±0.03 of setpoint throughout. No fueling change indicated.

Medium — Switch-patch TC first field test: **Works.** Pull 5 (2nd gear) shows front-vs-rear wheel-speed deltas up to 11.5 km/h at ~5400–5600 rpm with torque cut from ~410 Nm requested to 220–290 Nm delivered, plus the corresponding boost dips. This is the switch-patch slip-based TC intervening on real wheelspin. Driver-feel review (too aggressive / too soft) is Sam's call; TC behaviour tables remain at patch defaults.

Medium — Knock retard: One event to −3.0° on one cylinder in pull 4; all other loaded-WOT rows clean at 0.0°. Not systematic; watch in R08 logs.

Medium — Fuel system headroom: Watch only. Worst DI rail sag −15.7 bar; LPFP duty peaks 82.3%; HPFP effective volume peaks 94.7% (approaching the 95% watch line). Track as load grows.

Medium — Turbo / heat: OK. Turbo speed peaks 192 krpm (below the 220 krpm revised limit); IAT ≤ 38 °C; coolant ≤ 101 °C; oil ≤ 111 °C.

Low — Torque Limit Source = 64: **Expected, benign.** Code 64 = "temporary torque limitation at maximum absolute charge air pressure setpoint" (bitmask readout, `knowledge/ecu-tuning-basics.md`). Active ~3–5 s per pull through 3100–5900 rpm with requested torque 375–450 Nm; delivered torque does not collapse and PUT keeps tracking `IP_PUT_SP`  — Boost pressure setpoint. On a tune with raised load targets this flag is the normal WOT steady state: the boost setpoint curve is the binding constraint, as intended.

Low — Overboost margins: Peak PUT-minus-ambient 1781 hPa vs the 2700 hPa threshold in `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  — Overpressure upstream throttle threshold for turbocharger overpressure diagnosis (P0234): 918 hPa margin. Demanded setpoint far below `C_PRS_IM_SP_MAX`  — Maximum requested intake-manifold pressure setpoint.

### Evidence Plots

| Plot                             | Finding Supported                                        |
|----------------------------------|----------------------------------------------------------|
| `plots/analysis_boost.png`       | Mid-range tracking fixed; top-end overshoot; pull 5 dips. |
| `plots/analysis_wastegate.png`   | WG integral has headroom (−16% min) — FF short, not saturated. |
| `plots/analysis_lambda.png`      | Clean-pull lambda within ±0.03; pull 5 TC tails.          |
| `plots/analysis_knock.png`       | Single −3.0° event in pull 4.                             |
| `plots/analysis_rail_pressure.png` | Fuel headroom watch values.                             |
| `plots/analysis_turbo_heat.png`  | Turbo speed / IAT / coolant / oil peaks.                  |

### Disposition

Findings feed **R08** — top-end wastegate feedforward deepening in `IP_FAC_BPA_SP[0]` / `IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward VVL 0/1: six cells on the Int 0.90/1.05/1.25 × Exh 1.00/1.40 corner, row-weighted onto the Int 1.05 row (−0.06 at Exh 1.00, −0.04 at Exh 1.40, light −0.02 Int 0.90 fringe, mirrored Int 1.25 blend). Simulated ECU bilinear lookup over the clean-pull WOT points: −5.2% WG position in the worst band (~70% of the guide's 0.05/psi rule), −3.3 to −3.9% adjacent (absorbed by idling I-terms), zero below 3300 rpm. See `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R08.py` and REV_LOG.
