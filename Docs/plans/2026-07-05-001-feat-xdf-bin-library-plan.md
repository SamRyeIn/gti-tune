# Plan — Phase 1: Python XDF/BIN Tuning Library

**Date:** 2026-07-05
**Type:** feat
**Origin:** [[xdf-bin-library-requirements]] (`docs/brainstorms/xdf-bin-library-requirements.md`)
**Status:** ✅ **Phase 1 complete** — **U1–U6 all done** (see Implementation Progress). Only remaining thread is the optional one-time TunerPro AE1 capture (needs a Windows box; procedure documented in `Code/tests/fixtures/README.md`).
**Depth:** Standard–Deep (6 implementation units)

## Summary

Build the Phase 1 substrate: a Python library that parses an SC8S50 TunerPro `.xdf`,
maps its tables against the 4 MB `.bin`, reads/edits table values in **physical units**,
and writes a **minimal-diff, flashable** `.bin`. Flashing and checksum *recomputation*
are out of scope (handled by SimosTools/VW_Flash); the library only verifies-and-warns
on stale checksums. The object model is shaped so the later export, visualization, and
auto-tuning modules are read-only consumers with no redesign.

## Problem Frame

Tuning the 2017 GTI (`5G0906259L_0002`, Simos 18.1/18.6, SC8S50) is manual and
non-repeatable in TunerPro. There is no programmatic path to read a table by name,
transform it, and emit a modified bin. This library is that path, and the foundation
every later phase builds on.

## Stakes & Safety

**This is not a sandbox project.** The end product of this pipeline is a modified
`.bin` that gets flashed to the engine controller of a real, driven car. That carries
two distinct classes of real-world risk:

1. **ECU integrity (bricking).** Flashing a malformed, mis-checksummed, or partially-written
   calibration can leave the ECU non-booting or in an inconsistent state. Simos18 is
   *usually* recoverable via a full flash / boot-mode unlock with VW_Flash, but treat a
   brick as a serious, possibly shop-visit outcome — not a casual undo.
2. **Mechanical / vehicle damage (bad tune).** Even a perfectly-written bin can encode a
   *dangerous calibration*: over-boost, a lean lambda target, or excess timing →
   **knock/detonation, melted pistons, a blown turbo, or a slipping/damaged DSG clutch**.
   Beyond the engine, this is a safety-of-life concern (a car that makes unexpected power
   or fails under load) and has emissions/legal implications.

**Two different failure sources, two different owners:**

- **Software-fidelity risk — this library's responsibility (Phase 1).** The library must
  *never silently alter or misplace a value*. A parser/writer bug that writes the wrong
  bytes, the wrong cell, or the wrong scaling could cause *either* a brick *or* a
  dangerous tune the user never intended. So the plan's correctness guarantees are
  **safety mechanisms, not conveniences**:
  - **Minimal-diff writes + round-trip byte-equality** (Decision 10, AE2/AE3) — the output differs from the input *only* where the user intended.
  - **Independent read oracles** (bounds / inverse / KingAi cross-parser, U3) — prove the decode is faithful before any value is trusted.
  - **Warn-loud, never-silent edit policy** (Decision 8) — an out-of-range value is written *and reported*, never quietly changed to something else.
  - **Float-bug hard guard** (Decision 9) — blocks the specific irreversible-corruption case the SOP calls out.
  - **Checksum verify (+ optional correct) via VW_Flash** (U5) — a stale-checksum bin is flagged before it reaches the flasher.
- **Tuning-decision risk — the human's responsibility (and, later, Phase 4).** Whether
  24 psi and 5° of timing is *safe for this engine on this fuel* is a tuning judgment
  the library does not make in Phase 1. When Phase 4 (datalog-driven auto-tuning)
  starts proposing values, this risk shifts partly into software and will need its own
  guardrails (bounded corrections, sanity limits, human review gate).

**Operating principle for the whole pipeline:** *fail loud, change nothing silently, and
keep every modified bin verifiable before it is flashed.* Practical corollaries the
workflow assumes (documented in the U6 README):
- **Always retain a known-good stock bin** (`bin/5G0906259L__0002.bin`) as the recovery image.
- **A human review gate before every flash** — visually confirm changed tables
  (TunerPro or the Phase 3 viz module) and pass checksum verification; the library
  never flashes.
- **First flash full + unlock, battery on a charger** (per the SOP), so recovery is possible.
- Flashing itself stays **off-plan**, delegated to the tools built for it (SimosTools / VW_Flash) which carry their own recovery and checksum handling.

## Requirements (from origin doc)

- Parse XDF (`XDFTABLE`/`XDFCONSTANT`/`XDFAXIS`/`EMBEDDEDDATA`/`MATH`/categories/`BASEOFFSET`).
- Read tables/axes/constants in physical units; look up by A2L symbol and by title.
- Edit in physical units; write inverts the linear MATH and rounds to raw; only edited bytes change.
- Round-trip fidelity (load → save-unchanged → byte-identical).
- Values match TunerPro on a sampled set.
- Output bin flashes via SimosTools/VW_Flash.
- Verify/report stale checksums (no recompute).
- Acceptance examples **AE1–AE5** in the origin doc.

## Key Technical Decisions

1. **Language/stack:** Python 3.11+, standard-library `xml.etree.ElementTree` for
   parsing (no `lxml` dependency), `numpy` for table value arrays. No other runtime deps
   in Phase 1. `openpyxl` is deferred to the Phase 2 export module. *(Rationale: keeps
   the substrate dependency-light; numpy gives clean vectorized scale/round and is the
   natural interchange type for the later viz/export/auto-tune modules. Consistent with
   keeping all tooling in Python.)* **The library is pure-Python and fully cross-platform
   — it runs on the Mac with no Windows dependency.** The only Windows touchpoint in the
   whole plan is the optional one-time TunerPro oracle capture (see U3/U6 and Risks);
   flashing is off-plan entirely (Android SimosTools / VW_Flash).
2. **Parse strategy — streaming:** use `ElementTree.iterparse`, materializing one
   `XDFTABLE` element at a time and clearing it, so the parser scales from the 5.8 MB
   `V1.0` file up to the 59 MB `.ALL` without loading the whole tree. *(Rationale:
   `.ALL` is a valid future load target; streaming avoids a memory blowup.)*
3. **Lazy value materialization:** the XDF parse builds table **metadata** only
   (address, shape, strides, type, scaling, category, names). Raw bytes are read and
   decoded to physical values **on access**, then cached. *(Rationale: loading all
   ~3,900 tables' values eagerly is wasteful when a script touches a handful.)*
4. **Canonical table key = `uniqueid`:** `uniqueid` (e.g. `0x36ec`) is the primary
   handle. Symbol (`<description>`) and title are indexed as **multimaps** (name → list
   of tables) because they are not guaranteed unique. The convenience getter `get(symbol)`
   returns the single match or raises `AmbiguousTableError` listing candidates.
   *(Rationale: correctness over convenience; avoids silently editing the wrong table.)*
   **⚠ Corrected in U2 (empirical):** `uniqueid` is **not** globally unique in
   `SC8S50.V1.0.xdf` — the file has **3,912 `XDFTABLE` elements but only 3,814 distinct
   uniqueids**; **98 uniqueids appear twice.** Each duplicate pair is the *same
   calibration variable cross-listed under a different title/category framing* (a
   DTC-style vs MIL-style name; e.g. `0x2487a` = `C_ERR_CLAS_2_AFU_SENS_ERR` appears as
   both "P0000 DTC Fehlersymptom …" and "Second failure class number …"). **Verified: in
   every duplicate group the data-bearing fields — z/x/y address, shape, strides,
   typeflags, and scaling — are byte-identical; only title/description/`CATEGORYMEM`
   differ.** So the safety property (one uniqueid ⇒ one bin location ⇒ one decode) holds.
   The parser therefore: (a) keeps all 3,912 parsed tables in `model.tables` (faithful to
   the file); (b) computes a **data fingerprint** per uniqueid and **hard-fails
   (`XdfParseError`)** if a repeated uniqueid ever carries *different* data — never
   silently maps one id to two locations; (c) keeps the first occurrence in `by_id`
   (3,814 entries) and **dedupes the symbol/title/category multimaps by uniqueid** so a
   cross-listed table is not falsely reported `AmbiguousTableError`. Downstream note:
   `len(model.tables)` (3,912) ≠ `len(model.by_id)` (3,814); `model.duplicate_ids` maps
   each repeated uniqueid → extra-occurrence count.
5. **Address mapping:** `file_offset = mmedaddress + BASEOFFSET.offset` when
   `subtract="0"` (the observed case; offset `0x200000`). The CAL block occupies the
   upper 2 MB of the 4 MB bin. Every computed offset+extent is validated against the
   `REGION` size (`0x400000`); out-of-region ⇒ hard error. *(Rationale: grounded in
   the real files — table addresses are small and only make sense added to the base.)*
6. **`mmedtypeflags` decode (TunerPro layout):** bit `0x02` = little-endian (LSB-first),
   bit `0x04` = signed (two's-complement), bit `0x10000` = IEEE float; element width
   from `mmedelementsizebits` (8/16/32). Observed: `0x6`=signed LE, `0x2`=unsigned LE,
   `0x10006`=float **signed** LE (5 tables, 32-bit — the `0x04` sign bit is set even
   on floats, where it is moot). Decoded per-table, **not** from the global
   `DEFAULTS`. *(Community sources conflict on these bits — the KingAi exporter
   documents `0x01`=LE/`0x02`=signed, which would make every table big-endian and
   contradicts Simos + the XDF `DEFAULTS lsbfirst="1"`. Our decode is self-consistent
   with the file.)*
   - **⚠ U3 status (empirical).** The bit *interpretation* is now anchored by three
     TunerPro-free signals, but **not yet by a fully independent parser**: (a) internal
     self-consistency — all 3,814 tables decode inside their raw-type envelope and >75%
     inside their display `<min>`/`<max>`; a wrong endian/sign would scatter values;
     (b) physically-plausible pins (e.g. `0x36ec` → −98% power factor); (c) the domain
     prior (`lsbfirst="1"`, Simos is little-endian). The U3 `struct` cross-decode oracle
     (below) proves the *implementation* is correct but **shares this bit interpretation**,
     so it cannot adjudicate Decision 6 on its own. The **one-time TunerPro capture
     (AE1, U6) is the primary independent oracle** that settles the bit meanings
     outright; the KingAi cross-parser (Decision 11) is an *optional* Mac-native second
     opinion, no longer a gate.
7. **MATH = linear only:** on parse, assert every equation reduces to `phys = m·X + b`
   (identity or the `((a·X)-b)/(c-(d·X))` form with `d=0`). Read applies `m·X+b`; write
   applies `X = round((phys-b)/m)` into the raw integer type. A non-linear equation
   (none exist in `V1.0` — all 11,736 are linear) is flagged and its table falls back to
   raw-only editing. *(Rationale: empirically verified; keeps the math a closed form.)*
8. **Edit-safety policy (Q1 resolved):** default **warn + allow** — out-of-range writes
   vs. the table's XDF min/max succeed but emit a structured warning (table, cell,
   limit); the value is never silently altered. *(Rationale: matches how tuners
   deliberately exceed conservative XDF limits.)*
9. **Float-bug hard guard (resolved):** a small, explicit **flagged-list** of known
   float-bug-prone tables (overboost / max-airmass, by symbol) hard-rejects writes that
   exceed the raw type's representable range or the table's declared upper limit — even
   with an override flag. Note: writing raw bytes directly does not reproduce TunerPro's
   formula-editor float bug per se, but this guard also prevents raw-range overflow,
   which *would* corrupt a table. *(Rationale: the SOP calls this out as irreversible.)*
10. **Write minimality:** load keeps the original bin bytes; save mutates only the byte
    ranges of edited cells and writes the buffer back. Unedited bytes are never touched.
    *(Rationale: guarantees AE2/AE3.)*
11. **Build vs. reuse (from research):** every existing Python XDF tool is **read-only**
    (export/compare) — none does the write path — so the parser/read/write core stays
    ours. Two pieces are reused rather than reimplemented: (a) **checksums** adapt
    VW_Flash's `lib/checksum.py` + `lib/fastcrc.py` (BSD-2-Clause; Simos18 CRC +
    ECM3→ECM2 verify/correct) — see U5; (b) the **KingAi TunerPro-XDF-BIN Universal
    Exporter** (pure-Python, stdlib-only) is an **optional** second, Mac-native read
    oracle — see U3/U6. *(Rationale: don't reinvent a proven Simos
    checksum routine; use an independent parser to validate reads without TunerPro.
    **⚠ U3 update:** KingAi was downgraded from a planned gate to optional. U3 shipped a
    lighter independent oracle instead — a stdlib-`struct` re-decode that matches the
    numpy codec on all 3,814 tables — which fully covers *implementation* correctness
    (frombuffer/reshape/offset/endian-application; endianness has teeth: 840/933
    multi-byte tables differ LE vs BE). But that oracle **shares our typeflag-bit
    interpretation**, so KingAi's unique value — an independently-authored second
    opinion on the bit *semantics* (Decision 6) — is now largely subsumed by the
    one-time TunerPro capture (AE1), which is the stronger place to spend that effort.
    KingAi remains a cheap Mac-native belt-and-suspenders check to wire in when
    convenient, not a blocker for U4.
    Note: VW_Flash's `lzss/` subdir is GPL but is compression used only during flashing
    — out of scope; `checksum.py`/`fastcrc.py` are the BSD parts we touch. The KingAi
    exporter is MIT-with-attribution / no-commercial-without-permission — used here as
    a personal-use reference/oracle, not vendored into redistributable code.)*

## High-Level Technical Design

```
                 xdf/*.xdf                     bin/*.bin
                    │                              │
            ┌───────▼────────┐            ┌────────▼─────────┐
            │  XdfParser     │            │  BinImage        │
            │ (iterparse →   │            │ (raw byte buffer,│
            │  metadata)     │            │  region-aware)   │
            └───────┬────────┘            └────────┬─────────┘
                    │ builds                       │
            ┌───────▼───────────────────────────────▼────────┐
            │                 CalFile (façade)                │
            │  indexes: uniqueid, symbol→[], title→[]         │
            │  get()/search()/categories()                    │
            └───────┬───────────────────────┬─────────────────┘
                    │ Table.values (read)   │ Table.set()/save() (write)
            ┌───────▼────────┐      ┌────────▼─────────┐   ┌──────────────┐
            │ codec: bytes↔  │      │ writer: invert   │   │ checksum:    │
            │ physical (np)  │      │ scale, minimal   │   │ verify/report│
            │ typeflags+scale│      │ diff, safety     │   │ (no recompute)│
            └────────────────┘      └──────────────────┘   └──────────────┘
```

Later phases (export/viz/auto-tune) consume `CalFile`/`Table` read-only — they are not part of this plan.

**Bin memory map (address mapping, Decision 5).** XDF table addresses are small; the
file offset is `mmedaddress + 0x200000`, placing all calibration in the upper 2 MB:

```
   bin/5G0906259L__0002.bin  (4 MB)
0x000000 ┌───────────────────────────────┐
         │  CBOOT · ASW1 · ASW2 · ASW3    │  lower 2 MB — code/OS
         │  (not edited in Phase 1)       │
0x200000 ├───────────────────────────────┤ ◀── BASEOFFSET (subtract=0 ⇒ add)
         │  CAL block  (calibration)      │  upper 2 MB — what we read/edit
         │                                │
         │  table @ file_offset           │
         │    = mmedaddress + 0x200000    │  e.g. 0x36ec → 0x2036ec
0x400000 └───────────────────────────────┘
```

**Read/write data pipeline (the transformation, Decisions 6–10).** Modules above show
*structure*; this shows how a value flows byte↔physical:

```
 READ                                                          WRITE
 bin bytes                                                     physical value (user, in %/°/kPa)
   │ slice(file_offset, strides)                                 │ inverse MATH:  X = round((phys − b) / m)
   ▼                                                             ▼
 raw element                                                   raw int
   │ decode: width(8/16/32) · endian(0x02) ·                     │ range-check ─▶ ⚠ warn if outside XDF min/max
   │         signed(0x04) · float(0x10000)                       │            ─▶ ✖ hard-reject float-bug tables
   ▼                                                             │            ─▶ non-linear table ⇒ raw-only
 raw int (numpy)                                                 ▼
   │ MATH (linear):  phys = m · X + b                          pack: width · endian · signed
   ▼                                                             │
 physical value ─────────────────────────────────────────────▶ │ minimal-diff: write only these bytes
 (numpy array, cached)                                           ▼
                                                               bin buffer  ─▶ save()  ─▶ (checksum verify) ─▶ external flash
```

## Implementation Units

### U1. Package scaffold + core data model
- **Goal:** Establish the Python project and the immutable metadata types the rest of
  the code is built on.
- **Requirements:** foundation for all.
- **Dependencies:** none.
- **Files:** `Code/pyproject.toml`, `Code/simoscal/__init__.py`, `Code/simoscal/model.py`,
  `Code/tests/__init__.py`.
- **Approach:** Define dataclasses: `ScalingEquation` (m, b, `is_linear`, `to_physical()`,
  `to_raw()`), `EmbeddedData` (address, rows, cols, elem_bits, major_stride_bits,
  minor_stride_bits, signed, little_endian, is_float), `Axis` (id x/y/z, labels, units,
  min, max, embedded, scaling), `Table` (uniqueid, symbol, title, categories, x/y/z
  axes), `Category`. Define exceptions (`AmbiguousTableError`, `NonLinearEquationError`,
  `RegionBoundsError`, `FloatBugGuardError`). Pick package name `simoscal`.
  `pyproject.toml` declares numpy dep and pytest dev-dep.
- **Test scenarios:** happy — construct a `ScalingEquation(m=0.0029296875, b=-48.0)`;
  `to_physical(raw)` and `to_raw(phys)` are inverses within rounding. Edge — identity
  equation (`m=1,b=0`) round-trips exactly. Error — constructing a non-linear equation
  sets `is_linear=False`.
- **Verification:** package imports; model types instantiate; equation round-trip unit
  test passes.

### U2. XDF parser (XML → model, streaming, indexed)
- **Goal:** Turn an `.xdf` into a populated set of `Table` objects plus lookup indexes,
  without touching any bin.
- **Requirements:** parse XDF; symbol/title lookup; linear-equation assertion.
- **Dependencies:** U1.
- **Files:** `Code/simoscal/xdf.py`, `Code/tests/test_xdf.py`, `Code/tests/fixtures/` (a
  small hand-written XDF snippet + reference to `xdf/SC8S50.V1.0.xdf`).
- **Approach:** `iterparse` over `XDFTABLE`/`XDFCONSTANT`; per element extract title,
  description (symbol), `CATEGORYMEM`, and the x/y/z `XDFAXIS`. From the z-axis
  `EMBEDDEDDATA` read address/shape/strides/typeflags; from `MATH` parse coefficients
  into a `ScalingEquation`, asserting linearity (flag + continue on violation). Parse
  `XDFHEADER` for `BASEOFFSET`, `REGION`, `CATEGORY` names, `DEFAULTS`. Build indexes:
  `by_id`, `by_symbol` (multimap), `by_title` (multimap), `by_category`. Clear each
  element after processing.
  - **⚠ Corrected in U2 (empirical):** `CATEGORYMEM category="N"` is **1-based** — it
    references header `CATEGORY index = N-1`, **not** `index = N`. Confirmed against the
    Checksum/DTC/MIL tables (e.g. a checksum table's `category="11"` → header
    `index=0xa` "Checksum"; a `category="26"` → "MIL"). The parser subtracts 1 when
    resolving membership. The symbol is the **first non-empty line** of `<description>`
    (later lines are `X:`/`Y:`/"Original Name:" commentary). Each `XDFTABLE` in V1.0 has
    exactly 3 `XDFAXIS` (x/y/z); many x/y axes are label-only (no `EMBEDDEDDATA`).
- **Test scenarios:** happy — parse the fixture snippet; a known table yields expected
  address, 10×10 shape, symbol, units. Real-file — parse `xdf/SC8S50.V1.0.xdf`;
  `len(tables) == 3,912` (parsed `XDFTABLE` elements), **3,814 distinct uniqueids / 98
  duplicates**, `660` header categories, `5,305` embedded-data axes; every one of the
  `11,736` equations flagged linear. Edge — a 1×1 "scalar" table parses as a table. Error
  — a malformed/absent `EMBEDDEDDATA` raises a clear parse error naming the uniqueid; a
  repeated uniqueid carrying *different* data hard-fails (`XdfParseError`). Integration —
  `get('C_FAC_POW_PUT_CTL_BOL')` returns exactly one table; a cross-listed symbol
  (`C_ERR_CLAS_2_AFU_SENS_ERR`) still returns exactly one (deduped by uniqueid); a symbol
  with genuinely distinct uniqueids raises `AmbiguousTableError`.
- **Verification:** parsing `V1.0` produces the expected counts and a queryable index in
  well under a few seconds. **Result: 54 tests green; real parse ≈ 0.9 s.**

### U3. BIN read path (address mapping, typeflags codec, scaling → numpy)
- **Goal:** Read a table's cells from the bin as a numpy array of physical values.
- **Requirements:** read in physical units; values match TunerPro; AE1.
- **Dependencies:** U2.
- **Files:** `Code/simoscal/binimage.py`, `Code/simoscal/codec.py`,
  `Code/simoscal/calfile.py`, `Code/tests/test_read.py`.
- **Approach:** `BinImage` loads the 4 MB file into a mutable `bytearray`, exposing
  region-checked slice reads. `codec.decode(table, binimage)`: compute `file_offset =
  address + base_offset`; validate offset+extent ≤ region size; walk cells using
  major/minor strides; interpret each element per width + `little_endian` +
  `signed`/`is_float` (`0x02/0x04/0x10000`); assemble a `numpy` array shaped
  `(rows, cols)`; apply the linear scaling → physical values; cache.
  `CalFile.open(xdf_path, bin_path)` is the façade tying parser + binimage + indexes;
  `Table.values` triggers the lazy decode. Axis label values decoded the same way when
  embedded.
- **Test scenarios:** The primary correctness oracles need **no TunerPro** (Mac-friendly):
  (1) **bounds oracle** — for every table, decoded physical values fall within the
  z-axis declared `<min>`/`<max>`; run across all ~3,900 tables to catch systematic
  scale/typeflags errors. (2) **inverse oracle** — `to_raw(to_physical(raw)) == raw`
  within one LSB for one table of each element type (8-bit signed, 16-bit unsigned,
  32-bit float). (3) **axis-sanity oracle** — a known RPM axis spans a plausible engine
  range, a PR/temp axis is plausible. (4) **shape** — a 10×10 table returns a
  `(10,10)` array; cell order verified against the stride math. (5) **independent
  decode oracle (Mac-native)** — re-decode every table with the stdlib `struct` module
  and assert it matches the numpy codec (0 mismatches / 3,814); this catches
  cell-order/offset/endian-application/width errors without TunerPro. *(Note: this
  oracle consumes our parser's typeflag decode, so it validates the implementation but
  not the bit-semantics of Decision 6 — that is settled by AE1. The KingAi exporter
  cross-check remains available as an optional independent-parser oracle.)* Error —
  extent past the region raises `RegionBoundsError`. **AE1 (TunerPro parity)** is a
  separate `@pytest.mark.tunerpro`
  test asserting a small **captured oracle table** (see conftest) recorded once from
  TunerPro; it is skipped by default on Mac and runs when the captured file is present
  — final confirmation on top of the KingAi cross-check.
- **Verification:** all tables pass the bounds oracle; the three element types decode
  correctly; our reads agree with the KingAi exporter on the sampled tables; the
  TunerPro-parity test passes once the one-time capture is recorded.

### U4. BIN write path (inverse scale, minimal-diff, edit-safety, float-bug guard)
- **Goal:** Edit table values in physical units and write a minimal-diff bin to disk.
- **Requirements:** edit in physical units; only edited bytes change; edit-safety (Q1);
  float-bug guard; AE2, AE3, AE4, AE5.
- **Dependencies:** U3.
- **Files:** `Code/simoscal/writer.py`, `Code/simoscal/safety.py`, `Code/tests/test_write.py`,
  `Code/tests/test_roundtrip.py`.
- **Approach:** `Table.set(values)` / `Table.set_cell(r,c,value)` accept physical units,
  invert the linear scale (`round((phys-b)/m)`), and range-check against the raw type.
  `safety.py` holds the warn+allow policy (structured warning on out-of-XDF-min/max)
  and the float-bug flagged-list (hard-reject over raw-range/upper-limit, even with
  `override=True`). Non-linear tables reject physical `set` and expose `set_raw` only.
  Edits are staged into the `BinImage` bytearray at exact byte ranges; `CalFile.save(path)`
  writes the buffer. Unedited bytes are copied verbatim from the original buffer.
- **Test scenarios:** happy (AE3) — set a boost/limiter table's last row to a physical
  target, save; diff vs input shows only that table's byte range changed; re-read returns
  the set values within one LSB. Round-trip (AE2) — open, save with no edits, output is
  byte-identical to `bin/5G0906259L__0002.bin`. Edge (AE4) — set a value above the XDF
  max; write succeeds and a warning is emitted naming table/cell/limit. Error (AE5) — a
  (synthetic) non-linear table rejects `set(physical)` and permits `set_raw`. Error
  (float-bug) — a write over a flagged table's upper limit raises `FloatBugGuardError`
  even with `override=True`. Edge — quantization: setting a value between two raw steps
  stores the nearest and re-reads within one LSB.
- **Verification:** round-trip byte-equality holds; edits are minimal-diff; safety policy
  behaves per decisions 8–9.

### U5. Checksum verify/report (adapt VW_Flash)
- **Goal:** Detect and report that a written CAL block has stale checksums, adapting
  VW_Flash's proven Simos18 routine rather than reverse-engineering one.
- **Requirements:** verify/report stale checksums.
- **Dependencies:** U3 (needs region/address mapping); pairs with U4 output.
- **Files:** `Code/simoscal/checksum.py`, `Code/tests/test_checksum.py`.
- **Approach:** Adapt VW_Flash `lib/checksum.py` + `lib/fastcrc.py` (BSD-2-Clause — vendor
  with attribution or depend) for the Simos18 CAL CRC and ECM3→ECM2 summation. Given the
  4 MB bin, isolate the CAL block (upper 2 MB per the base offset) and run the reference
  verify; return a `ChecksumReport` (region, stored, computed, `is_stale`). Default
  behavior is **verify + warn** (do not silently rewrite); expose an **optional
  `correct=True`** path that writes corrected checksums using the same reference code,
  since the proven implementation makes correction low-cost. `save()` warns when edits
  touched a checksummed range and correction wasn't requested. Cross-check the ranges
  against the XDF `Checksum`-category tables. *(This removes the prior "algorithm unknown"
  risk — VW_Flash is the authoritative implementation, by the flasher's author.)*
- **Test scenarios:** happy — on the unmodified bin, report is `is_stale=False` (matches
  VW_Flash's own verdict on the same file). After an edit in the covered range,
  `is_stale=True`. Correction — with `correct=True`, the re-saved bin verifies clean and
  matches what VW_Flash would produce (compare against VW_Flash output on the same edit).
  Edge — an edit outside any checksummed range produces no stale warning. Error — if the
  CAL block can't be located, degrade to an explicit "cannot verify" report, not a crash.
- **Verification:** unmodified bin reports clean; an edit flags stale; `correct=True`
  yields a bin that passes VW_Flash's own verification.

### U6. Fixtures + integration/acceptance suite
- **Goal:** Lock the AE1–AE5 acceptance examples as an executable suite and provide
  reusable fixtures.
- **Requirements:** all acceptance examples; success criteria.
- **Dependencies:** U4 (and U2, U3, U5).
- **Files:** `Code/tests/conftest.py`, `Code/tests/test_acceptance.py`,
  `Code/tests/fixtures/README.md`, `Code/README.md`.
- **Approach:** `conftest.py` provides fixtures pointing at `xdf/SC8S50.V1.0.xdf` and
  `bin/5G0906259L__0002.bin` (skip-if-absent guard so the suite is portable), plus a
  `tunerpro` marker gated on the presence of `Code/tests/fixtures/tunerpro_oracle.json`.
  `test_acceptance.py` encodes AE1–AE5 end-to-end (AE1 gated on the oracle capture).
  `Code/README.md` documents the library API, the "load → edit → save → flash externally"
  workflow, the flash/checksum boundary, and **how to record `tunerpro_oracle.json`** in
  one Windows session (a documented list of ~10 tables spanning 8/16/32-bit,
  signed/unsigned/float, and one multi-row table, with their TunerPro-displayed values).
- **Test scenarios:** integration — AE2 round-trip, AE3 minimal-diff edit, AE4
  warn-on-range, AE5 non-linear fallback all pass against the real files **with no
  TunerPro**. AE1 TunerPro-parity passes when `tunerpro_oracle.json` is present, skips
  otherwise. Edge — suite skips cleanly (not fails) if the real bin/xdf are absent from
  a checkout.
- **Verification:** the TunerPro-free acceptance subset passes on Mac; AE1 passes once
  the one-time oracle capture is committed; README documents the boundary and the
  capture procedure.

## Implementation Progress

- **U1 — Package scaffold + core data model ✅ (2026-07-05).**
  `Code/pyproject.toml`, `Code/simoscal/{__init__,model}.py`, `Code/tests/test_model.py`.
  Dataclasses `ScalingEquation`/`EmbeddedData`/`Axis`/`Category`/`Table` and the four
  exceptions. Linearity is detected by **safe numeric probing of an AST-parsed MATH
  expression** (no `eval` of untrusted strings — an allowlisted arithmetic evaluator);
  `ScalingEquation.from_expression()` fits `m,b` and sets `is_linear`, refusing to
  transform non-linear/zero-slope equations (raises `NonLinearEquationError`). 28 tests.
- **U2 — XDF parser ✅ (2026-07-05).**
  `Code/simoscal/xdf.py`, `Code/tests/test_xdf.py`, `Code/tests/fixtures/mini.xdf`.
  Streaming `iterparse` → `XdfModel` (indexes + `get`/`search`/`categories`). 26 tests;
  **54 total green; real V1.0 parse ≈ 0.9 s.**
  Key empirical corrections folded into Decisions above:
  - **Duplicate uniqueids** (Decision 4): 3,912 tables / 3,814 distinct ids / 98
    metadata-only duplicates; parser fingerprints and hard-fails on genuine conflict.
  - **1-based `CATEGORYMEM`** (U2 approach): `category="N"` → header `index=N-1`.
- **U3 — BIN read path ✅ (2026-07-05).**
  `Code/simoscal/{binimage,codec,calfile}.py`, `Code/tests/test_read.py`.
  `BinImage` (region-checked byte buffer) + `codec` (typeflags/scaling → numpy) +
  `CalFile.open(xdf, bin)` façade returning `TableView` objects with lazy-cached
  `.values`/`.raw`. **36 U3 tests; 90 total green; real parse+read suite ≈ 3 s.**
  Key decisions/corrections folded into Decisions above:
  - **Duplicate-uniqueid policy resolved** (Decision 4): keep `model.tables` faithful
    (3,912) and added `XdfModel.unique_tables()` / `CalFile.unique_tables()` — a
    dedup-by-uniqueid view (3,814) for oracle sweeps and consumers. No model collapse.
  - **Packed-contiguous layout** (Decision 6/codec): every axis in V1.0 is tightly
    packed (`minorstride=0`, `majorstride`=elem size, *not* a row stride). The codec
    decodes row-major contiguous and **fails loud (`CodecError`) on any non-packed
    stride** rather than guess.
  - **Read oracle set** (Decision 11): the planned KingAi cross-check was **downgraded
    to optional**; U3 ships a stdlib-`struct` independent decode oracle (0 mismatches /
    3,814) covering implementation correctness, plus type-envelope bounds (0 violations),
    >75%-within-declared-limits guard, per-type inverse round-trip, and known-value pins.
    Bit-semantics (Decision 6) remain for the TunerPro capture (AE1, U6) to confirm.
  - **Empirical notes:** the XDF `<min>`/`<max>` are *display* limits — 543/3,814 tables
    legitimately exceed them (conservative limits + float sentinels like 239996.0), so a
    strict min/max oracle would be flaky. No 16-bit *unsigned* z-table exists (only as
    axis breakpoints); the 5 float tables are typeflags-signed (`0x10006`).
- **U4 — BIN write path ✅ (2026-07-05).**
  `Code/simoscal/{writer,safety}.py` (new), extensions to `calfile.py`/`binimage.py`/`model.py`,
  `Code/tests/{test_write.py,test_roundtrip.py}`. **20 U4 tests; 110 total green (~9 s).**
  Key decisions/corrections folded into Decisions above:
  - **Float32 precision preserved** (Decision 6/writer): `physical_to_raw` rounds ints via
    `ScalingEquation.to_raw` but **keeps float precision for float32 tables** — rounding a
    float table would corrupt it. `pack_block`/`stage_full`/`stage_cell` do minimal-diff
    staging.
  - **Warn+allow + hard guards** (Decisions 8/9): `safety.py` — `EditRangeWarning`+`RangeBreach`
    (warn on XDF min/max breach, value still written); `check_raw_fits`→`RawRangeError`
    (raw-width overflow hard guard, all tables); `check_display_range`+`FLOAT_BUG_SYMBOLS`
    (float-bug hard guard — rejects over-upper-limit even with `override=True`). Flagged list
    grounded in 4 real float32 symbols: `C_M_AIR_CYL_FL`, `C_M_AIR_CYL_SP_MAX`,
    `C_PRS_IM_SP_LIM`, `C_PRS_IM_SP_MAX` (extensible).
  - **Minimal-diff = byte-level** (Decision 10): `set()` rewrites the whole contiguous table
    range but unchanged cells serialize identically → on-disk diff is exactly the changed
    bytes (verified byte-identical no-op via AE2); `set_cell()` writes one element only.
    `CalFile.save()` + `.edited`/`.edited_ranges` (the latter is what U5 consumes to warn on
    checksum-touch).
  - **Honest note (ordering):** a value exceeding *both* display-max and raw-width emits the
    range warning *before* `RawRangeError` (nothing written). Intentional; may later prefer
    short-circuit.
  - **Tests:** `test_write.py` (14, synthetic via inline XDF `BASEOFFSET 0x0`) +
    `test_roundtrip.py` (6, real bin AE2/AE3; skip cleanly if xdf/bin absent).
- **U5 — Checksum verify/report ✅ (2026-07-05).**
  `Code/simoscal/checksum.py` (new), extensions to `calfile.py`/`__init__.py`,
  `Code/tests/test_checksum.py`. **18 U5 tests; 128 total green (~14 s).**
  Algorithm **validated against the real stock bin** — both embedded checksums
  recompute to their stored values byte-for-byte (the strongest oracle, stands in
  for VW_Flash's own verdict). Key decisions/findings:
  - **CAL CRC** (adapted from VW_Flash `fastcrc`): 32-bit CRC, poly `0x04C11DB7`,
    **initial value 0** (not `0xFFFFFFFF` — so *not* canonical CRC-32/MPEG-2), no
    reflection, no final xor. Header at CAL-relative `0x300`. The CRC table is
    **generated at import** (reproduces VW_Flash's `crctab`), not vendored. In the
    stock bin it covers `[0x0,0x2FF]+[0x400,0x7F9FF]` — the whole CAL block *except*
    its own header — so essentially any calibration edit makes it stale.
  - **ECM3 monitor** (64-bit summation of LE u32 words): header at CAL-relative
    `0x400`; **its area addresses live in the ASW1 block** (moved there in newer
    ECUs), read from ASW1 `0x520` (late) / `0x540` (early), so ECM3 needs a **full
    bin** (has ASW1). A CAL-only image degrades to `can_verify=False`. Stock-bin
    coverage is a small area `[0xD9AC,0x10230]`.
  - **Address spaces** (important): checksum header addresses are absolute ECU
    (`0xA0800000` CAL base) — distinct from the XDF's `BASEOFFSET 0x200000`. The
    module carries the Simos18 CAL constants itself (not in the XDF); the CAL block
    sits at bin offset `0x200000`, length `0x7FC00`.
  - **`ChecksumReport`** (`name`/`can_verify`/`is_stale`/`stored`/`computed`/
    `covered`/`detail`); `covered` is half-open full-bin ranges → intersect with
    `CalFile.edited_ranges` via `ranges_overlap`. **Correction order: ECM3 first,
    then CRC** (ECM3's stored value sits inside the CRC's coverage).
    `correction_patches()` returns only the few stored-checksum bytes so
    `correct_checksums=True` stays minimal-diff.
  - **`CalFile.save()`** now returns `list[ChecksumReport]` and takes
    `correct_checksums=` / `warn_stale=`. Default = **verify + report, never
    silently rewrite**: emits `StaleChecksumWarning` when a stale checksum's range
    was touched this session. `CalFile.verify_checksums()` added. Verify runs on
    every save (read-only, ~0.1 s) — AE2 byte-identical still holds.
  - **Reuse note:** algorithm/header layout adapted from VW_Flash
    (`lib/checksum.py`+`lib/fastcrc.py`, BSD-2-Clause) with attribution in the
    module docstring; reimplemented (table generated, no verbatim vendor), so no
    third-party files are carried in the tree.
- **U6 — Fixtures + integration/acceptance suite ✅ (2026-07-05).**
  `Code/tests/conftest.py` (new), `Code/tests/test_acceptance.py` (new),
  `Code/tests/fixtures/README.md` (new), `Code/README.md` (new). **7 new
  acceptance tests + 1 skipped (AE1); 135 passed / 1 skipped total (~20 s).**
  Locks the AE1–AE5 examples as an executable suite and documents the library.
  Key decisions/findings:
  - **conftest fixtures** — session-scoped `real_xdf`/`real_bin`/`real_cal`, each
    **skip-if-absent** so a lean checkout stays green; the `tunerpro` marker was
    already registered in `pyproject.toml`, and a `tunerpro_oracle` fixture skips
    (never fails) until the capture exists.
  - **Acceptance suite** (`test_acceptance.py`) maps one test-group per example:
    **AE1** read-parity (`@pytest.mark.tunerpro`, skips cleanly on Mac), **AE2**
    byte-identical round-trip + set-current-values no-op, **AE3** single-cell
    minimal-diff + whole-table extent bound, **AE4** over-range warn+write (names
    table + cell), **AE5** non-linear reject-`set(physical)` / allow-`set_raw`.
    AE5 uses a **synthetic** inline XDF (no non-linear equation exists in V1.0);
    the example itself calls for a constructed table.
  - **AE1 status:** authored but **not yet executed** — its comparison path first
    runs when `tunerpro_oracle.json` is recorded (Windows). The JSON schema is
    pinned in *both* `test_acceptance.py` and `tests/fixtures/README.md` so they
    agree: top-level `tables` list; per-entry `uniqueid` (hex str/int),
    row-major `values`, optional per-table `tol` / top-level `tolerance`,
    optional `symbol`/`note`. Capture spans 8/16/32-bit · signed/unsigned/float ·
    ≥1 multi-row (`ID_PORT_SP` 10×10) · ≥1 non-identity scaling.
  - **Docs:** `Code/README.md` covers install, quick-start, the
    load→edit→save→verify→flash-externally workflow, the full `CalFile`/
    `TableView`/`ChecksumReport` API tables, the flash/checksum boundary, and the
    safety spine (fail-loud / minimal-diff / warn-not-clamp / float-bug guard /
    non-linear fallback / retain stock bin + human review gate).
  - **Expected warnings:** the 4 suite `StaleChecksumWarning`s (2 in
    `test_roundtrip.py`, 2 in `test_acceptance.py` AE3) are the feature firing on
    edit-then-save, not failures.
- **Tooling:** a project venv lives at `Code/.venv` (gitignored). Run tests with
  `cd Code && ./.venv/bin/python -m pytest tests -v` (or `pip install -e ".[dev]"` in any
  fresh env). Python 3.14 / numpy 2.5 observed; `requires-python >= 3.11`.

## Scope Boundaries

**Phase roadmap.** This plan is Phase 1 only — the substrate every later phase consumes read-only:

```
        ┌────────────────────────────────────────────────────┐
        │  PHASE 1 — Core substrate  (THIS PLAN)              │
        │  XdfParser · BinImage · CalFile · codec · writer   │
        │  · checksum   →  read/edit/write flashable .bin     │
        └───────────────────────┬────────────────────────────┘
                                │ exposes CalFile / Table (values in physical units)
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   ┌─────────────┐       ┌─────────────┐       ┌──────────────────────┐
   │ PHASE 2     │       │ PHASE 3     │       │ PHASE 4              │
   │ Export      │       │ Visualize   │       │ Datalog auto-tuning  │
   │ .csv / .xlsx│       │ plots +     │       │ SimosTools CSV ─▶    │
   │ (+openpyxl) │       │ colormaps   │       │ corrections ─▶       │
   └─────────────┘       └─────────────┘       │ change-sets ─▶ .bin  │
   read-only consumers ──────────────┘         └──────────┬───────────┘
                                                          │ writes via Phase 1
                                                          ▼
                                              (human review gate ─▶ external flash)
```

Phases 2 and 3 are independent read-only consumers (either order). Phase 4 is the only
later phase that writes — and it does so *through* the Phase 1 writer, inheriting its
safety guards.

**In:** XDF parse, bin read/edit/write in physical units, minimal-diff save, checksum
verify/report, acceptance suite.
**Out:** flashing (SimosTools/VW_Flash), checksum *recompute*, CBOOT/ASW editing, bin
patching (MPI/SWG/HSL/switch), FRF→BIN extraction, GUI/CLI.

### Deferred to Follow-Up Work
- **Phase 2 — Export module** (`.csv`/`.xlsx`; adds `openpyxl`).
- **Phase 3 — Visualization module** (plots + colormap tables).
- **Phase 4 — Datalog-driven auto-tuning** (SimosTools CSV → corrections → change-sets → bin).
- Declarative "tune recipe"/change-set *files* (the object model supports change-sets in-memory; a serialized recipe format is Phase 4).
- Optional CLI/notebook front-ends.
- Loading/validating `SC8S50.ALL.xdf` (59 MB) and the switch-patch XDF as secondary fixtures.

## Open Questions

- **Q2 (canonical XDF) — resolved:** work against `SC8S50.V1.0.xdf` as the Phase 1 default; keep the parser general enough for other XDFs (validated later).
- **Checksum algorithm (U5) — resolved:** both Simos18 CAL checksums are implemented and
  **verified against the real stock bin** (recompute == stored, byte-for-byte). CAL CRC =
  poly `0x04C11DB7`, init 0, no reflection/xor, header at CAL `0x300`, covering the whole
  CAL block minus its header. ECM3 = 64-bit LE-u32 summation, header at CAL `0x400`, area
  addresses in ASW1 (`0x520`/`0x540`). No heuristic fallback was needed. (Adapted from
  VW_Flash, the authoritative implementation.)
- **typeflags confirmation (U3 → U6):** the `0x02/0x04/0x10000` bit meanings are
  asserted from the cross-tab survey and now further anchored by U3's self-consistency
  + plausibility checks (all tables in-envelope, plausible pins, `lsbfirst="1"`). The
  U3 `struct` oracle validates the *implementation* but shares this interpretation, so
  it is **not yet independently confirmed**. Final confirmation is the one-time TunerPro
  capture (AE1) recorded in U6 — the primary independent oracle for Decision 6. (KingAi
  cross-parser is an optional earlier check.)

## Risks & Dependencies

- **Checksum uncertainty** (Low, downgraded from Medium): resolved by adapting VW_Flash's
  BSD-2-Clause `checksum.py`/`fastcrc.py` — the authoritative Simos18 implementation —
  instead of reverse-engineering the algorithm. U5 now verifies (and can optionally
  correct) against a proven reference.
- **TunerPro oracle values** (Low): TunerPro is **Windows-only**; primary dev machine is
  a Mac. Mitigated by making TunerPro parity (AE1) a single **batched, one-time capture**
  (`tunerpro_oracle.json`, ~10 representative tables recorded in one Windows session)
  rather than a recurring dependency. The bulk of read-correctness is proven TunerPro-free
  via the bounds/inverse/axis-sanity oracles (U3). Day-to-day work — including all
  round-trip and edit tests — runs entirely on Mac. TunerPro is only revisited if a new
  box code/XDF needs a fresh capture.
- **Stride/endianness edge cases** (Low): covered by U3 tests across 8/16/32-bit and
  signed/unsigned/float; the 5 float tables and any big-endian tables are explicit
  cases.
- **No blocking external dependencies.**

## Sources & Research

- Origin requirements: `docs/brainstorms/xdf-bin-library-requirements.md`.
- Domain SOP: `knowledge/ecu-tuning-basics.md` (float-bug tables, checksum/patch cautions),
  `knowledge/tuning-getting-started.md`, `knowledge/sc8s50-switchpatch-xdf.md`.
- Direct inspection of `xdf/SC8S50.V1.0.xdf` (11,736 MATH equations all linear; typeflags
  cross-tab; base offset 0x200000; element sizes 8/16/32) and `bin/5G0906259L__0002.bin`
  (4 MB).
- Library research (2026-07-05): every existing Python XDF tool is read-only. Reuse
  targets — [VW_Flash](https://github.com/bri3d/VW_Flash) `lib/checksum.py`+`lib/fastcrc.py`
  (BSD-2-Clause, Simos18 checksum verify/correct); [KingAi TunerPro-XDF-BIN Universal
  Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter)
  (pure-Python read oracle). Reference — [a2l2xdf](https://github.com/bri3d/a2l2xdf)
  generated this XDF; its `default.csv` is a curated list of tuning-relevant tables,
  useful for **Phase 4** target selection.
