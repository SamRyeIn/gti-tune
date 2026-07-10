# BasicsGuide_R04 Log Review

Living review document for `5G0906259L_0002_BasicsGuide_R04.bin` flash logs. R04 is based on R03 and adds the local knock-retard timing overlay to `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle, VVL 0 Port Flap Low.

## 2026-07-08: R04 Ignition Validation Review

### Reviewed Files

| File                                  | Notes                                                    |
|---------------------------------------|----------------------------------------------------------|
| `simostools-2026_07_08-22_10_57.csv` | Two clean actual-3rd-gear WOT pulls after flashing R04.  |

Gear note: this R04 log uses actual gear numbering. `Gear (gear) = 3` is actual 3rd gear. Do not apply the R01 zero-indexed gear offset to this file.

### Main Findings

High - Knock retard: Resolved for this validation log. Both actual-3rd-gear WOT pulls show 0.0 deg knock correction on all four cylinders through the prior R01 problem regions.

High - Boost overshoot: Still needs revision. PUT peaks at 286.4 kPa / 26.7 psi, with observed overshoot up to +22.2 kPa. This log includes intake/exhaust flow-factor and wastegate-control channels, so wastegate/feedforward tuning can now be analyzed.

Medium - Lambda / fueling: OK under settled WOT. Lambda tracks target; max lean error is about +0.023 lambda, below the +0.03 watch line.

Medium - Fuel pressure: OK for these pulls. DI pressure tracks target within about -6.5 bar worst case; LPFP duty stays under 80%, and HPFP effective volume peaks around 96%.

Medium - Turbo / temps: OK for these pulls. Turbo speed peaks around 184 krpm logged, below the 220 krpm revised limit. IAT stays below about 29 deg C. This log does not include turbo air temperature.

Low - Performance: Similar strong load to R01, about 1.49 g/stk max airmass and about 415-416 Nm logged torque in 3rd gear.

### Evidence Plots

| Plot                            | Finding Supported                                  |
|---------------------------------|----------------------------------------------------|
| `plots/boost_overshoot.png`     | Boost overshoot remains.                           |
| `plots/knock_retard.png`        | Knock retard is clean after R04.                   |
| `plots/lambda_fueling.png`      | Lambda tracking is acceptable.                     |
| `plots/fuel_pressure.png`       | Fuel pressure and pump headroom are acceptable.    |
| `plots/turbo_temps.png`         | Turbo speed, IAT, oil temp, and trans temp.        |
| `plots/wastegate_control.png`   | Wastegate base/final position and corrections.     |
| `plots/flow_factors.png`        | Intake/exhaust flow factors for wastegate tuning.  |
| `plots/performance_summary.png` | Airmass, torque, requested torque, and power.      |

### Pull Summary

| Pull | Log Lines | RPM Range | Airmass Range | Min Knock | Max PUT | Max PUT Error | Max Boost | Lambda Error Range | LPFP Max | HPFP Eff Max | Turbo Speed Max |
|------|-----------|-----------|---------------|-----------|---------|---------------|-----------|--------------------|----------|--------------|-----------------|
| 1    | 143-327   | 2976-6674 | 918-1482      | 0.0 deg   | 283.3   | +19.3 kPa     | 26.3 psi  | -0.065 to +0.023   | 79.8%    | 93.8%        | 182.6 krpm      |
| 2    | 1732-1887 | 3017-6312 | 933-1491      | 0.0 deg   | 286.4   | +22.2 kPa     | 26.7 psi  | -0.074 to +0.023   | 79.1%    | 95.8%        | 183.6 krpm      |

### Safety Findings

Knock retard: R04 fixed the immediate high-priority knock finding in this log. There are zero loaded-WOT rows at or below -1.5 deg, -2.0 deg, or -3.0 deg knock retard. The previously problematic regions around 3500-4000 rpm / high load and 5000-5500 rpm / high load are clean.

Boost control: Boost remains the main open issue. The two pulls still show +19.3 kPa and +22.2 kPa maximum PUT overshoot. Peak PUT is almost unchanged versus the R01 worst case, so the ignition fix should not be mistaken for a boost-control fix.

Lambda tracking: Settled loaded-WOT lambda is acceptable. The lean side of lambda error stays below +0.03, and the rich-side deviations occur during ramp/transition portions rather than indicating a steady lean problem.

Fuel pressure: DI pressure tracks target adequately; worst DI pressure error is about -6.5 bar in pull 1 and -5.1 bar in pull 2. LPFP duty and HPFP effective volume are lower than the R01 watch values, so fuel system headroom looks better in these controlled 3rd-gear pulls.

Turbo / heat: Turbo speed peaks around 184 krpm logged, below `C_N_TCHA_MAX`  — Maximum turbo charger speed and `C_N_TCHA_MAX_SP`  — Maximum turbo charger speed setpoint as revised to 220k. IAT remains cool. Turbo air temperature was not logged, so repeat-pull heat risk is not fully characterized.

Torque limiting: `Torque Lim ()` ranges 0-64, but torque does not collapse during the settled WOT portions. Treat this as context for later review rather than a current intervention finding.

### Wastegate / Flow-Factor Context

This log includes the channels missing from R01:

| Channel              | Observed Range       | Use                                                      |
|----------------------|----------------------|----------------------------------------------------------|
| Intake Flow Fact     | 0.083-1.088          | Intake-flow axis/context for wastegate tuning.           |
| Exh Flow Factor      | 0.742-1.328          | Exhaust-flow axis/context for wastegate tuning.          |
| WG Pos Base          | 65.3-98.6%           | Base/feedforward wastegate command.                      |
| WG Pos Final         | 30.2-100.0%          | Final wastegate command after closed-loop correction.    |
| WG I Value           | -27.5 to +0.0%       | Integral correction; shows controller adaptation.        |
| WG P-D Value         | -16.0 to +62.6%      | Proportional/derivative correction during boost error.   |
| WG Flow Des          | 24.8-326.4 kg/hr     | Desired wastegate flow context.                          |

The wastegate channels show enough information to start a boost-control revision. Because the final wastegate command reaches about 100% in parts of the pull while PUT still overshoots target, review the flow-factor regions carefully before deciding whether the next change should be feedforward correction, lower `IP_PUT_SP`  — PUT setpoint curve, or both.

### Calibration Context

`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle, VVL 0 Port Flap Low: R04 local timing overlay appears successful in the validation log. No additional timing pull is recommended from this log alone.

`IP_PUT_SP`  — PUT setpoint curve: Boost target itself is unchanged in R04 and overshoot remains. This is now the main open calibration issue.

`IP_PQ_CHA_MAX`  — Turbo maximum pressure ratio: Still flattened/moved out of the way per the guide; not the primary boost shaper in this review.

`LC_PUT_SP_TOL_ENA_AMP`  — Use AMP for calculation of PUT out of pressure ratio instead of PRS_CHA_UP: Still set per the guide.

`IP_LAMB_BAS_HPDI[1]`  — Basic lambda setpoint grid, HPDI (direct injection): Leave unchanged based on this log.

`IP_LAMB_BAS_MPI[1]`  — Basic lambda setpoint grid, MPI (port injection): Leave unchanged based on this log.

`IP_LAMB_BAS[1]`  — Basic lambda setpoint grid: Leave unchanged based on this log.

`C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint, `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating protection, and `IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo charger overheating prevention versus engine speed: R04 is based on R03 and keeps the literal 0.80 writes; this log does not show a steady WOT fueling problem from those floors.

### Recommended Next Calibration Changes

High - Treat R04 as a successful knock-retard validation, not a final boost tune.

High - Address boost overshoot next using the now-available intake/exhaust flow-factor and WG-control channels. If wastegate feedforward correction is ambiguous, make a conservative `IP_PUT_SP`  — PUT setpoint curve reduction in the overshoot regions instead of stacking more timing/load stress.

Medium - Do not pull more timing from `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]`  — Basic Ignition Angle, VVL 0 Port Flap Low based on this log. The R04 ignition overlay did what it was intended to do.

Medium - Keep lambda tables unchanged unless a future log shows sustained lean tracking error under settled WOT.

### Next Log Request

For the next revision, keep logging the same channel set. The key channels are now present:

| Channel                         | Purpose                                            |
|---------------------------------|----------------------------------------------------|
| Engine Speed / Airmass / Gear   | Cell selection and pull segmentation.              |
| Pedal / TPS                     | WOT validation.                                    |
| Knock Cyl 1-4 / Ign Avg         | Timing validation.                                 |
| PUT / PUT SP                    | Boost tracking and overshoot quantification.       |
| MAP / MAP SP                    | Manifold pressure tracking.                        |
| Lambda / Lambda SP              | Fueling validation.                                |
| FP DI / FP DI SP                | HPFP validation.                                   |
| FP MPI / FP MPI SP              | MPI rail validation.                               |
| LPFP Duty / HPFP Eff Vol        | Fuel-pump headroom.                                |
| Turbo Speed / IAT / Oil Temp    | Turbo and heat context.                            |
| Intake / Exhaust Flow Factor    | Required for wastegate table cell selection.       |
| WG Pos Base / Final / I / P-D   | Wastegate feedforward and closed-loop correction.  |
| WG Flow Des                     | Wastegate flow context.                            |
| Torque Lim / Torque / Torque Req | Limiter and torque-intervention context.           |

### Regeneration

Run `python3 plot_log_review.py` from this folder to regenerate the plots. The script reads all `simostools-*.csv` files in this directory and writes PNGs under `plots/`.
