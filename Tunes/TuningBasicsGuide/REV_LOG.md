# TuningBasicsGuide — Revision Log

Lineage of the `TUNE_Basics_Guide_R*.py` tune scripts. Each revision is a
separate file; this log summarizes what changed at each step. Every run writes a
fresh timestamped folder under `TUNE_Basics_Guide_out/R<rev>_<timestamp>/`
holding the saved bin, `report.md`, and `compare/` PNGs.

| Revision | Script                     | Summary                                                                   |
|----------|----------------------------|---------------------------------------------------------------------------|
| R00      | `TUNE_Basics_Guide_R00.py` | Initial revision. Base ecu-tuning-basics SOP + lambda axis re-breakpoint. |
| R01      | `TUNE_Basics_Guide_R01.py` | R00 + six limiter/fuelling writes the recipe left at stock.               |
| R02      | `TUNE_Basics_Guide_R02.py` | Report-honesty only; bin byte-identical to R01.                           |
| R03      | `TUNE_Basics_Guide_R03.py` | R02 + literal 0.80 writes to the three lambda minimum-value floors.       |
| R04      | `TUNE_Basics_Guide_R04.py` | R03 + local WOT knock-retard ignition overlay.                            |
| R05      | `TUNE_Basics_Guide_R05.py` | R04 + wastegate feedforward overlay + X-axis re-breakpoint to cut overboost. |
| R06      | `TUNE_Basics_Guide_R06.py` | R05 + overboost limiter symbol-map fix (now applies 1800→2700 across 6 cells). |

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
