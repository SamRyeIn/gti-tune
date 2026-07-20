# R07 — base-timing advance for a little more power (SANDBOX / Opus-Thorough)

Sandbox exploration built on top of the existing R06 pipeline. Lives only under
`Tunes/TuningBasicsGuide/Test/Opus-Thorough/`; it does NOT modify any tracked tune
script, the shared `simoscal` library, or the project `REV_LOG.md`. If adopted,
promote to a real `TUNE_Basics_Guide_R07.py` and log it in the project REV_LOG.

## What R07 is
`R07 = the exact R06 pipeline + one new overlay.` R06 = lambda re-breakpoint (R00),
`apply_basics_sop` incl. the overboost limiter fix, R01 limiter/fuelling writes, R03
lambda floors, R04 knock-retard timing overlay, R05 wastegate feedforward overlay.
R07 adds a base-timing ADVANCE.

## The one change — base-timing advance overlay
Target: the nine WOT base-ignition tables `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][i][e]`
(i,e in 0..2) — `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][*][*]` — Basic Ignition Angle,
VVL 0 Port Flap Low.

Key context that shaped it:
- The base SOP recipe ALREADY writes the guide's published "safe starting" WOT
  timing curve to all nine tables, so R06 already runs that curve, INCLUDING its
  top-power corner. There is no free timing there to "restore".
- R04's real datalogs show the engine knock-limited to redline in the >=900 mg/stk
  rows (R04 retards 3500-6500 rpm there). Adding base timing in that corner is what
  causes knock; the guide caps it deliberately. So R07 leaves it alone.
- The safe headroom is the boost-onset mid-load band (600/700/800 mg/stk,
  3000-6500 rpm) where the guide sits 1-4 deg BELOW the FACTORY value and NO R04
  knock cell falls (all R04 cells are >=900 mg/stk).

Rule: `target = min(guide_value + 1.5 deg, factory/stock value)`, quantized to the
0.375 deg °CRK LSB. Restore up to 1.5 deg of guide-pulled timing, NEVER above what
the OEM shipped. 12 cells advanced +0.75 to +1.5 deg:

| rpm/load (mg/stk) | guide (R06) | -> R07   | factory (stock) |
|-------------------|-------------|----------|-----------------|
| 4000 / 600        | +15.375     | +16.875  | +17.625         |
| 4500 / 600        | +15.750     | +16.500  | +16.500 (cap)   |
| 6000 / 700        | +11.250     | +12.750  | +14.250         |
| 6500 / 700        | +10.500     | +12.000  | +12.000 (cap)   |
| 3000 / 800        | +4.125      | +4.875   | +4.875 (cap)    |
| 3500 / 800        | +4.125      | +5.625   | +8.250          |
| 4000 / 800        | +6.000      | +7.500   | +9.375          |
| 4500 / 800        | +7.125      | +8.625   | +9.375          |
| 5000 / 800        | +9.000      | +10.500  | +11.250         |
| 5500 / 800        | +9.375      | +10.500  | +10.500 (cap)   |
| 6000 / 800        | +6.750      | +8.250   | +10.500         |
| 6500 / 800        | +7.125      | +8.625   | +10.500         |

The same absolute targets go to all nine tables (they share identical stock values
in this band). A live fail-loud guard re-reads the stock bin and REFUSES to write
any value above the factory ceiling or onto any R04 knock cell.

## Verification (all passed)
- Build: checksums CLEAN (`CAL_CRC` + `ECM3`), coherence check passed, not DO NOT FLASH.
- Table-by-table diff of the SAVED, re-opened R07 bin vs a freshly-built R06 bin:
  EXACTLY the nine timing tables differ, each at EXACTLY the 12 intended cells with
  the intended values; zero R04-knock-cell overlap; every advanced cell <= factory.
- Guard test: injected an over-ceiling target and an R04 cell — both raise
  RuntimeError; valid targets apply cleanly.
- No new load-ordering inversion introduced (the 500->600 mg/stk inversions present
  in the guide/stock map are pre-existing, not created here).

## This is revision 0 for timing — MUST be knock-log validated
Base timing is the most engine-damage-prone thing to raise. Flash -> log with knock
monitoring on the very next pull -> back off any cell showing knock retard,
especially the 800 mg/stk row at 5000-6500 rpm (closest to the knock-limited 900
row). Do not treat this as a finished calibration.
