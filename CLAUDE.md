# SimosTools — project instructions

## What this project is

Programmatic ECU tuning for a **2017 VW GTI DSG** (box code `5G0906259L_0002`,
Simos 18.1/18.6, SC8S50 file structure). The Python library `simoscal`
(`Code/simoscal/`) parses a TunerPro XDF, edits tables in a Simos18 `.bin` in
physical units, and writes a minimal-diff, checksum-verified `.bin` — replacing
manual TunerPro GUI editing with 100%-traceable code. Flashing is done by the
human with the **SimosTools Android app**; the library NEVER flashes.

Boot reading order for a fresh session, before doing tuning work:

1. This file (loaded automatically) + auto-memory (`MEMORY.md` index).
2. `index.md` — wiki home: car quick-facts, knowledge-base note index.
3. `Code/README.md` — the `simoscal` API, workflow diagram, safety model.
   `Code/code_review.md` is the living code-review log for the `simoscal`
   library — check its findings index before trusting or extending reviewed
   code, and append new reviews there (see its own "How to use this file").
4. `Tunes/REV_LOG.md` — the single revision lineage across all tune projects —
   and the latest `Logs/<Tune>_R<rev>/log_review.md` — current tune state.
5. `Tunes/README_NEXT_STEPS.md` — the pre-work idea queue for upcoming
   revisions (what to change next, before it's scripted).

## Folder structure

Two kinds of folders: **human drop zones** (Sam puts files there; Claude reads
them) and **Claude-maintained** (Claude writes/updates; human reviews).

| Folder             | Role                         | Contents                                                              |
|--------------------|------------------------------|-----------------------------------------------------------------------|
| `Code/`            | Claude-maintained            | The `simoscal` library (its own git repo) — see notes below           |
| `Code/bin/`        | Human drop zone              | Known-good stock bin `5G0906259L__0002.bin` — the recovery image      |
| `Code/xdf/`        | Human drop zone              | TunerPro XDF definitions; primary is `SC8S50.V1.0.xdf`                |
| `Tunes/`           | Claude-maintained            | `REV_LOG.md` + `README_NEXT_STEPS.md` (shared lineage), tune projects |
| `Logs/`            | Human drop → Claude-analyzed | SimosTools datalog CSVs per flashed revision + `log_review.md`        |
| `PIDs/`            | Human drop zone              | SimosTools logging-list CSVs (PID definitions) + PID List Editor      |
| `Troubleshooting/` | Human drop → Claude-analyzed | Check-engine / fault info Sam drops in (codes, notes) by topic        |
| `Docs/`            | Mixed                        | Human: `.docx` guides (untracked); Claude: `plans/`, `brainstorms/`   |
| `knowledge/`       | Claude-maintained            | The wiki: ingested reference notes + `media/<note>/` screenshots      |
| `References/`      | Human drop zone              | External material: Funktionsrahmen PDF, Cobb links, example logs      |
| `BinToolz-main/`   | Vendored third-party         | BinToolz tool + `.btp` patches — reference only, do not edit          |
| `index.md`         | Claude-maintained            | Obsidian wiki home page (`.obsidian/` is the vault config)            |

Notes:

- The project root is a git repository (public remote `gti-tune`) holding the
  car-specific tuning work. `Code/` is a separate, nested-but-independent repo
  (`simoscal` library, remote `SamRyeIn/simoscal`) and is gitignored by the
  root repo, as are third-party material (`BinToolz-main/`, `References/`),
  generated `*_out/` run outputs, and `*.bin` files.
- Active project/work notes, when needed, live in `knowledge/` (there is no
  separate `projects/` folder).
- Hidden config folders: `.obsidian/` (Obsidian vault settings) and `.claude/`
  (Claude Code project settings). Leave both alone unless asked.
- `Code/` subfolders: `simoscal/` library source, `tests/`, `demos/`, `bin/`
  stock bin, `xdf/` definitions, `oracles/` captured TunerPro exports (test
  fixtures). XDFs must match the bin's SC8S50 file structure.
- `Tunes/REV_LOG.md` and `Tunes/README_NEXT_STEPS.md` live at the `Tunes/` root
  and track the **single, continuous revision lineage across all tune
  projects** — not per-project files. A `Tunes/<Tune>/` project folder holds
  just the revisioned `TUNE_<Tune>_R<rev>.py` scripts and
  `<Tune>_out/R<rev>_<timestamp>/` run outputs (saved bin, `report.md`,
  `compare/` PNGs). R00–R15 are `TuningBasicsGuide`; R16 onward is `MainTune`
  (bin names dropped the `CB_HSL_SP2933_..._BasicsGuide_` prefix in favor of
  `Patched_259L_R<NN>.bin`) — see `Tunes/REV_LOG.md` for the split rationale.
  `Tunes/TuningBasicsGuide/Test/` holds other-model comparison runs —
  reference only, not part of the lineage.
- A `Logs/<Tune>_R<rev>/` folder holds the raw `simostools-*.csv` logs Sam
  drops in, a `*.bin.txt` record of what was flashed, and Claude-written
  analysis: `log_review.md` (living review doc), plot scripts, `plots/`.
- Use `PIDs/` CSVs to interpret log channel names, units, and scaling.

## The tuning loop: revise → flash → log → review → iterate

Tuning is iterative, and each pass through the loop looks like this:

1. **Revise** — write the next tune revision as a new script
   `Tunes/<Tune>/TUNE_<Tune>_R<NN>.py` (revision-by-separate-file pattern: new
   file per revision, cumulative header history, `REV_LOG.md` entry — per the
   global revision-tracking instructions). Running it produces a timestamped
   output folder `<Tune>_out/R<NN>_<timestamp>/` containing the saved `.bin`,
   `report.md`, and before/after `compare/` PNGs.

   **From R13 on, revisions are written in the `simoscal.tune` API**: copy the
   previous revision, edit the domain calls, run it. A revision is one flat
   self-contained script — it NEVER imports from another revision script (R00–R12
   did, and are frozen history). Start from
   `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R13.py` as the template and
   `Code/docs/authoring-a-revision.md` as the guide. Sam authors these too, so
   keep them readable: physical units, an `intent=` on every call, and the
   calibration's values as named constants at the top.
2. **Verify** — prove the revision changed only the intended tables. `build()`
   now owns this: checksums corrected + independently verified, every journaled
   table read back off the saved file, and a byte-level audit against the
   previous revision's bin whose allowance is derived from the edit journal, so
   an undeclared change fails the build rather than passing quietly. Pass
   `reference_bin=` or that last gate does not run. (Pre-R13 revisions did this
   by hand — see the `tune-bin-verification` memory.) Then build the revision's
   **change-summary plot** — required for every revision, see the section below.
   Human review gate: Sam visually reviews the report, the change-summary plot
   and the `compare/` PNGs before flashing.
3. **Flash** — human step. Sam flashes the bin to the car with the SimosTools
   Android app. Claude cannot do this.
4. **Log** — human step. Sam drives (e.g. 3rd-gear WOT pulls), logs with
   SimosTools, and drops the CSVs into a new `Logs/<Tune>_R<NN>/` folder.
5. **Review** — Claude analyzes the logs. First run the analysis battery
   (`python -m simoscal.analysis Logs/<Tune>_R<NN>` or `analyze_folder()`), which
   writes `analysis_findings.{json,md}`, evidence plots, and per-table coverage
   maps into the folder — an identical, enumerable, deterministic set of checks
   with an explicit SKIPPED list. Then Claude reads that output and **writes
   `log_review.md`** (findings ranked High/Medium/Low with evidence plots),
   checking knock, boost tracking, lambda, fuel pressure, turbo/temps. The tool
   is findings-only — it never writes `log_review.md` and never proposes a
   calibration change; authorship and judgment stay with Claude. Check the
   gear-indexing rule below and the PID list before interpreting channels.
6. Findings feed the next revision → back to step 1.

Every tune revision is "a starting point, not a finished calibration" — never
declare a tune done from the bin alone; only logs validate it.

## Every revision ships a change-summary plot

**Required for every tune revision unless Sam says otherwise.** One PNG that
shows everything the revision changes, on one page, so the pre-flash review is a
single glance rather than a hunt through a dozen `compare/` PNGs and a claim
about the tables that produce no PNG *because* they did not move.

- **Script**: `Tunes/<Tune>/plot_r<NN>_changes.py`, alongside the revision
  script. **Output**: `<Tune>_out/R<NN>_changes_summary.png`. Written in the same
  Python/matplotlib tooling as the rest of the project — see
  `Tunes/MainTune/plot_r23_changes.py` as the reference implementation. The PNG
  lands under the gitignored `*_out/` tree like every other run artifact, so the
  script is the record and the plot is regenerated on demand.
- **Read every number off the two bins** — the previously flashed bin and the
  new one — via `CalFile`, never retyped from the revision script. That makes
  the plot an independent check rather than a restatement: if the figure and the
  script disagree, the figure is right. Say so in the module docstring.

What it must contain:

1. **One panel per domain the revision touches** (fuelling, timing, boost, …),
   each drawing the previous revision against the new one on the row or axis the
   engine actually runs on. Say which row in the panel title, e.g. "1400 mg/stk
   row", because a grid plotted on the wrong row can look unchanged.
2. **The negative.** Draw the tables the revision claims it did *not* change,
   both bins overplotted (thick for the old, dashed for the new), and put the
   worst difference in the panel title. An unchanged table generates no
   `compare/` PNG, so without this there is nothing in the review output that
   makes "boost is untouched" checkable.
3. **A slot-effect matrix whenever a change routes through a shared table.**
   Writing a shared grid and taking it back off some slots with per-slot
   modifiers means no single table shows what any one slot ends up running. A
   small table — one row per map slot, one column per domain — is the only place
   that appears. This is where a reviewer catches "slots 4 and 5 got the
   enrichment too".
4. **Before → after values annotated on the breakpoints that moved**, in physical
   units. Group runs of identical annotations (`0.800 → 0.780, 5504-7008 rpm`)
   rather than writing the same string over each column.
5. **A title carrying the provenance and the verdict**: both bin filenames, the
   number of tables that moved, the byte count, and the audit result.
6. A **reference calibration** where one exists and is relevant (EQT Stage 2,
   the stock bin), plotted as context so the size of the step is legible against
   something other than itself.

Conventions: bold axis labels, `grid on` plus minor gridlines on every axes,
`matplotlib.use("Agg")`, shading to mark the breakpoints that moved, and a
figure title stating what the reviewer is being asked to confirm.

## Safety — non-negotiable

A wrong byte can brick the ECU or damage the engine (overboost, lean lambda,
knock). Full safety model in `Code/README.md` § Safety. Core rules:

- Fail loud, never silently alter or clamp values; keep every modified bin
  checksum-verifiable before flashing.
- Never flash, and never skip the human review gate before Sam flashes.
- Keep the stock bin `Code/bin/5G0906259L__0002.bin` untouched as recovery.
- `C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint stores **kg/stk**
  despite the XDF's mg/stk label: write `0.002` for a 2000 mg/stk ceiling,
  never `2000` (see the `air-cyl-sp-max-kg-not-mg` memory).
- `C_PRS_IM_SP_MAX` / `C_PRS_IM_SP_LIM` — Maximum / limit requested
  intake-manifold pressure setpoint are **float32**, and the max declared for
  them in the XDF is not a real ECU ceiling (stock already exceeds it) — never
  treat an XDF-declared max as a guard on these tables. Overboost-fault routing
  lives in `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference
  threshold (int16), **not** `C_PRS_IM_SP_LIM`; the R05 recipe mis-routed it
  once. Detail and exact figures: `knowledge/ecu-tuning-basics.md`.

## Always name tables by ID + plain-English description

Whenever referring to an ECU table, calibration, or parameter — in prose, plan
items, reports, commit messages, code comments, REV_LOG entries, anywhere —
ALWAYS give **both** the parameter ID and its plain-English description, not one
or the other.

Format: `` `ID`  — Description ``

Examples:
- `ID_PV_AV_FL` — Pedal value threshold for the determination of LV_FL_RAW
- `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold pressure setpoint
- `IP_LAMB_BAS_HPDI[1]` — Basic lambda setpoint grid, HPDI (direct injection)

The description comes from the XDF `title` (or the tuning guide when clearer). If
the plain-English meaning of an ID is genuinely unknown, say so explicitly rather
than dropping the description.

## Call them map slots — never "arms"

A selectable map on the switch patch is a **map slot** (slot 1 … slot 5). Say
"slot 4", "the octane slots", "the aggressive slot". Do **not** call them "arms",
"the reduced-boost arm", "the control arm", or "test arms" — not in prose, plots,
reports, commit messages, REV_LOG entries, code comments, or chat.

`Tunes/REV_LOG.md` and `Tunes/README_NEXT_STEPS.md` were swept on 2026-09-01.
`Tunes/MainTune/TUNE_MainTune_R22.py` still says "arm" throughout: it is a frozen
revision script that produced a shipped bin, so its wording is left alone for
traceability. Do not copy it forward — R23 onward says "slot".

## Log gear indexing depends on the channel header

The gear offset in a SimosTools log is determined by the CSV column header:

- **`Gear ()`** — zero-indexed. The channel starts counting at zero, so the real
  gear is `logged + 1` (logged `0` = 1st gear, logged `2` = 3rd gear, etc.).
  Always apply this +1 offset.
- **`Gear (gear)`** — actual gear. No offset; the logged value is the real gear
  (logged `3` = 3rd gear).

This was confirmed by matching the same physical gear across two logs (drive
ratio ≈ 45.9 rpm/km/h): logged `2` under `Gear ()` vs `3` under `Gear (gear)` —
a clean +1 offset. Always check the header before interpreting or reporting gear.

## Trim to in-gear samples before quoting Calc HP or Calc TQ

SimosTools' `Calc HP (hp)` and `Calc TQ (nm)` are acceleration-derived **and**
gear-ratio-weighted. The DSG's gear channel flips to the next ratio several
samples *before* the shift actually pulls the engine down, so those samples get
computed against the wrong ratio and read about **50 hp high** — a step at the
very top of every pull that ends in an upshift.

Measured on `Logs/BasicsGuide_R14/simostools-2026_08_10-12_02_12.csv`: at the
3 → 4 flip `Calc HP` jumps 292 → 343 hp while `Accel. Long` is *falling* and rpm
is still climbing. The R14 3rd-gear peak is **347 hp raw, 298 hp trimmed**, and
every revision whose pull window caught a flip was inflated the same way.

So before peaking, curving, or plotting either channel over a pull, drop the rows
where the gear channel is not the pull's attributed gear
(`round(gear) == pull.gear`). There is no shared implementation of this trim —
`simoscal.analysis` does not do it, so any script quoting either channel must do
it itself. The old rule of thumb that a 2nd-gear pull
reads high was this artifact rather than gearing — trimmed, 2nd and 3rd agree to
within ~4 hp on the same session.
