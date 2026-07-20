# BasicsGuide_R11 Log Review

Living review document for `5G0906259L_0002_BasicsGuide_R11.bin` flash logs
(flashed as `CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R11.bin`, confirmed by
the SimosTools header tag in all four CSVs). R11 is R10 plus: `IP_PUT_SP` —
Pressure up throttle setpoint parked at a non-binding ~3085 hPa full-load
ceiling, and all five switch-patch `PUT setpoint` grids rewritten as explicit
lower caps on a shared twelve-point `PUT SP RPM Axis`. R11 carries R10's
`IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger compressor
reshape. CAL-flash eligible on the installed R07 patch set.

## 2026-07-19: R11 validation review (first drive of the 12-point cap axis)

Analysis battery: `python -m simoscal.analysis Logs/BasicsGuide_R11` — all 11
checks ran, cal resolved, **no skips**. See `analysis_findings.md` / `.json` and
`plots/analysis_*.png`. Band comparisons and the setpoint-curve reconstruction
below are my own follow-up over the raw CSVs (pedal ≥ 80 %).

### Reviewed files

Four files, **two detected WOT pulls**. No slot indicator is logged; slot is
classified from the full-load `PUT SP` ceiling. All four files top out at
**280.9 kPa (2809 hPa)** — the R11 **slot 3** curve (the former R10 slot-2
26 psi shelf). Slots 1/2/4/5 were never selected in this session.

| File (simostools-2026_07_19-…) | Rows | Pulls | Slot | Max pedal % | Max PUT SP (kPa) | Notes                                            |
|--------------------------------|------|-------|------|-------------|------------------|--------------------------------------------------|
| 19_02_22                       | 314  | 1     | 3    | 99.9        | 280.9            | 4th-gear pull, 3608–4789 rpm.                     |
| 19_05_02                       | 242  | —     | 3    | 89.7        | 280.9            | Part-throttle 4th/5th; below the 95 % pull gate.  |
| 19_12_15                       | 240  | —     | 3    | 86.2        | 280.9            | Part-throttle 4th/5th; below the 95 % pull gate.  |
| 19_23_18                       | 413  | 2     | 3    | 99.9        | 280.9            | 4th-gear pull, 3014–5309 rpm — the best pull.     |

Gear note: header is `Gear (gear)` = actual gear numbering, no offset applied.
Both pulls are **4th gear**; the R08/R09 lineage was logged in 3rd.

Data quality: 0.040 s sample interval, 0 time gaps, no stuck dynamic channels,
no duplicate-channel collisions in any file.

---

### Headline 1: the 12-point axis and the slot-3 cap are live and exact

The commanded `PUT SP` reconstructed from the logs matches R11's stored slot-3
calibration across the whole driven range. Stored slot 3 is the R09
`[3000, 3400, 4400, 5000, 5750, 6500] → [2699, 2809, 2809, 2712, 2519, 2243]`
hPa target resampled onto the twelve-point axis; the ECU commanded:

| RPM bin   | Commanded PUT SP mean (kPa) | Stored slot-3 curve at that rpm (kPa) |
|-----------|-----------------------------|----------------------------------------|
| 3000–3250 | 272.7                       | 269.9 → 276.8 (2699 → 2754 ramp)       |
| 3250–3500 | 279.8                       | 276.8 → 280.9                          |
| 3500–4500 | 280.9                       | 280.9 (flat shelf)                     |
| 4500–4750 | 277.6                       | 279.3 → 275.2 (taper start)            |
| 4750–5000 | 273.9                       | 275.2 → 271.2                          |
| 5000–5250 | 268.2                       | 271.2 → 264.8                          |
| 5250–5500 | 264.1                       | 264.8 → 258.3 (samples only to 5309)   |

Every bin lands on the stored curve. That validates, in-car, the three things
R11 changed: the patch `PUT SP RPM Axis` at `0x7D7DC` reads as a 12-point axis,
the slot-3 `PUT setpoint` grid at `0x7D59A` holds the resampled shelf, and the
parked `IP_PUT_SP` ceiling stays non-binding (it never appears as the commanded
value — the slot cap always binds, consistent with the R09-proven `min()`
semantics). Evidence: `plots/analysis_boost.png` middle panel, dashed PUT SP.

### Headline 2: mid-range delivery is on target — better than R09 on the same curve

The same 26 psi target curve under-delivered in R09. It now tracks:

| RPM band  | R09 slot 2 (3rd gear, pulls 10/13/14) | R11 slot 3 (4th gear, pull 2) | Setpoint |
|-----------|---------------------------------------|-------------------------------|----------|
| 3500–4000 | 274.4–279.1 kPa (25.1–25.7 psi)       | 282.5 kPa (26.4 psi)          | 280.9    |
| 4000–4500 | 271.8–272.7 kPa (24.7–24.8 psi)       | 279.7 kPa (26.0 psi)          | 280.8    |
| 4500–5000 | 266.3–267.0 kPa (23.9–24.0 psi)       | 270.9 kPa (24.8 psi)          | 275.4    |
| 5000–5500 | 256.7–257.3 kPa (22.5 psi)            | 259.7 kPa (23.1 psi)          | 267.2    |

The 4000–4500 band went from roughly −8 kPa short of target to −1 kPa. That is
the outcome R10's `IP_PQ_CHA_MAX` reshape was written to produce (clearing the
compressor-pressure-ratio cap that was trimming the shelf), and it is the first
evidence it worked.

**Caveat — this comparison is gear-confounded.** R09's pulls were 3rd gear and
R11's are 4th; 4th gear sweeps rpm more slowly, giving the turbo more time per
rpm band. Some of the gain is that, not calibration. To settle it, one 3rd-gear
slot-3 pull is needed (see next steps).

### Headline 3: this session does not validate R11's actual headline change

R11's point was the tapered cap above 4400 rpm on the new 12-point axis. The
highest rpm reached in any pull was **5309**. Everything from 5400 to 6500 rpm
— five of the twelve axis breakpoints, and the region where turbo speed, HPFP
volume, and heat all peak — is **unlogged**. Table coverage confirms how thin
the loaded-WOT sample is: 9/256 cells of `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]`
— ignition base map, 9/96 of `IP_LAMB_BAS_HPDI[1]` — basic lambda setpoint grid,
4/24 of `IP_PUT_SP` — Pressure up throttle setpoint. Two pulls, one gear, one
slot, ~15 s of loaded WOT total.

Read R11 as "the mechanism works and the mid-range is good", not as validated.

---

## Findings

### Medium — top-end boost deficit opens up above 4700 rpm

Tracking is essentially exact 3500–4500 rpm (error within ±2 kPa), then the
actual falls progressively below the tapering setpoint: −4.5 kPa mean over
4500–5000 and −7.5 kPa mean over 5000–5500, reaching about −9 kPa at 5200 rpm
(`plots/analysis_boost.png`, bottom panel, orange trace). Wastegate has room —
`WG Pos Final` sits at 60–75 % mean with brief 100 % excursions, and the WG
integral bottoms at only −1.2 %, so this is not authority saturation. It reads
as airflow/compressor-side capability at the top of the IS20 map rather than a
control problem, but with the deficit still growing at the last logged point and
nothing logged past 5309 rpm, the shape of it above 5400 rpm is unknown.

### Low — no knock seen, but the sample is too small to mean much either way

All four per-cylinder knock channels read a **flat 0.00° over every row of all
four files**. Two questions, separately:

**Is the channel live?** Yes — treat it as such. The R09 and R11 CSV headers are
byte-identical across all 83 columns, so the PID list did not change between the
two sessions, and R09's logs on that same list showed retard down to −3.0°. The
battery's boilerplate about verifying PID liveness is conditioned on a PID-list
change; none happened here, so it does not apply.

**Is zero knock meaningful?** Not very. Counting discrete events rather than
rows, R09 logged **5 knock events across 1733 loaded-WOT rows**. At that rate
R11's 374 WOT rows would expect ~1.1 events, making **P(zero) ≈ 34 %** — a
coin-flip-ish outcome under R09's own behaviour. So this session shows nothing
alarming, and would not have been expected to show much regardless.

Net: no action, no special check needed. The top-end pull requested below will
supply the WOT rows that make the knock trace worth reading.

### Medium — turbo speed and heat are in the watch band

Turbo speed peaks **205 krpm** (watch 190, limit 220) at only 5309 rpm, with the
taper region above that unlogged. Coolant peaks **99 °C**, oil **109 °C**, IAT
**36 °C** — pull 2 started at 99.2 °C coolant, i.e. it was a heat-soaked pull.
Nothing is over a limit, but 205 krpm before the rpm where turbo speed normally
peaks is the number to watch on the next top-end pull.
Evidence: `plots/analysis_turbo_heat.png`.

### Low — the lambda flag is a spool transient, not a settled lean condition

The battery flagged settled-WOT lambda lean by +0.049. Traced to the raw rows:
only **2 samples (~0.08 s)** exceed +0.03, both at 3063–3081 rpm during pull 2's
tip-in, peaking at lambda 0.976 vs setpoint 0.909 (+0.066) while airmass was
still ramping through 1138 mg/stk. Once loaded, commanded lambda goes to 0.80
and measured tracks it — pull 2's settled error range is −0.037…+0.003. This is
fuelling catching up to a fast airmass ramp, not a lean cruise at load. Worth
nothing more than a re-check if it grows. Evidence: `plots/analysis_lambda.png`.

### Low — transient boost overshoot, +13.3 kPa for 0.08 s

Pull 1 overshoots at 3660–3672 rpm by +13.2 kPa mean / +13.3 kPa peak over
0.08 s — above the +10 watch line, below the +20 high line, and not sustained
(the sustained test needs 0.5 s at +15). Wastegate integral had headroom at the
time (min −1.2 %, final command 54.0 %). P0234 margin is comfortable: logged
PUT-minus-ambient peaks 1928 hPa against the
`IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold of
2700 hPa, a 772 hPa margin. Evidence: `plots/analysis_wastegate.png`.

### Low — fuel system held, with modest headroom left

DI rail sag worst-case **−2.9 bar** against a 200.0 bar setpoint (watch −10) —
the rail held essentially flat all session. **LPFP duty peaks 77.1 %**, **HPFP
effective volume peaks 97.0 %**. HPFP at 97 % has little left, but the rail is
not sagging, so the pump is meeting demand. Both numbers were taken below
5400 rpm; top-end demand is unlogged. Evidence: `plots/analysis_rail_pressure.png`.

### Low — timing pull-back is spark-map scheduling, not protection

Delivered timing over loaded WOT (airmass ≥ 900 mg/stk, TPS ≥ 60 %) spans −17.6°
to +0.4°, mean −5.7° over 367 samples. `Torque Lim` reads **0 on every row of
all four files** — no torque-limiter activity anywhere — and knock retard is
zero throughout. The single −17.6° sample is one row at 5237 rpm. With no
limiter and no knock, this is the base ignition map plus IAT/charge correction
doing what it is calibrated to do. Evidence: `plots/analysis_ignition.png`.

### Low — boost stays far under the calibrated ceiling

Demanded manifold-pressure setpoint peaks 317.4 kPa against the
`C_PRS_IM_SP_MAX` — Maximum requested intake-manifold pressure setpoint ceiling
of 35000.0 kPa. Non-binding by design, as intended.

### Housekeeping

`CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R11.bin.txt` in this folder is
**0 bytes**. The battery resolved the calibration from the filename, so nothing
was skipped, but the record itself is empty — worth re-exporting if that file is
meant to capture the flashed bin's contents.

---

## What this feeds into the next revision

1. **Get the missing data before changing anything.** One 3rd-gear slot-3 pull
   from ~3000 rpm to redline answers three open questions at once: whether the
   mid-range gain survives the faster 3rd-gear sweep, what the taper actually
   delivers from 5400–6500 rpm, and where turbo speed / HPFP volume land at the
   top. Nothing above 5309 rpm should be re-calibrated before that pull exists.
2. **Read the knock trace off that pull**, where the WOT sample is finally large
   enough for a zero to carry weight. Nothing needs checking beforehand.
3. **Then, if the top end confirms the 4700+ rpm deficit**, the candidate change
   is wastegate-side — `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost pressure actuator
   setpoint in the top-end cells, not a higher target. Raising the slot-3 cap
   would only widen a deficit the turbo is already not meeting.
4. **Do not raise slot 3's shelf.** Delivery is at target 3500–4500 and short
   above it; there is no evidence of unused capability to claim.
