---
name: answer-bundle
description: Answer a "Tune with Claude" context bundle exported by the SimosTools Android app — read the session it describes and write a schema-valid recommendations file back. Use when given a bundle JSON path, or when asked to answer/review a bundle, write recommendations for a tune session, or produce a reply file for the app to import.
---

# Answering a context bundle

You have been given a **context bundle**: one JSON file describing somebody's
open tuning session. Produce one **recommendations file** they can import back
into the app.

You are the answering half of a courier. The person exported this file, is
asking you somewhere with no bin and no ECU in front of it, and will carry your
answer back to a tablet where every item is replayed through the library's real
edit guards before they see it, then accepted or rejected one at a time.

## Before anything else

Read `Code/docs/advice-answering-guide.md` in full. It is the method — how to
read a bundle, how to get from a log finding to a sized change, and which rules
cost a record if broken. Read `Code/docs/advice-schema.md` for the exact field
shapes. Do not write a recommendation before you have read both.

Then read `CLAUDE.md` at the repo root if you have not already: the table-naming
rule (`` `ID` — Description ``, always both) and the log-reading rules (gear
indexing by header, trimming before quoting Calc HP/TQ) are enforced here.

**Never open the bundle with Read.** It is hundreds of tables of decoded values
and will fill your context with cells nobody asked about. Use the reader:

```
Code/.venv/bin/python .claude/skills/answer-bundle/read_bundle.py <cmd> <bundle.json>
```

| Command | What it gives you |
|---------|-------------------|
| `sections` | What is in the bundle, how much of it, and the provenance to echo |
| `notes` | What the person actually asked — read this first |
| `brief` | The safety brief, both halves, verbatim |
| `logs [--evidence]` | Pulls, findings by severity, and the SKIPPED list |
| `journal` | What this session already changed, in order, with intents |
| `tables [--grep P] [--space S] [--owner-only]` | An index — names, IDs, shapes, owners. No values |
| `table <name> [--space S]` | One table in full: axes, values, and `source_values` if edited |
| `validate <reply> --bundle <bundle>` | Runs the **real** schema over your reply |

Use `Code/.venv/bin/python` by absolute path or from the repo root — bare
`python` is the wrong interpreter here.

## The loop

1. **`notes`** — what was asked. If it names a symptom, that is your question.
   If there are no notes, the question is "what do these logs justify changing?"
2. **`sections`** — profile, spaces, how many logs, and the three provenance
   fields you will echo character for character.
3. **`brief`** — read it before forming any opinion. It names this car's traps,
   and a recommendation against a table it warns about is wasted.
4. **`logs`** — findings in severity order, then the pulls behind each one, then
   the **SKIPPED list**. A check that did not run is not a check that passed.
5. **`journal`** — what has already been tried, and why. A finding whose cause
   is a change three revisions back is best answered by walking that change
   back, not by a fresh reshape.
6. **`tables --grep`** — find the table that owns the behaviour. Then `table` it
   in full and read its axes before you name a cell.
7. **Write the reply** to `reply.json` next to the bundle (or where you were
   told). One recommendation per coherent change.
8. **`validate reply.json --bundle bundle.json`** — fix everything it names and
   run it again. It reports every problem at once; do not fix them one per pass.
9. **Report** to the person: what you recommended, what you deliberately did
   not, and what the next drive should capture.

## What a good answer looks like

- **Every record cites something in this bundle** — a pull index, a row range,
  an rpm band, a channel and its values, a journal entry. Evidence is a schema
  requirement: a record without it is rejected before anyone reads it.
- **Every record predicts something the next log can settle.** A channel, a
  condition, a number. "Should feel better" is not gradeable.
- **Values in physical units**, the ones the table reports. Never raw bytes.
- **Both halves of the name**, always: the logical `name` the replay resolves
  through, plus the `id` and `description` from that same table entry.
- **Sized, not guessed.** Say where the number came from. Walking back a prior
  edit is the best-bounded move available, because its destination is a value
  this car has already run and logged.
- **Owner-locked tables take `set`/`fill`/`paste` only** — an operation stating
  the values the table should end at. Arithmetic on one is dropped.
- **Nothing the brief names as not-recommendable.** Put it in `summary` instead.

## When the answer is "nothing"

An empty `recommendations` list is a valid, useful answer, and a much better one
than a low-confidence change invented to fill the file. Put the reasoning in
`summary`: what you would have changed if a guard did not forbid it, which
skipped check you needed, and what the next drive should log to make a real
recommendation possible. `summary` always reaches the reviewer.

## Hard limits

- **You never flash anything, and you never edit a bin.** This skill writes one
  JSON file. The person flashes, with the app, after reviewing each item.
- **You cannot see the calibration's bytes** — only the decoded values in the
  bundle. If a fact you want is not in the bundle, you do not have it.
- **Do not modify the bundle.** It is the record of what was asked.
- **Do not invent a table.** Every `table.name` must exist in the bundle's
  `tables` section, with the `id` and `description` that entry carries.
