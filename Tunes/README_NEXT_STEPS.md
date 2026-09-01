# Next steps — Tune lineage

Living scratchpad for **what we want to change in upcoming tune revisions**, before
the work is scripted. One section per planned revision, newest ideas appended as
they come up. When a revision is actually built, its authoritative record moves to
`REV_LOG.md` (per-revision rationale) and the revision script's own header
history — this file is the pre-work idea queue, not the change log.

This file now lives at the `Tunes/` root and spans both project folders: it
tracked `TuningBasicsGuide` (R00–R15) alone until R15, and continues into
`MainTune` (R16 onward) — see `REV_LOG.md` for the project split.

Current lineage tip: **R22 — built and verified, awaiting human review and a
flash**. It reorders the map slot ladder by **fuel requirement** rather than by
boost and adds a second octane arm, so the boost-versus-timing trade can be
measured against a control in one session:

| Slot | Boost                                         | Timing           | Fuel      | Role                                         |
|------|-----------------------------------------------|------------------|-----------|----------------------------------------------|
| 1    | ~21.6 psi to 3800 rpm, then slot 2's to ~17.2 | base             | pump 92   | low / bad tank                               |
| 2    | conservative ~24.5                            | base             | pump 92   |                                              |
| 3    | aggressive ~26.0                              | base             | pump 92   | **everyday map, in-drive fallback, control** |
| 4    | mid ~24.4 psi                                 | R20 octane shape | **dosed** | reduced-**boost** arm                        |
| 5    | aggressive ~26.0                              | R21 octane shape | **dosed** | reduced-**timing** arm                       |

Slot 1 also stops being the factory curve above 4400 rpm — it takes slot 2's
there and falls to ~17.2 psi at redline, so the safe map is now safest exactly
where cylinder pressure is worst. Five tables move, all per-slot. Read `REV_LOG.md` § R22 before flashing, and log
it as **interleaved slot 3 / 4 / 5 pulls on one dosed tank**.

**The in-drive fallback is now slot 3, not slot 4.** Slot 4 is one of the two
maps that needs the dose. And when reading any `Logs/` folder: before R22, slot 4
means the aggressive pump-gas control; from R22 on it means the mid-boost octane
map. Record the selected slot per session rather than inferring it.

**R21 was built and verified but never flashed.** Its slot 5 timing is carried
forward into R22 byte for byte; nothing about it was rejected. R22's byte audit
is taken against the R20 bin, which is what the car actually holds.

**R20 was flashed, logged, and reviewed** on 2026-08-31 (`Logs/BasicsGuide_R20/`,
ten pulls). Its timing arrived as designed — the modifier lands in `Ign Avg`, not
`Ign Table`, correcting what the R20 gate predicted — but all ten pulls were slot
5, so there is no within-session control and R20 had to be scored cross-session
against R19 with day and fuel as confounds. Knock roughly doubled (15.33 vs 8.63
events per loaded minute) and went one step deeper (−2.25 vs −1.50 °CRK), all of
it attributable to 4500–5000 rpm. Sam's octane-mixing hypothesis was tested and
not supported (rank correlation of knock area with time +0.008).

**Queued for R23, gated on R22 logging clean:**

- **Raise near-redline timing.** 6000 rpm has room inside the +5.00 °CRK
  delivered ceiling (base +1.875, so the modifier could reach +3.000). 6500 rpm
  does not — R20/R21 already deliver +4.500 there and +1.500 modifier /
  +4.875 delivered is the last storable step under the guard. Held out of R21
  and R22 to keep each revision single-variable — and note R22's two octane
  arms barely separate above 6000 rpm (20 hPa by 6500), so that band is
  untested by R22 either way.
- **Write the 1049.97 mg/stk row of the `Spark modifier` grid.** At 6000+ rpm
  airmass runs ~1204 mg/stk, right at the 1200.01 breakpoint, so the grid
  interpolates down toward the neutral row and only ~90% of the column value is
  actually delivered at redline load.
- **The pre-existing 3000–3500 rpm knock zone.** Highest event rate in either
  session (43.2/min on R19 with no modifier), and where R20's two-cylinder
  same-sample events sit. Not caused by the modifier, never addressed, and the
  reason R20's AE6 gate failed as written.

**Do not re-breakpoint the `Spark modifier` grid's axes.** Checked during R21:
the rpm axis `0x3CE5A` and airmass axis `0x3CDBC` are each referenced by 37
tables — all 18 `IP_IGA_BAS_IVVT_VVL_PORT_L` — Basic ignition angle maps plus all
five slots' modifier grids. Moving a breakpoint re-indexes the whole ignition
calibration on every slot, slot 1 (stock) and the control slot included.
Re-confirmed as a standing "do not" during R22.

Its predecessor **R19 was flashed, logged, and reviewed** on 2026-08-30 (see
`Logs/BasicsGuide_R19/log_review.md`): it met all five of its measurements, but
it was flashed with code-review P1 open against the intake-axis re-breakpoint,
which that session did not test and which is **still open**. R19 was the first
revision to touch knock control, and the first since R07 to move two domains at
once (knock fast loop + wastegate feedforward), on Sam's direction.

**R18 was flashed, logged twice, and validated.** See
`Logs/BasicsGuide_R18/log_review.md`. Both outstanding data steps landed on
2026-08-28: the cool-air re-log (8 pulls at 26.6 °C loaded IAT, matching the R17
baseline) and the per-cylinder knock-sensor channels. Their answers:

- The 4500–5000 rpm pocket correction holds in matched air — 2 events over 21
  band-covering segments where R17's rate predicts 10.5 — and costs no measurable
  power (251 vs 252 F=ma wheel hp).
- The hot session's 5706/6084 rpm events were heat. Zero loaded knock above
  5000 rpm in cool air.
- **Sensor saturation is ruled out.** THD peaks 2.68–3.46 V against the 4.004 V
  clamp; NL never exceeds 1.53 V against the ~2 V onset. So the events are real
  threshold crossings, **R19 is the recovery change and not a gain change**, and
  `IP_KNKS_GAIN_PRE[0..3]` stays at stock.

That review reads **3rd and 4th gear WOT**, not 3rd alone, with the DSG shift
trimmed out of every gear-attributed segment. Two things follow that the earlier
3rd-gear-only pass could not see: six of ten knock events across the three
sessions are still recovering in 4th gear (which is the R19 case), and eleven WOT
3 → 4 upshifts show no sign of the R14 overboost. Keep holding WOT into 4th when
logging.

R16 was never flashed, and R17 is superseded.

**`Tunes/MainTune/` is active** for R16 onward, with output bins renamed to
`Patched_259L_R<NN>.bin` (dropping the `CB_HSL_SP2933_..._BasicsGuide_` prefix
used through R15). R16 is the first MainTune revision; R18 is the current
verified candidate at
`MainTune_out/R18_20260826-171645/Patched_259L_R18.bin`. Its script is
`TUNE_MainTune_R18.py`.

**R14 was the first real calibration change in the `simoscal.tune` API** — a stock
map on slot 1 and the drivable slots ordered least→most aggressive (1 stock
~21.6 psi, 2 conservative, 3 intermediate, 4 aggressive), slot 5 valet unchanged.
Only the four per-slot `PUT setpoint` grids moved; the shared base is
byte-identical to R13/R12. Flashed and validated in-car on 2026-08-10 —
`Logs/BasicsGuide_R14/log_review.md` remains the evidence base for the open slot
and upshift items below.

## Still open — validate the four slots R14 moved but nobody drove

The 2026-08-10 session was **slot 4 only**, so R14's four-slot reorder is 20 %
confirmed. Slot 4 matched its stored curve at 6–46 hPa RMS against the next-best
slot at 2.4–19× the error, which also proved the reorder took effect (under R13
slot 4 held the 2699 hPa conservative curve; the logs peak at 2809 hPa), and it
re-confirmed the R09 `min()` cap semantics — the base `IP_PUT_SP` — Pressure up
throttle setpoint parked at ~30 psi never binds. Still unconfirmed:

- **Slot 1 (stock)** — R14's headline new feature, never driven. Confirm it holds
  ~21.6 psi and that the shared tuned base (timing, lambda, wastegate) behaves
  sanely at the lower boost target — a stock *slot* is not a stock ECU.
- **Slot 2 (conservative)** and **slot 3 (intermediate)** — both moved in R14.
- **Slot 5** — was the valet cap (byte-untouched by R14, validated at R12) and
  never driven on this bin. **R20 retired the valet map**: slot 5 now carries
  slot 4's boost curve plus its own timing advance, so this item is superseded —
  what needs confirming there is the R20 A/B, not a 10 psi cap.

One gentle 3rd-gear pull per slot closes this, and the check is automated:
`python3 Logs/BasicsGuide_R14/verify_slot_identity.py` scores any log against all
five stored curves and names the best match. Keep it to its **own session** —
validating the slot ladder and R15's feedforward edit in one log makes both
harder to read, whichever order they happen in.

## R15 — flashed, logged, and reviewed

Moved out of this queue: R15 walks back R08's wastegate deepening in the five
`IP_FAC_BPA_SP[0]` / `[1]` — Wastegate Position Feedforward cells the R14 logs
show under-delivering, every value bounded at its R07 value. Deltas were solved
against the measured per-band shortfall, not guessed
(`Logs/BasicsGuide_R14/size_r15_wastegate.py`).

Full rationale, sizing method, predicted per-band effect and verification:
`REV_LOG.md` § R15. Script: `TUNE_Basics_Guide_R15.py`. Verified run:
`TUNE_Basics_Guide_out/R15_20260810-212341/` — 24 changed bytes vs R14, 0
unexplained, exactly 2 tables differ.

The 2026-08-25 slot-4 logs cleared R15's validation gate. Boost tracking improved
through 3500–5000 rpm, the redline wastegate integral fell from +17.8 % to
+12.5 %, and neither DI rail pressure nor lambda control regressed. Two isolated
−3.0° knock events occurred at 4596 and 4751 rpm, so the midrange remains out of
scope for timing increases. Full evidence: `Logs/BasicsGuide_R15/log_review.md`.

## Blocked on data — the WOT upshift overboost (priority lowered 2026-08-28)

> **Not reproducing on the post-R15 calibration.** Reading 4th-gear WOT across
> both R18 sessions puts eleven full-throttle 3 -> 4 upshifts in view. **None
> railed the PUT sensor** (peaks 247-287 kPa) and the worst overshoot through any
> of them is **+8.2 kPa**, against the R14 event's >= +19.7 kPa. That is what the
> R15 hypothesis below predicts: the feedforward walk-back stops the integral
> arriving at the shift wound up. It does not bound the original R14 overshoot, so
> it does not license a fix sized from that event — but it is a reason to stop
> hunting a second instance rather than to keep waiting for one. Evidence:
> `Logs/BasicsGuide_R18/log_review.md` § Low — the R14 WOT upshift overboost.


`Logs/BasicsGuide_R14/log_review.md` High 1: a full-throttle 3→4 upshift landed
in the shelf and overshot to **≥ 28.9 psi**, with HPFP pinned at 100 % and the DI
rail sagging −26.2 bar. **Do not aim a fix at this yet** — the `PUT` channel
railed at 300.6 kPa for 10 of 33 samples, so the overshoot is only known to be
**≥ +19.7 kPa**, and the R05/R08 sizing rule takes measured overshoot as its
input. There is no number to size from.

What would unblock it:

- A **second logged instance** — hold WOT through a 3→4 upshift that lands in the
  3900–4400 rpm band. One that does not rail bounds the true peak.
- Note that 61.6 % of the event's table load rode on a single cell
  (Int 0.75 × Exh 1.40) fixed by ~21 samples over 0.9 s, so cell attribution is
  fragile on one pass; a second trajectory firms it up.
- **The R15 edit above may shrink this on its own.** The overshooting shift went
  in carrying a +19.3 % integral pre-load, the highest of the five WOT upshifts
  logged; the 3→4 that did *not* overboost went in at +6.5 %. If the feedforward
  stops leaving the integral wound up, the gate is not held shut going into the
  shift. Suggestive on one event, but it is why R15 goes first.
- Separately, establish whether the ~3.0 bar `PUT` ceiling is the **physical
  sensor or the SimosTools PID scaling**. If it is the sensor, the ECU's closed
  loop is also blind above it, and a 26 psi target that transiently rails it is a
  design constraint, not just a logging nuisance.

## RESOLVED 2026-08-28 — the per-cylinder knock-sensor channels

**Logged, and they answered the question.** `knks_thd[0..3]` and all four `nl`
candidate groups were logged across eight cool-air pulls on 2026-08-28. Outcome,
with full evidence in `Logs/BasicsGuide_R18/log_review.md`:

- **`nl[0..3]` = `0xD00142B2`** (2 bytes each, volts = `raw / 13107`). The
  decisive test proposed below — reproduce `knks_thd` through
  `IP_KNKS_THD_FAC[0..3]` — Knock detection threshold factor — settles it: only
  this array leaves a non-negative adder (0.00 % of samples negative, mean 0.289–
  0.292 V and identical on all four cylinders to within 0.003 V). The other three
  need a negative adder on 10–38 % of samples, which the ECU's formula forbids.
- **No saturation.** THD peaks 2.68–3.46 V against the 4.004 V `C_KNKS_THD_MAX`
  clamp and never spends a sample above 3.5 V; NL peaks 1.53 V against the ~2 V
  onset, with 0.00 % of samples above 2 V. In the 5500–6200 rpm window that
  carried the hot session's unexplained events, THD sits 0.88–1.33 V below the
  clamp.
- **The gain-ordering suspicion below is falsified.** Measured NL ranks
  4, 1, 2, 3 against the gain-predicted 1, 4, 2, 3, and the whole spread across
  cylinders is 0.091 V (8.6 % of the mean) — far too small to explain a 5-versus-0
  event split. Cylinder 1 has the most events and only the second-highest noise
  floor.

**So: leave gain alone, and R19 is the recovery change, not a gain change** — the
branch § What the answer decides anticipated. Still not logged: **RNG**, the raw
sensor feedback. None of the four groups ever crosses THD, so none of them is it.
That only matters if a future question needs event-level confirmation rather than
threshold health; `PIDs/find_ram_symbols.py` is the tool that would find it.

The rest of this section is kept as the record of how the channels were found.

---

**Original entry — we need to log NL, THD and RNG per cylinder.** This was the
single highest-value logging change outstanding, and it gated the entire knock
domain: sensitivity, correction depth, and recovery speed all became guesswork
without it.

### Why

`knowledge/ecu-tuning-not-the-basics.md` § Timing and knock control describes
"ghost knock" — knock-sensor saturation. Engine noise rises naturally with rpm.
The sensor noise level (NL) should track roughly 0.5 V at idle to 1 V by
6000 rpm. The detection threshold is derived from it as
`THD = (NL × global knock-threshold factor) + knock-sum adder`, and an event is
recorded whenever the raw sensor feedback (RNG) exceeds THD. Once NL passes
about 2 V, THD flatlines at its 4 V ceiling, the sensor stops adapting, and it
reports events that are — in the guide's words — "probably not knock".

R18's review ruled out *rough-road* false knock but is blind to this mechanism:
saturation is **per-cylinder** (so cylinder simultaneity does not discriminate)
and **rpm-driven** (so scatter across road speed does not either). The guide's
own saturation example sits at 5366 rpm and rising — the same region as R18's
two new events at 5706 and 6084 rpm.

The circumstantial pattern is uncomfortable. Across R17 and R18 combined, the
stock last-row pre-window gain ranks exactly inversely against event count:

| Cylinder | `IP_KNKS_GAIN_PRE` mean, last row, ≥4512 rpm | Knock events, R17+R18 |
| -------- | -------------------------------------------- | --------------------- |
| 1        | 33.7                                         | 4                     |
| 4        | 36.3                                         | 3                     |
| 2        | 38.4                                         | 1                     |
| 3        | 40.0                                         | **0**                 |

Adding to these tables *lowers* gain, so a lower stock value means a higher noise
floor — the noisiest cylinder knocks most, and cylinder 3 has never logged an
event in fifteen pulls. The main `IP_KNKS_GAIN[0..3]` — Gain value for each
cylinder tables are nearly uniform (means 46.9–48.0), so the spread lives in the
pre-window family. This is suggestive only: eight events over four cylinders is
a tiny sample, a perfect four-way ordering arises by chance about 4 % of the
time, and cylinders 1 and 4 knocking most is also the textbook inline-four
end-cylinder thermal pattern. Gain and cylinder position are confounded and no
existing log can separate them.

### The ceiling the guide warns about is real, and it is set low on this car

`C_KNKS_THD_MAX` — Maximum value for KNKS_THD reads **4.004 V** in the untouched
stock bin `Code/bin/5G0906259L__0002.bin`. The guide's "once thd reaches 4V the
sensor has been fully saturated" is not a generic sensor property — it is this
calibration constant, and VW applied it about a volt below the 4.99 V Bosch
default the XDF description cites. The saturation mechanism is therefore
demonstrably live on this ECU at exactly the value the guide describes. That does
not prove THD is *reaching* it in our 5000–6100 rpm events; only a log can show
that. It does mean the hypothesis is not speculative.

### The channels to log — exact signal names

The Simos18 Funktionsrahmen (`References/Simos18 Funktionsrahmen.pdf`) names
these precisely. All are per-cylinder `[NC_CYL_NR]` arrays in volts, so the
guide's "nl / thd / rng" shorthand maps as:

| Guide term | Bosch signal           | Funktionsrahmen description                                    |
| ---------- | ---------------------- | -------------------------------------------------------------- |
| NL         | `KNKS_REF[0..3]`       | reference (noise) level per cylinder                           |
| THD        | `KNKS_THD[0..3]`       | detection threshold; capped by `C_KNKS_THD_MAX` = 4.004 V      |
| RNG        | `KNKS_RNG_H[0..3]`     | knock-window signal, before tuneable gains and gain adaptation |
| —          | `KNKS_PRE_RNG_H[0..3]` | knock noise acquired during the **pre**-window                 |

`KNKS_PRE_RNG_H` is worth including because the per-cylinder spread that
correlates with our event counts lives in the *pre-window* gain family
(`IP_KNKS_GAIN_PRE`), not the main one. Twelve channels covers REF/THD/RNG_H;
sixteen covers the pre-window too.

Detection is `KNKS_RNG_H[cyl] ≥ THD[cyl]`, so logging all three together shows
directly whether a recorded event was a genuine threshold crossing or a
consequence of THD being pinned.

### SOLVED for the threshold — `knks_thd` recovered from the firmware

**`knks_thd[0..3]` = `0xD000EFE3`, `0xD000EFE4`, `0xD000EFE5`, `0xD000EFE6`** —
one unsigned byte each, physical volts = `raw / 51.2`.

Recovered by disassembling the ASW rather than buying an A2L. Tool:
`PIDs/find_ram_symbols.py`. Method and the four independent confirmations:

1. **Register bases derived, not assumed.** Simos18 pins address registers to
   fixed bases at boot. Taking the mode of `known_address − offset` over the 73
   RAM addresses we already log recovers a0 = `0xD0018000` (761 supporting
   references) and a9 = `0xD000C000` (532). These match the values published on
   the Simos Wiki. Seeding a1 = `0xA0808000` from the same source puts **100 %**
   of a1-relative references inside the CAL block, which confirms it.
2. **The anchor is unique.** `C_KNKS_THD_MAX` — Maximum value for KNKS_THD sits
   at CAL `0xa91f`, i.e. `0xA080A91F`, and the entire 2 MB ASW contains
   **exactly one** reference to it — `ld.bu` at file `0x0c7bb0`. That is the
   clamp, so the surrounding code is the threshold routine.
3. **The pointer is 8 bytes earlier.** The instruction immediately preceding the
   clamp is `lea [a9]+0x2fe3` → `0xD000EFE3`: the base pointer of the array being
   clamped. `[0]` is referenced by five `lea` instructions across the image while
   `[1]`–`[3]` are never referenced individually — the signature of an array
   reached by base pointer plus cylinder index.
4. **Scaling verified against our own bin.** `C_KNKS_THD_MAX` stores raw byte
   **205**. Under the A05 `x / 51.2` scaling that is 4.00391 V, and `simoscal`
   independently decodes the same constant as 4.00390625 V. The A05 equation is
   therefore correct for this box code.

Cross-check: interpolating the A05 address `0xd0015ea5` onto the S50 map using
its two nearest known neighbours (`Accel. Lat` and `LTFT`, whose spans are 483
and 481 bytes in the two builds) predicts `0xd000efe3` — the same address the
disassembly found, arrived at independently.

### Still open — `nl` (noise level), narrowed to four candidates

`nl[0..3]` is four consecutive **2-byte** values, physical volts =
`raw / 13107`. It has not been pinned down as firmly as the threshold, because
there is no single-reference calibration constant to anchor on.

Evidence so far: every `lea` into RAM within ±700 bytes of the threshold clamp
was enumerated, and the candidates cluster where interpolation from the A05
address `0xb000bfea` predicts (`~0xd00142be`):

| Candidate    | vs. interpolation | Refs in ASW | Refs near the clamp |
| ------------ | ----------------- | ----------- | ------------------- |
| `0xd00142b2` | −12               | 10          | **7**               |
| `0xd00142c2` | +4                | 2           | 2                   |
| `0xd0014274` | −74               | 6           | 2                   |
| `0xd001429c` | −34               | 4           | 2                   |

`0xd00142b2` is the most-referenced array in the routine and `0xd00142c2` is
closest to the interpolated position; neither is proven.

**Resolve it empirically rather than by more static analysis.**
`PIDs/knock_sensor_candidates.csv` holds ready-to-paste rows: the four confirmed
`knks_thd` channels plus all four `nl` candidate groups (20 PIDs). Logging a
wrong address is read-only and harmless. One pull identifies the real `nl`: it
must sit near 0.5 V at idle, rise toward 1 V by 6000 rpm, differ between
cylinders, and — the decisive test — reproduce `knks_thd` when multiplied by
`IP_KNKS_THD_FAC[0..3]` — Knock detection threshold factor and offset, since
`THD = (NL × factor) + adder`. The wrong arrays will not satisfy that.

### Budget — it fits

`PIDs/20260828 List.csv` currently runs 73 native PIDs totalling 132 bytes, plus
9 calculated channels that cost nothing on the bus. Twelve new channels need
12–24 bytes depending on width. If the sample interval needs protecting, these
are droppable for a knock-focused session and free 27 bytes between them:

`FP MPI`, `FP MPI SP`, `Inj PW MPI`, `Fuel Split MPI` (the car is not running
MPI), `Fuel Level`, `Cruise`, `EOI Limit`, `SOI Limit`, `Trans Temp`,
`Accel. Lat`, `Wheel Speed FL`, `Wheel Speed FR`, `Exh Pres Desired`,
`DV Position`, `Port Flap Pos`, `Battery Volts`, `Eth Content`.

Keep `Engine Speed`, `Airmass`, `Knock Cyl 1–4`, `IAT`, `Ign Avg`, `Ign Table`
and `TPS` — the new channels are only interpretable against the gain tables'
rpm × airmass axes.

### What the answer decides

- **THD flatlines at 4 V through 5000–6100 rpm** → the high-rpm events are
  sensor saturation. The fix is the gain tables `IP_KNKS_GAIN[0..3]` /
  `IP_KNKS_GAIN_PRE[0..3]` — Gain value for each cylinder: add roughly 10 % to
  the last one or two airmass rows only, worst cylinder first, per the guide.
  That becomes R19, ahead of the recovery change.
- **THD stays off its ceiling** → the events are real detonation. Gain must not
  be touched, and the recovery change in § R19 candidate is the right next move.

**Answered 2026-08-28: the second branch.** THD never came within 0.5 V of its
clamp. Gain stays at stock and § R19 candidate is the next move.

Either way, **do not halve `IP_IGA_DEC_KNK`** — Spark retard at recognised
knocking. It is the wrong answer under both outcomes: it removes real protection
if the knock is real, and masks a blind sensor if it is not.

Heed the guide's warning verbatim: **"DO NOT reduce the gain just to eliminate
real knock. That's a horrible idea."** Gain is not a knob for quieting a symptom;
it is justified only once saturation is demonstrated on a log.

**XDF gap worth noting.** The Funktionsrahmen documents an rpm-indexed
calibration described as "Scaling factor for increasing KNKS_THD in case of
undesired noise not coming from knock events" — a lever aimed squarely at ghost
knock, raising the threshold instead of lowering the gain. It is **not defined in
`Code/xdf/SC8S50.V1.0.xdf`**, so we cannot currently read or edit it.

Treat that table with suspicion rather than enthusiasm.
[mygolfmk7.com/noise-and-knock](https://mygolfmk7.com/noise-and-knock/) documents
raising this exact "Knock Threshold Gain" table as the standard way tuners
**numb the knock sensors** — the noise spike still happens, the ECU simply stops
calling it knock, and the log then shows zero knock retard for an event that did
occur. Several commercial tunes are shown doing it. Raising the threshold to make
our own logs look clean would be the same self-deception, and it is precisely why
knock retard alone is weak evidence of tune safety. If saturation is confirmed,
the legitimate fix is lowering gain so the sensor stays in its working range —
not raising the bar until nothing trips it.

## R16 — superseded unflashed by R17

R16's verified build remains documented in `REV_LOG.md` § R16, but it is no
longer the flash candidate. Its EQT-derived high-RPM base advance stacked with
the new exact Spark-IAT correction before either change was validated in-car.
R17 retains the Spark-IAT family and removes the base-timing overlay.

## R17 — flashed and logged; local timing correction required

R17 writes the complete starting-values matrix from
`knowledge/ecu-tuning-basics.md` § Timing into all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps. It removes both the R16 EQT advance and every
R04 retard cell; all other calibration behavior remains identical to R16.

The 2026-08-26 slot-4 session supplies six full actual-3rd-gear pulls and four
WOT 3→4 shifts. Boost, steady lambda, rail hold, turbo speed, and limiters remain
controlled. The old shift-overboost question is now closed: all four shifts stay
below +10 kPa PUT error, although one reaches −24.5 bar DI rail error and another
reaches 99.2 % HPFP effective volume, so no additional boost is justified.

The timing gate does not pass unchanged. Three settled high-airmass events recur
at 4563, 4830, and 4973 rpm across three pulls and cylinders 1/4, each reaching
−3.0°. A separate −2.6° event occurs during spool at 3380 rpm. The three settled
events meet `knowledge/ecu-tuning-not-the-basics.md`'s criterion for consistent
knock in a defined rpm range rather than random single-cylinder noise. Full
evidence and the battery's lambda-transition downgrade are in
`Logs/BasicsGuide_R17/log_review.md`.

## R18 — flashed and logged; the pocket correction worked

R18 is built and verified with one narrow change in all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps. At both 1200 and 1400 mg/stk, 4500 rpm moves
from −3.000° to −3.750° and 5000 rpm moves from −0.750° to −2.250°. The 5000
rpm values restore R04 exactly; the 4500 rpm value restores R04 at 1400 mg/stk
and extends the same target to 1200 mg/stk for load consistency.

The authoritative candidate is
`MainTune_out/R18_20260826-171645/Patched_259L_R18.bin`, SHA-256
`b3bf96a47e0c6ab704401c09e36939b24eebdd76472ae080f9fd435205cb9bfd`.
Its raw-diff audit against R17 is clean: 36 journaled timing bytes plus four
checksum bytes, zero unexplained. Independent decoding found exactly the nine
intended timing maps changed among all 3814 tables; every other calibration
table is byte-identical to R17.

The R17 Spark-IAT family, boost, wastegate, lambda, pump, limiter, and
knock-control calibrations remain byte-identical. In particular,
`IP_KNKS_GAIN_PRE[0..3]` — Knock pre-window gain for cylinders 1–4,
`IP_IGA_DEC_KNK` — Spark retard at recognised knocking, and
`IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock
is detected are unchanged. Do not stack another calibration change before the
R18 timing pocket is validated.

Validate with normal full actual-3rd-gear WOT pulls to redline on slot 4 and
92-octane fuel. The R17 knock this revision answers was isolated, settled,
single-cylinder −3.0° retard that decayed normally, with factory knock
protection intact — the ECU doing its job, not a damage signature — so no short
containment pass is warranted. Stop and roll back only on a change in
character: simultaneous multi-cylinder retard, retard that ramps rather than
decays, loss of lambda or fuel-pressure control, or protection-limited timing
delivery.

Read the 5000–5700 rpm band on its own terms in the next logs: R18 edits only
the 4500 and 5000 rpm breakpoints, so the pull is fully handed back by 5500 rpm
and the interpolated advance crosses back through the R17 knock-onset value near
5230 rpm. R16 remains superseded and must not be substituted because it
requested still more high-rpm base timing.

**Outcome of the 2026-08-27 session (nine pulls, slot 4, 92 octane).** The
targeted pocket improved from three events in six pulls to **one in nine**, and
the survivor happened at 37.5 °C IAT — hotter than any R17 pocket event. The
correction is validated.

Two caveats carried forward. First, the session ran **13.7 °C hotter at the
intake** than R17 (39.5 °C vs 25.8 °C loaded mean, only 4.5 °C of it ambient —
the rest is intercooler soak from nine pulls in seventeen minutes), so nothing
in it is a like-for-like thermal match. Second, two new −3.0° events appeared at
5706 and 6084 rpm, where R18's base timing is **byte-identical to R17** — an
unchanged region cannot be the cause, so this is the heat, and it is new
information about the calibration's thermal envelope rather than an R18 defect.

**Rough-pavement** false knock is ruled out: these logs carry no GPS
(`Accel. Lat`/`Accel. Long` are accelerometer axes), so the test used undriven
rear-axle speed jitter, event speed spread, and cylinder simultaneity. Every
event sits below the knock-free 99th percentile for road disturbance, and the
four events occur at 68/105/124/133 km/h in four different files.

**Sensor-saturation ghost knock is a separate mechanism and remains untested.**
Per `knowledge/ecu-tuning-not-the-basics.md`, engine noise rises with rpm; once
the noise level (NL) passes ~2 V the threshold `THD = (NL × factor) + adder`
flatlines at 4 V and the sensor reports events that are probably not knock. That
mechanism is *per-cylinder* and *rpm-driven*, so neither the simultaneity test
nor the speed-scatter test discriminates against it. The per-cylinder event
distribution across R17+R18 is in fact consistent with it — stock
`IP_KNKS_GAIN_PRE` last-row means of 33.7 / 36.3 / 38.4 / 40.0 for cylinders
1 / 4 / 2 / 3 rank exactly inversely against event counts of 4 / 3 / 1 / 0, with
cylinder 3 never having knocked — though that is confounded with the ordinary
inline-four end-cylinder thermal pattern and n is tiny. **Decisive evidence
requires per-cylinder NL, THD and RNG, none of which we log today.**

**Next data step before any new revision: re-log R18 in cool air** (target
~25 °C loaded IAT, genuine cooldown between pulls, four to six full
actual-3rd-gear pulls to redline). That single session separates heat from
calibration for both open questions — whether the 4798 rpm residue persists, and
whether the 5700–6100 rpm knock is thermal.

## R19 — FLASHED, LOGGED, AND REVIEWED 2026-08-30. Knock fast loop plus a sized wastegate close

**Status: flashed, logged, and reviewed** — `Logs/BasicsGuide_R19/log_review.md`.
It met all five of its measurements and produced nothing dangerous. Two
caveats travel with that result: the human review gate was **never closed**
before the flash, and code-review **P1 against the intake-axis re-breakpoint
is still open** and untested by that session. `REV_LOG.md` § R19 records
both.

*Original status when written: scripted, built, and verified; awaiting human review and a flash.*
`Tunes/MainTune/TUNE_MainTune_R19.py`, output
`MainTune_out/R19_20260828-133356/Patched_259L_R19.bin`. The authoritative
record is now `REV_LOG.md` § R19 — read that, not this section, for what shipped.

Two things went differently from the plan below, both on Sam's direction:

1. **All three guide knock tables were changed, including
   `IP_IGA_DEC_KNK` — Spark retard at recognised knocking**, which "§ The change
   NOT to make" below held back. That hold was written while sensor saturation
   was still untested. The R18 logs then measured no saturation, which means the
   events are *real* — so halving the initial cut genuinely does reduce the
   response to detonation. `REV_LOG.md` § R19 states that trade plainly and
   lists what bounds it (`IP_IGA_MAX_KNK` and the gain tables both untouched).
   The next log must be read against it.
2. **The wastegate feedforward went in the same revision**, rather than waiting
   its turn. The two act through independent ECU paths and the R18 logs evidence
   each separately, so a single log can still attribute them.

The remainder of this section is the pre-work reasoning, kept because the
recovery-rate argument and the sign-convention warning are still the clearest
statement of why the change was made.

**Original status: candidate, not yet scripted. Both prerequisites are now cleared
(2026-08-28) and they cleared in this revision's favour** — the cool-air re-log
happened, and § RESOLVED — the per-cylinder knock-sensor channels came back "no
saturation", so R19 is this recovery change rather than a gain change. R18 is
validated.

### Why this instead of more timing

`Logs/BasicsGuide_R18/log_review.md` argues against a high-rpm base-timing pull:
the two events above 5500 rpm are in cells R18 left byte-identical to R17, at an
intake temperature R17 never tested, so pulling timing there would be
calibrating against a confound and would re-litigate the R16→R17 high-rpm
argument. Meanwhile the measured cost of the current calibration is not the
depth of the cut — it is **how long the cut is carried**:

| Event          | Time at ≥1° cut | Time to full zero | Gear at recovery |
| -------------- | --------------- | ----------------- | ---------------- |
| 3142 rpm cyl 1 | 3.28 s          | 4.00 s            | 3rd              |
| 4798 rpm cyl 4 | 3.16 s          | 4.32 s            | **4th**          |
| 5706 rpm cyl 1 | 1.44 s          | 3.16 s            | **4th**          |
| 6084 rpm cyl 2 | 0.36 s          | 4.52 s            | **4th**          |

Three of four events are still recovering in the next gear. That is exactly the
case `knowledge/ecu-tuning-not-the-basics.md` § Timing and knock control
describes — a knock event at 4000–4500 rpm carrying its cut halfway into the
next gear. R18's surviving events sit at 4798/5706/6084 rpm, which is where
`IP_DLY_INC_FAST_KNK` is at its slowest.

### The symbol mapping is confirmed, not inferred

The four guide screenshots were matched to SC8S50 symbols on 2026-08-27 by
decoding the stock bin `5G0906259L__0002.bin` and comparing axis breakpoints and
every cell value — all exact matches. The table is recorded in
`knowledge/ecu-tuning-not-the-basics.md` § Knock behavior and calibration.

**Watch the sign convention.** The knock correction is a negative number, and
*increasing* it moves it back toward zero. `IP_IGA_INC_KNK` — Increasing value
of knock integrated correction when knock is detected is therefore the
**recovery amount per step**, which is why TunerPro names the same table "Knock
Correction Decay Amount". Do not read "increase" as "pull more timing".

Easy mis-grabs to avoid: `IP_FAC_IGA_DEC_KNK` — Knock Factor Table Cyl. X is
indexed by rpm × **knock energy**, not airmass; the `IP_IGA_AD_1_*` /
`IP_DLY_INC_AD_1_KNK` family drives the slow adaptive (ad1) loop, not the fast
loop that handles a single WOT event.

### The two changes to make

Both shorten how long a cut is carried. **Neither reduces the initial protective
pull by one degree**, so the ECU's response to real detonation is unchanged.

1. `IP_DLY_INC_FAST_KNK` — number of segments between each increase of fast loop
   (1×8, rpm). Stock `2, 5, 7, 9, 16, 21, 27, 33`. Guide target
   `2, 5, 7, 9, 12, 15, 18, 21` — untouched below 3008 rpm, roughly 30 % faster
   from 3008 rpm up.
2. `IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock
   is detected (4×8, rpm × current correction). Stock `0.375` °CRK everywhere
   (`0.75` at the 736 rpm column). Guide target `0.75` across.

Together these are roughly **2.5–2.7× faster recovery** in R18's knock zone,
which should clear a cut before the following upshift rather than after it.

### The change NOT to make

`IP_IGA_DEC_KNK` — Spark retard at recognised knocking (4×8, rpm × airmass,
stock −1.50 to −3.00 °CRK). The guide suggests halving it to −0.75/−1.50. **Hold
this one.** It reduces the ECU's response to detonation, and we do not yet know
whether these events are real. Rough-road false knock is ruled out, but
sensor-saturation ghost knock is untested (see § R18 above) — and halving the
correction is the wrong answer under *either* outcome: if the events are real it
removes protection, and if they are saturation artifacts it treats the symptom
while the sensor stays blind. That is different in kind from base-timing work,
where the engine is simply asked for less advance up front. Revisit only after
the knock-sensor channels below are logged.

Leave `IP_KNKS_GAIN_PRE[0..3]` — Gain value for each cylinder for the knock
pre-window and `IP_IGA_MAX_KNK` — Maximum value for spark retard alone in both
cases.

### Prerequisite — CLEARED 2026-08-28

The knock-sensor channels were logged and show no saturation: THD peaks
2.68–3.46 V against the 4.004 V clamp, NL peaks 1.53 V against the ~2 V onset.
R18's events are real threshold crossings, so this recovery change is the right
next move and a gain change is not. See § RESOLVED — the per-cylinder
knock-sensor channels above and `Logs/BasicsGuide_R18/log_review.md`.

**The carry-into-next-gear evidence is also stronger than the table above.** That
table was built from 3rd-gear analysis of the hot session alone. Reading 3rd and
4th gear WOT across all three sessions gives ten events, of which **six are still
recovering in 4th gear**, and the cool session's single event never cleared at all
— it held from 4827 rpm to the 6178 rpm cut.

**One consideration to weigh deliberately before scripting:** faster recovery
returns the engine to a boundary it demonstrably still touches, roughly once every
ten band-covering segments in the pocket. Neither table reduces the initial −3.0°
protective pull, so a second event is met at full depth — but the engine will
spend more time near the boundary than it does today.

### Validation for R19

Same gate as R18: normal full actual-3rd-gear WOT pulls to redline, slot 4,
92 octane, in cool air. **Hold WOT into 4th after the upshift** — that is what
makes the carry measurable at all, and it is how the R18 review counted six of ten
events still recovering in the next gear. The specific measurement is the recovery
table above: time from knock onset to full zero, and whether the cut still spans
an upshift.
Success is a shorter carry at unchanged cut depth. Stop signals are unchanged —
a change in *character*, not another settled single-cylinder event.

Conventions: name every table as `` `ID` — Description `` (both, always). Switch-patch
tables are patch-added and have **no A2L IDs** — reference them by title. See
[[sc8s50-switchpatch-xdf]] for the switch-patch structure and per-slot table set.

---

## R20 — BUILT 2026-08-31. Slot 5 becomes the octane-boosted timing map

**Status: scripted, built, and verified; awaiting human review and a flash.**
`Tunes/MainTune/TUNE_MainTune_R20.py`. The authoritative record is
`REV_LOG.md` § R20 — read that, not this section.

Exactly two tables change, both slot 5's: `Spark modifier` — map slot 5 ignition
offset gains 16 of 256 cells (+1.125 to +3.750 °CRK across 3000–6500 rpm in the
1200 and 1400 mg/stk rows), and `PUT setpoint` — map slot 5 boost cap takes slot
4's curve, read off the R19 bin. Slot 4 is byte-identical to R19 and is the
control.

What this queue owes the next session:

- **The A/B protocol is the whole point.** At least three slot-5 and three
  slot-4 pulls, **interleaved**, one dosed tank, same road, cool air,
  per-cylinder knock channels in the list, and a `*.bin.txt` in
  `Logs/MainTune_R20/`. Logged as a normal single-slot session, R20 measures
  nothing.
- **The fuel is part of the calibration.** VP Octanium **Unleaded** only —
  2855 is leaded and would destroy the catalyst and the O2 sensor every log
  review depends on. 10–11 oz per 10 US gallons. See
  [[octane-booster-and-slot-5]].
- **The valet map is gone.** Nothing hard-caps a stranger to 10 psi any more.
  Restoring a valet cap on another slot is an open option if that matters.
- **Half the octane credit is unspent** (~2° of ~4°). A follow-up revision
  spending the rest is gated on R20 logging clean — do not queue it before the
  A/B session exists.
- **Deferred library work R20 touched but did not finish:** the five
  `Lambda modifier` grids (same profile gap, same shape family) are still
  unbound — deliberately, so an unexercised write path does not ship on the back
  of a revision that does not use it; A05's `Spark modifier` uniqueids are still
  unknown, and the shape to pass when they are read is **(16, 18)**, not
  (16, 16); and the Android app has no surface for editing a 16 × 16 per-slot
  grid.

## R21 candidate — the redline over-delivery, and the axis row R19 could not spare

*(Renumbered: R20 went to the slot-5 booster timing map instead. This section is
unchanged otherwise, and its "do not size this from the R18 logs" warning now
applies doubly — R19 has been flashed and logged since it was written.)*

R19 did the intake-axis re-breakpoint (1.25 → 1.15) and it worked: the 5000–6000
rpm shortfall goes from −7.3/−4.3 kPa to a predicted −3.8/−0.8. What it could
**not** fix is the other half of the problem.

**6000–6500 rpm runs over target, not under** — +1.7 kPa today, a predicted
+2.4 after R19, since both R19 deltas are close-only. It is a tracking error
rather than a safety event (+8.9 kPa worst sample against a 237 kPa setpoint,
peak PUT 254.7 kPa, versus a 2700 hPa overboost threshold), which is why it lost
to the four-times-larger underboost. But it is still wrong, and R19 nudged it.

**Why it needs an axis change and not a cell change.** Redline sits at median
intake flow factor 1.002; the 4000–4500 rpm band sits at 0.921. Both fall
between the 0.90 and 1.05 breakpoints, and 4000–4500 is itself 2.8 kPa short. So
every cell that could trim redline re-opens an underboost a band lower.
Separating them needs a breakpoint near **0.96**.

The problem: the axis has ten rows and R19 already spent the only dead one.
Rows 0 through 0.75 are live at spool and part throttle, 0.90 and 1.05 are the
contested pair, 1.15 is now the shortfall band's cell, and 1.50 is the top
guard. There is no spare row left to insert at 0.96.

Options, in rough order of appeal:

- **Re-breakpoint 0.90 → 0.96** and resample. Cheapest, and the same verified
  method R19 used — but check what 0.90 currently serves at part throttle before
  assuming it is free; it is not obviously dead the way 1.25 was.
- **Move 1.50 down** to somewhere useful now that 1.15 covers the top of the
  logged envelope, freeing it as a working row and re-spacing the top three.
  More disruptive, and it gives up the guard row entirely.
- **Accept the redline error.** It is under 1 % of setpoint and has been stable
  across three sessions. Genuinely defensible; list it as known and move on.

**Do not size any of these from the R18 logs.** R19 changed both the geometry
and the feedforward those numbers were measured against. Re-run
`Logs/BasicsGuide_R18/size_r19_wastegate.py` (pointed at the R19 logs and the
R19 bin) first, and confirm the predicted 5000–6000 rpm improvement actually
landed before spending another revision on this domain.

**One prior question the R19 logs will answer for free:** whether the remaining
shortfall is calibration or mechanical. R19's feedforward gain should show up as
a matching *drop* in `WG I Value` — the integral handing work back. If PUT error
and integral both sit unchanged, the commanded position is not reaching the
flap, and no further feedforward work will help.

## After the R12 human review and flash log

R12 is CAL-flash eligible because this ECU already has the R07 patch set. A full
flash is only needed if that patch/code set changes or its installed state cannot
be verified.

- Characterize the patch-added **`PUT setpoint`** grid's unlabelled Y axis
  (raw 0–7 at `0xC836`) before considering any non-tiled treatment.
- Confirm slot selection and the R09-proven `min()` behavior in-car, beginning
  with slot 1 before exercising slot 3. Review `IP_PUT_SP` — Pressure up
  throttle setpoint tracking against each selected slot's explicit cap.
  (The slot-5 10 psi clause that used to close this bullet is **obsolete as of
  R20**, which gave slot 5 slot 4's ~26 psi curve.)
- Review turbo speed, HPFP effective volume and rail hold, lambda, knock,
  `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo charger
  compressor limiting, and P0234 margin. R12 retains slot 3's former 26 psi
  target and adds no fuel-system or compressor headroom.

## Future revision-script hardening

The R11 flash-guidance and checksum-report fixes are currently local to
`TUNE_Basics_Guide_R11.py`. A future script copied from R11 inherits them, but a
script copied from R07–R10 or written independently could reintroduce either
error. Before the next revision script is created:

- Centralize or explicitly enforce the flash-mode rule: a matching-patch tune is
  CAL-flash eligible only when the verified R07 patch set is already installed;
  use FULL when installing or changing the patch/code set, or when its installed
  state cannot be verified.
- Make every generated report derive its checksum wording from the final
  verification result. A failed check must say **STALE — DO NOT FLASH** and must
  never leave a report that claims `CAL_CRC` and `ECM3` are clean.
- Add a focused regression check or shared report helper so future tune scripts
  cannot silently regress either behavior, including when based on an older
  revision.
