# MainTune R18 log review

**Sessions:** 2026-08-27 16:24–16:41 (hot air, 10 CSVs) and
2026-08-28 12:07–12:19 (cool air, 8 CSVs, dropped in as "R18 drive 2")
**Review:** 2026-08-28 (supersedes the 2026-08-27 single-session review)
**Calibration named by every CSV:** `Patched_259L_R18.bin`
**Authoritative candidate used for calibration-aware checks:**
`Tunes/MainTune/MainTune_out/R18_20260826-171645/Patched_259L_R18.bin`
(SHA-256 `b3bf96a4…5cb9bfd`, matching the `Tunes/REV_LOG.md` § R18 record)

**Verdict: R18 is validated. Keep it, and do not follow it with a knock-protection
revision.** The cool-air session is the controlled repeat the previous review
asked for, and it settles all three open questions at once:

1. **The pocket correction works and is nearly free.** Pooling both R18 sessions,
   the 4500–5000 rpm knock rate fell from 0.50 events per band-covering segment
   under R17 to 0.10 — 2 events where R17's rate predicts 10.5 — and in matched
   air R18 makes the same power as R17 (251 vs 252 F=ma wheel hp).
2. **The hot session's two knock events above 5500 rpm were heat.** In cool air,
   across eight full pulls to redline plus three 4th-gear stretches in the same
   byte-identical timing, there were **zero** loaded knock events above 5000 rpm.
3. **Sensor-saturation ghost knock is now ruled out by direct measurement, not
   inference.** The knock threshold `knks_thd` peaks at 2.68–3.46 V against a
   4.004 V ECU clamp, and the noise level never exceeds 1.53 V against a ~2 V
   saturation onset. Zero samples in the session come near either limit, so the
   knock this car reports is the sensor working, not a sensor that has stopped
   adapting. **Leave `IP_KNKS_GAIN_PRE[0..3]` — Gain value for each cylinder for
   the knock pre-window at stock.**

One settled single-cylinder −3.0° event remains in the pocket at 4827 rpm in cool
air, so the region sits at its margin rather than beyond it. That is a reason to
stop moving timing there, not a reason to pull more.

---

## Provenance and data quality

Both sessions' CSVs use `Gear (gear)`, so the logged gear is the actual gear and
no offset was applied; every file's metadata names `Patched_259L_R18.bin`. As in
R17, the folder carries no human-dropped flashed-bin text record, so the CSVs
prove the filename but cannot independently prove the flashed file's SHA-256.

The deterministic battery over the whole folder parsed **18 files / 17 pulls**
with the calibration resolved and **no checks skipped**, and found no gaps or
stuck channels. Re-run it with:

```
Code/.venv/bin/python -m simoscal.analysis Logs/BasicsGuide_R18 \
  --bin Tunes/MainTune/MainTune_out/R18_20260826-171645/Patched_259L_R18.bin \
  --xdf Code/xdf/SC8S50.V1.0.xdf
```

Both the `--bin` and the `--xdf` are required; without them the two boost checks
and all five coverage maps skip, which is what happened on the first pass of the
previous review.

The cool session was also run through the battery on its own, saved beside the
combined run as `analysis_findings_drive2.{json,md}` with its evidence plots in
`plots/drive2_battery/`, so its numbers stay reproducible now that the folder
holds two sessions. Cross-session work is in `analyze_r18_drive2.py`
(`../../Code/.venv/bin/python analyze_r18_drive2.py`), which imports the shared
helpers from `analyze_r18_validation.py`.

### This review covers 3rd **and** 4th gear WOT

Several logs hold a full 3rd-gear sweep and then a stretch of 4th at wide-open
throttle. Both are the same operating condition once binned by rpm — across all
R18 pulls, 3rd and 4th agree on mean airmass within ~30 mg/stk and on mean PUT
error within ~2 kPa in every band from 4500 rpm up — so both are included, in all
three sessions equally. 4th gear contributes almost entirely above 4400 rpm,
which is where the interesting bands are, and it raises loaded-WOT sample counts
by roughly a fifth. Three mechanics make that safe:

- **The shift is trimmed out of every gear-attributed segment.** The DSG's gear
  channel flips to the next ratio several samples before the shift actually
  pulls the engine down. In `16_37_04` the channel goes 3 → 4 at row 331 while
  rpm keeps climbing to 6255 through row 336, and `Calc HP` steps 297 → 353 hp at
  exactly that flip — the ~50 hp artefact the project convention warns about.
  Each segment therefore starts at the rpm trough that follows the flip,
  typically discarding 12–13 samples.
- **Every rpm-binned statistic is masked to those trimmed segments, not to a raw
  gear filter.** A DSG upshift holds pedal, TPS and airmass high straight through
  the torque interrupt: in `12_08_37` rows 284–288 sit at 99.9 % pedal and
  1279 mg/stk while torque swings to −65 Nm, fuel cuts, and lambda rails to 2.000
  against a 0.800 setpoint. A plain gear filter keeps those samples and they land
  in the 4500–5000 rpm band. Masking to the segments removes them — which is what
  drops the cool session's settled-WOT lambda error from a shift-contaminated
  +0.0042 back to −0.0003.
- **Knock events are anchored on their onset.** Runs are found over the whole log
  and kept only if the onset falls inside a loaded segment. Gating the run itself
  would split one event in two at an upshift, because a cut taken in 3rd routinely
  decays through the shift and on into 4th — that produced three phantom "new"
  events at ~4400 rpm before the rule was fixed.

Rates are quoted **per band-covering segment** rather than per pull. With 4th gear
in the mix a fixed pull count is the wrong denominator: a 4th-gear stretch
starting at 4400 rpm never had the chance to knock at 3500 rpm, and the hot
session's partial `16_24_26` stops at 4157 rpm and never reached the pocket.

Two consequences worth stating plainly, since the method change moved numbers in
both directions:

- **R17 gains a knock event.** `12_34_25` cylinder 1 at 4507 rpm, −3.0°,
  1567 mg/stk, 24.8 °C — in 4th gear, and genuine: that cylinder read exactly
  0.00° for the nine samples before onset, at a settled 416 Nm. R17's pocket count
  is 4, not 3.
- **R18 gains no events at all,** in either session, and gains 4th-gear coverage
  in which nothing knocked.

The `simoscal.analysis` battery does its own pull detection and reports 3rd-gear
pulls only; its findings are unaffected by any of the above.

### The knock-sensor channels are new, and one of them is firmware-anchored

The logging list grew from 81 enabled PIDs
(`PIDs/20260828 List (as-logged-R18).csv`, which is the 08-27 session's list) to
101 (`PIDs/20260828 List.csv`), adding `knks_thd[0..3]` plus four candidate
per-cylinder noise-level address groups (`nl_c42b2`, `nl_c42c2`, `nl_c4274`,
`nl_c429c`). Both counts match their sessions' CSV headers exactly once `Time`
and the trailing metadata column are accounted for. The new channels' provenance
and confidence are not equal:

- **`knks_thd[0..3]` is anchored to the firmware.** `PIDs/find_ram_symbols.py`
  recovers the Simos18 base registers empirically (a0 = `0xD0018000`,
  a9 = `0xD000C000`, from 93 known addresses) and finds the single code reference
  to `C_KNKS_THD_MAX` — Maximum value for KNKS_THD; the `lea [a9]` eight bytes
  earlier supplies `0xd000efe3`, exactly the address the PID list logs. The
  constant it clamps against reads raw 205 in **both** the stock bin and the
  flashed R18 bin, which with the `x / 51.2` scaling is **4.004 V**. So the
  guide's "THD saturates at 4 V" is not a generic figure here — it is this ECU's
  own clamp, and the scaling used to log the channel is confirmed by the fact
  that the clamp lands on it.
- **The four `nl_*` groups are identified by behaviour, not by symbol.** They are
  raw RAM addresses in `0xd0014274`–`0xd00142c9` with no A2L to name them. What
  the data shows is that all four are noise-level-family channels in volts:
  `nl_c42b2` and `nl_c42c2` are filtered (median 0.005 V change per sample),
  `nl_c4274` and `nl_c429c` move per combustion cycle (median ≈0.09–0.10 V) and
  oscillate about their filtered partners.

`nl_c42b2` is the one used as NL below, on two independent tests:

| Group      | Low-rpm mean | ~6000 rpm mean | Session max | R² vs THD | Median Δ/sample |
| ---------- | ------------ | -------------- | ----------- | --------- | --------------- |
| `nl_c42b2` | 0.562 V      | 1.109 V        | 1.532 V     | **0.797** | 0.0053 V        |
| `nl_c42c2` | 0.267 V      | 1.188 V        | 1.655 V     | 0.490     | 0.0050 V        |
| `nl_c4274` | 0.584 V      | 1.126 V        | 2.096 V     | 0.500     | 0.1003 V        |
| `nl_c429c` | 0.246 V      | 1.169 V        | 2.527 V     | 0.394     | 0.0836 V        |

The guide's healthy-sensor reference is ~0.5 V at idle rising to ~1 V by 6000
rpm. `nl_c42b2` matches it almost exactly and has by far the tightest affine
relation to the logged threshold.

**The decisive test `Tunes/README_NEXT_STEPS.md` specified settles it outright.**
The threshold formula is `THD = (NL × factor) + knock-sum adder`, and the factor
is a real per-cylinder calibration —
`IP_KNKS_THD_FAC[0..3]` — Knock detection threshold factor, 4×16 over
rpm × airmass. Interpolating it out of the flashed bin at every logged sample and
solving for the implied adder:

| Group      | Adder mean (cyl 1–4)          | sd        | Min      | Negative samples |
| ---------- | ----------------------------- | --------- | -------- | ---------------- |
| `nl_c42b2` | 0.289 / 0.290 / 0.291 / 0.292 | 0.07 V    | +0.085 V | **0.00 %**       |
| `nl_c42c2` | 0.504 / 0.345 / 0.576 / 0.288 | 0.37–0.50 | −0.702 V | 10.7–37.5 %      |
| `nl_c4274` | 0.258 / 0.268 / 0.267 / 0.257 | 0.26–0.30 | −1.237 V | 13.5–17.0 %      |
| `nl_c429c` | 0.477 / 0.326 / 0.558 / 0.256 | 0.43–0.57 | −2.277 V | 14.1–33.6 %      |

`nl_c42b2` is the only candidate whose adder never goes negative — which the ECU's
own formula forbids — and it is tight (sd 0.07 V) and, tellingly, the same value
on all four cylinders to within 0.003 V. That is what a shared knock-sum adder
looks like. Every other candidate has to produce a negative adder on 10–38 % of
samples to reproduce the logged threshold, so none of them can be NL.

**`nl[0..3]` = `0xD00142B2` (2 bytes each, volts = raw / 13107) is therefore
settled**, closing the "Still open — `nl` (noise level), narrowed to four
candidates" item in `Tunes/README_NEXT_STEPS.md`. Static analysis had ranked
`0xd00142b2` first on reference count and `0xd00142c2` first on interpolated
position; the log decides for the former.

**What is still not logged is RNG, the raw sensor feedback.** A knock is recorded
when RNG exceeds THD, and no candidate group ever crosses THD anywhere in the
session (`nl_c429c` reaches 0.09–0.44 % of samples, the rest 0.00 %). The verdict
below therefore rests on the threshold and noise floor, which is exactly what the
saturation question needs, and does not claim to have watched a knock event cross
a threshold in real time.

> **Folder naming.** Under the project convention this should be
> `Logs/MainTune_R18/`; R16 onward is the `MainTune` lineage. Left as-is to match
> the existing `BasicsGuide_R17/`, but both are misnamed.

---

## The cool session is the controlled repeat, and it is a good one

| Session      | Files | 3rd-gear pulls | 4th-gear segments | Loaded samples | Ambient (median) | Loaded-WOT IAT mean | Loaded-WOT IAT range |
| ------------ | ----- | -------------- | ----------------- | -------------- | ---------------- | ------------------- | -------------------- |
| R17          | 6     | 6              | 3                 | 988            | 18.8 °C          | 25.7 °C             | 22.6–33.4 °C         |
| R18 hot      | 9     | 8              | 5                 | 1578           | 23.3 °C          | 39.1 °C             | 36.1–44.7 °C         |
| **R18 cool** | 8     | 8              | 3                 | 1327           | 19.5 °C          | **26.5 °C**         | 23.3–33.8 °C         |

The cool session sits within 0.8 °C of the R17 baseline on loaded charge
temperature — and marginally *hotter*, so it is if anything the harder side of
the comparison. Band by band:

| RPM band  | R17     | R18 hot | R18 cool |
| --------- | ------- | ------- | -------- |
| 3500–4000 | 28.4 °C | 41.7 °C | 29.2 °C  |
| 4000–4500 | 26.8 °C | 39.2 °C | 27.8 °C  |
| 4500–5000 | 25.5 °C | 38.4 °C | 26.1 °C  |
| 5000–5500 | 24.7 °C | 38.1 °C | 25.3 °C  |
| 5500–6000 | 24.0 °C | 37.7 °C | 24.7 °C  |
| 6000–6500 | 24.1 °C | 37.4 °C | 24.8 °C  |

Load is matched too, so the timing and boost comparisons below are like for like:

| RPM band  | R17 airmass | R18 hot     | R18 cool    |
| --------- | ----------- | ----------- | ----------- |
| 3500–4000 | 1515 mg/stk | 1481 mg/stk | 1512 mg/stk |
| 4000–4500 | 1531 mg/stk | 1512 mg/stk | 1531 mg/stk |
| 4500–5000 | 1518 mg/stk | 1482 mg/stk | 1510 mg/stk |
| 5000–5500 | 1437 mg/stk | 1401 mg/stk | 1428 mg/stk |
| 5500–6000 | 1305 mg/stk | 1283 mg/stk | 1303 mg/stk |
| 6000–6500 | 1211 mg/stk | 1182 mg/stk | 1198 mg/stk |

Evidence: `plots/r18_cool_vs_hot.png`.

---

## High — the 4500–5000 rpm pocket correction is validated

Every loaded WOT knock event across all three sessions, 3rd and 4th gear:

| Session      | File     | Gear  | Cyl | Onset rpm | Worst | Airmass     | IAT     | Other cyls |
| ------------ | -------- | ----- | --- | --------- | ----- | ----------- | ------- | ---------- |
| R17          | 12_30_30 | 3     | 1   | 3380      | −2.62 | 1237 mg/stk | 33.3 °C | 0          |
| R17          | 12_34_25 | **4** | 1   | 4507      | −3.00 | 1567 mg/stk | 24.8 °C | 0          |
| R17          | 12_29_45 | 3     | 4   | 4563      | −3.00 | 1511 mg/stk | 25.1 °C | 0          |
| R17          | 12_26_24 | 3     | 1   | 4830      | −3.00 | 1508 mg/stk | 23.2 °C | 0          |
| R17          | 12_32_53 | 3     | 4   | 4973      | −3.00 | 1480 mg/stk | 25.3 °C | 0          |
| R18 hot      | 16_28_04 | 3     | 1   | 3142      | −2.62 | 1383 mg/stk | 41.4 °C | 0          |
| R18 hot      | 16_30_31 | 3     | 4   | 4798      | −3.00 | 1468 mg/stk | 37.5 °C | 0          |
| R18 hot      | 16_34_22 | 3     | 1   | 5706      | −3.00 | 1279 mg/stk | 38.8 °C | 0          |
| R18 hot      | 16_37_04 | 3     | 2   | 6084      | −3.00 | 1194 mg/stk | 37.6 °C | 0          |
| **R18 cool** | 12_07_40 | 3     | 4   | 4827      | −3.00 | 1499 mg/stk | 25.1 °C | 0          |

Events against the segments that actually swept each band:

| RPM band  | R17         | R18 hot     | R18 cool    |
| --------- | ----------- | ----------- | ----------- |
| 3500–4000 | 0/6  (0.00) | 0/9  (0.00) | 0/8  (0.00) |
| 4000–4500 | 0/7  (0.00) | 0/13 (0.00) | 0/10 (0.00) |
| 4500–5000 | 4/8  (0.50) | 1/11 (0.09) | 1/10 (0.10) |
| 5000–5500 | 0/7  (0.00) | 0/9  (0.00) | 0/8  (0.00) |
| 5500–6000 | 0/6  (0.00) | 1/9  (0.11) | 0/8  (0.00) |
| 6000–6500 | 0/6  (0.00) | 1/7  (0.14) | 0/8  (0.00) |

In the targeted band, pooling both R18 sessions gives 2 events over 21
band-covering segments against R17's 0.50 per segment, which predicts 10.5.
Treating segments as independent trials at a constant rate,
P(≤2 | mean 10.5) = 0.0018; the cool session alone is 1 in 10 against 5 expected,
P = 0.040. That Poisson model is a convenience — segments in one session share
weather, road, and driver — so read it as a weight rather than a p-value, but a
five-fold rate drop that reproduces across two sessions in opposite thermal
conditions is not noise.

The remaining cool-air event is cylinder 4 at 4827 rpm, 1499 mg/stk, 25.1 °C —
within 3 rpm of R17's `12_26_24` event at 4830 rpm and in the same airmass row.
So the pocket is thinner but not clean, and the surviving event sits exactly where
R17's did. That is the boundary of what the −0.750° / −1.500° correction bought.

Evidence: `plots/r18_cool_vs_hot.png`, `plots/analysis_knock.png`,
`plots/drive2_battery/analysis_knock.png`.

---

## High — the high-rpm knock was heat, and that is now demonstrated

The hot session logged −3.0° events at 5706 and 6084 rpm, in base ignition R18
left byte-identical to R17. The previous review argued from the byte-identity
that R18 could not have caused them and pointed at 37–39 °C intake air. The cool
session tests that directly: eight full pulls to 6300–6580 rpm at 24–25 °C charge
air, plus three 4th-gear stretches, produced **no loaded knock at all above
5000 rpm** — see the band table above. The high-rpm events belong to 38 °C intake
air, not to the calibration. **No high-rpm timing change is warranted** — which is
what the previous review's gate item 1 asked to be checked before building R19.

The confirmation shows up in delivered timing too. Delivered ignition minus the
base table, over loaded WOT:

| RPM band  | R17    | R18 hot | R18 cool |
| --------- | ------ | ------- | -------- |
| 3500–4000 | −0.90° | −2.36°  | −0.68°   |
| 4000–4500 | −0.25° | −0.92°  | −0.09°   |
| 4500–5000 | −0.37° | −0.74°  | −0.04°   |
| 5000–5500 | −0.40° | −1.06°  | −0.13°   |
| 5500–6000 | −0.62° | −1.08°  | −0.29°   |
| 6000–6500 | −0.48° | −0.76°  | −0.23°   |

In cool air the ECU delivers essentially the calibrated base everywhere — the
protection families have almost nothing to do. The hot session's roughly 2×
pull-back was the Spark-IAT family working as intended against 13 °C hotter air.
And the cool session's pull-back is *smaller than R17's* in every band, because
R17 was carrying retard from four pocket events and this session carried one.

---

## High — sensor saturation is ruled out, and the gain hypothesis is dead

This is the question the previous review could not answer and explicitly held the
next revision on. It is now answered.

### The measurement

Per-cylinder noise level (`nl_c42b2`) and threshold (`knks_thd`), by rpm:

| RPM band  | NL cyl 1–4 (V)          | THD cyl 1–4 (V)         |
| --------- | ----------------------- | ----------------------- |
| 2000–2500 | 0.600 0.581 0.627 0.556 | 1.463 1.342 1.613 1.570 |
| 2500–3000 | 0.619 0.712 0.700 0.736 | 1.507 1.580 1.707 1.953 |
| 3000–3500 | 0.709 0.772 0.781 0.813 | 1.573 1.728 1.813 1.934 |
| 3500–4000 | 0.810 0.736 0.779 0.755 | 1.738 1.659 1.679 1.678 |
| 4000–4500 | 0.872 0.729 0.851 0.816 | 1.821 1.625 1.858 1.777 |
| 4500–5000 | 0.939 0.877 0.942 0.987 | 1.891 1.848 1.950 2.047 |
| 5000–5500 | 1.039 1.082 0.999 1.103 | 2.088 2.231 1.998 2.315 |
| 5500–6000 | 1.103 1.121 1.006 1.105 | 2.230 2.260 2.031 2.236 |
| 6000–6600 | 1.047 1.184 1.154 1.124 | 2.100 2.269 2.258 2.178 |

Against the two limits — sensor saturation near 2 V of noise, threshold clamped
at `C_KNKS_THD_MAX` = **4.004 V** on this bin:

| Cyl | NL max | NL max loaded | THD max | THD p99 | Headroom to 4.004 V | % NL > 2 V | % THD > 3.5 V |
| --- | ------ | ------------- | ------- | ------- | ------------------- | ---------- | ------------- |
| 1   | 1.360  | 1.360         | 2.676   | 2.500   | 1.33 V              | 0.00 %     | 0.00 %        |
| 2   | 1.532  | 1.282         | 3.457   | 2.871   | 0.55 V              | 0.00 %     | 0.00 %        |
| 3   | 1.369  | 1.348         | 2.930   | 2.617   | 1.07 V              | 0.00 %     | 0.00 %        |
| 4   | 1.296  | 1.296         | 3.008   | 2.738   | 1.00 V              | 0.00 %     | 0.00 %        |

And specifically in 5500–6200 rpm — the window that carried the hot session's two
unexplained events (455 samples):

| Cyl | NL mean | NL max  | THD mean | THD max | Below the clamp |
| --- | ------- | ------- | -------- | ------- | --------------- |
| 1   | 1.086 V | 1.360 V | 2.189 V  | 2.676 V | 1.33 V          |
| 2   | 1.135 V | 1.513 V | 2.263 V  | 3.125 V | 0.88 V          |
| 3   | 1.040 V | 1.312 V | 2.077 V  | 2.930 V | 1.07 V          |
| 4   | 1.115 V | 1.296 V | 2.233 V  | 3.008 V | 1.00 V          |

The noise floor tracks the guide's healthy reference — about 0.56 V at 2000 rpm
rising to about 1.1 V at 6000 — with a modest overshoot of roughly 0.1–0.2 V above
the reference line from 4500 rpm up. The guide's saturated example had NL at
2.26 V with THD flatlined on 4 V by 5366 rpm. Nothing resembling that appears
anywhere in this session. **The knock sensors on this car are adapting normally,
so the events they report are not saturation ghosts.**

### The per-cylinder gain ordering does not survive contact with the data

The previous review noted, as a suggestion rather than a finding, that the
per-cylinder event counts rank-ordered inversely against the stock
`IP_KNKS_GAIN_PRE[0..3]` values, and that this is what a per-cylinder noise
problem would look like. The measured noise floor kills that idea:

| Cyl | `IP_KNKS_GAIN_PRE` mean | Predicted noise rank | Measured NL | Measured rank | Events, all 3 sessions |
| --- | ----------------------- | -------------------- | ----------- | ------------- | ---------------------- |
| 1   | 33.71                   | 1 (noisiest)         | 1.088 V     | 2             | 5                      |
| 2   | 38.43                   | 3                    | 1.056 V     | 3             | 1                      |
| 3   | 40.00                   | 4 (quietest)         | 1.010 V     | 4             | 0                      |
| 4   | 36.29                   | 2                    | 1.101 V     | 1             | 4                      |

Two things go wrong for the hypothesis at once. The predicted order (1, 4, 2, 3)
is not the measured order (4, 1, 2, 3) — cylinder 1, which has the most events and
the lowest gain table, does *not* have the highest noise floor. And the whole
measured spread across four cylinders is **0.091 V, 8.6 % of the mean**, over 870
loaded samples above 4500 rpm. A 9 % difference in noise floor, with every
cylinder more than 1 V clear of saturation, cannot produce a 5-versus-0 split in
event counts.

So the cylinder-1/cylinder-4 bias is not an instrumentation artefact. The textbook
thermal explanation — the end cylinders of an inline-four run hottest — remains on
the table and is untestable from these channels.

**Conclusion: leave knock control entirely at stock.** `IP_KNKS_GAIN_PRE[0..3]`
— Gain value for each cylinder for the knock pre-window,
`IP_IGA_DEC_KNK` — Spark retard at recognised knocking, and
`IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock is
detected all stay unchanged for now. The guide's warning — **"DO NOT reduce the
gain just to eliminate real knock"** — now applies with the evidence to back it:
THD is nowhere near its ceiling, so there is no saturation to correct, and
touching gain would only blind a sensor that is working.

Evidence: `plots/r18_cool_knock_sensor.png`.

---

## Medium — knock correction decay carries most of a pull, usually into 4th

Every knock event in all three sessions decays monotonically back toward zero — no
ramping, no re-triggering, no multi-cylinder involvement. Including 4th gear makes
the cost of that decay explicit, because it shows where the cut is still being
carried:

| Session  | File     | Cyl | Onset rpm | Held  | Gear when it cleared | State at clear                   |
| -------- | -------- | --- | --------- | ----- | -------------------- | -------------------------------- |
| R17      | 12_30_30 | 1   | 3380      | 2.7 s | 3rd                  | cleared at 5057 rpm              |
| R17      | 12_34_25 | 1   | 4507      | 3.1 s | 4th                  | cleared at 5026 rpm              |
| R17      | 12_29_45 | 4   | 4563      | 3.4 s | 3rd                  | cleared at 6204 rpm              |
| R17      | 12_26_24 | 1   | 4830      | 3.3 s | **4th**              | cleared at 5437 rpm              |
| R17      | 12_32_53 | 4   | 4973      | 3.3 s | **4th**              | cleared at 6349 rpm              |
| R18 hot  | 16_28_04 | 1   | 3142      | 4.0 s | 3rd                  | cleared at 5346 rpm              |
| R18 hot  | 16_30_31 | 4   | 4798      | 4.3 s | **4th**              | cleared at 4335 rpm              |
| R18 hot  | 16_34_22 | 1   | 5706      | 3.1 s | **4th**              | cleared at 4715 rpm              |
| R18 hot  | 16_37_04 | 2   | 6084      | 4.5 s | **4th**              | cleared at 5201 rpm              |
| R18 cool | 12_07_40 | 4   | 4827      | 3.9 s | 3rd                  | still −1.12° at the 6178 rpm cut |

**Six of ten events are still recovering in the next gear**, and the cool
session's single event never cleared at all before the driver lifted — it cost
cylinder 4 timing from 4827 rpm all the way to the 6178 rpm cut. That is exactly
the behaviour `knowledge/ecu-tuning-not-the-basics.md` § Timing and knock control
describes, and it is a legitimate revision topic under
`IP_DLY_INC_FAST_KNK` — number of segments between each increase of fast loop and
`IP_IGA_INC_KNK` — Increasing value of knock integrated correction when knock is
detected.

This is the measurement 4th-gear inclusion bought. Restricted to 3rd gear, four of
these ten events simply vanish from view at the upshift and the carry looks like a
truncation rather than a cost.

`Tunes/README_NEXT_STEPS.md` § R19 candidate already specifies this change
(`IP_DLY_INC_FAST_KNK` stock `2, 5, 7, 9, 16, 21, 27, 33` → `2, 5, 7, 9, 12, 15,
18, 21`; `IP_IGA_INC_KNK` stock 0.375 °CRK → 0.75 °CRK) and gates it on the
knock-sensor channels. **That gate is now satisfied**, and it resolved in the
direction that keeps the plan intact: the events are real threshold crossings, not
saturation ghosts, so R19 is the recovery change and not a gain change — exactly
the branch that section anticipated. Its carry-into-4th argument is confirmed here
on a larger event set.

The one consideration this session adds: faster recovery returns the engine to a
boundary it demonstrably still touches, in the pocket, about once every ten
band-covering segments. Neither table reduces the initial −3.0° protective pull,
so a second event is still met at full depth — but the engine will spend more time
near the boundary than it does today. That is a real trade-off to make
deliberately, not a reason to abandon the change.

---

## Medium — the boost shortfall is confirmed as a carry-over, not an R18 effect

The battery flags a 4.9 kPa mean shortfall from 3699–6186 rpm with the wastegate
integral winding to 14.8 % while the final command sits 15.9 points above the
position feedforward `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost pressure actuator
setpoint. With the cool session in hand, the earlier reading that R18 "improved"
boost tracking is corrected: that was thermal, and in matched air R18 reproduces
R17 almost exactly.

| RPM band  | R17 PUT err | R18 hot | R18 cool | R17 WG I | R18 hot | R18 cool |
| --------- | ----------- | ------- | -------- | -------- | ------- | -------- |
| 3500–4000 | −1.1 kPa    | +0.2    | −0.9     | 0.4 %    | 2.1     | 1.0      |
| 4000–4500 | −3.5 kPa    | +0.2    | −3.0     | 3.9 %    | 4.1     | 3.1      |
| 4500–5000 | −2.2 kPa    | −0.9    | −3.2     | 8.3 %    | 4.7     | 6.9      |
| 5000–5500 | −7.4 kPa    | −5.8    | −7.8     | 10.2 %   | 8.5     | 9.6      |
| 5500–6000 | −5.3 kPa    | −3.3    | −4.9     | 13.3 %   | 11.6    | 13.0     |
| 6000–6500 | −0.1 kPa    | +1.9    | +1.5     | 15.2 %   | 12.4    | 14.8     |

Cool R18 tracks R17 within about 1 kPa and 1.4 points of integral in every band.
The hot session simply needed less absolute correction in less dense air. The
position feedforward under-commanding at high rpm is a real, unchanged, pre-R18
gap and remains a live candidate for a future revision.

Evidence: `plots/analysis_boost.png`, `plots/analysis_wastegate.png`,
`plots/drive2_battery/analysis_boost.png`.

---

## Low — the R14 WOT upshift overboost did not recur in eleven upshifts

`Logs/BasicsGuide_R14/log_review.md` High 1 caught a full-throttle 3 → 4 upshift
that landed in the shelf and railed the PUT sensor at 300.6 kPa, an overshoot only
bounded as ≥ +19.7 kPa. `Tunes/README_NEXT_STEPS.md` § Blocked on data — the WOT
upshift overboost has been waiting on a second instance to size a fix from.

Reading 4th gear puts those shift windows in view — they are exactly the samples
this review trims out of its gear-attributed segments, so they are free to
examine. Across **eleven** WOT 3 → 4 upshifts on R18:

| Session  | Upshifts | PUT peak      | Worst PUT overshoot | Sensor railed |
| -------- | -------- | ------------- | ------------------- | ------------- |
| R18 hot  | 7        | 247–287 kPa   | +8.2 kPa            | 0 of 7        |
| R18 cool | 4        | 257–280 kPa   | +8.0 kPa            | 0 of 4        |

Not one railed the sensor, and the worst overshoot through any of them is
+8.2 kPa against the R14 event's ≥ +19.7 kPa. That is consistent with the
hypothesis that section already raised — the R15 wastegate-feedforward walk-back,
which is in this bin, stops the integral arriving at the shift wound up.

This does not bound the original R14 overshoot, so it does not license a fix sized
from that event. What it does say is that the condition is not currently
reproducing on the post-R15 calibration, which is a reason to lower the item's
priority rather than to keep hunting a second instance.

---

## Low — the battery's lambda High is the same spool transition as before

The cool session's battery reports a +0.069 settled-WOT lean error. Enumerated
manually over the segment-masked data, every excursion above +0.03 is one to three
samples (0.04–0.12 s) at 3094–3113 rpm while PUT is 20–79 kPa below a rapidly
moving setpoint:

| File     | Duration | Peak error | rpm  | Lambda / SP   | PUT error |
| -------- | -------- | ---------- | ---- | ------------- | --------- |
| 12_10_17 | 0.12 s   | +0.079     | 3097 | 0.979 / 0.900 | −75.0 kPa |
| 12_17_04 | 0.08 s   | +0.078     | 3094 | 0.979 / 0.900 | −44.9 kPa |
| 12_11_32 | 0.08 s   | +0.066     | 3102 | 0.979 / 0.913 | −79.0 kPa |
| 12_08_37 | 0.04 s   | +0.041     | 3113 | 0.954 / 0.913 | −22.1 kPa |
| 12_14_04 | 0.04 s   | +0.036     | 3109 | 0.940 / 0.904 | −19.5 kPa |

Mean settled-WOT lambda error across all 1327 loaded samples is **−0.0003**. This
is the spool transition, identical in character to R17 and the hot session, and it
does not support changing `IP_LAMB_BAS_HPDI[1]` — Basic lambda setpoint grid, HPDI
(direct injection) or any lambda floor.

Note the shift-mask point from § Provenance: the upshift fuel cut rails lambda to
2.000 at ~4600 rpm in five of eight cool files. Those samples are excluded here
because they are not a loaded pull in any gear. Include them and the settled-WOT
mean becomes +0.0042 with five spurious "+1.200 lean excursions" — an artefact of
counting the shift as WOT, not a fueling finding.

Evidence: `plots/drive2_battery/analysis_lambda.png`.

---

## Low — fuel, turbo, and limiters all controlled

Cool session, from the battery:

- Worst DI rail sag −4.8 bar (hot session −9.3 bar; R17 −4.6 bar).
- LPFP duty peaks 81.5 %, HPFP effective volume peaks 96.6 % — still the fuel
  system's tightest moment, unchanged in character.
- Turbo speed peaks 204 krpm against the 220 krpm working ceiling.
- Logged PUT-minus-ambient peaks **1908 hPa**, leaving 792 hPa of margin to
  `IP_PUT_AMP_DIF_MAX_PRS_DIF_THR` — Overboost pressure-difference threshold
  (2700 hPa). Higher than the hot session's 1848 hPa, as expected in denser air.
- Demanded manifold-pressure setpoint peaks 314.7 kPa, far under
  `C_PRS_IM_SP_MAX` — Maximum requested intake-manifold pressure setpoint.
- `Torque Lim` is 0 and `Misfires` is 0 across all three sessions, loaded and
  unloaded, in both gears.
- Oil peaks 111 °C, coolant 100 °C — hot, consistent with back-to-back pulls.

Evidence: `plots/drive2_battery/analysis_rail_pressure.png`,
`plots/drive2_battery/analysis_turbo_heat.png`.

---

## Timing and performance — R18 costs nothing in matched air

The base-table column confirms the flashed calibration is R18 in both sessions:

| RPM band  | R17 table | R18 hot | R18 cool |
| --------- | --------- | ------- | -------- |
| 3500–4000 | −5.68°    | −5.63°  | −5.66°   |
| 4000–4500 | −3.69°    | −4.10°  | −4.10°   |
| 4500–5000 | −1.95°    | −3.03°  | −3.03°   |
| 5000–5500 | −0.05°    | −0.77°  | −0.74°   |
| 5500–6000 | +1.31°    | +1.26°  | +1.32°   |
| 6000–6500 | +2.29°    | +2.49°  | +2.55°   |

Changed at 4500 and 5000 rpm, identical from 5500 rpm up — exactly the pocket R18
declared.

Power uses the same actual-gear-trimmed F=ma road method as the R14/R15/R17
reviews. Cross-session comparison stays on the full 3rd-gear sweeps: 4th-gear
segments are long enough for a power estimate only in the hot session (1360 and
1067 rpm of span), while R17 and the cool session top out at 440–730 rpm.

|                               | R17               | R18 hot           | R18 cool          |
| ----------------------------- | ----------------- | ----------------- | ----------------- |
| F=ma wheel hp, mean (3rd)     | 252 hp            | 242 hp            | **251 hp**        |
| F=ma wheel hp, range (3rd)    | 244–257 (6 pulls) | 237–247 (8 pulls) | 243–259 (8 pulls) |
| Trimmed `Calc HP`, mean (3rd) | 301.4 hp          | 298.1 hp          | **304.6 hp**      |

**This resolves the open power question.** The previous review saw −10 F=ma wheel
hp against R17 and could not separate the deliberate timing pull from 13.7 °C
hotter air. In matched air, R18 is within 1 hp of R17 by F=ma and 3.2 hp above it
by trimmed `Calc HP`, with heavily overlapping per-pull ranges. The hot session's
loss was heat. The pocket correction is, within the resolution of a road
measurement, **free**.

The hot session's two 4th-gear estimates (267 and 254 wheel hp; trimmed `Calc HP`
304 and 286) show why they are not used for comparison: in 4th, acceleration is
lower and aero plus rolling resistance carry a much larger share of the force
balance, so F=ma reads about 20 hp above the same session's 3rd-gear mean while
`Calc HP` brackets it. Both methods still disagree on absolute magnitude by
roughly 50 hp, unchanged and unresolved; road grade, wind, and direction of travel
remain uncontrolled between sessions. Treat the R17-vs-R18 comparison as "no
measurable difference", not as a precise figure.

Evidence: `plots/r18_vs_r17_validation.png`.

---

## What these logs still cannot tell us

- **RNG is not logged.** The saturation verdict rests on NL and THD, which is the
  right pair for that question, but no channel here shows the sensor feedback
  crossing the threshold at a knock event. If a future question needs event-level
  confirmation rather than threshold health, that address still has to be found —
  `PIDs/find_ram_symbols.py` is the tool that would find it, using the same
  clamp-anchoring method that pinned `knks_thd`.
- **Cylinder position versus cylinder gain is still confounded.** Cylinders 1 and
  4 carry 9 of 10 events. The noise floor does not explain it; whether it is
  thermal, mechanical, or injector-related is out of reach of these channels.
- **The 4827 rpm cool-air event is a single event.** One event in ten
  band-covering segments is consistent with anything from a genuinely marginal
  cell to bad luck. It is enough to say "don't add timing here", not enough to
  justify pulling more.
- **4th-gear coverage is thin outside the hot session.** R17 and the cool session
  each contribute three short 4th-gear stretches; only the hot session has 4th
  pulls of real length. The 4th-gear evidence is good enough to catch events, to
  check load matching, and to measure decay carry — not to build a 4th-gear-specific
  calibration claim on.
- **5th gear is excluded.** One 49-sample 5th-gear WOT stretch exists, in
  `16_39_32` only. Including a gear present in one session would introduce an
  asymmetry between the three for very little data.

---

## Next-revision gate

**R18 is validated and stays.** All three questions the previous gate held open
are now answered, and none of them calls for a base-timing or knock-protection
change.

1. **Do not build R19 as a base-timing or gain change.** No high-rpm timing pull —
   the hot session's high-rpm events did not reproduce in cool air, in either
   gear. No pocket deepening — one settled event in ten band-covering segments
   does not justify giving back more of an advance the R16→R17 work already
   litigated. No gain change — THD sits 1.0–1.3 V below its 4.004 V clamp and NL
   never exceeds 1.53 V, so there is no saturation to fix, and the guide's warning
   against quieting real knock with gain applies directly.
2. **The R19 candidate in `Tunes/README_NEXT_STEPS.md` is unblocked, and its
   prerequisite resolved in its favour.** That section gates the knock-recovery
   change (`IP_DLY_INC_FAST_KNK`, `IP_IGA_INC_KNK`) on the per-cylinder
   knock-sensor channels, and says the answer decides whether R19 is a recovery
   change or a gain change. The answer is **recovery change**: THD is not
   saturating, so there is nothing for a gain change to fix. Its own reasoning is
   confirmed and strengthened here — six of ten events across the three sessions
   are still recovering in 4th gear, and the cool session's event never cleared
   before the pull ended.
3. **The other live candidate is the wastegate feedforward.**
   `IP_FAC_BPA_SP[0]`/`[1]` — Map for boost pressure actuator setpoint
   under-commands at high rpm and leaves the closed loop carrying 13–15 % integral
   to hold a 5–8 kPa shortfall from 5000 rpm up. This session confirms it as a
   pre-R18 carry-over, reproducible across three sessions and both thermal
   conditions.

   **Recommendation, and it is a judgement call rather than a finding:** take the
   knock-recovery change first, as the queue already plans. Its evidence base is
   complete now, it is the one whose measured cost this session quantified, and
   delaying it leaves a known tax on every pull that knocks. The boost item is
   equally well evidenced but has been stable across three sessions and will keep.
   Whichever goes first, they go in separate revisions — one domain at a time, and
   neither stacked with a base-timing change.
4. **Stop/rollback signals are unchanged** and none has appeared across 16 pulls
   and 8 4th-gear stretches on R18: simultaneous multi-cylinder retard (0 of 10
   events had any co-cylinder), retard that ramps instead of decaying (all 10
   decayed monotonically), loss of lambda or fuel-pressure control, or
   protection-limited timing delivery (`Torque Lim` 0 throughout).
5. **Keep logging the knock-sensor channels, and keep holding WOT into 4th.** The
   channels cost nothing and converted the largest open question in this review
   from untestable to settled in one session. The 4th-gear stretches are what made
   the decay carry measurable, and they found an R17 event that 3rd-gear-only
   analysis had missed.

Still **revision 18 — a starting point, not a finished calibration.** It is now a
validated starting point rather than a candidate one.
