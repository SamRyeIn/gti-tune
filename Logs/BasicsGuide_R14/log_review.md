# BasicsGuide_R14 Log Review

Living review document for the R14 flash, logged as
`CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R14.bin` — confirmed by the
SimosTools header tag in all eight CSVs. R14 is R13/R12 calibration with **only
the switch-patch slot assignments changed**: a new stock map on slot 1 and the
drivable slots reordered least→most aggressive (1 stock, 2 conservative,
3 intermediate, 4 aggressive), slot 5 valet unchanged. The shared base
calibration — knock retard, lambda enrichment, wastegate feedforward, limiters,
P0234 threshold — is byte-identical to R13. CAL-flash eligible on the installed
R07 patch set.

## 2026-08-10: R14 validation review (slot 4 only)

Analysis battery: `python -m simoscal.analysis Logs/BasicsGuide_R14` — all 11
checks ran, cal resolved, **no skips**. See `analysis_findings.md` / `.json` and
`plots/analysis_*.png`. The calibration only resolved after adding the missing
`*.bin.txt` record naming the flashed bin; on the first run both
calibration-aware checks and all five coverage maps skipped.

Two follow-up scripts in this folder are my own work over the raw CSVs:

- `verify_slot_identity.py` → `plots/r14_slot_identity.png` — reads all five
  slot curves live off the flashed bin and scores every logged WOT window
  against them.
- `plot_upshift_overboost.py` → `plots/r14_upshift_overboost.png` — the
  4th-gear segment the battery's pull windows do not cover.

### Reviewed files

**Sam drove slot 4 for the whole session.** No slot indicator is logged, so this
is confirmed independently below rather than assumed.

| File (simostools-2026_08_10-…) | Rows | WOT n | Gears at WOT | RPM at WOT | Max PUT SP | Notes                                             |
|--------------------------------|------|-------|--------------|------------|------------|---------------------------------------------------|
| 11_54_03                       | 236  | —     | —            | —          | 101.6 kPa  | Stationary warm-up, coolant 61.7 °C. No pull.     |
| 12_00_06                       | 225  | 46    | 3, 4         | 4204–5212  | 280.9 kPa  | Partial 3rd-gear pull, ends in a lift.            |
| 12_02_12                       | 606  | 162   | 3, 4         | 3246–6276  | 280.9 kPa  | Clean 3rd-gear pull to 6276 rpm.                  |
| 12_03_17                       | 328  | 153   | 2, 3, 4      | 3700–6301  | 280.9 kPa  | **Holds WOT through a 3→4 upshift — see High 1.** |
| 12_06_23                       | 412  | 157   | 3            | 2986–6192  | 280.9 kPa  | Clean 3rd-gear pull.                              |
| 12_07_51                       | 516  | 158   | 3            | 3001–6246  | 280.9 kPa  | Clean 3rd-gear pull. Hottest file; only knock.    |
| 12_11_04                       | 268  | 93    | 2, 3         | 3919–5999  | 280.9 kPa  | 2nd-gear segment with TC activity, then 3rd.      |
| 12_14_10                       | 183  | —     | —            | —          | 238.8 kPa  | Low-rpm throttle stab, never reaches full load.   |

Gear note: header is `Gear (gear)` = actual gear numbering, **no offset**.

Data quality: 0 gaps, 0 stuck channels, no duplicate-channel collisions, 0
misfires in any file. Ethanol 0.0 %, LTFT +0.8 %, battery ≥ 13.77 V under load.
Ambient 16.5–17.3 °C at 101.9 kPa — sea-level, cool, favourable conditions.
One caveat on the battery's "Interval 0.000 s": the `Time` channel is quantised
to 0.1 s (diffs are only 0.0/0.2/0.3/0.4), so the median diff degenerates to
zero. The true rate is uniform at ~39.6 ms/sample; sample counts and
reconstructed time are reliable, the reported interval is not.

---

## Headline: the R14 reorder is live, exact, and correctly capped

The deliverable of R14 was the slot reorder, and it is confirmed in-car. Reading
all five `PUT setpoint` — boost target grids straight off the flashed bin and
scoring each logged WOT window against them (`verify_slot_identity.py`):

| Slot | Role in R14                            | Peak curve   | RMS vs logged PUT SP |
|------|----------------------------------------|--------------|----------------------|
| 1    | stock — factory `IP_PUT_SP` target     | 2506 hPa     | 218–253 hPa          |
| 2    | conservative                           | 2699 hPa     | 269–362 hPa          |
| 3    | intermediate                           | 2699 hPa     | 105–121 hPa          |
| 4    | **aggressive — the R09/R10 shelf**     | **2809 hPa** | **6–46 hPa**         |
| 5    | valet                                  | 1705 hPa     | 967–1049 hPa         |

Every one of the six WOT files matches **slot 4**, at 6–46 hPa RMS (0.1–0.7 psi)
against the next-best slot at 2.4–19× the error. Evidence:
`plots/r14_slot_identity.png` — the logged setpoint traces the slot-4 curve
through its entire shape, plateau and taper alike.

That match is also the proof the **reorder took effect**. Under R13, slot 4 held
the conservative curve peaking at 2699 hPa; the logs peak at 280.9 kPa =
2809 hPa, which is the aggressive curve and nothing else. The slot Sam selected
delivered the map R14 says it should.

Three further calibration facts fall out of the same data:

- **`min()` cap semantics hold.** The base `IP_PUT_SP` — Pressure up throttle
  setpoint is parked non-binding at ~30 psi. It never appears as the commanded
  value anywhere in the session; the slot grid always binds. The parked ceiling
  is doing exactly what R11 designed it to do.
- **`IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor is no longer the constraint.** `Torque Lim ()` reads **0 in every
  one of the 769 WOT samples** across all eight files. Code 128 — the
  charge-pressure-ratio limitation that trimmed the R09 shelf by 1.0–1.4 psi —
  is completely absent. Peak measured pressure quotient is 2.88 against the R10
  cap of 3.1. The R10 reshape is validated.
- **The wastegate feedforward tables are live and byte-exact.** Running the
  ECU's bilinear lookup over `IP_FAC_BPA_SP[0]` — Wastegate Position Feedforward,
  VVL 0 as read from the flashed bin reproduces the logged `WG Pos Base (%)`
  with **mean absolute error 0.00 % and r = +1.000 over 560 settled samples**.
  This also fixes the sign convention for everything below: `WG Pos Base` is the
  table cell × 100, so **higher % = more closed**, and
  `WG Pos Final ≈ Base + I + P-D`.

---

## High 1 — a WOT 3→4 upshift into the shelf overshoots to 28.9 psi and rails the boost sensor

> [!warning] The worst boost, airmass, and fuel-rail numbers of the session, and
> none of them appear in `analysis_findings.md`.

In `12_03_17` at t ≈ 8.0 s, a full-throttle 3→4 upshift at 5544 rpm drops the
engine to 3906 rpm — landing exactly on the flat top of the slot-4 curve, where
the target is at its 26.0 psi maximum. Pedal stays at 99.9 % throughout. Boost
then overshoots for ~0.9 s:

| Quantity                     | Value                                          |
|------------------------------|------------------------------------------------|
| Peak `PUT`                   | 300.6 kPa = **28.9 psi gauge** (target 26.0)   |
| Peak `PUT` error             | **+19.7 kPa** (battery High line is +20.0)     |
| Peak `MAP` error             | +15.1 kPa — the manifold really saw it         |
| Samples pinned at the rail   | 10 of 33                                       |
| Peak airmass                 | 1692 mg/stk (ceiling 2000)                     |
| HPFP effective volume        | **100.0 %, pinned for the whole window**       |
| Worst DI rail error          | **−26.2 bar** (battery High line is −25)       |
| Lambda                       | held 0.787–0.807 against a 0.800 target        |
| P0234 margin                 | 713 hPa (lowest of the session)                |

Evidence: `plots/r14_upshift_overboost.png`.

**`PUT` is railed, so 28.9 psi is a floor, not the peak.** The channel sits at
exactly 300.6009 kPa for 10 consecutive samples while every neighbouring value
is distinct — a hard ceiling at ~3.0 bar absolute, not a plateau. `MAP` tracks
`PUT` to within 0.3 kPa here (the throttle has no authority left to trim), so
the manifold saw the same thing. I cannot tell from the log alone whether the
ceiling is the physical sensor or the SimosTools PID scaling; if it is the
sensor, the ECU's closed loop was also running blind above it for that ~0.4 s.

**Why this shift and not the others.** The other two WOT 3→4 upshifts in the
session (`12_00_06`, `12_02_12`) both ended in a pedal lift, so boost decayed
instead of rebuilding — the large apparent errors there are the setpoint
collapsing to ~102 kPa on lift-off, not overboost. `12_03_17` is the only shift
where full throttle was held through and after, and it landed in the 3900–4400
rpm band where the slot-4 target is highest. So this is one occurrence, but the
condition that produced it is ordinary, not exotic.

**Mechanism** (middle panel of the evidence plot): the wastegate is commanded
fully closed (100 %) through the torque cut, which is what keeps boost alive
across the shift. On re-engagement the feedforward base reads ~79 % closed at
the post-shift flow factors, and the closed loop can only trim it — P-D goes to
−13 % and the integral unwinds from +21 % to +13 %, netting ~80 % commanded.
That is not enough authority to catch the spike before the pull ends.

The fuel side is the part I would watch hardest: the rail error walks
monotonically from −3 bar to −26 bar across the window with the HPFP already
saturated. Lambda held this time, but it held with no pump headroom left and the
error still deepening when the pull ended.

---

## Medium 2 — slot 4 under-delivers 0.8–1.5 psi with the wastegate integral carrying the load

Combined clean 3rd-gear WOT bands (`12_00_06`, `12_02_12`, `12_06_23`,
`12_07_51`; pedal ≥ 90 %, gear = 3, rpm ≥ 3000):

| RPM band  | n  | PUT err (kPa) | Delivered | Target | WG Final | WG I  | Turbo max | HPFP max   | Lambda / SP   |
|-----------|----|---------------|-----------|--------|----------|-------|-----------|------------|---------------|
| 3500–4000 | 66 | −5.5          | 25.2 psi  | 26.0   | 70.3 %   | +0.7  | 187 krpm  | 96.8 %     | 0.885 / 0.882 |
| 4000–4500 | 65 | **−10.4**     | 24.5 psi  | 26.0   | 70.8 %   | +3.5  | 199 krpm  | **97.7 %** | 0.852 / 0.854 |
| 4500–5000 | 90 | −6.5          | 24.4 psi  | 25.3   | 66.8 %   | +6.5  | 201 krpm  | 96.1 %     | 0.830 / 0.828 |
| 5000–5500 | 80 | −7.9          | 22.7 psi  | 23.8   | 71.8 %   | +11.5 | 203 krpm  | 94.0 %     | 0.798 / 0.804 |
| 5500–6000 | 85 | −5.5          | 21.0 psi  | 21.8   | 72.4 %   | +15.4 | 201 krpm  | 83.4 %     | 0.802 / 0.800 |
| 6000–6500 | 44 | −1.0          | 19.8 psi  | 19.9   | 72.7 %   | +17.8 | 196 krpm  | 74.5 %     | 0.801 / 0.800 |

The shelf is delivered about **1.5 psi short at 4000–4500 rpm**, narrowing to
on-target by redline. This is a different failure from R09's shortfall: that one
was commanded (code 128 capping the setpoint), this one is authority. The
signature is the integral — `WG I Value` climbs from +0.7 % to +17.8 % with rpm,
which means the feedforward base is systematically **too open** at high flow and
the closed loop is spending its integral just to reach target. Base falls to
50 % by 5000 rpm while Final holds ~72 %; the integral is carrying that ~20 gap.

That is a consequence of history, not a bug: the R05 and R08 feedforward edits
were sized to *cut overboost* against lower targets, before R10 unclamped the
compressor cap. Against the R14 slot-4 curve on a cool sea-level day they now
leave the gate too open. Boost tracking is still good in absolute terms
(−1 to −10 kPa, well inside any safety threshold) — this is a "leaving
performance on the table and burning integral headroom" finding, not a risk one.

Note the interaction with High 1: an integral parked at +20 % is exactly what
slams the gate shut through a shift, and it has less room to unwind afterwards.
The overshooting upshift went in carrying +19.3 %, the highest of the five WOT
upshifts logged; the 3→4 that did not overboost went in at +6.5 %. That is
suggestive, not established, on one event — but it is why the R15 notes below
put this fix first.

---

## Medium 3 — cylinder-1-only knock retard from 5545 rpm to redline, on the hottest pull

`12_07_51` is the only file with any knock retard at WOT, and it is **cylinder 1
alone** — cylinders 2, 3 and 4 read 0.0° for the entire session. It latches at
−3.0° at 5545 rpm and decays through −2.6° and −2.2° to the end of the pull at
6246 rpm (43 samples). The decay pattern is the knock controller walking timing
back after a single event, not repeated fresh knock.

Context: this file has the session's highest coolant (100.8 °C) and oil
(110 °C). IAT at the event was 23 °C and airmass 1210–1366 mg/stk, so it is not
a charge-temperature event. Cylinder 1 was already flagged as the knock-prone
cylinder in the R07 logs at −3.0°, so this is a persistent, localised trait
rather than a new R14 symptom — R14 changed no timing table.

One event in six pulls on cool ambient is not alarming, but it is the cylinder
to watch on a warm day.

---

## Medium 4 — fuel pump headroom is thin even on clean pulls

Before the shift event, normal 3rd-gear pulls already run HPFP effective volume
at **96–98 %** through 3500–5000 rpm, with the worst clean-pull rail sag at
−4.8 bar and LPFP duty peaking 78.2 % (80.1 % session-wide, in 2nd gear). The
low-pressure side has room; the high-pressure side does not. So the rail holds
in steady state, but
there is essentially no high-pressure headroom left in the shelf zone — which is
precisely why the extra ~2.9 psi in High 1 pushed it straight to 100 % and
−26 bar. Any further airmass at 4000–4500 rpm comes out of a pump that is
already at its ceiling.

---

## Low — confirmations and channels within limits

- **Lambda tracks target** across the whole session: max lean excursion +0.028
  against a +0.03 watch line, and the band means sit within 0.006 of setpoint.
  The R00 lambda re-breakpoint and R03 floors are behaving.
- **Turbo speed** peaks 205 krpm against the ~220 krpm limit — ~7 % margin, in
  line with R09/R10 and not worsened by R14.
- **P0234 margin** never drops below 713 hPa against the raised 2700 hPa
  `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold.
  No overboost fault, including through the High 1 event.
- **`C_PRS_IM_SP_MAX`** — Maximum requested intake-manifold pressure setpoint is
  nowhere near binding (peak demand 305.5 kPa against a 35000 kPa ceiling).
- **Zero misfires**, zero torque-limiter codes, LTFT +0.8 %.
- **Temperatures** climbed over the session as expected for back-to-back pulls —
  coolant to 100.8 °C, oil to 110 °C, transmission 21 → 71 °C, IAT peak 36.1 °C.
  Nothing out of range; worth noting the trans temp trend if the session were
  extended.
- **Traction control activity** on the two 2nd-gear segments: `12_03_17` reached
  9.2 km/h front-vs-rear slip with torque cut to 271 Nm against 394 Nm requested
  and timing pulled to **−14.2°**. That −14.2° is the low end of the battery's
  "timing envelope" finding — it is a **TC intervention, not a knock or timing
  calibration issue**, and the battery's suggestion to cross-reference the knock
  finding is a false lead here. Keep 2nd-gear data out of boost and timing
  conclusions, as in the R08 review.

---

## Coverage gap — four of the five slots are unvalidated

R14's change was a **four-slot** reorder, and this session exercised **one** of
them. Nothing here says anything about:

- **Slot 1 — the new stock map.** This is R14's headline new feature and it has
  never been driven. Its curve is read live from the stock bin and verified in
  the bin, but not in the car.
- **Slot 2 (conservative) and slot 3 (intermediate)** — both moved in R14.
- **Slot 5 (valet)** — byte-untouched by R14 and validated previously, so the
  lowest priority, but still unconfirmed on this bin.

A short drive selecting each slot in turn, even one gentle 3rd-gear pull each,
would close this. The check is cheap: `verify_slot_identity.py` classifies any
new log against all five curves automatically.

---

## What this feeds into R15 — candidates, not decisions

None of these are applied; they are what the evidence supports, for Sam to rule
on.

1. **Validate the remaining slots before changing anything.** R14's own
   deliverable is only 20 % confirmed. Changing calibration on top of an
   unvalidated reorder makes the next log harder to read, not easier.
2. **The two wastegate findings are largely separable — the intake flow factor
   row is the discriminator, as it was in R08.** `map_ff_cell_load.py`
   accumulates the bilinear weight each `IP_FAC_BPA_SP` cell receives from each
   finding's samples:

   | Finding                     | n   | Dominant cells                                             | Overlap |
   |-----------------------------|-----|------------------------------------------------------------|---------|
   | Upshift spike (High 1)      | 21  | Int 0.75 × Exh 1.40 (61.6 %), Int 0.75 × Exh 1.00 (17.2 %) | 10.5 %  |
   | Steady shortfall (Medium 2) | 301 | Int 1.05 × Exh 1.40 (39.3 %), Int 0.90 × Exh 1.00 (18.5 %) | 10.5 %  |

   The spike lives on the **Int 0.75** rows — right after an upshift the engine
   is at low rpm with high boost, so intake flow factor is low — while the
   steady-state shortfall lives on **Int 1.05/1.25**. Only ~10 % of each
   population's table load is shared, concentrated in the Int 0.90 blend row.
   So these can be aimed independently; they do not have to move together.
3. **Do Medium 2 first, and it may shrink High 1 for free.** The shortfall fix
   is the better-evidenced of the two (n = 301 across four pulls vs n = 21 in one
   event), sits in cells the spike barely touches, and removes the +19.3 %
   integral pre-load that the overshooting shift carried into the upshift — the
   highest of the five upshifts logged; the 3→4 that did *not* overboost went in
   at +6.5 %. Raising the Int 1.05/1.25 cells so the integral stops doing
   feedforward's job may therefore reduce the spike without touching the Int
   0.75 rows at all. Caveat: it puts more airmass through a fuel system already
   at 97 % HPFP (Medium 4), so it should be sized conservatively.
4. **High 1 cannot be sized from this log even if you want to fix it directly.**
   The R05/R08 method takes *measured* overshoot as the input to the ~0.05
   WG-position-per-psi rule. Here the measurement is censored: `PUT` railed for
   10 of 33 samples, so the overshoot is only known to be **≥ +19.7 kPa**. And
   61.6 % of the spike's table load rides on a single cell whose weight is fixed
   by ~21 samples over 0.9 s — a slightly different landing rpm redistributes
   that between the Exh 1.00/1.40 columns and the Int 0.60/0.75/0.90 rows
   (11.4 % already sits on Int 0.60). A second instance is what turns this from
   a bounded-below anecdote into a sizable edit.
5. **Consider whether the boost sensor's ~3.0 bar ceiling is now a design
   constraint.** A 26 psi target that transiently rails the sensor means the
   closed loop may lose feedback exactly when it most needs it. Worth confirming
   whether the rail is the sensor or the logging PID before treating it as one.

Still **revision 14 — a starting point, not a finished calibration**. Slot 4
delivers what R14 says it should; the rest of the ladder is unproven, and the
tune's remaining margin is in the fuel system, not the turbo.
