# Human-friendly tune API — requirements

**Date:** 2026-07-19
**Status:** Brainstorm complete, ready for `/ce-plan`
**Owner:** Sam

## Problem

The tuning loop works, but revision scripts are only writable (and largely only
readable) by Claude. `TUNE_Basics_Guide_R12.py` illustrates the disease:

- It imports private helpers from five earlier revision scripts (R03, R07, R08,
  R10, R11) and monkey-patches another module's globals to inject its change.
- The actual tuning intent — "cap slot 5 at 10 psi gauge" — is ~40 lines buried
  in ~200 lines of orchestration, verification, and report plumbing that is
  re-written (by Claude) every revision.
- Understanding what a revision flashes requires mentally executing a chain of
  files.

Sam wants to (1) be able to author and confidently tweak revisions himself, and
(2) eventually share the library with other Simos 18 tuners who have **no AI
assistance** — the human-facing layer must stand on its own.

## Goals & success criteria

- A tune revision script is a **self-contained, one-page declaration** of the
  full calibration in physical units, written with domain-level function calls.
- No revision script ever imports from another revision script.
- The standard safety pipeline (patch application, checksum correction,
  readback verification, raw-diff audit vs the previous revision, report +
  compare plots) runs from **one library entry point** and cannot be forgotten
  or partially copied.
- A newcomer with Simos 18 knowledge but no simoscal history can read a
  revision script and state what it changes; and can write a simple revision
  (e.g. change a boost target) from docs alone.
- Works against **any Simos 18 XDF**, not just `SC8S50.V1.0.xdf` — table
  references go through a symbol-resolution layer that fails loud when a
  logical name doesn't resolve in the loaded XDF.

## Scope

**In scope (v1 domain modules):**

| Module        | Covers                                                                          |
|---------------|---------------------------------------------------------------------------------|
| `boost`       | PUT setpoint ceiling/curves, pressure limiters, PQ/compressor caps, airmass cap |
| `wastegate`   | `IP_FAC_BPA_SP[0]/[1]` — Map for boost pressure actuator setpoint (feedforward) |
| `fueling`     | Lambda setpoint grids, fuel-pressure-related tables touched by the lineage      |
| `ignition`    | Base timing grids touched by the lineage                                        |
| `limits`      | Torque/limiter tables from the basics-guide SOP                                 |
| `switchpatch` | BTP patch application, slot PUT-setpoint curves, TC flags, patch sanity checks  |

Plus the shared machinery:

- `Tune` object wrapping a CalFile + XDF profile; `tune.build("R13")` runs the
  full standard pipeline and writes the timestamped output folder.
- Symbol-resolution profile layer: logical names → XDF table IDs per loaded
  XDF; unresolved = loud failure, never a guess (extends the proven
  `sop_recipe` resolution pattern).
- **Auditable edit journal (the A+B hybrid):** every domain-method call is
  recorded internally as a typed entry (intent, table ID + plain-English
  description, before/after values, units); `build()` emits the standard
  report from that journal, in the same spirit as `RecipeReport`.
- Safety invariants carried over unchanged: fail loud, never silently clamp,
  never flash, guarded ceiling writes, the `C_M_AIR_CYL_SP_MAX` — Maximum
  allowed airmass setpoint kg/stk trap encoded in the library (not in per-tune
  scripts), checksum verification before any bin is declared buildable.

**Out of scope:**

- Flashing, or any interaction with the SimosTools app.
- The log-analysis battery (already its own module) — unchanged.
- Rewriting the existing R00–R12 scripts; they are frozen history.
- Non-Simos-18 platforms (design keeps the door open via the profile layer,
  but no second platform is built or tested in v1).
- A no-code config/spec format — revisions stay Python scripts.

## Key decisions

1. **Revision model: flat script per revision** (revision-by-separate-file
   kept). Each `TUNE_<Tune>_R<NN>.py` declares the entire calibration
   top-to-bottom via domain functions; creating R(N+1) = copy, edit, run.
   Chosen over a layered change-set project to preserve the existing
   convention, keep any single file the complete truth, and allow trivial
   side-by-side revision diffs. Accepted cost: the unchanged bulk is
   duplicated each revision — acceptable because domain functions shrink a
   full declaration to roughly a page.
2. **Audience: any Simos 18 XDF.** Hence the profile/symbol-resolution layer
   is a v1 requirement, not a later generalization.
3. **Approach: A + B hybrid.** Domain-module API for authoring ergonomics,
   with mandatory internal typed-entry recording for auditability. The
   existing private helpers (R03–R11) are the distillation source for the new
   modules, not discarded.
4. **v1 includes the switch-patch module** — currently the gnarliest
   private-helper code and central to the active lineage (R07+ patched bins).

## Key flows

1. **Author a revision (human or Claude):** copy previous revision script →
   edit domain calls (physical units) → run it → review `report.md` +
   compare plots → human review gate → flash (human, unchanged).
2. **Adopt a different XDF:** load tune with another Simos 18 XDF → profile
   resolves logical names → any unresolved symbol fails loud listing what
   didn't resolve, before any edit is attempted.
3. **Audit a revision:** read the one script (intent) and the generated
   report (journal of every edit with before/after + verification verdicts).

## Acceptance examples

- **AE1:** `TUNE_Basics_Guide_R13.py`, written in the new style, reproduces
  the R12 output bin **byte-identical** (or with an explained, enumerated
  diff) while containing zero imports from other revision scripts.
- **AE2:** The R12 valet change ("slot 5 flat at 10 psi gauge") is expressible
  in ≤ 5 lines of domain calls, with the floor-not-round psi→hPa conversion
  handled by the library.
- **AE3:** Pointing the same script at an XDF missing one referenced table
  fails loud before any edit, naming the unresolved logical symbol and the
  XDF; no bin is written.
- **AE4:** `build()` output includes the edit journal: every changed table
  listed as `` `ID` — Description`` with before/after values and units; the
  raw-diff audit reports zero unexplained bytes vs the declared change-set.
- **AE5:** Attempting `airmass_cap(2000)`-style misuse of
  `C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint is impossible or
  fails loud: the API takes mg/stk and performs the kg/stk raw conversion
  internally.
- **AE6:** A revision script that only calls domain functions and `build()`
  still produces the full standard artifact set: saved bin, `report.md`,
  `compare/` PNGs, checksum CLEAN verdict.

## Deferred / out of scope for later

- Layered/manifest hybrid revision model (revisit if flat scripts grow past
  ~2 pages).
- Second-platform profile (other ECU families).
- Config-file (no-code) authoring front end.
- Public packaging/distribution (PyPI, docs site) — shareability shapes the
  design now; publishing is its own later effort.

## Outstanding questions

- **Deferred:** How fuzzy should profile symbol resolution be across Simos 18
  XDFs (exact ID, title match, per-XDF explicit map file)? Decide at plan
  time; start strictest.
- **Deferred:** Whether `sop_recipe` is refactored to sit on the new journal
  types or left as-is with the new layer alongside it.
- **Deferred:** Naming (`simoscal.tune` vs top-level `Tune` export) and how
  the `lambda` keyword collision is handled (`fueling` chosen provisionally).
