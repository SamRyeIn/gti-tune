# Simoscal Quick Edit — v1 (personal) implementation plan

Date: 2026-07-21
Type: feat
Origin: `Docs/brainstorms/2026-07-21-simoscal-android-app-requirements.md`
Supersedes: `Docs/plans/2026-07-21-001-feat-simoscal-android-app-plan.md`
  (that plan is retained as the Phase 2 / public-release reference)
Depth: Medium (9 implementation units)
Status: proposed

## What changed from the 001 plan, and why

The 001 plan built the community product in one pass: 15 units spanning a Room
database, a byte-identical-forever recipe/replay engine, projects, portable
bundles, a curated influence registry, in-app log analysis, a generic-XDF write
path, and an OSI-licensed Play Store release. That is a year-plus of work aimed
at a community that does not exist yet, layered onto a tool that today has one
user tuning one car.

This plan does the smallest thing that delivers real value: **Quick Edit for
Sam's own GTI**. Import a bin and XDF, make a small deliberate edit in physical
units — with an interactive per-slot boost-curve editor as the hero surface —
run the existing verification pipeline, and share a checksum-clean bin to
SimosTools for flashing. Everything that only matters for strangers is deferred
to Phase 2, gated on "v1 went well."

Nothing in this plan flashes an ECU.

### Cut from v1 (deferred to Phase 2 — public release)

- Projects, cumulative recipe snapshots, revision lineage, byte-identical
  rebuild-across-versions (001 U4, U12). v1 has one recoverable edit session.
- Curated finding-to-calibration influence registry (001 U7, U13).
- In-app log analysis battery (001 U7, U13). Log review stays on desktop for
  now; v1 is edit-only. (First Phase 2 candidate — see "Natural Phase 2 order".)
- Generic-XDF **write** path (001 profile-support). v1 is SC8S50-only; other
  XDFs are not writable. This removes the highest-liability surface.
- Portable project bundles (001 U9, U12).
- OSS licensing audit, git-history scrub, Play Store release (001 U14).
- Tablet multi-pane adaptive layout as a hard requirement (001 U10). v1 targets
  a phone; it stays responsive but is not held to feature-parity screenshots.
- Kotlin safety-kernel port evaluation. v1 uses Chaquopy (see V0 rationale);
  the Kotlin-kernel question is re-opened only at the public-release gate, where
  APK size and cold-start actually matter.

### Kept, because it is real work that pays off regardless

- Break import-time / matplotlib coupling so the engine is embeddable (V1).
- Deterministic compatibility preflight that blocks unusable bins (V2).
- Renderer-independent build service returning a report model, not PNGs (V3).
- The full existing safety gate chain: immutable source, checksum correct +
  independently verify, readback, byte audit, no export until verified.

## Current-state evidence (verified 2026-07-21)

- `Code/` is the independent `simoscal` repo (remote `SamRyeIn/simoscal`,
  **private**). It stays private for v1. Public-release history audit is Phase 2.
- Engine is ~19.4k lines of Python. The safety-critical kernel is small:
  `xdf.py` (520), `codec.py` (179), `calfile.py` (366), `checksum.py` (392),
  `model.py` (408), `safety.py` (154), plus writer/binimage — ~2.5k lines. The
  bulk (analysis `checks.py` 1041 / `evidence.py` 837 / `log.py` 553,
  `sop_recipe.py` 1466, `report_html.py` 740, `plot.py` 781, `btp.py` 689) does
  **not** need to run on the phone for Quick Edit.
- Heavy-dep coupling is narrow and splittable: matplotlib in 3 files
  (`plot.py`, `analysis/evidence.py`, `tune/report_html.py`), openpyxl in 1
  (`export.py`), scipy in 0. numpy is in 26 files and is unavoidable (Chaquopy
  ships numpy).
- The switch-patch boost machinery the hero feature needs already exists:
  `tune/domains/switchpatch.py` — `slot_curve(slot, psi=[...per rpm...])` writes
  a per-rpm cap tiled across the 8×12 grid; `slot_rpm_axis()` edits the shared
  12-point X axis; `_check_below_base_ceiling()` enforces the min() invariant.
  Profile constants live in `tune/profiles/switchpatch_2933.py` (5 slots, grid
  shape `(8, 12)`, `SLOT_DEFAULT_HPA = 4000.0`).
- The edit-session abstraction the 001 plan called missing already exists:
  `tune/project.py`'s `Tune` class *is* the in-memory journaled session (every
  `Tune.write` stages bytes and journals the edit as one operation), and
  `sop_recipe.py` (1466) already demonstrates a recipe-as-reviewable-data
  pattern (`RecipeEntry`). So V4 is recovery-persistence only, not a new engine,
  and any Phase 2 general-recipe work starts from these files, not greenfield.
- No Android project, Gradle config, or app code exists in either repo today.

## Key design decisions

1. **v1 is personal and private.** Success criterion is "Sam uses this on the
   GTI instead of TunerPro-on-desktop," not "the community adopts it." Public
   release is a separate later decision with its own gate.
2. **Chaquopy for v1, no Kotlin port.** For a single trusted user, embedding the
   already-trusted Python engine is the fastest path to a tool Sam can rely on,
   and it takes zero risk with the safety math. The known costs — tens-of-MB APK,
   multi-second cold start, an ABI/16 KB-page treadmill — are tolerable on your
   own phone in a garage. Those costs matter for a broad audience, so the Kotlin
   kernel is re-evaluated at the public gate, not now.
3. **SC8S50-only, no generic writes.** v1 reads/edits only tables the SC8S50 +
   switch-patch profiles resolve exactly. Any other XDF is inspect-only. This
   keeps your curated safety knowledge always in force and removes the
   stranger-with-a-random-XDF hazard entirely.
4. **One recoverable edit session, not a project model.** Quick Edit keeps an
   in-memory journaled session, persisted enough to survive process death and
   app restart. No cumulative replay, no cross-version byte-identity guarantee.
   "Reproducible" in v1 means "re-openable and byte-identical within this engine
   version," which is all a personal tool needs.
5. **Engine stays authoritative; Kotlin owns lifecycle/UI/files only.** No bin
   math in Kotlin. Kotlin copies user-selected files into app-private immutable
   storage, hashes them, and passes absolute private paths to Python. Python
   never touches an Android URI.
6. **Computation separated from rendering.** Python returns report/table/curve
   *models*; Compose draws them. Desktop matplotlib/openpyxl paths stay optional
   and are not in the mobile dependency closure.
7. **No network or vehicle permissions.** Manifest omits Internet, Bluetooth,
   location, USB, CAN. Asserted in a test.
8. **The safety gate chain is non-negotiable and unchanged.** Immutable source,
   checksum correct + independent verify, per-edit readback, byte audit against
   the source, and export gated on the verified state. Boost is the most
   dangerous domain (overboost), so the hero feature's invariant enforcement and
   the build audit are load-bearing, not decoration.

## Hero feature — interactive per-slot boost-curve editor

A visual, draggable version of the `r09_boost_curves.png` compare plot, styled
like the five-slot reference (dark canvas, one colored curve per slot, direct
end-of-curve labels rather than a legend — matching the project's label-curves
convention). It is the showcase of Quick Edit and the thing a generic grid
editor does badly.

### What it edits (all through existing APIs)

| On-screen                      | Engine call                                   | Table(s)                                                  |
| ------------------------------ | --------------------------------------------- | --------------------------------------------------------- |
| Drag a slot's curve point      | `switchpatch.slot_curve(slot, psi=[...])`     | `slot{N}_put_setpoint` — PUT setpoint grid for slot N     |
| Flat-cap a whole slot          | `switchpatch.slot_curve(slot, psi=<scalar>)`  | same, tiled across all 8 rows                             |
| Move an rpm breakpoint (Adv.)  | `switchpatch.slot_rpm_axis([...])`            | `slot_put_rpm_axis` — shared RPM breakpoints              |
| Base ceiling reference line    | read-only unless edited                       | `IP_PUT_SP` — Pressure up throttle setpoint (full-load)   |

### Behavior

- **Axes:** X = engine speed (the 12 shared breakpoints), Y = boost gauge (psi).
  Points sit on the breakpoints; the curve segments interpolate between them.
- **Five named slots** (e.g. `1 Stock(ish)`, `2 Conservative`, `3 Intermediate`,
  `4 Aggressive`, `5 Valet`) as distinct colored curves with direct labels at the
  right edge. Slot names are a v1 UI convenience mapping to slots 1–5; they are
  presentation only and do not change the recipe.
- **Active vs ghosted:** the selected slot's 12 points are draggable; the other
  four render ghosted for context. Tapping a label/chip switches the active slot.
- **The min() semantics made visual.** The base `IP_PUT_SP` full-load ceiling is
  drawn as a distinct line, and the region above it is shaded "capped by base —
  unreachable." A slot point dragged into that region snaps to (or warns at) the
  ceiling, because the effective target is `min(base, slot)`. This is
  `_check_below_base_ceiling()` turned into a tactile guard, so the safety
  invariant is enforced *at the fingertip*, not just at build time.
- **Precision:** tap a point for numeric entry; drag snaps to 0.1 psi. psi is
  **floored, never rounded up** (the `slot_curve(rounding="floor")` contract), so
  a cap asked as "20 psi" cannot encode above 20. Show requested-vs-encoded when
  quantization bites.
- **Bulk moves:** drag the whole active curve up/down; copy one slot's curve onto
  another; smooth; undo/redo. Each committed change is one journaled recipe op,
  flowing through the same build → verify → audit as any edit.
- **Advanced only:** editing the shared rpm breakpoints (re-breakpoints *all*
  five slots at once — the code enforces strictly-increasing X).
- **Prettier than the PNG:** theme-aware, filled area under the active curve,
  clean ghost/active states, the base-cap band, smooth 60fps drag.

```text
 Boost — gauge (psi)                                   Slot: [1][2][3][4][●5●] 
 26 |            ●━━━━●━━━━━━━━●                        4 Aggressive (active)
 24 |●━━━●━━━━━●          ╲    ╲●                       ── base ceiling (IP_PUT_SP)
 22 |  ╲   ╲       ╲          ╲   ╲●                    ▓ region above = capped
 20 |·····●·············●·········· base ceiling ·····  
 18 |        ·. ghosted slots 1–3 .·        ╲●          [ Copy from… ][ Flat ]
 16 |                                                    [ Smooth ][ Undo ][Redo]
 10 |●━━━●━━━●━━━●━━━●━━━●━━━●━━━●━━━●  5 Valet          Point @4400rpm: 26.0 psi
    +--------------------------------------------       (encoded 25.98 psi)
     3.0k     4.0k     5.0k     6.0k    6.5k  rpm
```

## Implementation units

### V0. Runtime feasibility gate (Chaquopy)

- **Goal:** Prove the Python engine runs in an Android app with byte-for-byte
  parity before any UI work.
- **Dependencies:** none.
- **Files:** new `Code/android/settings.gradle.kts`, top-level Gradle + wrapper,
  `Code/android/engine/` (one Chaquopy library module), a diagnostic screen,
  instrumentation harness.
- **Approach:** pin JDK, Android SDK, AGP, Kotlin, Compose, Chaquopy 17, Python
  3.13. Bundle `simoscal` + the minimal dep closure (numpy, not matplotlib).
  On arm64 + x86_64: open the real SC8S50 XDF/full bin, enumerate tables, verify
  checksums, do a copy-on-write single-cell edit, correct + reverify checksums,
  and run `slot_curve()` once. Compare Android output to host Python
  byte-for-byte and field-for-field. Measure cold start, peak memory, APK size,
  full-XDF parse time, 16 KB-page behavior.
- **Go/no-go:** continue only if Android produces identical bytes, checksum
  verdicts, and decoded values. If native loading or parity fails, stop and
  write a decision doc (this is where the Phase 2 Kotlin-kernel option would be
  pulled forward — do **not** start a piecemeal port).
- **Verification:** emulator + one physical arm64 device; host/Android golden
  comparison committed with legal synthetic fixtures; strict local run against
  the real files.

### V1. Portable package boundary

- **Goal:** Make the engine embeddable without dragging matplotlib/openpyxl or
  import-time side effects onto the phone.
- **Dependencies:** V0.
- **Files:** `Code/pyproject.toml`, `simoscal/__init__.py`, analysis/tune
  `__init__` modules, the 3 matplotlib files + `export.py`, packaging tests.
- **Approach:** split core deps from `[plot]`/`[export]` extras; remove eager
  top-level imports so parsing/editing/checksums/build/analysis import without
  matplotlib or openpyxl; keep desktop PNG/xlsx behavior via lazy imports; pin a
  reproducible Python/NumPy proven in V0; add installed-wheel tests so the mobile
  artifact can't silently omit a module.
- **Verification:** core wheel installs and passes without matplotlib/openpyxl;
  desktop extras still pass; embedded smoke test imports only the mobile closure.

### V2. Compatibility preflight (SC8S50-only)

- **Goal:** Block an unusable input before an edit session exists; recognize the
  SC8S50 + switch-patch profiles exactly.
- **Dependencies:** V1.
- **Files:** new app-neutral preflight/provenance module under `simoscal/`,
  profile identity checks, checksum/XDF tests, bridge fixtures.
- **Approach:** return a structured verdict (size, hashes, XDF region, parse,
  CAL CRC + ECM3 recognizability/currentness, profile match, reversible-write
  capability, plain-language reason, advanced details) **without modifying the
  source**. Recognize SC8S50 by explicit profile identity + required symbol/shape
  checks, never filename/fuzzy title. Separate stale-but-correctable checksum
  (reportable) from unrecognized layout (blocks). Re-running with a replacement
  file retains no state from the rejected one. No "Continue anyway" path.
- **Verification:** valid full bin; CAL-only; truncated; malformed CAL CRC;
  missing ECM3; mismatched/corrupt XDF; stale-correctable; as-patched vs
  unpatched (switch-patch present/absent); non-SC8S50 XDF is inspect-only.

### V3. Renderer-independent build service

- **Goal:** Run the full gate chain and return a report *model*, no matplotlib.
- **Dependencies:** V1, V4, V5.
- **Files:** refactor `simoscal/tune/pipeline.py`; audit/journal/report modules;
  new app build-service module; build tests.
- **Approach:** separate mandatory verification from optional plot/HTML render.
  Accept explicit source/reference/output paths (no repo-folder inference). Write
  to private staging, correct checksums, reopen the actual file, run readback +
  post-save checks, byte-audit against the source with allowances derived from
  journal entries + stored checksum bytes; any unexplained byte blocks the
  verified state. For v1, the imported bin is both baseline and byte-audit
  reference. Return one machine-readable report model for the Compose review UI.
  Expose save/share only after every gate passes.
- **Verification:** happy Quick Edit; boost-curve edit; checksum unrecognized;
  readback fault; unjournaled byte blocks export; failed build has no shareable
  bin; identical inputs rebuild byte-identical.

### V4. Session recovery persistence (recovery-only)

- **Goal:** Make an open Quick Edit session survive process death and app
  restart. The session model itself already exists and is **not** rebuilt here.
- **Reconciliation (already done):** `tune/project.py`'s `Tune` class *is* the
  in-memory journaled edit session — it binds a bin to its table spaces and
  every `Tune.write` stages bytes and journals the edit as one inseparable
  operation via `tune/journal.py`. `sop_recipe.py` separately demonstrates the
  recipe-as-reviewable-data pattern (`RecipeEntry` dataclasses + resolver +
  applier), scoped to the tuning-basics guide. So the ordered-operation log,
  journaling, and edit/record coupling V4 needs already work; the only missing
  piece is durable recovery. (Corrects the 001 plan's "no session abstraction"
  premise — do not build a new one.)
- **Dependencies:** V2.
- **Files:** small recovery-persistence layer over the existing `Tune` +
  `journal.py`; Android-side session store (V7 wires it in); session tests. No
  new session/recipe abstraction.
- **Approach:** serialize the live `Tune`'s source provenance + ordered journal
  to durable storage and restore it into an equivalent live `Tune`; drive
  undo/redo off the existing journal; no cumulative-replay and no cross-version
  byte-identity promise. If a general recipe format is ever wanted (Phase 2),
  copy `sop_recipe.py`'s `RecipeEntry`-as-data pattern rather than inventing one.
- **Verification:** serialize → restore reproduces the same live session and
  pending edits; recover after simulated process kill mid-edit; undo/redo
  restores prior state; source hash unchanged throughout.

### V5. Generic + boost-curve edit operations (engine side)

- **Goal:** The app-neutral editing behavior Quick Edit needs, including the
  boost-curve ops — no raw byte writes.
- **Dependencies:** V4.
- **Files:** `simoscal/calfile.py`, tune/session, `domains/switchpatch.py`,
  `domains/boost.py`, writer/safety helpers, new editor tests.
- **Approach:** read-only table catalog + detail models keyed by exact
  ID/symbol/description; journaled generic **axis** writes (today `TableView`
  only exposes Z); set/add/sub/mul/div/fill/interpolate/paste/restore/undo as
  recipe ops over explicit selections; atomic batch (a rejected value leaves
  table + journal unchanged); report requested-vs-encoded. Surface the
  switch-patch ops as first-class: per-rpm `slot_curve`, flat cap, `slot_rpm_axis`
  (Advanced), the below-base-ceiling guard, and a `base ceiling` read for the
  reference line. Non-reversible tables stay read-only; keep raw/address/equation
  readable but with no write command.
- **Verification:** scalar/1D/2D/axis/shared-axis/nonlinear/zero-slope; float-bug
  guard; atomic multi-cell failure; undo/redo; **boost-curve suite** — per-rpm
  curve tiles across 8 rows, psi floored, below-base-ceiling rejected, rpm-axis
  strictly-increasing enforced, requested-vs-encoded reported; source immutable.

### V6. Versioned Python↔Kotlin bridge (v1 surface)

- **Goal:** One stable boundary exposing only the operations v1 uses.
- **Dependencies:** V2–V5.
- **Files:** Python bridge module; `Code/android/engine/` Kotlin facade +
  result types; contract fixtures; host + instrumentation tests.
- **Approach:** coarse ops — preflight, session create/recover, table
  catalog/detail, edit/undo, **boost-curve read/edit**, build, report. Versioned
  request/result envelope with deterministic serialization; bins/logs stay
  private files passed by verified path + hash, never base64. Known failures →
  stable error codes + plain/advanced detail; tracebacks only in private debug
  logs. Serialize calls on a background dispatcher so build/edit never blocks
  Compose or races the session. No `PyObject`/numpy/exceptions cross into UI.
- **Verification:** parity fixtures per op; malformed request; schema mismatch;
  missing private file; concurrent-request attempt; exception mapping; restart +
  recovery.

### V7. Android shell + Quick Edit flow

- **Goal:** Import → preflight → edit → review → share, on a phone.
- **Dependencies:** V6.
- **Files:** Compose shell, navigation, theme, SAF import, `FileProvider`
  share, minimal Room (or DataStore) for session recovery, mode toggle, UI tests.
- **Approach:** landing = Quick Edit (dominant), plus recent-session recovery.
  Sequential, replaceable bin then XDF selection via the Storage Access
  Framework (no broad storage permission); stream into a fresh app-private hashed
  copy; never edit a URI in place. No session until both pass preflight; an
  unusable input shows a non-dismissible blocker with **Choose another bin** /
  **Cancel**, never Continue-anyway. Workspace destinations: Tables, Boost, Build.
  `Simple | Advanced` toggle changes visible controls only, never gates. Build
  screen shows changed tables, gate states, and the "software verification ≠
  mechanical safety" disclaimer; **Export/Share** appears only in the verified
  state and hands off to SimosTools via the share sheet. Manifest omits
  network/vehicle permissions.
- **Verification:** airplane-mode import/edit/export; process kill during copy/
  edit/build recovers cleanly; blocker has no bypass; export hidden until
  verified; manifest permission test; physical-device select + share of the real
  files.

### V8. Boost-curve editor UI + calibration editors

- **Goal:** The hero boost-curve surface plus the scalar/grid/axis editors.
- **Dependencies:** V7.
- **Files:** boost-curve Compose canvas + gesture/drag layer, slot chips + direct
  labels, base-ceiling band; scalar/line/grid/axis editors; batch controls;
  Compose + screenshot tests.
- **Approach:** render the five slots as directly-labeled colored curves on a
  theme-aware canvas; active slot draggable (12 points), others ghosted; base
  ceiling line + "capped above" band with fingertip enforcement of the min()
  invariant; tap-for-numeric-entry with requested-vs-encoded; flat-cap, copy
  slot→slot, smooth, undo/redo; rpm-breakpoint editing behind Advanced. Generic
  editors show source/proposed/delta, selection, units, encoded values, undo/
  redo, restore, validation. Every committed change → one journaled op via V5.
- **Verification:** drag maps to correct `slot_curve` values; ceiling guard
  blocks/snaps; psi floored; copy/flat/smooth/undo correct; screenshot tests
  light + dark; scalar/grid/axis editors round-trip; on-device pull on the real
  SC8S50 bin produces a verified boost-only diff, hand-reviewed against a desktop
  `simoscal` build of the same edit (parity).

## Natural Phase 2 order (only if v1 goes well)

1. **In-app log analysis** — the other half of the field loop; the boost-curve
   editor gains an overlay of the *logged* boost-vs-rpm trace on the curve you're
   editing (data + target on one canvas).
2. **Curated influence registry** — findings → relevant tables (001 U7/U13).
3. **Projects + revision lineage** — reconciled with `sop_recipe.py`/
   `project.py`, and with "reproducible" scoped to within-version unless a real
   need for cross-version replay emerges.
4. **Public release** — Kotlin-kernel re-eval, OSS license audit, **git-history
   scrub of the private `simoscal` repo before going public**, generic-XDF
   decision, tablet parity, Play upload.

## Validation strategy

- **Host Python:** full `Code/tests` suite green; focused suites for preflight,
  session recovery, the boost-curve ops, and renderer-independent build;
  installed-wheel tests core-only and with extras.
- **Android:** Gradle unit + lint; session-recovery tests; Compose navigation/
  editor/boost-curve tests; bridge + golden-parity instrumentation on x86_64
  emulator + arm64 hardware; process-death/rotation/low-storage recovery.
- **Cross-runtime gate (v1 scope):** for identical XDF + bin + session ops,
  host Python and Android must produce identical preflight verdicts/hashes,
  decoded values, byte-identical candidate bins, and identical checksum/readback/
  audit verdicts. No UI test substitutes for this.

## Risks and mitigations

- **Chaquopy startup/size** on a personal phone — acceptable for v1; V0 measures
  it; re-evaluated only at the public gate.
- **V0 native-loading failure** — hard go/no-go; fallback is the documented
  Kotlin-kernel decision, not a piecemeal port.
- **Boost is the overboost domain** — fingertip ceiling enforcement + build byte
  audit + verified-only export; "software verification ≠ mechanical safety"
  stated on the build screen; only logs validate a tune.
- **Stale recipe premise** — reconciled: `Tune` already is the journaled
  session, so V4 is recovery-persistence only and no recipe engine is built in
  v1.
- **Dirty nested repos** — start from recorded statuses, isolate each unit, never
  revert unrelated user work.

## Agentic coding implementation

This plan is meant to be executed by a fresh **Opus** driver session pointed at
this file, delegating the low-risk volume to **Sonnet** subagents. Match model
spend to the ECU-bricking risk of each unit, not to unit size.

- **Opus drives, and authors the safety-critical / architecture units directly:**
  V0 (feasibility gate — the un-choosable architecture bet), V2, V3, V5, V6
  (preflight, build service, edit ops incl. the boost-curve min() invariant and
  psi-floor math, and the Python↔Kotlin bridge contract). Anything touching bin
  bytes, checksums, or the boost ceiling stays with Opus.
- **Sonnet subagents take the tightly-specced volume:** V7, V8 (Compose shell,
  navigation, the boost-curve canvas/gestures, Gradle wiring, screenshot/UI
  tests) and the well-scoped V1, V4. The Opus driver reviews each subagent's
  output against that unit's Verification list before integrating.
- **Optional independent review:** run a different-family model (GPT-5.6 via the
  `codex:rescue` plugin) as an adversarial second pass on the byte-critical units
  (V0/V2/V3/V5/V6). A cross-vendor review catches different bugs — the same
  double-entry instinct recorded in the `transcription-verify-double-entry`
  memory, applied to the safety kernel. The cross-runtime golden gate is the
  objective judge, so it never matters whose code "wins" a disagreement.

**Subagents start cold — point them at the docs, and inline anything
memory-only.** The distinction that matters: the repo boot docs live *on disk*
and a subagent can read them when told to, but the driver's private auto-memory
(`~/.claude/.../memory/`) lives outside the repo and never transfers. So every
delegated task prompt must do two things:

1. **Point the subagent at the boot reading order for its unit** — project
   `CLAUDE.md`, `index.md`, `Code/README.md`, `Code/code_review.md`, and the
   specific module/docstring it will edit. The orchestrator names these; the
   subagent reads them.
2. **Restate inline only the safety facts that are memory-only** and not yet
   captured in a repo doc — plus the unit's acceptance criteria.

Most of the safety model is already repo-resident, so (1) covers it: the
`C_M_AIR_CYL_SP_MAX` kg/stk-not-mg/stk trap is in `CLAUDE.md` § Safety; the
below-base-ceiling invariant and the psi-floor rule are in `switchpatch.py`'s
docstrings; source immutability is in `CLAUDE.md` and `Code/README.md`. Where a
needed fact is memory-only, prefer **writing it into the repo doc first** (the
lesson of `boot-docs-and-subagent-lessons`: safety facts belong in repo docs
precisely because subagents don't inherit private memory) over leaning on the
task prompt. A wrong byte from a cold agent bricks the ECU exactly as fast as
one from the driver.

## Handoff

Begin only after Sam approves. Start a fresh Opus session pointed at this plan;
entry point is `/ce-work` with this file as the source. Execute **V0 first** and
report its parity result and measurements before V1–V8. Delegate per the
Agentic coding implementation section: Opus authors the engine/safety units,
Sonnet subagents take the UI and well-scoped units under Opus review.
