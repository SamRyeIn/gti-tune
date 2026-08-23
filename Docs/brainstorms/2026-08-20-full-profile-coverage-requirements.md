---
date: 2026-08-20
status: Brainstorm complete, ready for /ce-plan
owner: Sam
scope: simoscal library (profile maps) — no Android changes
---

# Full profile coverage — requirements

Map every table the tuning guides name or the revision lineage has touched, so the
Android app can edit all of them instead of the 122 it reaches today. **93 new
`TableSpec` entries; zero Kotlin changes.**

> [!note] The framing changed during this brainstorm
> The opening ask was read as "edit any table in the XDF" — all 3,912 base tables
> plus the patch XDF. That is *not* the request. The request is **any table
> mentioned in the guide or that we've touched during tuning**, which is a
> bounded, hand-mappable set. Everything below is scoped to that.

Related: [[ecu-tuning-basics]] · [[sc8s50-switchpatch-xdf]] · [[tuning-getting-started]]

## Problem

The app's editable surface is the profile map, not the XDF. `catalog()` enumerates
`ResolvedProfile.names()` — the profile's declared specs — so a table nobody wrote a
`TableSpec` for is unreachable, whatever the XDF holds.

Today that is **122 mapped tables** — 35 base and 87 patch. Only **33** of them are
editable in the generic Tables screen: the base 35 less 2 domain-owned, plus nothing
at all from the patch space, whose 87 specs are reachable only through the purpose-
built Boost and Slots screens.

`profiles/sc8s50.py` states its own scope in its docstring: *"Every logical name
below is bound to a symbol that the R00–R12 revision lineage actually touched."*
That was the right boundary when it was written. The lineage is now past R16, and
the guides describe a good deal more than the lineage has used.

The practical cost: wanting to change a table outside those 122 means leaving the
tablet, going back to the Mac, and adding a spec by hand before a revision can even
express the edit. The whole point of the app is that the loop closes on one device.

## Goals & success criteria

1. Every table named in `3. ECU Tuning - Basics.docx`, `4. ECU Tuning - Not the
   Basics.docx`, [[ecu-tuning-basics]], or any `TUNE_*.py` revision resolves through
   a profile spec.
2. The app shows and edits them with **no Kotlin change** — they arrive through
   `catalog()`.
3. No table becomes reachable without a spec. The safety properties that live on a
   spec — corrected units, guard tags, declared shape, `owner` — remain in force for
   every reachable table.
4. `IP_IGA_BAS_IVVT_VVL_PORT_H` — Basic ignition angle, VVL 0, port H and
   `C_PRS_IM_SP_LIM` — Offset to the pressure behind air cleaner for the limitation
   of the manifold setpoint both become reachable, closing the two known
   discrepancies below.
5. The mapped surface goes **122 → 215** tables (base 35 → 102, patch 87 → 113).
   The subset editable in the generic Tables screen goes **33 → 126**, before any
   of the new tables are given an `owner`.

## Scope

**In:** 67 new specs in the base space (35 → 102), 26 in the patch space (87 → 113),
and a test per spec asserting it resolves at the declared shape.

**Out:** the other ~3,845 base tables. Browse/search rework beyond assigning each new
spec its `group` (the grouped browser itself already shipped — see Key decision 4).
Tablet layout. Any new Android code.

### The 67 base-space tables, by domain

| Domain                                                        | Count | Cited by      |
|---------------------------------------------------------------|-------|---------------|
| Impulse combustion (pops and bangs), `*IMP_COMB*`             | 25    | guide         |
| Driver interpretation / pedal maps, `IP_FAC_TQ_REQ_DRIV_*`    | 9     | notes         |
| Ignition port H, `IP_IGA_BAS_IVVT_VVL_PORT_H[STND][i][e]`     | 9     | notes         |
| Turbo protection (speed, IAT, torque cut)                     | 6     | notes         |
| Torque limits and reference                                   | 5     | notes         |
| Speed limiter, `LMVLim_vMax_vLim_C_VW.*`                      | 4     | guide + notes |
| Head-temperature control, `CoTE_tHdCtlSp_*`                   | 3     | notes         |
| Lambda full-load enrichment, `IP_LAMB_FL_SP*`                 | 2     | notes         |
| Boost remainder (`C_PRS_IM_SP_LIM`, two axes, one diagnostic) | 4     | notes + tunes |

### The 26 patch-space tables, by domain

Traction-control PID (slip weights, I and D terms, filter, clamps), soft/medium/hard
rev limits, SCC threshold and duration, wastegate temperature compensation, EGT
ignition table and axis, flex-fuel weight axis, lambda modifier, RAL and cruise
button mappings.

## Key decisions

1. **Hand-map all 93 as real specs.** Not a generic "any XDF table" path. Guard
   tags, corrected units, declared shapes and `owner` live only on specs; a table
   reached without one carries none of them. That is `CR-20260815-06`, and
   `C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint is what it costs when it
   goes wrong: the XDF labels a genuine kg/stk store as mg/stk, so the sane-looking
   typed correction raises the ceiling roughly 1.44 million-fold. Hand-mapping keeps
   the existing safety model exactly as it is and simply stops the map being the
   limit.
2. **Impulse combustion is in scope.** All 25, despite appearing only in the guide
   and never in the lineage.
3. **The 26 patch tables get the generic grid, not owners.** Unlike the 87 per-slot
   tables — which carry cross-slot coherence a grid edit can silently break, the
   substance of `CR-20260813-01` — these are independent scalars and small curves.
   The existing build-time patch sanity post-check still runs on every patched
   build. The per-slot tables stay owner-locked.
4. **Library only; reassess browsing from evidence.** The app inherits all 93
   through `catalog()`, and its search already filters on ID, description and units.
   Whether a 126-table catalog needs category grouping is a question to answer after
   using the real list on the tablet, not before.

   > [!note] Answered 2026-08-22 — grouping shipped ahead of this work
   > Sam called it on the 58-table list: the browser now renders one collapsible
   > section per domain (**Boost · Timing · Fueling · Airflow · Limiters ·
   > Turbo & thermal · Pedal & torque request · Launch & traction**), grouped by
   > a curated `TableSpec.group` rather than by the XDF's own categories — those
   > file every breakpoint vector under "Axis" and put `IP_PUT_SP` — Pressure up
   > throttle setpoint under "Airflow".
   >
   > **This changes what this plan must deliver.** `simoscal.tune.profile.GROUPS`
   > is a closed vocabulary and every generically editable spec must name one:
   > `Profile.ungrouped()` must stay empty for the base map, and
   > `_ungrouped_is_deliberate()` fails at import for a patch spec with no `owner`
   > and no `group`. So each of the 93 new specs is authored with a `group=`, added
   > to the `_GROUPS` block in `profiles/sc8s50.py` (which errors on a name in no
   > group *and* a group naming no table), and the per-spec test asserts the group
   > alongside the shape.
   >
   > Two of the domains in the table below have no home in the current eight and
   > are the one open question this hands to planning: **impulse combustion (pops
   > and bangs), 25 tables** and the patch space's **flex-fuel modifier /
   > map-switching / RAL / gauge** switches. Either they earn a ninth and tenth
   > heading or they are filed under existing ones — decide it when the specs are
   > written, not by defaulting.

## Acceptance examples

- **AE1** — `catalog()` on a session opened with base + patch XDFs returns **126**
  entries — 100 base (102 specs less the 2 domain-owned) and 26 patch — minus one
  for each new table planning decides to give an `owner`. Passing
  `include_domain_owned=True` returns all **215**.
- **AE2** — Every new spec resolves against `SC8S50.V1.0.xdf` at its declared shape;
  a shape mismatch fails loud at resolution rather than at edit time.
- **AE3** — `IP_IGA_BAS_IVVT_VVL_PORT_H[STND][0][0]` — Basic ignition angle, VVL 0,
  intake 0, exhaust 0, port H appears in the catalog alongside its already-mapped
  `PORT_L` counterpart, at the same shape.
- **AE4** — `C_PRS_IM_SP_LIM` is editable and, being float-bug flagged, refuses a
  write above its declared max while accepting one below it.
- **AE5** — A generic edit to a per-slot patch table is still refused; a generic
  edit to one of the 26 new patch tables is accepted and journaled.
- **AE6** — Building a patched session after editing a new patch table still runs
  the patch sanity post-check, and a failure fails the build.
- **AE7** — The Android app displays and edits a newly mapped table with no Kotlin
  change and no new bridge op.

## Findings this brainstorm turned up

> [!warning] Two discrepancies, worth fixing regardless of what else ships
> **`IP_IGA_BAS_IVVT_VVL_PORT_H` is unmapped while `PORT_L` is fully mapped.** All
> nine `[STND][i][e]` cells of the L set have specs; none of the H set do, and
> [[ecu-tuning-basics]] cites both. This reads as an oversight, not a decision.
>
> **`C_PRS_IM_SP_LIM` is not in the profile at all.** `Code/code_review.md`'s "Not
> findings (checked and clean)" section states that it and `C_PRS_IM_SP_MAX` were
> *"left generically writable deliberately."* That is true of `_MAX`, which has a
> spec. `_LIM` has none, so it is not writable — nor readable — through any path.
> The review recorded a property the map does not have.

> [!note] The curated patch XDFs in `Code/xdf/` do not parse
> `SC8S50_switchpatch29.33_v1.005.xdf` and `…v1.006.xdf` both fail with *"uniqueid
> 0x11f9c reused with DIFFERENT data"*. This is known and documented in
> `simoscal/btp.py`. The authoritative definition is BinToolz'
> `definitions/S50 Switch Patch.29.33.V2.xdf` — **185 tables**, of which 87 are
> mapped and 26 are the gap. Any planning work must read the BinToolz file, not the
> curated copies.

## Outstanding questions

**Blocking — need a decision per table during planning:**

- Which of the new tables need an `owner` rather than the generic grid. The
  candidates are the ones where a plausible typed value is catastrophic or where
  coherence spans tables: turbo protection (`C_N_TCHA_MAX` — Maximum turbo charger
  speed and its setpoint sibling), torque limits (`IP_TQI_POW_MAX_BAS` — Maximum
  allowed indicated torque at full load), the speed limiter quartet, the rev-limiter
  trio, and SCC threshold/duration.
- Which need guard tags — particularly whether any of the new float32 tables belong
  on `FLOAT_BUG_SYMBOLS`, and whether any repeat the kg/stk unit trap.
- Whether the impulse-combustion set needs a caution string, given it drives exhaust
  and catalyst temperature.

**Deferred, not blocking:**

- Does a 126-table catalog need category grouping in the app? Answer after using it.
- Should the tablet two-pane layout come next? Already owed independently.
- Do any of the newly mapped domains deserve a purpose-built screen the way boost
  and slots have?

## Handoff

Ready for `/ce-plan`. The plan needs to resolve the per-table `owner` and guard-tag
questions above, then the work is largely mechanical: spec entries plus a resolution
test each.
