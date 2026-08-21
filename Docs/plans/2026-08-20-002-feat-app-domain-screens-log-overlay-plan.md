# App domain screens + log overlay — implementation plan

Date: 2026-08-20
Type: feat
Origin: `Docs/brainstorms/2026-08-20-app-domain-screens-log-overlay-requirements.md`
Depth: Standard–Deep (7 units, two repos)
Status: completed 2026-08-21 — branch `feat/domain-screens-log-overlay` in both repos

## Summary

Bring the boost-editor pattern to more of the tuning loop: overlay a logged
pull's actual boost and setpoint behind the slot curves being edited, and add
three purpose-built screens — Limiters, Pedal feel, Lambda enrichment — over
newly mapped specs and domain ops. Library work lands in the `simoscal` repo
(`Code/`), UI work in `simoscal-android`.

## Problem frame

The app edits well but tunes blind (no log context on the edit surface), and
the next domains' invariants — soft ≤ medium ≤ hard, quartet coherence, a
lean-danger direction — cannot be expressed by the generic grid. Full frame in
the origin doc.

## What research changed

The requirements doc's blocking questions are now mostly resolved by evidence:

- **Pull detection is already on-device.** `simoscal/analysis/pulls.py` is
  numpy-only (no matplotlib), `bridge._op_analyze_logs` is a sessionless op,
  and the app already has an AnalyzeScreen with SAF log import. The overlay
  needs no extraction work — only a lighter read path and a canvas layer.
- **Boost + setpoint series already exist.** `analysis/series.py` defines
  `_boost_fn` / `_boost_sp_fn` (gauge psi = PUT − ambient, same for setpoint)
  per pull against engine speed, in the `boost` PlotSpec. The overlay draws
  exactly these series — one implementation of the psi reframe.
- **Rev-limit tables located.** BinToolz `definitions/S50 Switch
  Patch.29.33.V2.xdf` (the parseable authority) carries `Rev soft limit above
  engagement point`, `Rev medium limit …`, `Rev hard limit …`, plus `Release
  RPM limiter speed` and `Timing during RPM limiter and rampout`. The 5×
  per-slot `RPM limiter` / `Speed limiter` tables are slot-owned and stay on
  the Slots screen — the Limiters screen owns only the non-slot set.
- **Speed limiter symbols resolve**: `LMVLim_vMax_vLim_C_VW.VehSpdl` (and
  siblings) exist in `SC8S50.V1.0.xdf`; exact quartet membership is confirmed
  at spec-writing time (U1).
- **A `Fueling` domain already exists** (`tune/domains/fueling.py`:
  `lambda_grid`, `lambda_floors`, `pedal_threshold`) and `tune/domains/
  limits.py` exists for ceilings. New ops extend these files — no new domain
  architecture.
- **Lean bound decided by Sam**: engine-side refusal of any full-load
  enrichment setpoint ≥ 1.00; UI warning band above 0.90.

## Requirements

AE1–AE8 from the origin doc, plus its Key Decisions (pattern reuse, read-only
overlay, one pull-semantics implementation, SAF per-file pick, owner
resolution, exclusions).

## Key technical decisions

1. **Overlay data comes from a new lightweight sessionless bridge op
   (`log_overlay`)**, not from re-running `analyze_logs`. It reuses
   `load_logset_files` + `detect_pulls` + the `boost` PlotSpec serialization
   and returns: pull list (gear, rpm span, duration, source file) and, per
   pull, the `boost` and `boost_sp` series. No battery, no findings, no
   session. Rationale: the battery is seconds of work the overlay doesn't
   need, and coupling BoostScreen to AnalyzeScreen state would make one
   screen's lifecycle a dependency of another's.
2. **Overlay state lives beside, never inside, the edit session.** No journal
   entries, no recovery-format change; a recovered session simply has no
   overlay loaded.
3. **Invariants are engine-side refusals; the UI clamps drags and surfaces
   refusals for typed values** — the established split. New engine guards:
   rev trio ordering (soft ≤ medium ≤ hard), speed-limiter quartet written as
   one call, lambda FL setpoint < 1.00.
4. **Pedal maps stay generically writable (dual-path).** The Pedal screen is a
   curve presentation over the existing `catalog`/`table_detail`/`edit` ops —
   no new domain op, no owner. The "stock ghost" is the session's **source
   values** (the imported bin), which `table_detail` already carries.
5. **Limiter and lambda-FL tables become domain-owned** (generic grid refuses
   them), resolving the coverage brainstorm's blocking `owner` question for
   these tables. The eventual coverage plan treats U1's specs as already done.
6. **Additive bridge ops, `BRIDGE_VERSION` not bumped** — same reasoning as
   the V8 `boost_rpm_axis` precedent: an older app never names a new op; a
   newer app on an older engine gets a clean `UNKNOWN_OP`.
7. **Lambda FL screen mirrors the boost canvas structure.** The enrichment
   table is 2D (rpm × time-at-full-load): the active time-row is the editable
   curve, the other rows render ghosted — the exact active/ghost interaction
   already proven on slots.

## Implementation units

### U1. Profile specs for limiters, pedal, lambda (library)

- **Goal:** Every table the three screens touch resolves through a
  `TableSpec` with correct units, shape, guard tags, and `owner`.
- **Requirements:** AE4–AE7 preconditions; origin Key Decision 5.
- **Dependencies:** none.
- **Files:** `simoscal/tune/profiles/sc8s50.py`,
  `simoscal/tune/profiles/switchpatch_2933.py`, `tests/test_profiles*.py`.
- **Approach:** Base space — the `LMVLim_vMax_vLim_C_VW.*` quartet (confirm
  membership against the XDF; record the hysteresis relationship in the spec
  docstrings), the nine `IP_FAC_TQ_REQ_DRIV_*` — Driver interpretation /
  pedal maps, and the `IP_LAMB_FL_SP*` — Lambda full-load enrichment set
  (main rpm×time map; the IAT-dependent map and increments/decrements are
  mapped but stay grid-editable). Patch space (addresses from the BinToolz
  V2 XDF only): rev soft/medium/hard above engagement, release speed, limiter
  timing. Owners: limiter set + lambda FL main map → domain-owned; pedal maps
  → none. Check each new float32 table against `FLOAT_BUG_SYMBOLS` criteria
  and every unit label against its stored scale (the kg/stk lesson).
- **Test scenarios:** each spec resolves at declared shape against the real
  XDFs (shape mismatch fails loud); domain-owned tables absent from
  `catalog()` without `include_domain_owned`; pedal specs present and
  reversible; a deliberate wrong-shape spec fixture is rejected at
  resolution.
- **Verification:** resolution test per spec green; catalog counts change by
  exactly the added non-owned specs.

### U2. Domain ops with engine-side invariants (library)

- **Goal:** The writes the screens will make exist as guarded, journaled
  domain calls.
- **Requirements:** AE4, AE5, AE7; Key Decision 3.
- **Dependencies:** U1.
- **Files:** `simoscal/tune/domains/limits.py`,
  `simoscal/tune/domains/fueling.py`, `tests/test_domains_*.py`.
- **Approach:** `limits.rev_limits(soft, medium, hard)` — writes the trio in
  one call, refuses unless soft ≤ medium ≤ hard and each is within declared
  bounds; `limits.speed_limiter(kmh, ...)` — writes the quartet coherently in
  one call (relationship encoded from U1's findings); optional single-value
  variants re-validate ordering against live values of the others.
  `fueling.full_load_enrichment(row, values)` — writes one time-row of the
  lambda FL map, refuses any value ≥ 1.00, reports requested-vs-encoded.
  All ops carry `intent=` and journal one entry per table written.
- **Test scenarios:** ordering violation refused with table + journal
  unchanged (atomicity); valid trio journals three entries; quartet partial
  write impossible (a rejected member rejects all); lambda 1.00 refused,
  0.999 accepted and encoded ≤ requested; bounds refusal on each table.
- **Verification:** focused domain suites green; full Python suite green.

### U3. Bridge ops (library)

- **Goal:** The Kotlin layer can read/edit the new domains and fetch overlay
  series, with stable error codes.
- **Requirements:** AE1, AE4, AE5, AE7; Key Decisions 1, 6.
- **Dependencies:** U2 (edit ops); U1 only for `log_overlay` (none — it is
  sessionless and calibration-free).
- **Files:** `simoscal/bridge.py`, `tests/test_bridge.py`.
- **Approach:** `log_overlay` (sessionless: verified log paths → pulls +
  per-pull `boost`/`boost_sp` series, reusing the analysis helpers — no
  battery); `limiters` (read all limiter values in one call, mirroring
  `slot_settings`' comparative-read rationale) and `limiters_edit` (routes to
  the U2 ops); `lambda_fl` read/edit likewise. Errors map to existing codes
  (`EDIT_REJECTED`, `ANALYSIS_ERROR`, `BAD_PARAMS`). No version bump.
- **Test scenarios:** overlay on a real-format fixture log returns pulls and
  both series, and gear attribution matches across a `Gear ()` and a
  `Gear (gear)` fixture of the same pull (AE2); overlay with an unreadable
  CSV returns `ANALYSIS_ERROR`; limiter edit violating ordering returns
  `EDIT_REJECTED` and a re-read shows unchanged values; session state hash
  identical before/after overlay calls (AE3's engine half); unknown-op name
  on an old engine stub returns `UNKNOWN_OP`.
- **Verification:** bridge suite green; op table documented in the bridge
  docstring.

### U4. Log overlay on the Boost screen (app)

- **Goal:** AE1–AE3 on the tablet: pick log → pick pull → actual + setpoint
  drawn behind the slot curves; provably inert.
- **Requirements:** AE1, AE2, AE3, AE8.
- **Dependencies:** U3.
- **Files:** `engine/src/main/java/com/simoscal/android/` — BoostScreen/
  BoostCanvas/BoostUiState + new `OverlayUiState.kt`; reuse the existing SAF
  import path from the Analyze flow; unit tests beside existing ones.
- **Approach:** "Overlay log" action on BoostScreen → SAF pick →
  `log_overlay` → pull chooser (gear, rpm span, duration) → traces rendered
  in the canvas's existing psi/rpm coordinate space (solid actual, dashed
  setpoint, visually subordinate to the editable curves). Overlay survives
  slot switches and drafts; one-tap clear; not persisted with recovery.
- **Test scenarios:** coordinate mapping puts overlay samples at the same
  x/y transform as curve points (shared `BoostPlot` math); overlay present →
  state gates unchanged (`exportVisible`, `canApply` unaffected); clearing
  restores prior render state; pull-chooser formats gear per the header rule
  as delivered by the engine (no gear math in Kotlin).
- **Verification:** `:engine:testDebugUnitTest` green; on-device: load an R14
  log over the real bin's curves and hand-check the trace against the
  desktop analysis PNG for the same pull; AE3 checked by building with and
  without an overlay loaded and comparing output hashes.

### U5. Limiters screen (app)

- **Goal:** AE4/AE5: the rev trio on one rpm strip with ordering enforced at
  the fingertip; the speed limiter as one control.
- **Requirements:** AE4, AE5, AE8.
- **Dependencies:** U3.
- **Files:** new `LimitersUiState.kt`, `ui/LimitersScreen.kt`; navigation in
  `SimoscalApp.kt`; tests.
- **Approach:** three markers on a horizontal rpm strip (drag clamps at the
  neighbor's value minus one step; typed violation surfaces the engine's
  refusal), engagement/release and timing values as labeled fields, the
  speed-limiter target + hysteresis as one grouped control. Staged draft →
  Apply → one `limiters_edit` call. Screen requires the patch space for the
  rev trio and degrades to base-only (speed limiter) without it.
- **Test scenarios:** drag clamp math (no reachable position violates
  ordering); typed refusal path renders reason; Apply sends one op with all
  changed values; base-only session hides the rev strip rather than erroring.
- **Verification:** unit tests green; on-device pull of the screen against
  the real patched bin shows current values matching the desktop read.

### U6. Pedal feel screen (app)

- **Goal:** AE6: pedal-% vs torque-factor curve editing with the source
  values ghosted.
- **Requirements:** AE6, AE8.
- **Dependencies:** U1 (specs); no new bridge ops.
- **Files:** new `PedalUiState.kt`, `ui/PedalScreen.kt`; navigation; tests.
- **Approach:** a curve canvas over the pedal-map family using existing
  `table_detail` + `edit` ops; table picker (sport/normal/drive-off maps);
  source values drawn as the ghost; drag/type/Apply staging identical to the
  boost editor; requested-vs-encoded from the edit result.
- **Test scenarios:** curve↔grid mapping round-trips (a dragged point edits
  exactly one cell); ghost always renders source, not last-applied draft;
  undo re-reads the open table (the V8 stale-grid rule).
- **Verification:** unit tests green; a pedal edit builds and byte-audits
  clean with only the intended table in the journal.

### U7. Lambda enrichment screen (app)

- **Goal:** AE7: the FL enrichment map as active-row curve vs rpm with the
  danger band; refusal ≥ 1.00 surfaced.
- **Requirements:** AE7, AE8.
- **Dependencies:** U3.
- **Files:** new `LambdaUiState.kt`, `ui/LambdaScreen.kt`; navigation; tests.
- **Approach:** rows = time-at-full-load, chips to select the active row,
  others ghosted (the slots interaction); warning band shaded above λ 0.90
  with copy explaining leaner-is-hotter; drag clamps at 0.99-and-a-step,
  typed ≥ 1.00 shows the engine refusal; Apply → `lambda_fl` edit per changed
  row.
- **Test scenarios:** no reachable drag position produces a value the engine
  refuses (the `maxSettablePsi` sweep pattern, for lambda); band renders from
  0.90 regardless of data range; typed 1.00 refused end-to-end; row switch
  with unapplied draft refused (the V8 rule).
- **Verification:** unit tests green; on-device read shows stock enrichment
  values matching the desktop decode.

## Scope boundaries

Out (per origin doc): pops & bangs, ignition editor, grid coverage shading,
whole-log scatter, folder watch, any in-app findings/verdicts on the overlay.

### Deferred to follow-up work

- The remaining ~73 coverage specs (the full-profile-coverage plan; it should
  subtract U1's tables from its counts).
- SCC threshold/duration surfacing (mapped later by the coverage plan; not on
  the Limiters screen).
- Two-pull before/after overlay; overlay on the lambda screen (logged lambda
  vs setpoint) — natural once U4's pattern exists.

## Risks & dependencies

- **Patch-space addresses must come from the BinToolz V2 XDF** — the curated
  copies do not parse (`uniqueid 0x11f9c` reuse). U1 must not touch them.
- **Quartet semantics unknown until U1** — if `LMVLim` members turn out to be
  more than a target+hysteresis pair-of-pairs, `speed_limiter()`'s signature
  is decided then; the screen contract (one coherent control) stands.
- **Lambda FL map shape** — if the real table's time dimension differs from
  the assumed rows, U7's row-chip design flexes; the invariant and band do
  not.
- **Two-repo coordination** — U1–U3 land in `Code/` first and the app builds
  against the working-tree wheel; no app unit starts before its bridge op is
  merged.
- Safety: every new write path goes through specs + domain guards + the
  unchanged build/audit chain; the overlay is read-only by construction and
  AE3 is tested, not assumed.

## What execution changed

Four things the plan got wrong or left open, resolved against the evidence
rather than the assumption:

1. **The rev trio is not a rev limiter.** The plan framed
   `Rev soft/medium/hard limit above engagement point` as absolute rev limits on
   an rpm strip. The XDF says otherwise: all three are rpm *offsets above an
   engagement point*, and all three sit in the patch's **RAL** category beside
   `Minimum engagement RPM` (2500) and `Maximum engagement RPM` (4500). The
   escalating cut pattern is documented per level, which is what makes
   `soft ≤ medium ≤ hard` a real invariant — so the ordering guard and the strip
   both stand, but every description and the screen's own copy say what these
   actually are. Stock reads 0 / 64 / 64 rpm, so **equal neighbours are legal**
   and the rule is `≤`, not `<`. `Timing during RPM limiter and rampout` and
   `Release RPM limiter speed` turned out to be **LC** (launch control), not part
   of the trio; they are mapped, generically editable, and shown read-only on the
   screen with a pointer to Tables.
2. **The speed-limiter quartet has no hysteresis.** The plan flagged its
   membership as a blocking unknown and hedged `speed_limiter()`'s signature on
   it. The XDF defines exactly four `LMVLim_vMax_vLim_C_VW.*` scalars — the three
   levels and the not-active value, all stock 200 km/h — and no hysteresis
   sibling, so the call takes one km/h figure and writes all four.
3. **`table_detail` did not carry source values.** Key Decision 4 asserted it
   already did; `TableInfo` only ever held current values, so the pedal screen's
   stock ghost had nothing to draw. Added as `source_values`, decoded from the
   tune's pre-write `source_snapshot` through the live space's own XDF model, and
   carried by `table_detail` only — `catalog` would pay for it on every browse.
4. **The lambda warning band could not be driven by the whole curve.** Stock is a
   flat 1.00 map, so every point of an untouched row is already above λ 0.90 and
   the warning fired the moment the screen opened. A warning that always fires is
   one people stop reading, which is the worst habit to teach about this band, so
   the card names only points *this draft* moved into it and the standing state
   gets its own calmer line. Found by a failing test, not by review.

Also fixed in passing: six axes arrived uncurated with the new specs (they would
have shown raw A2L symbols over columns of numbers on the tablet), and the
Limiters screen shipped its Apply without invalidating a completed build.

## Handoff

Execute with `/ce-work` pointed at this file, unit order U1 → U7 (U4 may run
in parallel with U5–U7 once U3 lands). Engine/safety units (U1–U3) stay with
the driver model; screens (U4–U7) are delegable under review, per the v1
plan's delegation pattern. Point subagents at the repo boot docs; the lean
bound (refuse ≥ 1.00, warn > 0.90) and the BinToolz-XDF-only rule must be
restated inline in any delegated prompt.
