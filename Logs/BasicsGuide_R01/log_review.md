# BasicsGuide_R01 Log Review

Living review document for the first `5G0906259L_0002_BasicsGuide_R01.bin` flash logs. Add new dated entries at the top as the calibration changes and new logs are collected.

## 2026-07-07: First R01 Flash Review

### Reviewed Files

| File                                  | Notes                                            |
|---------------------------------------|--------------------------------------------------|
| `simostools-2026_07_07-22_15_22.csv` | Idle / no WOT baseline.                          |
| `simostools-2026_07_07-22_23_50.csv` | Clean 2nd-gear WOT sweep.                        |
| `simostools-2026_07_07-22_25_12.csv` | 2nd into 3rd WOT with knock and shift transient. |
| `simostools-2026_07_07-22_30_53.csv` | Short 1st/2nd WOT pull.                          |
| `simostools-2026_07_07-22_32_25.csv` | 1st-gear WOT pull.                               |
| `simostools-2026_07_07-22_48_25.csv` | Long multi-gear WOT event.                       |

### Main Findings

High - Boost overshoot: Needs revision. Peaks at 286 kPa PUT / 26.9 psi, with +18 to +26 kPa overshoot pockets.

High - Knock retard: Needs revision. Repeated -3.0 deg corrections in several WOT regions.

Medium - Lambda / fueling: Mostly OK under settled WOT. Lean spikes are mostly shift/torque-cut transients.

Medium - Fuel pressure: OK for this level, but LPFP/HPFP are getting close to high-load headroom.

Medium - Turbo / temps: Usable, but turbo air temp and shaft speed are high enough to avoid stacking pulls.

Low - Performance: Strong for a first guide flash: about 24-25 psi typical, 26.9 psi peak, about 1.50 g/stk max airmass, about 449 Nm logged torque.

### Evidence Plots

| Plot                              | Finding Supported             |
|-----------------------------------|-------------------------------|
| `plots/boost_overshoot.png`       | Boost overshoot               |
| `plots/knock_retard.png`          | Knock retard                  |
| `plots/lambda_fueling.png`        | Lambda / fueling              |
| `plots/fuel_pressure.png`         | Fuel pressure                 |
| `plots/turbo_temps.png`           | Turbo / temps                 |
| `plots/performance_summary.png`   | Performance                   |

Single-log deep dive for `simostools-2026_07_07-22_48_25.csv`: `plots/deepdive_22_48_25/`.

Gear note: the logged `Gear ()` channel is zero-based, so actual gear is logged gear + 1. The deep-dive plots display corrected actual gear labels.

| Deep-Dive Plot                                         | Focus                                   |
|--------------------------------------------------------|-----------------------------------------|
| `plots/deepdive_22_48_25/01_run_overview.png`          | RPM, speed, gear, pedal, and TPS.       |
| `plots/deepdive_22_48_25/02_boost_tracking_time.png`   | Time-based PUT, PUT SP, error, boost.   |
| `plots/deepdive_22_48_25/03_boost_vs_rpm_by_gear.png`  | Boost and PUT error versus RPM by actual gear. |
| `plots/deepdive_22_48_25/04_knock_timing_time.png`     | Knock retard, ignition, and airmass.    |
| `plots/deepdive_22_48_25/05_lambda_transients_time.png` | Lambda tracking and torque transients.  |
| `plots/deepdive_22_48_25/06_fuel_system_time.png`      | DI/MPI fuel pressure and pump headroom. |
| `plots/deepdive_22_48_25/07_turbo_heat_time.png`       | Turbo speed, turbo air temp, wastegate. |
| `plots/deepdive_22_48_25/08_performance_time.png`      | Airmass, torque, power, and airflow.    |

### Safety Findings

Boost control: Actual PUT overshoots target by about +18 to +26 kPa in multiple WOT regions. The largest observed point is 286 kPa PUT / 26.9 psi in `22_48_25`.

Knock retard: Repeated -3.0 deg knock retard appears in loaded WOT regions, especially around 3500-4000 rpm and 4900-5500 rpm. This should be corrected before more hard pulls.

Lambda tracking: Settled WOT lambda generally tracks target well. Large lean lambda spikes line up with torque collapse / shift transients and should not be tuned as steady WOT.

Fuel pressure: DI pressure usually tracks target near 200 bar under load. LPFP duty reaches about 85% and HPFP effective volume reaches about 98%, so headroom is not unlimited.

Turbo / heat: Turbo speed reaches about 191k rpm, below the raised 220k limiter, but turbo air temp reaches about 176 deg C during the long pull.

### Calibration Context

`IP_PUT_SP`  — PUT setpoint curve: Main shaped boost target. The logs show actual PUT overshoot versus this target in several regions.

`IP_PQ_CHA_MAX`  — Turbo maximum pressure ratio: Flattened to 2.8 in R01, so it should not be the main boost shaper.

`LC_PUT_SP_TOL_ENA_AMP`  — Use AMP for calculation of PUT out of pressure ratio instead of PRS_CHA_UP: Set to 1 per the guide.

`C_PRS_IM_SP_LIM`  — Maximum allowed PRS_IM_SP: Left unchanged because stock was already above the guide value. Not the primary problem seen in these logs.

`IP_PUT_MAX_CAP_H_DIAG`  — Charge air pressure too high diagnostic cap: Moved out of the way. This avoids nuisance intervention but does not make boost overshoot mechanically ideal.

`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]`  — Basic Ignition Angle, VVL 0 Port Flap Low: Representative active WOT timing family. Needs local timing reduction where repeat knock appears.

`IP_LAMB_BAS_HPDI[1]`  — Basic lambda setpoint grid, HPDI (direct injection): R01 wrote the guide lambda grid. Settled WOT tracking looks acceptable.

`IP_LAMB_BAS_MPI[1]`  — Basic lambda setpoint grid, MPI (port injection): R01 wrote the guide lambda grid. Settled WOT tracking looks acceptable.

`IP_LAMB_BAS[1]`  — Basic lambda setpoint grid: Rewritten to stay coherent with the re-breakpointed HPDI/MPI lambda family.

`ID_PV_AV_FL`  — Pedal value threshold for the determination of LV_FL_RAW: Lowered to 72%, so full-load lambda enrichment enters earlier than stock.

`C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint: Left stock because this bin is already richer than the guide's 0.80 floor.

`IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating protection: Left stock because this bin is already richer than the guide's 0.80 floor.

`IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo charger overheating prevention versus engine speed: Left stock because this bin is already richer than the guide's 0.80 floor.

`C_N_TCHA_MAX`  — Maximum turbo charger speed: Raised to 220k. Logs peak around 191k, below the revised limit.

`C_N_TCHA_MAX_SP`  — Maximum turbo charger speed setpoint: Raised to 220k. Logs peak around 191k, below the revised limit.

`IP_IGA_BAS_TEMP_N_32`  — Basic ignition angle correction by intake air temperature and engine speed: IAT correction context for the hotter WOT samples.

### Recommended Next Calibration Changes

High - Do not treat R01/R02 as final. Make a conservative R03 before more long WOT testing.

High - Fix boost control first. Either soften `IP_PUT_SP`  — PUT setpoint curve by about 10-20 kPa in overshoot regions, or collect the required intake/exhaust flow-factor logs and tune wastegate feedforward properly.

High - Pull about 1.5-2.0 deg from high-airmass timing cells around 3500-4000 rpm in `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]`  — Basic Ignition Angle, VVL 0 Port Flap Low and related active WOT tables, then blend neighboring cells.

Medium - Pull about 1.0-1.5 deg from high-airmass timing cells around 4750-5500 rpm if repeat knock remains after boost control is improved.

Medium - Leave `IP_LAMB_BAS_HPDI[1]`  — Basic lambda setpoint grid, HPDI (direct injection) and `IP_LAMB_BAS_MPI[1]`  — Basic lambda setpoint grid, MPI (port injection) alone for now. Settled WOT lambda is acceptable.

Medium - Keep `C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint, `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating protection, and `IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo charger overheating prevention versus engine speed at stock unless new logs show a real lean issue.

### Next Log Request

| Channel                         | Purpose                                            |
|---------------------------------|----------------------------------------------------|
| Exhaust flow factor             | Required for exact wastegate table cell selection. |
| Intake flow factor              | Required for exact wastegate table cell selection. |
| Torque Limit Source bitmask     | Confirms whether a limiter is intervening.         |
| PUT / PUT SP                    | Boost tracking.                                    |
| MAP / MAP SP                    | Manifold pressure and charge tracking.             |
| Lambda / Lambda SP              | Fueling validation.                                |
| Knock Cyl 1-4                   | Timing validation.                                 |
| FP DI / FP DI SP                | HPFP validation.                                   |
| FP MPI / FP MPI SP              | MPI rail validation.                               |
| LPFP Duty                       | Low-side fuel headroom.                            |
| Turbo Speed                     | Turbo safety.                                      |
| IAT / Turbo Air Temp / Oil Temp | Heat context.                                      |

### Regeneration

Run `python3 plot_log_review.py` from this folder to regenerate the plots. The script reads all `simostools-*.csv` files in this directory and writes PNGs under `plots/`.
