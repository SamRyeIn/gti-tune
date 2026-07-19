# SimosTools Wiki — Index

Home page for the tuning knowledge base. This is a wiki of interlinked `.md` notes covering ECU tuning for a **2017 VW GTI** (box code `5G0906259L_0002`, Simos 18.1/18.6, SC8S50 file structure).

## Knowledge base

Stable reference and how-to material, ingested from `Docs/` (text via pandoc; embedded screenshots extracted to `knowledge/media/<note>/` and captioned inline).

- [[tuning-getting-started]] — Toolchain overview: editor + flasher + logger, obtaining a stock BIN, XDF/XML definition files, TunerPro vs ecuEdit, VW_Flash vs SimosTools, Mode 22 vs high-speed RAM logging. **Start here.**
- [[simostools-app-guide]] 🖼️ *14 figures* — SimosTools Android app walkthrough: logging modes (Mode22/Mode3E/DSG), log triggers, PID CSV import, gauges, full vs CAL flashing, log viewer, DTC/utilities.
- [[ecu-tuning-basics]] 🖼️ *77 figures · 6 transcribed HINT tables (double-entry verified)* — TunerPro tuning SOP: torque request model, TTA/ATT airflow-torque tables, boost control, wastegate flow-factor tuning, timing, lambda/fueling, ethanol, limiter removal, DSG farts, pops & bangs.
- [[sc8s50-switchpatch-xdf]] — Reference note on the curated switch-patch XDF (`SC8S50_switchpatch29.33_v1.005.xdf`): TunerPro 1.80 structure, on-the-fly map switching (5 slots), and patch-added features (Launch Control, TC, NLS).
- [[eqt-s2-baseline-log-review]] — Baseline analysis of the **currently-installed EQT Stage 2 91** tune from a clean WOT 3rd-gear street datalog: peak 28 psi / 409 ft-lb on the IS20, confirmed underdamped boost overshoot, zero knock on 92 octane. Fault-free reference point for a more conservative DIY rewrite.
- [[bintoolz-btp-patching]] — BinToolz `.btp` code review: the format stores original+modified bytes with byte-exact pre-verification; safety procedures and gaps; license blocks porting → **wrap, don't port** decision for future multi-slot (switch patch) work, with open questions.
- [[subagent-boot-test]] — 2026-07-10 experiment: four fresh subagents (Sonnet/Opus × quick/thorough) given a bare "add base timing" prompt to test whether the boot docs transfer project knowledge. All four found the right tables and protected the R04 knock cells; conclusions on why (rationale-style REV_LOGs) and process lessons.
- [[eqt-s2-track-log-p2563]] — On-track Pacific Raceways session on the same tune: catches the **[[P2563]] mechanism live** — actuator pinned at 100% while boost stays 2–3 psi under target for ~40 s cumulative. Shows the root cause is a turbo/exhaust-heat target-vs-capability gap (not IAT/intercooler), plus a mild cyl-1 knock event and oil/EGT thermal limits.

## Projects

Active, time-bound work.

- [[diy-conservative-track-tune]] *(not yet written)* — Goal: a slightly more conservative version of the EQT S2 tune for longevity + track; softer boost target/ramp, IAT-based taper to kill [[P2563]]. Baseline captured in [[eqt-s2-baseline-log-review]].

## This car — quick facts

| | |
|---|---|
| Vehicle | 2017 VW GTI |
| Transmission | DQ250 DSG (dual-clutch |)
| Box code | `5G0906259L_0002` |
| ECU | Simos 18.1 / 18.6 |
| File structure | SC8S50 ("S50") |
| Stock BIN | `bin/5G0906259L__0002.bin` |
| XDF (definition) | `xdf/SC8S50.V1.0.xdf`, `xdf/SC8S50.ALL.xdf`, `xdf/SC8S50_switchpatch29.33_v1.005.xdf` |

## Repo layout

Full folder-by-folder map (with human-drop-zone vs Claude-maintained roles) in `CLAUDE.md`. Summary:

- `Code/` — the `simoscal` Python library (its own git repo). Includes `Code/bin/` (stock ECU binary — the recovery image) and `Code/xdf/` (TunerPro definition files; **must match the BIN's file structure, SC8S50**).
- `Tunes/` — tune projects: revisioned `TUNE_*_R<rev>.py` scripts, `REV_LOG.md`, timestamped run outputs.
- `Logs/` — SimosTools datalogs, one folder per flashed revision, each with a `log_review.md`. The `simoscal.analysis` battery (`python -m simoscal.analysis Logs/<Tune>_R<NN>`) writes a read-only, findings-only `analysis_findings.{json,md}` + evidence plots + coverage maps into the folder that Claude reads to author `log_review.md` — see `Code/README.md` § Log analysis battery.
- `PIDs/` — SimosTools logging-list CSVs (PID definitions) + PID List Editor.
- `Troubleshooting/` — human-dropped check-engine / fault material (codes, notes), one subfolder per topic (e.g. `CheckEngine/`); Claude analyzes what lands here.
- `Docs/` — original source documents (`.docx`), plus `plans/` and `brainstorms/`.
- `knowledge/` — ingested reference notes (this wiki).
- `knowledge/media/<note>/` — screenshots extracted from the source `.docx` files, one folder per note, referenced inline by that note.
- `References/` — external reference material (Funktionsrahmen PDF, Cobb links, example logs).
- `BinToolz-main/` — vendored third-party BinToolz tool + patches (reference only).

## Unresolved topics

Wikilinks referenced across notes that don't have their own page yet — candidates to write:
`[[Simos 18.1]]` · `[[Simos 18.10]]` · `[[VW_Flash]]` · `[[SimosTools]]` · `[[TunerPro]]` · `[[ecuEdit]]` · `[[Macchina A0]]` · `[[XDF]]` · `[[Diggs]]` · `[[Exley]]` · `[[P2563]]` · `[[HPFP]]` · `[[diy-conservative-track-tune]]`
