# BasicsGuide_R09 Log Review

Living review document for `5G0906259L_0002_BasicsGuide_R09.bin` flash logs
(flashed under the name `CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R09.bin`,
confirmed by every log's SimosTools header tag). R09 is R08 plus: base
`IP_PUT_SP` — Boost pressure setpoint reshaped into a 26 psi full-load shelf at
3400–4400 rpm (via re-breakpointed RPM axis), with the switch patch's per-slot
PUT-setpoint caps on slots 1/3/4/5 filled with the R08 curve so only **slot 2**
sees the raised base. The initial patch installation required a full flash; this
matching-patch tune update is CAL-flash eligible.

## 2026-07-12: R09 Validation Review (cap semantics + first drive of the 26 psi shelf)

Analysis battery: `python -m simoscal.analysis Logs/BasicsGuide_R09` — all 11
checks ran (cal resolved via the `.bin.txt` record, written this review from the
log-header bin tag), no skips. See `analysis_findings.md` / `.json` and
`plots/analysis_*.png`. Band comparisons below are my own follow-up over the raw
CSVs (pedal ≥ 90 %, 3rd gear).

### Reviewed Files

15 files, 14 detected pulls. No slot indicator is logged; slot is classified
from the WOT `PUT SP` ceiling — the R08 cap tops out at ≈ 269 kPa (2699 hPa)
while the slot-2 shelf commands ≈ 281 kPa (2809 hPa = 26 psi):

| File (simostools-2026_07_12-…) | Pulls   | Slot | Max PUT SP (kPa) | Notes                                             |
|--------------------------------|---------|------|------------------|---------------------------------------------------|
| 21_59_53                       | —       | —    | —                | No WOT rows (warm-up / positioning).              |
| 22_13_02                       | 1       | 1    | 269.4            | Short 3rd-gear pull 3428–4375 rpm.                |
| 22_15_41                       | 2       | 1    | 267.5            | Clean 3rd-gear pull to 6248 rpm.                  |
| 22_18_46                       | 3, 4    | 1    | 267.9            | 2nd- then 3rd-gear pulls to ~6300 rpm.            |
| 22_22_08                       | 5       | 1    | 268.3            | 3rd-gear pull; knock −3.0° (cyl 1).               |
| 22_29_33                       | 6       | 1    | 258.5            | 2nd-gear pull; LPFP duty peak 87.7 %.             |
| 22_29_47                       | 7       | 1    | 265.7            | Short 3rd-gear pull.                              |
| 22_31_27                       | 8       | 1    | 267.5            | Clean 3rd-gear pull to 6298 rpm.                  |
| 22_37_11                       | 9       | 2    | 280.7            | First slot-2 pull, short (3056–3885 rpm).         |
| 22_38_52                       | —       | 2    | 245.7            | Partial throttle only, no pull detected.          |
| 22_41_31                       | 10      | 2    | 280.8            | Clean 3rd-gear shelf pull to 6442 rpm.            |
| 22_45_35                       | 11      | 2    | 278.3            | Short 2nd-gear burst.                             |
| 22_45_46                       | 12      | 2    | 280.9            | Short 3rd-gear pull; knock −3.0° (cyl 4).         |
| 22_46_45                       | 13      | 2    | 280.6            | Full shelf pull; knock −3.0° (cyl 1).             |
| 22_47_44                       | 14      | 2    | 280.8            | Full shelf pull; knock −2.6° (cyl 3, 3050–3400).  |

Gear note: `Gear (gear)` = actual gear numbering; no offset applied.

### Headline 1: cap semantics = min() is now IN-CAR PROVEN

The R09 first-drive gate is passed. Pulls 1–8 ran on a capped slot and tracked
the R08 curve exactly — WOT `PUT SP` ceiling 265.7–269.4 kPa across six files,
matching the cap value 2699 hPa, with band-by-band tracking in line with the
R08 logs (table below). Pulls 9–14 then ran slot 2 and the setpoint stepped to
280.6–280.9 kPa = the 2809 hPa (26 psi) shelf. Same bin, same drive, two
different boost targets — only possible if the per-slot cap binds by `min()`
against the raised base, as designed. The switch patch's boost-by-slot
mechanism is validated end to end.

### Headline 2: the 26 psi shelf is only partially delivered (~24.6–25.3 psi)

Band means, 3rd-gear WOT (pedal ≥ 90 %), slot 1 vs slot 2, R08 logs for
reference:

| Band (rpm) | R08 err | Slot-1 err | Slot-2 err | Slot-2 WG-I | Slot-2 WG final | Slot-1 WG final |
|------------|---------|------------|------------|-------------|-----------------|-----------------|
| 3300–4500  | +0.2    | −4.5       | −9.5       | +1.7 %      | 70.1 %          | 62.7 %          |
| 4500–5200  | −2.6    | +0.6       | −8.1       | +8.5 %      | 67.8 %          | 53.3 %          |
| 5200–5800  | −2.6    | −1.5       | −6.9       | +14.7 %     | 72.3 %          | 54.9 %          |
| 5800–6200  | +6.6    | +1.7       | +7.4       | +15.9 %     | 62.6 %          | 54.4 %          |
| 6200–6700  | +9.9    | +14.1      | +21.1      | +8.4 %      | 44.8 %          | 38.6 %          |

(err = mean PUT − PUT SP, kPa.) On slot 2 the car runs 7–10 kPa (~1.0–1.4 psi)
under the shelf from 3300 to 5800 rpm: actual boost holds ~24.6–25.3 psi
against the 26.0 target, with the wastegate integral climbing to +15 % and the
gate held 67–72 % closed (vs ~54–63 % on slot 1) without closing the gap.

**Root cause identified: the gap is commanded, not plant.** `Torque Lim ()`
code 128 appears only on slot-2 files and only at 3500–4800 rpm — exactly the
shelf zone (233 samples across all five slot-2 pull files). Per the tuning
basics guide (p. 29), code 128 = *"Temporary torque limitation because of
operation at maximum charge pressure ratio (Max Pressure ratio table)"* — the
table is `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
compressor (8×8), which reads back **flat 2.80** across all 64 cells in the
R09 bin. The numbers close exactly:

- Shelf demand: 281 kPa over a pre-compressor pressure of ~96–98 kPa (ambient
  101.6 minus 3–5 kPa intake depression at 1450–1550 mg/stk) = PQ 2.87–2.91 —
  **over the 2.80 cap**, so code 128 fires and PUT is trimmed.
- Delivered: settled slot-2 PUT plateaus at 266–272 kPa; at PQ = 2.80 that
  implies upstream pressure 96.6–98.9 kPa — a physically right intake
  depression. The cap, not the wastegate, sets the delivered level.
- Slot-1 control: the R08 curve peaks at PQ ≈ 2.77 vs ambient — just under the
  cap, which is exactly why code 128 never appears on slot-1 files. (Code 64 —
  temporary limit at maximum absolute charge-air-pressure setpoint, the known
  `IP_PUT_SP`-chain saturation — appears on both slots as before.)

The persistent positive WG-I is the closed loop chasing the unreduced logged
`PUT SP` while the limiter trims the achievable setpoint downstream — do NOT
read it as a feedforward shortfall. `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost
pressure actuator setpoint (wastegate feedforward) work cannot recover this
gap while PQ 2.80 binds.

### Headline 3: top-end overshoot grew to +21 kPa — the R09 down-ramp is steeper, not the control worse

Battery High finding: sustained ridge 6060–6375 rpm, mean +19.6 / peak
+24.6 kPa (pull 14). This is the same rate-limit mechanism R08 diagnosed —
boost cannot bleed down as fast as the falling `IP_PUT_SP` — Boost pressure
setpoint — but R09 made the ramp steeper: the full-load row now falls
26.0 → 17.8 psi over 4400–6500 rpm (8.2 psi) vs R08's 21.5 → 17.2 (4.3 psi).
The plant delivers nearly the same absolute top-end boost as slot 1 (219 vs
214 kPa mean at 6200–6700); the larger "error" is mostly definitional against
the steeper untrackable ramp. Wastegate has headroom (integral min −4.6 %,
final 22 % at the peak), confirming this is not an authority problem.

It is still a real margin consumer: PUT−ambient peaked 1925 hPa vs the
`IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — P0234 overboost threshold (PUT-minus-ambient)
at 2700 hPa — margin 775 hPa, down from R08's 933 hPa. Safe, but the trend
direction is worth tracking if the top-end setpoint rises further.

### Main Findings

**High — Shelf under-delivery is a commanded cap: `IP_PQ_CHA_MAX` — Maximum
allowed pressure quotient at turbo charger compressor binds at 2.80 (slot 2,
3300–5800 rpm).** Headline 2 above. Evidence: `plots/analysis_boost.png`,
`plots/analysis_wastegate.png`, table readback from the R09 bin.

**High — Top-end PUT overshoot +21 kPa mean / +24.6 peak (6060–6440 rpm, both
slots, worse on slot 2).** Headline 3 above — rate-limited setpoint down-ramp,
not wastegate authority. P0234 margin 775 hPa. Evidence:
`plots/analysis_boost.png`.

**Medium — Knock: worst −3.0°, cylinder 1 recurring, and the watched 3000–3500
plateau zone did knock (mildly).** Events (pedal ≥ 90 %): pull 5 (slot 1) cyl 1
−3.0° at 4217–5517 rpm; pull 13 (slot 2) cyl 1 −3.0° spanning 3258–6400 rpm;
pull 12 cyl 4 −3.0° at 4500–4670; pull 14 cyl 3 −2.6° at 3052–3399 rpm — the
exact zone the R09 REV_LOG flagged (R07's retard episodes sat there). All
events decay in normal 0.375° steps; nothing exceeds the −3.0° line, and knock
is NOT systematically worse on slot 2 than slot 1. Channel liveness (R08 open
question) is re-confirmed — the channels report nonzero again. Timing is at the
edge as expected; watch cyl 1. Evidence: `plots/analysis_knock.png`.

**Medium — Fuel system: HPFP effectively at ceiling on the shelf.** HPFP
effective volume peaks 98.1 % (pull 12) and runs 97 %+ on every full slot-2
pull; LPFP duty peaks 87.7 % (pull 6 — notably a slot-1, 2nd-gear pull); worst
DI rail sag −9.4 bar (inside the −10 watch line). Lambda still holds — so R09
is not yet fuel-limited — but there is essentially no high-pressure-pump
headroom for more airmass. Any R10 boost increase needs a fuel-side answer
first. Evidence: `plots/analysis_rail_pressure.png`.

**Medium — Turbo speed 208 krpm (slot-2 pulls) vs 220 krpm limit.** Up from
187 krpm in R08 with the added load; 202–208 krpm on all three full shelf
pulls. ~5 % margin left. IAT ≤ 38 °C, coolant ≤ 101 °C, oil ≤ 108 °C — all
fine. Evidence: `plots/analysis_turbo_heat.png`.

**Low — Battery lambda High finding downgraded.** The "+0.066 settled-WOT lean"
(pull 10) is two samples at 3086–3096 rpm while `Lambda SP` steps rich at pull
start and delivered mixture is still ramping in — an enrichment-transition
artifact, with rail pressure on target (201 vs 200 bar). Band-mean lambda error
at WOT is +0.013 or better everywhere on both slots. Pull 14's +1.097 excursion
is a lift-off fuel-cut tail. No settled lean condition exists. Evidence:
`plots/analysis_lambda.png`.

**Low — `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold pressure setpoint
ceiling.** Demanded map_sp peak 310.3 kPa, far under the (deliberately parked)
35000 kPa ceiling. Context only.

**Low — Timing envelope.** Loaded-WOT delivered timing spans −13.1 to +3.4°
(mean −3.3°). Shelf-band mean: slot 1 −6.1° vs slot 2 −7.3° — the shelf costs
~1.2° of delivered timing at 3300–4500 rpm. Consistent with the knock picture;
context.

### Disposition

R09's two purposes are both answered by data: the cap mechanism works
(slot-by-slot boost is real), and the 26 psi shelf is drivable but capped ~1.0–
1.4 psi short by `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo
charger compressor (flat 2.80), identified via torque-limit code 128.

Candidate R10 scope, in order:

1. **Decide the PQ-cap posture**: either raise `IP_PQ_CHA_MAX` — Maximum
   allowed pressure quotient at turbo charger compressor enough to clear the
   shelf demand (~2.90 needed at 101.6 kPa ambient; more at altitude, where
   the same shelf is a larger PQ), or trim the shelf to fit under 2.80.
   Caution before raising: the cap is compressor protection, turbo speed is
   already 208 of 220 krpm on shelf pulls, and the 6000-ft use case pushes PQ
   up at fixed boost — this limiter is doing exactly its job near the IS20's
   map edge. Trimming the shelf to the delivered ~24.6–25.3 psi may be the
   honest calibration.
2. **No wastegate feedforward change for the midrange** — the positive WG-I on
   slot 2 is the loop fighting the PQ limiter, not a feedforward level error.
   Re-evaluate FF only after the cap decision, from logs where code 128 is
   silent.
3. **Decide the top-end down-ramp posture**: R09 steepened the 4400–6500 ramp
   and the definitional overshoot grew accordingly (P0234 margin 775 hPa).
   Either flatten the ramp toward what the plant can track or accept and
   monitor the margin.
4. **Fuel headroom before any further boost**: HPFP at 97–98 % is the binding
   constraint on more airmass; no lambda symptom yet, but the ceiling is here.
5. **Knock watch**: cyl 1 recurring at −3.0°; the 3000–3500 plateau knocked at
   −2.6°. No action yet — re-check on the next revision's logs; escalate if
   events stop decaying or exceed −3.0°.

No fueling or ignition changes indicated by these logs. R09 remains a starting
point, not a finished calibration — slot 2 validates the mechanism; the shelf
calibration itself is one iteration old.
