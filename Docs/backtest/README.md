---
date: 2026-08-27
type: backtest
status: all four cases answered and replayed
plan: "[[2026-08-24-001-feat-tune-with-claude-courier-plan]]"
scope: SC8S50 only
---

# The courier back-test — aggregate findings

The evidence U8 was built to produce, and the gate the brainstorm set for
stage 2 of [[2026-08-24-001-feat-tune-with-claude-courier-plan|Tune with
Claude]]. For a revision that already happened, `backtest.py` reconstructs the
session as it stood *before* it, exports a context bundle exactly as the app
would, and lets a model that has never seen the repository answer it. The reply
is replayed through the library's real guards and each recommendation is sorted
into one of four buckets against what the revision actually did.

**The answer is produced blind, and that is enforced rather than promised.**
`answer` copies the bundle, the answering guide, the schema reference and the
bundle reader into a throwaway directory outside this repository and runs a
fresh `claude -p` there — no repo, no `CLAUDE.md`, no auto-memory, no lineage.
Every run's full tool transcript is kept, and `replay` audits it. All audits so
far report **no tool call named a path outside the sandbox**.

## Bucket counts

| Revision | Recommendations | Agrees | Refused | Novel | Wrong | Case quality |
|----------|-----------------|--------|---------|-------|-------|--------------|
| R10      | 1               | 0      | 0       | **1** | 0     | **strong** — torque-limiter driven, and the battery has that check |
| R14      | 0               | 0      | 0       | 0     | 0     | weak — the actual change was not log-derived |
| R15      | 0               | 0      | 0       | 0     | 0     | **strong** — a log-driven change with its own logs in the bundle |
| R16      | 3               | 0      | 0       | **3** | 0     | fair — the actual change was later superseded unflashed |
| **Total**| **4**           | **0**  | **0**   | **4** | **0** | |

Of the four recommendations, **all four passed the guards** — nothing was
dropped, nothing was malformed, and no journal entry was ever written by a
review. Every record carried a gradeable prediction (G6).

> [!important] The **Agrees** bucket is empty, and the **Wrong** bucket is too
> Zero Agrees is not four disagreements. R14's actual change was not log-derived
> at all, so no answerer could have reached it; R15 returned nothing because its
> motivating evidence is filtered out of the bundle (below); R16's actual change
> was later judged wrong by Sam and removed in R17. Only R10 is a genuine
> head-to-head, and there the two reached the **same constraint and opposite
> conclusions** for a reason the bundle does not carry.
>
> Zero Wrong is real but thin: four records is a small sample, and the plan is
> right that an enumerated Wrong bucket is what gates stage 2. **The gate is not
> met and not failed.** It is under-powered, and the reason it is under-powered
> is fixable.

## The single most important case: R10

Sam and the answering side both identified `IP_PQ_CHA_MAX` — Maximum allowed
pressure quotient at turbo charger compressor as the binding constraint, both
read it correctly (a flat 2.80, against a logged 2.893), and then went opposite
ways: Sam **raised the ceiling** to 3.1 to clear a code-128 torque-limiter cap;
Claude **lowered the request** to 2715 hPa to come back inside the declared
ceiling.

The answering side even found the limiter independently — *"the torque-limiter
finding shows source code 128 active for 385 samples with timing at −10.9 deg"* —
and declined to act on it, on the grounds that the boost target was not the
binding quantity. Detection was not the gap. The gap is the step from *"a limiter
is capping this"* to *"and here is the table that raises the limiter."*

> [!important] The bundle carries no statement of the tuner's goal
> Absent one, the answering side defaults to bringing the car back inside its own
> declared limits — here, the inverse of the lineage's purpose. Partly a rig
> artifact: `backtest.py` uses a deliberately neutral prompt, because a
> per-revision prompt would be *"a prompt written knowing the answer."* In the
> real app the person writes their own note. What R10 proves is that the goal is
> **load-bearing**, not that the answering side is wrong.

Full detail in [[Docs/backtest/R10/comparison|R10/comparison.md]].

## Why R14 and R15 returned nothing

Not model reticence — R10 and R16 both produced sized, guard-passing edits from
the same rig, so the capability is not in question. Each empty reply is instead a
7,000-character `summary` of correct, checkable reasoning that stops one step
short of an edit, and the step it stops at is the same one each time. Three
symptoms, one root cause.

```mermaid
flowchart TD
    ROOT["advice.bundle.logs_section(...)<br/>calls run_battery with cal=None"]
    ROOT --> S1["boost_cal and boost_p0234<br/>land in SKIPPED"]
    ROOT --> S2["compute_coverage would skip<br/>every table under needs_cal"]
    S2 --> S3["coverage is never computed<br/>and never merged via extra="]
    S1 --> R1["'a check that did not run<br/>is not a check that passed'<br/>-- will not grade the boost curve"]
    S3 --> R2["cannot show which cells<br/>the car actually visited<br/>-- will not size a cell edit"]
    SEP["analysis boost check is<br/>overshoot-only"] --> R3["a boost shortfall is<br/>never a finding at all"]
    R1 --> OUT["recommendations: 0"]
    R2 --> OUT
    R3 --> OUT
```

### 1. `cal=None` disables both the cal-aware checks and coverage

`simoscal/advice/bundle.py`'s `logs_section` calls the battery with `cal=None`.
The docstring gives a real reason — the cal-aware checks want the bin the logs
were *recorded on*, and a mid-edit session's working buffer has not been flashed
— and `advice-answering-guide.md` repeats it, telling the answerer that
`cal_resolved` is normally false and to say so in `summary` rather than guess.
Which is exactly what all three answers did.

But the reasoning does not hold for the case the courier is built for. The
bundle's own prompt is *"I flashed this calibration and drove it; these are the
logs from that session"* — in that case the session bin **is** the flashed bin.
The honest fix is to let the session say so, not to hard-code the pessimistic
answer.

`_op_advice_bundle` in `bridge.py` calls the same `logs_section`, so this is the
on-device behaviour too, not a property of the rig.

### 2. The guide promises a `coverage` section the bundle cannot produce

`advice-answering-guide.md` lists `coverage` in its table of what `logs` holds
(*"which table cells the logged operating points actually visited"*) and then
instructs the answerer to use it: *"Use `coverage` to check the cells you want
to move were actually visited."*

The bundle has no `coverage` key. `json.dumps(bundle).count("coverage")` is
**0** for all three exported bundles. `logs_section` never calls
`compute_coverage`, and never passes `extra=` to `findings_to_dict` — the
parameter that exists precisely to merge that section in. And even if it did,
`compute_coverage` skips every table when `ctx.cal is None`, per symptom 1.

This is what the R15 answer ran into head-on. It named `IP_FAC_BPA_SP[1]` —
Map for boost pressure actuator setpoint, VVL 1 — the exact table Sam edited —
and then refused, because *"its axes are exhaust flow factor × intake flow
factor and neither channel appears anywhere in this bundle, so I cannot show
which cells were visited or size a trim from evidence rather than from feel."*
The guide told it to check coverage. There was none to check.

### 3. The analysis battery has no boost-shortfall check

Separate root cause, and the one that fully explains R15. `simoscal.analysis`'s
`boost` check reports **overshoot only** — `_overshoot_zones` finds contiguous
regions where PUT exceeds setpoint. There is no undershoot, shortfall or deficit
check anywhere in the battery.

R15 exists to close a measured 4000–4500 rpm boost **shortfall**. That shortfall
is therefore not a finding in the bundle, in any form. Its raw signature is
present but unreported: the `wastegate` check's evidence carries
`max_wg_final_pct: 99.9985` — the gate driven fully closed — and that check's
own docstring already knows what that means (*"WG hit 100% only while under
setpoint during spool"*). The number reaches the bundle; the finding does not.

## The reproducibility result

Three of the four sessions converged on the same lambda edit, independently and
blind:

| Session | Table and cells | Values | Outcome |
|---------|-----------------|--------|---------|
| R10 | `IP_LAMB_BAS[1]` @ 3008 rpm, rows 1100/1200/1389 mg/stk | 0.975 / 0.955 / 0.925 | written out in `summary`, then **declined** |
| R14 | same signature (+0.049 lean at 3081 rpm) | — | **declined** |
| R16 | `IP_LAMB_BAS[1]` @ 3008 rpm, rows 900/1100/1200/1389 | 0.97 / 0.95 / 0.93 / 0.90 | **recommended**, queued |

Same table, same column, near-identical values, from three sessions that could
not see each other. The *analysis* is highly reproducible; the *risk threshold*
is not — R10 and R14 refused on the grounds that a measured-versus-commanded
lean error at 98 % HPFP may be delivery rather than setpoint, which is the
guide's own "symptom's table rather than the cause's" anti-pattern; R16 checked
pump headroom, judged it sufficient, and acted.

That variance is more useful than the bucket counts. It says the answering side
agrees on *what the logs mean* and disagrees on *when evidence is sufficient to
spend a flash* — which is a threshold the guide could state explicitly and
currently does not.

## What the answers got right

Worth recording, because it is the part that no guard supplies and the part
stage 2 would be buying:

- **Reconstructed the live switch-patch slot from first principles.** No channel
  in the bundle names the active slot. Both R14 and R15 recovered it by taking
  logged PUT minus logged setpoint error and matching the remainder to eight
  significant figures against a specific slot's breakpoints (slot 3 and slot 4
  respectively).
- **Refused to trust a dead PID.** R14: knock retard reads a flat 0.00° on every
  cylinder across every loaded WOT sample, and *"a dead PID and a clean engine
  look identical in that column."* It declined to recommend added boost or
  timing until the channel is verified live. A dry-run replay would not have
  caught that — the guards bound values, not premises.
- **Cross-domain sizing.** R15 computed that richening `IP_LAMB_BAS[1]` — Basic
  lambda setpoint grid from 0.800 to 0.75 needs ≈7 % more fuel, i.e. ≈104 % of
  what the pump actually delivered at 97.7 % HPFP effective volume — and used
  that to argue against adding boost at all: *"there is no fuel behind it."*
- **Declined to move a limit that does not bind.** Both replies found the lambda
  floors sitting leaner than the brief's stock figures, flagged that they must
  come down in the same revision that ever richens the setpoint grid or the
  enrichment gets clipped, and refused to move them alone.
- **Honoured the brief's traps.** Neither touched `C_M_AIR_CYL_SP_MAX` —
  Maximum allowed airmass setpoint. R15 explicitly noted it quoted no Calc HP or
  Calc TQ figure, so the in-gear trimming rule did not bear on any of its claims.

## Recommended next actions

In the order that would most change the bucket counts:

1. **Add a boost-shortfall check to the battery.** Until one exists the courier
   cannot reproduce a change of R15's kind however good the answering side is.
   The signal is already computed inside the `wastegate` check.
2. **Let a session declare that its bin is the one that was driven**, and pass
   the calibration to `logs_section` when it does. That un-skips `boost_cal` and
   `boost_p0234` and makes coverage computable, in one change.
3. **Wire coverage into the bundle** via `findings_to_dict(..., extra=...)`, or
   remove its row and its instruction from the answering guide. Promising a
   section that cannot be produced is worse than not having it.
4. **Re-run all four cases** once 1–3 land. Only then are the bucket counts
   evidence about the answering side rather than about the bundle.
5. **Carry the active switch-patch slot in the bundle.** Three independent
   sessions reconstructed it numerically — matching peak PUT minus logged
   overshoot to eight significant figures — before they could say anything about
   boost. R10 went further and proved the session had *mixed* slots, splitting
   its pulls into two incomparable groups; the battery never reported that.
6. **Say in the bundle which of the identical variant grids is live**, or say
   that the convention is to move all of them together. Two cases stalled on it:
   R10 refused a lambda edit because *"an edit to one is a one-in-three chance of
   editing the grid that is actually in force"*, and R16 left timing alone
   because it *"cannot tell from the bundle which of the nine cam-position
   ignition tables was active."* The lineage's own answer in both cases is
   *move them all* — which R16's actual revision did across all nine maps.
7. **Carry the tuner's goal.** R10 is the whole argument: a sound analysis
   produced advice pointing away from the lineage's intent because nothing said
   the intent was more power on upgraded hardware. In the app this is the
   person's own note, so the fix may be prompting for it rather than adding a
   field — but the answering guide should say that an absent goal means
   *bring the car inside its declared limits*, so a reader knows what default
   they are getting.
8. **State a sufficiency threshold in the answering guide.** R10, R14 and R16
   reached the same lambda cells and split on whether one lean sample at 98 %
   HPFP justifies acting. The guide blesses the empty answer and warns against
   low-confidence changes, but never says where the line is.

## Reproducing

```
Code/.venv/bin/python Docs/backtest/backtest.py list
Code/.venv/bin/python Docs/backtest/backtest.py export R15
Code/.venv/bin/python Docs/backtest/backtest.py answer R15
Code/.venv/bin/python Docs/backtest/backtest.py replay R15
```

Per-case detail is in `R<NN>/comparison.md`, which is what this repo tracks.

The artifacts themselves — `bundle.json`, `reply.json`, `replay.{json,md}`,
`state.json` and `answer_transcript.jsonl` — are **gitignored**. This remote is
public and a bundle is the entire decoded calibration in the clear, so the
evidence stays local and is regenerated by the four commands above rather than
published. `answer` costs an API call per case; `export` and `replay` are free
and deterministic.
