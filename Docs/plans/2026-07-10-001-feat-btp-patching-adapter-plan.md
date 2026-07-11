# BTP Patching Adapter (BinToolz wrapper) — Implementation Plan

**Date:** 2026-07-10
**Type:** feat
**Origin:** `Docs/brainstorms/2026-07-10-btp-patching-requirements.md`
**Prior art:** `knowledge/bintoolz-btp-patching.md` (code review, license),
`knowledge/sc8s50-switchpatch-xdf.md` (switch-patch XDF structure)

## Summary

Add generic BinToolz `.btp` patch support — check / apply / remove — to the
`simoscal` pipeline as a thin adapter that imports BinToolz's Python modules at
runtime (wrap, don't port), layered with `simoscal`-grade guarantees: fail-loud
identity and file-size guards, post-apply full-bin diff confined to the patch's
declared blocks, round-trip proof, explicit `CAL_CRC`/`ECM3` checksum
reporting, and an XDF sanity load for the switch patch. Finish line is
**offline-verified**; flashing and on-car validation are out of scope (tuning
is paused pending the DSG electrical diagnosis — see
`Troubleshooting/CheckEngine/`).

## Problem Frame

Enabling on-the-fly map switching (5 slots) and other BinToolz features
requires applying `.btp` patches to the bin. The only existing applier is
BinToolz's Windows-oriented GUI; nothing in the pipeline can apply, check, or
remove a patch, verify the result, or report checksum state. Patching must
become as traceable and verifiable as every other bin operation in this
project.

## Requirements

From the origin doc (acceptance examples AE1–AE7):

- **AE1** — check mode is read-only: bin left byte-identical, definitive
  readiness state returned (PATCH_FOUND / READY_TO_ACCEPT / NOT_READY).
- **AE2** — apply confined to declared blocks: full-bin diff shows zero
  changes outside the patch's declared (offset, length) blocks.
- **AE3** — round-trip: apply then remove yields a byte-identical bin.
- **AE4** — identity guards: software-code or file-size mismatch rejected
  loudly; nothing written.
- **AE5** — checksum report: `CAL_CRC`/`ECM3` state reported explicitly
  (clean / stale / not-verifiable), never assumed.
- **AE6** — XDF sanity: patched bin resolves the Map Slot 1–5 / Map Switching
  tables with plausible decoded values; the authoritative XDF is recorded.
- **AE7** — missing dependency fails loud: adapter raises a clear error when
  `BinToolz-main/` is absent; tests skip, not fail.

## Key Technical Decisions

1. **Wrap BinToolz, don't port** (carried from brainstorm; license has no
   derivation grant). `BinToolz-main/` stays untouched and gitignored; the
   adapter imports its modules at runtime and their byte-level logic stays
   authoritative for `.btp` files.
2. **Bypass `Patch.py`; wrap `BTP` + `SimosBIN` directly.** Research finding:
   `Patch.py` (the check/apply/remove orchestration layer) imports PyQt6 at
   module top, references an undefined `self`, and calls its own
   `PatchFunctionCheck` with a missing argument — it is GUI-coupled and not
   safely importable headless. The Qt-free lower layer is sufficient and
   clean: `library/BTP.py` (`BTP.load` / `checkChecksum` / `checkBin` /
   `changeBin`), `library/SimosBIN.py` (`load` / `save` / `hardwareType` /
   `softwareCode`), and `Return.py` (`ReturnType`). The adapter re-implements
   only the thin orchestration (the check → ready/found/not-ready state
   machine and add/remove sequencing), which it must do anyway to add the
   fail-loud guards.
3. **Import shim, not vendoring.** BinToolz modules use flat imports
   (`from Return import ReturnType`, `from library.BTP import ...`), so the
   adapter temporarily prepends `BinToolz-main/source/` to `sys.path` inside a
   guarded loader. The loader takes an explicit BinToolz root parameter with a
   default resolved relative to the `Code/` repo root (`../BinToolz-main`),
   and raises a clear `BinToolzNotFound`-style error naming the expected path
   when absent or when the expected API surface (classes/methods above) is
   missing (AE7).
4. **Never patch in place.** Adapter operates on bytes/copies: input bin path
   is read-only; apply/remove write a new output file. Check mode never
   writes at all (AE1).
5. **Patch stock first, tune on top** (carried from brainstorm). The patched
   stock bin becomes the canonical base; tune revision scripts re-apply on
   top of it. BinToolz's "ignore data" CAL-skip mode is not wrapped.
6. **Post-verification is ours, not BinToolz's.** After every apply/remove
   the adapter re-diffs the entire bin against the input and fails loud if
   any changed byte falls outside the patch's declared blocks (AE2), then
   runs `simoscal.checksum.verify` and reports `CAL_CRC`/`ECM3` state
   explicitly (AE5). BinToolz's block offsets are bin positions (verified in
   `BTP.checkBin`), so declared blocks map directly onto the diff.
7. **File-size mismatch is a hard failure.** BinToolz logs it and continues;
   the adapter rejects before any write (AE4). Same for software-code and
   hardware-type mismatches (BinToolz already fails these; the adapter
   surfaces them as exceptions with both values named, not return codes).
8. **Synthetic `.btp` fixtures for unit tests.** The format is documented
   (100-byte header: version string, software code, block count, CRC32,
   file size; per block: 8-byte offset/length header + original bytes +
   modified bytes). Tests author tiny synthetic patch files against synthetic
   bins so guard and round-trip logic is testable without the real 4 MB bin;
   acceptance tests use the real files and skip cleanly when absent
   (existing `conftest.py` convention).

## High-Level Design

```
caller (demo / tune script / tests)
        │
        ▼
Code/simoscal/btp.py  (new adapter)
  ├─ loader: locate BinToolz-main/source, sys.path shim, API-surface check (AE7)
  ├─ check(bin, patch)  → PatchCheckResult (read-only; AE1, AE4)
  ├─ apply(bin, patch, out) ─┐
  ├─ remove(bin, patch, out) ┤→ BinToolz BTP.changeBin on a copy
  │                          └→ post-verify: full-bin diff vs declared
  │                             blocks (AE2/AE3) + checksum report (AE5)
  └─ report: human-readable apply/remove report (review gate)
        │                         │
        ▼                         ▼
BinToolz-main/source/       Code/simoscal/checksum.py
  library/BTP.py              verify() → CAL_CRC + ECM3 state
  library/SimosBIN.py
  Return.py
```

## Implementation Units

### U1. Offline investigation: patch anatomy, checksums, XDF match

**Goal** — answer the two blocking questions from the brainstorm, offline, on
bin copies, before the adapter's report semantics are frozen:

1. Do the `.btp`'s stored modified bytes already include corrected block
   checksums for the ASW regions it touches (i.e., is a patched bin
   internally consistent as stored), or is correction deferred to
   SimosTools/VW_Flash at full-flash time? Determines what the AE5 checksum
   report must cover and what "flash-ready" means.
2. Which XDF is authoritative for the patched bin —
   `Code/xdf/SC8S50_switchpatch29.33_v1.005.xdf` / `..._v1.006.xdf` (curated)
   or `BinToolz-main/definitions/S50 Switch Patch.29.33.V2.xdf`?

**Requirements** — feeds AE5 and AE6; de-risks decisions 6–7.
**Dependencies** — none (first unit; uses BinToolz directly via a throwaway
sys.path shim, no `simoscal` changes yet).
**Files** — a scratch investigation script (not committed to `simoscal`);
findings recorded by updating `knowledge/bintoolz-btp-patching.md` (resolve
its "Open questions" 1–2) and, if the XDF comparison warrants it,
`knowledge/sc8s50-switchpatch-xdf.md`.
**Approach** — parse `BinToolz-main/patches/SL PATCH.29.33 - S50.btp`
headers/blocks; map each declared block onto the SC8S50 block layout
(`SimosBIN.py` hardware table; block 4 = CAL); apply the patch to a **copy**
of `Code/bin/5G0906259L__0002.bin`; run `simoscal.checksum.verify` on the
result; characterize whether patched ASW regions carry self-consistent
checksums (compare against VW_Flash checksum knowledge already reimplemented
in `checksum.py`); load the patched copy against each candidate XDF and
compare table resolution/decoding for the Map Slot / Map Switching groups.
**Test scenarios** — none (investigation unit; its outputs are recorded
findings). Test expectation: none — knowledge-gathering, no shipped behavior.
**Verification** — both questions have recorded, evidence-backed answers in
the knowledge notes; the patched-copy artifacts stay out of git (`*.bin`
already ignored).

### U2. Adapter core: loader, models, read-only check

**Goal** — `simoscal.btp` module exists with the guarded BinToolz loader and
a read-only `check` operation.
**Requirements** — AE1, AE4 (identity guards on check), AE7.
**Dependencies** — U1 (report semantics informed by findings).
**Files** — create `Code/simoscal/btp.py`; touch `Code/simoscal/__init__.py`
only if the package re-exports publicly (match existing convention).
**Approach** — decisions 2–4: loader with explicit BinToolz root parameter,
default `../BinToolz-main` relative to the `Code/` repo root, sys.path shim
scoped as narrowly as practical, API-surface presence check with a clear
error naming the missing piece. Dataclasses for patch identity
(version string, software code, block count, declared blocks, expected file
size) and check results (readiness state + identity info). `check` never
writes: it loads the patch (CRC32 self-check via `BTP.load`), validates
hardware type / software code / file size (hard-fail on any mismatch), and
reproduces the check state machine (already-patched → PATCH_FOUND; originals
match → READY_TO_ACCEPT; else NOT_READY).
**Test scenarios** —
- Happy path: synthetic patch + matching synthetic bin → READY_TO_ACCEPT with
  correct identity info; input file bytes unchanged after check (AE1).
- Happy path: synthetic already-patched bin → PATCH_FOUND.
- Edge: bin matching neither originals nor modifieds → NOT_READY.
- Error: patch file with corrupted CRC32 → loud failure naming the checksum
  mismatch.
- Error: software-code mismatch → loud failure naming both codes; file-size
  mismatch → loud failure naming both sizes (AE4).
- Error: BinToolz root absent or missing expected classes → clear
  dependency error (AE7).
**Verification** — check runs headless on the Mac against the real patch and
stock bin (READY_TO_ACCEPT) and against a nonexistent BinToolz path (clean
failure); no PyQt6 import anywhere in the path.

### U3. Apply / remove with post-verification and checksum report

**Goal** — `apply` and `remove` produce verified output bins plus a
machine-usable result object and human-readable report.
**Requirements** — AE2, AE3, AE4 (guards on write paths), AE5.
**Dependencies** — U2.
**Files** — modify `Code/simoscal/btp.py`.
**Approach** — decisions 4–7: operate on a copy, run the U2 check first and
refuse to write unless the state is the expected one (apply requires
READY_TO_ACCEPT; remove requires PATCH_FOUND), call `BTP.changeBin` with the
CAL block included (no ignore-data mode), then post-verify: byte-diff output
vs input and assert every changed byte lies inside a declared block (note:
BinToolz's gap-fill merges nearby changes into blocks, so declared blocks may
legitimately contain unchanged bytes — the invariant is one-directional);
run `simoscal.checksum.verify` and embed the `CAL_CRC`/`ECM3` reports plus
the U1-informed characterization of non-CAL block checksum state
(clean / stale / not-verifiable — stated, never assumed). Render a report
(markdown, in the style of existing SOP-recipe reports) for the human review
gate.
**Test scenarios** —
- Happy path: apply synthetic patch → output differs from input only inside
  declared blocks; result object lists per-block outcomes (AE2).
- Happy path: apply then remove → output byte-identical to original input
  (AE3).
- Edge: apply to an already-patched bin → refused loudly (state is
  PATCH_FOUND, not READY_TO_ACCEPT); remove from an unpatched bin →
  refused loudly.
- Error: any U2 identity guard on the write path → nothing written, no
  partial output file left behind.
- Error (synthetic): craft a wrapper-level fault injection where a byte
  outside declared blocks differs post-change → post-verification fails loud
  (proves the diff check is real, not vacuous).
- Integration: checksum report present in every apply/remove result and
  states each checksum's status explicitly (AE5).
**Verification** — real-file run: stock copy → apply `SL PATCH.29.33 -
S50.btp` → confined diff, round-trip restores byte-identity, checksum states
match U1's findings.

### U4. Switch-patch XDF sanity load

**Goal** — the patched bin provably loads against the authoritative
switch-patch XDF: Map Slot 1–5 / Map Switching tables resolve and decode
plausible values.
**Requirements** — AE6.
**Dependencies** — U1 (which XDF), U3 (a verified patched bin to load).
**Files** — modify `Code/simoscal/btp.py` (or a small helper if it fits
better beside existing XDF-loading code); update
`knowledge/sc8s50-switchpatch-xdf.md` with the recorded answer.
**Approach** — reuse the existing `simoscal` XDF/calfile loading path
(`SC8S50_switchpatch29.33_v1.005/.006.xdf` are already valid load targets
per the knowledge note); "plausible" means: the slot/switching tables
resolve to in-region addresses, decode without codec errors, and slot tables
mirror stock values where the patch initializes slots from the base map —
define the concrete plausibility assertions from U1's empirical comparison.
**Test scenarios** —
- Happy path: patched bin + authoritative XDF → all Map Slot 1–5 and Map
  Switching tables resolve and decode; spot-check values against stock
  equivalents.
- Edge: stock (unpatched) bin + switch-patch XDF → characterize (document
  whether slot regions read as garbage/defaults) so the sanity check can't
  false-pass on an unpatched bin.
- Integration: sanity result included in the U3 apply report for the switch
  patch.
**Verification** — AE6's "which XDF matches" answer is recorded in the
knowledge note with the evidence; sanity check passes on the patched bin and
distinguishes it from stock.

### U5. Demo: stock → patch → verify

**Goal** — a runnable end-to-end demonstration of the canonical pipeline
order (patch stock first), producing reviewable artifacts.
**Requirements** — Key Flow 2 and 4 from the origin doc (canonical pipeline,
human review gate).
**Dependencies** — U3, U4.
**Files** — create `Code/demos/apply_btp_patch.py` (pattern:
`Code/demos/apply_sop_recipe.py` with its timestamped output folder
convention).
**Approach** — check the stock bin, apply the switch patch to a copy, run
full post-verification + checksum report + XDF sanity, write the report and
the patched base bin into a timestamped `apply_btp_patch_out/` folder
(gitignored via `*_out/`). The demo is the reference for how future tune
scripts consume the patched base.
**Test scenarios** — Test expectation: none beyond U6's acceptance coverage —
the demo composes already-tested operations; its correctness is the
acceptance suite's job.
**Verification** — demo runs headless on the Mac against the real files and
its report contains: readiness state, per-block apply outcomes, confined-diff
confirmation, checksum states, XDF sanity result.

### U6. Test suite: unit + acceptance

**Goal** — the AE1–AE7 guarantees are pinned under test, following the
existing skip-cleanly convention.
**Requirements** — all of AE1–AE7; origin doc's "Done = all of the above
under test, offline."
**Dependencies** — U2, U3, U4 (tests land with their units where practical;
this unit covers the acceptance layer and any remaining unit-test gaps).
**Files** — create `Code/tests/test_btp.py` (unit, synthetic fixtures) and
`Code/tests/test_acceptance_btp.py` (real files); extend
`Code/tests/conftest.py` with a `bintoolz_root` / real-patch fixture that
skips when `BinToolz-main/` or the real bin is absent (mirror
`requires_real_files`).
**Approach** — decision 8: a minimal test-only synthetic `.btp` writer built
from the documented format (fixture-authoring code, not a port of BinToolz);
synthetic bins sized small with a fake hardware entry only if BinToolz's
hardware table permits, otherwise synthetic tests target the adapter's guard
logic and the real-file acceptance tests cover BinToolz interop. Acceptance
tests: AE1 (check leaves real bin byte-identical), AE2 (confined diff),
AE3 (round-trip), AE4 (mismatched patch rejected), AE5 (checksum states
asserted, not assumed), AE6 (XDF sanity on patched bin), AE7 (loader error
with BinToolz path pointed at a nonexistent directory — testable even on a
machine that has BinToolz).
**Test scenarios** — the AE1–AE7 list above is the scenario set; plus the
skip behavior itself (suite green with `BinToolz-main/` absent).
**Verification** — full `Code/` suite passes (299 existing tests stay
green); new tests skip, not fail, when the real patch/bin/BinToolz are
absent.

## Scope Boundaries

**Out (from the origin doc):** flashing and on-car validation; slot switching
procedure on the car; patch creation (`patchCreate`); porting BinToolz code;
slot-aware tuning workflow (which tune in which slot, REV_LOG conventions for
slots); BinToolz's ignore-data mode.

### Deferred to Follow-Up Work

- Slot-aware tuning workflow brainstorm (after this substrate exists).
- Full-flash procedure and first-flash safety steps for a patched bin —
  future flash-validation effort, gated on the DSG diagnosis.
- Ingesting `Docs/4. ECU Tuning - Not the Basics.docx` (likely covers the
  on-car slot-selection procedure) — user has said not yet.
- If U1 finds ASW block checksums are corrected at flash time by
  SimosTools/VW_Flash: deciding whether `simoscal` should ever learn to
  compute non-CAL block checksums itself (out of scope here; the report just
  states the facts).

## Open Questions

Both blocking questions from the brainstorm are **resolved by U1 inside this
plan** (that's its purpose); none remain open for the user at plan time.
One judgment call is deliberately deferred to U1 evidence: the exact
"plausible values" assertions for AE6 (defined empirically, not guessed).

## Risks & Dependencies

- **BinToolz API drift** — mitigated by the loader's API-surface check
  (AE7): fail loud, never guess.
- **Synthetic-bin limits** — BinToolz's `hardwareType()` recognizes real
  Simos layouts; if synthetic 4 MB fixtures can't satisfy it cheaply, unit
  tests cover adapter-side guards and real-file acceptance tests carry the
  interop burden (explicitly allowed in U6).
- **Checksum characterization ambiguity** — if U1 cannot fully determine
  ASW checksum handling offline, AE5's contract still holds: the report says
  "not-verifiable" for those regions rather than asserting cleanliness.
- **License** — no BinToolz code is copied; the synthetic fixture writer is
  built from the format description in `knowledge/bintoolz-btp-patching.md`.
- **Safety** — all work on copies; stock bin `Code/bin/5G0906259L__0002.bin`
  untouched; nothing here flashes (tuning paused regardless, pending DSG
  diagnosis).

## Sources & Research

- `Docs/brainstorms/2026-07-10-btp-patching-requirements.md` — requirements.
- `knowledge/bintoolz-btp-patching.md` — `.btp` format, BinToolz safety
  procedures, gaps, license analysis.
- `knowledge/sc8s50-switchpatch-xdf.md` — switch-patch XDF structure, slot
  categories, full-flash requirement.
- Code review this session: `BinToolz-main/source/library/BTP.py`,
  `SimosBIN.py`, `Patch.py`, `Return.py` — confirmed Qt-free callable layer,
  bin-position block offsets, CAL = block 4, GUI layer unusable headless.
- `Code/tests/conftest.py` — skip-cleanly convention to mirror.
- `Code/simoscal/checksum.py` — existing `verify` API for AE5.
