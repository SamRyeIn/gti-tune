# Mermaid documentation diagrams — requirements

**Date:** 2026-08-20
**Status:** Brainstorm complete, ready for planning
**Scope:** all three repos — `gti-tune` (this repo, including the `knowledge/`
Obsidian vault), `simoscal` (`Code/`, public, GPL-3.0), and `simoscal-android`
(`~/simoscal-android`).

## Problem

Across three repos and roughly 6,500 lines of hand-written Markdown there is
exactly **one** mermaid diagram, and it sits in a brainstorm written three days
before this one. That is not because the documentation has no structure worth
drawing. It is because two documents got far enough to need a diagram and drew
it in ASCII art instead:

- `Code/README.md:68-89` — the `CalFile` load → edit → save → verify → flash
  workflow, drawn with box-drawing characters.
- `knowledge/ecu-tuning-basics.md:246-263` — the torque → boost chain, drawn the
  same way and **already misaligned**, because ASCII art has no layout engine
  and every edit degrades it.

The ASCII art is the symptom, not the problem. The need for diagrams is
established; the tooling was simply never adopted.

Four readers pay for that, and all four matter:

1. **Fresh Claude sessions.** The boot chain in `CLAUDE.md` hands a new session
   five documents and a numbered list of a six-step loop. Structure that could
   be absorbed at a glance is instead reconstructed from prose every session.
2. **Beta testers and the public.** `Code/` is public as of 2026-08-19 with a
   334-line `BETA_GUIDE.md`. A stranger's first two questions — *what is this*
   and *is my car supported* — are both answered by prose spread across several
   sections. GitHub renders mermaid natively; nothing is exploiting that.
3. **Sam, in Obsidian.** The vault renders mermaid natively. The single richest
   piece of domain knowledge in the project — the torque → boost chain that
   dictates tune order — is a decaying ASCII drawing.
4. **Future maintainers.** `simoscal-android/README.md` is 1,117 lines and needs
   a dedicated section (§"Ordering note — V1 came before V0, necessarily") to
   explain its own version numbering.

Three specific failures make the cost concrete:

- **The `reference_bin=` footgun is documented only in prose.** Omit that
  argument and `build()`'s byte audit silently does not run, so an undeclared
  change passes quietly. This is stated in `CLAUDE.md`, in `Code/README.md`, and
  in a private auto-memory — and private memory **does not transfer to
  subagents**. A conditional branch is exactly what a flowchart makes
  unmissable and what a paragraph makes skippable.
- **The supported-car path is a decision tree written as prose**, spread across
  `BETA_GUIDE.md` §3, §5 and §6. Supported / `INSPECT_ONLY` / unsupported →
  porting path is a tree. It is currently three sections of text.
- **Nothing states how the three repos relate.** `gti-tune` consumes `simoscal`;
  `simoscal-android` embeds it; SimosTools (third-party) does the flashing that
  none of them do. No single document draws this.

## Goals & success criteria

1. **A reader orients without reading.** Someone landing cold on any of the
   three repos can tell what the project is, where they are in it, and what the
   other two repos do, from one diagram in the README.
2. **Every safety-critical conditional is visual.** The `reference_bin=` branch,
   the flash boundary, and the android clamp-vs-refuse asymmetry each appear as
   a drawn branch, not a sentence.
3. **No ASCII art survives.** Both existing hand-drawn blocks are replaced, not
   supplemented.
4. **The set reads as one system.** A reader who has seen two of the diagrams
   can predict what the shapes mean in the third.
5. **Diagrams render correctly for all four readers** — GitHub, Obsidian, and
   raw-text (Claude) — in both light and dark themes.

Explicitly **not** a goal: restructuring the documents themselves. This work
inserts and replaces diagrams. Reorganising `README.md` or splitting
`code_review.md` is separate work.

**Verification:** `mmdc` (mermaid-cli) is installed at
`/opt/homebrew/bin/mmdc`. Every diagram must compile to SVG via `mmdc` before it
is committed — that is the syntax gate, and it is scriptable over all
`.md` files in the three repos. `mmdc` exits 1 and writes no output on a parse
failure, so the gate is usable directly; note that piping its output to `tail`
masks that exit code. Before any document is edited, the complete set
is published as a **single rendered Artifact** for visual review, applying the
project's existing human-review-gate discipline to documentation. Theme
correctness is verified by viewing that Artifact in both light and dark.

## Scope

**In scope — 21 diagrams.** Priority is P1 (safety-critical or highest
orientation value), P2 (clear win), P3 (marginal, ship last or drop).

### Cross-repo

| ID  | Diagram        | Home                        | Type        | Pri | Why                                                                                  |
|-----|----------------|-----------------------------|-------------|-----|--------------------------------------------------------------------------------------|
| D1  | The system map | all three READMEs, verbatim | `flowchart` | P1  | gti-tune uses simoscal; android embeds it; SimosTools flashes. Stated nowhere today. |

### gti-tune

| ID  | Diagram               | Home                                  | Type                | Pri | Why                                                                                     |
|-----|-----------------------|---------------------------------------|---------------------|-----|-----------------------------------------------------------------------------------------|
| D2  | The tuning loop       | `CLAUDE.md`, `index.md`               | `flowchart` (cycle) | P1  | The six-step cycle, split by actor. A numbered list hides which steps are Sam's.        |
| D3  | Folder data flow      | `CLAUDE.md`, `index.md`               | `flowchart`         | P1  | The layout table shows roles but cannot show flow between folders.                      |
| D4  | Log analysis pipeline | `CLAUDE.md` §5, `Code/README.md`      | `flowchart`         | P2  | Draws the findings-only boundary: the tool never writes `log_review.md`.                |
| D5  | Torque → boost chain  | `knowledge/ecu-tuning-basics.md:246`  | `flowchart`         | P1  | Replaces decaying ASCII. The core domain knowledge; renders in Obsidian.                |
| D6  | Tune-order overlay    | `knowledge/ecu-tuning-basics.md`      | `flowchart`         | P2  | Same graph, numbered: airflow → boost → wastegate → timing/lambda.                      |
| D7  | Revision lineage      | `Tunes/REV_LOG.md`                    | `gitGraph`          | P2  | 1,122 lines with no visual index. Shows the R15/R16 project split and what was flashed. |
| D8  | P2563 causal chain    | `knowledge/eqt-s2-track-log-p2563.md` | `flowchart`         | P2  | Actuator pinned → boost under target → heat gap. Mermaid for reasoning, not structure.  |
| D9  | Knowledge map         | `index.md`                            | `mindmap`           | P3  | Redundant with Obsidian's graph view; only earns its place in the GitHub view.          |

### simoscal (`Code/`)

| ID  | Diagram                     | Home                                      | Type              | Pri | Why                                                                                 |
|-----|-----------------------------|-------------------------------------------|-------------------|-----|-------------------------------------------------------------------------------------|
| D10 | `build()` gate sequence     | `README.md`, `authoring-a-revision.md` §3 | `flowchart`       | P1  | Makes the `reference_bin=` branch unmissable. Highest safety value in the set.      |
| D11 | Supported-car decision tree | `BETA_GUIDE.md` §3/§5/§6                  | `flowchart`       | P1  | A genuine decision tree currently written as prose across three sections.           |
| D12 | CalFile workflow            | `README.md:68-89`                         | `flowchart`       | P1  | Direct ASCII replacement.                                                           |
| D13 | Three-layer stack           | `README.md` §Authoring                    | `flowchart`       | P2  | `tune` → `CalFile`/`TableView` → bin/XDF. Proves the "substrate" claim at a glance. |
| D14 | The flash boundary          | `README.md` §Safety                       | `flowchart`       | P1  | What the library does vs refuses to do. Matters more now the repo is public.        |
| D15 | BTP patch flow              | `README.md` §BTP                          | `flowchart`       | P2  | Surfaces byte-exact pre-verification as a safety property, not a detail.            |
| D16 | Revision lifecycle          | `authoring-a-revision.md` §1              | `stateDiagram-v2` | P2  | drafted → built → reviewed → flashed → logged → superseded.                         |

### simoscal-android

| ID  | Diagram            | Home                                     | Type              | Pri | Why                                                                                |
|-----|--------------------|------------------------------------------|-------------------|-----|------------------------------------------------------------------------------------|
| D17 | The V-ladder       | `README.md` §Status                      | `timeline`        | P1  | The README needs a whole section to explain its numbering. A timeline replaces it. |
| D18 | App architecture   | `README.md`, `implementation_details.md` | `flowchart`       | P1  | Compose (Kotlin) → bridge → Chaquopy → simoscal → bin. The bridge is the key fact. |
| D19 | A bridge call      | `implementation_details.md` §V6          | `sequenceDiagram` | P2  | Sequence is the right shape here; a flowchart is not.                              |
| D20 | Edit staging rules | `README.md` §V8                          | `flowchart`       | P1  | Encodes the refusal asymmetry — dragged clamps, typed refuses. A safety property.  |
| D21 | Build path         | `README.md` §Build                       | `flowchart`       | P2  | JDK 17 + Gradle 8.4 pin + `-Psimoscal.dir` + R8 + external keystore → APK.         |

**Out of scope.** Generating diagrams from live data (see KD1 and Deferred).
Any CI or pre-commit rendering check. Exporting diagrams to PNG/SVG committed as
images. Restructuring or splitting the host documents. Editing
`code_review.md` in either repo — those are append-only logs.

## Key flows

**Authoring one diagram.**

1. Draft the mermaid source against the host document's actual content.
2. Compile with `mmdc` — a diagram that does not compile does not proceed.
3. Add to the review Artifact.
4. After Sam's visual sign-off, insert into the host document, replacing any
   ASCII art rather than sitting beside it.
5. Add the ID-to-description legend beneath the diagram where table IDs appear
   (see KD4).

**Rollout order.** Vocabulary first (KD2), then D1 (the shared asset, which
constrains everything else), then P1 diagrams repo by repo — `simoscal` first
because it is public and has the clearest reader — then P2, then reassess P3.

## Acceptance examples

**AE1.** Running `mmdc` over every mermaid block in all three repos compiles all
21 without error, including every block whose labels contain bracketed table IDs
such as `IP_FAC_BPA_SP[0]`.

**AE2.** A reader opening `Code/README.md` on GitHub sees the system map and can
state, without scrolling further, that simoscal does not flash and that
SimosTools does.

**AE3.** A reader of `Code/README.md` §`build()` can answer "what happens if I
omit `reference_bin=`" from the diagram alone, without reading the surrounding
prose.

**AE4.** A tester on an unrecognised box code follows `BETA_GUIDE.md`'s decision
tree from "is my car supported" to the porting path in §6 without reading §3 and
§5 in full.

**AE5.** Opening `knowledge/ecu-tuning-basics.md` in Obsidian renders the
torque → boost chain correctly in both the light and dark vault themes, and no
box-drawing characters remain anywhere in the file.

**AE6.** A fresh Claude session given only `CLAUDE.md` can name which of the six
loop steps are Sam's and which are its own, citing the diagram.

**AE7.** Someone new to `simoscal-android` can state what V7, V8 and V9
delivered, and that V1 preceded V0, from the timeline alone.

## Key decisions

**KD1 — Hand-written, not generated.** Diagrams are authored into documents.
The alternative considered was having `simoscal` emit mermaid into every tune
`report.md` and `analysis_findings.md`, built from the edit journal, so it is
always true by construction. Rejected for now: it is a library feature requiring
code and tests, and it would not have fixed any of the three named failures,
which are all in prose documentation. Deferred rather than discarded.

**KD2 — A shared visual vocabulary, defined before any diagram is drawn.** One
`classDef` set reused across all 21 so shapes carry meaning: human step (Sam),
automated/Claude step, safety gate or refusal, external tool (SimosTools,
TunerPro, VW_Flash), and data file (bin, CSV, `.md`). Without this, 21 diagrams
read as 21 one-offs. Fills must be chosen with explicit strokes and legible
contrast in **both** light and dark, because Obsidian and GitHub both theme.

**KD3 — The system map is duplicated verbatim, not linked.** D1 appears in all
three READMEs as identical source. Cross-repo links are fragile — the repos have
separate remotes and one is public while the others are not — and a reader
arriving at any one of them needs the orientation immediately.

**KD4 — ID in the node, description in a legend beneath.** `CLAUDE.md` requires
every table reference to carry both the ID and its plain-English description.
Two-line node labels destroy diagram layout. The convention is the ID inside the
node and a small aligned legend table directly under the diagram, which honours
the rule without wrecking the graph.

**KD5 — Every node label carrying a table ID is quote-wrapped.** This project's
IDs contain brackets (`IP_FAC_BPA_SP[0]`, `IP_LAMB_BAS_HPDI[1]`). **Confirmed by
test, not assumed:** `A[IP_FAC_BPA_SP[0]]` fails to render and `mmdc` exits 1
with no SVG produced, while `A["IP_FAC_BPA_SP[0]"]` renders cleanly. Expected to
affect roughly half the set.

**KD6 — No LaTeX in node labels.** Obsidian renders LaTeX in note bodies but
**not** inside mermaid labels. Any maths in a diagram uses Unicode and plain
expressions; LaTeX stays in the surrounding prose.

**KD7 — Mermaid replaces ASCII art; the two never coexist.** Leaving the ASCII
in place guarantees the two drift apart.

**KD8 — Raw-text readability is a design constraint.** A fresh Claude session
reads `CLAUDE.md` as unrendered text. Mermaid source is still denser and less
ambiguous than ASCII art, but diagrams destined for `CLAUDE.md` should keep node
labels self-explanatory so the source reads sensibly unrendered.

## Deferred / out of scope for later

- **Generated diagrams in tool output** (KD1) — mermaid emitted into
  `report.md` and `analysis_findings.md` from the edit journal and findings set.
  The natural follow-on once the authored set proves the vocabulary.
- **D9, the knowledge map** — largely redundant with Obsidian's built-in graph
  view. Ship last, and drop it if it does not earn its place on GitHub.
- **A rendering check in CI** — a `mmdc` compile gate on every `.md` would keep
  the set from rotting, but no repo here runs CI on documentation today.
- **PNG/SVG export** for any surface that cannot render mermaid.

## Outstanding questions

**Blocking — must be answered before planning:**

- None. The vocabulary (KD2) is the first work item and resolves itself.

**Non-blocking — decide during the work:**

1. Does `Tunes/REV_LOG.md` want `gitGraph` or a plain flowchart for D7? Real git
   history and revision lineage are not the same thing here, and `gitGraph` may
   imply a branch structure that does not exist.
2. Should the tune-order overlay (D6) be a second diagram or numbered
   annotations on D5? One graph is more honest; two are easier to read.
3. Does `AGENTS.md` need the same treatment as `CLAUDE.md`, or does it point at
   it?
4. Should D1's SimosTools node link out to `knowledge/simostools-app-guide.md`
   in the gti-tune copy, making the three copies non-identical after all?
