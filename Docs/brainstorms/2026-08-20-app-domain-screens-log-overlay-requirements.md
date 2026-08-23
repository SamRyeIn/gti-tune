---
date: 2026-08-20
status: Brainstorm complete, ready for /ce-plan
owner: Sam
scope: simoscal-android app + simoscal library (log parsing, domain ops)
---

# App domain screens + log overlay — requirements

Extend what made the boost/slots editor work — domain-shaped surfaces, physical
units, safety invariants at the fingertip — to more of the tuning loop: a
**logged-pull overlay on the boost screen**, and **three new purpose-built
screens** (limiters, pedal feel, lambda enrichment).

Related: [[2026-08-20-full-profile-coverage-requirements]] ·
[[ecu-tuning-basics]] · the deferred question that brainstorm left open ("do any
newly mapped domains deserve a purpose-built screen?") is answered here.

## Problem

The app edits well but tunes blind. The boost editor shows the target curve,
never where the car actually went — closing that gap still means the Mac.
Meanwhile the full-profile-coverage work is about to make ~93 more tables
reachable, and for a handful of domains the generic grid is the wrong shape:
their values carry ordering or coherence invariants (soft ≤ medium ≤ hard rev
limits, a speed-limiter quartet that must move together, a lambda curve with a
lean-danger direction) that a cell-by-cell grid cannot express, let alone
enforce at the fingertip.

## The pattern being repeated

What the boost/slots editor established, and every surface here inherits:

1. Domain-shaped visualization, not a raw grid.
2. Physical units in and out, requested-vs-encoded always shown.
3. Safety invariants drawn and enforced tactilely — dragged values clamp,
   typed values are refused.
4. Multi-table coherence owned by the screen: one Apply = one coherent set of
   journaled ops.
5. Reference context ghosted behind the draft (other slots, stock values, and
   now: the log).

## Goals & success criteria

1. On the tablet, after a drive, Sam can open a SimosTools log, pick a pull,
   and see actual boost **and** the ECU's boost setpoint drawn behind the slot
   curves being edited — the flash → log → review → revise loop closes on one
   device for boost.
2. Limiters, pedal feel, and lambda enrichment are editable through screens
   that make their invariants visible and unbreakable, not through the grid.
3. The overlay is provably inert: loading a log changes no session state and
   no output byte.
4. All new screens ride on `catalog()`/domain ops over specs delivered by the
   full-profile-coverage plan — no table becomes reachable without a spec.

## Scope

**In:**

- **Log overlay (boost screen):** SAF-pick a `simostools-*.csv` already on the
  tablet; auto-detect WOT pulls; user selects a pull; overlay that pull's
  actual boost and boost setpoint vs rpm, in psi, behind the slot curves.
  Gear attribution honors the header rule (`Gear ()` zero-indexed vs
  `Gear (gear)` actual) and samples are trimmed to the pull's attributed gear.
- **Limiters screen:** patch-space soft/medium/hard rev limits on one rpm
  strip with soft ≤ medium ≤ hard enforced at the fingertip, plus the
  `LMVLim_vMax_vLim_C_VW.*` — Speed limiter quartet edited as one coherent
  control (target + hysteresis visualized).
- **Pedal feel screen:** `IP_FAC_TQ_REQ_DRIV_*` — Driver interpretation /
  pedal maps as a pedal-% vs requested-torque curve editor, stock curve
  ghosted behind the draft.
- **Lambda screen:** `IP_LAMB_FL_SP*` — Lambda full-load enrichment setpoint
  as a curve vs rpm with a lean-danger band drawn above the safe bound — the
  enrichment analogue of the boost base-ceiling band.

**Out (explicitly):**

- Pops & bangs / impulse combustion — excluded despite being the most
  slot-like candidate; guide-only, never in the lineage, and cat-temp risk for
  a party trick.
- Ignition maps (`IP_IGA_BAS_IVVT_VVL_PORT_L/H` — Basic ignition angle, VVL 0,
  ports L/H) — stay in the generic grid; a heatmap/region-delta editor is its
  own later brainstorm.
- Log-coverage shading on generic 2D grids — natural follow-on, not this round.
- Whole-log scatter mode, folder watching / auto-discovery of new logs.
- Any in-app analysis findings, verdicts, or calibration suggestions — the
  overlay draws data; judgment stays with the human (and desktop review).

## Key flows

1. **Overlay:** Boost screen → "Overlay log" → SAF picker → pull list (gear,
   rpm span, duration) → pick one → actual + setpoint traces render behind the
   curves → edit slots against them → Apply as today. Overlay persists across
   slot switches; clearing it is one tap.
2. **Limiters:** Limiters screen → drag/type any of the three rev limits →
   ordering violation clamps (drag) or is refused (typed) → Apply journals the
   changed tables together. Same screen hosts the speed-limiter control.
3. **Pedal / Lambda:** open screen → stock ghost + current curve → drag points
   or type values → lambda values in the danger band refused when typed,
   clamped when dragged → Apply → one journaled op set.

## Acceptance examples

- **AE1** — Picking a real `simostools-*.csv` lists its detected pulls; selecting
  one draws actual boost and boost setpoint vs rpm in psi behind the five slot
  curves.
- **AE2** — Two logs of the same physical pull, one logged under `Gear ()` and
  one under `Gear (gear)`, attribute the same gear and produce the same trimmed
  overlay.
- **AE3** — With an overlay loaded, `build()` output is byte-identical to the
  same session without it, and the journal contains no overlay-related entries.
- **AE4** — Typing a soft rev limit above the medium limit is refused with the
  reason; dragging it clamps at the invariant.
- **AE5** — A speed-limiter change writes all quartet tables coherently as
  journaled ops; a partial write is impossible from the screen.
- **AE6** — The pedal screen shows stock ghost values; every edit reports
  requested-vs-encoded.
- **AE7** — A typed lambda value leaner than the declared bound is refused; the
  band is drawn on the curve.
- **AE8** — All four surfaces work with no new manifest permissions and no
  change to the export gate chain.

## Key decisions

1. **Repeat the boost-editor pattern verbatim** (staged draft, clamp-drag /
   refuse-type, ghosts, atomic Apply). It is proven and already reviewed.
2. **Overlay is read-only decoration.** Log parsing and pull detection live in
   Python (renderer-free), return plot models over the bridge, and never touch
   the session, journal, or safety kernel.
3. **One implementation of pull semantics.** Extract/reuse the desktop analysis
   battery's pull detection rather than reimplementing it in Kotlin — the gear
   and trim rules are subtle enough to have their own memory entries.
4. **SAF per-file pick for logs.** Keeps the zero-permission manifest; the logs
   are already on the same tablet SimosTools runs on. Folder memory is deferred.
5. **Domain screens resolve the `owner` question** the coverage brainstorm left
   blocking for their tables: the rev-limit trio, speed-limiter quartet, and
   lambda enrichment tables become domain-owned (generic grid refuses them),
   consistent with how the per-slot tables are handled. Pedal maps may stay
   dual-path — low stakes.
6. **Ignition and pops & bangs stay out** (see Scope), by explicit choice, not
   omission.

## Dependencies

- The **full-profile-coverage plan** must land first: limiter, pedal, and
  lambda specs are among its 93 new `TableSpec` entries. This work adds the
  domain ops and screens on top.

## Outstanding questions

**Blocking (resolve in planning):**

- Exact patch-space table IDs for the soft/medium/hard rev limits (from
  BinToolz `S50 Switch Patch.29.33.V2.xdf` — the curated copies do not parse).
- Which tables constitute the coherent speed-limiter write, and what the
  hysteresis relationship is.
- The lambda lean bound: what value, where it comes from (guide vs judgment),
  and whether it is a hard refusal or a strong warning. This is a calibration
  judgment, not a UI default.
- ~~Whether Sam's active PID list logs a usable boost **setpoint** channel~~ —
  **verified 2026-08-20**: the R14 logs carry both `PUT (kpa)` and
  `PUT SP (kpa)` (and `Boost (psi)`, `MAP SP (kpa)`), so actual + setpoint are
  both available.
- Whether pull detection can be imported on-device as-is (no matplotlib in its
  import closure) or needs extraction first.

**Deferred:**

- Log-coverage shading on generic 2D grids.
- Ignition heatmap editor.
- Remembering the SimosTools log folder / newest-log shortcut.
- Overlaying two pulls (before/after a revision) on the same canvas.

## Handoff

Ready for `/ce-plan`, sequenced after (or together with) the full-profile
coverage plan. Suggested unit order: log overlay first (highest payoff, zero
new write paths), then Limiters (smallest editor), then Pedal, then Lambda.
