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

Questions 1–2 were **resolved offline** during the BTP-adapter U1 investigation
(2026-07-10) against a copy of the stock bin; see the "U1 findings" section below.
Question 3 remains future work. Question 4 is resolved from the established
in-car flash procedure.

3. **Switching procedure** — how slots are selected/configured in practice
   (cruise-stalk actuation, slot defaults); possibly covered by the not-yet-
   ingested `Docs/4. ECU Tuning - Not the Basics.docx`.
4. **Flash mode for a switch-patched bin** — a full flash installs or changes
   the ASW/code patch components. After the ECU is confirmed to have the same
   patch set, later calibration-only tune updates may use a CAL flash; do not
   use CAL-only to introduce or upgrade a patch.

Note: per `Troubleshooting/CheckEngine/20260710_Troubleshooting.txt`, tuning is
paused until the DSG electrical faults are diagnosed — flashing is future work.

## U1 findings (2026-07-10) — offline, on a stock-bin copy

Applying `SL PATCH.29.33 - S50.btp` (softCode `SC800S50`, fileSize 4194304, **38
blocks**) to a copy of `5G0906259L__0002.bin` (BinToolz hardware `Simos 18.1`,
CAL = block 4 at `0x200000`, len `0x7fc00`):

- **10130 bytes change**, 4098 in CAL (block 4), the rest across ASW/code
  blocks 1–3. All changed bytes fall **inside the patch's declared (offset,
  length) blocks** — 0 outside. `changeBin` offsets are bin positions, so
  declared blocks map directly onto a full-bin diff. Gap-fill means declared
  blocks total 11436 bytes but only 10130 actually differ — the confined-diff
  invariant is one-directional (changes ⊆ declared, not the reverse).
- **Round-trip proven**: apply then remove yields a **byte-identical** bin.

**Q1 — checksum coverage (answer).** The `.btp`'s stored modified bytes do **not**
carry corrected checksums:

- **`CAL_CRC` goes STALE on apply** (stock `0x38521ef3` → recomputed
  `0x164a251f`). It must be corrected before flash — `simoscal`'s
  `save(..., correct_checksums=True)` / `checksum.correct` recomputes it, or the
  flasher does. A patched bin is therefore **not internally self-consistent as
  stored**.
- **`ECM3` stays VALID** — the patch does not touch the CAL areas ECM3 sums.
- **ASW/code block checksums (blocks 1–3)** are **outside `simoscal`'s checksum
  scope** (it only implements `CAL_CRC` + `ECM3`). They are computed by
  SimosTools/VW_Flash at full-flash time. The AE5 report states them as
  **not-verifiable**, never assumes clean.

**Q2 — which XDF (answer).** The authoritative XDF that **loads under `simoscal`**
is BinToolz's own **`BinToolz-main/definitions/S50 Switch Patch.29.33.V2.xdf`**
(185 tables; 123 Map Slot 1–5 / Map Switching tables resolve and **all decode
without codec error**). The curated `xdf/SC8S50_switchpatch29.33_v1.005/.006.xdf`
**do not load** — they reuse a single `uniqueid` across the 5 slots (different
address per slot), which `simoscal`'s uniqueid→single-location model rejects
(`uniqueid 0x11f9c reused with DIFFERENT data`). BinToolz's XDF instead gives each
slot a distinct `uniqueid` (e.g. RPM-limiter slots `0x7cb40`/`0x7cb42`/… for slots
1–5). Loading these XDFs also required a `simoscal` parser fix: a non-z axis whose
`<EMBEDDEDDATA>` lacks `mmedaddress` is a TunerPro **label/static axis**
(`mmedmajorstridebits="-32"`, breakpoints from `<LABEL>`s) — the switch-patch XDFs
use 854+ of these; the parser now treats them as label axes instead of erroring.

Patched-vs-stock is clearly distinguishable (guards AE6 against a false pass on an
unpatched bin): stock reads the slot regions as uninitialized (PUT-setpoint slots
`0.0`, "PUT SP RPM Axis" `0.0`), the patched bin reads plausible values
(PUT-setpoint slots ≈ 4000 hPa; "PUT SP RPM Axis" `0x7d7dc` decodes to a
monotonic rpm breakpoint set `[2000, 2500, 3000, …]`). 17 slot/switch tables
differ from stock.

Related: [[sc8s50-switchpatch-xdf]], [[ecu-tuning-basics]], [[tuning-getting-started]]
