# Code review brief — supporting other file structures (U1–U8)

A self-contained assignment for a reviewer with no prior context on this project.
Everything needed to do the review is in this file; you are not expected to have
seen this repository, its conventions, or its history before.

## 1. The assignment

Review the library changes that made a second car's ECU calibration file a
first-class, writable profile.

| Field         | Value                                                          |
|---------------|----------------------------------------------------------------|
| Repository    | `/Users/sam/SimosTools/Code` (the `simoscal` Python library)    |
| Branch        | `feat/file-structure-support`                                   |
| Diff range    | `c561f47~1..829025f`                                            |
| Size          | 61 files, 5804 insertions, 580 deletions                        |
| Library only  | 29 files, 2485 insertions, 446 deletions under `simoscal/`      |

Note that `Code/` is its own git repository, nested inside but independent of the
repository at `/Users/sam/SimosTools`. Run git commands against `Code/` directly.

```
git -C /Users/sam/SimosTools/Code log --oneline c561f47~1..829025f
git -C /Users/sam/SimosTools/Code diff c561f47~1..829025f -- 'simoscal/*'
```

The commit range is the whole effort: a behaviour-pinning commit, then eight
implementation units U1–U8.

## 2. What this software does, and why a mistake is expensive

`simoscal` parses a TunerPro-format XDF definition file, edits tables inside a
Simos18 ECU calibration binary in physical units, and writes back a minimal-diff,
checksum-verified binary. A human then flashes that binary to a real car's engine
control unit with a separate Android app. The library itself never flashes.

The consequences of a wrong byte are not abstract:

- A corrupted or wrongly-checksummed image can **brick the ECU**.
- A wrong calibration value can **damage the engine** — overboost, lean lambda,
  or uncontrolled knock.

The governing rule for the whole codebase is **fail loud**. The library must
never silently alter, clamp, round, or approximate a value, and must never let an
undeclared byte change reach a saved file. A guard that quietly does nothing is a
worse defect here than a guard that crashes.

> Treat "this code silently proceeds where it should raise" as a High-severity
> finding class, not a style nit.

## 3. What the change actually did

Before this effort the library was single-car by accumulation rather than by
design: facts about one specific car were scattered through module-level globals.

The effort did two things at once:

1. **Moved every per-car fact out of module globals** and onto a `Profile` /
   `StructureSpec` value object that is passed explicitly. Per-car facts include
   the calibration block layout, the location of the `ECM3` header, checksum
   constants, safety facts, and per-car table shapes.
2. **Added a second car** — `SCGA05`, box code `3CN906259B` — as a writable
   profile, and re-expressed the original car `SC8S50`, box code
   `5G0906259L_0002`, through that same new mechanism.

Facts established during the work that you can rely on:

- The `ECM3` header sits at calibration-relative `0x400` on **both** cars. The
  calibration block moved between cars; the header's relative position did not.
- The two `SCGA05` definition files use **different addressing conventions**. Its
  base XDF is calibration-relative; its patch XDF declares `BASEOFFSET 0x220000`
  and is full-bin addressed. Both must open over one buffer at effective base
  `0x220000`.
- Ten table names present for `SC8S50` are genuinely absent from the `SCGA05`
  definition. They are declared in `SCGA05.unavailable` with a reason.

## 4. Where to look

The riskiest surfaces, roughly in order:

| File                                        | What changed                                     | Why it is risky                                                        |
|---------------------------------------------|--------------------------------------------------|------------------------------------------------------------------------|
| `simoscal/checksum.py`                      | +386 lines — checksums became per-car             | A wrong checksum is an unflashable or bricking image                    |
| `simoscal/tune/profiles/scga05.py`          | +573 lines — the entire new car profile           | Every address and shape here is unvalidated against a real car          |
| `simoscal/tune/profiles/switchpatch_2933.py`| +438 lines — patch table resolution               | Address resolution across two files with different conventions          |
| `simoscal/tune/profile.py`                  | +323 lines — the `Profile` abstraction itself     | The mechanism every per-car fact now flows through                      |
| `simoscal/preflight.py`                     | +292 lines — profile resolution and compatibility | Picks which profile a given binary gets edited as                       |
| `simoscal/calfile.py`                       | +159 lines — calibration layout became data       | Base-offset errors move every subsequent write                          |
| `simoscal/tune/profiles/sc8s50.py`          | Rewritten onto the new mechanism                  | **This is the validated car.** Any behaviour change here is serious     |
| `simoscal/tune/audit.py`                    | Base-offset fix (U7)                              | The byte-level audit is the last gate before a human flashes            |
| `simoscal/safety.py`                        | Per-car safety facts                              | Where the guards live                                                   |

## 5. Invariants that must hold

These are the specific things worth proving rather than assuming. Each is a
genuine hazard in this domain, not a hypothetical.

**The table shape check must not be bypassable.** Declaring a table's shape
per-car was necessary, because `IP_IGA_BAS_IVVT_VVL_PORT_L` — Basic ignition
angle by VVT/VVL, port injection — is (16, 18) on `SCGA05` and (16, 16) on
`SC8S50`. Mutation testing during the work established that the shape check is
the *only* barrier protecting these nine ignition grids. So the central question
is: **can a per-car shape declaration now be used to write a wrongly-shaped table
that would previously have been refused?** A wrong shape on an ignition grid
misaligns timing against load and rpm, which is an engine-damage path.

**`C_M_AIR_CYL_SP_MAX` — Maximum allowed airmass setpoint — stores kg/stk, not
mg/stk.** The XDF labels it mg/stk with an identity scale, and that label is
wrong. A 2000 mg/stk ceiling is written as `0.002`. Writing `2000` does not raise
the limit — it removes the limiter by a factor of roughly 1.44 million. This is
the one table in the codebase where the physical value is not what gets written.
Check that this survived the refactor and is still enforced per-car.

**`C_PRS_IM_SP_MAX` and `C_PRS_IM_SP_LIM` — Maximum / limit requested
intake-manifold pressure setpoint — are float32, and their XDF-declared maximum
is not a real ECU ceiling.** The stock calibration already exceeds the declared
maximum by more than 20x. Any code that treats an XDF-declared max as a safety
guard on these two tables is wrong. Overboost fault routing lives in a different
table entirely: `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference
threshold, an int16.

**Checksum correctness on the foreign profile.** Both `CAL_CRC` and `ECM3` must be
corrected on save and then verified *independently* by reading them back off the
written file. A checksum routine that computes over the wrong range, or that
verifies using the same code path that wrote it, is a finding.

**No per-car fact may still be read from a module global.** The point of the
refactor was to eliminate these. A leftover global means car B silently gets car
A's value. Grep for surviving module-level constants that encode addresses,
offsets, shapes, or limits.

**An absent or unmapped table must never silently resolve to an address.** Ten
names are legitimately absent on `SCGA05`. Confirm that asking for one raises
rather than returning a default, a zero, or a neighbouring table's address.

## 6. Priority — which findings matter most

Rank findings by which car they affect:

1. **Anything that changes `SC8S50` behaviour is the top priority.** That is a
   real car with sixteen validated tune revisions behind it. The stated
   acceptance criterion for this effort was that the existing test bodies were
   not edited to accommodate the refactor — so a behaviour change there is both a
   regression and a broken promise. Verify that claim rather than trusting it.
2. **`SCGA05` findings are real but cannot hurt anyone today.** That profile is
   bench-verified only; no such car has ever been driven on a binary this library
   produced. Report them, but they do not block.

## 7. Already verified — do not re-report as findings

Independent verification already exists for the following. Re-deriving them is
wasted effort; *contradicting* them with evidence is very much a finding.

- **The test suite passes.** 966 tests at the branch tip `829025f`. A later
  branch stacked on top of this work runs 1164, also passing. Four warnings in
  both runs are intentional `StaleChecksumWarning` assertions in the AE3 tests,
  not failures.
- **A `SCGA05` edit survives the full build gate chain**, not merely
  `CalFile.save`. Covered by `test_ae4_an_a05_edit_passes_every_build_gate`,
  which runs save-with-checksums, independent checksum verification off the
  written file, read-back of every journaled table, and a byte-level audit
  against the stock binary with an allowance derived from the edit journal.
- **That pass is meaningful, not vacuous.** It is paired with
  `test_ae4_an_undeclared_change_still_fails_the_audit`, which requires an
  unaccounted byte to surface as `unexplained` and as a build failure.
- **A wrongly declared shape still fails.** Covered by
  `test_f6_declaring_the_wrong_shape_...`.
- **The structural assertions were rewritten, not deleted.** Twelve structural
  assertions are listed by name in
  `test_ae6_the_structural_claims_were_rewritten_not_deleted`, so silently
  dropping one to make the suite green fails.
- **The foreign suite fails loudly when its fixtures vanish.** Setting
  `SIMOSCAL_REQUIRE_FOREIGN=1` converts an absent fixture into a failure rather
  than a skip.

Acceptance criteria in this repository are numbered **per effort, not globally**.
`AE4` in `tests/test_acceptance_foreign.py` means this effort's AE4 and nothing
else; other `test_acceptance_*.py` files scope their own AE1–AEn. Grepping `ae8`
across the suite finds the wrong test.

## 8. Accepted risks — explicitly not findings

These were considered and deliberately accepted. Raising them again as findings
is noise.

- **A bench-verified binary is indistinguishable from a validated one.** An
  `SCGA05` build passes the same byte-level gates and presents identically to an
  `SC8S50` build. Nothing in the library marks a calibration that nobody has ever
  driven. This was a deliberate call, recorded in the plan.
- **Domain guidance was deliberately not ported.** Domain *machinery* works for
  the new car; domain *guidance* — what a sensible value is for this engine —
  does not, and was scoped out.
- **No validated-tune claim is made for `SCGA05`**, and none should be inferred
  from the code.

## 9. Out of scope

- Anything under `simoscal/analysis/` beyond the four lines this range touches.
- The Android client, which lives in a separate repository.
- Whether `SCGA05` should mirror a separate in-progress effort's 93 additional
  table specifications. That is an open question by design, not an omission.
- Calibration judgment — whether a given timing or boost number is wise. Review
  the machinery, not the tune.

## 10. How to report

Findings are appended to `Code/code_review.md`, which is a living log. Match its
existing conventions:

- Append one new section `## Review YYYY-MM-DD — <scope>` at the end of the file,
  newest last. Do not edit earlier reviews.
- Give every finding an ID of the form `CR-YYYYMMDD-NN` and add a row to the
  findings index table near the top of the file.
- **Severity:** `High` = weakens a safety guarantee, or breaks a user on first
  contact. `Medium` = wrong on realistic future inputs, or a latent hazard.
  `Low` = cleanup, documentation, efficiency.
- **Verdict:** `CONFIRMED` = reproduced or proven against the code as written.
  `PLAUSIBLE` = mechanism verified, but triggering it needs a
  realistic-but-not-current state.
- **Status:** starts `Open`, then moves to `Fixed (YYYY-MM-DD)`,
  `Dismissed (reason)`, or `Superseded (by CR-...)`.

For each finding give a concrete failure scenario — specific inputs or state
leading to a specific wrong output — not a general worry. A finding that cannot
be stated as "given X, this produces Y, which is wrong because Z" is probably not
ready to report.

When naming any ECU table, calibration, or parameter anywhere in your write-up,
**always give both the identifier and its plain-English description**, in the form
`` `ID` — Description ``. If you genuinely do not know what an identifier means,
say so explicitly rather than dropping the description.
