# MainTune R20 log review

Twelve SimosTools logs from 2026-08-31, 07:51–08:06, ten of which contain a
detected in-gear WOT pull. Reviewed against the AE1–AE7 acceptance evidence in
`Tunes/REV_LOG.md` § R20.

**Verdict: the calibration did exactly what it was written to do, and the answer
is that we outspent the fuel at peak load.** The `Spark modifier` — map slot 5
ignition offset delivers to within 0.05–0.75 °CRK of prediction, but knock
roughly doubled against the R19 baseline and every significant event is in one
band. R21 cuts that band and holds the rest.

**Two structural problems with the session itself**, both of which limit what
can be concluded and neither of which is a calibration fault:

1. **The within-session A/B was not logged.** All ten pulls are slot 5. R20's
   whole design was slot 5 vs slot 4 on the same road in the same air; without
   slot-4 pulls the comparison falls back to R19, a different day on undosed
   fuel. Every knock number below therefore carries day and fuel as confounds.
2. **The gate predicted the wrong channel.** § R20 says slot 5's `Ign Table`
   should sit above slot 4's. It does not, and should not have been expected to
   — see AE5.

## Provenance and data quality

| Item | Value |
|------|-------|
| Flashed bin | `Patched_259L_R20.bin` (CSV header column 103, identical in all 12 files) |
| Logs | 12 files, 4663 rows, 0.040 s interval, 0 gaps, no stuck channels |
| Pulls detected | 10, all **actual 3rd gear** (`Gear (gear)` header — no offset) |
| Ambient | 15.0 °C, 101.2 kPa |
| Loaded IAT | 24.5–26.8 °C mean per pull |
| Ethanol | 0.0% |
| Fuel | pump 92 AKI dosed with VP Octanium Unleaded per the § R20 protocol |
| Per-cylinder knock | present (`Knock Cyl 1–4`), as the gate required |

The `*.bin.txt` the gate asked for is **not needed** — SimosTools writes the
flashed filename into the CSV header's last column, and it reads
`Patched_259L_R20.bin` in every file. Check that column instead.

Nine of the ten pulls reach ≥ 6000 rpm; `08_05_45` tops out at 5714 and
`07_51_22` / `08_05_11` (not counted as pulls) at 4506 / 4747. Anywhere a
per-pull trend is quoted below, the partial pulls are excluded — a pull that
ends at 4500 rpm cannot record top-end knock, so counting it as "clean" would
bias whichever end of the session it falls in.

## AE5 — does the timing arrive? **Yes, and not where the gate looked**

`Ign Table (°)` on R20 is identical to R19's at every rpm (−6.6 / −4.6 / −3.65 /
−2.1 / +0.65 / +1.9 at 3500–6000). That channel is the **base-map output**; the
patch applies its offset downstream, so the modifier appears in `Ign Avg (°)`.
The gate's stated measurement would have read "no effect" on a calibration that
was working perfectly.

Measured on knock-clean samples, `Ign Avg − Ign Table`, R19 slot 4 vs R20 slot 5:

| Band (rpm) | n R19 | n R20 | R19    | R20    | Gain   | Expected | Residual |
|------------|-------|-------|--------|--------|--------|----------|----------|
| 3500–4000  | 142   | 119   | −0.75  | +1.12  | +1.88  | +1.87    | −0.75    |
| 4000–4500  | 147   | 155   | −0.29  | +2.22  | +2.51  | +2.54    | −0.32    |
| 4500–5000  | 147   | 113   | −0.04  | +3.23  | +3.27  | +3.37    | −0.14    |
| 5000–5500  | 174   | 191   | −0.03  | +2.91  | +2.95  | +2.95    | −0.03    |
| 5500–6000  | 180   | 216   | −0.01  | +1.87  | +1.87  | +1.88    | −0.01    |
| 6000–6500  | 126   | 114   | −0.02  | +1.43  | +1.45  | +1.38    | +0.05    |

R19 sits at zero across the board, which is what makes it a usable control: it
is the same calibration with a neutral modifier grid. **AE5 passes.** The effect
is also present in true post-shift 4th gear (+3.00 at 4000–4500, +3.24 at
4500–5000), so it is not a gear- or transient-specific artifact.

Two residual probes worth recording:

- The naive model `Ign Avg = Ign Table + modifier + Knock Avg` fits badly on
  pull 5 (rms 1.079, bias −0.975). `Knock Avg` is a four-cylinder mean and does
  not represent a single-cylinder event; substituting the **worst logged
  per-cylinder correction** fits to rms 0.301, bias −0.042.
- A 6.376 °CRK outlier on `08_00_09` sits at 3057 rpm in a combustion-mode 2 /
  valve-lift 0 transition, outside steady WOT. Restricted to steady WOT the same
  model's worst residual is 0.948.

## AE6 — knock character: **the gate fails as written**

§ R20 asks for no channel below −1.50 °CRK and no window with two cylinders
retarding in the same sample. Both are breached:

- **Depth:** pull 5 (`07_57_32`) reaches **−2.25 °CRK** on cylinders 1 and 4,
  and pull 8 (`08_01_14`) reaches −2.25 on cylinder 4 **in the 4th-gear
  continuation**. A 3rd-gear-only read sees only the first of these — hold WOT
  into 4th and read it.
- **Simultaneity:** pulls 7 and 8 have 13 and 23 samples with two cylinders
  retarding together, at 3048 and 3149 rpm.

Character is otherwise sound — cuts are one to one-and-a-half detected events
deep, decay rather than ramp, and cylinders 2 and 3 are clean in every pull. The
bias is strongly cylinder 1 and cylinder 4.

Scored against R19 on identical event definitions (all gears, pedal ≥ 90%,
rpm ≥ 3000, airmass ≥ 0.9 g/stk, TPS ≥ 60%):

|      | Loaded WOT | Events | Rate            | Worst  |
|------|------------|--------|-----------------|--------|
| R19  | 69.6 s     | 10     | 8.63 /loaded-min | −1.50 |
| R20  | 62.6 s     | 16     | 15.33 /loaded-min | −2.25 |

## Findings

### High — the 4500–5000 rpm band is the whole regression

| Band (rpm) | R19 ev/min | R20 ev/min | Mean mg/stk | R20 modifier   |
|------------|------------|------------|-------------|----------------|
| 3000–3500  | 43.2       | 40.5       | 1278        | +1.12 → +1.50  |
| 3500–4000  | 0.0        | 9.4        | 1517        | +1.50 → +2.25  |
| 4000–4500  | 7.9        | 6.3        | 1518        | +2.25 → +3.00  |
| **4500–5000** | **4.2** | **27.5**   | 1505        | +3.00 → +3.75  |
| 5000–5500  | 9.7        | **0.0**    | 1423        | +3.75 → +2.25  |
| 5500–6000  | 4.0        | 6.0        | 1305        | +2.25 → +1.50  |
| 6000–6600  | 6.7        | 22.1       | 1204        | +1.50 → +1.12  |

Only 4500–5000 separates from noise — 6 events against an exposure-matched
expectation of 0.9, Poisson p ≈ 0.0006 — and it is the only band to exceed one
detected event's retard, with both −2.25 °CRK cuts (4615 and 4653 rpm). The six
events sit at 4508–4694 rpm.

**The +3.750 °CRK apex at 5000 rpm logged zero events** over 9.5 s and improved
on R19's 9.7/min. Load separates the two bands: 1505 mg/stk mean at 4500–5000
against 1423 at 5000–5500. Cylinder filling is binding, not offset size — which
is why R21 cuts the shoulder and holds the apex.

Evidence: `plots/r20_validation.png`, `plots/r20_knock_traces.png`,
`analyze_r20_validation.py`.

### Medium — two apparent findings that are not R20's

- **3000–3500 rpm is pre-existing.** Highest event rate in either session, and
  R19 ran 43.2/min there with **no modifier at all**. R20's two-cylinder
  same-sample events live here. Not caused by this revision; never addressed by
  any revision. Worth its own future pass.
- **6000–6600 does not separate.** 3 events against 1 on comparable exposure is
  Poisson p ≈ 0.3. It is not evidence of a regression and equally not evidence
  of headroom.

### Medium — the octane-mixing hypothesis is not supported

Tested directly: knock retard area against minutes into the drive has rank
correlation **+0.008** over the nine full pulls. The cleanest pull of the session
is the second one (zero retard, and the session's highest peak rpm at 6368); the
worst is in the middle at 6.2 min; thirds of the sequence run 1.05 → 2.65 → 1.35
°CRK·s. Oil temperature is effectively a clock here (+0.983 with time) but
correlates only +0.084 with knock area, so heat soak is not driving it either.

Scope: this rules out mixing *progressing during the logged session*. It cannot
rule out that the dose had blended before the first pull — that scenario also
predicts a flat trend.

Evidence: `plots/r20_knock_timeline.png`, `analyze_r20_knock_timeline.py`.

### Medium — boost shortfall, carried over from R19

PUT runs under setpoint through the midrange on every pull; the wastegate
integral winds to ~12.9% while the final command sits ~18.2 points above
`wg_pos_base`. Slot-to-slot this is a **non-finding for R20** — setpoints match
R19 to within +0.25 kPa in every band, so slot 5 is carrying slot 4's curve as
designed and the AE "boost unchanged" control passes. As a calibration item it
is the same open feedforward question R19 logged.

| Band (rpm) | SP R19 | SP R20 | Δ SP  | PUT R19 | PUT R20 | Err R19 | Err R20 |
|------------|--------|--------|-------|---------|---------|---------|---------|
| 3500–4000  | 280.88 | 280.88 | +0.00 | 281.00  | 280.24  | +0.12   | −0.65   |
| 4000–4500  | 280.82 | 280.84 | +0.02 | 278.44  | 274.91  | −2.38   | −5.93   |
| 4500–5000  | 275.85 | 276.09 | +0.25 | 269.98  | 270.79  | −5.87   | −5.31   |
| 5000–5500  | 265.36 | 265.57 | +0.20 | 260.27  | 257.86  | −5.10   | −7.71   |
| 5500–6000  | 251.85 | 252.09 | +0.23 | 248.42  | 247.21  | −3.43   | −4.87   |
| 6000–6500  | 238.18 | 238.41 | +0.23 | 238.90  | 239.00  | +0.72   | +0.59   |

### Low — the battery's High lambda finding is 2 samples

`analysis_findings.md` raises lambda +0.068 lean on pull 3. It is **2 samples
(0.08 s)** at 3089–3094 rpm with fuel flow running +0.40 to +1.46 mg/stk *above*
setpoint — a transient, not a mixture problem. Not actionable.

### Low — everything else is within watch limits

Turbo 204 krpm (limit 220), IAT peak 33 °C, coolant 100 °C, oil 111 °C, worst DI
rail sag −7.3 bar, LPFP 79.3%, HPFP 97.3%. Demanded MAP setpoint peaks 310.9 kPa
against `C_PRS_IM_SP_MAX`; logged PUT-minus-ambient peaks 1899 hPa against the
`IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold of
2700 hPa, an 801 hPa margin.

## AE7 — power

3rd-gear F=ma wheel power, trimmed to each pull's own gear per the `Calc HP`
gear-flip rule: **R20 263 hp mean (259–272, 8 pulls) against R19 256 hp mean
(252–259, 6 pulls)**. Cross-session, so day and fuel are confounds and this is
directionally consistent with the added timing rather than proof of it. AE7 as
written — slot 5 above slot 4 *in the same session* — could not be evaluated.

## What to do next

**R21 is built** (`Tunes/MainTune/TUNE_MainTune_R21.py`,
`REV_LOG.md` § R21): the 4000 and 4500 rpm modifier columns come down to +1.500
°CRK, the +3.750 apex at 5000 and everything above it are held, and nothing else
in the calibration moves. Exactly one table, four cells.

Deferred to R22, gated on R21 logging clean: raise 6000 rpm toward +3.000 °CRK
(6500 is nearly at the +5.00 delivered guard already), write the 1049.97 mg/stk
row so the full column value is delivered at redline load, and take a pass at the
pre-existing 3000–3500 rpm zone.

**Log R21 interleaved slot 4 / slot 5.** That is the one thing this session
needed and did not have, and without it R21 will be scored the same compromised
way this one was.

## Tooling notes

- `analyze_r20_validation.py` — AE5/AE6/AE7 battery, boost control, residual
  probes. Writes `plots/r20_validation.png`, `plots/r20_knock_traces.png`,
  `plots/r20_cumulative_knock_events_vs_wot_time.png`.
- `analyze_r20_knock_timeline.py` — the mixing-hypothesis test. Writes
  `plots/r20_knock_timeline.png`.
- The cumulative-events plot is arithmetically correct but is a poor form for a
  trend question: a monotone staircase cannot show a rate change, and the
  17.90 → 12.93 events/loaded-min drop from first five to last five pulls is
  invisible in it. Use the timeline plot for that question.
