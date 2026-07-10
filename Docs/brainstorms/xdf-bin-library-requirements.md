# Requirements — Python XDF/BIN Tuning Library

**Date:** 2026-07-05
**Topic:** Read `.xdf` + `.bin`, edit calibration tables, write a flashable `.bin` (Python)
**Status:** Requirements captured — ready for `/ce-plan`
**Related notes:** [[tuning-getting-started]], [[ecu-tuning-basics]], [[simostools-app-guide]]

## Problem

Tuning the 2017 GTI (box code `5G0906259L_0002`, Simos 18.1/18.6, **SC8S50** structure) is done by hand in TunerPro: open a 4 MB `.bin`, load the matching `.xdf`, and edit tables cell-by-cell. This is manual, non-repeatable, and can't be driven by data. There is no programmatic way to read a table by name, transform it, and produce a modified `.bin` — which blocks any automation of the tuning workflow described in [[ecu-tuning-basics]].

## Goals & Success Criteria

- A Python **library/package** that loads an SC8S50 `.xdf`, maps its tables against a 4 MB `.bin`, and exposes tables for reading and editing in **physical units** (%, °, kPa, mg/stk).
- Writing produces a modified 4 MB `.bin` that is **byte-identical to the input except for the cells actually edited**.
- Round-trip fidelity: load → write-unchanged → output equals input byte-for-byte.
- Values read through the library **match TunerPro** for a sampled set of tables (spot-check correctness).
- Output `.bin` flashes successfully via **SimosTools or VW_Flash** (which handle CAN flashing and checksum correction).
- Foundation is structured so later phases (**export**, **visualization**, **datalog-driven auto-tuning**) can build on it without redesign.

## Scope

### In scope (Phase 1 — the substrate)
- Parse TunerPro **XDF** format: `XDFTABLE`, `XDFCONSTANT`, `XDFAXIS` (x/y/z), `EMBEDDEDDATA` (address, element bit-size, row/col counts, strides, type flags), `MATH` scaling equations, categories, `BASEOFFSET`.
- Handle the `BASEOFFSET` (`0x200000`) address→file-offset mapping.
- Read tables/axes/constants: raw bytes → apply MATH → real values, with correct signedness, bit width, and row/col strides.
- Look up tables by **A2L symbol name** (the `<description>`, e.g. `C_FAC_POW_PUT_CTL_BOL`) and by human title.
- Edit table values in **physical units**; write back by **inverting the (linear) MATH equation** to raw bytes at the exact offset.
- Emit a modified 4 MB `.bin` with only edited bytes changed.
- **Verify/report** stale checksums as a warning (Checksum category), without recomputing them.
- Object model designed to accept **declarative change-sets** later (symbol → new values / transform), the reproducibility bridge and the emit-target for Phase 2.

### Out of scope (Phase 1)
- **Flashing the ECU.** Output `.bin` is handed to SimosTools / VW_Flash. No CAN/UDS/Macchina A0 code. *(Decided.)*
- **Computing/writing checksums.** Flash tools recompute them. *(Decided.)*
- Editing CBOOT/ASW blocks, bin patching (MPI/SWG/HSL), or FRF→BIN extraction (VW_Flash does this).
- GUI. TunerPro already covers GUI editing.
- **Export** (CSV/spreadsheet) and **visualization** (plots/colormap tables) modules — wanted, but **later phases**; foundation must *support* them, not implement them now.
- Auto-tuning logic (datalog ingestion, correction algorithms) — foundation must *support* it, not implement it.

## Key Flows

1. **Inspect** — load XDF + BIN; list/search tables by category or symbol; print a table's axes + values in real units.
2. **Scripted edit** — load; fetch table by symbol; transform values (set/scale/replace) in physical units; save modified `.bin`; flash externally.
3. **Round-trip check** — load; save unchanged; assert output == input.

## Acceptance Examples

- **AE1** — Load `xdf/SC8S50.V1.0.xdf` + `bin/5G0906259L__0002.bin`; read `C_FAC_POW_PUT_CTL_BOL`; the z-values, units (`%`), and axis labels match TunerPro.
- **AE2** — Save the loaded bin with no edits; output is byte-identical to `bin/5G0906259L__0002.bin`.
- **AE3** — Fetch a boost/limiter table by symbol, set its last row to a target value in physical units, save; only that table's bytes differ from the input, and re-reading returns the set values (within one raw-LSB quantization).
- **AE4** — Editing a value outside the table's XDF min/max raises a warning (and, per policy, is clamped or rejected — see Outstanding Q1).
- **AE5** — On load, every table's MATH equation is asserted to be linear (identity or scale/offset). If an equation is ever encountered that is *not* linear (none exist in `SC8S50.V1.0.xdf` — see MATH note below), it is flagged and that table falls back to raw-byte editing rather than being silently corrupted.

## Key Decisions

- **Flash boundary:** library stops at a flashable `.bin`; flashing handed to SimosTools/VW_Flash. *(Lower risk, avoids reimplementing UDS.)*
- **Checksums:** rely on the flash tool; library only verifies/warns. *(Redundant to recompute; flasher already does.)*
- **Interface:** Python **library/package** (no CLI/GUI in Phase 1). Scripts drive it.
- **End goal:** **phased** — see phase map below; Phase 1 is the scripted read/edit/write substrate everything else builds on.
- **Edit units:** physical/scaled units, not raw bytes. Read applies the linear MATH scale; write inverts it (linear un-scale) and rounds to the nearest raw integer. Raw-byte editing is only a fallback for the (empirically nonexistent) non-linear case.
- **Architecture:** thin faithful XDF↔BIN mapper (Approach A), object model shaped to accept declarative change-sets (Approach B) later; do **not** wrap a general third-party XDF lib (Approach C).
- **Write minimality:** only edited cells change; everything else preserved byte-for-byte.

## MATH Equations — empirical finding

A survey of all **11,736** MATH equations in `SC8S50.V1.0.xdf` found only **two** forms:

- `X` — identity (raw *is* the value): **7,612**
- `((a * X) - b) / (c - (d * X))` — rational: **4,124**, and in every case **d = 0.0**, so the denominator collapses to a constant.

So **every equation is linear** (`phys = (a/c)·X − b/c`), and there are **zero** multi-variable equations. Inversion is therefore a one-line closed form (`X = (phys + b/c)·(c/a)`) — no numeric root-finding, no ambiguity. The only round-trip loss is **quantization** (raw `X` is integer, so writes round to nearest LSB), which is why AE3 allows a one-LSB tolerance. The non-linear/non-invertible handling (AE5) is retained purely as a **defensive guard** for other XDFs (e.g. `SC8S50.ALL.xdf` or a different box code), not a path this file exercises.

## Phase Map

- **Phase 1 — Core substrate (this build):** XDF/BIN parse, read/edit in physical units, write minimal-diff flashable `.bin`, round-trip fidelity. Object model designed to accept change-sets (B) and to be consumed by later modules.
- **Phase 2 — Export module:** export a given list of tables to `.csv` and spreadsheet (`.xlsx`) files — values in physical units, axes as headers/labels.
- **Phase 3 — Visualization module:** render tables as **plots** (surface/line) and **colormap tables** (heatmap-style, TunerPro-like) for inspection and comparison.
- **Phase 4 — Datalog-driven auto-tuning:** ingest SimosTools datalog CSVs; compute table corrections (e.g. wastegate flow-factor from boost error, timing from knock/corrections); emit change-sets → new `.bin`.

*Phase order after Phase 1 is flexible; export/visualization are independent read-only consumers and can come in either order.*

## Deferred / Out of Scope (beyond the phase map)

- Declarative "tune recipe" files encoding the [[ecu-tuning-basics]] SOP steps (bridges Phase 1's change-set design to Phase 4).
- Optional CLI / notebook front-ends over the library.
- In-library checksum computation (only if a use case needs a standalone-valid bin).

## Outstanding Questions

Non-blocking — sensible defaults exist; confirm during planning:

- **Q1 (edit safety):** On out-of-range edits vs. XDF min/max — warn-and-clamp, warn-and-allow, or reject? (Note the [[ecu-tuning-basics]] TunerPro float-bug caution: saving over an upper limit can break certain tables — worth a hard guard on those.)
- **Q2 (canonical XDF):** Default/test against `SC8S50.V1.0.xdf` (3,912 tables, 5.8 MB); still support loading any XDF incl. the 59 MB `.ALL` and the switchpatch variant. Confirm V1.0 as the working default.
- **Q3 (non-linear MATH):** *Resolved for this XDF* — all 11,736 equations in `SC8S50.V1.0.xdf` are linear (see MATH note); inversion is closed-form. Remaining question is only the defensive policy if a *different* XDF ever presents a non-linear equation: flag + raw-byte fallback (planned) vs. numeric inversion.
- **Q4 (auto-tuning inputs):** Which datalog fields/PIDs and which tables are the first auto-tuning target (likely wastegate/boost, per the SOP) — scoped when Phase 4 starts, not now.
