# Simoscal Android app — requirements

**Date:** 2026-07-21
**Status:** Brainstorm complete, ready for `/ce-plan`
**Owner:** Sam

## Problem

The tuning workflow moves between calibration editing, Simos Tools logging,
log review, revision building, verification, and flashing. Existing Android XDF
editors cover general table editing, but they do not provide Simoscal's
evidence-connected revision workflow, deterministic analysis battery,
journal-driven audit, or reviewer-facing build evidence.

A tuner who has just collected logs should be able to review them and make a
small, deliberate calibration revision on the same Android device. The app must
preserve the separation between software verification and the human decision to
flash or drive the car.

## Goals and success criteria

- Release a free, open-source, standalone Android app named Simoscal.
- Give phones and tablets identical capabilities; only the layout adapts to
  available screen space.
- Make Quick Edit the default first-run path: choose a `.bin` and `.xdf`, edit,
  verify, and export without creating a project.
- Let Quick Edit optionally ingest Simos Tools logs and convert the complete
  session into a persistent project without losing context.
- Support a project workflow that connects logs, deterministic findings,
  relevant calibration influences, edits, revision history, and build evidence.
- Provide Simple and Advanced modes without weakening any safety gate.
- Work entirely offline with no account or cloud service.
- Leave every selected source file untouched.
- Produce only bins whose supported checksums were corrected and independently
  verified, whose edits passed final-file readback, and whose byte changes were
  attributed.
- Never flash an ECU or imply that a software-verified bin is mechanically safe.

## Product shape

Android is the primary community product. A thin CLI may remain as a secondary
surface for development, automation, reproducible testing, and power users.
Both surfaces must ultimately use the same deterministic calibration and safety
behavior.

Simoscal is separate from Simos Tools. Interoperability uses ordinary Android
file selection and sharing rather than private APIs, shared databases, or
flashing permissions.

## Scope

### Quick Edit

- Quick Edit is the primary action on the app's landing screen.
- The user selects one `.bin` and one `.xdf`.
- The app runs compatibility preflight before creating an editing session.
- The user may optionally attach one or more Simos Tools log files.
- The user may use Simple or Advanced mode when the loaded profile permits it.
- The app automatically journals every edit.
- A revision reason is not required.
- The app builds a new, non-overwriting output with a concise review report.
- The input bin is the immutable source and the byte-audit reference.
- The user may convert the session into a project at any time.

### Projects

- A project stores an immutable baseline, XDF, cumulative revision recipes,
  generated bins, logs, findings, journals, and reports.
- Each revision is a cumulative recipe snapshot replayed from the immutable
  baseline.
- Creating a revision feels like copying the previous revision and making a
  small change, but the new revision remains independently reproducible.
- The previous revision's generated bin is the comparison and byte-audit
  reference, not the next revision's build source.
- Converting Quick Edit to a project makes the imported bin the immutable
  baseline and the current edits the first cumulative revision.
- Attached logs, findings, journal entries, and verification results survive
  conversion unchanged.

### Simple and Advanced modes

| Area           | Simple mode                                      | Advanced mode                                      |
| -------------- | ------------------------------------------------ | -------------------------------------------------- |
| Navigation     | Task-oriented tuning, comparison, and log review | Adds the complete XDF table browser                |
| Editing        | Curated domain operations in physical units      | Direct XDF-defined scalar, axis, curve, and grid   |
| Identification | Plain-English meaning is prominent               | Parameter ID and plain-English description shown   |
| Detail         | Summarized source, proposed, and delta values    | Adds encoding, address, scaling, and byte details  |
| Verification   | Every mandatory gate                             | The same mandatory gates                           |

- Mode changes visibility and edit controls, not project data or verification
  rigor.
- Advanced mode does not disable guards or permit silent clamping.
- Simple mode must disclose advanced edits as read-only items when opening a
  revision that already contains them.
- Advanced mode may edit every XDF-defined item with a reversible physical-unit
  conversion.
- Tables without a reversible physical-unit conversion are read-only.
- Raw encoded values and addresses are read-only diagnostics.
- Arbitrary byte editing is excluded.

### Profile support

- The SC8S50 profile receives the complete v1 experience: guided domain edits,
  deterministic finding-to-calibration mappings, and log-coverage highlighting.
- Other compatible XDFs may be inspected, compared, and edited through generic
  physical-unit XDF controls.
- Semantic guidance for an unknown XDF must never be inferred through fuzzy
  matching.
- Additional Simos 18 profiles are added through explicit, curated, testable
  mappings.

### Log analysis and calibration influences

- The analysis battery remains deterministic, enumerable, and rule-based.
- Identical logs, profile, bin, and battery version produce identical findings
  and suggestion ordering.
- A finding may list calibrations that can influence the observed behavior.
- Influence mappings are expert-curated by finding type and profile.
- Log conditions and table coverage deterministically rank eligible influences
  and highlight relevant cells or curve regions.
- Every listed calibration includes its relationship to the finding in plain
  language.
- Tapping an influence opens the correct editor while preserving the finding,
  evidence, pulls, and highlighted operating region.
- The list identifies relevant influences; it does not assert that every listed
  calibration should be changed.
- The app does not generate a target value, apply an automatic correction, or
  use AI-generated tuning suggestions in v1.
- For boost tracking, candidates may include
  `IP_FAC_BPA_SP[0]/[1]` — Map for boost pressure actuator setpoint
  (feedforward), `IP_PUT_SP` — Pressure up throttle setpoint,
  `IP_PQ_CHA_MAX` — Maximum allowed pressure quotient at turbocharger
  compressor, and `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold
  pressure setpoint, when the active profile and deterministic rules identify
  them as relevant.

### Rationale and audit metadata

- Simoscal automatically records what changed, including affected calibrations,
  cells or regions, source values, proposed values, units, and encoded bytes.
- Users do not type an intent for every edit or cell.
- A project revision may have one optional reason tag and one optional note.
- An edit opened from a finding automatically retains that finding and log
  context.
- A batch edit receives one shared context rather than prompting per cell.

### Compatibility preflight

- Selecting a bin immediately checks its size, supported layout, CAL CRC, ECM3,
  and ability to correct and independently verify the supported checksums.
- An unusable bin produces a non-dismissible blocking state.
- The blocking state gives a plain-language reason and a **Choose another
  `.bin`** action.
- There is no **Continue anyway** path.
- Advanced details show file size, detected layout, checksum results, and the
  technical failure reason.
- Selecting a replacement reruns the complete preflight without restarting
  setup.
- No Quick Edit session or project is created until required bin and XDF checks
  pass.

### Build and review

- Source bins are immutable.
- Output names are unique by default and never overwrite an input.
- Checksum correction is followed by independent verification of the written
  file.
- Every edited calibration is read back from the written file and compared with
  the journal.
- A byte-level audit attributes changes to journaled edits and stored checksum
  values.
- Any unexplained byte blocks the build.
- Build reports distinguish software verification from calibration safety.
- Simoscal exports or shares the verified bin for a separate human-controlled
  flashing workflow.
- Simoscal never flashes an ECU.

### Local-only storage

- Core functionality works in airplane mode.
- The app requires no account and has no cloud backend.
- Projects persist locally across app and device restarts.
- Users import and export through Android's standard file and share surfaces.
- Users may export an individual verified bin, its report, or a portable project
  bundle.
- A project bundle excludes large or sensitive source files unless the user
  explicitly includes them.

## Key flows

### Quick Edit without logs

1. Launch Simoscal and choose Quick Edit.
2. Select a bin and XDF.
3. Pass compatibility preflight.
4. Choose Simple or Advanced mode.
5. Make and review edits.
6. Build a checksum-clean, readback-verified, byte-audited copy.
7. Save or share the output and report.

### Field revision with logs

1. Collect logs in Simos Tools.
2. Share the logs to Simoscal Quick Edit or an existing project.
3. Run the deterministic analysis battery.
4. Review findings, evidence plots, and calibration influences.
5. Tap an influence to open its editor with logged coverage highlighted.
6. Make a human-chosen edit.
7. Review and build the next verified bin.
8. Share the bin to the separate human flashing workflow.

### Quick Edit conversion

1. Start with a bin, XDF, optional logs, and edits in Quick Edit.
2. Choose **Save as project**.
3. Name the project.
4. Preserve the original bin as the immutable baseline.
5. Preserve the current session as the first cumulative revision with identical
   findings, journal, build result, and output bytes.

## Acceptance examples

- **AE1:** A new user selects a valid SC8S50 full bin and XDF, changes one
  guided target, and exports a verified output without creating a project.
- **AE2:** A CAL-only, malformed, or unsupported bin produces a blocking
  compatibility message and cannot reach an editor until replaced.
- **AE3:** The selected input bin remains byte-identical after Quick Edit and
  project workflows.
- **AE4:** The same Quick Edit performed on a phone and tablet produces
  byte-identical output, journal, and verification results.
- **AE5:** Switching between Simple and Advanced mode changes available views
  and controls but does not change recipe data or safety gates.
- **AE6:** Advanced mode can edit an arbitrary XDF-defined grid with reversible
  physical scaling, but cannot write raw bytes or a table without a reversible
  conversion.
- **AE7:** A known boost-tracking finding produces the same ordered calibration
  influence list on repeated runs, and tapping
  `IP_FAC_BPA_SP[0]/[1]` — Map for boost pressure actuator setpoint
  (feedforward) opens the correct tables and logged region.
- **AE8:** No finding proposes a numeric calibration value or applies an edit
  without the user choosing the value.
- **AE9:** A Quick Edit session with logs converts to a project without changing
  its output bin, findings, journal, or reports.
- **AE10:** Rebuilding any project revision from the immutable baseline and its
  cumulative recipe reproduces the original output byte-for-byte.
- **AE11:** One unjournaled changed byte causes the build to fail and prevents
  verified-bin export.
- **AE12:** All core flows succeed in airplane mode and after an app restart.

## Key decisions and rationale

1. **Android is the primary community interface.** It is available on the same
   device used for Simos Tools logging and flashing.
2. **Simoscal remains a separate app.** This preserves an explicit safety and
   ownership boundary around flashing.
3. **Quick Edit is the default.** A full project is valuable but should not be
   required for a small field revision.
4. **Projects use cumulative recipe snapshots.** Each revision remains
   reproducible without executing a chain of prior bins.
5. **Phone and tablet have feature parity.** Responsive layout must not create
   platform-dependent calibration capability.
6. **Simple and Advanced modes share safety gates.** Expertise changes the
   exposed controls, not the standard of verification.
7. **Guidance is curated and deterministic.** This keeps behavior testable and
   prevents plausible-sounding generated tuning advice.
8. **Storage is local-only.** The workflow must work beside the car without
   connectivity or an account.
9. **Physical-unit XDF editing is the lowest writable level.** Raw encoding is
   visible for diagnosis but arbitrary byte editing is a different product.

## Deferred or out of scope

- Flashing or direct ECU communication.
- Cloud accounts, synchronization, collaboration, or telemetry.
- AI-generated calibration suggestions or values.
- Automatic tuning changes from analysis findings.
- Arbitrary byte or hex editing.
- Full semantic guidance for profiles other than SC8S50.
- A general replacement for ECULeg or every TunerPro editing feature.
- Applying patches that require unsupported ASW/code-block checksum handling.
- iOS and desktop graphical applications.

## Outstanding questions

- **Deferred:** Exact v1 list and ordering of guided Simple-mode operations.
- **Deferred:** Exact portable project-bundle contents and size limits.
- **Deferred:** App name styling, package identifier, icon, and store listing.
- **Deferred:** Whether a later release supports verified patch application.
- **Required before implementation:** Update `CLAUDE.md` to permit curated
  calibration-influence links from analysis findings while continuing to
  prohibit automatic calibration changes.
