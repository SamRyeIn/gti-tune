# Simoscal Android app — implementation plan

Date: 2026-07-21
Type: feat
Origin: `Docs/brainstorms/2026-07-21-simoscal-android-app-requirements.md`
Depth: Deep (15 implementation units)
Status: proposed

## Summary

Build a free, open-source, offline Android app around the existing `simoscal`
engine. The primary flow is Quick Edit: select a compatible bin and XDF, make
guided or direct physical-unit edits, run the complete verification pipeline,
and share a new bin without creating a project. Users may attach Simos Tools
logs and convert the complete session into a project whose revisions are
cumulative recipe snapshots replayed from an immutable baseline.

The Android client will be native Kotlin with Jetpack Compose. It will embed
the existing Python engine behind a narrow, versioned bridge rather than
reimplementing calibration and safety logic in Kotlin. That choice is subject
to an explicit feasibility gate before feature development.

Nothing in this plan flashes an ECU.

## Current-state evidence

- `Code/` is the independent `simoscal` repository and the only repository
  suitable for a future public release. The root repository contains private,
  car-specific tuning work and must not contain the public app implementation.
- There is no Android project, Gradle wrapper, Android SDK configuration, or
  app code in either repository today.
- The existing Python engine already provides XDF parsing, reversible
  physical-unit writes, exact profile resolution, journaling, checksum
  correction and verification, final-file readback, byte-level auditing,
  deterministic log findings, and table-coverage calculation.
- The current tune API is imperative. It has no serializable recipe model,
  cumulative replay engine, or application-session abstraction.
- `TableView` writes Z values but has no generic public axis-writing API.
- `simoscal.analysis.evidence` and `simoscal.tune.pipeline` import matplotlib
  paths directly. The mobile runtime needs computation and verification to be
  separable from desktop PNG rendering.
- `simoscal.__init__` eagerly imports export, plotting, and analysis surfaces,
  which forces optional desktop dependencies into an embedded runtime.
- `Code/pyproject.toml` still declares a proprietary license, despite the new
  open-source product requirement.
- `Code/code_review.md` contains open High findings, including two current
  reviewer-report defects (`CR-20260720-05` and `CR-20260720-06`) and earlier
  acceptance-suite weaknesses. These must be resolved or explicitly dismissed
  before an Android release can claim the affected guarantees.
- Baseline verification on 2026-07-21: `554 passed`, with four expected
  `StaleChecksumWarning` instances, in 410.23 seconds using the current dirty
  `Code/` working tree. Existing changes remain user work.

## Scope boundaries

### In scope

- One public monorepo under `Code/` containing the Python package and Android
  client.
- Native Android phone and tablet UI with feature parity and adaptive layout.
- Quick Edit as the default landing action.
- Local projects, cumulative recipe snapshots, revision rebuilds, logs,
  findings, influence links, reports, and portable bundles.
- Simple mode for curated SC8S50 operations.
- Advanced mode for direct XDF-defined edits with reversible physical scaling.
- Exact, curated SC8S50 finding-to-calibration influence rules.
- Mandatory compatibility preflight and build gates.
- Secure local import, export, and Android share-sheet interoperability.
- A secondary host CLI/service surface only where needed to exercise the same
  application contracts outside Android.

### Out of scope

- Flashing, Bluetooth, CAN, ECU communication, or integration with private
  Simos Tools APIs.
- Cloud accounts, synchronization, telemetry, remote services, or a required
  network connection.
- AI-generated tuning advice, automatic target values, or automatic edits.
- Arbitrary bytes, raw-value writes, hex editing, or non-reversible XDF writes.
- Patch application requiring unsupported ASW/code checksum verification.
- Semantic finding guidance for profiles other than SC8S50.
- iOS or a desktop graphical client.

## Key design decisions

1. **Keep the safety engine in Python.** Kotlin owns Android lifecycle,
   persistence, file access, and presentation. Python remains authoritative for
   calibration parsing, edits, analysis, recipe replay, and verification.
2. **Use a feasibility-gated embedded runtime.** Start with Chaquopy in one
   Android library module. Chaquopy 17 supports Python 3.10–3.14, Android API
   24+, current Android Gradle plugins, Kotlin/Java calls, and byte-array
   exchange. The project does not proceed past U0 until real-file parity,
   dependency loading, memory, startup, and 16 KB-page compatibility pass.
3. **Use Kotlin and Jetpack Compose for the client.** Material 3 adaptive
   layouts change pane arrangement by window size while preserving identical
   capabilities on phones and tablets.
4. **Put the Android client in the public `Code/` repository.** Use
   `Code/android/app/` for the application and `Code/android/engine/` for the
   single Chaquopy-enabled Android library. Do not place app code in the private
   root repository.
5. **Define one versioned application contract.** Kotlin calls coarse Python
   operations through a bridge and receives deterministic, serializable result
   documents. Raw `PyObject`, numpy arrays, Python exceptions, and mutable
   engine objects do not cross into UI code.
6. **Pass private file paths, not storage URIs, to Python.** Kotlin copies
   user-selected content into app-private immutable storage, records its hash
   and provenance, and passes an absolute private path to the engine. Python
   never navigates Android shared storage directly.
7. **Persist metadata and artifacts separately.** Room stores projects,
   revisions, sessions, file provenance, findings, and artifact indices.
   App-private files store bins, XDFs, logs, recipes, reports, and build
   artifacts. Database rows point to stable internal paths and hashes.
8. **Use one recipe model for Quick Edit and projects.** Quick Edit starts an
   unnamed recoverable session backed by the same serializable recipe model.
   Conversion adds project metadata without translating or replaying edits.
9. **Rebuild cumulative revisions from an immutable baseline.** Each revision
   stores a complete ordered recipe snapshot plus schema, engine, profile,
   baseline, and XDF provenance. The previous revision is used only for
   comparison and byte audit.
10. **Separate computation from rendering.** Python produces findings, coverage,
    table comparison data, gate results, and report models. Compose renders the
    interactive UI. Host-only matplotlib/openpyxl features remain optional and
    are not required by the Android runtime.
11. **Treat app output as a state machine.** A session progresses through
    imported, compatible, edited, build-running, build-blocked, and verified
    states. Only the verified state exposes `.bin` save/share actions.
12. **Do not request network or vehicle permissions.** The release manifest
    omits Internet, Bluetooth, location, USB, and CAN-related capabilities.

## High-level architecture

```text
Android file picker / share sheet
              |
              v
Kotlin import layer ---- SHA-256 + immutable app-private copies
              |
              v
Room metadata <---- repositories ----> app-private project/session files
              |                              |
              v                              v
Jetpack Compose UI <---- Kotlin engine facade ----> Chaquopy bridge
                                                     |
                                                     v
                    Python simoscal application services
                    - compatibility preflight
                    - table catalog/read/edit
                    - recipe replay
                    - build verification
                    - log analysis + coverage
                    - influence rules
```

The Android layer never edits bin bytes itself. The Python bridge never opens a
user-facing URI or decides where an exported file is written.

## UI concept and reference applications

The closest existing mental model is ECULeg's calibration-table interaction,
Simos Tools' phone-in-the-car log workflow, and a modern Android adaptive
list/detail shell. No single reference app represents the complete product:

- [ECULeg](https://play.google.com/store/apps/details?id=com.app.eculeg&hl=en_US)
  is the primary interaction reference for cell selection, group arithmetic,
  axis editing, copy/paste, sizing, and undo in a mobile calibration grid.
- [Simos Tools](https://play.google.com/store/apps/details?id=com.app.simostools&hl=en_US)
  represents the existing field workflow in which the same Android device
  captures logs and then hands them to Simoscal for offline review.
- [Android adaptive app guidance](https://developer.android.com/develop/ui/compose/build-adaptive-apps)
  defines the layout model: one-pane navigation on compact windows and
  list/detail or supporting panes when more space is available.
- [Now in Android](https://github.com/android/nowinandroid) is a reference for
  Material 3 and Compose visual language, not for Simoscal's denser technical
  content.

The app should feel like a focused Android diagnostic tool that opens a dense,
spreadsheet-like surface only when the user reaches a calibration table. It
must not resemble a desktop tuning program compressed onto a phone.

### Landing and Quick Edit

Quick Edit is the visually dominant default action. Projects remain available
without adding setup friction to the field workflow.

```text
+--------------------------------+
| Simoscal                       |
|                                |
|  +--------------------------+  |
|  |        Quick Edit        |  |
|  |    Open a bin and XDF    |  |
|  +--------------------------+  |
|                                |
|  Open Project    New Project   |
|                                |
|  Recent                        |
|  Golf R - Rev 04               |
|  GTI quick edit                |
+--------------------------------+
```

Quick Edit leads through sequential bin and XDF selection. Compatibility
preflight runs before an editing session is created. An unusable input produces
a blocking explanation with Choose another bin and Cancel; it never exposes a
Continue anyway action. The resulting session remains recoverable and can be
converted into a project without changing its recipe or output bytes.

### Workspace and adaptive layout

The primary workspace destinations are Overview, Tables, Logs, and Build. A
compact phone uses bottom navigation and displays one primary pane at a time.
An expanded phone or tablet uses a navigation rail and shows related panes
together, such as a table list beside its editor or a finding beside its
evidence and calibration influences. Both layouts expose the same actions and
produce identical artifacts.

A persistent segmented control presents `Simple | Advanced` wherever its mode
affects available editing controls. Simple mode emphasizes supported domain
operations, important tables, warnings, physical units, and plain-English
descriptions. Advanced mode additionally exposes search and direct editing for
every safely reversible XDF-defined scalar, axis, curve, and grid. Switching
modes changes presentation and capability visibility only; it never changes
recipe data, validation, or build gates.

### Calibration editor

Every editor keeps the exact parameter ID, plain-English description, and
physical units visible. Source, Proposed, and Delta views share the same
selection so the user can inspect the consequence of an edit without losing
context.

```text
Wastegate base duty cycle
CWDIMX - Maximum WG duty cycle

[ Source ] [ Proposed ] [ Delta ]

          2000   3000   4000   5000
  40%     32.0   35.0   38.0   40.0
  60%     38.0  [42.0] [44.0]  46.0
  80%     43.0  [47.0] [49.0]  51.0

Selected: 4 cells       Current: 42-49 %

[ Set ] [ + ] [ - ] [ x ] [ Smooth ]
                  Undo
```

The editor supports tap, drag, and rectangular selection; direct value entry;
set/add/subtract/multiply/divide operations; interpolation and smoothing where
valid; copy/paste; restore; and undo/redo. Suitable tables can switch among
grid, curve, and heatmap presentations. Requested and encoded/readback values
remain distinguishable when quantization occurs. Users are never required to
write an intent for an individual edit.

### Log findings and calibration influences

Log review starts with data quality, selected pulls, and ranked deterministic
findings. Each finding shows observed evidence before listing relevant
calibration influences. Influence items are navigation aids, not prescribed
fixes, and never contain generated target values.

```text
Boost tracking performance                 Review recommended

Observed
- Overshoot near 3,900 RPM
- Slow recovery after throttle transition

Relevant calibration influences
> Wastegate base duty cycle
> Wastegate PID proportional term
> Requested boost curve
> Turbocharger protection limits
```

Each influence displays its exact parameter ID and description, why it matters,
applicability, and the logged region. Tapping it opens the normal calibration
editor with the finding retained as context. Returning to the finding indicates
which linked tables changed but does not imply resolution until new logs are
collected.

### Build review

Build is a review and verification destination rather than a generic save
button. It summarizes changed tables, before/proposed/delta values, warnings,
and every build gate. Save and share actions remain hidden until the verified
state.

```text
Build Rev 05

[pass] 4 tables changed
[pass] Values encode correctly
[pass] Output rereads correctly
[pass] Byte audit passed
[pass] Checksum verified

Software verification passed.
Mechanical safety has not been established.

[ Review Changes ]              [ Export bin ]
```

Flashing, ECU connectivity, and vehicle-control actions never appear in the
application.

## Implementation units

### U0. Toolchain and embedded-engine feasibility gate

- **Goal:** Prove the existing Python engine can run safely inside a modern
  Android app before committing to the architecture.
- **Requirements:** offline operation, shared engine, phone/tablet parity
  foundation.
- **Dependencies:** none.
- **Files:** new `Code/android/settings.gradle.kts`, top-level Gradle files and
  wrapper, `Code/android/engine/`, a minimal instrumentation harness, and CI
  bootstrap documentation. No production UI beyond a diagnostic screen.
- **Approach:**
  - Install and pin a supported JDK, Android SDK, emulator image, Android Gradle
    plugin, Kotlin, Compose, Chaquopy, and Python 3.13 build interpreter.
  - Apply Chaquopy in exactly one Android library module.
  - Bundle the local `simoscal` package and the smallest viable dependency set.
  - On arm64 and x86_64, open the real SC8S50 XDF/full bin, enumerate tables,
    verify checksums, perform a copy-on-write single-cell edit, correct and
    reverify checksums, and run one representative log-analysis fixture.
  - Compare Android outputs with host Python byte-for-byte and field-for-field.
  - Measure startup, peak memory, package size, full-XDF parse time, log-analysis
    time, and 16 KB-page behavior. Record measurements before choosing budgets.
- **Go/no-go:** Continue only if the Android runtime produces identical bytes,
  checksum verdicts, decoded values, and findings. If native dependency loading
  or parity fails, stop and write a replacement architecture decision; do not
  begin a Kotlin port piecemeal.
- **Verification:** instrumentation test on an emulator and one physical
  arm64 device; host/Android golden comparison committed using legal synthetic
  fixtures, with local strict runs against the real files.

### U1. Safety-review and policy prerequisites

- **Goal:** Establish a trustworthy engine baseline before exposing it to a
  community-facing editor.
- **Requirements:** mandatory gates, correct reviewer evidence, curated
  finding-to-calibration links.
- **Dependencies:** U0 may run in parallel, but U2 cannot close until U1 closes.
- **Files:** `Code/code_review.md`, affected `Code/simoscal/` and `Code/tests/`
  files, `CLAUDE.md`, and related authoring/analysis documentation.
- **Approach:**
  - Resolve `CR-20260720-05` so duplicate XDF titles cannot collide in plot or
    report identity.
  - Resolve `CR-20260720-06` so every reviewer-facing before value is relative
    to the declared reference bin.
  - Audit every open High finding in `Code/code_review.md`; fix it or document a
    verified dismissal before mobile release work depends on its guarantee.
  - Add a strict real-file test mode so missing safety fixtures fail release
    verification rather than silently skip.
  - Update `CLAUDE.md` to allow curated calibration-influence links while
    retaining the ban on generated target values and automatic changes.
  - Preserve the existing requirement for explicit intents in human-authored
    revision scripts. The app's optional revision context is a separate UI
    contract and must not weaken script authoring rules.
- **Verification:** full host suite green; focused reproductions for each closed
  finding; regenerated reviewer report manually inspected; finding index
  statuses updated.

### U2. Portable Python package boundary

- **Goal:** Make the safety-critical runtime embeddable without pulling desktop
  artifact dependencies or import-time side effects into Android.
- **Requirements:** offline embedded engine, same behavior as host Python.
- **Dependencies:** U0, U1.
- **Files:** `Code/pyproject.toml`, `Code/simoscal/__init__.py`, analysis and tune
  package initializers, optional-renderer modules, packaging tests, Android
  engine dependency configuration.
- **Approach:**
  - Split core runtime dependencies from optional spreadsheet and matplotlib
    extras.
  - Remove eager top-level imports that require `openpyxl` or `matplotlib` when
    a caller only needs parsing, editing, checksums, tune building, or analysis.
  - Keep desktop export and PNG behavior backward compatible through explicit
    optional extras and lazy public imports.
  - Pin a reproducible Python/NumPy combination proven by U0; generate the
    Android bundle from the same package source tested on the host.
  - Add installed-wheel tests for every tune domain and application-service
    module so the Android artifact cannot omit packages as the earlier
    `CR-20260720-03` defect did.
- **Verification:** core wheel installs and passes without matplotlib/openpyxl;
  desktop extras still pass their suites; embedded smoke test imports only the
  intended mobile dependency closure.

### U3. Compatibility preflight and provenance

- **Goal:** Turn bin/XDF acceptance into a public, deterministic operation that
  blocks unusable inputs before a session exists.
- **Requirements:** non-dismissible unusable-bin state, replacement flow,
  exact SC8S50 recognition, source immutability.
- **Dependencies:** U2.
- **Files:** new app-neutral preflight/provenance modules under
  `Code/simoscal/`, SC8S50 profile metadata, checksum/XDF tests, bridge fixtures.
- **Approach:**
  - Return a structured result containing file identity, size, hashes, XDF
    region, parse verdict, checksum recognizability/currentness, profile match,
    reversible-write capability, plain-language reason, and advanced details.
  - Verify checksum recognition without modifying the selected source.
  - Validate XDF region bounds and sweep table metadata/embedded extents so an
    obvious mismatch is rejected before editing.
  - Recognize SC8S50 through explicit profile identity and required exact
    symbol/shape checks, not filename or fuzzy title matching.
  - Separate a stale-but-correctable checksum from an unrecognized layout. A
    stale source may be reported precisely; an unverifiable source blocks.
  - Re-running preflight with a replacement file must not retain state from the
    rejected input.
- **Verification:** valid full bin; CAL-only image; truncated bin; malformed CAL
  CRC table; missing ECM3 addresses; mismatched XDF region; corrupt XDF; stale
  but correctable source; exact SC8S50 and generic-compatible XDF cases.

### U4. Serializable recipe and cumulative replay engine

- **Goal:** Represent every app edit as deterministic data that can be saved,
  copied, migrated, replayed, compared, and audited.
- **Requirements:** Quick Edit recovery, project conversion, cumulative recipe
  snapshots, independent rebuilds.
- **Dependencies:** U3.
- **Files:** new recipe/session modules under `Code/simoscal/tune/`, domain
  adapters, schema fixtures, migration tests, public exports.
- **Approach:**
  - Define a versioned recipe document with ordered operations and provenance.
    Keep its canonical persistence format deterministic and dependency-free.
  - Represent guided domain calls with operation identity and typed physical
    arguments; represent direct XDF edits with exact table identity, expected
    shape/axes, and physical target values.
  - Store optional revision-level reason, note, and finding/log context once;
    never require per-cell user text.
  - Replay from an immutable baseline into a fresh buffer. Profile, XDF,
    baseline, schema, or shape mismatches fail before the first write.
  - Preserve operation order because later writes may intentionally supersede
    earlier domain or table writes.
  - Copying revision N to N+1 creates a full recipe snapshot, not a pointer to
    N's output bin.
  - Converting Quick Edit to a project wraps the existing baseline, recipe,
    evidence, and artifacts without changing output bytes.
- **Verification:** serialization round trip; deterministic canonical bytes;
  migration fixtures; replay after process restart; copied revision; restore to
  baseline; intentionally reordered operations produce a detected difference;
  every historical snapshot rebuilds byte-identically.

### U5. Generic physical-unit edit session

- **Goal:** Provide the app-neutral editing behavior needed by Simple and
  Advanced modes without exposing raw writes.
- **Requirements:** all reversible XDF scalars/axes/curves/grids, batch edits,
  undo, source/proposed/delta, no arbitrary bytes.
- **Dependencies:** U4.
- **Files:** `Code/simoscal/calfile.py`, tune/session modules, writer/safety
  helpers, new generic-editor tests.
- **Approach:**
  - Add read-only table catalog and table-detail result models keyed by exact
    unique ID, symbol, and description.
  - Add journaled generic axis writes; current `TableView` only exposes Z writes.
  - Expose set, add, subtract, multiply, divide, fill, interpolate, paste,
    restore, and undo as recipe operations over explicit selections.
  - Compute proposed values before staging and validate the complete batch
    atomically. A rejected value must leave the entire table and recipe
    unchanged.
  - Report requested versus encoded/readback values so quantization is visible.
  - Treat nonlinear, zero-slope, absent, out-of-region, or otherwise
    non-reversible definitions as read-only.
  - Continue enforcing hard float-bug and raw-range guards. Display-range
    warnings require an explicit Advanced-mode acknowledgement captured in the
    operation; they never silently clamp.
  - Keep raw values, addresses, equations, and byte ranges readable for
    diagnostics but provide no write command for them.
- **Verification:** scalar, 1D, 2D, axis, shared-axis, label-only axis,
  nonlinear equation, zero slope, float-bug guard, display-range acknowledgement,
  atomic multi-cell failure, undo/redo, and source immutability tests.

### U6. Renderer-independent build service

- **Goal:** Run the complete build gate sequence and return a stable report
  model without requiring matplotlib or desktop paths.
- **Requirements:** checksum correction/verification, readback, byte audit,
  unique output, blocked export, concise and detailed reports.
- **Dependencies:** U4, U5.
- **Files:** refactor `Code/simoscal/tune/pipeline.py`, audit/journal/report
  modules, add an application build-service module, and extend build tests.
- **Approach:**
  - Separate mandatory verification from optional plot and HTML/Markdown
    rendering.
  - Accept explicit source, baseline, reference, recipe, and output paths; do
    not infer repository folders.
  - Write to a new private staging directory, correct checksums, reopen the
    actual file, run every readback and post-save check, and audit against the
    declared reference.
  - For Quick Edit, use the imported bin as both baseline and reference. For a
    project revision, rebuild from baseline and audit against the previous
    revision output.
  - Derive every audit allowance from measured journal entries and supported
    checksum storage. Unexplained bytes block verified state.
  - Return one machine-readable report model used by native review UI and
    exported Markdown/HTML. Reference-relative before values and collision-free
    table identities are invariant.
  - Preserve failed reports internally for diagnosis, but expose bin save/share
    only after every gate passes.
- **Verification:** happy Quick Edit; first project revision; later cumulative
  revision; restored table; duplicate XDF titles; source/reference/candidate
  all different; checksum unrecognized; readback fault; unjournaled byte;
  failed build has no shareable bin; successful rebuild is byte-identical.

### U7. Mobile analysis service and deterministic influence registry

- **Goal:** Return analysis, coverage, evidence-series data, and curated
  finding-to-calibration navigation without writing desktop artifacts.
- **Requirements:** optional Quick Edit logs, deterministic rule-based
  suggestions, exact SC8S50 mappings, no generated target values.
- **Dependencies:** U3, U5.
- **Files:** refactor `Code/simoscal/analysis/evidence.py` and package exports;
  add analysis service, presentation-series, and influence-registry modules;
  extend SC8S50 profile data and tests.
- **Approach:**
  - Separate log loading, pull detection, battery execution, coverage, evidence
    series, and artifact rendering into independently callable layers.
  - Define influence registry entries by finding/check ID and exact SC8S50
    logical tables. Each entry includes relationship text, applicability rules,
    rank rules, and the editor target.
  - Rank candidates only from explicit finding evidence, log channels,
    operating region, profile resolution, and coverage. Stable tie-breakers
    make ordering deterministic.
  - Map coverage to exact table regions and return editor-selection coordinates
    where the available channels justify them. Otherwise open the table without
    inventing a region.
  - Keep generic XDF analysis available where existing checks support it, but
    omit semantic influence links outside a recognized profile.
  - Never return a proposed calibration value or mutation command from a
    finding.
- **Verification:** repeated runs are byte-identical; every registry entry
  resolves exactly; unresolved tables are omitted with a reason; boost tracking
  ranks `IP_FAC_BPA_SP[0]/[1]` — Map for boost pressure actuator setpoint
  (feedforward), `IP_PUT_SP` — Pressure up throttle setpoint,
  `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbocharger
  compressor, and `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold
  pressure setpoint according to explicit rule fixtures; no result contains a
  target value.

### U8. Versioned Python↔Kotlin bridge

- **Goal:** Expose the application services to Android through one stable,
  testable boundary.
- **Requirements:** same engine on host and Android, useful errors, no Python
  objects in UI state.
- **Dependencies:** U3–U7.
- **Files:** new Python bridge module, `Code/android/engine/` Kotlin facade and
  result types, contract fixtures, host and instrumentation tests.
- **Approach:**
  - Expose coarse operations for preflight, session creation/recovery, table
    catalog/detail, edit/undo, recipe replay, build, analysis, and report data.
  - Use a versioned request/result envelope with deterministic serialization.
    Large bins and logs remain private files; requests carry verified private
    paths and hashes rather than base64 payloads.
  - Convert known Python failures into stable error codes plus plain and
    advanced details. Preserve diagnostic tracebacks only in private debug logs.
  - Serialize bridge calls through a dedicated background dispatcher so long
    analysis/build operations never block Compose or race one mutable session.
  - Add contract tests that run the same fixture documents through direct host
    calls and Chaquopy and compare results.
- **Verification:** parity fixtures for every operation; malformed request;
  schema mismatch; missing private file; canceled UI collector; concurrent
  request attempt; Python exception mapping; process restart and recovery.

### U9. Android local storage, import, export, and recovery

- **Goal:** Implement the local-only source of truth and secure file exchange.
- **Requirements:** no account/cloud, airplane mode, immutable sources,
  standard picker/share sheet, restart recovery, portable bundles.
- **Dependencies:** U8.
- **Files:** `Code/android/app/` data layer, Room database/entities/DAOs and
  migrations, file repository, import/export services, `FileProvider`
  configuration, tests.
- **Approach:**
  - Use the Storage Access Framework for selecting bins, XDFs, logs, output
    destinations, and project bundles without broad storage permission.
  - Stream selected content into a fresh app-private file while hashing; never
    edit the content URI in place.
  - Store structured metadata in Room and artifacts in project/session
    directories with manifest hashes.
  - Make Quick Edit sessions recoverable until explicitly discarded. Use
    atomic manifest/database transitions so a crash cannot mark an incomplete
    build verified.
  - Share verified outputs with `content://` URIs and temporary read grants.
  - Define and version a portable bundle manifest. Exclude source bins, XDFs,
    and logs by default when they are large or sensitive; show an explicit
    inclusion review.
  - Validate every imported bundle path, hash, size, and schema before copying
    it into active storage.
- **Verification:** airplane-mode import/edit/export; process kill during copy,
  edit, build, and conversion; Room migration tests; corrupted bundle; path
  traversal attempt; duplicate filename; source hash unchanged; receiving app
  can read shared output only through the granted URI.

### U10. Android shell, adaptive navigation, and mode policy

- **Goal:** Build the production navigation and mode framework before dense
  editors are added.
- **Requirements:** Quick Edit default, projects secondary, phone/tablet feature
  parity, Simple/Advanced visibility rules.
- **Dependencies:** U9.
- **Files:** Compose application shell, navigation, theme, window-adaptive
  scaffolds, mode policy, accessibility resources, UI tests.
- **Approach:**
  - Landing screen actions: Quick Edit, Open Project, New Project.
  - Use window size classes and canonical adaptive layouts. Compact windows
    show one pane at a time; expanded windows may show list/detail or
    finding/editor panes together.
  - Persist one user mode preference. Entering Advanced mode shows a one-time
    explanation; it does not change recipe data or gate behavior.
  - Centralize capability policy. Simple mode shows supported domain controls;
    Advanced mode adds the table browser and direct editor. Existing advanced
    edits remain visible and read-only in Simple mode.
  - Omit Internet, Bluetooth, location, and vehicle permissions from the
    manifest and assert that in tests.
- **Verification:** navigation and state restoration on compact/medium/expanded
  emulator configurations; the same operation set is reachable at every size;
  mode switch leaves recipe and build result unchanged; accessibility scan;
  manifest permission test.

### U11. Quick Edit and calibration editors

- **Goal:** Deliver the smallest complete user value: two-file import through
  verified output.
- **Requirements:** default Quick Edit, blocking preflight, guided and direct
  editing, review, no overwrite.
- **Dependencies:** U10 and U3–U8.
- **Files:** Quick Edit flow, compatibility blocker, table browser, scalar/line/
  grid/axis editors, batch-action controls, review screen, Compose tests.
- **Approach:**
  - Make bin and XDF selection sequential and replaceable. Do not create a
    session until both pass preflight.
  - Display a non-dismissible incompatible-file state with Choose another bin
    and Cancel. There is no Continue anyway.
  - Simple mode presents SC8S50 domain operations in physical units. Advanced
    mode supports search/category navigation and exact parameter ID plus
    description.
  - Editors show source, proposed, and delta; selected region; units; requested
    versus encoded values; undo/redo; restore; and validation results.
  - Phone and tablet use the same editor actions with different pane layouts.
  - Review changed tables, gate states, warnings, and software-verification
    disclaimer before build. Share/save appears only after verified state.
  - Offer Save as project without requiring a reason or rewriting the session.
- **Verification:** AE1–AE6 and AE11 from the requirements; Compose interaction
  tests; screenshot tests at representative window sizes; physical-device test
  selecting and sharing real files.

### U12. Projects and cumulative revision UX

- **Goal:** Add durable tuning lineage without changing Quick Edit semantics.
- **Requirements:** immutable baseline, cumulative recipes, logs/findings,
  revision comparison, exact Quick Edit conversion.
- **Dependencies:** U11.
- **Files:** project/revision repositories, project screens, revision creation
  and comparison flows, bundle integration, tests.
- **Approach:**
  - Create a project only after compatible inputs pass preflight.
  - Copy the previous cumulative recipe when creating a revision; replay the
    copy from the immutable baseline and compare against the previous output.
  - Display immutable file hashes and recipe provenance in Advanced details.
  - Keep optional revision reason/note at revision level. Inherited finding and
    log context remains visible without per-edit prompts.
  - Convert Quick Edit transactionally: project baseline equals the imported
    source, R01 recipe equals the active session, and existing findings/reports
    are re-indexed rather than regenerated.
- **Verification:** AE9 and AE10; multi-revision rebuild; deleted cached output
  regenerated from baseline; conversion output and report hashes unchanged;
  source replacement prohibited after revisions exist.

### U13. Logs, findings, evidence, and influence-to-editor UX

- **Goal:** Complete the field loop from Simos Tools log to a deliberate next
  edit.
- **Requirements:** optional Quick Edit logs, deterministic findings, evidence
  plots, coverage, relevant tables, tap-to-edit.
- **Dependencies:** U7, U11, U12.
- **Files:** Android share receiver, log import/selection, analysis runner,
  findings/evidence/coverage screens, influence list and editor deep links,
  tests.
- **Approach:**
  - Accept one or more CSVs through picker or share intent into Quick Edit or a
    selected project revision.
  - Present log-quality preflight, pulls, ranked findings, skipped checks,
    evidence series, and coverage before calibration influences.
  - Label the influence section as relevant calibration influences, not fixes.
  - Each item shows exact ID plus description, why it matters, applicability,
    and logged region. Tapping opens the same editor used by normal navigation
    with finding context retained.
  - Returning to the finding shows which linked tables changed, without
    implying the finding is resolved until new logs exist.
- **Verification:** AE7, AE8, and AE12; share multiple logs from a fixture app;
  deterministic ordering; missing PID and unresolved profile behavior;
  deep-link round trip preserves selection/context; no numeric suggestion text
  appears in serialized or rendered results.

### U14. End-to-end acceptance, open-source release, and documentation

- **Goal:** Prove the product contract and prepare a reproducible public beta.
- **Requirements:** all acceptance examples, free/open-source release, no flash
  capability.
- **Dependencies:** U0–U13.
- **Files:** cross-runtime acceptance harness, CI workflows, release build
  configuration, privacy/data-safety documentation, `Code/README.md`, Android
  user/developer guides, licenses and notices.
- **Approach:**
  - Run host tests on supported Python versions and Android unit, lint,
    instrumentation, adaptive-layout, migration, and golden-parity suites.
  - Add a strict local/release job requiring the real SC8S50 XDF/bin/log corpus
    without committing proprietary recovery images or user logs.
  - Exercise a physical phone and tablet or equivalent expanded window with
    identical inputs and assert identical engine artifacts.
  - Fuzz or property-test XDF parsing, recipe documents, project bundles, and
    bridge requests within bounded resources.
  - Choose and apply an OSI-approved project license; audit compatibility and
    ship third-party notices for VW_Flash-derived BSD-2-Clause code, Chaquopy,
    and all bundled dependencies.
  - Set the final immutable Android application ID before the first Play upload.
  - Build a signed release candidate for human review. Store signing keys
    outside the repository. Publishing remains a separate explicit user action.
  - Document Quick Edit, projects, Simple/Advanced modes, supported profiles,
    local data behavior, compatibility errors, exported artifacts, and the
    software-verification versus calibration-safety distinction.
- **Verification:** every requirements AE passes; release AAB installs and runs
  offline on supported arm64 hardware; source hash remains unchanged; verified
  output matches host Python; manifest has no network/vehicle permissions;
  independent clean-checkout build succeeds; no flashing code or dependency is
  present.

## Files and areas affected

### Existing Python repository

- `Code/pyproject.toml`
- `Code/simoscal/__init__.py`
- `Code/simoscal/calfile.py`
- `Code/simoscal/checksum.py`
- `Code/simoscal/tune/`
- `Code/simoscal/analysis/`
- `Code/simoscal/tune/profiles/sc8s50.py`
- `Code/tests/`
- `Code/code_review.md`
- `Code/README.md` and `Code/docs/`

### New Android and application-service areas

- `Code/android/settings.gradle.kts`
- `Code/android/build.gradle.kts`
- `Code/android/gradle/`
- `Code/android/engine/`
- `Code/android/app/`
- New app-neutral preflight, recipe, session, build-service, presentation, and
  bridge modules under `Code/simoscal/`
- Android unit, instrumentation, UI, migration, and golden-parity fixtures

### Root repository documentation only

- `CLAUDE.md` policy update for curated influence links
- This requirements document and implementation plan

No car-specific bin, XDF, log, generated tune, or recovery image moves into the
public Android source tree.

## Validation strategy

### Host Python

1. Run the full `Code/tests` suite with cache and bytecode writes disabled when
   auditing a dirty worktree.
2. Add focused suites for preflight, recipe serialization/replay, generic edits,
   influence rules, bridge contracts, and renderer-independent builds.
3. Run installed-wheel tests with core-only dependencies and with desktop
   extras.
4. Run strict real-file acceptance locally before any release candidate.

### Android

1. Run Gradle unit tests and lint.
2. Run Room migration tests on an emulator/device.
3. Run Compose navigation, mode, editor, and adaptive-layout tests.
4. Run bridge and golden-parity instrumentation tests on x86_64 emulator and
   arm64 hardware.
5. Test process death, rotation, window resize, low-storage failure, and
   interrupted import/build recovery.
6. Install and exercise the release AAB offline.

### Cross-runtime release gate

For identical XDF, bin, recipe, logs, profile, and engine version, host Python
and Android must produce:

- Identical compatibility verdicts and hashes.
- Identical decoded physical values and writable/read-only classifications.
- Identical canonical recipe documents.
- Byte-identical candidate bins.
- Identical checksum, readback, and byte-audit verdicts.
- Identical findings, skips, influence ordering, and coverage counts.
- Semantically identical report models.

No UI-only test can substitute for this gate.

## Risks and mitigations

- **Embedded Python/native package risk:** Android wheels, 16 KB pages, ABI
  support, startup, memory, or package size may be unacceptable. Mitigation:
  U0 is a hard go/no-go and Python 3.13+ is preferred for current 16 KB-page
  compatibility.
- **Safety logic duplication:** Kotlin implementations could drift from Python.
  Mitigation: Kotlin handles no bin math; one bridge and cross-runtime goldens
  enforce parity.
- **Recipe drift across engine versions:** a new domain implementation could
  replay old operations differently. Mitigation: version recipes and profiles,
  keep migration fixtures, and require byte-identity rebuild tests before a
  migration is accepted.
- **Large XDF/log memory pressure:** SC8S50 XDFs and evidence arrays can exceed
  comfortable phone memory if copied repeatedly. Mitigation: private-path
  bridge, coarse calls, paged table catalogs, bounded result documents,
  measured U0 budgets, and no base64 bin transfer.
- **Dense grid usability on phones:** a full table is inherently compact.
  Mitigation: feature parity with different layouts, explicit selection detail,
  zoom/pan or focused region presentation, batch operations, undo, and physical
  device testing.
- **Source/output confusion:** a tuner may select or share the wrong bin.
  Mitigation: immutable hashes, provenance display, unique output names,
  reference-relative review, and no overwrite.
- **Misread calibration influence:** users may interpret relevance as a required
  fix. Mitigation: deterministic curated wording, relationship explanations,
  no target values, and explicit unresolved-until-relogged state.
- **Project corruption or app uninstall:** local-only storage has no server
  recovery. Mitigation: transactional persistence, restart recovery, portable
  bundles, and visible backup/export guidance.
- **Open-source licensing:** the package is currently proprietary and includes
  adapted third-party code. Mitigation: license/notice audit and explicit
  license decision before public beta, not after publication.
- **Dirty nested repositories:** current changes span both root and `Code/`.
  Mitigation: implementation starts from recorded statuses, isolates each unit,
  and never reverts unrelated user work.

## Deferred decisions

- Exact ordering and visual grouping of Simple-mode operations.
- Final Android package/application ID, icon, store copy, and screenshots.
- OSI license choice, subject to the U14 compatibility audit.
- Project-bundle default size threshold and optional compression.
- Performance budgets, set from U0 measurements rather than guessed here.
- Later verified patch application after ASW/code checksum support exists.
- A YAML or other human-editable recipe export; canonical v1 persistence remains
  deterministic and app-owned.

## External constraints verified during planning

- Chaquopy 17 supports Python 3.10–3.14, Android Gradle plugin 7.3–9.2, API 24+,
  and one plugin-enabled module per app:
  <https://chaquo.com/chaquopy/doc/current/android.html>
- Chaquopy is free and open-source and distributed through Maven Central:
  <https://chaquo.com/chaquopy/license/>
- Android recommends Compose window size classes and adaptive layouts rather
  than device-type feature forks:
  <https://developer.android.com/develop/ui/compose/build-adaptive-apps>
- The Storage Access Framework provides user-controlled document access without
  broad storage permission:
  <https://developer.android.com/training/data-storage/shared/documents-files>
- Android recommends Room for non-trivial local structured data:
  <https://developer.android.com/training/data-storage/room>
- Android requires secure inter-app file sharing through content URIs and
  temporary grants:
  <https://developer.android.com/training/secure-file-sharing>

## Handoff

Begin implementation only after Sam approves this plan. Execute U0 first and
report its measurements and parity result before starting U1–U14. The natural
execution entry point after approval is `/ce-work` with this plan as the source.
