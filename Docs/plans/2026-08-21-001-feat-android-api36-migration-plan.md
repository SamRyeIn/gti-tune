# Android API 36 migration — implementation plan

Date: 2026-08-21
Type: feat
Origin: Play publication readiness review, step 2
Depth: Standard–Deep (6 units, Android app only)
Status: ready for execution

## Summary

Move `simoscal-android` from `compileSdk` / `targetSdk` 35 to Android 16
(API 36), remove the temporary edge-to-edge opt-out, and make the Compose shell
correct under system bars, display cutouts, the software keyboard, rotation,
and predictive back. Preserve the app's byte-critical Python runtime and all
existing safety gates while upgrading the Android build toolchain far enough to
support API 36 officially.

This is not a two-line SDK bump. Google lists AGP 8.9.1 as the minimum supported
plugin for API 36, and AGP 8.9 requires Gradle 8.11.1. The project is currently
pinned to AGP 8.1.4 + Gradle 8.4 because Gradle 8.11.1 previously turned
Chaquopy's undeclared task-graph edges into build failures. Proving or repairing
that toolchain boundary is the first gate; layout work does not begin until it
passes.

## Goal

A minified arm64 release artifact must report `targetSdkVersion:'36'`, retain
the same embedded `simoscal` behavior and permission-free contract, render every
interactive control outside unsafe system UI in portrait and landscape, and
complete the existing import → preflight → edit → build → share workflow on the
Galaxy Tab A9+ running Android 16.

## Assumptions and scope boundaries

- Work occurs in the separate `/Users/sam/simoscal-android` repository, based
  on its current `feat/domain-screens-log-overlay` branch and the matching
  `Code/feat/domain-screens-log-overlay` library checkout.
- `minSdk = 26`, `applicationId = "com.simoscal.engine"`, arm64-only delivery,
  Python 3.13, and the pinned NumPy runtime remain unchanged unless a build or
  runtime failure proves a change is required.
- Target stable API 36, not the API 36.1/QPR2 SDK. API 36 needs AGP 8.9.1;
  API 36.1 would unnecessarily raise the minimum to AGP 8.13.0.
- Do not mix this migration with store-listing work, upload-key creation,
  feature development, package renaming, or the broader 16 KB native-library
  migration.
- The existing 16 KB alignment failure is recorded during verification but is
  not silently folded into this unit. If the required AGP upgrade improves ZIP
  alignment, keep the evidence; native ELF/runtime compatibility remains its
  own release follow-up.
- No ECU flashing occurs. Device testing ends after generating and sharing a
  verified candidate file; flashing remains human-only.

## Design decisions

1. **Use the minimum officially supported API-36 toolchain first.** Start with
   AGP 8.9.1 + Gradle 8.11.1 + JDK 17. Do not jump to AGP 9 or API 36.1 unless
   evidence makes 8.9.1 unusable.
2. **Repair task dependencies narrowly.** If the known Chaquopy failure
   returns, capture the exact producer and consumer task names and declare the
   missing `dependsOn` edges for those variant tasks. Do not suppress Gradle's
   validation, disable the affected tasks, or accept a build in which the
   Python-generation/install tasks did not execute.
3. **Handle insets once in the app shell.** `SimoscalApp` owns the sole
   `Scaffold`, top bar, bottom navigation, snackbar, busy bar, and `NavHost`.
   It is the right place to establish and consume `safeDrawing` insets; adding
   ad-hoc system-bar padding to all ten screens would double-inset some paths and
   guarantee drift.
4. **Draw backgrounds edge-to-edge; inset interactive content.** The app's dark
   background may extend behind transparent system bars. Titles, navigation
   items, plot gestures, buttons, dialogs, and text fields must remain in the
   safe drawing area.
5. **Migrate predictive back instead of opting out.** API 36 enables predictive
   back by default. Move Navigation Compose to at least 2.8.0 and AndroidX
   Activity to a version with `enableEdgeToEdge`; do not add the temporary
   `android:enableOnBackInvokedCallback="false"` escape hatch.
6. **Keep dependency movement coherent and bounded.** Navigation Compose 2.8.0
   requires the corresponding Compose generation, and Material3 1.3.0 provides
   predictive-back-aware components. Pin a compatible stable set rather than
   upgrading every AndroidX dependency to latest.

## Implementation units

### U1. Capture the baseline and prove the toolchain path

- **Goal:** Establish a known-good pre-migration result and determine the exact
  toolchain work required before changing runtime behavior.
- **Files inspected:** `build.gradle.kts`, `gradle/wrapper/gradle-wrapper.properties`,
  `gradle.properties`, `engine/build.gradle.kts`.
- **Approach:**
  1. Record both repositories' clean status and exact commits.
  2. Run the current debug unit tests, permission gate, debug assembly, Python
     suite, host parity, and current release assembly/parity path.
  3. Install the stable Android 16/API 36 platform if it is absent. The machine
     currently has `android-36.1`, which is not a reason to target the QPR API.
  4. On a short-lived migration branch, change only AGP to 8.9.1, Gradle to
     8.11.1, and `compileSdk` to 36; leave `targetSdk` at 35 for this probe.
  5. Run `help`, `check`, `assembleDebug`, and the release packaging tasks with
     `--stacktrace`. Confirm every Chaquopy `generate*Python*` and
     `install*PythonRequirements` task actually runs.
  6. If Gradle reports undeclared task outputs, use the task names in the error
     to add explicit, variant-scoped producer dependencies in
     `engine/build.gradle.kts`, then repeat from a clean task output.
- **Stop condition:** Do not proceed if the API-36-capable toolchain cannot build
  both debug and release variants with the embedded Python tasks present.
- **Verification:** Baseline and upgraded-toolchain tests have the same pass
  counts; the recovery image hash is unchanged; the generated APK contains the
  expected Python/NumPy libraries.

### U2. Upgrade the API-36 behavior dependencies

- **Goal:** Put the app on stable libraries that support the API-36 behavior it
  actually uses, without broad modernization.
- **Files:** `build.gradle.kts`, `engine/build.gradle.kts`,
  `gradle/wrapper/gradle-wrapper.properties`, `gradle.properties`.
- **Approach:**
  1. Set `compileSdk = 36` and `targetSdk = 36`; keep `minSdk = 26`.
  2. Pin AGP 8.9.1 and its compatible Gradle 8.11.1 wrapper after U1 proves the
     task graph.
  3. Move `activity-compose` to a stable version providing
     `ComponentActivity.enableEdgeToEdge()`.
  4. Move `navigation-compose` to at least 2.8.0 and its Compose dependencies to
     a compatible stable family; use Material3 1.3.0 or newer for supported
     predictive-back behavior. Keep Kotlin 1.9.24 / Compose compiler 1.5.14 if
     the selected stable dependency set compiles cleanly; move them only as a
     coordinated pair if the compiler requires it.
  5. Leave lifecycle, DataStore, coroutines, Python, NumPy, ABI, and minSdk pins
     untouched unless dependency resolution demonstrates a real incompatibility.
  6. Replace the now-stale build comments with the measured API-36 matrix and
     the reason for any explicit Chaquopy task edges.
- **Verification:** Dependency resolution is reproducible; debug and release
  unit suites pass; `aapt dump badging` reports compile/target API 36; no new
  manifest permissions appear.

### U3. Make the activity and Compose shell edge-to-edge safe

- **Goal:** Remove the API-35 hold and make system-bar handling correct on API
  26 through 36.
- **Files:** `engine/src/main/java/com/simoscal/android/MainActivity.kt`,
  `engine/src/main/java/com/simoscal/android/ui/SimoscalApp.kt`,
  `engine/src/main/res/values/themes.xml`,
  `engine/src/main/res/values-v35/themes.xml`, `engine/src/main/AndroidManifest.xml`.
- **Approach:**
  1. Call `enableEdgeToEdge()` before `setContent` in `MainActivity` so the same
     behavior is exercised on pre-35 devices rather than existing only under
     platform enforcement.
  2. Configure light system-bar icons over the app's consistently dark
     background. Retain the platform's protective scrim for three-button
     navigation unless device evidence shows it harms contrast.
  3. Remove `windowOptOutEdgeToEdgeEnforcement` and delete the v35-only theme
     override once no unique value remains. Keep the dark launch background in
     the base theme to prevent the Python-startup white flash.
  4. Set the shell's `Scaffold` inset contract explicitly to safe drawing
     insets. Apply its `PaddingValues` to the body and consume them before the
     `NavHost`, preventing descendants from applying the same inset again.
  5. Let `TopAppBar` and `NavigationBar` handle their own relevant insets. Pay
     special attention to landscape, where the top app bar is intentionally
     absent and the `Scaffold` body must therefore protect the top/display-cutout
     edge itself.
  6. Preserve `android:windowSoftInputMode="adjustResize"`; verify text-field
     and dialog behavior with the IME rather than adding permanent keyboard
     padding.
- **Verification:** No title, plot gesture area, button, snackbar, dialog action,
  or navigation item overlaps status, navigation, caption, or cutout regions in
  portrait or landscape. Background color reaches the window edges without a
  white or mismatched system-bar flash.

### U4. Close the other target-36 behavior changes used by this app

- **Goal:** Ensure API 36 does not change navigation or large-screen behavior in
  a way hidden by the inset fix.
- **Files:** `engine/src/main/java/com/simoscal/android/ui/SimoscalApp.kt`,
  `engine/src/main/AndroidManifest.xml`, affected UI tests.
- **Approach:**
  1. Exercise predictive back from nested navigation destinations, Analyze with
     and without a session, dialogs, and the root activity. A committed swipe
     must reach the same state as ordinary Back; a cancelled swipe must change
     nothing.
  2. Confirm the non-dismissible blocked-preflight dialog still cannot be
     bypassed by Back or a predictive-back gesture.
  3. Confirm API 36's large-screen orientation/resizability behavior needs no
     compatibility property: the app declares no orientation lock and already
     owns portrait/landscape layouts. Do not add the temporary restricted-
     resizability opt-out unless a reproducible tablet defect demands it.
  4. Test multi-window/resizing enough to prove the shell does not leave buttons
     outside the visible bounds; full adaptive redesign remains out of scope.
- **Verification:** Back-stack and safety-gate state match before and after
  rotation, predictive-back cancellation, and process recreation.

### U5. Add a focused inset/navigation regression harness

- **Goal:** Keep the API-36 migration from reverting silently in the next UI
  change.
- **Files:** new `engine/src/androidTest/java/com/simoscal/android/` UI test,
  `engine/build.gradle.kts`, and minimal test tags in `SimoscalApp.kt` or shared
  chrome composables.
- **Approach:**
  1. Add only the Compose UI-test dependencies required by an instrumented shell
     test; do not stand up a broad screenshot-test framework in this unit.
  2. Tag the shell body, top app bar, bottom navigation, and the landscape boost
     action row.
  3. Assert their visible/touch bounds stay inside the device's safe drawing
     bounds in portrait and landscape while the background fills the whole root.
  4. Add navigation assertions for committed and cancelled Back where the test
     APIs permit; retain manual gesture verification for animation quality.
  5. Capture reference screenshots for the release record, but treat bounds and
     navigation assertions—not pixels—as the automated gate.
- **Verification:** The test fails when shell inset consumption is removed or
  when a protected action is deliberately placed under a system bar.

### U6. Run the API-36 release gate and update the record

- **Goal:** Prove the exact minified artifact, not merely a debug layout.
- **Files:** `README.md`, `docs/implementation_details.md`, build outputs only.
- **Approach:**
  1. Run the full Python suite and Android debug/release unit suites.
  2. Run `check`, the merged-manifest permission receipt, `assembleRelease`,
     `bundleRelease`, and the R8 keep-rule inspection.
  3. Run the V0 parity and V6 bridge instrumentation against the minified release
     variant on Android 16; compare the device report with the host golden and
     require zero skipped parity legs.
  4. On the Galaxy Tab A9+, inspect Import, Analyze, Tables/browser/editor,
     Boost with overlay, Limiters, Pedal, Lambda, Slots, Changes, and Build in
     both orientations. Repeat with gesture and three-button navigation, an open
     keyboard, rotation, and at least one resized/multi-window state.
  5. Complete a real-file import → preflight → session → edit → undo/redo → build
     → export/share-to-SimosTools run. Review the report and candidate; do not
     flash it.
  6. Inspect the final artifact: target 36, arm64-only, non-debuggable, no BIN/XDF
     payload, expected signing identity, no unexpected permission, and unchanged
     Chaquopy class names under R8.
  7. Run the 16 KB ZIP/ELF checks and record their result without conflating them
     with the API-36 gate.
  8. Replace README's API-35 hold text with the exact toolchain, inset design,
     device matrix, commands, results, remaining gaps, and date.
- **Acceptance:** All checks above pass on the exact candidate commit. Any
  skipped parity leg, hidden control, broken share, changed calibration bytes,
  or permission addition blocks release.

## Validation matrix

- API 35 arm64 emulator: backward-compatibility smoke, both orientations.
- Galaxy Tab A9+ on Android 16: primary physical gate, portrait/landscape,
  gesture/three-button navigation, IME, rotation, and share handoff.
- Android 16 API 36 emulator: automated shell inset and predictive-back tests;
  use a cutout-capable profile if the physical tablet has no cutout.
- Minified release variant: Chaquopy startup, V0 parity, V6 bridge contract,
  full editing/build/share path.

## Risks

- **Chaquopy task graph on Gradle 8.11.1.** This is the load-bearing unknown.
  Resolve from the concrete producer/consumer error; do not bypass it.
- **Dependency-family rendering drift.** Navigation 2.8 and Material3 1.3 may
  alter component sizing. The full-screen device pass is mandatory because the
  app has no broad screenshot suite.
- **Double-consumed or unconsumed insets.** Centralizing at `Scaffold` and adding
  the bounds regression test are the mitigations.
- **Landscape boost height regression.** The top bar is absent there by design;
  the action row and canvas remain explicit acceptance points.
- **False confidence from debug.** R8 can break Chaquopy while builds stay green;
  the minified-release instrumentation gate remains mandatory.

## Explicitly deferred

- Production upload-key creation and Play App Signing.
- Store listing, screenshots selected for the listing, and Play declarations.
- Full Compose golden/screenshot infrastructure for every screen and theme.
- API 36.1/QPR2-specific APIs.
- Full 16 KB native-runtime remediation and any NumPy pin change it requires.
- Any ECU flash or calibration validation from driving logs.

## Primary references

- Android 16 SDK setup and API-36 toolchain minimums:
  <https://developer.android.com/about/versions/16/setup-sdk>
- AGP/API compatibility table:
  <https://developer.android.com/build/releases/about-agp>
- Android 16 target behavior changes:
  <https://developer.android.com/about/versions/16/behavior-changes-16>
- Compose edge-to-edge setup:
  <https://developer.android.com/develop/ui/compose/system/setup-e2e>
- Material3 inset handling:
  <https://developer.android.com/develop/ui/compose/system/material-insets>
- Predictive back with Navigation Compose:
  <https://developer.android.com/develop/ui/compose/system/predictive-back-setup>
