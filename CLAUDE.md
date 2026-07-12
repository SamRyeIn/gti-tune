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
4. The active tune's `REV_LOG.md` (e.g. `Tunes/TuningBasicsGuide/REV_LOG.md`)
   and the latest `Logs/<Tune>_R<rev>/log_review.md` — current tune state.

## Folder structure

Two kinds of folders: **human drop zones** (Sam puts files there; Claude reads
them) and **Claude-maintained** (Claude writes/updates; human reviews).

| Folder             | Role                            | Contents                                                           |
|--------------------|---------------------------------|--------------------------------------------------------------------|
| `Code/`            | Claude-maintained               | The `simoscal` library (its own git repo) — see notes below        |
| `Code/bin/`        | Human drop zone                 | Known-good stock bin `5G0906259L__0002.bin` — the recovery image   |
| `Code/xdf/`        | Human drop zone                 | TunerPro XDF definitions; primary is `SC8S50.V1.0.xdf`             |
| `Tunes/`           | Claude-maintained               | Tune projects: revision scripts, `REV_LOG.md`, run outputs         |
| `Logs/`            | Human drop → Claude-analyzed    | SimosTools datalog CSVs per flashed revision + `log_review.md`     |
| `PIDs/`            | Human drop zone                 | SimosTools logging-list CSVs (PID definitions) + PID List Editor   |
| `Troubleshooting/` | Human drop → Claude-analyzed    | Check-engine / fault info Sam drops in (codes, notes) by topic     |
| `Docs/`            | Mixed                           | Human: source `.docx` guides; Claude: `plans/`, `brainstorms/`     |
| `knowledge/`       | Claude-maintained               | The wiki: ingested reference notes + `media/<note>/` screenshots   |
| `References/`      | Human drop zone                 | External material: Funktionsrahmen PDF, Cobb links, example logs   |
| `BinToolz-main/`   | Vendored third-party            | BinToolz tool + `.btp` patches — reference only, do not edit       |
| `index.md`         | Claude-maintained               | Obsidian wiki home page (`.obsidian/` is the vault config)         |

Notes:

- The project root is a git repository (private remote `gti-tune`) holding the
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
- A `Tunes/<Tune>/` project holds revisioned `TUNE_<Tune>_R<rev>.py` scripts,
  `REV_LOG.md`, and `<Tune>_out/R<rev>_<timestamp>/` run outputs (saved bin,
  `report.md`, `compare/` PNGs). `Tunes/TuningBasicsGuide/Test/` holds
  other-model comparison runs — reference only, not part of the lineage.
- A `Logs/<Tune>_R<rev>/` folder holds the raw `simostools-*.csv` logs Sam
  drops in, a `*.bin.txt` record of what was flashed, and Claude-written
  analysis: `log_review.md` (living review doc), plot scripts, `plots/`.
- Use `PIDs/` CSVs to interpret log channel names, units, and scaling.

## The tuning loop: revise → flash → log → review → iterate

Tuning is iterative, and each pass through the loop looks like this:

1. **Revise** — Claude writes the next tune revision as a new script
   `Tunes/<Tune>/TUNE_<Tune>_R<NN>.py` (revision-by-separate-file pattern: new
   file per revision, cumulative header history, `REV_LOG.md` entry — per the
   global revision-tracking instructions). Running it produces a timestamped
   output folder `<Tune>_out/R<NN>_<timestamp>/` containing the saved `.bin`,
   `report.md`, and before/after `compare/` PNGs.
2. **Verify** — prove the revision changed only the intended tables
   (checksums CLEAN, `cal.unique_tables()` value-compare against the previous
   revision's bin; see the `tune-bin-verification` memory). Human review gate:
   Sam visually reviews the report and PNGs before flashing.
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
