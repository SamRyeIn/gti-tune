# BasicsGuide_R08 Log Review

Living review document for `5G0906259L_0002_BasicsGuide_R08.bin` flash logs. R08 is R07 (patched bin + TC) plus the top-end wastegate feedforward deepening: six cells lowered in `IP_FAC_BPA_SP[0]` / `IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward VVL 0/1, row-weighted onto the Int 1.05 flow-factor row. The initial patch installation required a full flash; this matching-patch tune update is CAL-flash eligible.

## 2026-07-12: R08 Validation Review (did the top-end FF deepening work?)

Analysis battery: `python -m simoscal.analysis Logs/BasicsGuide_R08 --bin <R08 bin>` — all 11 checks ran (cal resolved), no skips. See `analysis_findings.md` / `.json` and `plots/analysis_*.png`.

### Reviewed Files

| File                                  | Gear | Notes                                                          |
|---------------------------------------|------|----------------------------------------------------------------|
| `simostools-2026_07_12-17_31_01.csv`  | —    | No full pull.                                                  |
| `simostools-2026_07_12-17_33_07.csv`  | 3rd  | Clean WOT pull 2840–6308 rpm.                                  |
| `simostools-2026_07_12-17_34_21.csv`  | 3rd  | Clean WOT pull 3029–6213 rpm.                                  |
| `simostools-2026_07_12-17_35_58.csv`  | 3rd  | Clean WOT pull 2878–6482 rpm.                                  |
| `simostools-2026_07_12-17_38_18.csv`  | 1st  | Short 1st-gear burst; +46 kPa headline is a lift-off artifact. |
| `simostools-2026_07_12-17_39_41.csv`  | 2nd  | 2nd-gear pull; kept out of boost-FF conclusions.               |

Gear note: `Gear (gear)` = actual gear numbering; no offset applied.

### Headline: the R08 wastegate change was DELIVERED but the top-end error did not move

Band comparison, clean 3rd-gear pulls, R07 baseline → R08 (mean PUT error, kPa):

| Band (rpm) | R07 err | R08 err | R07 WG-I | R08 WG-I | R07 WG final | R08 WG final |
|------------|---------|---------|----------|----------|--------------|--------------|
| 3300–4500  | +3.0    | +0.2    | −2.2%    | −1.5%    | 61.2%        | 62.9%        |
| 4500–5200  | −1.8    | −2.6    | −6.0%    | −3.1%    | 56.9%        | 57.5%        |
| 5200–5800  | −2.4    | −2.6    | −4.2%    | −0.3%    | 55.6%        | 57.2%        |
| 5800–6200  | +6.6    | +6.6    | −4.7%    | −0.5%    | 46.9%        | 49.2%        |
| 6200–6700  | +10.6   | +9.9    | −11.9%   | −7.1%    | 35.7%        | 38.1%        |

The mechanism worked exactly as designed: the wastegate final position opened ~2.4% more at the top end and the integral relaxed by almost exactly the simulated feedforward contribution (−4.7 → −0.5 and −11.9 → −7.1). But PUT error above 5800 rpm is unchanged. **Opening the gate more does not reduce the top-end overshoot — the wastegate-position lever has no remaining authority there.** Conclusion: the residual +7–10 kPa (~1–1.5 psi) is boost failing to *bleed down* as fast as the falling `IP_PUT_SP`  — Boost pressure setpoint down-ramp toward redline (a rate/lag effect), not a feedforward level error. Deeper FF cells would only sag the well-tracking 4500–5800 region.

### Main Findings

High — Boost tracking (top end): Structural conclusion above. **Do NOT deepen `IP_FAC_BPA_SP` further for this.** R09 options: (a) soften the `IP_PUT_SP` top-end down-ramp so the commanded setpoint falls at a rate the plant can physically track (actual boost would be nearly unchanged — the "error" is largely definitional against an untrackable ramp), or (b) accept it: margins are wide (933 hPa under the P0234 threshold, knock clean, lambda on target, turbo 187 of 220 krpm).

Medium — Spool blip: Essentially unchanged from R07, as expected (R08 left spool cells alone). Crest +13.6 to +15.8 kPa (+2.0 to +2.3 psi) for 0.12–0.24 s at 3320–3450 rpm, settling to ~0 within a few tenths. Slightly later/larger than R07's (+12.7 kPa at 3155) — within pull-to-pull variance. A small extra bite (−0.02/−0.03) at the spike-corner cells is a candidate for R09 now that it repeats across all three pulls.

Medium — Knock channel liveness: All four cylinder channels plus `Knock Avg` read exactly 0.00 across all six files. The R07 logs (same PID list) showed a real −3.0° event, so the channel *can* report; an all-zero day at IAT 32–41 °C is plausible but unverified. Treat "knock clean" as provisional until a log shows any nonzero deviation again.

Medium — Lambda (pull 1 battery finding): 6 isolated samples lean past +0.05 scattered over 3091–5438 rpm — transient blips at higher IAT, not a settled lean condition. Watch, no action.

Medium — Fuel system headroom: Watch only, similar to R07: worst DI sag −12.1 bar; LPFP duty 84.7% (creeping up, hot day); HPFP 94.3%.

Low — Pull 4 (+46 kPa battery headline): Lift-off artifact — pedal at 0%, setpoint collapsing to ~102 kPa while PUT decays through ~195. Not a control finding.

Low — Torque Limit Source 64: Present at WOT as expected (setpoint chain saturated at the `IP_PUT_SP` — Boost pressure setpoint ceiling); torque does not collapse. Normal for this tune.

Low — Turbo / heat: OK. 187 krpm peak, IAT ≤ 41 °C, coolant ≤ 100 °C, oil ≤ 111 °C.

### Disposition

R08's feedforward hypothesis is now answered by data: the top-end residual is rate-limited, not level-limited. Candidate R09 scope: (1) decide on the `IP_PUT_SP` down-ramp softening vs acceptance; (2) small spool-corner bite now that the crest repeats; (3) re-confirm knock channel liveness. No fueling or timing changes indicated.
