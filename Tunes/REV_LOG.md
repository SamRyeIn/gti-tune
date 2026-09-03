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

| Revision | Script                     | Summary                                                                                                                                                                                                                                                                                                                                                                  |
| -------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| R00      | `TUNE_Basics_Guide_R00.py` | Initial revision. Base ecu-tuning-basics SOP + lambda axis re-breakpoint.                                                                                                                                                                                                                                                                                                |
| R01      | `TUNE_Basics_Guide_R01.py` | R00 + six limiter/fuelling writes the recipe left at stock.                                                                                                                                                                                                                                                                                                              |
| R02      | `TUNE_Basics_Guide_R02.py` | Report-honesty only; bin byte-identical to R01.                                                                                                                                                                                                                                                                                                                          |
| R03      | `TUNE_Basics_Guide_R03.py` | R02 + literal 0.80 writes to the three lambda minimum-value floors.                                                                                                                                                                                                                                                                                                      |
| R04      | `TUNE_Basics_Guide_R04.py` | R03 + local WOT knock-retard ignition overlay.                                                                                                                                                                                                                                                                                                                           |
| R05      | `TUNE_Basics_Guide_R05.py` | R04 + wastegate feedforward overlay + X-axis re-breakpoint to cut overboost.                                                                                                                                                                                                                                                                                             |
| R06      | `TUNE_Basics_Guide_R06.py` | R05 + overboost limiter symbol-map fix (now applies 1800→2700 across 6 cells).                                                                                                                                                                                                                                                                                           |
| R07      | `TUNE_Basics_Guide_R07.py` | R06 calibration on a PATCHED bin: CBRICK + HSL + 5-slot switch patch, switch-patch TC enabled on all 5 slots. Full flash to install the patch set; later matching-patch tune updates are CAL-flash eligible.                                                                                                                                                             |
| R08      | `TUNE_Basics_Guide_R08.py` | R07 + top-end wastegate FF deepening: 6 cells lowered in IP_FAC_BPA_SP[0]/[1], row-weighted onto Int 1.05. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                                                                                      |
| R09      | `TUNE_Basics_Guide_R09.py` | R08 + slot-2 boost to a 26 psi shelf: base IP_PUT_SP reshape + slot 1/3/4/5 PUT caps hold R08. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                                                                                                  |
| R10      | `TUNE_Basics_Guide_R10.py` | R09 + reshape IP_PQ_CHA_MAX (max compressor pressure ratio): 1.70 @ 1000 rpm, flat 3.1 @ 2000-7000 rpm, to clear the code-128 cap trimming the shelf. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                                           |
| R11      | `TUNE_Basics_Guide_R11.py` | R10 + park `IP_PUT_SP` — Pressure up throttle setpoint at 30 psi gauge-equivalent full-load ceiling; all five switch-patch `PUT setpoint` grids become explicit lower caps on a shared 12-point RPM axis. CAL-flash eligible after the R07 patch set is installed.                                                                                                       |
| R12      | `TUNE_Basics_Guide_R12.py` | R11 + repurpose slot 5 as a valet map: its patch `PUT setpoint` grid is a flat 1705 hPa absolute cap (9.993 psi gauge) across the shared 12-point RPM axis. CAL-flash eligible after the R07 patch set is installed.                                                                                                                                                     |
| R13      | `TUNE_Basics_Guide_R13.py` | No calibration change. Re-declares the complete R00–R12 calibration in the `simoscal.tune` API as one flat script (zero imports from other revisions); output bin byte-identical to R12. Do not flash.                                                                                                                                                                   |
| R14      | `TUNE_Basics_Guide_R14.py` | R13 calibration + add a stock map (slot 1, factory `IP_PUT_SP` boost target ~21.6 psi read live from the stock bin) and reorder the drivable slots least→most (1 stock, 2 conservative, 3 intermediate, 4 aggressive); slot 5 valet unchanged. Only the four per-slot `PUT setpoint` grids move. CAL-flash eligible after the R07 patch set is installed.                |
| R15      | `TUNE_Basics_Guide_R15.py` | R14 calibration + walk back R08's wastegate deepening in the five `IP_FAC_BPA_SP[0]`/`[1]` cells the R14 logs show under-delivering, every value bounded at its R07 level. Only the two wastegate feedforward maps move. CAL-flash eligible after the R07 patch set is installed.                                                                                        |
| R16      | `TUNE_MainTune_R16.py`     | First MainTune revision. R15 calibration + exact guide-author Spark IAT axis/grid, a curve-preserving shared-axis migration of the Reference IGA correction, and the EQT Stage 2 log's 5000-rpm-up `Ignition Table Output` curve across 1050/1200/1400 mg/stk in all nine VVL-0 port-flap-low base-timing maps. CAL-flash eligible after the R07 patch set is installed. |
| R17      | `TUNE_MainTune_R17.py`     | R16 calibration with all R04 and R16 base-timing overlays removed: every cell in all nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0 port-flap-low maps matches the tuning basics guide exactly; the R16 Spark-IAT family remains unchanged. CAL-flash eligible after the R07 patch set is installed.                                        |
| R18      | `TUNE_MainTune_R18.py`     | R17 calibration + a logged local timing correction in all nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0 port-flap-low maps: −0.75° at 4500 rpm and −1.50° at 5000 rpm in the 1200/1400 mg/stk rows. All other calibration tables stay byte-identical to R17. CAL-flash eligible after the R07 patch set is installed.                      |
| R19      | `TUNE_MainTune_R19.py`     | R18 calibration + the guide's knock fast-loop tables (`IP_IGA_DEC_KNK` — Spark retard at recognised knocking and its two recovery companions), so one detected event costs ~−1.50° instead of −3.00° and hands timing back faster; plus a sized close of two `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost pressure actuator setpoint cells on a re-breakpointed intake-flow axis. CAL-flash eligible after the R07 patch set is installed. |
| R20      | `TUNE_MainTune_R20.py`     | R19 calibration + slot 5 stops being the valet map: it takes slot 4's boost curve (read off the R19 bin, not retyped) and gains its own `Spark modifier` — map slot 5 ignition offset of +1.125 to +3.750 °CRK across 3000–6500 rpm in the 1200/1400 mg/stk rows, for a VP Octanium Unleaded–dosed tank. Two tables move, both slot 5's. CAL-flash eligible after the R07 patch set is installed. |
| R21      | `TUNE_MainTune_R21.py`     | R20 calibration + a cut to slot 5's `Spark modifier` — map slot 5 ignition offset from the R20 log evidence: the 4000 and 4500 rpm columns come down to +1.500 °CRK (−0.750 / −1.500) because 4500–5000 rpm ran 27.5 knock events per loaded minute against R19 slot 4's 4.2. The +3.750° apex at 5000 rpm and everything above it are held. Exactly one table moves, 4 cells. CAL-flash eligible after the R07 patch set is installed. **Built and verified, never flashed; superseded by R22.** |
| R22      | `TUNE_MainTune_R22.py`     | R20 calibration + the map slot ladder reordered by **fuel requirement** instead of by boost, and a second octane slot. The aggressive ~26 psi curve moves from slot 4 down to slot 3 (read off the R20 bin, not retyped) and becomes the pump-gas everyday map, the in-drive fallback, and the A/B control; the intermediate ~24.4 psi curve moves up to slot 4 and gains R20's **uncut** `Spark modifier` — map slot 4 ignition offset; slot 5 keeps its ~26 psi curve and R21's **cut** offset. Slots 1–3 are pump-92 safe, slots 4–5 need the dosed tank. Three slots — control, reduced boost, reduced timing — testable in one session. Slot 1 also stops being the factory curve above 4400 rpm, taking slot 2's there and falling to ~17.2 psi at redline. Five tables move, all per-slot. CAL-flash eligible after the R07 patch set is installed. |

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

## R16 — exact Spark IAT correction and EQT-matched high-RPM timing

**⚠ CAL flash eligible after R07 patch installation.** R16 retains R07's
CBRICK, HSL, and switch-patch 29.33 ASW/code components byte-identically and
moves calibration bytes only. Flashing and the final review gate remain human
steps.

R16 is the first revision under `Tunes/MainTune/`. It opens the untouched stock
recovery image, reapplies the complete R15 patch and calibration declaration,
then adds the Spark-IAT and base-timing changes recorded in
`Docs/plans/2026-08-25-001-r16-spark-iat-high-rpm-timing-plan.md`.

### R15 prerequisite

`Logs/BasicsGuide_R15/log_review.md` closes the predecessor gate. The R15
wastegate walk-back improved 3500–5000 rpm boost tracking, reduced redline
integral load, and did not regress rail pressure or lambda control. Its two
isolated −3.0° knock events were at 4596 and 4751 rpm, outside R16's timing
cells. No recurring retard appeared at 6000–6500 rpm.

### Exact Spark IAT family

R16 writes the tuning-guide author's complete table to
`IP_IGA_BAS_TEMP_N_32` — Basis for temperature correction of Basic IGA versus
N_32, TIA. The shared `ldpm_tia_iga_cor_sel` — Basis for temperature correction
of IGA versus N_32, TIA intake-air-temperature axis changes from
−30/−20.25/−9.75/0/30/40.5/50.25/60/70.5/80.25 °C to
−30/−20.25/−9.75/0/30/**35.25**/40.5/50.25/60/80.25 °C.

Because that axis is shared, R16 resamples
`IP_IGA_REF_TEMP_N_32` — Basis for temperature correction of Reference IGA
versus N_32, TIA onto the new breakpoints before moving the axis. A dense
continuous-IAT comparison after final-bin encoding gives **0.187158°CRK maximum
deviation**, below the one-step 0.375°CRK limit.

### EQT-matched base timing from 5000 rpm

At Sam's explicit direction, the final R16 supersedes the first unflashed
bounded-timing draft. It matches `Ignition Table Output` from the same-car EQT
Stage 2 91 log `References/20220522_EQTS2_3Gear1.csv`; it does not target the
correction-dependent `Ignition Timing Final` channel. The source segment has 132
third-gear WOT samples from 5024–6336 rpm, with zero knock retard on all four
cylinders and zero COBB spark reduction.

A least-squares piecewise-linear fit on the ECU's 5000/5500/6000/6500 rpm
breakpoints, quantized to the table's 0.375°CRK resolution, gives the following
curve. The same targets are written at 1050, 1200, and 1400 mg/stk in every map
of the nine-member `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition
angle, VVL 0 port-flap-low cam-position family so the EQT match is not diluted
as logged airmass tapers toward redline.

| Engine speed | R15 at 1050 / 1200 / 1400 mg/stk | R16 at all three loads | Largest increase |
|--------------|----------------------------------|------------------------|------------------|
| 5000 rpm     | 1.125 / −2.250 / −2.250°         | 1.875°                 | +4.125°CRK       |
| 5500 rpm     | 0.750 / −0.750 / 0.000°          | 3.750°                 | +4.500°CRK       |
| 6000 rpm     | 1.875 / 1.875 / 1.875°           | 6.000°                 | +4.125°CRK       |
| 6500 rpm     | 3.375 / 3.375 / 3.375°           | 8.250°                 | +4.875°CRK       |

Across all 132 source samples, the encoded curve matches EQT table output with
**0.188898° RMS error**, **0.435° maximum absolute error**, and **+0.059° mean
bias**. This deliberately supersedes R04 cells from 5000 rpm upward, including
the 5500-rpm and 1050-mg/stk cells retained by the first draft. It does not
change timing below 5000 rpm or at/below 900 mg/stk, and stock knock detection
remains untouched. The R14 cylinder-1 event beginning at 5545 rpm and R15's
4596/4751-rpm events are explicit human-review risks, not hidden assumptions.

### Verification (replacement run `R16_20260825-140451`)

- Output: `Tunes/MainTune/MainTune_out/R16_20260825-140451/Patched_259L_R16.bin`.
  SHA-256:
  `061d878dee5d5229e9273b5e9ca7c5ad5e4706475639623f73c253bc0c2021bd`.
- R15 byte-audit reference SHA-256:
  `02f09df6fbe4ef057f47a05a5b52656ca8bdbbfdd587c9e24f0de25d7073207a`.
- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); final-bin readback **PASS** for all
  139 touched tables; switch-patch sanity **PASS** — 123/123 tables resolved
  and decoded, 52 differ from stock.
- Raw-diff audit vs R15 **CLEAN** — 177 changed bytes, all attributed:
  173 journaled calibration bytes plus 4 stored-checksum bytes; unexplained = 0.
- Independent XDF decode found exactly **12 changed calibration tables**: the
  shared IAT axis, the Basic and Reference IGA temperature-correction grids,
  and the nine base-ignition maps. Every other decoded calibration table is
  identical to R15.
- All nine base-ignition maps contain exactly the twelve targets above, are
  mutually identical, and differ from R15 in exactly those twelve cells each.
  No timing cell below 5000 rpm or at/below 900 mg/stk changed.
- Independent decode repeated the EQT fit against the final-bin targets and
  reproduced 0.188898° RMS / 0.435° maximum error over all 132 source samples.
- Focused library tests: **80 passed**. Review all nine
  `compare/IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]__compare_heatmap.png` files.
  The IAT family is unchanged from the superseded draft; the standard axis and
  table artifacts remain in `compare/`, while the continuous-curve review is in
  the earlier unflashed draft folder as `compare/R16_IAT_family_review.png`.

### Human review and logging gate

Review `report.md`, the IAT-family plot, and all nine timing heatmaps before any
CAL flash. For the first validation session use slot 4 and 92-octane fuel.
Capture one controlled actual-3rd-gear pull to redline rather than stacking
back-to-back pulls; the EQT-matched cells begin at 5000 rpm and include the
known 5500-rpm cylinder-1 susceptibility.

After the human-performed flash, run the standard analysis battery and author
`Logs/MainTune_R16/log_review.md`. Compare 5000+ rpm table and delivered timing,
all four knock channels, IAT, lambda, DI rail pressure, HPFP effective volume,
boost tracking, turbo speed, and physics-derived power against R14/R15. Recurring
retard in the changed band, any fresh multi-cylinder event, a deeper or longer
cylinder-1 event, loss of fuel or lambda control, or a protection that prevents
the requested timing from being delivered is a rollback signal. No further
timing increase is authorized until those logs are reviewed.

Still **revision 16 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU.

## R17 — restore the complete tuning-guide base-timing table

**⚠ CAL flash eligible after R07 patch installation.** R17 retains R07's
CBRICK, HSL, and switch-patch 29.33 ASW/code components byte-identically and
moves calibration bytes only. Flashing and the final review gate remain human
steps.

R17 supersedes the unflashed R16 candidate. After comparing R16/R17 against the
starting-values table in `knowledge/ecu-tuning-basics.md` § Timing, Sam directed
R17 to remove both R16's EQT-derived high-RPM advance and every older R04
knock-retard cell. The reason for returning to the guide baseline is attribution:
R16 already added the exact Spark-IAT correction, so retaining a large base-table
advance would stack two timing changes before either was validated in-car.

### Complete guide table

The script embeds the guide's full 16 × 16 encoded matrix and writes it to all
nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps. It then asserts every staged cell against that
matrix before the build can proceed. Relative to R16:

| Removed overlay               | Cells per map | R16 → R17 delta      | Effect                                                                         |
| ----------------------------- | ------------- | -------------------- | ------------------------------------------------------------------------------ |
| R16 EQT high-RPM advance      | 11            | −2.250 to −4.875°CRK | Restores the guide at 5000–6500 rpm / 1050–1400 mg/stk.                        |
| Remaining effective R04 cells | 7             | +0.750 to +2.250°CRK | Restores the guide in the prior knock region and two high-RPM 900 mg/stk cells. |

The resulting curves are the guide curves without scaling, blending, or a
derived smoothing factor. `IP_IGA_BAS_TEMP_N_32` — Basis for temperature
correction of Basic IGA versus N_32, TIA, `IP_IGA_REF_TEMP_N_32` — Basis for
temperature correction of Reference IGA versus N_32, TIA, and their shared
axes remain byte-identical to R16. Stock knock detection remains untouched.

### Verification (authoritative run `R17_20260826-120335`)

- Output: `Tunes/MainTune/MainTune_out/R17_20260826-120335/Patched_259L_R17.bin`.
  SHA-256:
  `5b011833c32484cfa1afe7d7154971187e777dae497f1bc4086d56134b5fc31b`.
- R16 byte-audit reference SHA-256:
  `061d878dee5d5229e9273b5e9ca7c5ad5e4706475639623f73c253bc0c2021bd`.
- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); final-bin readback **PASS** for all
  139 touched tables; switch-patch sanity **PASS** — 123/123 tables resolved
  and decoded, 52 differ from stock.
- Raw-diff audit vs R16 **CLEAN** — 166 changed bytes, all attributed:
  162 journaled base-timing bytes plus 4 stored-checksum bytes; unexplained = 0.
- Independent XDF decode read all 3814 tables with zero errors and found exactly
  nine changed calibration tables: the nine base-ignition maps. Every other
  decoded calibration table is byte-identical to R16.
- Each changed map matches the guide's complete encoded 16 × 16 matrix
  cell-for-cell. Each differs from R16 in exactly 18 cells: 11 lower and 7
  higher, with deltas from −4.875 to +2.250°CRK.
- Focused library tests: **80 passed**. The untouched recovery image retained
  SHA-256 `d61a6e297b3ac1d25f60ec8cb3bb504ff47f2db603a960a56e6a6e34074ad69b`.
- Visual review of the R16→R17 column and heatmap comparisons confirms the
  finished curves reproduce the guide shape. Review all nine comparison sets.

The earlier `R17_20260826-114316` smoothing candidate is superseded, and
`R17_20260826-115840` is an interrupted, incomplete run. Only the authoritative
run above is eligible for human review.

### Human review and logging gate

R17 removes R04 protection from the documented 3500–4500 rpm / high-airmass
knock region. The Spark-IAT correction is temperature-dependent and must not be
treated as unconditional replacement protection, especially at cool IAT where
it commands no retard. Before any CAL flash, review all nine timing plots and
confirm the exact R07 patch set remains installed.

For the first human-performed validation use slot 4 and 92-octane fuel. Capture
one controlled actual-3rd-gear pull without stacking attempts, then inspect the
3500–4750 rpm region before considering a second pull to redline. Review all four
knock channels, delivered-versus-table timing, IAT, lambda, DI rail pressure,
HPFP effective volume, boost tracking, turbo speed, and physics-derived power.
Any recurring knock, multi-cylinder event, loss of fuel/lambda control, or
protection-limited timing delivery is a stop/rollback signal.

### In-car validation (2026-08-26)

R17 was CAL-flashed by the human and logged on slot 4 with 92-octane fuel. The
seven-file session contains six complete actual-3rd-gear pulls and four WOT
3→4 shifts. The full authored review is
`Logs/BasicsGuide_R17/log_review.md`; the deterministic battery ran every check
with none skipped.

Boost, steady lambda, rail hold, turbo speed, torque limiting, and misfires
remain controlled. Four WOT shifts land at 4395–4472 rpm with only +4.7 to
+9.3 kPa peak PUT error, closing the prior shift-overboost question. Fuel
headroom remains the reason not to add boost: the worst shift reaches −24.5 bar
DI rail error and another reaches 99.2 % HPFP effective volume.

The timing gate does not pass unchanged. Three settled events recur at
4563–4973 rpm and 1480–1511 mg/stk across three separate pulls and cylinders 1
and 4, each reaching −3.0° knock retard. A fourth −2.6° event occurs during
spool at 3380 rpm. This is a repeatable rpm/load pocket under the criterion in
`knowledge/ecu-tuning-not-the-basics.md`, not isolated noise without a pattern.
R18 is therefore unblocked only as a local base-timing correction in the
4500–5000 rpm / 1200–1400 mg/stk region across all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps. Knock sensitivity/correction behavior and all
other calibration domains stay unchanged so the next logs isolate that fix.

Still **revision 17 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU.

## R18 — local 4500–5000 rpm timing correction

**⚠ CAL flash eligible after R07 patch installation.** R18 retains R07's
CBRICK, HSL, and switch-patch 29.33 ASW/code components byte-identically and
moves calibration bytes only. Flashing and the final review gate remain human
steps.

R18 responds to the three settled R17 knock events at 4563–4973 rpm and
1480–1511 mg/stk. Each event reached −3.0° across cylinders 1 and 4, so the
repeatable rpm/load pocket meets the advanced guide's criterion for a local
base-timing change. No knock-sensor gain, knock-correction, boost, wastegate,
fueling, limiter, pump, Spark-IAT, or switch-slot change is stacked into this
revision.

### Exact timing correction

Four cells per map change in all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low cam-position maps:

| Engine speed | Airmass rows       | R17 value | R18 value | Delta    |
| ------------ | ------------------ | --------- | --------- | -------- |
| 4500 rpm     | 1200 / 1400 mg/stk | −3.000°   | −3.750°   | −0.750°  |
| 5000 rpm     | 1200 / 1400 mg/stk | −0.750°   | −2.250°   | −1.500°  |

The values are exact multiples of the ECU's 0.375°CRK storage step. The 5000
rpm targets restore R04's prior values at both loads. The 4500 rpm target
restores R04's prior 1400 mg/stk value and extends it to 1200 mg/stk so the two
high-load rows remain consistent rather than introducing a load-direction
step. The 4500-rpm pull is two encoding steps (0.750° = 2 × 0.375°) and the
5000-rpm pull is four; the stronger 5000-rpm pull covers the two events nearest
that breakpoint while remaining within R04's proven bound. That −3.750° target
at 4500 rpm / 1200 mg/stk is also exactly R04's own interpolated value there,
midway between its (4000, 1200) = −5.25° and (5000, 1200) = −2.25° targets, so
all four R18 cells sit on R04's surface rather than merely near it.

`IP_KNKS_GAIN_PRE[0..3]` — Knock pre-window gain for cylinders 1–4,
`IP_IGA_DEC_KNK` — Spark retard at recognised knocking, and
`IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock
is detected remain unchanged. Factory knock protection therefore continues to
report and control any residual event.

### Verification (authoritative run `R18_20260826-171645`)

- Output: `Tunes/MainTune/MainTune_out/R18_20260826-171645/Patched_259L_R18.bin`.
  SHA-256:
  `b3bf96a47e0c6ab704401c09e36939b24eebdd76472ae080f9fd435205cb9bfd`.
- R17 byte-audit reference SHA-256:
  `5b011833c32484cfa1afe7d7154971187e777dae497f1bc4086d56134b5fc31b`.
- Checksums **CLEAN** (`CAL_CRC`, `ECM3`); final-bin readback **PASS** for all
  139 touched tables; switch-patch sanity **PASS** — 123/123 tables resolved
  and decoded, 52 differ from stock.
- Raw-diff audit vs R17 **CLEAN** — 40 changed bytes, all attributed: 36
  journaled timing bytes plus 4 stored-checksum bytes; unexplained = 0.
- Independent XDF decode read all 3814 tables with zero errors and found exactly
  nine changed calibration tables: the nine base-ignition maps. Each differs
  in exactly the four cells above; every other decoded calibration table is
  byte-identical to R17.
- Representative R17→R18 column and heatmap comparisons were visually
  inspected and show only the intended two-rpm/two-load pocket. All nine maps
  were independently asserted identical to one another after the edit.
- Focused ignition-domain tests: **21 passed**. Script compilation passed, and
  the untouched recovery image retained SHA-256
  `d61a6e297b3ac1d25f60ec8cb3bb504ff47f2db603a960a56e6a6e34074ad69b`.

### Human review and logging gate

R18 is a verified candidate, not a validated calibration. After reviewing the
nine timing comparison sets, the human may CAL-flash it only if the exact R07
patch set is confirmed installed. Validate with normal full actual-3rd-gear WOT
pulls to redline on slot 4 and 92-octane fuel — no short containment pass. The
R17 knock this revision answers was three isolated, settled, single-cylinder
−3.0° events that decayed normally, on a bin with factory knock protection
intact; that is the ECU working, not an engine-damage signature, and it does not
justify holding the car short of redline.

What would change that judgement is a change in *character*, not another −3.0°
event: simultaneous multi-cylinder retard, retard that ramps instead of decaying,
loss of lambda or fuel-pressure control, or protection-limited timing delivery.
Any of those is a stop/rollback signal. Note also that R18 pulls timing only at
the 4500 and 5000 rpm breakpoints, so its correction is fully handed back by
5500 rpm; the interpolated advance climbs back through the R17 knock-onset value
at roughly 5230 rpm. Read the 5000–5700 rpm band in the next logs on its own
terms rather than assuming the pocket correction covers it.

Still **revision 18 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU.

---

## R19 — knock fast-loop recovery and a sized wastegate close

**⚠ CAL flash eligible after R07 patch installation.** R19 retains R07's
CBRICK, HSL, and switch-patch 29.33 ASW/code components byte-identically and
moves calibration bytes only. Flashing and the final review gate remain human
steps.

R19 is the first revision in this lineage to touch knock control, and it changes
two domains rather than one. That is a deliberate departure from the
one-domain-at-a-time rule, taken on the human's direction: the two changes act
through independent ECU paths — the knock fast loop and the boost feedforward —
and the R18 logs support both independently, so a next-session log can attribute
a knock-recovery change from a boost-tracking change without ambiguity. Base
timing is not stacked in; all nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle, VVL 0
port-flap-low maps are byte-identical to R18.

### Knock — all three tuning-guide fast-loop tables

The screenshot-to-symbol mapping was confirmed cell-by-cell against the stock
bin on 2026-08-27 and is recorded in
`knowledge/ecu-tuning-not-the-basics.md` § Knock behavior and calibration. It is
independently corroborated by `SCGa05_cal.xdf`, which titles the same three
symbols with the guide's own names.

| Table                                                                                     | Stock                      | R19                        |
| ----------------------------------------------------------------------------------------- | -------------------------- | -------------------------- |
| `IP_IGA_DEC_KNK` — Spark retard at recognised knocking                                    | −1.50 to −3.00 °CRK        | −0.75 to −1.50 °CRK        |
| `IP_DLY_INC_FAST_KNK` — number of segments between each increase of fast loop             | 2, 5, 7, 9, 16, 21, 27, 33 | 2, 5, 7, 9, 12, 15, 18, 21 |
| `IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock is detected | 0.375 °CRK (0.75 at 736)   | 0.750 °CRK everywhere      |

The sign convention is the trap and the script guards against it. The knock
correction is a **negative** angle, so *increasing* it moves back toward zero:
`IP_IGA_INC_KNK` is the recovery step size, which is why TunerPro names the same
table "Knock Correction Decay Amount". Reading "increase" as "pull more timing"
inverts the edit.

The last two tables are the recovery change the R18 review's gate called for, and
together they are roughly a 2.5× faster recovery in R18's knock zone. The
evidence is that R18 does not knock *often* — two events over 21 band-covering
segments in matched air — but carries each cut a long way: six of ten events
across the three logged sessions were still recovering in 4th gear, and the cool
session's single event never cleared before the pull ended.

`IP_IGA_DEC_KNK` is the one change `Tunes/README_NEXT_STEPS.md` § R19 candidate
explicitly held back, and it is included here on the human's direction. That
section's reasoning was written while sensor saturation was still untested, and
its argument has to be read against what the R18 logs then measured: knock
threshold peaks 2.68–3.46 V against the 4.004 V `C_KNKS_THD_MAX` clamp and noise
level never exceeds 1.53 V, so **the events are real threshold crossings, not
ghost knock**. Halving the initial cut therefore does reduce the ECU's response
to genuine detonation — that is the honest statement of the trade, and it is the
thing the next logs must be read against. What bounds it:

- `IP_IGA_MAX_KNK` — Maximum value for spark retard is untouched at −13.9 to
  −19.1 °CRK, so the backstop on *total accumulated* retard is unchanged. A
  cylinder that keeps knocking still integrates down to the same floor; it now
  takes more events to get there.
- `IP_KNKS_GAIN_PRE[0..3]` — Gain value for each cylinder for the knock
  pre-window is untouched, so detection sensitivity is unchanged. This revision
  does not quiet the sensors, which is the failure mode the guide warns about.
- The three settled single-cylinder −3.0° events R18 logged decayed
  monotonically with no co-cylinder involvement. R19 makes each such event cost
  about −1.50 °CRK instead, on an engine whose knock protection is otherwise
  intact.

### Wastegate — an axis re-breakpoint, then two cells closed toward stock

`IP_FAC_BPA_SP[0]` / `[1]` — Map for boost pressure actuator setpoint
under-commands from 5000 rpm up. Across three sessions and both thermal
conditions the closed loop carries 8.6–12.1 % integral to hold a 4.3–7.3 kPa
shortfall. This is a pre-R18 carry-over, not an R18 effect.

**The first attempt at this was cell values alone, and it was barely worth
shipping.** Bounded at the factory value, it recovered about 0.3 psi of a
0.6–1.1 psi shortfall, because the one cell that discriminates the shortfall
band from redline hit its stock cap immediately. The limit was geometry, not
cell values — so R19 fixes the geometry first.

#### The re-breakpoint

`ldp_fac_2_ip_fac_bpa_sp` — the intake-flow-factor y axis of both feedforward
maps — carried breakpoints at 1.25 and 1.50. Nothing in 2537 logged 3rd-gear
WOT samples exceeds **1.201**, so both rows sat entirely above the operating
envelope while the 5000–6000 rpm shortfall (median intake 1.06–1.10) and
redline (median 1.00) were left sharing the cells on rows 0.90 and 1.05.

R19 moves breakpoint 8 from **1.25 to 1.15** and resamples both maps onto it.
That gives the shortfall band a cell of its own:

| Band       | cell (1.15 × 1.40) weight before | after |
| ---------- | -------------------------------- | ----- |
| 5000–5500  | 0.201                            | 0.384 |
| 5500–6000  | 0.201                            | 0.380 |
| 6000–6600  | 0.033                            | 0.066 |

Three things make this a safe edit rather than the riskiest class of change:

- **Blast radius is two tables.** That axis breakpoints `IP_FAC_BPA_SP[0]` and
  `[1]` and nothing else in the XDF — checked, not assumed. Contrast
  `ldpm_n_32_5_igsp`, which breakpoints ten IGA correction tables.
- **The move is a verified no-op at WOT.** `move_intake_flow_breakpoint`
  resamples both maps as it moves the breakpoint, and the script replays the
  ECU's own bilinear lookup over all 2537 logged operating points before and
  after. Worst commanded-position change: **0.0027 points**, below half the
  table's 6.1 × 10⁻⁵ encoding step. Cells are only edited after that assertion
  passes, so any WOT boost behaviour change in the next log is attributable to
  the cell deltas alone.

  **Scope, and an open finding against it.** Those 2537 points are the WOT
  subset — ≥90 % pedal, actual 3rd gear, ≥3000 rpm. Replaying the axis move over
  *every* logged flow-factor row instead finds 34 samples whose modelled
  feedforward moves by more than 0.1 points and 28 by more than 1 point, worst
  −6.079 at 6557 rpm / 53 % pedal / intake flow factor 1.515. So the claim that
  the top rows sit above the operating envelope holds at WOT and not at part
  throttle, and the transient behaviour of this map is changed in a way this
  revision has not reviewed. **`Tunes/MainTune/tune_code_review.md` P1 is open
  against exactly this, and R19 is not flash-reviewable until it is resolved** —
  by preserving the whole reachable envelope, dropping the axis move, or showing
  those states do not consume this map.
- **The trade is stated, not hidden.** The surface is preserved exactly only up
  to intake flow factor 1.21; above that the top rows are extrapolated along the
  same slope. That spends the axis's top-end reserve, which is sound only
  because this engine cannot reach there. **If the turbo is ever changed, this
  region must be recalibrated before it is trusted.**

#### The cells

Deltas re-solved on the new geometry by
`Logs/BasicsGuide_R18/size_r19_wastegate.py` — the same bounded least squares
that sized R15, run in the closing direction. The model is validated before it
is used: replaying the lookup against the logs reproduces `WG Pos Base (%)` to
**0.066 points RMS**.

| Cell (Int × Exh) | R18 (resampled) | delta  | R19   | stock at that intake |
| ---------------- | --------------- | ------ | ----- | -------------------- |
| 0.90 × 1.00      | 0.675           | +0.010 | 0.685 | 0.735                |
| 1.15 × 1.40      | 0.525           | +0.066 | 0.591 | 0.625                |

Guardrails, unchanged from the first attempt except that the stock cap is now
read off the stock *surface* at the cell's new breakpoint rather than off the
stock cell that used to sit at that index:

- **Never more closed than stock**, asserted against the stock bin.
- **4500–5000 rpm is held, not fixed** — it under-delivers 3.9 kPa, but HPFP
  effective volume already peaks at 95.9 % there, so it has no fuel headroom to
  accept more airmass.
- **6000–6500 rpm is held** — it already runs +1.7 kPa *over* target.

Delivered effect, replayed from the saved R19 bin over the logged points:

| Band       | R18   | R19 predicted |
| ---------- | ----- | ------------- |
| 4000–4500  | −2.8  | −2.3          |
| 4500–5000  | −3.9  | −3.2          |
| 5000–5500  | −7.3  | **−3.8**      |
| 5500–6000  | −4.3  | **−0.8**      |
| 6000–6600  | +1.7  | +2.4          |

#### What R19 does NOT fix

**The redline over-delivery.** 6000–6500 rpm runs +1.7 kPa over target and R19
leaves it slightly worse at +2.4. Both deltas are close-only; nothing in this
revision removes boost anywhere.

This is not an oversight, it is the same geometry problem one row lower. Redline
(median intake 1.002) and the 4000–4500 rpm band (median 0.921) both sit between
the 0.90 and 1.05 breakpoints, and 4000–4500 is itself 2.8 kPa *short*. So every
cell that could trim redline also re-opens an underboost a band lower.
Separating them needs a breakpoint near 0.96, and this ten-row axis has no spare
row down there — everything from 0 to 0.75 is live at spool and part throttle.

In context it is a tracking error, not a safety event: +1.7 kPa mean and
+8.9 kPa worst sample against a 237 kPa setpoint, peak absolute PUT 254.7 kPa,
against an `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference
threshold of 2700 hPa. The underboost traded against it is four times larger.
See `README_NEXT_STEPS.md` § R20.

The boost setpoint is not touched anywhere in R19. This moves work from the
integral to the feedforward at a target the closed loop already commands.

### Verification (authoritative run `R19_20260829-072607`)

- Output: `Tunes/MainTune/MainTune_out/R19_20260829-072607/Patched_259L_R19.bin`.
  SHA-256:
  `70d4da677f2f623bb6293ae9cb3f90873a16fd3b7dc199d5ff78b844db2047f5`.
- R18 byte-audit reference SHA-256:
  `b3bf96a47e0c6ab704401c09e36939b24eebdd76472ae080f9fd435205cb9bfd`.
- Checksums **CLEAN** (`CAL_CRC`, `ECM3`), verified independently after save;
  final-bin readback **PASS** for all 143 touched tables.
- Raw-diff audit vs R18 **CLEAN** — 152 changed bytes, all attributed;
  unexplained = 0. Attributed by hand as well: 32 `IP_IGA_DEC_KNK` cells, 4
  `IP_DLY_INC_FAST_KNK` cells, 30 `IP_IGA_INC_KNK` cells, 40 bytes in each
  `IP_FAC_BPA_SP` map (the resampled rows plus the two cell deltas), 2 bytes of
  `ldp_fac_2_ip_fac_bpa_sp`, and the 4 stored `CAL_CRC` bytes at `0x200304`.
- Independent XDF decode read all 3814 tables with zero errors and found exactly
  **six** changed calibration tables: the three knock tables, the two wastegate
  maps, and their shared intake-flow-factor axis. Every other decoded table —
  including all nine base ignition grids and `IP_IGA_MAX_KNK` — is
  byte-identical to R18.
- The intake-axis re-breakpoint was asserted a no-op over all 2537 logged
  operating points *before* any cell was edited: worst commanded-position change
  0.0027 points, against a tolerance of half an encoding step.
- Script guards that must hold for the build to finish: all three knock tables
  read exactly stock going in; every declared knock angle is a whole multiple of
  the 0.375 °CRK encoding step; the retard grid is strictly shallower than stock
  in every cell, the delay never longer, the recovery step never smaller; the
  intake breakpoint being moved still reads its inherited 1.25 going in; the
  re-breakpoint is a no-op over the logged points; and each wastegate cell's
  declared stock cap is checked against the stock surface at the cell's new
  intake breakpoint.
- The untouched recovery image retained SHA-256
  `d61a6e297b3ac1d25f60ec8cb3bb504ff47f2db603a960a56e6a6e34074ad69b`.
- The earlier `R19_20260828-172224` run is superseded. Its bin is byte-identical
  — same SHA-256 — but its `report.md` narrates the abandoned three-cell,
  no-re-breakpoint version of the wastegate edit, which is not what the script
  applies. Only the run above is eligible for human review.

### Human review and logging gate

> **Recorded 2026-08-30: this gate was never closed, and R19 was flashed and
> logged anyway.** The 2026-08-30 cool-air session is reviewed in
> `Logs/BasicsGuide_R19/log_review.md`, which finds R19 met all five measurements
> below and produced nothing dangerous — but that is a post-hoc result, not
> retroactive approval, and P1 remains open and untested by that session.
> The original blocking text follows, unchanged.

> **This gate does not pass yet.** `Tunes/MainTune/tune_code_review.md` P1 is
> open against the intake-axis re-breakpoint: it is proven a no-op only over the
> 3rd-gear WOT subset, and replaying it over every logged flow-factor row shows
> part-throttle and lift states whose modelled feedforward moves by up to 6
> actuator-position points. Resolve that before flashing R19. Everything below
> is the gate as it will stand once it is resolved.

Review the R18→R19 comparison plots for the three knock tables and both
`IP_FAC_BPA_SP` maps. **The nine base ignition grids must show no change at
all** — that is the check that R19 did not quietly stack a timing change onto a
knock change.

Validate with normal full actual-3rd-gear WOT pulls to redline on slot 4 and
92-octane fuel, **in cool air**, and **hold WOT into 4th after the upshift** —
the carry into the next gear is the specific thing this revision is trying to
shorten, and it is only measurable if 4th is logged. Keep the per-cylinder
knock-sensor channels in the logging list.

The measurements that decide whether R19 worked:

1. **Recovery carry** — time from knock onset to full zero, and whether the cut
   still spans an upshift. Success is a shorter carry.
2. **Cut depth** — a single event should now cost about −1.50 °CRK instead of
   −3.00. That is the intended change, not a fault.
3. **Event rate and character** — this is the one to watch hardest, because a
   shallower cut plus faster recovery returns the engine to the knock boundary
   sooner and more often. A rise in event *rate* at unchanged character is the
   expected cost and is readable; a change in *character* is not.
4. **Boost tracking at 5000–6000 rpm** — PUT error should improve by about
   3.5 kPa at 5000–5500 and 3.5 kPa at 5500–6000, with `WG I Value` falling by
   roughly the amount the feedforward gained (about 2.5 points). **If PUT error
   and integral both stay put, the command is not reaching the flap** and the
   remaining shortfall is mechanical, not calibration — that is the one outcome
   this revision is designed to distinguish.
5. **Redline over-delivery** — expected to go from +1.7 to about +2.4 kPa. That
   is predicted, not a regression. Anything materially beyond it means the
   re-breakpoint behaved differently in the car than in the replay.

Stop/rollback signals are unchanged and are all about character, not depth:
simultaneous multi-cylinder retard, retard that ramps instead of decaying, total
accumulated retard approaching the untouched `IP_IGA_MAX_KNK` floor, loss of
lambda or fuel-pressure control, or protection-limited timing delivery. Any of
those is a stop signal. Given that this revision reduces the initial protective
cut on events already shown to be real, treat the first R19 session as a
higher-attention log than R18's, not a routine one.

Still **revision 19 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU.

---

## R20 — slot 5 becomes the octane-boosted timing map

**⚠ CAL flash eligible after R07 patch installation.** R20 retains R07's CBRICK,
HSL, and switch-patch 29.33 ASW/code components byte-identically and moves
calibration bytes only. Flashing and the final review gate remain human steps.

R20 changes **exactly two tables**, and both belong to **map slot 5 alone**. It
is the first revision in this lineage whose validation is a *within-session A/B*
rather than a comparison against the previous session, because for the first time
two selectable maps differ from each other in one controlled variable.

Everything else — every base ignition cell, R19's three knock fast-loop tables,
the wastegate feedforward and its re-breakpointed intake axis, the exact Spark
IAT tables, fueling, limiters, slots 1–4, and the patch set — is inherited from
R19 byte for byte.

### What changed, and why here

**`Spark modifier` — map slot 5 ignition offset** (patch-added, no A2L symbol;
uniqueid `0x7d31a`) gains 16 of its 256 cells.

The problem this solves is structural. The nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle maps are
**shared by all five slots**. There is exactly one base-timing calibration in
the bin, so "more timing on a boosted tank, stock timing otherwise" cannot be
expressed by editing them — that would move slot 4 too. The switch patch's
per-slot `Spark modifier` grid is the only per-slot timing surface the patch
provides, and R20 is the first revision to write one.

That the grid is an **additive** offset rather than a replacement or a
multiplier was established before anything was written, and the evidence is
recorded in `knowledge/sc8s50-switchpatch-xdf.md` § Per-slot `Spark modifier`
semantics:

1. The five grids reuse the base ignition maps' own axis tables **byte for
   byte** — rpm at `0x3ce5a`, airmass at `0x3cdbc`.
2. They reuse the same codec and declared range: `0.375·raw − 35.625`,
   −35.625 … +60.0 °CRK.
3. All five ship neutral at a **decoded 0.00°, not a raw zero** (raw 95). A
   replacement table shipping at 0.00 would mean slot 4 commands no timing at
   all; a multiplier would need to ship at 1.0.

What is *not* statically provable is the control-state scope — whether the
offset applies in every state or only some. A neutral table is indistinguishable
from one that is never read, and settling it would take a TriCore disassembly of
the patch's 7,236-byte code block. It does not need settling here, because the
map fails benign: only the 1200 and 1400 mg/stk rows above 3000 rpm are
non-zero, so an unexpectedly narrow scope costs advance rather than adding it
somewhere unintended.

**`PUT setpoint` — map slot 5 boost cap** (uniqueid `0x7d71a`) takes slot 4's
curve, retiring the R12 valet map.

Slot 5 held a flat 10 psi gauge cap from R12 onward and nothing in the R14–R19
log record ever selected it. Giving it slot 4's boost is what makes R20 a
single-variable experiment: the two slots now differ in ignition timing and
nothing else. The curve is **read off the R19 bin**, never retyped — a
transcription slip would silently turn the A/B into a comparison of two boost
targets. `switchpatch.slot_curve` tiles one rpm row across all eight
uncharacterized Y rows, so the script asserts slot 4's grid is row-uniform
before using row 0, and cross-checks the read curve against the value this
script independently declares for slot 4.

### The map

The offsets, in °CRK, written identically into the 1200 and 1400 mg/stk rows:

| rpm         |   3000 |   3500 |   4000 |   4500 |   5000 |   5500 |   6000 |       6500 |
| ----------- | -----: | -----: | -----: | -----: | -----: | -----: | -----: | ---------: |
| slot 4 base | −7.500 | −6.750 | −4.500 | −3.750 | −2.250 | +0.750 | +1.875 |     +3.375 |
| modifier    | +1.125 | +1.500 | +2.250 | +3.000 | +3.750 | +2.250 | +1.500 |     +1.125 |
| **slot 5**  | −6.375 | −5.250 | −2.250 | −0.750 | +1.500 | +3.000 | +3.375 | **+4.500** |

Every other cell of the 16 × 16 grid stays neutral at 0.00°, so outside WOT
above 3000 rpm slot 5 *is* slot 4.

**Why this shape.** `Logs/BasicsGuide_R19/log_review.md` established that
delivered WOT timing on R19 is **scheduling-limited, not knock-limited** at the
top end — the headroom is real. What 92 AKI could not do is claim it: R17 tried
and R18 had to retard 4500–5000 rpm back out. Raising fuel octane moves the
knock boundary itself, which is why this is a fuel change with a calibration
attached rather than the reverse. The peak sits at 5000 rpm, exactly where R18
had to give timing back.

**Why these exact values.** The shape was authored as
1.00 / 1.50 / 2.00 / 2.75 / 3.50 / 2.00 / 1.50 / 1.00. Four of those are not
storable: the grid holds 0.375 °CRK per step. `slot_spark_map` **refuses** a
non-storable offset rather than rounding it, naming both neighbours — a silent
round of +1.00 to +1.125 would be a round *up*, on advance, which is not a
rounding error anyone should discover from a log. The round-up neighbours were
chosen deliberately on Sam's direction: the ~4-octane-number dose is worth
roughly 4° of margin and this map spends about half of it, so rounding up
preserves that reserve rather than eroding it.

**The delivered-timing ceiling.** The quantity worth capping is base + modifier,
not the offset: +3.00° onto a cell already at +3.375° is a very different engine
from +3.00° onto one at −7.50°. `slot_spark_map` requires a
`max_delivered_degrees`, has no default for it, reads the **live** base map to
check it, and refuses outright if that map cannot be read rather than passing.
R20 declares **+5.00 °CRK** and delivers a peak of +4.500. The ceiling is
deliberately tight: transposing the 5000 rpm offset into the 6500 column would
deliver +7.125° and be refused.

**The top-row question.** WOT reaches ~1600 mg/stk while the grid's top
breakpoint is 1400, so what the ECU does above the last row — clamp or
extrapolate — would decide the effective advance there. R20 does not resolve it;
it makes it moot by writing the 1200 and 1400 rows identically, so the surface is
flat going into the top breakpoint and both behaviours give the same answer.
`slot_spark_map` enforces this rather than trusting the author to remember.

### The fuel — a constraint, not a note

Slot 5 is calibrated for pump 92 AKI dosed with **VP Octanium Unleaded** at
**10–11 oz per 10 US gallons**. The full record, including the operating rules
and the stop signals, is `knowledge/octane-booster-and-slot-5.md`, linked from
`index.md`. Three points belong here too, because they change what is safe:

- **Octanium 2855 must never go in this car.** It contains TEL, and VP states it
  is for engines without oxygen sensors or catalytic converters. This car has
  both, and every log review in this repo depends on the wideband O2 sensor.
- **10–11 oz / 10 gal is the emissions-device-safe ceiling**, worth about 4.2
  octane numbers. VP's headline "up to 7 numbers" needs 23–32 oz / 10 gal, the
  non-ECD dose. Do not chase it on this car.
- **Selecting slot 5 on plain 92 will knock.** Accepted knowingly (origin doc
  Key Decision 6): the control is discipline, not calibration. Knock control
  still catches it at −1.50 °CRK per event under R19's halved cut, but being
  caught by knock control is not the same as being safe to run.

**The valet map is gone** (Key Decision 8). Slots 1 (stock ~21.6 psi), 2
(conservative) and 3 (intermediate) remain as tamer maps, but nothing hard-caps a
stranger to 10 psi any more. Restoring a valet cap on another slot is listed in
`README_NEXT_STEPS.md` if that turns out to matter.

### Verification (authoritative run `R20_20260831-062648`)

- Output: `Tunes/MainTune/MainTune_out/R20_20260831-062648/Patched_259L_R20.bin`.
  SHA-256:
  `8c0b4d18ea7491f7c0ea595805abfa2aae3d23b55697e640622a4d26bfe83990`.
- R19 byte-audit reference SHA-256:
  `70d4da677f2f623bb6293ae9cb3f90873a16fd3b7dc199d5ff78b844db2047f5`
  (`R19_20260829-072607` — the flashed bin).
- Checksums **CLEAN** (`CAL_CRC`, `ECM3`), verified independently after save;
  final-bin readback **PASS** for all 144 touched tables.
- Raw-diff audit vs R19 **CLEAN** — 212 changed bytes, all attributed;
  unexplained = 0. Attributed by hand as well: 192 bytes of the slot 5
  `PUT setpoint` grid (8 rows × 12 int16 columns), 16 bytes of the slot 5
  `Spark modifier` grid (16 single-byte cells), and the 4 stored checksum bytes.
- **Independent XDF decode of both bins** — 3814 base-XDF tables and 185
  switch-patch tables, zero decode errors — finds exactly **two** changed
  tables: `0x7d31a` `Spark modifier` (16 cells) and `0x7d71a` `PUT setpoint`
  (96 cells). Every table under the base XDF is byte-identical to R19,
  including all `IP_IGA_BAS_*` maps (**AE1**). Slot 4's `Spark modifier` and
  `PUT setpoint` are byte-identical to R19 (**AE2**). Slot 5's `Spark modifier`
  reads back with exactly 16 non-neutral cells and 240 at 0.00° (**AE3** — the
  origin doc's "224" was an arithmetic slip; the grid is 16 × 16 = 256). Slot 5's
  `PUT setpoint` reads back equal to slot 4's cell for cell, peak 2809 hPa
  absolute (**AE4**).
- **Determinism:** four independent runs produced byte-identical bins.
- Comparison PNGs exist for **both** changed tables, named per table:
  `compare/Spark modifier 0x7d31a__*.png` and
  `compare/PUT setpoint 0x7d71a__*.png`.
- **Negative control — and a correction to what the byte audit proves.** The
  R20 plan expected that pointing `reference_bin` at the *R18* bin would make
  the audit fail. **It does not, and should not.** Run that way the audit
  reports 360 changed bytes, all attributed, unexplained = 0. The reason is the
  lineage's own convention: a revision re-declares its **entire** calibration,
  so R20's journal covers all 144 tables including the ones R19 changed, and the
  allowance derived from that journal legitimately absorbs R19's edits too.

  The audit's actual guarantee is **"no byte changed that this script did not
  declare"** — not "the reference bin is the one you meant". What enforces the
  latter is the `R19_REFERENCE_SHA256` check at the top of `main()`, which
  refuses to build at all against a bin whose hash is not the flashed R19's.
  Verified: repointing `R19_REFERENCE` at the R18 bin exits 1 with
  `R19 reference hash mismatch: b3bf96a4… ; expected 70d4da67…` before a single
  table is read. Both mechanisms are needed and neither substitutes for the
  other. Future revisions should not expect a wrong-reference audit to fail.
- Script guards that must hold for the build to finish: every declared offset is
  positive, finite, and a whole multiple of the 0.375 °CRK storage step; the
  grid's rpm and airmass axes match the ones the timing constants are written
  on; slot 5's grid reads the as-patched neutral going in; slot 4's R19 boost
  grid is row-uniform and matches this script's own slot 4 declaration; after
  the write, all nine base ignition maps and all four other slots' `Spark
  modifier` grids are unchanged; and delivered timing never exceeds +5.00 °CRK.
- The untouched recovery image retained SHA-256
  `d61a6e297b3ac1d25f60ec8cb3bb504ff47f2db603a960a56e6a6e34074ad69b`.

### Library work this revision required

`SwitchPatch2933` bound 92 tables and the five `Spark modifier` grids were not
among them, so the revision could not be written at all until the library gained
them. Two commits on `feat/switchpatch-spark-modifier-grids` in `Code/`:

- **Profile binding** — `S50_SPARK_GRID_UIDS` plus one `TableSpec` per slot;
  the profile now resolves 97 specs. Slot attribution is from each table's third
  `CATEGORYMEM` (Map Slot 1–5), **not** from the tidy `0x100` address stride,
  which would have been a guess that happened to be right. The grid **shape
  travels with the address book** rather than being a constant of the patch:
  A05's grids are (16, 18), not (16, 16), and because these tables bind by
  uniqueid a wrong shape resolves perfectly and writes wrong.
- **`slot_spark_map()`** — the one guarded, journaled write path, with the four
  guards described above. Generic bridge edits to it are refused, matching the
  existing domain-owned-table contract.

One defect surfaced during R20's own verification and was fixed in the same
branch: comparison plots are named from a table's symbol, and every patch-added
table's "symbol" is the XDF description line `|X: x|Y: y`. Both of R20's changed
tables therefore wrote to the same three PNG filenames and one silently
overwrote the other — the review gate would have been looking at one table
believing it was looking at two. Plot stems now carry the uniqueid whenever the
name is not shaped like an A2L symbol.

### Human review and logging gate

Review the R19→R20 comparison plots for **both** changed tables. They are the
only two that may differ: **the nine base ignition maps and every slot 4 table
must show no change at all**, or slot 4 is no longer the control this revision is
measured against.

**This revision's validation is a within-session A/B, and it will be worthless if
it is logged the way every previous revision was logged.** The protocol:

1. **One dosed tank.** 10–11 oz VP Octanium **Unleaded** per 10 US gallons,
   mixed, before the session. Not 2855.
2. **At least three slot-5 and three slot-4 pulls, interleaved** — alternate
   slots, do not do all of one then all of the other. Same road, same direction,
   cool air.
3. Full actual-3rd-gear WOT pulls to redline, **holding WOT into 4th** after the
   upshift, as with R18 and R19.
4. **Per-cylinder knock-sensor channels in the logging list.**
5. **Drop a `*.bin.txt` record of the flashed file into `Logs/MainTune_R20/`.**
   Three revisions are now in play and a log folder cannot otherwise prove which
   bin produced it.

What decides whether R20 worked:

1. **The timing actually arrives** (**AE5**) — at matched rpm and airmass, slot 5
   `Ign Table` should sit above slot 4 by approximately the modifier row above.
   Note that `Ign Table` is the base-table output, not final commanded timing;
   the R19 fit reproduces it from a pure lookup to 0.184° rms, which is what
   makes this a readable measurement. If the gap is absent, the `Spark modifier`
   does not apply in this control state and the whole approach is wrong — that
   is the single most informative outcome this session can produce.
2. **Knock character** (**AE6**) — no `Knock Cyl n` channel below −1.50 °CRK, and
   no window with two cylinders retarding in the same sample. Character, not
   depth: one settled event that recovers is a working knock loop.
3. **Power** (**AE7**) — slot 5 above slot 4 on peak F=ma wheel hp in the same
   session, computed with the in-gear trim from the `Calc HP` gear-flip rule.
4. **Boost is unchanged between slots.** Slot 5 carries slot 4's curve exactly,
   so any boost difference between the two is instrumentation or conditions, not
   calibration — and a real one would invalidate the single-variable claim.

**Stop signals** — switch to slot 4 immediately and end the session: retard
deeper than −1.50 °CRK, retard that ramps rather than decaying, two cylinders
retarding in the same sample, accumulated retard approaching the untouched
`IP_IGA_MAX_KNK` — Maximum value for spark retard floor, or loss of lambda or
fuel-pressure control.

**Carried forward, unresolved:** `Tunes/MainTune/tune_code_review.md` P1 against
the R19 intake-axis re-breakpoint is still open. R19 was flashed with it open
(recorded in § R19); R20 inherits that geometry unchanged and does not resolve
it. It is not a reason to hold R20 — R20 changes nothing in that domain — but it
is still owed a part-throttle high-rpm log.

Still **revision 20 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU.

## R21 — cut slot 5's peak-load timing, keep the top end

R21 inherits the complete R20 calibration byte for byte and changes **exactly
one table**: slot 5's `Spark modifier` — map slot 5 ignition offset, in two of
its eight written rpm columns. Four cells move. Slot 5's `PUT setpoint` — map
slot 5 boost cap, the nine `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic
ignition angle maps, and every slot 4 table are untouched, which is what keeps
slot 4 usable as the control.

Script: `Tunes/MainTune/TUNE_MainTune_R21.py`. Output:
`MainTune_out/R21_20260831-155410/Patched_259L_R21.bin`.

### What the R20 logs actually said

`Logs/BasicsGuide_R20/` holds ten dosed-tank pulls from 2026-08-31. The R20
gate asked for an interleaved within-session slot-4 / slot-5 A/B and **did not
get one — all ten pulls were slot 5** (every pull carries the modifier in
`Ign Avg`). R20 therefore had to be scored cross-session against R19's eight
slot-4 pulls, with day and fuel left as explicit confounds. Same event
definitions (`knock_events` / `loaded_mask`, all gears, pedal ≥ 90%, rpm ≥ 3000,
airmass ≥ 0.9 g/stk, TPS ≥ 60%):

| Band (rpm) | R19 ev/loaded-min | R20 ev/loaded-min | Mean mg/stk | R20 modifier   | Read                                    |
|------------|-------------------|-------------------|-------------|----------------|-----------------------------------------|
| 3000–3500  | 43.2              | 40.5              | 1278        | +1.12 → +1.50  | pre-existing, R20 did not cause it      |
| 3500–4000  | 0.0               | 9.4               | 1517        | +1.50 → +2.25  | 1 event, noise                          |
| 4000–4500  | 7.9               | 6.3               | 1518        | +2.25 → +3.00  | flat                                    |
| 4500–5000  | 4.2               | 27.5              | 1505        | +3.00 → +3.75  | **the regression** — p ≈ 0.0006         |
| 5000–5500  | 9.7               | 0.0               | 1423        | +3.75 → +2.25  | apex is clean, and improved             |
| 5500–6000  | 4.0               | 6.0               | 1305        | +2.25 → +1.50  | flat                                    |
| 6000–6600  | 6.7               | 22.1              | 1204        | +1.50 → +1.12  | 3 events vs 1 — does not separate       |

Only 4500–5000 separates from noise: 6 events against an exposure-matched
expectation of 0.9, and the only band in the session to exceed one detected
event's worth of retard — two −2.25 °CRK cuts, at 4615 and 4653 rpm. Session
totals were 15.33 ev/loaded-min on R20 against 8.63 on R19, worst −2.25 against
−1.50.

Two things that look like findings and are not. **3000–3500 is pre-existing**:
it is the highest-rate band in either session and R19 ran 43.2/min there with no
modifier at all, so it is not R20's to fix and R21 does not touch it. **6000–6600
does not separate**: 3 events against 1 on comparable exposure is Poisson
p ≈ 0.3.

Sam's mixing hypothesis — that the octane dose had not blended and the early
pulls were effectively on lower octane — was tested and **is not supported**.
Rank correlation of knock retard area with minutes into the drive is +0.008
across the nine full pulls; the cleanest pull of the session is the second one
(zero retard, and the session's highest peak rpm at 6368), the worst is in the
middle at 6.2 min, and thirds of the sequence run 1.05 → 2.65 → 1.35 °CRK·s.
Oil temperature is effectively a clock here (+0.983 with time) yet correlates
only +0.084 with knock area, so heat soak is not the driver either. This rules
out mixing *progressing during the logged session*; it cannot rule out that the
dose had already blended before the first pull. Evidence:
`Logs/BasicsGuide_R20/plots/r20_knock_timeline.png`,
`Logs/BasicsGuide_R20/analyze_r20_knock_timeline.py`.

### The shape, and why the cut is not at the peak

The counterintuitive result is that the **+3.750 °CRK apex at 5000 rpm produced
zero knock** over 9.5 s of exposure and improved on R19's 9.7/min, while the
+3.000 cell at 4500 produced six events. The separating variable is cylinder
filling: 1505 mg/stk mean across 4500–5000 against 1423 across 5000–5500. So
R21 cuts the peak-load shoulder and holds the apex.

    rpm       3000    3500    4000    4500    5000    5500    6000    6500
    base     -7.500  -6.750  -4.500  -3.750  -2.250  +0.750  +1.875  +3.375
    R20      +1.125  +1.500  +2.250  +3.000  +3.750  +2.250  +1.500  +1.125
    R21      +1.125  +1.500  +1.500  +1.500  +3.750  +2.250  +1.500  +1.125
    slot 5   -6.375  -5.250  -3.000  -2.250  +1.500  +3.000  +3.375  +4.500

Mean offset across the 4500–4700 knock cluster falls from +3.15 to +1.95 °CRK;
the two −2.25 °CRK cut points fall from +3.17/+3.23 to +2.02/+2.19. The 4000
column comes down with 4500 so the interpolation into the cut does not restore
the same offset at 4250 rpm — on its own 4000–4500 was flat between sessions and
is not independently indicted. Delivered timing still peaks at +4.500 °CRK at
6500 rpm, unchanged from R20, because the cut is below the peak.

### Why the rpm breakpoints did not move

Sam asked whether a breakpoint change would help. It would — a breakpoint near
4700 rpm separates the peak-load shoulder from the clean apex far better than
the existing columns can — but **it is not available**. The `Spark modifier`
grid's rpm axis `0x3CE5A` and airmass axis `0x3CDBC` are each referenced by
**37 tables**: all 18 `IP_IGA_BAS_IVVT_VVL_PORT_L` — Basic ignition angle maps
(both VVL banks × 9) *and* all five slots' `Spark modifier` grids. Moving a
breakpoint would silently re-index the entire ignition calibration on every
slot, including slot 1 (stock) and slot 4 (the everyday map and this revision's
control). The shape is expressed on the existing columns instead. This is the
blast-radius grep the `shared-axis-editing` rule exists for, and it is the
second time in this lineage that it has changed a design.

### Deliberately single-variable

Sam also asked about adding timing near redline. It was considered and declined
for this revision, and queued for R22:

- **6500 rpm is nearly capped already.** R20 delivers base +3.375 + 1.125 =
  **+4.500 °CRK** against the script's `MAX_DELIVERED_DEG` = +5.00 guard. The
  next storable step (+1.500 modifier → +4.875 delivered) is the last one that
  fits; going further means raising the safety ceiling itself.
- **6000 rpm has room** — base +1.875, so the modifier could reach +3.000
  (delivered +4.875) inside the same guard.
- **But 6000–6600 is the band that went 6.7 → 22.1 ev/min.** The sample is too
  small to call a regression, and equally too small to call it headroom.
- **And R20's own lesson was about readability.** A revision that cuts at 4500
  and raises at 6000 cannot be read either way by the next session — which is
  exactly what the missing slot-4 A/B already cost R20.

Also queued for R22: writing the 1049.97 mg/stk row. At 6000+ rpm airmass runs
~1204 mg/stk, right at the 1200.01 breakpoint, so the grid interpolates down
toward the neutral row and only ~90% of the column value is actually delivered
at redline.

### Verification

- `build()` reports **checksums CLEAN** (CAL_CRC, ECM3), **final-bin readback
  PASS** (144 tables re-read off the saved file and matched to the journal), and
  a **raw-diff audit vs `Patched_259L_R20.bin`: CLEAN — 8 changed bytes, all
  attributed, unexplained = 0** (4 journaled edit bytes = 2 columns × 2 rows at
  1 byte per cell, plus 4 stored checksum bytes).
- **Independent XDF decode of both bins** — 3814 base-XDF tables and 185
  switch-patch tables, zero decode errors — finds exactly **one** changed table:
  `0x7d31a` `Spark modifier`, 4 cells. Every base ignition map and every slot 4
  table is byte-identical to R20.
- **Determinism:** two independent runs produced byte-identical bins,
  SHA-256 `ec2374f693752640c800ee8ed2fc9a87bbe6e5813c7687d56ef3843e028ca5c6`.
- The `R20_REFERENCE_SHA256` gate at the top of `main()` refuses to build at all
  against a reference bin whose hash is not the flashed R20's
  (`8c0b4d18ea7491f7c0ea595805abfa2aae3d23b55697e640622a4d26bfe83990`). As
  recorded in § R20, the byte audit alone does not prove the reference is the
  one you meant — that gate does, and both are needed.
- Script guards added for R21 specifically: the declared shape must differ from
  R20's in **exactly** the two declared columns, and every changed column must
  move **down**. A transposed or mis-indexed edit that happened to stay on the
  0.375 °CRK lattice would otherwise reach the ECU looking deliberate. The R20
  guards all still run: positive, finite, storable offsets; axes matching the
  ones the timing constants are written on; slot 5 neutral going in; base maps
  and the other four slots unchanged after the write; delivered timing ≤ +5.00.
- Only one table has comparison PNGs, which is itself the check —
  `compare/Spark modifier 0x7d31a__*.png`.

### Human review and logging gate

Review the single R20→R21 comparison plot. It is the only table that may differ.
**Slot 5's boost cap, the nine base ignition maps, and every slot 4 table must
show no change at all**, or slot 4 is no longer the control.

**Log this one the way R20 was supposed to be logged.** R20's protocol was
correct and was not followed; R21 is unreadable without it:

1. **One dosed tank.** 10–11 oz VP Octanium **Unleaded** per 10 US gallons,
   mixed, before the session. Not 2855.
2. **At least three slot-5 and three slot-4 pulls, interleaved** — alternate
   slots, do not do all of one then all of the other.
3. Full actual-3rd-gear WOT pulls to redline, **holding WOT into 4th** after the
   upshift. The 4th-gear continuation is not optional: R20's second-deepest cut
   (−2.25 °CRK on pull 8) is only visible there.
4. **Per-cylinder knock-sensor channels in the logging list.**
5. Log folder `Logs/MainTune_R21/`. The flashed bin is recorded automatically in
   the CSV header's last column (`SimosTools [R2.12:…:Patched_259L_R21.bin]`),
   so a separate `*.bin.txt` is redundant — but check that column matches.

What decides whether R21 worked:

1. **The 4500–5000 band comes back down** toward R19's 4.2 ev/loaded-min. This
   is the whole question.
2. **The 5000–5500 apex stays clean** at its unchanged +3.750 °CRK. If it starts
   knocking now, the read that load rather than offset size is binding was wrong.
3. **Power** — slot 5 above slot 4 on peak F=ma wheel hp in the same session,
   in-gear trimmed per the `Calc HP` gear-flip rule. R20 measured 263 hp (8
   pulls) against R19's 256 (6 pulls), cross-session.
4. **Boost identical between slots**, since slot 5 still carries slot 4's curve
   exactly.

**Stop signals** — switch to slot 4 and end the session: retard deeper than
−1.50 °CRK that does not recover, retard that ramps rather than decaying, two
cylinders retarding in the same sample sustained, accumulated retard approaching
the untouched `IP_IGA_MAX_KNK` — Maximum value for spark retard floor, or loss
of lambda or fuel-pressure control.

**Carried forward, unresolved.** `Tunes/MainTune/tune_code_review.md` P1 against
the R19 intake-axis re-breakpoint is still open; R21 inherits that geometry
unchanged and does not resolve it, and it is still owed a part-throttle high-rpm
log. R20's AE6 gate as written ("no channel below −1.50 °CRK, no window with two
cylinders retarding in the same sample") **failed on both counts** — pull 5 and
pull 8 both reached −2.25, and pulls 7 and 8 had 13 and 23 two-cylinder samples,
at 3048/3149 rpm in the pre-existing low-rpm zone. R21 does not address that
zone; it is a candidate for a later revision.

Still **revision 21 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU.

## R22 — reorder the slot ladder by fuel requirement, add the mid-boost octane slot

R22 inherits the complete R20 calibration and changes **five tables, all of them
per-slot**: the `PUT setpoint` — map slot boost caps of slots 1, 3 and 4, and the
`Spark modifier` — map slot ignition offsets of slots 4 and 5. Slots 3 and 4
exchange curves; slot 1 takes slot 2's curve above 4400 rpm. Slot 5's boost cap
and slot 2 are unchanged from R20. Every shared table — the nine
`IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]` — Basic ignition angle maps, the knock
fast-loop tables, the wastegate feedforward and its re-breakpointed intake axis,
the Spark IAT tables, fueling, limiters, and the patch set — is untouched.

Script: `Tunes/MainTune/TUNE_MainTune_R22.py`. Output:
`MainTune_out/R22_20260901-060746/Patched_259L_R22.bin`.

**R21 is superseded and was never flashed.** It was built and fully verified
(§ R21), but the car still holds R20, so R22's byte-level audit is taken against
the R20 bin — that diff is the change that actually reaches the ECU. R21's slot 5
timing is carried forward byte for byte; nothing about it was rejected.

### Why the ladder had to move

R14 ordered the five slots least-to-most **boost**. That stopped being the right
axis in R20, when slot 5 became a *timing* map rather than a boost map: a slot
that runs slot 4's boost with more ignition advance has no position on a boost
ladder, and "slot 4 is the safe one" — the rule every stop-signal instruction in
this lineage was written around — stopped describing anything structural.

R22 orders the ladder by **fuel requirement** instead:

| Slot | Boost                                         | Timing           | Fuel      | Role                                         |
|------|-----------------------------------------------|------------------|-----------|----------------------------------------------|
| 1    | ~21.6 psi to 3800 rpm, then slot 2's to ~17.2 | base             | pump 92   | low / bad tank / handing the keys over       |
| 2    | conservative ~24.5                            | base             | pump 92   |                                              |
| 3    | aggressive ~26.0                              | base             | pump 92   | **everyday map, in-drive fallback, control** |
| 4    | mid ~24.4 psi                                 | R20 octane shape | **dosed** | the reduced-**boost** slot                   |
| 5    | aggressive ~26.0                              | R21 octane shape | **dosed** | the reduced-**timing** slot                  |

Slots 1–3 are safe on any tank; slots 4 and 5 require the VP Octanium dose. That
boundary is a single line in the ladder rather than a fact about one slot, which
is the whole reason for the reorder.

The shuffle is a **permutation of curves the car has already run**, not a
recalibration. The aggressive ~26 psi curve that has been slot 4 since R14 moves
down to slot 3 unchanged, and the intermediate ~24.5 psi curve that was slot 3
moves up to slot 4. Both are *read off the R20 bin* by `_curve_from_r20` rather
than retyped, and each read is checked against the curve this script
independently declares — so the control slot provably keeps the exact calibration
every log from R14 through R20 was scored against. Nothing is deleted except the
intermediate slot's *position*; slot 1's stock map survives, and with the R12
valet cap already spent on slot 5 back in R20 it is the only genuinely low map
left in the ladder.

### Slot 1 sheds boost at high rpm

Slot 1 is still **named** the stock map and is still the least aggressive slot,
but from R22 that name is not a claim about the whole range. At and above 4400
rpm it takes slot 2's conservative curve, which sits **below** the factory
`IP_PUT_SP` — Pressure up throttle setpoint target there:

| rpm     | 3000 | 3200 | 3400 | 3800 | 4400 | 4700 | 5000 | 5400 | 5750 | 6000 | 6250 | 6500 |
|---------|------|------|------|------|------|------|------|------|------|------|------|------|
| factory | 2502 | 2502 | 2502 | 2503 | 2503 | 2504 | 2504 | 2505 | 2505 | 2505 | 2506 | 2506 |
| slot 2  | 2699 | 2659 | 2619 | 2540 | 2440 | 2395 | 2350 | 2323 | 2299 | 2266 | 2232 | 2199 |
| slot 1  | 2502 | 2502 | 2502 | 2503 | 2440 | 2395 | 2350 | 2323 | 2299 | 2266 | 2232 | 2199 |

So slot 1 holds ~21.6 psi to 3800 rpm and then falls with slot 2 to **~17.2 psi
at 6500 rpm**, against the factory ~21.6. It gets *less* aggressive exactly where
cylinder pressure and knock risk are worst, and its low end keeps the factory
value — still read live off the recovery bin by `_stock_full_load_curve`, so the
provenance R14 established survives for the part of the range where the factory
number is the conservative one.

**Why the threshold is expressible at all.** The two curves cross at roughly 4020
rpm: below it the factory target is the lower of the two, above it slot 2's is.
The shared slot axis steps 3800 then 4400, with no 4100 breakpoint, so any
threshold in (3800, 4400] produces the identical curve — and because the crossing
falls in that same interval, the composed curve is exactly the **lower** of the
two at every breakpoint. `_slot1_curve` asserts that rather than leaving it as a
coincidence: a threshold moved off the crossing would have slot 1 silently taking
the *higher* value somewhere, which is a boost lift on the map that exists to be
the safe one.

`_check_slot_ladder` also asserts slot 1 sits at or below **every** other slot at
every breakpoint. Composing a slot from two curves instead of reading one makes
that worth checking rather than assuming.

Slot 1 and slot 2 are now byte-identical from 4400 rpm up, which is visible in
the plot as slot 1's dashed line running on top of slot 2's. They still differ
below it — slot 2 starts at 2699 hPa and decays, slot 1 holds the flat factory
value — so the two slots remain distinct maps.

### What this costs, and it is not nothing

**The in-drive fallback moved from slot 4 to slot 3.** Every stop-signal
instruction in §§ R20–R21 said "switch to slot 4 immediately"; slot 4 is now one
of the two maps that *needs* good fuel. From R22 the fallback is **slot 3**.

**Log review inherits the same hazard.** In any log before R22, slot 4 means the
aggressive pump-gas control. In any log from R22 on, it means the mid-boost
octane map. The two have different boost curves, so they are distinguishable
after the fact — but the selected slot must be **recorded per session**, not
inferred from the slot number's history. This is the single most likely way to
misread the next log folder.

### The experiment R22 actually runs

R20's logs said the 4500–5000 rpm knock tracked **cylinder filling**, not offset
size: the band ran 1505 mg/stk and 27.5 events per loaded minute against R19 slot
4's 4.2 (Poisson p ≈ 0.0006), carrying both of the session's −2.25 °CRK cuts,
while the larger +3.750 °CRK apex at 5000 rpm ran 1423 mg/stk and logged **zero**
events over 9.5 s (§ R21, `Logs/BasicsGuide_R20/log_review.md`).

There are two ways to act on that reading, and R21 only took one of them. R22
runs both, against the same control, in the same session, on the same tank:

| rpm         | 3000   | 3500   | 4000   | 4500   | 5000   | 5500   | 6000   | 6500   |
|-------------|--------|--------|--------|--------|--------|--------|--------|--------|
| base        | −7.500 | −6.750 | −4.500 | −3.750 | −2.250 | +0.750 | +1.875 | +3.375 |
| slot 3 mod  | —      | —      | —      | —      | —      | —      | —      | —      |
| slot 4 mod  | +1.125 | +1.500 | +2.250 | +3.000 | +3.750 | +2.250 | +1.500 | +1.125 |
| slot 5 mod  | +1.125 | +1.500 | +1.500 | +1.500 | +3.750 | +2.250 | +1.500 | +1.125 |
| slot 4 dlvd | −6.375 | −5.250 | −2.250 | −0.750 | +1.500 | +3.000 | +3.375 | +4.500 |
| slot 5 dlvd | −6.375 | −5.250 | −3.000 | −2.250 | +1.500 | +3.000 | +3.375 | +4.500 |

- **Slot 4** holds R20's *uncut* timing — the timing that knocked — and removes
  ~1.6 psi of boost instead.
- **Slot 5** holds R21's cut timing on the full boost curve.
- **Slot 3** holds neither, on the full boost curve.

Each octane slot differs from the control in exactly one dimension, and the two
slots differ from each other in exactly two rpm columns of timing and one boost
curve. If slot 4 runs clean at 4500–5000 where R20 knocked, cylinder filling is
confirmed as the binding variable and trading boost for timing is on the table.
If it knocks anyway, offset size is what matters and R21's cut is the right
shape. Either outcome is readable in **one** session, which R20's slot-5-only
session was not.

**Where the contrast is, and where it is not.** Slot 4 sits 110–123 hPa
(1.6–1.8 psi) under slot 5 from 3200 through 5400 rpm — the whole knock band —
and converges to within 20 hPa by 6500 rpm:

| rpm     | 3000 | 3200 | 3400 | 3800 | 4400 | 4700 | 5000 | 5400 | 5750 | 6000 | 6250 | 6500 |
|---------|------|------|------|------|------|------|------|------|------|------|------|------|
| slot 5  | 2699 | 2754 | 2809 | 2809 | 2809 | 2760 | 2712 | 2609 | 2519 | 2427 | 2335 | 2243 |
| slot 4  | 2699 | 2699 | 2699 | 2699 | 2699 | 2645 | 2589 | 2503 | 2414 | 2350 | 2286 | 2223 |
| Δ (hPa) | 0    | 55   | 110  | 110  | 110  | 116  | 123  | 106  | 105  | 77   | 49   | 20   |

So R22 **does not** claim to test the 6000–6600 band, where the two octane slots
are nearly the same map. That band went 6.7 → 22.1 ev/min on R20 and is still
unresolved; it is R23's, not this revision's.

### What was considered and rejected

**Re-breakpointing the modifier grid's rpm axis** — still refused, for the reason
recorded in § R21: the grid's rpm axis `0x3CE5A` and airmass axis `0x3CDBC` are
shared by all 18 `IP_IGA_BAS_IVVT_VVL_PORT_L` — Basic ignition angle maps *and*
all five slots' `Spark modifier` grids, 37 axis references each. Moving a
breakpoint re-indexes the whole ignition calibration on every slot, the control
included. Standing "do not".

**Dropping slot 1's stock map** to free a slot. Not needed: moving slot 4's curve
to slot 3 frees the intermediate slot, which is the near-duplicate of slot 2
(2699 flat to 4400 rpm against conservative's 2659–2440) and the only genuinely
redundant entry in the ladder. Spending slot 1 as well would have left ~24.5 psi
as the least map in the car.

**A larger boost step for slot 4** — e.g. slot 2's conservative curve, ~5.3 psi
under slot 5 at 4400–5000. It would almost certainly run clean, but it throws
away enough of the pull that the power comparison against slot 5 stops meaning
anything. `OCTANE_BOOST_DELTA_MAX_HPA = 200` in the script encodes that as a
design bound: past it, the reduced-boost slot is a different engine rather than a
neighbouring calibration.

**Raising the near-redline modifier in the same revision.** Still queued for R23,
still gated on this session logging clean, for the reason § R21 gives.

### Verification (run `R22_20260901-060746`)

- `build()` reports **checksums CLEAN** (CAL_CRC, ECM3), **final-bin readback
  PASS** (145 tables re-read off the saved bin and matched to the journal), and a
  **raw-diff audit vs `Patched_259L_R20.bin`: CLEAN — 504 changed bytes, all
  attributed, unexplained = 0**. The 504 reconcile exactly: 2 × 176 bytes for the
  two swapped `PUT setpoint` grids (11 of 12 rpm columns differ — both curves
  start at 2699 hPa at 3000 rpm — × 8 rows × 2 bytes each), 128 bytes for slot 1's
  grid (the 8 rpm columns at and above 4400 × 8 rows × 2 bytes), 16 bytes for
  slot 4's newly written `Spark modifier` grid (8 columns × 2 rows × 1 byte), 4
  bytes for slot 5's `Spark modifier` (R21's cut), and 4 stored checksum bytes.
- **Independent XDF decode of both bins** — 3814 base-XDF tables and 185
  switch-patch tables, zero decode errors — finds **zero** changed tables in the
  base XDF and exactly **five** in the switch-patch XDF: `0x7d41a` `PUT setpoint`
  (slot 1, 64 cells), `0x7d59a` and `0x7d65a` `PUT setpoint` (slots 3 and 4, 88
  cells each) and `0x7d21a` / `0x7d31a` `Spark modifier` (slots 4 and 5, 16 and 4
  cells). The five tables with comparison PNGs are the same five, which is itself
  the check.
- **Slot-level permutation check**, decoded independently of the build: R22 slot
  3's boost cap is byte-identical to R20 slot 4's; R22 slot 4's is byte-identical
  to R20 slot 3's; slot 5's is unchanged from R20 and equal to slot 3's; slot 2 is
  unchanged; slot 1 is byte-identical to R20's below 4400 rpm and to slot 2's at
  4400 and above, and sits ≤ every other slot at every breakpoint; slot 4's grid
  is ≤ slot 5's at **every** breakpoint; slot 4's `Spark modifier` is
  byte-identical to R20's slot 5 grid (R20's timing, restored exactly); slots 1–3
  hold the as-patched neutral `Spark modifier` and are byte-identical to R20.
- **Determinism:** three independent runs produced byte-identical bins, SHA-256
  `08372bdee7c1c6b7b0ca89c8f9da31515622080927c99439f5578e6965bb475e`. Only the
  `R22_20260901-060746` run folder is kept; the earlier R22 folders — two more of
  this build, and three of the pre-slot-1 build (SHA-256 `8635469a…`, 376 changed
  bytes) — were deleted once superseded.
- The `R20_REFERENCE_SHA256` gate at the top of `main()` refuses to build against
  a reference bin whose hash is not the flashed R20's
  (`8c0b4d18ea7491f7c0ea595805abfa2aae3d23b55697e640622a4d26bfe83990`).
- **Script guards added for R22 specifically.** `_check_slot_ladder()` runs
  before any write and proves the ladder is the claimed permutation: control and
  full-boost slot carry the same aggressive curve, the mid slot carries the
  intermediate one, the mid slot is at or below the full slot at every breakpoint,
  the two actually differ, they differ by no more than the declared design bound,
  and slot 1 is at or below every other slot everywhere. `_slot1_curve()` proves
  the composed slot 1 curve is slot 2's above the threshold, the factory target
  below it, and the lower of the two at every breakpoint. `_apply_r22_slot_timing()` proves the *relationship* between the slots,
  which no single-slot check can see: slot 4 must restore R20's timing exactly,
  slot 5 must differ from it in exactly the declared columns and never upward.
  All the R20/R21 guards still run — positive, finite, storable offsets; axes
  matching the ones the timing constants are written on; both octane slots
  neutral going in; base maps and slots 1–3 unchanged after the write; delivered
  timing ≤ +5.00 °CRK on both slots (both peak at +4.500° at 6500 rpm).
- One note on reading the bin yourself: the patch's neutral `Spark modifier`
  value decodes to 7.1 × 10⁻¹⁵ °CRK, not exact 0.0. An equality-to-zero test on
  slots 1–3 will report a false difference; compare with a tolerance, or compare
  against R20 byte for byte.

### Human review and logging gate

Review the five R20→R22 comparison plots. **They are the only five tables that
may differ**: `PUT setpoint` `0x7d59a` and `0x7d65a` (slots 3 and 4 exchanging
curves — each plot's delta panel should show the *other* slot's curve arriving,
not a new shape), `PUT setpoint` `0x7d41a` (slot 1 — the delta panel must be zero
at 3000–3800 rpm and negative everywhere above), and `Spark modifier` `0x7d21a`
and `0x7d31a`. Slot 5's boost cap, slot 2, the nine base ignition maps, and every
shared base table must show no change at all, or the control is not a control.

`Tunes/MainTune/plot_r22_slot_boost.py` draws all five slot curves on one pair of
axes, read off the candidate bin, and is the quickest way to see the ladder whole
before flashing:
`MainTune_out/R22_20260901-060746/compare_slots/R22 map slot boost caps.png`.

**Before driving: confirm the slot mapping in the car.** The ladder changed
positions. Verify by boost, not by memory — slot 3 must now pull ~26 psi and slot
4 ~24.4 psi, and slot 1 must fall away above 4400 rpm rather than holding ~21.6
psi to redline. If they read the other way round, stop; the flash did not take or
the slot indexing is not what this revision assumes.

**Log it as a three-slot session:**

1. **One dosed tank.** 10–11 oz VP Octanium **Unleaded** per 10 US gallons,
   mixed, before the session. Not 2855.
2. **At least three pulls each on slots 3, 4, and 5, interleaved** — rotate
   3 → 4 → 5 → 3 → …, do not run all of one slot and then the next. R20's whole
   readability problem was a single-slot session; R22 has three slots and the same
   failure mode is three times as easy to fall into.
3. Full actual-3rd-gear WOT pulls to redline, **holding WOT into 4th** after the
   upshift. The 4th-gear continuation is not optional — R20's second-deepest cut
   was only visible there.
4. **Per-cylinder knock-sensor channels in the logging list.**
5. Log folder `Logs/MainTune_R22/`. The flashed bin is recorded in the CSV
   header's last column; **also note the selected slot per pull**, because the
   slot numbers no longer mean what they meant in earlier folders.

What decides whether R22 worked:

1. **Does slot 4 knock at 4500–5000 rpm?** This is the question. Clean → cylinder
   filling is the binding variable, and boost-for-timing is a real trade.
   Knocking → offset size binds, and R21's cut is the right response.
2. **Does slot 5's 4500–5000 band come back down** toward the control's rate?
   That is R21's own hypothesis, now finally measured against a same-session
   control instead of cross-session against R19.
3. **The 5000–5500 apex stays clean on both slots** at its unchanged +3.750 °CRK.
   If it starts knocking, the load reading was wrong on both slots.
4. **Power**, in-gear trimmed per the `Calc HP` gear-flip rule: slot 5 vs slot 4
   vs slot 3 peak F=ma wheel hp in the same session. Slot 4 giving up little to
   slot 5 would make the reduced-boost slot the better map outright.
5. **Boost separation is real in the logs** — slot 4 should track ~110–123 hPa
   under slots 3 and 5 across 3400–5400 rpm. If it does not, the slots are not
   what this revision built and nothing above is interpretable.

**Stop signals** — switch to **slot 3** (not slot 4) and end the session: retard
deeper than −1.50 °CRK that does not recover, retard that ramps rather than
decaying, two cylinders retarding in the same sample sustained, accumulated
retard approaching the untouched `IP_IGA_MAX_KNK` — Maximum value for spark
retard floor, or loss of lambda or fuel-pressure control.

**Carried forward, unresolved.** `Tunes/MainTune/tune_code_review.md` P1 against
the R19 intake-axis re-breakpoint is still open; R22 inherits that geometry
unchanged and is still owed a part-throttle high-rpm log. The pre-existing
3000–3500 rpm knock zone (43.2 ev/min on R19 with no modifier at all) and the
6000–6600 band are both untouched here.

### What the R22 logs actually said

R22 was flashed and logged on 2026-09-01: 21 pulls in
`Logs/BasicsGuide_R22/`, 20 in 3rd gear, one dosed tank, ambient within 0.4 °C
of the R20 session. Full review with evidence: `Logs/BasicsGuide_R22/log_review.md`.
Recorded here because several of its findings change what the *next* revision
should assume, and one of them is about the fuel rather than the calibration.

**Attribution worked, and cost nothing to recover.** The gate asked for the
selected slot to be recorded per pull and it was not, but two independent
fingerprints resolved all 21 pulls with no ambiguity: fitting logged `PUT SP`
against each slot's `PUT setpoint` — map slot boost cap read off the flashed bin
(RMS 6–7 hPa on the right curve against 90–110 on every wrong one), and
reconstructing the delivered offset as `Ign Avg − Ign Table + worst per-cylinder
retard`, since `Ign Table` carries no slot modifier. Control read 0.00 ± 0.4°,
both octane slots +1.5 to +3.4°, nothing in between. Slot 3 = pulls 10–13,
slot 4 = 5–9/16–18/21, slot 5 = 1–4/14/15/19/20. Automated in
`Logs/BasicsGuide_R22/slot_attribution.py`.

**The calibration delivered what this section promised.** At 4500–5000 rpm slot 4
ran 11.7 kPa under the control against a designed 12.3, slot 5 matched the
control's boost to 0.3 kPa, and the delivered offsets came back at +3.08° and
+2.46°. Airmass corroborates it: slots 3 and 5 within 1.3 mg/stk of each other,
slot 4 48 mg/stk below.

**The experiment came back null.** The two octane slots are indistinguishable —
+0.2 deg-s/min of retard integral apart over 3000–6600 rpm, interval ±15. R22
does not resolve filling versus offset size. The cause is exposure, not design:
the control got 4 pulls against 9 and 8, and no gate item had asked for balance
across slots. **Add that to every future logging gate.**

**§ R21's premise was an artifact.** R21 was built on R20's reading that
4500–5000 rpm went 4.2 → 27.5 ev/min because of the modifier. R22's control runs
the calibration verified byte-identical to R19's slot 4 — same boost cap, all-zero
`Spark modifier` — and lands at 24.0 ev/min in that band, in near-identical
weather. R20's p ≈ 0.0006 treated a rate estimated from **one event** as known.
The band knocks on base timing. R21 should be re-derived, not revived. Where the
slots *do* rise above the control is 5000–5500 — the band R20 called clean — and
they rise together, in the one place their modifiers are byte-identical.

**The octane dose has now been measured, and shows nothing on the everyday map.**
This is the first direct evidence on VP Octanium in the lineage. R20's logs
cannot supply it: all ten usable logs fingerprint as octane-map pulls, so R20
compared a dosed offset map against a plain-92 base map and confounded fuel with
timing. R22 slot 3 is the first dosed *base-timing* slot ever logged, and against
the R19 session — same calibration, plain 92, since R20 introduced the dose — it
is no better on knock (+3.19 deg-s/min over 3000–6600, interval spanning zero)
and no better on power (−2.31 hp at 1.15 se, matched peak filling), despite a
2 °C cooler ambient. See `Logs/BasicsGuide_R22/analyze_octane_value.py` and
`Logs/BasicsGuide_R22/plots/r22_knock_by_slot.png` — on shared axes the plain-92
and dosed base-timing panels are interchangeable and neither passes −1.50 °CRK,
while both dosed octane slots breach it at roughly double the retard rate.

Read that null carefully: base timing is not knock-limited over most of the range
(plain-92 retard 1.3–6.8 deg-s/min outside 3000–3500), so octane has little room
to show a benefit there. It does **not** prove the dose is worthless on the offset
maps — but that case cannot be settled, because the direct test is slot 5 on
plain 92, which § R20 forbids by design. So the booster's whole measurable return
is the **+5.98 hp (2.89 se)** slot 5 makes over the control, bought with more
knock than the control. Whether ~2% is worth dosing every tank, maintaining a
two-tier ladder and never mis-selecting a slot is now an economics decision to
take deliberately rather than an assumption to inherit — and R22's own reorder
already made slot 3 the everyday map and the in-drive fallback, so dropping
slots 4–5 costs nothing structural.

**New safety item, outside the experiment.** Pull 7 (slot 4) reached **−4.50 °CRK
on cylinder 4** at 3156 rpm and held it 1.6 s — twice R20's worst and the deepest
cut in this lineage. Unambiguously real: one cylinder, ramping and decaying, with
`knks_thd[3]` rising alongside. And every 3000–3500 rpm event in the session, on
all three slots, sits at 3026–3156 rpm while the intake **valve-lift 1 → 0
transition** occurs at 3052–3104 rpm on every pull. R20 logged a 6.376 °CRK
ignition-model outlier at 3057 rpm in the same transition and set it aside. The
zone both prior reviews called "pre-existing and never addressed" now has a
candidate mechanism, and it is a larger safety item than anything in the
experiment band.

Still **revision 22 — a starting point, not a finished calibration**. The script
and build pipeline never flash an ECU. The logs above are the first evidence
against it, and they do not close it out.
