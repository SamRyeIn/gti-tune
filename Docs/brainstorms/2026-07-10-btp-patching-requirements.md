# BTP Bin Patching (BinToolz wrapper) — Requirements

**Date:** 2026-07-10
**Status:** Brainstorm complete, ready for `/ce-plan`
**Prior art:** `knowledge/bintoolz-btp-patching.md` (code review, safety
analysis, license constraint), `knowledge/sc8s50-switchpatch-xdf.md`

## Problem

Enabling on-the-fly map switching (5 slots) — and other BinToolz features like
HSL logging — requires applying `.btp` patches to the bin. Today the only
applier is BinToolz's Windows-oriented GUI; nothing in our pipeline can apply,
check, or remove a patch, verify the result, or report checksum state. Sam
wants patching to be as traceable and verifiable as every other bin operation
in this project.

## Goals & Success Criteria

- Any BinToolz `.btp` can be **checked / applied / removed** on a bin copy
  from Python on the Mac, with fail-loud behavior throughout.
- A patched bin is **provably correct offline**: every changed byte is inside
  the patch's declared blocks, and nothing else changed.
- Checksum state of the patched bin (`CAL_CRC` + `ECM3`) is **characterized
  and reported**, never silently assumed.
- The switch-patched bin **loads sanely against the switch-patch XDF** (slot
  tables resolve and decode plausible values).
- Done = all of the above under test, offline. **Flashing and on-car
  validation are explicitly out of scope** (tuning is paused pending the DSG
  electrical diagnosis; see `Troubleshooting/CheckEngine/`).

## Scope

**In:**
- Generic `.btp` support (check / apply / remove) — the switch patch
  `SL PATCH.29.33 - S50.btp` is the first use case, not the boundary.
- A `simoscal` adapter module wrapping BinToolz's Python `library/` at
  runtime, plus a `demos/` script showing stock → patch → verify.
- Post-apply verification: full-bin diff confined to declared blocks;
  checksum verify/report; XDF sanity load for the switch patch.
- Guards the wrapper must add over BinToolz: hard-fail on patch/bin file-size
  mismatch; surface (not swallow) errors; fail loud if `BinToolz-main/` is
  missing or its API surface changed.
- Tests, skipping cleanly when `BinToolz-main/` or the real bin is absent
  (existing convention).

**Out:**
- Flashing, on-car validation, slot switching procedure on the car.
- Patch *creation* (`patchCreate`) — we consume patches, we don't author them.
- Porting/copying BinToolz code into `simoscal` (license; see Key Decisions).
- Slot-aware tuning workflow (which tune goes in which slot, REV_LOG
  conventions for slots) — future brainstorm after this substrate exists.
- BinToolz's "ignore data" mode (patching an already-tuned bin) — not needed
  under the chosen pipeline order.

## Key Flows

1. **Check:** open a bin copy → check a `.btp` → report PATCH_FOUND /
   READY_TO_ACCEPT / NOT_READY, plus identity info (hardware key, software
   code) — read-only.
2. **Apply (canonical pipeline):** stock bin → apply patch → verified patched
   base → existing tune revision scripts run on top of that base. Patch-first
   ordering is canonical; tune edits always re-apply from scripts.
3. **Remove:** patched bin → remove patch → byte-identical to the pre-patch
   input (round-trip proof).
4. **Review:** every apply/remove produces a report the human reads before
   the bin goes anywhere near a flasher.

## Acceptance Examples

- **AE1 — check is read-only:** running check mode on any bin leaves the file
  byte-identical and returns a definitive readiness state.
- **AE2 — apply confined to declared blocks:** applying
  `SL PATCH.29.33 - S50.btp` to a copy of the stock bin changes bytes only
  inside the patch's declared (offset, length) blocks; a full-bin diff
  confirms zero changes elsewhere.
- **AE3 — round-trip:** apply then remove yields a bin byte-identical to the
  input.
- **AE4 — identity guards:** a patch whose software code or file size does
  not match the bin is rejected loudly; nothing is written.
- **AE5 — checksum report:** after apply, `CAL_CRC`/`ECM3` state is reported
  explicitly (clean, stale, or not-verifiable), never assumed.
- **AE6 — XDF sanity:** the patched bin opened with the switch-patch XDF
  resolves the Map Slot 1–5 / Map Switching tables and decodes plausible
  values; the answer to "which XDF matches the patched bin" is recorded.
- **AE7 — missing dependency fails loud:** with `BinToolz-main/` absent, the
  adapter raises a clear error (and tests skip, not fail).

## Key Decisions

1. **Generic `.btp` capability, not switch-patch-only** — the code path is
   identical; the patch file is data.
2. **Wrap BinToolz, don't port it** — its license ("AS IS", commercial use
   needs written permission, no explicit derivation grant) rules out copying
   code into `simoscal`; its byte-level logic stays authoritative for its own
   patch files. `BinToolz-main/` stays untouched and gitignored.
3. **Patch stock first, tune on top** — deterministic, re-runnable base;
   avoids relying on BinToolz's subtler CAL-skip path.
4. **Offline-verified is the finish line** — flash validation is a separate,
   later effort gated on the car being healthy.
5. **Approach A** — `simoscal` adapter + demo, consistent with how export,
   visualization, and the SOP recipe were built.

## Outstanding Questions

**Blocking (the plan must answer these early, offline):**
1. Do the `.btp`'s stored modified bytes already include corrected block
   checksums for the ASW regions it touches, or does SimosTools/VW_Flash
   correct them at full-flash time? (Determines what our checksum report must
   cover and what "flash-ready" means for a patched bin.)
2. Which XDF is authoritative for the patched bin — curated
   `SC8S50_switchpatch29.33_v1.005`/`.006` or BinToolz's
   `S50 Switch Patch.29.33.V2.xdf`? Validate empirically against the patched
   bin (AE6 records the answer).

**Deferred (not needed to build this):**
3. Slot selection/configuration procedure on the car (cruise stalk, slot
   defaults) — likely in `Docs/4. ECU Tuning - Not the Basics.docx`
   (not yet ingested).
4. Full-flash procedure and first-flash safety steps for a patched bin —
   belongs to the future flash-validation effort.
