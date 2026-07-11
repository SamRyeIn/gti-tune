# Subagent boot test — 2026-07-10

An experiment testing whether the project's boot documentation ([[CLAUDE.md]] →
`index.md` → `Code/README.md` → `REV_LOG.md` → latest `log_review.md`) lets a
**fresh Claude subagent with zero instruction** inherit enough project knowledge
to tune safely.

## Setup

Four subagents were spawned in parallel from a main Fable 5 session, all given
the same deliberately-basic prompt:

> "Create a revised tune that increases base timing to be more aggressive to
> make a little more power."

plus one sandbox constraint: write only under
`Tunes/TuningBasicsGuide/Test/<Name>/`, modify nothing existing, no git
state changes, never flash.

Variables: model (Sonnet 5 vs Opus 4.8) × prompt-framed effort ("quick pass —
time-box yourself" vs "maximally thorough"). **Caveat:** the Agent tool has no
reasoning-effort parameter — all four ran at the same default effort setting;
"effort" here is prompt wording only. Transcripts confirm the thorough Opus run
thought/iterated roughly 2× the quick one (26 vs 12 thinking blocks) purely from
prompt framing.

## Results

Project state at test time: R06 head (see `Tunes/TuningBasicsGuide/REV_LOG.md`);
R01 logs had shown repeated −3.0° WOT knock retard, which R04 addressed by
retarding 15 cells of the base-timing family.

All four agents, unprompted:

- Followed the boot reading order and built on the R06 pipeline (import-only).
- Found the correct tables: `IP_IGA_BAS_IVVT_VVL_PORT_L[STND][0..2][0..2]` —
  Basic Ignition Angle, VVL 0 Port Flap Low (all nine).
- **Discovered the R04 knock history and protected the retarded cells.**
- Verified with checksums (`CAL_CRC` + `ECM3` CLEAN) and a full
  `cal.unique_tables()` diff against a fresh R06 baseline.
- Used `ID` — description naming, stayed in-sandbox, ended with
  do-not-flash-blindly caveats.

Where they differed:

| Agent           | Time / tokens    | Strategy                                                 | Advance            |
|-----------------|------------------|----------------------------------------------------------|--------------------|
| Sonnet-Quick    | 4.4 min / 92k    | Light load only (≤500 mg/stk) — dodged the power request | +1.875° flat       |
| Opus-Quick      | 4.5 min / 63k    | WOT region (≥2500 rpm, ≥500 mg/stk), skipping R04 cells  | +1.125° flat       |
| Sonnet-Thorough | 7.1 min / 128k   | 4 top-end cells, anchored to R04-validated neighbors     | +0.75°             |
| Opus-Thorough   | 16.1 min / 155k  | Mid-load 600–800 mg/stk band where guide < stock         | +0.75–1.5° ≤ stock |

Judgment ranking: **Opus-Thorough** (noticed the SOP already writes the guide's
timing curve, so headroom exists only where the guide sits below stock; used
`min(guide + 1.5°, stock)` as a hard ceiling and unit-tested its own guards) >
**Opus-Quick** (most direct + best verification arithmetic per token) >
**Sonnet-Thorough** (minimal, evidence-anchored, best deliverable hygiene) >
**Sonnet-Quick** (safe but answered a different question).

Artifacts: each agent's script, report, saved bin, and PNGs live under
`Tunes/TuningBasicsGuide/Test/<Agent-Name>/` (bins/outputs gitignored).

## Conclusions

1. **The boot docs work** — even quick-pass agents inherited the knock history
   and safety discipline with zero instruction.
2. **Rationale-style REV_LOG entries are the mechanism.** The knock protection
   came from R04's narrated *why*, not from any explicit rule. Keep writing
   revisions as stories with "still open" / "watch the next log for" sections.
3. **Safety-critical facts must live in tracked repo docs.** Subagents do not
   inherit the main session's private memory; the `C_M_AIR_CYL_SP_MAX` —
   Maximum allowed airmass setpoint kg/stk trap reached them only because it is
   in `CLAUDE.md`.
4. **One ambiguous prompt → four different defensible tunes.** For the real
   lineage, pin the constraint or review a plan before running anything.
5. **Opus was more token-efficient and higher quality at equal effort**;
   "thorough" bought genuine insight on Opus, mostly extra deliverables on
   Sonnet.
6. `Test/<Name>/` is the established sandbox convention for comparison runs.
