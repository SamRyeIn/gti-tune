# Agent instructions — TUNE_Basics_Guide_R07: patched bin (CBRICK + HSL + switch patch) with switch-patch TC enabled

Written 2026-07-11. These are standalone instructions for a fresh agent session.
Read them fully before writing any code.

## Boot reading (do this first, in order)

1. `CLAUDE.md` (loaded automatically) — folder roles, safety rules, the
   ID-plus-description naming rule, the tuning loop.
2. `index.md` — wiki home.
3. `Code/README.md` — the `simoscal` API, especially §"BTP patching —
   `simoscal.btp`" and §Safety.
4. `Tunes/TuningBasicsGuide/REV_LOG.md` — the full R00–R06 lineage. R06 is the
   current head; read its entry closely.
5. `knowledge/sc8s50-switchpatch-xdf.md` — especially §"Enabling the patch's
   traction control (TC) — per-slot flags" (the exact addresses you will write)
   and §"Which XDF loads under `simoscal`".
6. `knowledge/bintoolz-btp-patching.md` — the `.btp` format, safety procedures,
   and the U1 checksum/XDF findings.
7. `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R06.py` — the script you are
   extending; R07 must reuse its structure and pipeline verbatim.

## Goal

Create `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R07.py`. Relative to R06, the
saved bin gains exactly four things:

1. **`SL CBRICK v1.2 - S50.btp`** — SimosTools anti-brick patch, applied.
2. **`SL HSL v1.1 - S50.btp`** — High Speed Logging patch (enables Mode3E
   logging in the SimosTools app), applied.
3. **`SL PATCH.29.33 - S50.btp`** — the 5-slot on-the-fly map switch patch
   (version 29.33, matching the switch-patch XDFs in the repo), applied.
4. **Switch-patch traction control turned on**: for map slots, set
   `Enable SL TC` — Enable the switch-patch's slip-based traction control = `1`
   AND `Disable OEM TC` — Disable the factory ECU-side TC torque intervention
   = `1` (see "TC flag writes" below for addresses and the slot decision).

Everything R00–R06 already does (lambda re-breakpoint, limiter/fuelling writes,
lambda floors, knock-retard timing overlay, wastegate feedforward overlay,
overboost limiter) must be preserved unchanged.

All three patch files live in `BinToolz-main/patches/` (exact filenames as
listed above, e.g. `BinToolz-main/patches/SL PATCH.29.33 - S50.btp`). Use the
**S50** variants only — they
match this car's SC8S50 file structure. Do not use `SL PATCH.29.33.1` (no S50
variant exists) or older CBRICK/HSL versions.

## Revision mechanics (project conventions — mandatory)

- New file `TUNE_Basics_Guide_R07.py`; never edit R00–R06.
- Cumulative "Revision history" header-comment block: one line per revision
  R00→R07, each with a one-line summary and a pointer to `REV_LOG.md`.
- Add the R07 row to the summary table in `REV_LOG.md` **and** a full `## R07`
  narrative section in the same rationale-heavy style as R05/R06: what changed,
  why, root causes of anything discovered, verification evidence.
- Output goes to a timestamped folder
  `TUNE_Basics_Guide_out/R07_<timestamp>/` containing the saved bin,
  `report.md`, and `compare/` PNGs — same as prior revisions.

## Pipeline order — investigate, don't assume

The script must produce its bin deterministically from the stock bin
`Code/bin/5G0906259L__0002.bin` (read-only; never modify it). You have two
candidate orderings and must **determine empirically which is viable** before
committing to one:

- **(A) Patch first, then CAL edits:** apply the three `.btp` patches to stock,
  then run the R06 tuning pipeline against the patched bin.
- **(B) CAL edits first, then patch:** run the R06 pipeline on stock (i.e.
  reproduce the R06 bin), then apply the patches.

Why this matters: a `.btp` stores original+modified bytes and `btp.check`
pre-verifies the original bytes **byte-exactly**. If any patch's blocks overlap
bytes the R06 CAL edits changed, order (B) will come back `NOT_READY` — that is
the fail-loud system working, not something to work around. Conversely, under
order (A) you must confirm the R06 pipeline's own writes don't land inside
patch-modified regions (compare `res.changed_bytes` block ranges against the
CAL edit offsets; remember file offset = `0x200000 +` XDF address).

Procedure:

1. Run `btp.check` for each patch against plain stock — all three should be
   `READY_TO_ACCEPT` (sanity baseline).
2. Apply the three patches sequentially (each `apply` writes a new file; check
   readiness before each). If a later patch is `NOT_READY` on the
   earlier-patched bin, report exactly which blocks conflict — do not force it.
   Try the other patch order only if the conflict is order-dependent.
3. Test both orderings (A) and (B) for the CAL-edit interaction. Prefer the
   order in which every `btp.check` is `READY_TO_ACCEPT` and every CAL edit
   verifies on the final bin. If both work and produce byte-identical output,
   say so; if they differ, explain why and pick the one whose diff is fully
   accounted for.
4. **Open question you must investigate and report (not guess):** how the five
   map slots relate to the base CAL after patching. If the switch patch copies
   base-CAL tables into per-slot storage, the R06 tuning edits may need to be
   present in the base CAL *before* patching to propagate, or may need
   per-slot writes afterward. Inspect the slot tables in the patched bin (the
   BinToolz XDF exposes `Map Slot 1–5` categories) and compare slot values
   against the base tables to establish what the patch actually did. Write the
   finding into the REV_LOG and, if slot values do NOT inherit the R06 edits,
   STOP and surface that to Sam before inventing a propagation scheme.

## XDF usage

- R06 CAL-edit pipeline: keep using `Code/xdf/SC8S50.V1.0.xdf` exactly as R06
  does.
- Anything on the patched bin (TC flags, slot inspection, sanity checks): use
  **`BinToolz-main/definitions/S50 Switch Patch.29.33.V2.xdf`**. The curated
  `SC8S50_switchpatch29.33_v1.005/6.xdf` files do NOT load under `simoscal`
  (reused uniqueids) — do not try them.

## TC flag writes

From `knowledge/sc8s50-switchpatch-xdf.md` (verified against both switch-patch
XDFs on 2026-07-11). All ten are 8-bit scalars, 0 = off / 1 = on, identity
MATH, no A2L symbols (patch-added). XDF addresses; file offset =
`0x200000 +` address. In the BinToolz XDF each table's `uniqueid` equals its
address — fetch with `cal.get(<uniqueid int>)`.

| Table            | Slot 1    | Slot 2    | Slot 3    | Slot 4    | Slot 5    |
|------------------|-----------|-----------|-----------|-----------|-----------|
| `Enable SL TC`   | `0x7D83F` | `0x7D840` | `0x7D841` | `0x7D842` | `0x7D843` |
| `Disable OEM TC` | `0x7D83A` | `0x7D83B` | `0x7D83C` | `0x7D83D` | `0x7D83E` |

- **Default decision: set both flags to `1` on all five slots**, so TC behavior
  is uniform regardless of which slot is selected from the stalk. Record this
  as an explicit, easily-reversed decision in the report and REV_LOG so Sam
  can veto it at the review gate (e.g. he may want one slot left with OEM TC
  intact as a "safe" map).
- Confirm the stock-patched values before writing (expected `0`); report
  old→new for every flag byte.
- **Do NOT tune the TC behavior tables** (TC category `0xF8`: `Slip target
  straight`, PID weights, `Slip ignition weight` / `Slip WG weight`, `SCC
  Threshold`/`SCC duration`, etc.). Instead, dump their as-patched values into
  the report (a table or PNGs) so Sam can review the defaults before flashing.
  Changing them is a future revision informed by logs.

## Checksums

- `btp.apply` leaves **`CAL_CRC` stale** (a `.btp` carries no corrected CAL
  CRC) and `ECM3` clean; CAL edits also dirty `CAL_CRC`. The final save must
  correct checksums (`correct_checksums=True` on the last `cal.save`, or an
  equivalent final step) so the shipped bin verifies CLEAN on both `CAL_CRC`
  and `ECM3`. Verify by re-opening the saved bin.
- ASW/code-block checksums are **not verifiable in `simoscal`** — the patches
  modify ASW, and SimosTools computes block checksums at full-flash time.
  State this explicitly in the report rather than implying full coverage.
- **A patched bin requires a FULL flash, not CAL-only.** Put this in bold at
  the top of `report.md` and in the REV_LOG entry — flashing this CAL-only is
  a wrong-flash hazard.

## Verification (all mandatory before calling it done)

1. Each `btp.check` readiness result and each `apply`'s `confined` = True,
   with `format_change_report` output saved into the run folder.
2. `btp.switch_patch_sanity` passes on the final bin.
3. **Full-bin byte diff, final R07 bin vs a freshly-generated R06 bin:** every
   changed byte must be accounted for by exactly (a) the three patches'
   declared blocks, (b) the ten TC flag bytes `0x27D83A`–`0x27D843` (file
   offsets), and (c) the stored-checksum bytes (`CAL_CRC` at file `0x200304`,
   ECM3 stored value). Unexplained bytes = STOP and investigate.
4. Re-open the saved bin with the BinToolz XDF and assert all ten TC flags
   decode to `1`, and (per the slot-inheritance investigation) that the R06
   calibration values read back correctly wherever they are supposed to live.
5. `cal.unique_tables()` value-compare against the R06 bin for the CAL region
   covered by `SC8S50.V1.0.xdf` — expect zero table-value differences from
   R06's calibration (the patches and flags live outside those tables); any
   difference must be explained.
6. Run the `Code` test suite (`./.venv/bin/python -m pytest tests -q`) if you
   touched any library code; do not modify library behavior unless the task
   forces it, and document it if so.

## Safety rails (non-negotiable)

- Never flash; never present the bin as flash-ready without the review gate.
  The deliverable ends at: verified bin + report + PNGs + REV_LOG entry, and
  Sam reviews before flashing.
- Never modify `Code/bin/5G0906259L__0002.bin` (recovery image) or anything
  under `BinToolz-main/` (vendored, license forbids derivation — the adapter
  wraps it at runtime).
- Every intermediate write goes to the R07 run output folder, not over an
  input file (`btp.apply`/`remove` already enforce copy-on-write — keep it
  that way).
- Fail loud: a `NOT_READY`, a non-confined diff, an unexplained byte, or a
  slot-inheritance surprise is a finding to report, never something to patch
  around silently.
- Name every table as `` `ID` — plain-English description`` everywhere
  (script comments, report, REV_LOG). The TC flags have no A2L symbols — use
  their XDF titles plus addresses and say the symbol is patch-added.

## Report to Sam (in `report.md` + the REV_LOG entry)

- The FULL-FLASH-REQUIRED banner.
- Patch order chosen and why; the slot-inheritance finding.
- All ten TC flag old→new values and the all-five-slots decision (flagged for
  veto).
- The TC behavior-table defaults dump (for pre-flash review).
- Checksum states: `CAL_CRC` corrected+CLEAN, `ECM3` CLEAN, ASW blocks
  not-verifiable-here.
- A reminder that Mode3E/HSL logging needs an HSL PID list imported in the
  SimosTools app (see `PIDs/` and `knowledge/simostools-app-guide.md`), and
  that gear indexing in logs depends on the PID list (see `CLAUDE.md`).
