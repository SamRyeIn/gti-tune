---
date: 2026-08-27
type: backtest
revision: R14
profile: SC8S50
---

# R14 back-test — comparison

Bundle: `bundle.json` · Reply: `reply.json` · Replay: `replay.md`

## The reconstruction

| | |
|---|---|
| Session bin | `CB_HSL_SP2933_5G0906259L_0002_BasicsGuide_R13.bin` |
| Logs in the bundle | `Logs/BasicsGuide_R11` — 4 CSV, 2 detected pulls |
| Journal | empty (the app's shape: one imported bin, no prior edits) |
| Sandbox audit | clean — no tool call named a path outside the sandbox |

> [!warning] Caveat carried from the case definition
> The bundled logs were recorded on the R11 bin while the session opens on R13.
> R12 (slot-5 valet cap) and R13 (no calibration change) sit between them — the
> same mismatch Sam worked under, since no logs were taken on R12 or R13.

## What R14 actually did

Reordered the switch-patch slots least→most aggressive and made slot 1 a stock
map by setting its `PUT setpoint` — Pressure up throttle setpoint, map slot 1
grid to the factory `IP_PUT_SP` — Pressure up throttle setpoint curve read live
from the stock bin. Only the four per-slot PUT setpoint grids moved.

## What Claude recommended

**Nothing.** `recommendations: []`, with a 7,066-character `summary`.

## Buckets

| Bucket | Count | Entries |
|---------|-------|---------|
| Agrees  | 0     | — |
| Refused | 0     | — |
| Novel   | 0     | — |
| Wrong   | 0     | — |
| **Total recommendations** | **0** | |

Replay counts: `{'queued': 0, 'dropped': 0, 'malformed': 0, 'total': 0}`. The
journal was unchanged at 0 entries, so `advice_review` honoured its contract.

## Reading the null result

An all-zero table is not the same as a failure, and it is not the same as a
success. Three separate things have to be said about it.

### 1. The actual change was not log-derived, so no answerer could have proposed it

R14 reordered slots and installed a stock map. That is an **ergonomics and
lineage decision** about how the five switchable maps are arranged — it is not a
response to anything the R11 logs said, and no amount of log evidence would
motivate it. R14 is therefore a weak back-test case: its **Agrees** bucket could
not have been non-empty even in principle. This is a property of the case, not
of the answering side.

### 2. The refusal was reasoned, and one inference in it was genuinely strong

The reply identified **which switch-patch slot was live** by taking the logged
PUT at the overshoot minus the logged setpoint error and matching the remainder
to eight significant figures against slot 3's breakpoints
(280.900 kPa = 2808.997 hPa = `0x7d59a` — PUT setpoint, map slot 3). No channel
in the bundle names the active slot; that had to be reconstructed. It then
declined to touch the boost curve because the single overshoot was +13.3 kPa
across 0.08 s — below the battery's own +20 kPa High line — with the wastegate
integral only at −1.2 %, i.e. a feedforward knee transient rather than a
controller out of authority.

### 3. It named the bundle's own gaps as the reason it could not size anything

Quoted from the reply: *"A check that did not run is not a check that passed."*
The two skipped checks are `boost_cal` and `boost_p0234` — see
[[Docs/backtest/README|the aggregate findings]] for why they skip and why that
matters more than any single case.

It also declined to credit the knock result at all: knock retard reads a flat
0.00° on every cylinder across every loaded WOT sample, and *"a dead PID and a
clean engine look identical in that column."* It refused to recommend added
boost or timing until the channel is verified live. That is the correct call and
it is the kind of judgment the guards cannot supply — no dry-run replay would
have caught a recommendation that was unsafe because a PID was dead.

## Verdict for the stage-2 gate

Contributes **no bucket evidence**. Contributes one qualitative data point: the
answering side refused for stated, checkable, correct reasons rather than
inventing a low-confidence change to fill the file — which §4 of
`advice-answering-guide.md` explicitly asks for.
