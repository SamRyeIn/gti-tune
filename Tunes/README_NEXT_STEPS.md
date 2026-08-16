# Next steps — Tune lineage

Living scratchpad for **what we want to change in upcoming tune revisions**, before
the work is scripted. One section per planned revision, newest ideas appended as
they come up. When a revision is actually built, its authoritative record moves to
`REV_LOG.md` (per-revision rationale) and the revision script's own header
history — this file is the pre-work idea queue, not the change log.

This file now lives at the `Tunes/` root and spans both project folders: it
tracked `TuningBasicsGuide` (R00–R15) alone until R15, and continues into
`MainTune` (R16 onward) — see `REV_LOG.md` for the project split.

Current lineage tip: **R15 — built and verified, awaiting Sam's review + flash**
(see `REV_LOG.md`). R14 is flashed, logged and reviewed.

**`Tunes/MainTune/` now exists** for R16 onward, with output bins renamed to
`Patched_259L_R<NN>.bin` (dropping the `CB_HSL_SP2933_..._BasicsGuide_` prefix
`TuningBasicsGuide` used). R16 is not written yet — it's blocked on flashing
and logging R15 first, since R16 will need R15's validation logs the same way
R15 needed R14's. When it's time: copy `TUNE_Basics_Guide_R15.py` into
`Tunes/MainTune/TUNE_MainTune_R16.py`, update `OUT_ROOT`, `OUT_BIN_NAME`, and
the R15 reference-bin path, then edit the domain calls per R15's log findings.
Guide: `Code/docs/authoring-a-revision.md`.

**R14 was the first real calibration change in the `simoscal.tune` API** — a stock
map on slot 1 and the drivable slots ordered least→most aggressive (1 stock
~21.6 psi, 2 conservative, 3 intermediate, 4 aggressive), slot 5 valet unchanged.
Only the four per-slot `PUT setpoint` grids moved; the shared base is
byte-identical to R13/R12. Flashed and validated in-car on 2026-08-10 —
`Logs/BasicsGuide_R14/log_review.md` is the evidence base for everything queued
below. To write R16, copy `TUNE_Basics_Guide_R15.py`, edit the domain calls, run
it. Guide: `Code/docs/authoring-a-revision.md`.

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
- **Slot 5 (valet)** — byte-untouched by R14 and validated at R12, so lowest
  priority, but unconfirmed on this bin.

One gentle 3rd-gear pull per slot closes this, and the check is automated:
`python3 Logs/BasicsGuide_R14/verify_slot_identity.py` scores any log against all
five stored curves and names the best match. Keep it to its **own session** —
validating the slot ladder and R15's feedforward edit in one log makes both
harder to read, whichever order they happen in.

## R15 — built, awaiting review + flash

Moved out of this queue: R15 walks back R08's wastegate deepening in the five
`IP_FAC_BPA_SP[0]` / `[1]` — Wastegate Position Feedforward cells the R14 logs
show under-delivering, every value bounded at its R07 value. Deltas were solved
against the measured per-band shortfall, not guessed
(`Logs/BasicsGuide_R14/size_r15_wastegate.py`).

Full rationale, sizing method, predicted per-band effect and verification:
`REV_LOG.md` § R15. Script: `TUNE_Basics_Guide_R15.py`. Verified run:
`TUNE_Basics_Guide_out/R15_20260810-212341/` — 24 changed bytes vs R14, 0
unexplained, exactly 2 tables differ.

**Primary watch item on the validation logs is fuel, not boost.** HPFP effective
volume already runs 96-98 % through the shelf zone and this edit adds boost
there. If the next logs show the shortfall persisting with fuel still in hand,
R16 can go past the R07 values with evidence — that bound is a first-pass
safety choice, not a physical limit.

## Blocked on data — the WOT upshift overboost

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

## Apply the author's Spark IAT correction table (currently stock — power left on the table)

`IP_IGA_BAS_TEMP_N_32` — Spark IAT correction (RPM × IAT → °CRK offset) has never
been touched in any revision (R00–R14) and is still bit-for-bit stock. R11's log
review found delivered timing pulled back over loaded WOT with **zero** knock and
**zero** torque-limiter activity (`Torque Lim` = 0 on every row, all four files —
see `Logs/BasicsGuide_R11/log_review.md`), consistent with the stock IAT table
pulling timing above 30°C/86°F per its calibrated shape, not a protection event.
With the upgraded intercooler this car likely isn't reaching charge temps that
justify stock's pull point.

The tuning basics guide already has an author's alternative transcribed and
double-entry verified (`knowledge/ecu-tuning-basics.md:462-466`,
`media/ecu-tuning-basics/38-iat-correction.png`): no added timing when cold
(winter-blend fuel knocks more), no pull until 40°C/104°F instead of stock's
30°C, plus a re-breakpointed Y axis (35.25 added, 70.5 dropped vs stock).

- Transcribe the author's table values into the next revision script as named
  constants (re-verify the double-entry transcription against the screenshot
  before writing).
- Write the table via the `simoscal.tune` API with an `intent=` describing the
  IC-justified rationale above.
- Re-run the R11-style loaded-WOT timing/knock analysis after the next flash +
  log to confirm the new table isn't exposing knock that the stock pull-back was
  masking — this is a timing *increase*, so treat the first pulls conservatively
  and watch knock retard closely.

**Do not stack this with the R15 wastegate edit.** One change per revision is what
makes the logs readable — a timing increase and a boost increase in the same flash
cannot be attributed if knock appears. The R14 logs also give this item a specific
watch target: cylinder 1 was the **only** cylinder to retard all session (−3.0°
latching at 5545 rpm and decaying to redline, on the hottest pull), and it was
already flagged at −3.0° in the R07 logs. Cylinder 1 is the constraint on any
timing increase, and IAT peaked at only 36 °C on a cool day — so the stock table's
30 °C pull point was being crossed, which supports the premise here.

Conventions: name every table as `` `ID` — Description `` (both, always). Switch-patch
tables are patch-added and have **no A2L IDs** — reference them by title. See
[[sc8s50-switchpatch-xdf]] for the switch-patch structure and per-slot table set.

---

## After the R12 human review and flash log

R12 is CAL-flash eligible because this ECU already has the R07 patch set. A full
flash is only needed if that patch/code set changes or its installed state cannot
be verified.

- Characterize the patch-added **`PUT setpoint`** grid's unlabelled Y axis
  (raw 0–7 at `0xC836`) before considering any non-tiled treatment.
- Confirm slot selection and the R09-proven `min()` behavior in-car, beginning
  with slot 1 before exercising slot 3 and finally the new slot-5 valet cap.
  Review `IP_PUT_SP` — Pressure up throttle setpoint tracking against each
  selected slot's explicit cap; slot 5 must not exceed 10 psi gauge at WOT.
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
