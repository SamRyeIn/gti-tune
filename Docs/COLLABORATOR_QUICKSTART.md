# Welcome to the GTI tuning repos — quick start

Hey! Glad to have you on board. Here's the lay of the land so you can find your
way around without needing to write any Python. There are **two repos**, and
they do very different jobs.

## The two repos at a glance

| Repo        | What it is                                                                | Think of it as...               |
|-------------|---------------------------------------------------------------------------|---------------------------------|
| `gti-tune`  | Everything about **my car specifically** — tunes, datalogs, notes, guides | The tuning binder for the car   |
| `simoscal`  | A Python library that **edits Simos18 bin files** from code               | A scriptable TunerPro           |

`simoscal` lives *inside* the `gti-tune` folder (at `Code/`) but it's its own
separate repo — so if you clone `gti-tune`, you'll want to clone `simoscal`
into its `Code/` folder too:

```
git clone https://github.com/SamRyeIn/gti-tune.git SimosTools
cd SimosTools
git clone https://github.com/SamRyeIn/simoscal.git Code
```

## Heads up: a few things are NOT in git

The `gti-tune` repo deliberately ignores tuned `.bin` files, the `References/`
folder, the vendored `BinToolz-main/` tool, and generated run outputs — so a
fresh clone won't have any *tuned* bins or the timestamped run-output folders
(they're regenerable by re-running the revision scripts).

The good news: the `simoscal` repo **does** include the stock bin
(`Code/bin/5G0906259L__0002.bin`) and all the XDF definition files
(`Code/xdf/`), so once you've cloned both repos you can open and explore the
stock calibration right away. If you want anything from `References/`
(Funktionsrahmen PDF, example logs) or a specific tuned bin, just ask and I'll
send it.

## What is simoscal, in plain English?

You know the TunerPro workflow: open an XDF + bin, click around tables, change
values, save. `simoscal` does exactly that, but from code instead of a GUI:

- **Input:** a TunerPro XDF + a Simos18 bin.
- **You do:** read or change table values *in real physical units* (psi-ish,
  lambda, degrees — whatever the table's units are), from a short Python script.
- **Output:** a new bin where **only the bytes you meant to change are
  different**, plus checksum verification so a stale bin gets caught before it
  ever reaches the flasher.

Why bother? Traceability. Every change is a line of code you can read, diff,
and re-run — no "wait, what did I change in TunerPro three weeks ago?" It can
also export tables to CSV/Excel and render tables as PNG images (3D surfaces
and TunerPro-style heatmaps), including before/after comparison pictures for
every change.

Two things it will **never** do, on purpose:

1. **It never flashes.** Flashing is always a human with the SimosTools
   Android app.
2. **It never silently "fixes" anything.** If a value looks wrong or a
   checksum is stale, it complains loudly instead of quietly clamping or
   correcting. That's a safety feature, not an annoyance.

The full API docs are in `Code/README.md` if you ever get curious about the
Python side, but you can get a lot out of these repos without touching it.

## A tour of gti-tune (the fun repo)

Start with **`index.md`** — it's the wiki home page with quick facts about the
car and links to all the knowledge notes. If you use Obsidian, open the repo
root as a vault and the `[[wikilinks]]` all work.

- **`knowledge/`** — the good stuff. Ingested guides and analysis notes:
  a TunerPro tuning SOP with 77 screenshots (`ecu-tuning-basics`), the
  SimosTools app guide, a baseline review of the EQT Stage 2 tune currently on
  the car, a track-session log analysis that caught a P2563 (underboost)
  mechanism live, and more. Honestly, if you only read one folder, read this
  one.
- **`Tunes/`** — tune projects. Each revision of a tune is its own script
  (`TUNE_<Tune>_R00.py`, `R01`, ...) with a `REV_LOG.md` explaining what
  changed at each revision *and why*. Run outputs (the built bin, a markdown
  report, before/after PNGs of every changed table) land in timestamped
  folders. **The reports and PNGs are readable without any Python** — that's
  where most of the reviewing happens.
- **`Logs/`** — SimosTools datalog CSVs, one folder per flashed revision, each
  with a `log_review.md` analyzing knock, boost tracking, lambda, fuel
  pressure, etc., with plots.
- **`PIDs/`** — the SimosTools logging-list CSVs (what channels get logged and
  how they're scaled).
- **`Docs/`** — original source documents plus plans and brainstorms.
- **`Troubleshooting/`** — drop zone for check-engine codes and fault info.

## How the tuning actually works here (the loop)

Nothing gets declared "done" from the bin alone — only datalogs validate a
tune. Every cycle looks like:

1. **Revise** — a new revision script produces a new bin + report + PNGs.
2. **Review** — verify the bin changed *only* the intended tables, checksums
   clean, then eyeball the report and comparison pictures.
3. **Flash** — human step, SimosTools app.
4. **Log** — go drive (3rd-gear WOT pulls are the standard), log with
   SimosTools, drop the CSVs into `Logs/`.
5. **Review the logs** — findings get written up in `log_review.md` and feed
   the next revision. Back to step 1.

The mantra: *every tune revision is a starting point, not a finished
calibration.*

## Best practices (please read this bit)

You already know the stakes from tuning your own GTI — a bad calibration can
mean overboost, lean lambda, knock, or a bricked ECU. House rules:

- **Never flash a bin that hasn't passed review** — checksums verified clean
  and the changed tables visually confirmed against the report/PNGs.
- **The stock bin `Code/bin/5G0906259L__0002.bin` is the recovery image.**
  Never edit or overwrite it. Ever.
- **New work goes in a new revision script**, never by editing an old one —
  the whole point is that the history stays readable.
- **When naming ECU tables, always give both the ID and what it means in
  English** — e.g. `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold
  pressure setpoint. IDs alone are unreadable; descriptions alone are
  ambiguous.
- **Check gear indexing before reading logs.** Depending on the PID list, the
  logged gear channel can be zero-indexed (logged 2 = 3rd gear) or actual.
  The column header tells you which — `Gear ()` means add 1, `Gear (gear)`
  means take it at face value.
- **One famous gotcha:** the airmass ceiling table `C_M_AIR_CYL_SP_MAX` —
  Maximum allowed airmass setpoint — actually stores **kg/stroke** even though
  the XDF labels it mg/stroke. Writing `2000` there instead of `0.002` doesn't
  set a 2000 mg limit, it multiplies the limit by ~1.4 million. It's the
  canonical example of why we double-check units.
- **Branch and PR for anything non-trivial**, and keep bins out of commits
  (the gitignore already handles this — don't force-add one).

## Where to start

1. Read `index.md`, then `knowledge/tuning-getting-started.md`.
2. Skim `knowledge/ecu-tuning-basics.md` — you'll recognize a lot of it from
   your own tuning, and it's the SOP the scripted recipes are built from.
3. Open `Tunes/REV_LOG.md` and a couple of the run-output reports to see what
   a revision actually looks like end to end.
4. If anything's confusing or you want the bins, just ping me.

Happy to walk through any of it — welcome aboard! 🚗💨
