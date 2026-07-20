# Human-friendly tune API (`simoscal.tune`) — implementation plan

**Status: completed 2026-07-19.** All seven units landed on
`feat/human-friendly-tune-api` (both repos). AE1 met on the first run:
`TUNE_Basics_Guide_R13.py` reproduces the R12 bin with **0 changed bytes**,
locked in by `Code/tests/test_acceptance_tune.py`. Full suite green.

Deviations from the plan as written, all decided during implementation:

- **One shared byte buffer instead of staged saves.** Key decision 3 described
  mirroring R11/R12's stage → slot-caps → TC-flags save sequence. Binding both
  XDFs to the same `BinImage` (they declare identical region and base offset,
  asserted at open) makes the whole revision save once. Byte-identical result,
  and it removes the relay entirely rather than generalizing it.
- **Audit allowances are measured, not computed from table extents.** The plan
  had the raw-diff audit derive its allowance from journaled tables' byte
  offsets. Each write instead measures which bytes actually moved by diffing the
  table's extent across the write — strictly tighter (a 6-cell boost write moves
  8 bytes, not 12) and it needs no per-edit row bookkeeping.
- **`sop_recipe` bridged by byte attribution.** Rather than trusting the recipe's
  outcomes, the bridge snapshots the buffer, runs the recipe, and assigns every
  changed byte to the outcome whose table owns it — raising if any byte is
  unaccounted for.
- **`build()` gained post-save checks** (U5), for gates only the finished file
  can answer, e.g. switch-patch sanity.
- `positional_axis_match` and `checksum.stored_checksum_ranges` promoted to
  public API (the "small public promotions" U2 anticipated).

## Context

Requirements: `Docs/brainstorms/2026-07-19-human-friendly-tune-api-requirements.md`.

Revision scripts today are Claude-only artifacts: `TUNE_Basics_Guide_R12.py`
imports private helpers from five earlier revisions (R03/R07/R08/R10/R11),
monkey-patches `r11.R11_SLOT_CURVES_HPA`, and buries ~40 lines of intent in
~200 lines of per-revision plumbing. Sam wants (1) revisions a human can author
and read, and (2) a library shareable with other Simos 18 tuners who have no AI.

Settled decisions (from brainstorm + follow-up):

- **Flat script per revision**, self-contained, zero cross-revision imports.
- **Audience: any Simos 18 XDF** → symbol-resolution profile layer in v1.
- **Approach A+B hybrid**: domain-module API whose every call is journaled as
  a typed entry; one `build()` entry point owns the whole verification pipeline.
- **Resolution: map file + exact match.** Ship an explicit SC8S50 map
  (logical name → XDF symbol/uid). Other XDFs: map lookup → exact symbol-name
  match → fail loud with nearby-title suggestions. Never fuzzy-resolve.
- **v1 modules:** `boost`, `wastegate`, `fueling`, `ignition`, `limits`,
  `switchpatch`.
- Resolved here: `sop_recipe` is **not refactored** — it coexists; its
  `TableOutcome`s are adapted into the new journal. Package name
  `simoscal.tune`; `fueling` avoids the `lambda` keyword.

## Key technical decisions

1. **New package `Code/simoscal/tune/`** inside the existing simoscal repo:
   `profile.py`, `journal.py`, `project.py` (the `Tune` object), `pipeline.py`
   (build orchestration), and one file per domain module. Existing modules
   (`calfile`, `btp`, `sop_recipe`, `checksum`, `plot`) are reused, not changed
   — except small public promotions noted in U2.
2. **Journal is the single audit source.** Every domain call appends a typed
   `EditEntry` (logical name, resolved `` `ID` — Description``, kind,
   before/after physical values, units, guard verdicts). `build()` renders
   `report.md` from the journal (reusing `format_report`-style rendering) and
   drives the raw-diff audit's allowed-byte set from journaled table offsets —
   the R11/R12 `_byte_offsets`/`_raw_diff_audit` logic generalized into the
   library.
3. **Pipeline = the R12 `main()` distilled and made generic:** apply BTP
   patches (optional, only if the tune declares them) → run journaled edits on
   the CalFile → staged saves (mirroring R11/R12's stage → slot-caps → TC-flags
   sequence where switchpatch is active) → checksum correction + verify →
   final-bin readback of every journaled table → raw-diff audit vs a declared
   reference bin → compare plots + report. Any failed gate raises; no partial
   success.
4. **Safety invariants live in the library:** guarded ceiling writes reuse
   `sop_recipe._guarded_ceiling_write` semantics; the airmass cap API takes
   **mg/stk** and converts to the kg/stk raw store internally
   (`C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint), making the
   2000-raw mistake unmakeable (AE5). Floor-not-round psi→hPa conversion is a
   library helper (AE2). Never flashes; never silently clamps.
5. **Profile maps are Python data files** (`tune/profiles/sc8s50.py`): a dict
   of logical name → (symbol-or-uid, plain-English description, units,
   optional guard tags). Adding an XDF = writing one map file. Resolution
   failures raise before any edit, listing every unresolved name plus
   `cal.search()` title suggestions (AE3).
6. **Equivalence gate before adoption (AE1):** `TUNE_Basics_Guide_R13.py`
   written in the new style must reproduce the R12 output bin byte-identically
   (timestamps/paths aside) against the same reference. Only after that gate
   passes does the new style become the authoring path.

## Implementation units

### U1. Profile + symbol resolution (`tune/profile.py`, `tune/profiles/sc8s50.py`)
- **Goal:** logical-name registry and fail-loud resolution against a loaded `CalFile`.
- **Requirements:** AE3; "any Simos 18 XDF" goal.
- **Dependencies:** none.
- **Approach:** `Profile` holds the map; `resolve(cal)` returns resolved views
  or raises `ProfileResolutionError` naming every miss with suggestions.
  Reuse `sop_recipe.resolve_symbol_map` patterns (`_resolve_one`,
  ambiguity handling). Seed the SC8S50 map with every symbol the R00–R12
  lineage touches (harvest from R03/R07/R08/R10/R11 constants + `SYMBOL_MAP`).
- **Tests:** resolves all seeded names on the real SC8S50 XDF; unknown name →
  loud error listing it; ambiguous symbol → error, never a guess; suggestions
  present when a near-title exists.
- **Verification:** unit tests green; map covers 100% of symbols referenced by
  later units (checked by a test that imports the domain modules' needs).

### U2. Journal + build pipeline core (`tune/journal.py`, `tune/project.py`, `tune/pipeline.py`)
- **Goal:** `Tune` object + `build()` producing bin, `report.md`, `compare/`
  PNGs, checksum verdict, readback, raw-diff audit — with no domain modules yet
  (raw `set_table`-style journaled escape hatch only).
- **Requirements:** AE4, AE6.
- **Dependencies:** U1.
- **Files:** new files above; small promotions in `simoscal`: make the
  R11 `_byte_offsets` / raw-diff-audit logic a public library helper
  (new `tune/audit.py` or `binimage` addition), reuse `compare_tables`,
  `verify_checksums`, `StaleChecksumWarning` handling from R12's `main()`.
- **Approach:** `Tune.open(profile, xdf, bin)`; edits go through the journal;
  `build(rev, out_root, reference_bin=None)` runs pipeline steps in fixed
  order, returns a `BuildResult`; any gate failure raises with the R12-style
  problem list. Timestamped `R<NN>_<stamp>` output folder matching the
  existing convention.
- **Tests:** happy path on stock bin with one journaled edit (artifact set
  complete, checksums CLEAN, journal rendered with `` `ID` — Description``
  before/after); raw-diff audit flags an unexplained byte (fault-injected via
  `tests/faultinject.py` conventions); stale-checksum path fails loud; build
  with zero edits still verifies and reports.
- **Verification:** AE4/AE6 acceptance tests pass on the real stock bin.

### U3. Core domain modules: `boost`, `wastegate`, `limits`
- **Goal:** the domains the lineage iterates on, distilled from R03–R10 helpers.
- **Requirements:** AE2 (psi→hPa floor helper), AE5, module-scope table.
- **Dependencies:** U1, U2.
- **Files:** `tune/domains/boost.py`, `wastegate.py`, `limits.py`; extend the
  SC8S50 profile map as needed.
- **Approach:** distill, don't rewrite: `boost` covers PUT setpoint
  ceiling/curves (`IP_PUT_SP` — Pressure up throttle setpoint), pressure
  limiters, `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbo
  charger compressor (from R10's `_apply_r10_pq_cha_max`), airmass cap
  (mg/stk API per decision 4). `wastegate` covers the
  `IP_FAC_BPA_SP[0]/[1]` — Map for boost pressure actuator setpoint overlay
  (from R08). `limits` covers guarded ceiling raises + torque/limiter scalars
  (bridging `sop_recipe` kinds where the basics SOP is invoked, adapting
  `TableOutcome` → journal entries).
- **Tests:** each method journals correctly with physical units; guarded
  ceiling refuses to lower; airmass cap given 2000 mg/stk writes raw 0.002 and
  given a raw-looking value ≥ guard threshold fails loud; wastegate overlay
  reproduces R08's cell deltas on the real bin.
- **Verification:** table-level value comparison against the corresponding
  historical revision outputs for each distilled helper.

### U4. Remaining domains: `fueling`, `ignition` + basics-SOP bridge
- **Goal:** lambda/fueling and ignition grids; expose the R00–R06 basics
  recipe as one journaled pipeline step so a flat script can declare it.
- **Requirements:** module-scope table; AE1 needs it (R12 inherits the R06 pipeline).
- **Dependencies:** U2 (journal adapter), U3 patterns.
- **Files:** `tune/domains/fueling.py`, `ignition.py`, plus the SOP bridge in
  `pipeline.py` or `limits.py`.
- **Approach:** `fueling` covers `IP_LAMB_BAS[1]` — Basic lambda setpoint grid
  (HPDI) literal-grid writes with axis matching (reuse
  `KIND_LITERAL_TABLE` axis-guard semantics), pedal threshold
  `ID_PV_AV_FL` — Pedal value threshold, lambda-floor tables (R03). `ignition`
  covers the base timing grids the SOP touches. SOP bridge:
  `tune.apply_basics_sop()` runs `sop_recipe` and folds its `RecipeReport`
  outcomes into the journal (coexist decision).
- **Tests:** literal grid with mismatched axes fails loud (no write); SOP
  bridge journal contains one entry per recipe outcome incl. skips; lambda
  cell writes match R03 values on the real bin.
- **Verification:** journal from `apply_basics_sop()` reconciles 1:1 with
  `format_report(recipe)` content.

### U5. `switchpatch` domain module
- **Goal:** first-class BTP switch-patch support: patch application, slot PUT
  curves, TC flags, sanity — distilled from R07/R11/R12 helpers.
- **Requirements:** module-scope decision "Also switch-patch slots"; AE1.
- **Dependencies:** U2; independent of U3/U4 internals.
- **Files:** `tune/domains/switchpatch.py`; profile additions for the
  switch-patch XDF (`S50 Switch Patch.29.33.V2.xdf`) as a second profile map.
- **Approach:** wrap `btp.apply/check/switch_patch_sanity`; slot curve API in
  hPa-or-psi with the R11 `_resample` + floor conversion helpers; per-slot
  validation generalized from `_validate_r11_configuration` /
  `_validate_r12_configuration` (flat-cap check, ambient/ceiling bounds,
  untouched-slot equality); TC flag writes from R07's `_write_tc_flags` with
  readback. Pipeline staging order preserved (stage → caps → TC flags).
- **Tests:** slot cap above shared ceiling fails loud; editing slot 5 leaves
  slots 1–4 bit-identical; TC flags readback 10/10; sanity result journaled;
  psi cap of 10.0 floors, never rounds up.
- **Verification:** slot-grid bytes match R11/R12 reference bins for the same
  declared curves.

### U6. Equivalence harness: `TUNE_Basics_Guide_R13.py` (root repo)
- **Goal:** prove AE1 — a flat, new-style, zero-cross-import R13 reproduces
  the R12 bin byte-identically; then it becomes the live authoring template.
- **Requirements:** AE1, AE2, key flow 1.
- **Dependencies:** U3, U4, U5.
- **Files:** `Tunes/TuningBasicsGuide/TUNE_Basics_Guide_R13.py`,
  `Tunes/TuningBasicsGuide/REV_LOG.md`, cumulative header per the
  revision-tracking convention;
  `Code/tests/test_acceptance_tune.py` gains the equivalence test (skipped
  when the reference bin is absent, like existing real-bin acceptance tests).
- **Approach:** R13 declares the full R00–R12 calibration via domain calls +
  `apply_basics_sop()` + switchpatch slots, `build("R13",
  reference_bin=<R12 output>)`; byte-compare vs the R12 reference
  (`CB_HSL_SP2933_..._R12.bin`) allowing only CAL_CRC-equivalent zero diff.
  Any diff is enumerated by the audit and must be explained or fixed before
  the unit closes.
- **Tests:** the equivalence test itself; R13 script contains no imports from
  `TUNE_Basics_Guide_R*` modules (asserted in the test).
- **Verification:** byte-identical output (or empty unexplained-diff set with
  every allowed diff documented in the report); human review of R13's
  readability — it should fit ~1 page of domain calls.

### U7. Human-facing docs
- **Goal:** the shareability deliverable — a human can author a revision from
  docs alone.
- **Requirements:** newcomer success criterion; key flows 1–3.
- **Dependencies:** U6 (documents the proven style).
- **Files:** `Code/README.md` (new § Tune API), a worked authoring guide
  (`Code/docs/` or README section): copy-previous-revision workflow, domain
  call reference, profile/map-file how-to for a new XDF, safety model pointers.
- **Tests:** none — documentation; correctness checked by U6's script matching
  the documented workflow.
- **Verification:** the doc's worked example is literally R13's content.

## Risks

- **AE1 byte-identity may be brittle** (encode/round paths differing between
  old helpers and new modules). Mitigation: distill helper math verbatim
  first, refactor style second; the raw-diff audit pinpoints any divergence to
  exact table offsets.
- **Over-abstraction of thin domains** (`ignition` has little lineage): keep
  those modules minimal wrappers; don't invent API surface without a use.
- **Real-bin tests** need `Code/bin/` + `BinToolz-main/` present; follow the
  existing skip-if-absent acceptance-test convention.

## Verification (end-to-end)

1. `pytest Code/tests` — new unit + acceptance tests green, existing suite
   untouched-green.
2. Run `TUNE_Basics_Guide_R13.py`; confirm artifact set, checksums CLEAN,
   raw-diff audit vs R12 reference = 0 unexplained bytes, byte-identity per U6.
3. Human review gate unchanged: Sam reviews R13's report + compare PNGs; the
   bin is NOT flashed as part of this work (R13 is calibration-identical to
   R12 by construction).
