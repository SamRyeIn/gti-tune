# Mermaid documentation diagrams — implementation plan

**Date:** 2026-08-20
**Origin doc:** `Docs/brainstorms/2026-08-20-mermaid-documentation-diagrams-requirements.md`
**Depth:** Deep — cross-cutting, three repositories, 21 catalog IDs
**Type:** docs / feat

## Summary

Author 20 mermaid diagram blocks (21 catalog IDs; D6 merges into D5) across
`gti-tune`, `simoscal`, and `simoscal-android`, replacing two decaying ASCII
drawings and making three safety-critical conditionals visual. A shared visual
vocabulary is defined first and proven on a two-diagram pilot before the
remaining eighteen are drawn.

## Problem frame

Three repos, ~6,500 lines of Markdown, one mermaid diagram — and two documents
that needed a diagram badly enough to draw one in ASCII art
(`Code/README.md:68-89`, `knowledge/ecu-tuning-basics.md:245-264`, the latter
already misaligned). Full problem statement, the four readers, and the three
named failures are in the origin doc; this plan does not restate them.

## Requirements carried forward

Goals G1–G5 and acceptance examples AE1–AE7 from the origin doc apply
unchanged. Decisions KD1–KD8 carry forward, amended by KTD2, KTD3 and KTD5
below.

## Path convention

Each unit names its repository. Paths are relative to **that** repository:
`gti-tune` paths are repo-root-relative (`knowledge/…`, `Code/README.md`);
`simoscal` paths are relative to `Code/`; `simoscal-android` paths are relative
to that repo's own root. `Code/` and `simoscal-android` are independent git
repositories.

## Key technical decisions

**KTD1 — The vocabulary is a copy-pasted `classDef` block, because mermaid has
no include mechanism.** Every one of the 20 blocks inlines its own styling.
The canonical text lives in `Docs/diagram-conventions.md` (gti-tune) and is
copied verbatim. Five roles, each with a fixed shape and class: human step
(Sam), automated/Claude step, safety gate or refusal, external tool
(SimosTools, TunerPro, VW_Flash), and data file (bin, CSV, `.md`). This is the
single largest drift risk in the plan and is why the conventions doc exists.

**KTD2 — D7 uses `flowchart`, not `gitGraph`** (resolves origin OQ1). The tune
lineage is linear with one project split at R15/R16. `gitGraph` renders
branches, implying a branching history that does not exist and that no reader
should infer. Flashed / superseded status is carried by `classDef`, not by
graph topology.

**KTD3 — D6 merges into D5 as numbered annotations** (resolves origin OQ2).
Tune order is a property of the torque chain, not a second graph. Duplicating a
twelve-node diagram to add four numbers guarantees the two drift. The catalog
keeps 21 IDs; the work produces 20 blocks.

**KTD4 — `AGENTS.md` receives no diagrams** (resolves origin OQ3). It states
its own role explicitly: *"Do not create a second rule set here … keep this
file as the Codex entry point."* It points at `CLAUDE.md`, which gets D2 and D3.

**KTD5 — D1 draws and links all three repos, including the private one**
(user decision, amending KD3). `simoscal-android` is private; a stranger
reading the public `simoscal` README will meet a door that does not open. This
is accepted on the assumption android goes public. See Risks for the revisit
trigger.

**KTD6 — `mmdc` is a necessary but not sufficient gate.** `mmdc` bundles
mermaid 11.16.0; Obsidian 1.12.7 ships its own build. A clean compile proves
syntax, not that the vault renders it. Every diagram landing in `knowledge/` or
`index.md` additionally needs an eyeball in Obsidian, in both light and dark.

**KTD7 — simoscal changes land via PR from a branch cut off `main`.** That
repo's `main` carries a `pull_request` ruleset, and its working tree is
currently on `feat/iat-timing-correction` with untracked `android/`. Doc work
must not entangle with that feature branch. `gti-tune` and `simoscal-android`
have no ruleset and take direct commits.

**KTD8 — Every node label carrying a table ID is quote-wrapped.** Verified, not
assumed: `A[IP_FAC_BPA_SP[0]]` exits 1 and produces no SVG;
`A["IP_FAC_BPA_SP[0]"]` renders. Applies to roughly half the set.

**KTD9 — Styling is theme-explicit.** Both Obsidian and GitHub theme light and
dark. Every class sets an explicit stroke and a fill chosen for legibility in
both; no diagram relies on renderer defaults.

## Implementation units

### U1. Diagram vocabulary + pilot slice (D1, D10)

**Repo:** gti-tune (+ read-only reference to the other two)
**Goal:** Fix the visual grammar and prove it on the two highest-value
diagrams before eighteen more inherit it.
**Requirements:** G4, G1, G2; KD2, KTD1
**Dependencies:** none

**Files**
- create `Docs/diagram-conventions.md` — canonical vocabulary, the copy-paste
  `classDef` block, the ID-plus-legend rule (KD4), quoting rule (KTD8), theme
  rule (KTD9)
- draft D1 (system map) and D10 (`build()` gate sequence) — not yet inserted

**Approach**
D1 and D10 are chosen deliberately as the pilot: one is pure structure and
appears verbatim in three repos, the other is a safety branch with a
conditional. Between them they exercise every class in the vocabulary. D10 must
make the `reference_bin=` branch legible as a branch — that is its whole
purpose.

**Verification**
- Both compile under `mmdc` with exit 0 and non-empty SVG
- Both published in one Artifact and reviewed by Sam in light and dark
- Sam confirms the five roles read correctly before U2 begins
- **This unit is a hard gate. No further diagram is drawn until it passes.**

### U2. simoscal P1 diagrams (D10 insert, D11, D12, D14)

**Repo:** simoscal (`Code/`) — PR from a branch off `main` per KTD7
**Goal:** The public repo's safety and orientation diagrams.
**Requirements:** G1, G2, G3; AE2, AE3, AE4
**Dependencies:** U1

**Files**
- modify `README.md` — insert D1 (§top), D10 (§Authoring / build), D14
  (§Safety, line ~498); **replace** the ASCII fence at lines 68-89 with D12
- modify `docs/BETA_GUIDE.md` — D11 spanning §3 (line ~85) → §5 → §6 (~192)
- modify `docs/authoring-a-revision.md` — D10 cross-reference at §3 (~128)

**Approach**
D11 is the largest single readability win: a decision tree currently spread as
prose across three sections. It must route supported / `INSPECT_ONLY` /
unsupported to the §6 porting path without the reader consulting §3 and §5.
D12 replaces ASCII outright — the fence at 68-89 is deleted, not kept alongside
(KD7).

**Verification**
- All four compile clean; no box-drawing characters remain in `README.md`
- AE2, AE3, AE4 satisfied by reading the rendered GitHub view
- PR opens against `main`, not `feat/iat-timing-correction`

### U3. simoscal P2 diagrams (D13, D15, D16)

**Repo:** simoscal (`Code/`)
**Goal:** Complete the library's diagram set.
**Requirements:** G4
**Dependencies:** U2

**Files**
- modify `README.md` — D13 (§Authoring, ~91), D15 (§BTP, ~374)
- modify `docs/authoring-a-revision.md` — D16 (§1, ~15)

**Verification:** all compile; vocabulary classes match U1 verbatim.

### U4. gti-tune P1 diagrams (D2, D3, D5+D6)

**Repo:** gti-tune — direct commit
**Goal:** The project's core loop and its central domain knowledge.
**Requirements:** G1, G3; AE5, AE6
**Dependencies:** U1

**Files**
- modify `CLAUDE.md` — D2 (§The tuning loop, line 74), D3 (§Folder structure, 25)
- modify `index.md` — D1, plus D2/D3 references
- modify `knowledge/ecu-tuning-basics.md` — **replace** the ASCII fence at
  lines 245-264 with D5, carrying the tune-order numbering per KTD3

**Approach**
D2 must visually separate Sam's steps (flash, drive, log) from Claude's
(revise, verify, review) — that split is the diagram's reason to exist (AE6).
D5 is Obsidian-bound and therefore subject to KTD6.

**Verification**
- No box-drawing characters remain in `knowledge/ecu-tuning-basics.md`
- D5 rendered and eyeballed **in the Obsidian vault**, light and dark (KTD6)
- AE5, AE6 satisfied

### U5. gti-tune P2/P3 diagrams (D4, D7, D8, D9)

**Repo:** gti-tune
**Goal:** Wiki and lineage navigation.
**Requirements:** G4
**Dependencies:** U4

**Files**
- modify `CLAUDE.md` §5 and `Code/README.md` §Log analysis — D4
- modify `Tunes/REV_LOG.md` — D7 near the head (after line ~12), per KTD2
- modify `knowledge/eqt-s2-track-log-p2563.md` — D8 at §Headline finding (~16)
- modify `index.md` — D9, **provisional**

**Approach**
D9 is P3 and provisional: Obsidian's graph view already does this job. Render
it, look at the GitHub view, and drop it if it does not earn its place. Deleting
it here is a success outcome, not a failure.

**Verification:** all compile; Obsidian check for D5-adjacent notes; explicit
keep-or-drop decision recorded for D9.

### U6. android P1 diagrams (D17, D18, D20)

**Repo:** simoscal-android — direct commit
**Goal:** Make a 1,117-line README navigable.
**Requirements:** G1, G2; AE7
**Dependencies:** U1

**Files**
- modify `README.md` — D1 (§top), D17 (§Status, ~22), D20 (§V8, ~286)
- modify `docs/implementation_details.md` — D18 (§Architecture, ~59)

**Approach**
D17 replaces the need for §"Ordering note — V1 came before V0, necessarily" to
carry the explanation alone; the timeline shows the real chronology directly.
D20 must encode the refusal asymmetry — dragged values clamp, typed values are
refused — as two distinct outcomes, because that is a safety property.

**Verification:** all compile; AE7 satisfied; `timeline` confirmed rendering in
the GitHub view.

### U7. android P2 diagrams (D19, D21)

**Repo:** simoscal-android
**Goal:** Complete the android set.
**Requirements:** G4
**Dependencies:** U6

**Files**
- modify `docs/implementation_details.md` — D19 (§V6, ~189)
- modify `README.md` — D21 (§Build path, ~857)

**Verification:** both compile; vocabulary matches.

### U8. Cross-repo sweep and sign-off

**Repo:** all three
**Goal:** Prove the set is complete, consistent, and rendering.
**Requirements:** G1–G5; AE1
**Dependencies:** U2–U7

**Approach**
Sweep every `.md` in all three repos: extract each mermaid block, compile it,
and confirm exit 0. Grep for surviving box-drawing characters. Diff the three
copies of D1 against each other and against `Docs/diagram-conventions.md`.
Republish the complete set as one Artifact.

**Verification**
- AE1: all 20 blocks compile, including every bracketed table ID
- Zero box-drawing characters in any documentation file
- The three D1 copies are byte-identical
- Every diagram's `classDef` block matches the conventions doc
- Final Artifact reviewed by Sam in both themes

## Scope boundaries

**In:** 20 diagram blocks, one conventions doc, insertion and ASCII removal.

**Out:** generating diagrams from live data (origin KD1 — deferred); CI or
pre-commit render checks; PNG/SVG committed as images; restructuring or
splitting host documents; any edit to `code_review.md` in either repo (they are
append-only logs).

### Deferred to follow-up work

- Mermaid emitted into `report.md` and `analysis_findings.md` from the edit
  journal — the natural sequel once the vocabulary is proven.
- A `mmdc` compile gate in CI. No repo here runs CI on documentation today.

## Risks

**R1 — Vocabulary drift across 20 inlined `classDef` blocks.** Mermaid has no
include; every block is a copy. Mitigation: the conventions doc is canonical
and U8 diffs every block against it. This is the most likely long-term decay
mode and it will not announce itself.

**R2 — `mmdc` passes, Obsidian does not render** (KTD6). Version skew between
the two mermaid builds. Mitigation: `knowledge/` and `index.md` diagrams get a
mandatory vault check in U4/U5; falling back to `flowchart` from any newer
diagram type is always available.

**R3 — D1's android link is a dead end for public readers** (KTD5, accepted).
Revisit trigger: if `simoscal-android` has not gone public by the time the beta
program opens to testers, change the node to unlinked-and-labelled rather than
leaving strangers a broken door.

**R4 — simoscal doc PR entangles with in-flight feature work.** That repo sits
on `feat/iat-timing-correction` with untracked `android/`. Mitigation: KTD7 —
branch from `main`, and confirm the working tree before starting U2.

**R5 — Diagrams drift from code as simoscal evolves.** Acknowledged in origin
KD1 as the cost of hand-authoring. Accepted; the deferred generated-diagram
work is the real fix.

## Verification (end-to-end)

1. Every mermaid block in all three repos compiles under `mmdc` with exit 0 and
   a non-empty SVG (AE1). Note that piping `mmdc` output masks its exit code.
2. No box-drawing characters survive in any documentation file (G3).
3. The three D1 copies are byte-identical; every `classDef` matches
   `Docs/diagram-conventions.md` (G4).
4. Obsidian-bound diagrams render correctly in the vault, light and dark (G5,
   KTD6).
5. AE2–AE7 each confirmed against the rendered view of their host document.
6. The complete set is published as one Artifact and signed off by Sam.

## Open questions

**Non-blocking:**

1. Does D9 survive contact with the GitHub render, or is it dropped? Decided in
   U5.
2. Should `Docs/diagram-conventions.md` be copied into `simoscal` so public
   contributors can follow it, or linked cross-repo? Defer until U2 shows
   whether an outside contributor would ever need it.

## Sources

- Origin: `Docs/brainstorms/2026-08-20-mermaid-documentation-diagrams-requirements.md`
- Repo state verified 2026-08-20: `simoscal` public with `pull_request` ruleset
  on `main`; `gti-tune` public, no ruleset; `simoscal-android` private.
- Tooling verified 2026-08-20: `mmdc` 11.16.0, mermaid 11.16.0, Obsidian
  1.12.7. `mindmap`, `timeline` and `stateDiagram-v2` all compile.
