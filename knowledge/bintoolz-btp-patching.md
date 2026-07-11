---
source: BinToolz-main/source/ (code review, 2026-07-10)
date: 2026-07-10
key_people: BinToolz author (license holder)
key_concepts: .btp patch format, bin patching, switch patch, map slots, wrap-don't-port decision, license constraint
---

# BinToolz `.btp` patching — code review and integration decision

Reviewed the BinToolz Python source (~1,200 lines: `BTP.py`, `Functions.py`,
`Patch.py`, `SimosBIN.py`) to answer: **do we know enough to implement bin
patching (e.g. the multi-slot switch patch) in our pipeline?** Answer: yes —
and the decision is **wrap BinToolz, don't port it into `simoscal`**.

## What we have on disk

- `BinToolz-main/patches/SL PATCH.29.33 - S50.btp` — the switch patch for our
  box code (`5G0906259L_0002`, SC8S50), same 29.33 version as the curated
  [[sc8s50-switchpatch-xdf]] (`xdf/SC8S50_switchpatch29.33_v1.005/.006.xdf`).
- `BinToolz-main/definitions/S50 Switch Patch.29.33.V2.xdf` — BinToolz's own
  matching definition.
- Full Python source in `BinToolz-main/source/` — `patchApply()` is callable
  headless; no Windows or the bundled `.exe` needed.

## The `.btp` format (from `BTP.py`)

100-byte header: version string ("BinToolz Patch v1.1"), software code,
block count, CRC32 over the payload, expected bin file size. Then per block:
8-byte header (offset, length) + **the original bytes** + **the modified
bytes**. Storing both directions is the key safety design — apply verifies
against originals; remove verifies against modifieds and restores originals.

## Safety procedures BinToolz already enforces

1. Patch-file integrity: CRC32 self-checksum + version string check on load.
2. Identity: bin hardware type must be recognized (`SimosBIN.hardwareType()`);
   patch header software code must match the bin's.
3. **Byte-exact pre-verification**: every target byte must equal the stored
   original bytes before anything is written — structurally cannot patch the
   wrong bin, wrong region, or a drifted bin.
4. Mismatch classification CAL vs ASW (block 4 = CAL): modified-ASW always
   blocks; modified-CAL blocks in normal mode, and an explicit "ignore data"
   mode applies only non-CAL blocks so an already-tuned CAL is preserved.
5. Read-only check mode (PATCH_FOUND / READY_TO_ACCEPT / NOT_READY_TO_ACCEPT).
6. First-class removal: restores the stored original bytes, same verification.

## Gaps by `simoscal` standards (what a wrapper must add)

- File-size mismatch between patch header and bin is **logged but not
  aborted** — must hard-fail.
- Broad `try/except` collapses errors into generic return codes — must
  surface loudly.
- No post-apply verification pass — must re-diff the whole bin and confirm
  changes are confined to the patch's declared blocks.
- No `CAL_CRC`/`ECM3` recompute or report after patching — checksum state of
  a freshly patched bin is an **open question** (see below).

## License constraint → wrap, don't port

`BinToolz-main/license.txt` is an "AS IS" notice with **commercial use
requiring written permission from the author** and no explicit grant to copy
or derive. Unlike VW_Flash (BSD-2-Clause, which permitted the
reimplement-with-attribution approach used for `simoscal`'s checksums),
porting BinToolz code into `simoscal` is not clearly permitted. Wrapping —
keeping `BinToolz-main/` untouched and importing its `library/` modules from a
thin adapter — avoids the issue and keeps their byte-level logic authoritative
for the `.btp` files they ship together.

## Intended implementation shape (future phase)

A `simoscal` adapter: BinToolz check → apply, wrapped in our guarantees —
hard-fail on file-size mismatch, post-apply full-bin diff confined to declared
blocks, `CAL_CRC` + `ECM3` verify/report, and a sanity load of the patched bin
against the switch-patch XDF (slot tables decode plausibly).

## Open questions before implementing

1. **Checksum coverage outside CAL** — the patch touches ASW/code regions with
   their own block checksums; establish whether the `.btp`'s stored modified
   bytes already include corrected block checksums, and what SimosTools
   requires at full-flash time.
2. **Which XDF** for a patched bin — curated `v1.005`/`v1.006` vs BinToolz's
   `S50 Switch Patch.29.33.V2.xdf`; validate against the actually-patched bin.
3. **Switching procedure** — how slots are selected/configured in practice
   (cruise-stalk actuation, slot defaults); possibly covered by the not-yet-
   ingested `Docs/4. ECU Tuning - Not the Basics.docx`.
4. A switch-patched bin **requires a full flash** (not CAL-only) per
   [[ecu-tuning-basics]] — plan the flash procedure accordingly.

All investigation (items 1–2) is safe offline against bin copies. Note: per
`Troubleshooting/CheckEngine/20260710_Troubleshooting.txt`, tuning is paused
until the DSG electrical faults are diagnosed — this is future work.

Related: [[sc8s50-switchpatch-xdf]], [[ecu-tuning-basics]], [[tuning-getting-started]]
