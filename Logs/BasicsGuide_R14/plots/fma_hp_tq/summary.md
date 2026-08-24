| log | gear | rpm span | peak wheel HP | peak crank HP | peak crank TQ (Nm) | peak Calc HP (trimmed) |
|---|---|---|---|---|---|---|
| simostools-2026_08_10-12_02_12.csv | 3 | 3246-6194 | 248 | 276 | 409 | 302 |
| simostools-2026_08_10-12_06_23.csv | 3 | 2986-6192 | 244 | 271 | 412 | 298 |
| simostools-2026_08_10-12_07_51.csv | 3 | 3001-6246 | 254 | 282 | 410 | 297 |
| simostools-2026_08_10-12_11_04.csv | 2 | 4258-5920 | 219 | 243 | 302 | 291 |
| simostools-2026_08_10-12_11_04.csv | 3 | 3919-5096 | 239 | 266 | 409 | 276 |

## Method

F = m·a + F_aero + F_roll, P_wheel = F·v, evaluated per sample over each WOT pull:

- m = 3400 lb (1542 kg, car + driver), effective mass ×1.05 for rotating inertia
- v from the undriven rear wheel speeds (mean RL/RR) — immune to front slip
- a = dv/dt via a 0.6 s local linear-regression slope (Time channel rebuilt from
  the sample index; the logged Time is float32-quantised to ~0.2 s)
- F_aero = ½·ρ·Cd·A·v² with Cd = 0.31, A = 2.21 m², ρ from the logged ambient
  pressure and temperature channels (~101.7 kPa / 18 °C → ρ ≈ 1.215 kg/m³)
- F_roll = Crr·m·g with Crr = 0.011
- Crank estimate = wheel power / 0.90 (DSG FWD driveline); crank TQ = P/ω(rpm)

Pulls are pedal > 90% spans split into contiguous constant-gear runs, each run
started at its rpm minimum to drop the DSG's early gear-channel flip transient
(the same artifact that inflates Calc HP).

## Cross-checks

- ECU `Calc HP` (identically in-gear-trimmed) tracks the physics curve's shape
  closely but reads ~8–10% higher (297–302 vs 271–282 crank hp). Calc HP is the
  app's own accel-based estimate and scales with whatever mass/inertia it
  assumes, so a constant ~9% offset is an assumed-parameter difference, not a
  shape disagreement.
- Published Mk7 GTI dyno data: stock ≈ 200 whp; IS20 Stage 1 on 91/93 octane
  ≈ 250–268 whp; IS20 Stage 2 vendor claims run ~300–316 whp / ~365 wtq on 93
  (performancebyie.com, boostdynamictuning.com, mygolfmk7.com Unitronic Stage 2
  post). This calibration's airflow requests are Stage-2-level — 27.5 psi peak
  boost, ~1550–1580 mg/stk peak airmass, ~1230 mg/stk still in at 5800+ rpm —
  yet measured output (244–254 whp) lands at the bottom of the *Stage 1* band.
  The gap is not airflow: above 5800 rpm the logs show `Ign Avg` ≈ 1–2 °
  with zero knock retard. Lambda ≈ 0.80 there is ON target — 0.80 at full load
  is this build's deliberate, log-validated setpoint (ecu-tuning-basics.md;
  floors set via `tune.fueling.lambda_floors(0.80)` since R03) and normal for a
  boosted DI engine. Conservative high-rpm ignition timing on 92 octane is
  where the missing ~40–60 whp lives, not boost and not fueling.
- The 2nd-gear pull reads ~60 hp / ~110 Nm lower than 3rd at the same rpm:
  ECU torque limiting in lower gears and/or front-tire slip (speed here comes
  from the undriven rears, so slip shows up as genuinely lower ground force).
