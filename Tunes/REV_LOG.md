# Tune Revision Log

Single, continuous revision lineage across the car's tune projects. Each
revision is a separate script file; this log summarizes what changed at each
step, in one unbroken numbering sequence regardless of which project folder
holds the script. Every run writes a fresh timestamped folder under
`<Project>_out/R<rev>_<timestamp>/` holding the saved bin, `report.md`, and
`compare/` PNGs.

- **R00–R15** — `Tunes/TuningBasicsGuide/` — worked the ecu-tuning-basics guide
  end to end, output bins prefixed `CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_`.
- **R16 onward** — `Tunes/MainTune/` — the guide is fully worked; this project
  continues the same calibration and numbering as the car's ongoing daily tune.
  Output bins are named `Patched_259L_R<NN>.bin`.

This file and `README_NEXT_STEPS.md` live at the `Tunes/` root (not inside
either project folder) so one document tracks the full lineage across the
split.

## Flash-method rule for this patched lineage

The one-time installation of the CBRICK, HSL, and 5-slot switch-patch ASW/code
components requires a **full flash**. Once the ECU is confirmed to already have
that same patch set, later tune revisions are **CAL-flash eligible**: their
calibration changes can be sent with a CAL flash without rewriting the unchanged
patch code. Use a full flash again when introducing, removing, or changing a
patch/code component, or when the installed patch state is unknown. Flashing and
the final review remain human-only steps.

| Revision | Script                     | Summary                                                                                                                                                                                                                                                                                                                                                   |
| -------- | -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R00      | `TUNE_Basics_Guide_R00.py` | Initial revision. Base ecu-tuning-basics SOP + lambda axis re-breakpoint.                                                                                                                                                                                                                                                                                 |
| R01      | `TUNE_Basics_Guide_R01.py` | R00 + six limiter/fuelling writes the recipe left at stock.                                                                                                                                                                                                                                                                                               |
| R02      | `TUNE_Basics_Guide_R02.py` | Report-honesty only; bin byte-identical to R01.                                                                                                                                                                                                                                                                                                           |
| R03      | `TUNE_Basics_Guide_R03.py` | R02 + literal 0.80 writes to the three lambda minimum-value floors.                                                                                                                                                                                                                                                                                       |
| R04      | `TUNE_Basics_Guide_R04.py` | R03 + local WOT knock-retard ignition overlay.                                                                                                                                                                                                                                                                                                            |
| R05      | `TUNE_Basics_Guide_R05.py` | R04 + wastegate feedforward overlay + X-axis re-breakpoint to cut overboost.                                                                                                                                                                                                                                                                              |
| R06      | `TUNE_Basics_Guide_R06.py` | R05 + overboost limiter symbol-map fix (now applies 1800→2700 across 6 cells).                                                                                                                                                                                                                                                                            |
| R07      | `TUNE_Basics_Guide_R07.py` | R06 calibration on a PATCHED bin: CBRICK + HSL + 5-slot switch patch, switch-patch TC enabled on all 5 slots. Full flash to install the patch set; later matching-patch tune updates are CAL-flash eligible.                                                                                                                                              |
| R08      | `TUNE_Basics_Guide_R08.py` | R07 + top-end wastegate FF deepening: 6 cells lowered in IP_FAC_BPA_SP[0]/[1], row-weighted onto Int 1.05. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                                                                       |
| R09      | `TUNE_Basics_Guide_R09.py` | R08 + slot-2 boost to a 26 psi shelf: base IP_PUT_SP reshape + slot 1/3/4/5 PUT caps hold R08. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                                                                                   |
| R10      | `TUNE_Basics_Guide_R10.py` | R09 + reshape IP_PQ_CHA_MAX (max compressor pressure ratio): 1.70 @ 1000 rpm, flat 3.1 @ 2000-7000 rpm, to clear the code-128 cap trimming the shelf. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                            |
| R11      | `TUNE_Basics_Guide_R11.py` | R10 + park `IP_PUT_SP` — Pressure up throttle setpoint at 30 psi gauge-equivalent full-load ceiling; all five switch-patch `PUT setpoint` grids become explicit lower caps on a shared 12-point RPM axis. CAL-flash eligible after the R07 patch set is installed.                                                                                        |
| R12      | `TUNE_Basics_Guide_R12.py` | R11 + repurpose slot 5 as a valet map: its patch `PUT setpoint` grid is a flat 1705 hPa absolute cap (9.993 psi gauge) across the shared 12-point RPM axis. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                      |
| R13      | `TUNE_Basics_Guide_R13.py` | No calibration change. Re-declares the complete R00–R12 calibration in the `simoscal.tune` API as one flat script (zero imports from other revisions); output bin byte-identical to R12. Do not flash.                                                                                                                                                    |
| R14      | `TUNE_Basics_Guide_R14.py` | R13 calibration + add a stock map (slot 1, factory `IP_PUT_SP` boost target ~21.6 psi read live from the stock bin) and reorder the drivable slots least→most (1 stock, 2 conservative, 3 intermediate, 4 aggressive); slot 5 valet unchanged. Only the four per-slot `PUT setpoint` grids move. CAL-flash eligible after the R07 patch set is installed. |
| R15      | `TUNE_Basics_Guide_R15.py` | R14 calibration + walk back R08's wastegate deepening in the five `IP_FAC_BPA_SP[0]`/`[1]` cells the R14 logs show under-delivering, every value bounded at its R07 level. Only the two wastegate feedforward maps move. CAL-flash eligible after the R07 patch set is installed.                                                                         |

## R00 — Initial revision

Based on `Code/demos/apply_sop_recipe.py`. Runs the full `apply_basics_sop`
pipeline against the stock bin `5G0906259L__0002.bin`, saving a checksum-clean
`5G0906259L_0002_BasicsGuide_R00.bin`.

**Added over the base demo — lambda axis re-breakpoint.** The guide's Basic
lambda setpoint grid was authored on a re-breakpointed bin, so on the stock bin
the base demo reports `IP_LAMB_BAS_HPDI[1]` / `IP_LAMB_BAS_MPI[1]` as
`axis_mismatch` and writes no fuelling — leaving boost raised without enrichment
(LEAN RISK → DO NOT FLASH). R00:

1. Re-breakpoints the two **shared** lambda axes — the named breakpoint tables
   `ldpm_n_32_1_lasp` (RPM, 0xb2e1) and `ldpm_maf_1_lasp` (load, 0x54700) — to
   the guide's breakpoints (RPM 1504–7008, load 150–1389).
2. Lets the recipe write the guide's 8×12 grid to `HPDI[1]` and `MPI[1]`
   verbatim (they now axis-match).
3. Also rewrites `IP_LAMB_BAS[1]` (the third table sharing those axes, not
   covered by the recipe) to the same guide grid, so the whole lambda setpoint
   family stays coherent on the new breakpoints.

The shared axes are used **only** by this lambda family (verified against the
XDF), so the blast radius is contained. With fuelling in place, the coherence
check clears the lambda LEAN-RISK finding automatically.

**Still open (not addressed in R00):**
- `C_PRS_IM_SP_MAX` (guard_blocked) and `C_PRS_IM_SP_LIM` (guarded_skip) —
  pressure-limiter tables tripping the float-bug / ceiling guards. Pending an XDF
  scaling inspection to resolve the true intended values before deciding whether
  to write or keep the guard.
- The documented `skipped` entries (vague / log-dependent / out-of-scope) are
  intentional and unchanged.

## R01 — six limiter/fuelling writes

Based on R00 (keeps the lambda re-breakpoint unchanged). Adds six writes the base
recipe left at stock, all targets read straight off the guide and verified in-bin.
Verified run: checksums CLEAN (CAL_CRC + ECM3), all six confirmed on the re-opened
saved bin. The three that the recipe reported as skip/guard_blocked are superseded
in the merged report so each table shows once, with its true final state.

| # | `Symbol` — Title                                       | Shape   | Stock     | → Write        | Method   |
|---|--------------------------------------------------------|---------|-----------|----------------|----------|
| 1 | `ID_PV_AV_FL` — Pedal value threshold for LV_FL_RAW    | (7,8)   | 99.90 %   | flat 72 %      | `.set`   |
| 2 | `C_PRS_IM_SP_MAX` — Maximum allowed PRS_IM_SP          | (1,1)   | 239996    | 350000 hPa     | `.set_raw` |
| 3 | `IP_M_AIR_CYL_MAX_STND_VVL[STND]` — Max intake air     | (1,12)  | 515–1275  | flat 2000      | `.set`   |
| 4 | `IP_M_AIR_CYL_MAX_STND_VVL[LFT_1]` — Max intake air    | (1,12)  | 515–1275  | flat 2000      | `.set`   |
| 5 | `IP_TQI_REF_MAX_MON` — Max reference indicated torque  | (1,7)   | 535–568   | flat 1000 Nm   | `.set`   |
| 6 | `C_M_AIR_CYL_SP_MAX` — Maximum allowed M_AIR_CYL_SP    | (1,1)   | 0.001389  | 0.002 (stored) | `.set`   |

**Two things worth remembering:**

- **#2 uses `set_raw`.** 350000 exceeds the XDF *display* max (10000), so `.set`
  trips the FloatBugGuard. That guard is motivated by a TunerPro *editor* artifact
  this library can't hit (we write float bytes directly), so `set_raw` is the
  correct bypass. (When the library reframes that guard to a soft, override-able
  ceiling, this can move to `.set(override=True)`.)
- **#6 stores `0.002`, NOT `2000`.** The guide says "max allowed airmass → 2000
  (if it displays wrong, type `0.002`)" — screenshots 62→63. This float32 uses the
  XDF's identity equation `X`, exactly like TunerPro, so stock stores 0.001389 while
  TunerPro shows 1389 (×1e6, a kg/stroke↔mg/stk unit scale). The guide's target
  therefore maps to a stored **0.002**; writing 2000 would set the ceiling ~1e6×
  too high and would NOT trip any guard. The earlier "can't map 2000 to raw"
  anomaly is resolved: it's the guide's own float-bug fix value.

**Still open (deferred past R01):**
- Two scoped `simoscal` library changes (reframe FloatBugGuard → soft/override-able
  ceiling; add shared-axis-write detection warning). Doing these lets a future
  revision drop the `set_raw` on #2.
- `C_PRS_IM_SP_LIM` — Maximum allowed PRS_IM_SP (overboost limit): leave (guide:
  don't lower; stock 271696 already high).
- `IP_TQI_REF_MON_MAX` / other "out of the way" limiters at 1000/800 — most already
  satisfied; revisit if a log shows one intervening.

**Explicitly out of scope for R01:**
- `IP_FAC_TQ_REQ_DRIV_H/L_VS_DCT` (pedal-feel) — subjective, no literal target.
- Wastegate flow factors — log-dependent, not a static value.
- Ethanol, V30/LB6, DSG farts, pops & bangs — car-config, not part of this SOP.

## R02 — report honesty (no calibration change)

Based on R01. **The saved bin is byte-identical to R01's** — R02 changes nothing
the ECU sees. It exists to make the recipe and report tell the truth after this
session's symbol-identification work. Three changes:

1. **Base recipe reclassified (`simoscal/sop_recipe.py`).** The seven
   `skip_vague` rows became `skip_stock` (a new kind: *known table, deliberately
   left at stock*), each carrying its real symbols and an honest reason. Nothing
   is reported as an unknown anymore, because nothing is unknown:

   | Guide row                              | `Symbol(s)`                                           | Why left at stock (base recipe)                       |
   |----------------------------------------|-------------------------------------------------------|-------------------------------------------------------|
   | Torque request — pedal-feel            | `IP_FAC_TQ_REQ_DRIV_H/L_VS_DCT`                       | Pedal map; subjective, WOT is 1.0 either way          |
   | Fueling-influence → 0.80               | `C_LAMB_BAS_COR_MIN`, `IP_LAMB_COP_MIN`, `IP_LAMB_TUR_OHP_MIN` | Min-lambda floors; stock 0.72-0.75 already richer than 0.80 |
   | Two tables set to 1                    | `IP_LAMB_FL_SP`, `IP_LAMB_FL_SP_TIA`                 | Full-load enrichment maps; stock already all 1.0      |
   | Max ref torque / airmass / intake air / heavy-throttle | (as R01 writes)                      | Conservative baseline; raised by the revision instead |

2. **CR-04 fixed — supersede by guide section, not symbol.** R01 dropped
   superseded recipe rows by matching `symbol`, which missed the heavy-throttle
   (`ID_PV_AV_FL`) and two max-intake-air rows (their skip outcome carries a
   joined / `—` symbol). Those showed as *both* applied and skipped. R02 matches
   by `guide_section`, so each table appears exactly once.

3. **Result:** the report has zero `skip_vague`, no duplicate rows, and every
   remaining skip is a documented deliberate choice (`skip_stock` /
   `skip_out_of_scope` / `skip_log_dependent`).

**Decision recorded (2026-07-07):** the three lambda floors are kept at stock
(already richer than the guide's 0.80); revisit only if a datalog shows lean.

## R03 — literal guide lambda-floor writes

Based on R02. Applies the tuning basics guide's literal `0.80` target to the
three fueling-influence / lambda minimum-value floors that R02 kept at stock:

- `C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint: stock `0.72` → flat `0.80`.
- `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating protection: stock `0.75` → flat `0.80`.
- `IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo charger overheating prevention versus engine speed: stock `0.75` → flat `0.80`.

The R03 report supersedes the prior `skip_stock` row for
`Fueling — fueling-influence tables → 0.80` with applied rows for those three
tables, so the final report reflects the actual saved-bin state.

Verified run: `TUNE_Basics_Guide_out/R03_20260708-132742/`, checksums CLEAN
(`CAL_CRC` + `ECM3`). Re-opened saved-bin values are flat and within storage
resolution of `0.80`: `C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint
decodes to `0.799988`; `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst
overheating protection decodes to `0.799805`; `IP_LAMB_TUR_OHP_MIN`  — Minimum
lambda value for turbo charger overheating prevention versus engine speed decodes
to `0.799805`.

## R04 — local knock-retard ignition overlay

Based on R03. Keeps all R03 behavior unchanged, including the literal guide
`0.80` writes to the three lambda minimum-value floors:

- `C_LAMB_BAS_COR_MIN`  — Minimal value for lambda setpoint.
- `IP_LAMB_COP_MIN`  — Minimum lambda value for catalyst overheating protection.
- `IP_LAMB_TUR_OHP_MIN`  — Minimum lambda value for turbo charger overheating prevention versus engine speed.

Adds a conservative ignition-only overlay to all nine low-port-flap STND timing
tables, targeting repeated -3.0 deg WOT knock retard observed in the first R01
flash logs:

- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][0]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][1]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0][2]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][1][0]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][1][1]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][1][2]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][2][0]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][2][1]`  — Basic Ignition Angle, VVL 0 Port Flap Low.
- `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][2][2]`  — Basic Ignition Angle, VVL 0 Port Flap Low.

The R04 overlay is intentionally local and leaves boost/wastegate tuning alone.
The current logs do not include the intake/exhaust flow-factor channels required
to select wastegate feedforward cells, so wastegate tuning remains deferred.

## R05 — wastegate feedforward boost-tracking overlay

Based on R04. Keeps every R00-R04 change unchanged and adds ONE thing: a
wastegate feedforward overlay to cut the PUT-vs-PUT-SP overboost seen in the R04
log. It changes the two wastegate Z maps and their **shared X-axis breakpoint
table**, with the **same cell deltas** applied to both maps (their small
pre-existing VVL0/VVL1 differences preserved):

- `IP_FAC_BPA_SP[0]`  — Wastegate Position Feedforward, VVL 0 (Map for boost
  pressure actuator setpoint).
- `IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward, VVL 1 (Map for boost
  pressure actuator setpoint).
- `ldp_fac_1_ip_fac_bpa_sp`  — Wastegate feedforward X axis (Exhaust flow factor
  breakpoints), shared by both maps above and **only** those two (grep-verified).

Cells = commanded wastegate position (1 = closed, 0 = open); axes X = exhaust flow
factor, Y = intake flow factor. Per the guide, overboost → lower the cell (open the
wastegate sooner).

**X-axis re-breakpoint (1.25 → 1.40).** The R04 log reaches Exhaust flow factor
~1.33, which clamps against the stock last breakpoint (1.25) into a flat shelf —
every operating point above 1.25 reads one identical value, and the top-end is
where boost is most out of authority (integral saturated). R05 moves the last
breakpoint to 1.40 and slopes that last column further open, so the whole top-end
operating range (Exh ~1.00-1.33) becomes a resolvable, monotonically-more-open
gradient. Because the axis is one shared byte region, the re-breakpoint applies to
both VVL tables at once. **Decision rationale (simulated, not guessed):** running
the ECU's bilinear feedforward lookup over every logged operating point shows the
re-breakpoint + sloped last column opens the wastegate an extra ~0.01-0.02 across
the sustained top-end overboost (biggest at ~5400-6100 rpm, the high-Exh band that
was clamping), while leaving the spool spike and every Exh ≤ 1.00 (low-flow) cell
byte-identical to the cells-only version — so it strictly improves the top end
without disturbing anything else.

**Log analysis** (`Logs/BasicsGuide_R04/simostools-2026_07_08-22_10_57.csv`, two
actual-3rd-gear WOT pulls). PUT overshoots PUT SP along one continuous diagonal
ridge of flow-factor cells, in three severity zones:

| Zone         | RPM band   | Exh FF (X)  | Int FF (Y)  | Overboost (mean / max)     | Controller state                         |
|--------------|------------|-------------|-------------|----------------------------|------------------------------------------|
| Spool spike  | ~3100-3400 | 0.86-0.91   | 0.62-0.74   | +16 / +22 kPa (~+3.2 psi)  | P-D reacts, integral barely moves        |
| Mid-range    | ~3500-5400 | 0.86-1.27   | 0.83-1.06   | +5 / +8 kPa (~+0.7-1.2 psi) | Steady overboost after the spike         |
| Top-end      | ~5800-6700 | 1.07-1.31   | 0.97-1.10   | +11 / +17 kPa              | Integral saturates to ~-28%, WG ~35% — out of authority |

**Edit sizing.** Each cell's pull is sized from its measured mean overboost at
that flow-factor cell (~0.05 wastegate position per 1 psi, 7 kPa ≈ 1 psi),
smoothed along the ridge, with a light upper blend row (Int 0.45) and lower blend
row (Int 1.25) to avoid a wastegate-position cliff. 18 cells per table:

- Spool spike corner (heaviest, but still conservative ~2/3 of the raw 0.05/psi
  rule because it is a fast transient the P-D term partly catches): −0.08 to −0.11.
- Mid-range ridge: −0.03 to −0.06.
- Top-end (firm, since the closed loop is saturated and can't help): −0.06 to −0.07
  at Exh 1.00, deepening to −0.11 at the re-breakpointed Exh 1.40 endpoint so the
  last column slopes open with flow.
- Blend rows: −0.03 to −0.06.

**Verified run** (`TUNE_Basics_Guide_out/R05_20260709-145551/`): checksums CLEAN
(`CAL_CRC` + `ECM3`). Re-opening the saved bin and comparing against a fresh R04
bin confirms — across all 3814 unique tables — that **exactly three** differ:
`IP_FAC_BPA_SP[0]`, `IP_FAC_BPA_SP[1]` (each by exactly the 18 intended cells, with
**identical deltas on both**, max deviation from intended 2.9e-5, within the
1/16384 ≈ 6.1e-5 storage resolution), and the shared `ldp_fac_1_ip_fac_bpa_sp`
X axis (last breakpoint 1.25 → 1.40; the other 15 breakpoints and the Y axis
untouched). The applied rows supersede the base recipe's generic wastegate
`skip_log_dependent` row, so the report shows the wastegate once.

Still **revision 5 — a starting point, not a finished calibration**. The edits are
deliberately conservative; flash → log → review → iterate. Watch the next log for
(a) any swing into *underboost* in the spool-spike corner (back the −0.11/−0.10
cells off if so) and (b) whether the top-end residual clears now that the
feedforward gives the integral headroom and the re-breakpoint has unclamped the
high-Exh region.

**R06 candidate (if a log still overboosts at the very top):** with the axis now
unclamped, deepen the Exh 1.40 last column further, or add an intermediate
breakpoint (~0.83 Int, per the guide) for finer control — the re-breakpoint done
here is what makes that finer shaping possible.

## R06 — overboost limiter symbol-map fix

Based on R05. Runs the **exact R05 pipeline** (lambda re-breakpoint, R01
limiter/fuelling writes, R03 lambda floors, R04 knock-retard timing overlay, and
the R05 wastegate feedforward overlay + X-axis re-breakpoint) with **no new
script-level tuning overlay**. R06's sole change is a **bug fix in the shared SOP
recipe** (`Code/simoscal/sop_recipe.py`) that finally makes the guide's overboost
limit take effect.

**Root cause.** The recipe entry "Limiters — Overboost limit → 2700" was mapped to
the wrong symbol, `C_PRS_IM_SP_LIM`  — Offset to the pressure behind air cleaner
for the limitation of the manifold setpoint (a float32 manifold-setpoint limit,
stock ~271696 hPa). Because stock already exceeded 2700, the guarded-ceiling
writer correctly guarded-skipped it — so **through R05 the overboost limit was
never actually written**. The real table is `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`  —
Overpressure upstream throttle threshold for turbocharger overpressure diagnosis
(the P0234 overboost diagnosis): a 1×6 int16 hPa map, stock ~1800 in all six
cells, XDF hard max 2716.96 hPa.

**The fix (in `sop_recipe.py`, shared by all revisions):**

1. Repointed the overboost entry from `C_PRS_IM_SP_LIM` to
   `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`, target 2700 (intentionally just under the
   2716.96 hard ceiling — do not exceed).
2. Fixed `_guarded_ceiling_write` to **broadcast across every cell** with
   never-lower semantics (it previously read/wrote only cell (0,0), which would
   have raised one overboost cell and left the other five at ~1800 — a silent,
   wrong tune). It now raises only cells below target, leaves any cell at/above
   target untouched, and **refuses to write above a table's declared max** (fail
   loud, never overflow a limiter's element width). The 1×1 limiter constants
   (compressor temp, turbo speed) are the degenerate single-cell case — unchanged.
3. Updated the U3 unit tests and the AE2 acceptance test, which had encoded the
   old mis-mapping, and added a synthetic never-lower test (pre-raise one cell
   above target, confirm it is left alone while the rest are raised) so the AE2
   guarantee survives independent of stock values.

`C_PRS_IM_SP_LIM` (the manifold-setpoint offset limit) is **deliberately NOT
changed** — the guide does not call for it, and whether it should also be raised
is an open question for Sam, not something to guess. It must not be left at 2700.

**Effect on the saved bin.** Relative to R05, the **only** change is the six-cell
overboost table `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR`, raised 1800 → 2700 (raw 32562,
decoded 2699.96 hPa, within the 1/12.06 hPa storage resolution). The prior R05
output (`R05_20260709-145551`) is now stale — the overboost limit was never
applied there.

**Verified run** (`TUNE_Basics_Guide_out/R06_20260709-214405/`): checksums CLEAN
(`CAL_CRC` + `ECM3`), coherence check passed. Re-opening the saved R06 bin and
comparing table-by-table against the R05 bin confirms **exactly one** table
differs — `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` (all six cells raw 32562 = 2700 hPa).
The report shows it under **applied** ("raised 6 of 6 cell(s)"), and
`C_PRS_IM_SP_LIM` no longer appears (no guarded_skip row). Full suite: 299 passed.

Still **revision 6 — a starting point, not a finished calibration**. Now that the
overboost diagnosis threshold is actually raised, watch the next log to confirm no
spurious P0234 and that the wastegate overlay + this limiter work together as
intended.

## R07 — patched bin (CBRICK + HSL + switch patch) with switch-patch TC enabled

**⚠ Full flash required to install the patch set.** R07 introduces the
switch-patched ASW/code components, so its first patch-installation flash must be
full. After that same patch set is installed on the ECU, CAL-only flashes are
appropriate for later calibration updates in this lineage; do not use CAL-only to
introduce, replace, or remove patch/code components.

Based on R06. Runs the **exact R06 base-calibration pipeline unchanged** (lambda
axis re-breakpoint, R01 limiter/fuelling writes, R03 lambda floors, R04
knock-retard timing overlay, R05 wastegate feedforward overlay + X-axis
re-breakpoint, R06 overboost-limiter fix) with **no new base-calibration tuning**.
Relative to the R06 saved bin, R07 gains exactly four things:

1. **`SL CBRICK v1.2 - S50.btp`** — SimosTools anti-brick patch, applied (19 bytes,
   ASW only).
2. **`SL HSL v1.1 - S50.btp`** — High Speed Logging (Mode3E) patch, applied (477
   bytes, ASW only).
3. **`SL PATCH.29.33 - S50.btp`** — the 5-slot on-the-fly map switch patch (v29.33),
   applied (10130 bytes; 3404 in CAL slot storage, the rest ASW).
4. **Switch-patch traction control enabled on all five slots** — the patch-added
   flags `Enable SL TC` — Enable the switch-patch's own slip-based traction control,
   and `Disable OEM TC` — Disable the factory ECU-side TC torque intervention, each
   set `0 → 1` on slots 1–5 (addresses `0x7D83F`–`0x7D843` and `0x7D83A`–`0x7D83E`).

### Pipeline order — investigated, not assumed

Two candidate orderings were tested empirically (2026-07-11): **(A)** patch the
stock bin first, then run the R06 CAL-edit pipeline on the patched base; **(B)** run
the R06 pipeline on stock first, then apply the patches. Findings:

- All three patches are `READY_TO_ACCEPT` on stock and confined on each other
  (`btp.apply` diff ⊆ declared blocks for every patch).
- The R06 CAL edits (~13.6 KB across the base calibration) and the patch-modified
  regions are **fully disjoint**: **0** R06-edited bytes fall inside any patch's
  declared blocks, and **0** bytes are changed by both. So order (B)'s
  byte-exact `.btp` pre-verify still passes (all three patches remain
  `READY_TO_ACCEPT` on the R06 bin), and orders (A) and (B) were confirmed to
  produce a **byte-identical** final bin.
- **Order (A) is used** — it reuses the R06 pipeline verbatim on the patched base,
  matching the canonical `demos/apply_btp_patch.py` "the patched bin is the base for
  tune revisions" flow. Two-XDF flow: the R06 CAL edits use `SC8S50.V1.0.xdf`
  exactly as R06; the TC flags, slot inspection, and `switch_patch_sanity` use
  BinToolz's `S50 Switch Patch.29.33.V2.xdf` (the curated `v1.005/.006` XDFs do not
  load under `simoscal` — reused uniqueids; U1).

### Slot-inheritance finding — no shadowing; R06 cal is global

The open question — *do the five map slots copy base-CAL tables into per-slot
storage, so the R06 edits would fail to propagate?* — was investigated against the
patched bin's `Map Slot 1–5` categories (120 tables, 24 distinct titles). The
switched tables are **feature-enable flags and additive modifiers / independent
per-slot limits**: `PUT setpoint`, `RPM limiter`, `Speed limiter`, `Lambda
modifier`, `Spark modifier`, `Torque Request AT/MT Type 1–3`, `Enable
LC/NLS/RAL/flex-fuel`, `Pops enable`, `Gauge settings`. **None are copies of the
R06-edited base tables** (lambda setpoint grid, timing, wastegate feedforward,
limiters). The R06 base calibration is therefore **global** — it applies under every
slot, and **no per-slot re-writes are needed** for the R06 tune to take effect. This
is corroborated at the byte level: 0 R06-edited bytes lie in any patch/slot block,
and a `unique_tables()` value-compare shows **0 of 3814** CAL tables differ between
R07 and R06.

> **Flagged for Sam (not tuned by R07):** the per-slot `PUT setpoint`, `RPM
> limiter`, and `Speed limiter` tables carry the **patch author's baked defaults**,
> independent of the R06 calibration. Inspect them (BinToolz XDF, `Map Slot 1–5`)
> before relying on a given slot.

### TC decision (flagged for veto) and behaviour defaults

**Decision:** both TC flags set to `1` on **all five slots**, so TC behaviour is
uniform regardless of the stalk-selected slot. **Sam can veto** — e.g. leave one
slot with OEM TC intact as a "safe" map; it is a one-line change to the address
tuples in the script. All ten flags read the expected as-patched `0` before the
write and decode to `1` on the saved bin. The **TC behaviour tables** (category
`TC`, `0xF8`: `Slip target straight`, PID I/D weights and clamps, `Slip ignition
weight` / `Slip WG weight`, `Minimum timing`, `SCC Threshold`/`SCC duration`, …) are
**NOT tuned** — their as-patched defaults are dumped in `report.md` for review;
changing them is a future revision informed by logs.

### Verification (run `20260711-185725`, all mandatory checks pass)

- Each patch `btp.check` = `READY_TO_ACCEPT`; each `apply` `confined = True`;
  per-patch `format_change_report`s saved under `patches/`.
- `switch_patch_sanity` on the final bin: 123 slot/switch tables resolved, 123
  decoded, 0 errors, **plausible = YES**.
- **Full-bin byte diff, R07 vs a freshly-generated R06 bin: 10640 bytes differ, all
  accounted for** — 10626 inside the three patches' declared blocks, 10 TC flag
  bytes (`0x27D83A`–`0x27D843`), 4 `CAL_CRC` bytes (`0x200304`). **0 unexplained.**
  (ECM3's stored value is unchanged — the patches and TC flags touch no
  ECM3-covered area.)
- Re-opening with the BinToolz XDF: all ten TC flags decode to `1`.
- `unique_tables()` value-compare vs R06 over the `SC8S50.V1.0.xdf` CAL region:
  **0 of 3814 tables differ** — the R06 calibration is preserved exactly; the
  patches and flags live outside those tables.
- Checksums on the saved bin: **`CAL_CRC` corrected + CLEAN, `ECM3` CLEAN**;
  **ASW/code-block checksums are not-verifiable in `simoscal`** (SimosTools/VW_Flash
  compute them at full-flash time — stated, never assumed clean).
- No library code was modified (R07 is a pure consumer script), so the `Code` test
  suite was not required to re-run.

### Flash + logging notes

For the initial patch installation, use a **FULL FLASH**, with a known-good stock
recovery image on hand and the battery on a charger. Once that patch set is
already installed, later calibration-only updates may use **CAL flash**. The HSL
patch enables **Mode3E high-speed logging**,
but the SimosTools app must have an **HSL PID list imported** to actually log it
(see `PIDs/` and `knowledge/simostools-app-guide.md`); gear indexing in the
resulting logs depends on which PID list is loaded (`Gear ()` = zero-indexed +1
offset vs `Gear (gear)` = actual — see `CLAUDE.md`; check the CSV header first).

Still **revision 7 — a starting point, not a finished calibration**. The script
never flashes; the deliverable ends at a verified bin + report + PNGs + this
entry, and Sam reviews before flashing.

**Post-review script hardening (2026-07-11, no calibration change).** Two
behavior-only fixes from the R07 code review were applied in place to
`TUNE_Basics_Guide_R07.py`; **the saved bin is byte-identical** (sha256
`6a23f7fe829bed2aeeb5a0e203e103407f0477aa`, confirmed by re-running and `cmp`):
(1) `main()` now raises `SystemExit` with the issues message when the verification
`problems` list is non-empty, so a scripted caller detects failure with a nonzero
exit — `report.md` is still written first so the failure stays reviewable
(negative-tested by monkeypatching `switch_patch_sanity` to force a
not-plausible result: the process raised `SystemExit` and still wrote `report.md`,
then the throwaway run folder was deleted); (2) the intermediate stage-bin save's
blanket `warnings.simplefilter("ignore")` was narrowed to only
`StaleChecksumWarning` (from `simoscal.checksum`), so an unexpected warning can no
longer be masked — narrowing surfaced no previously-swallowed warning. No `Code/`
library or `BinToolz-main/` files were touched.

## R08 — top-end wastegate feedforward deepening

**⚠ CAL flash eligible after R07 patch installation.** R08 retains R07's
switch-patched ASW/code components, so an ECU already running that verified patch
set can receive this calibration update by CAL flash. A full flash is required if
the patch/code components are being installed or changed.

Based on R07. Runs the **exact R07 pipeline unchanged** (three `.btp` patches on
the stock bin, full R06 CAL-edit pipeline on the patched base, switch-patch TC
flags = 1 on all five slots) and adds exactly one change: **six cells lowered in
`IP_FAC_BPA_SP[0]` / `IP_FAC_BPA_SP[1]`  — Wastegate Position Feedforward VVL 0/1**
(XDF title "Map for boost pressure actuator setpoint"), identical deltas to both
tables:

| Cell (row, col) | Int FF × Exh FF | R07 → R08       | Delta  |
|-----------------|-----------------|-----------------|--------|
| (6, 14)         | 0.90 × 1.00     | 0.675 → 0.655   | −0.02  |
| (6, 15)         | 0.90 × 1.40     | 0.630 → 0.610   | −0.02  |
| (7, 14)         | 1.05 × 1.00     | 0.600 → 0.540   | −0.06  |
| (7, 15)         | 1.05 × 1.40     | 0.565 → 0.525   | −0.04  |
| (8, 14)         | 1.25 × 1.00     | 0.545 → 0.485   | −0.06  |
| (8, 15)         | 1.25 × 1.40     | 0.515 → 0.475   | −0.04  |

### Why — clean 3rd-gear R07 logs only

Evidence base: `Logs/BasicsGuide_R07/`, the three clean actual-3rd-gear WOT pulls
(16_02_51 / 16_05_57 / 16_07_36). The two 2nd-gear pulls were excluded: 16_04_31
is spool-transient-dominated, and 16_10_19 is contaminated by switch-patch TC
interventions (up to 11.5 km/h front-vs-rear wheel slip, torque cut ~410 → 220-290
Nm) — which also explains that pull's lean-lambda battery finding.

- Mid-range 3300–5800 rpm tracks at **+0.1 kPa mean** — the R05 overlay did its
  job; its cells are not touched again.
- Top-end 5800–6700 rpm holds a sustained **+8.5 kPa mean / +15.1 kPa max**
  overshoot (worst band 6200–6700: +10.6 kPa) while the WG integral reaches only
  ~−16% — headroom available, so the feedforward base is short and the loop slow.
- **The flow-factor trajectory is a hysteresis loop, not monotonic with rpm.**
  Exh flow factor peaks ~1.33 at 5200–5800 rpm (tracking GOOD there, −2.4 kPa) and
  falls back to ~1.10 by 6200–6700 rpm (WORST overshoot). Good and bad regions
  overlap in Exh-flow space; the discriminator is the **intake** flow factor row —
  the worst band runs Int ~1.04 (93% weight on the Int 1.05 row), the good bands
  Int ~0.94–1.00. Hence the row-weighted shape: deep on Int 1.05 (and its Int 1.25
  mirror blend, log max Int 1.063), light on Int 0.90.

Sizing was verified by simulating the ECU's bilinear lookup at every logged
clean-pull WOT point before/after: **−5.2% WG position mean in the worst
6200–6700 band** (~70% of the guide's 0.05-per-psi rule for +10.6 kPa — a
conservative second pass), −3.3 to −3.9% in the adjacent 3300–5800 bands (absorbed
by I-terms currently idling at −4 to −6% doing feedforward's work), and exactly
0.000 below 3300 rpm (spool untouched). Because the same four cells serve both the
good 4500–5800 region and the overshooting top end, some mid-band opening is
unavoidable; the closed loop has authority to trim it back.

### Verification (run `R08_20260712-170312`)

- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); patches confined; switch-patch sanity
  plausible (123/123 decoded); all 10 TC flags read back 1.
- `cal.unique_tables()` value-compare vs the flashed R07 bin
  (`R07_20260711-223757`, byte-identical to the other R07 run folder): **exactly 2
  tables changed** — the two wastegate maps, 6 cells each, exact intended deltas.
- Raw byte diff vs R07: **28 bytes** = 12 cells × 2 bytes + the 4-byte `CAL_CRC`
  at file offset `0x200304`. Nothing else moved.
- No library code modified (pure consumer script); `Code` test suite not required.

### Flash + logging notes

CAL flash is appropriate when the R07 patch set is already installed; otherwise
use a full flash. Keep the stock recovery image on hand and the battery on a
charger.
For the validation logs: prefer **3rd-gear pulls to redline (≥6500 rpm)** so the
5800–6700 band is well covered, plus one 2nd-gear pull if TC feel is being
evaluated (keep it out of boost-FF conclusions). Same PID list as the R07 logs so
channels stay comparable.

Still **revision 8 — a starting point, not a finished calibration**. The script
never flashes; the deliverable ends at a verified bin + report + PNGs + this
entry, and Sam reviews before flashing.

## R09 — slot-2 boost increase to a 26 psi shelf

**⚠ CAL flash eligible after R07 patch installation.** R09 retains R07's
switch-patched ASW/code components, so an ECU already running that verified patch
set can receive this calibration update by CAL flash. A full flash is required if
the patch/code components are being installed or changed.

Based on R08. Runs the **exact R08 pipeline unchanged** (three `.btp` patches,
full R06 CAL pipeline, R05 + R08 wastegate feedforward overlays, switch-patch TC
flags = 1 on all five slots) and adds **two** changes that raise the boost target
on **map slot 2 only** to a rounded 26 psi (gauge) plateau.

**Change 1 — base `IP_PUT_SP`  — Boost pressure setpoint: full-load reshape.**
The full-load (top) row is reshaped into a 26 psi shelf between 3400 and 4400 rpm,
joining the R08 tail from 5000 rpm up, by **re-breakpointing the table's own RPM
axis** `ldp_n_ip_put_sp` (0x2fd2). That axis is grep-verified referenced by
nothing except `IP_PUT_SP`, so the re-breakpoint has **zero blast radius**. The
stock axis wastes a column on 2000 rpm (redundant — 2000 and 3000 both sit at
24.4 psi), so that column is spent on the new 3400 breakpoint; below 3000 rpm the
ECU clamps to the first column (24.4 psi), byte-identical low-end behaviour to R08.

| rpm (new) | rpm (old) | R08 psi | R09 psi | R08 hPa | R09 hPa |
|-----------|-----------|---------|---------|---------|---------|
| 3000      | 2000      | 24.4    | 24.4    | 2699    | 2699    |
| 3400      | 3000      | 24.4    | 26.0    | 2699    | 2809    |
| 4400      | 4000      | 21.5    | 26.0    | 2500    | 2809    |
| 5000      | 5000      | 19.3    | 24.6    | 2350    | 2712    |
| 5750      | 5750      | 18.6    | 21.8    | 2299    | 2519    |
| 6500      | 6500      | 17.2    | 17.8    | 2199    | 2243    |

(ambient conversion: `hPa_abs = psi_gauge × 68.95 + 1016`.) Only the full-load row
and the shared RPM axis change; the three part-load rows are left as-is.

**Change 2 — slot 1/3/4/5 PUT-setpoint caps held at the R08 curve.**
`IP_PUT_SP` is the shared ceiling for all five slots, so raising it alone would
raise all five. The switch patch adds a per-slot PUT-setpoint **cap** (8×12, hPa)
that binds by `min()` against the base; all five ship at a uniform 4000 hPa
(~43 psi, non-binding), which is why the car currently follows the base. The caps
for slots 1/3/4/5 (`0x7D41A` / `0x7D59A` / `0x7D65A` / `0x7D71A`) are filled with
the R08 full-load curve resampled onto the cap's own 12-point RPM axis, written to
**all eight load rows** so they bind at full load regardless of the cap's
uncharacterised raw 0–7 load-axis, while staying well above the ≤1062 hPa
part-load base. **Slot 2 (`0x7D4DA`) is left untouched** → it sees the full raised
base = the 26 psi shelf.

- Slot 1 = `0x7D41A` → cap = R08 curve
- Slot 2 = `0x7D4DA` → **untouched** (4000 hPa non-binding) → 26 psi
- Slot 3 = `0x7D59A` → cap = R08 curve
- Slot 4 = `0x7D65A` → cap = R08 curve
- Slot 5 = `0x7D71A` → cap = R08 curve

### Cap semantics = min() — evidenced, not yet in-car proven

All five caps sit at 4000 hPa today while the car tracks the ~2699 hPa base — this
is only possible under `min()` (cap) semantics, not override (the car would
target 43 psi). The clean confirmation is still an **in-car check: a slot-1 pull
on R09 must match R08 exactly.** If slot 1 shows the 26 psi shelf, the cap
direction is wrong — flagged in the R09 report as a first-drive gate.

### Verification (run `R09_20260712-213556`)

- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); patches confined; switch-patch sanity
  plausible (123/123 decoded); all 10 TC flags read back 1.
- `cal.unique_tables()` value-compare vs the R08 bin (`R08_20260712-170312`) across
  **both** XDFs: **SC8S50** — exactly 2 tables changed, `IP_PUT_SP` (0x1b6e2) and
  its RPM axis (0x2fd2); **BinToolz S50** — exactly 4 tables changed, the slot
  1/3/4/5 caps. Slot 2 (0x7d4da) and all 10 TC flags **unchanged**. Nothing else
  moved.
- Final-bin readback: RPM axis = `[3000, 3400, 4400, 5000, 5750, 6500]`, full-load
  row psi = `[24.4, 26.0, 26.0, 24.6, 21.8, 17.8]`, each capped slot = the R08
  curve tiled across 8 rows, slot 2 still 4000 hPa — all confirmed by the script's
  own verify step (`base_ok` / `caps_ok` / `slot2_ok`).
- No library code modified (pure consumer script); `Code` test suite not required.

### Flash + logging notes

CAL flash is appropriate when the R07 patch set is already installed; otherwise
use a full flash. Keep the stock recovery image on hand and the battery on a
charger.
Drive **slot 2** for the boost validation. First-drive gates and watch items:

- **Slot-1 pull first** — confirm it matches R08 (cap-semantics proof) before
  leaning on slot 2.
- **Fuel system** — R08 already ran LPFP ~84.7% duty / HPFP ~94.3% effective
  volume at lower boost; the +4 to +5.4 psi midrange on slot 2 may become
  fuel-limited. Watch rail-pressure hold and LPFP duty.
- **Knock at 3000–3500 rpm** — the plateau now sits right where R07 logged
  −2.6/−3.0° retard episodes; timing is at the edge, not conservative.
- Prefer 3rd-gear pulls to redline (≥6500 rpm); same PID list as the R07/R08 logs.

Still **revision 9 — a starting point, not a finished calibration**. The script
never flashes; the deliverable ends at a verified bin + report + PNGs + this
entry, and Sam reviews before flashing.

## R10 — reshape the compressor pressure-quotient cap to unclamp the 26 psi shelf

**⚠ CAL flash eligible after R07 patch installation.** R10 retains R07's
switch-patched ASW/code components, so an ECU already running that verified patch
set can receive this calibration update by CAL flash. A full flash is required if
the patch/code components are being installed or changed.

Based on R09. Runs the **exact R09 pipeline unchanged** (three `.btp` patches on
the stock bin, full R06 CAL pipeline, R05 + R08 wastegate feedforward overlays,
switch-patch TC flags = 1 on all five slots, the R09 base `IP_PUT_SP` 26 psi
shelf reshape, and the R09 slot 1/3/4/5 PUT-setpoint caps) and adds **exactly one
calibration change**:

- `IP_PQ_CHA_MAX`  — Maximum allowed pressure quotient at turbo charger
  compressor (8×8, unitless): reshaped from flat **2.80** to the ecu-tuning-basics
  SOP's default RPM shape — **1.70 at the 1000 RPM breakpoint** (column 0, all 8
  Y rows), **flat 3.1 from ~2000 up to 7000 RPM** (columns 1–7, all 8 Y rows). The
  table's X axis is RPM `[1000, 2000, 3000, 4000, 5000, 6000, 6500, 7000]`, shared
  identically across all 8 rows. (The stock table is flat 9.30; the
  ecu-tuning-basics SOP recipe flattens it to 2.80 as part of the Option-2 boost
  method, so the R09 baseline this revision builds on already reads a uniform
  2.80.) XDF z-data at 0x1ab9a (uint16, scale 1/4096); 3.1 stores raw 12698 =
  3.100098 decoded, 1.70 stores raw 6963 = 1.700195 decoded.

### Why — R09 slot-2 logs (`Logs/BasicsGuide_R09/log_review.md`)

R09 proved the slot-2 26 psi full-load shelf is delivered **~1.0–1.4 psi short**
(actual ~24.6–25.3 psi against the 26.0 target from 3300–5800 rpm), and the
shortfall is **commanded, not plant**:

- `Torque Lim ()` code 128 — "Temporary torque limitation because of operation at
  maximum charge pressure ratio (Max Pressure ratio table)" (guide p. 29) —
  appears **only** on slot-2 files and **only** at 3500–4800 rpm (the shelf zone;
  233 samples across the five slot-2 pulls). That table is `IP_PQ_CHA_MAX`.
- Delivered slot-2 PUT plateaus at exactly **2.80 × the measured pre-compressor
  pressure** — the cap, not the wastegate, sets the achievable boost. The
  persistent positive wastegate integral (+15 %, gate held 67–72 % closed) is the
  closed loop chasing the un-trimmed logged `PUT SP` while the limiter caps the
  achievable setpoint downstream — NOT a feedforward shortfall.

Required PQ to clear the shelf, from 219 settled capped log rows: **2.887–2.958**
on the logged day (~101.6 kPa ambient) and **~3.02** on a low-pressure (99 kPa)
day. So 3.0 is insufficient margin; **3.1 clears the worst realistic sea-level
case with ~0.08 headroom**. This cap is genuine compressor protection near the
IS20 map edge (turbo speed was already 208 of 220 krpm on shelf pulls, and the
6000-ft use case pushes PQ up at fixed boost). Sam has **explicitly acknowledged
the compressor-protection risk and requested 3.1**.

### Verification (run `R10_20260713-000102`)

- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); patches confined; switch-patch sanity
  plausible (123/123 decoded); all 10 TC flags read back 1.
- `cal.unique_tables()` value-compare vs the R09 bin (`R09_20260712-213556`)
  across **both** XDFs: **SC8S50** — exactly **1** table changed of 3814,
  `IP_PQ_CHA_MAX` (0x1ab9a); **BinToolz S50** — **0** of 185 changed (all four
  slot caps, slot 2, and all 10 TC flags unchanged). Nothing else moved.
- Raw byte diff vs R09: **132 bytes** = 64 cells × 2 bytes in the PQ z-data
  (0x21ab9a–0x21ac1a) + the 4-byte `CAL_CRC` at file offset 0x200304. **0
  unexplained.**
- Final-bin readback: `IP_PQ_CHA_MAX` column 0 (1000 rpm, all 8 rows) decodes to
  **1.699951**; columns 1–7 (2000–7000 rpm, all 8 rows) decode to **3.100098**
  (both within the 1/4096 ≈ 2.44e-4 storage resolution); the R09 base reshape,
  slot caps, and slot-2 non-binding default all still read back correct
  (`base_ok` / `caps_ok` / `slot2_ok` / `pq_ok` all pass in the script's own
  verify step).
- **Comparison PNGs scoped to what actually changed.** `compare/` holds only
  `IP_PQ_CHA_MAX__compare_{heatmap,surface}.png` (R09 flat-2.80 baseline vs the
  R10 reshape). Earlier R10 drafts also regenerated the `IP_FAC_BPA_SP[0]`/`[1]`
  wastegate composites and the R09 boost-curve PNG inherited unchanged from
  R08/R09 — those were dropped: a before/after composite for a table this
  revision does not touch misleadingly implies R10 changed it. Their true
  before/after lineage lives in the R08 and R09 reports/`compare/` folders.
- No library code modified (pure consumer script); `Code` test suite not required.

### Flash + logging notes

CAL flash is appropriate when the R07 patch set is already installed; otherwise
use a full flash. Keep the stock recovery image on hand and the battery on a
charger.
Drive **slot 2** for the boost validation; same PID list as the R07/R08/R09 logs,
3rd-gear pulls to redline (≥6500 rpm). Watch items:

- **Turbo speed** — 208 of 220 krpm (~5 % margin) on R09 shelf pulls; clearing
  the cap delivers more boost and will push it higher. **Primary safety watch.**
- **HPFP effective volume** — 97–98 % (at ceiling) on R09 shelf pulls; almost no
  high-pressure-pump headroom for more airmass. Watch rail-pressure hold and
  lambda.
- **`Torque Lim ()` code 128** — should now be **silent** in the shelf zone (the
  direct proof the cap was the constraint); confirm the shelf now delivers ~26 psi.
- Top-end down-ramp / P0234 margin (775 hPa on R09) and knock at 3000–3500 rpm
  (cyl 1 recurring at −3.0°): unchanged by R10, keep watching.

Still **revision 10 — a starting point, not a finished calibration**. The script
never flashes; the deliverable ends at a verified bin + report + PNGs + this
entry, and Sam reviews before flashing.

## R11 — switch-patch PUT maps become the effective WOT target curves

**⚠ CAL flash eligible after R07 patch installation.** R11 retains R07's
switch-patched ASW/code components, so an ECU already running that verified patch
set can receive this calibration update by CAL flash. A full flash is required if
the patch/code components are being installed or changed.

R11 is rebuilt from the untouched stock recovery image through the established
three-patch → R06 → R08 → R10 pipeline. It deliberately does **not** run the
R09 base-shape or cap helpers: R11's architecture is an explicit new minimum
chain, proven by the R09 logs to be
`min(IP_PUT_SP — Pressure up throttle setpoint, active-slot PUT setpoint)`.
The switch-patch `PUT setpoint` grid is a lower cap, not an override.

### Shared base: parked but non-binding

R11 retains the R09 private `ldp_n_ip_put_sp` RPM layout
`[3000, 3400, 4400, 5000, 5750, 6500]` and changes only the full-load row of
`IP_PUT_SP` — Pressure up throttle setpoint. All six cells read back
**3085.03 hPa absolute** (30.0 psi gauge-equivalent using the documented 1016
hPa ambient reference and 68.95 hPa/psi conversion). The three lower load rows
are raw-byte-identical to R10. This is a deliberately non-binding shared
ceiling, not a 30 psi delivery request: every selectable patch slot is verified
below it.

### Patch target axis and cap placement

The patch-added **`PUT SP RPM Axis`** at `0x7D7DC` is now the shared twelve-point
axis `[3000, 3200, 3400, 3800, 4400, 4700, 5000, 5400, 5750, 6000, 6250, 6500]`.
It preserves each R09 `IP_PUT_SP` — Pressure up throttle setpoint anchor while
adding round-number resolution where the target tapers. Its associated
**`PUT SP RPM Axis Header`** at `0x7D7DA` still reads **12**. The patch Y-axis is
still uncharacterized, so each 12-cell curve is tiled unchanged over all eight
rows of its 8 × 12 **`PUT setpoint`** grid.

| Slot | Patch `PUT setpoint` Z-data | R11 role | Stored full-load curve (hPa absolute) |
|---:|---|---|---|
| 1 | `0x7D41A` | Conservative R08-style | Resampled R08 curve |
| 2 | `0x7D4DA` | Intermediate | `[2699, 2699, 2699, 2699, 2699, 2645, 2589, 2503, 2414, 2350, 2286, 2223]` |
| 3 | `0x7D59A` | Former high map | Resampled former R10 slot-2 target curve |
| 4 | `0x7D65A` | Retained safety map | Resampled R08 curve |
| 5 | `0x7D71A` | Retained safety map | Resampled R08 curve |

Slot 2 follows the approved bright-green sketch: it is flat at 2699 hPa
(24.4 psi gauge) through 4400 rpm, then tapers approximately through 22.3 psi
at 5200 rpm to 17.5 psi at 6500 rpm. Its maximum equals slot 1's; every
post-4400 breakpoint is strictly above the resampled slot-1 curve. Slots 1, 4,
and 5 are identical R08-style curves. Slot 3 receives the former R10 slot-2
**target curve** (the 26 psi shelf) rather than a copied 4000 hPa non-binding
default grid.

### Verification (run `R11_20260713-112124`)

- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); all ten inherited switch-patch TC
  flags decode to 1; switch-patch sanity is plausible (123/123 decoded).
- Dual-XDF value comparison vs the known R10 reference is exactly scoped:
  **SC8S50** changes only `IP_PUT_SP` — Pressure up throttle setpoint; the
  switch-patch XDF changes only its **`PUT SP RPM Axis`** and all five
  **`PUT setpoint`** grids. `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient
  at turbo charger compressor is raw-identical to R10.
- Readback proves the base full-load row is flat at ~3085 hPa, all five grids
  are their intended eight-row tiles, every cap is below the shared ceiling,
  no grid retains the dangerous 4000 hPa default, and the header remains 12.
- Raw diff vs R10 is **813 bytes**. Every changed byte belongs to the declared
  `IP_PUT_SP` — Pressure up throttle setpoint full-load cells, shared patch
  **`PUT SP RPM Axis`**, five **`PUT setpoint`** grids, or corrected `CAL_CRC`;
  **0 unexplained**.
- `compare/r11_all_slot_targets.png` shows the parked shared ceiling and all
  five effective target curves. `compare/r11_slots_1_2_3_boost_target.png`
  shows slots 1–3 with the requested fixed 0–30 psi-gauge Y scale. The
  `IP_PUT_SP` comparison composites use R10→R11 (their private axis matches);
  the dedicated curves are the honest artifact for the changed patch axis.

### Flash and logging gate

This remains **revision 11 — a starting point, not a finished calibration**.
Sam must visually review the report and all curve assets before flashing (CAL is
eligible when the R07 patch set is already installed), with the untouched recovery
image and a charger available. Post-flash logs must
review turbo speed, rail-pressure hold/HPFP volume, lambda, knock,
charge-pressure-ratio limiting, boost tracking, and P0234 margin. R11 relocates
the existing 26 psi request to slot 3; it does not authorize a new peak request.

## R12 — slot-5 valet boost cap

**⚠ CAL flash eligible after R07 patch installation.** R12 retains the identical
three-patch ASW/code set and all inherited R11 calibration. It repurposes the
existing fifth selectable switch-patch slot rather than attempting to add a sixth
slot, which would require a separate code-patch design and full-flash review.

### Change: slot 5 is capped below 10 psi gauge

The patch-added slot-5 **`PUT setpoint`** grid at `0x7D71A` is a shared-axis 8 ×
12 grid. Its Y axis remains uncharacterized, so the same curve is intentionally
tiled across all eight rows. On the established **`PUT SP RPM Axis`** at
`0x7D7DC` (`[3000, 3200, 3400, 3800, 4400, 4700, 5000, 5400, 5750, 6000, 6250,
6500]` rpm), R12 writes every slot-5 cell to **1705 hPa absolute**.

Using the documented 1016 hPa ambient reference and 68.95 hPa/psi conversion,
this is **9.993 psi gauge**. The value is floored rather than rounded so it cannot
exceed the requested 10 psi-gauge maximum. With the R09-proven min() semantics,
the active slot's `PUT setpoint` grid is a lower cap beneath the shared
`IP_PUT_SP` — Pressure up throttle setpoint ceiling, so slot 5 becomes the
effective full-load valet boost ceiling. This is a boost-only valet measure:
it does not change pedal, torque, speed, ignition, lambda, or traction-control
calibration.

### Verification (run `R12_20260715-165615`)

- Checksums **CLEAN** (`CAL_CRC` + `ECM3`); all ten inherited switch-patch TC
  flags decode to 1; switch-patch sanity remains plausible.
- The final slot-5 readback is eight identical rows of twelve 1705 hPa cells.
  Every other slot retains its R11 curve, and the shared axis/header and
  `IP_PUT_SP` — Pressure up throttle setpoint remain unchanged.
- Raw R11→R12 audit finds **196 changed bytes**, all confined to the 192 bytes of
  the slot-5 `PUT setpoint` grid plus four corrected `CAL_CRC` bytes; **0
  unexplained** bytes.
- Review `compare/r12_slot5_valet_target.png`,
  `compare/r12_all_slot_boost_targets.png`, and the slot-5 comparison assets in
  the generated output before flashing. The all-slot plot retains both slot 1
  and slot 4 as distinct solid/dashed traces even though their values coincide.

### Flash and logging gate

This remains **revision 12 — a starting point, not a finished valet calibration**.
After human review, CAL flash is eligible only if the verified R07 patch set is
already installed. Log slot 5 independently, beginning with gentle operation;
then review `IP_PUT_SP` — Pressure up throttle setpoint tracking, lambda, rail
pressure, knock, turbo speed, and P0234 margin. Do not assume that reduced boost
alone meets every valet-mode goal (such as speed or throttle restriction).

## R13 — the R12 calibration, re-declared in the tune API

**No calibration change. Nothing to flash.** R13's output bin is **byte-identical**
to R12's, verified by full-file comparison. It exists to prove the new authoring
path, not to change the car.

### Why

R12 was the end of a road. To know what it flashed you had to mentally execute
five files: it imported private helpers from R03, R07, R08, R10, and R11, and
monkey-patched `r11.R11_SLOT_CURVES_HPA` to inject its one change. The tuning
intent — "cap slot 5 at 10 psi" — was about 40 lines buried in 200 lines of
orchestration, verification, and report plumbing that every revision re-typed.
That plumbing is where a gate gets quietly dropped, because a build with a
missing gate produces output that looks exactly like one without.

### Change: authoring path only

R13 declares the complete R00–R12 calibration as one flat script with **zero
imports from other revision scripts**, using the new `simoscal.tune` package:

- Table references go through a **profile** — logical names resolved exactly
  against the loaded XDF, or a loud failure listing every miss before any bin is
  opened. Two profiles compose here, `SC8S50` for the base calibration and
  `SwitchPatch2933` for the patch-added slot tables, sharing one byte buffer, so
  the whole revision saves once instead of the save/reopen/save relay R07–R12
  each hand-rolled.
- Every edit is **journaled** with its `` `ID` — Description ``, units, and
  before/after values. `report.md` is rendered from that journal, so it cannot
  drift from what the code did.
- `build()` owns the verification pipeline: save with checksums corrected,
  verify off the written file, read every journaled table back off it, audit the
  bytes against the R12 reference, draw compare plots, write the report. Any
  failed gate raises *after* the report is written, so failures stay reviewable.

The safety-relevant conversions now live in the library rather than in each
script: `switchpatch.slot_curve(5, psi=10.0)` floors to 1705 hPa (never 1706),
and `limits.airmass_cap_mg(2000)` writes 0.002 kg/stk — the
`C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint trap is no longer
something to remember, because the API has no way to express the mistake.

### Verification (run `R13_20260719-213357`)

- **Byte-identical to R12**: the raw-diff audit reports **0 changed bytes** vs
  `CB_HSL_SP2933_..._R12.bin`, and the script additionally asserts a full-file
  comparison. Checksums **CLEAN**; 137 tables read back off the saved bin and
  matched the journal; switch-patch sanity 123/123 tables resolved and decoded.
- The audit's allowance is derived from the journal, so this is a real check:
  an edit made outside the journal would surface as unexplained bytes rather
  than passing quietly.
- Locked in as `Code/tests/test_acceptance_tune.py`, which rebuilds R13 and
  re-compares against the frozen R12 bin, and asserts R13 imports nothing from
  another revision script.

### Flash and logging gate

**Do not flash R13.** It is the same bytes as the already-reviewed R12; flashing
it would be a no-op at best. The next revision to flash is R14, which will be
the first to use this authoring path for an actual calibration change — and it
inherits the same rule as every revision before it: a starting point, not a
finished calibration, reviewed by a human before it reaches the car.

## R14 — add a stock map and order the slots least→most aggressive

**First calibration change written in the `simoscal.tune` API** (R13 was a
byte-identical re-declaration). R14 changes **only the switch-patch slot
assignments** — the shared base calibration (knock retard, lambda enrichment,
wastegate feedforward, limiters, P0234 threshold) is byte-identical to R13/R12.

### Why

The five slots had grown up ad hoc: slot 3 was the aggressive shelf, slot 1 and
slot 4 were the *same* conservative curve (a wasted duplicate), and there was no
low-boost map for daily / pump-gas / handing-the-keys-over driving. R14 gives
the slots a deliberate least→most ladder and spends the freed duplicate on a
stock map.

| R13 slot             | R14 slot                | Full-load peak |
| -------------------- | ----------------------- | -------------- |
| 1 conservative       | 1 **stock** (new)       | ~21.6 psi      |
| 2 intermediate       | 2 conservative          | ~24.5 psi      |
| 3 aggressive         | 3 intermediate          | ~24.5 psi held |
| 4 conservative (dup) | 4 aggressive            | ~26.0 psi      |
| 5 valet              | 5 valet (unchanged)     | ~10.0 psi      |

### What a "stock" slot can and cannot be

On a switch-patched bin only the 24 per-slot tables differ between slots; the
base calibration is **shared** across all five. So a stock **slot** reverts only
the per-slot boost target — its `PUT setpoint` grid is set to the factory
`IP_PUT_SP` — Pressure up throttle setpoint value (~2502–2506 hPa absolute,
~21.6 psi gauge). It still runs the shared tuned base (timing, fuelling,
wastegate) underneath. That is the most stock a single slot can be short of
reverting the whole tune; it is a genuine low-boost map, not a stock ECU.

The stock curve is read **live** from the stock recovery bin's `IP_PUT_SP`
full-load row and resampled onto the 12-point slot axis (see
`_stock_full_load_curve` in the script), so it is provably the factory target
rather than a transcribed number.

The R09 min() semantics are unchanged: the base `IP_PUT_SP` ceiling stays parked
non-binding at 30 psi and each slot's grid is the effective cap, so every slot
curve sits below that ceiling (the library enforces it per slot).

### Verification (run `R14_20260810-111002`)

- **Checksums CLEAN** (CAL_CRC, ECM3); **final-bin readback PASS** — 137 tables
  re-read off the saved bin matched the journal; **switch-patch sanity PASS** —
  123/123 tables resolved and decoded, 52 differ from stock.
- **Raw-diff audit vs R13: CLEAN** — 724 changed bytes, all attributed,
  unexplained = 0. An independent byte-diff confirms the composition: 720 bytes
  are the four reordered slot grids (slot 1 fully rewritten, slots 2–4 partially),
  4 bytes are the CAL_CRC. **Slot 5's grid is byte-untouched**, and ECM3's stored
  value did not change (the CAL slot region is outside ECM3 coverage).

### Flash and logging gate

CAL-flash eligible on the installed R07 patch set (only calibration bytes moved).
A starting point, not a finished calibration: flash, then **drive each slot** so
the reorder and the new stock map are confirmed in-car, log, review, iterate.
Human review of `report.md` and the `compare/` PNGs before it reaches the car.

### Flashed and logged — 2026-08-10

Validated in-car on **slot 4 only** (`Logs/BasicsGuide_R14/log_review.md`). Slot
4 matched its stored curve at 6–46 hPa RMS against the next-best slot at 2.4–19×
the error, which also proved the reorder took effect: under R13 slot 4 held the
2699 hPa conservative curve, and the logs peak at 2809 hPa. The R09 `min()` cap
semantics held — the parked ~30 psi base ceiling never binds — and `Torque Lim`
code 128 was absent from all 769 WOT samples, confirming the R10 compressor-cap
reshape. **Slots 1, 2, 3 and 5 remain unvalidated in-car.**

Two findings fed R15: slot 4 under-delivers up to 1.5 psi at 4000–4500 rpm with
the wastegate integral carrying +18 %, and a WOT 3→4 upshift into the shelf
overshot to ≥ 28.9 psi with the `PUT` channel railed and the HPFP saturated.

## R15 — walk back R08's wastegate deepening where it now under-delivers

**⚠ CAL flash eligible after R07 patch installation.** R15 retains R07's
switch-patched ASW/code components and moves calibration bytes only.

Based on R14. Runs the **exact R14 declaration unchanged** — the slot ladder,
timing, fuelling, limiters, P0234 threshold and compressor cap are all
byte-identical — and adds **one** change: a third wastegate overlay that moves
five cells of `IP_FAC_BPA_SP[0]` / `[1]` — Wastegate Position Feedforward,
VVL 0 / VVL 1 back toward their R07 values.

### Why — the R14 logs invert R08's premise

`Logs/BasicsGuide_R14/log_review.md` Medium 2: on the clean 3rd-gear pulls slot 4
delivers **1.5 psi short** of its 26 psi target at 4000–4500 rpm, narrowing to
on-target by redline, while `WG I Value` climbs from +0.7 % to +17.8 % with rpm.
The closed loop is spending its integral doing feedforward's job — the signature
of a feedforward base too **open** at high flow for the target it now serves.

The cells carrying that shortfall are **exactly the six R08 lowered**, still at
R08's values. R08 opened them to cut a measured top-end overboost against the
R08-era targets; R10 then unclamped `IP_PQ_CHA_MAX` — Maximum allowed pressure
quotient at turbo charger compressor, and R14 put the aggressive curve on slot 4.
The overboost R08 was correcting no longer exists, so its edit now reads as a
shortfall. R15 is therefore a **walk-back of one prior edit**, not a fresh
reshape — a far better-bounded change.

### Sizing — solved, not guessed

Commanded feedforward position is a bilinear-weighted sum of table cells, so the
position change in an rpm band is **linear** in the cell deltas.
`Logs/BasicsGuide_R14/size_r15_wastegate.py` builds that design matrix from the
logged operating points and solves a bounded least squares against the measured
per-band shortfall, at the guide's ~0.05-position-per-psi rule and R08's own
~70 % conservatism factor. The lookup used is verified exact against logged
`WG Pos Base` (r = +1.000, 0.00 % mean error, n = 560), so the simulation is
trustworthy rather than assumed.

Two bounds carry the safety argument:

- **Never above the R07 value.** R08's deltas are the upper bound, so R15 can at
  most undo R08 in a cell — it can never write a more-closed feedforward than
  this lineage has already run and logged.
- **Never negative**, and the **Int 0.75 rows are excluded outright**: they carry
  the upshift-overboost load, which cannot be sized because the `PUT` channel
  railed during the only logged instance.

The already-correct 6000–6500 rpm band (−1.0 kPa) is weighted up in the solve so
the edit does not push a band that is right into overshoot to buy a little more
elsewhere; that costs ~1.4 kPa across 4500–5500 and halves the predicted redline
overshoot (+3.0 → +1.4 kPa).

| Cell (row, col) | Int FF × Exh FF | R14 → R15     | Delta  | R07 cap | At cap |
|-----------------|-----------------|---------------|--------|---------|--------|
| (6, 14)         | 0.90 × 1.00     | 0.655 → 0.675 | +0.020 | 0.675   | yes    |
| (6, 15)         | 0.90 × 1.40     | 0.610 → 0.630 | +0.020 | 0.630   | yes    |
| (7, 14)         | 1.05 × 1.00     | 0.540 → 0.600 | +0.060 | 0.600   | yes    |
| (7, 15)         | 1.05 × 1.40     | 0.525 → 0.535 | +0.010 | 0.565   | no     |
| (8, 15)         | 1.25 × 1.40     | 0.475 → 0.515 | +0.040 | 0.515   | yes    |

`(8, 14)` — Int 1.25 × Exh 1.00 solved to zero and is **deliberately left at its
R08 value**; R15 declares five cells, not six.

Predicted effect over the logged points:

| RPM band  | R14 actual | R15 predicted | Position change |
|-----------|------------|---------------|-----------------|
| 3500–4000 | −5.5 kPa   | −2.9 kPa      | +0.019          |
| 4000–4500 | −10.4 kPa  | −7.2 kPa      | +0.023          |
| 4500–5000 | −6.5 kPa   | −4.1 kPa      | +0.018          |
| 5000–5500 | −7.9 kPa   | −4.5 kPa      | +0.025          |
| 5500–6000 | −5.5 kPa   | −2.0 kPa      | +0.025          |
| 6000–6500 | −1.0 kPa   | +1.4 kPa      | +0.018          |

That recovers roughly **half** the shortfall, on purpose. Closing it fully would
need cells more closed than R07, which one session's logs do not justify and
which would push more airmass through a fuel system already at 96–98 % HPFP
effective volume. If the next logs still show a gap, R16 can go past R07 with
evidence.

### Verification (run `R15_20260810-212341`)

- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); **final-bin readback PASS** — 137
  tables re-read off the saved bin matched the journal; **switch-patch sanity
  PASS** — 123/123 resolved and decoded, 52 differ from stock.
- **Raw-diff audit vs R14: CLEAN** — 24 changed bytes, all attributed,
  unexplained = 0. Composition confirmed independently: 5 cells × 2 bytes × 2
  maps = 20, plus the 4-byte `CAL_CRC` at `0x200304`. ECM3's stored value did not
  change.
- `unique_tables()` value-compare vs the R14 bin: **exactly 2 of 3814 tables
  differ** — `IP_FAC_BPA_SP[0]` and `[1]`, five cells each, **identical deltas on
  both** (asserted), every cell within 1 LSB (1/16384 ≈ 6.1e-5) of intent and
  **none above its R07 cap**. `(8, 14)` confirmed unmoved.
- Review `compare/IP_FAC_BPA_SP[0]__compare_heatmap.png` and its `[1]` twin —
  those are the only two assets that reflect an R15 change. As with R13/R14,
  `build()` emits a stock-baseline compare plot for every journaled table (211
  PNGs), so the rest show the whole tune vs stock, not what R15 moved; the
  raw-diff audit is what scopes the revision.

### Flash and logging gate

CAL flash is appropriate on the installed R07 patch set. Keep the stock recovery
image on hand and the battery on a charger. **Primary watch item is fuel, not
boost** — this edit adds boost where the high-pressure pump has least headroom,
though it adds least there by construction (+0.46 psi at 4000–4500, the tightest
band). Watch HPFP effective volume, DI rail hold, and lambda first; then boost
tracking at 4000–5500, `WG I Value` (it should stop climbing to +18 %), knock on
cylinder 1, and turbo speed. Prefer 3rd-gear pulls to redline on **slot 4** so
the bands above are directly comparable, and consider driving the unvalidated
slots in a separate session rather than the same one.

Still **revision 15 — a starting point, not a finished calibration**. The script
never flashes; Sam reviews `report.md` and the two wastegate PNGs before it
reaches the car.
