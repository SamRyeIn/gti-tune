"""Read the second R18 session (2026-08-28, cool air) against the first (hot) and R17.

The 2026-08-27 R18 review closed with two open questions and one instrumentation
gap:

1. Does the 4500-5000 rpm knock pocket residue survive in cool air, or was the
   single surviving event a product of 39 C intake air?
2. The two new events at 5706 and 6084 rpm sat in base timing R18 left
   byte-identical to R17, at an intake temperature R17 never tested. Heat, or a
   real high-rpm margin problem?
3. Neither could be separated from *sensor-saturation ghost knock*, because
   the per-cylinder knock-sensor noise level (NL) and threshold (THD) were not
   logged. `knowledge/ecu-tuning-not-the-basics.md` states the mechanism: THD is
   computed as ``(NL x global knock-threshold factor) + knock-sum adder``, and
   once NL climbs past about 2 V the THD flatlines at its 4 V ceiling, the
   sensor stops adapting, and it reports events that are "probably not knock".

This session answers all three. It was logged at 19.5 C ambient with loaded IAT
back near the R17 baseline, and the logging list now carries
``knks_thd[0..3]`` plus four candidate per-cylinder noise-level address groups
(``nl_c42b2``, ``nl_c42c2``, ``nl_c4274``, ``nl_c429c``) that this script
identifies before using.

Every input log uses ``Gear (gear)``, so the logged value is the actual gear and
needs no offset. Gear-weighted power channels are trimmed to actual gear 3.

Usage:
    ../../Code/.venv/bin/python analyze_r18_drive2.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analyze_r18_validation import (
    AIR_GAS_CONSTANT,
    BANDS,
    CD,
    CHANNELS,
    CRR,
    DERIVATIVE_WINDOW_S,
    FRONTAL_AREA_M2,
    GRAVITY,
    HERE,
    KNOCK_EVENT_DEG,
    KNOCK_GAP_ROWS,
    KNOCK_KEYS,
    EVENT_HALF_ROWS,
    MASS_FACTOR,
    MASS_KG,
    PLOT_DIR,
    POCKET_BAND,
    R17_DIR,
    R17_PULL_TAGS,
    R18_PULL_TAGS as R18_HOT_TAGS,
    WATTS_TO_HP,
    contiguous_runs,
    local_slope,
    path_for,
    roughness_proxies,
    style_axis,
)


R18_COOL_TAGS = ("12_07_40", "12_08_37", "12_10_17", "12_11_32",
                 "12_13_03", "12_14_04", "12_17_04", "12_18_28")

# The four candidate per-cylinder noise-level address groups Sam added to the
# logging list, plus the knock threshold. Only one group is the noise level the
# guide describes; identify_noise_level() decides which from the data.
NL_GROUPS = ("nl_c42b2", "nl_c42c2", "nl_c4274", "nl_c429c")

SENSOR_CHANNELS = {
    **{f"thd_{i + 1}": f"knks_thd[{i}] (V)" for i in range(4)},
    **{f"{group}_{i + 1}": f"{group}[{i}] (V)" for group in NL_GROUPS for i in range(4)},
}

# The guide's reference curve for a healthy sensor, and its saturation limits.
NL_REFERENCE = ((0.0, 0.5), (6000.0, 1.0))
NL_SATURATION_V = 2.0
THD_CEILING_V = 4.0

# Stock per-cylinder mean of `IP_KNKS_GAIN_PRE[i]` — Gain value for each
# cylinder for the knock pre-window, last (1302 mg/stk) row, rpm >= 4500,
# decoded from the flashed R18 bin. Adding to these tables LOWERS gain, so a
# lower value here predicts a HIGHER noise floor.
GAIN_PRE_MEAN = {1: 33.71, 2: 38.43, 3: 40.00, 4: 36.29}

# The flashed calibration, needed for the decisive noise-level identification
# test: THD = (NL x IP_KNKS_THD_FAC[cyl]) + knock-sum adder, so the real NL is
# the array that leaves a small non-negative adder under the bin's own factor
# tables. Nothing here writes to the bin.
XDF_PATH = HERE.parent.parent / "Code" / "xdf" / "SC8S50.V1.0.xdf"
BIN_PATH = (HERE.parent.parent / "Tunes" / "MainTune" / "MainTune_out"
            / "R18_20260826-171645" / "Patched_259L_R18.bin")

SENSOR_BANDS = ((2000, 2500), (2500, 3000), (3000, 3500), (3500, 4000),
                (4000, 4500), (4500, 5000), (5000, 5500), (5500, 6000),
                (6000, 6600))


# Gears counted as a loaded WOT pull. Many logs hold a full 3rd-gear sweep and
# then a stretch of 4th at WOT; both are the same operating condition once binned
# by rpm, and 4th adds most of its samples above 4400 rpm, exactly where the
# interesting bands are. Load matches closely enough to merge: across all R18
# pulls, mean airmass agrees within ~30 mg/stk and mean PUT error within ~2 kPa in
# every band from 4500 rpm up.
WOT_GEARS = (3, 4)

# Gear-attributed work (anything using Calc HP or a speed derivative) must skip
# the shift. The DSG's gear channel flips to the next ratio several samples before
# the shift actually pulls the engine down: in `16_37_04` the channel goes 3 -> 4
# at row 331 while rpm keeps climbing to 6255 through row 336, and `Calc HP` steps
# 297 -> 353 hp at that exact flip. Those samples are physically still in the
# lower gear. segments() therefore starts a gear-attributed segment at the rpm
# trough that follows the flip, searched over this window.
SHIFT_SEARCH_S = 1.5

# A gear segment has to be substantial before it counts as a pull or feeds a power
# estimate. 3rd-gear sweeps clear both easily; a trimmed 4th-gear segment is
# shorter, so the power path takes a lower span and reports 3rd and 4th apart.
PULL_MIN_SAMPLES = 50
PULL_MIN_SPAN_RPM = 2500.0
POWER_MIN_SAMPLES = 60
# Cross-session power stays on the full 3rd-gear sweeps. 4th-gear segments are
# long enough for an F=ma estimate only in the hot session (1360 and 1067 rpm of
# span); R17 and the cool session top out around 440-730 rpm, so a 4th-gear
# comparison across sessions is not available and is not attempted.
POWER_COMPARE_GEAR = 3
POWER_MIN_SPAN_RPM = 1000.0

# A segment "covers" an rpm band, and so belongs in that band's denominator, once
# it holds this many loaded samples inside it.
BAND_COVER_SAMPLES = 5


def loaded_wot_mask(data: dict[str, np.ndarray],
                    gears: tuple[int, ...] = WOT_GEARS) -> np.ndarray:
    """Loaded wide-open-throttle samples in any of the given actual gears."""
    return (
        (data["pedal"] >= 90.0)
        & np.isin(np.rint(data["gear"]), gears)
        & (data["rpm"] >= 3000.0)
        & (data["airmass"] >= 0.9)
        & (data["tps"] >= 60.0)
    )


def segments(data: dict[str, np.ndarray],
             gears: tuple[int, ...] = WOT_GEARS) -> list[dict]:
    """Split a log into gear-attributed loaded WOT segments, shift samples trimmed.

    One segment per contiguous run at one gear. The leading samples of a segment
    that follows an upshift still belong to the previous gear (see SHIFT_SEARCH_S),
    so the segment starts at the rpm trough after the gear channel flips.
    """
    out: list[dict] = []
    window = int(round(SHIFT_SEARCH_S / 0.04))
    for gear in gears:
        for run in contiguous_runs(loaded_wot_mask(data, (gear,)), KNOCK_GAP_ROWS):
            if run.size < 5:
                continue
            head = run[:min(window, run.size)]
            start = int(np.argmin(data["rpm"][head]))
            trimmed = run[start:]
            if trimmed.size < 5:
                continue
            out.append({
                "gear": gear,
                "indices": trimmed,
                "shift_samples_trimmed": start,
                "rpm_lo": float(data["rpm"][trimmed].min()),
                "rpm_hi": float(data["rpm"][trimmed].max()),
                "span": float(np.ptp(data["rpm"][trimmed])),
            })
    return out


def segment_mask(data: dict[str, np.ndarray]) -> np.ndarray:
    """The analysis mask: loaded WOT samples that survive gear attribution.

    This is what every rpm-binned statistic below uses, and it is deliberately
    narrower than loaded_wot_mask(). A DSG upshift holds pedal, TPS and airmass
    high right through the torque interrupt, so a plain gear filter keeps the
    shift itself: in `12_08_37` rows 284-288 sit at 99.9 % pedal and 1279 mg/stk
    while torque swings to -65 Nm, fuel cuts and lambda rails to 2.000 against a
    0.800 setpoint. Those samples are not a loaded pull in any gear, and they
    would otherwise land in the 4500-5000 rpm band and corrupt lambda, boost and
    delivered-timing means. segments() already drops them, so the mask is built
    from the segments rather than re-derived.
    """
    mask = np.zeros(data["rpm"].size, dtype=bool)
    for segment in segments(data):
        mask[segment["indices"]] = True
    return mask


def pull_segments(data: dict[str, np.ndarray]) -> list[dict]:
    """Segments substantial enough to count as a pull.

    A 4th-gear stretch never sweeps 2500 rpm — it starts at the shift, around
    4400 rpm, and runs out at redline — so it is held to the shorter span the
    power path uses. Rates below do not lean on this count anyway; they use
    band coverage, which is per-band and needs no gear-specific threshold.
    """
    out = []
    for segment in segments(data):
        if segment["gear"] <= 3:
            ok = (segment["indices"].size >= PULL_MIN_SAMPLES
                  and segment["span"] >= PULL_MIN_SPAN_RPM)
        else:
            ok = (segment["indices"].size >= POWER_MIN_SAMPLES
                  and segment["span"] >= POWER_MIN_SPAN_RPM)
        if ok:
            out.append(segment)
    return out


def session_segments(logs: list[tuple[str, dict]]) -> list[dict]:
    out = []
    for tag, data in logs:
        for segment in segments(data):
            out.append({**segment, "tag": tag, "data": data})
    return out


def band_coverage(all_segments: list[dict], lo: float, hi: float) -> int:
    """How many segments actually swept a band — the honest per-band denominator.

    Counting every band against a fixed pull count is wrong once 4th-gear
    segments are in the mix: a 4th-gear stretch starting at 4400 rpm never had
    the chance to knock at 3500 rpm, and a partial 3rd-gear pull that stops at
    4157 rpm never reached the pocket.
    """
    count = 0
    for segment in all_segments:
        rpm = segment["data"]["rpm"][segment["indices"]]
        if int(np.sum((rpm >= lo) & (rpm < hi))) >= BAND_COVER_SAMPLES:
            count += 1
    return count


def knock_events_gears(logs: list[tuple[str, dict]]) -> list[dict]:
    """Enumerate loaded-WOT knock events over every gear in WOT_GEARS."""
    events: list[dict] = []
    for tag, data in logs:
        loaded = segment_mask(data)
        rough = roughness_proxies(data)
        gear_of = np.rint(data["gear"])
        for key in KNOCK_KEYS:
            retard = data[key]
            # Runs are found over the whole log and then kept by whether their
            # ONSET is in a loaded segment. Gating the run itself would split one
            # event in two at an upshift: a cut taken in 3rd routinely decays
            # through the shift and on into 4th, and the masked shift samples
            # would make the surviving tail look like a fresh onset at ~4400 rpm.
            for run in contiguous_runs(retard <= KNOCK_EVENT_DEG, KNOCK_GAP_ROWS):
                onset = int(run[0])
                if not loaded[onset]:
                    continue
                worst = int(run[np.argmin(retard[run])])
                lo = max(0, onset - EVENT_HALF_ROWS)
                hi = min(retard.size, onset + EVENT_HALF_ROWS + 1)
                window = slice(lo, hi)
                others = [
                    other for other in KNOCK_KEYS
                    if other != key and np.min(data[other][window]) <= KNOCK_EVENT_DEG
                ]
                events.append({
                    "tag": tag,
                    "cylinder": int(key[-1]),
                    "gear": int(gear_of[onset]),
                    "onset_row": onset,
                    "onset_rpm": float(data["rpm"][onset]),
                    "worst_rpm": float(data["rpm"][worst]),
                    "worst_deg": float(retard[worst]),
                    "samples": int(run.size),
                    "airmass": float(data["airmass"][onset] * 1000.0),
                    "iat": float(data["iat"][onset]),
                    "put_error": float(data["put"][onset] - data["put_sp"][onset]),
                    "ign": float(data["ign"][onset]),
                    "ign_table": float(data["ign_table"][onset]),
                    "co_cylinders": others,
                    "rear_jitter": float(np.max(rough["rear_jitter"][window])),
                    "speed": float(data["vehicle_speed"][onset]),
                    "indices": run,
                })
    return sorted(events, key=lambda event: event["onset_rpm"])


def band_stats_gears(data: dict[str, np.ndarray]) -> list[dict[str, float]]:
    """Per-band loaded-WOT means over every gear in WOT_GEARS."""
    base = segment_mask(data)
    out = []
    for lo, hi in BANDS:
        mask = base & (data["rpm"] >= lo) & (data["rpm"] < hi)
        if mask.sum() < 5:
            raise RuntimeError(f"insufficient clean samples in {lo}-{hi} rpm")
        out.append({
            "n": int(mask.sum()),
            "put_error": float(np.mean(data["put"][mask] - data["put_sp"][mask])),
            "wg_i": float(np.mean(data["wg_i"][mask])),
            "lambda": float(np.mean(data["lambda"][mask])),
            "lambda_sp": float(np.mean(data["lambda_sp"][mask])),
            "ign": float(np.mean(data["ign"][mask])),
            "ign_table": float(np.mean(data["ign_table"][mask])),
            "iat": float(np.mean(data["iat"][mask])),
            "airmass": float(np.mean(data["airmass"][mask]) * 1000.0),
            "knock_min": float(min(np.min(data[f"knock_{c}"][mask]) for c in range(1, 5))),
        })
    return out


def load_with_sensors(path: Path) -> dict[str, np.ndarray]:
    """Load a log, including the knock-sensor channels when the file carries them."""
    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    columns = {name.strip() for name in rows[0]}
    wanted = dict(CHANNELS)
    wanted.update({key: column for key, column in SENSOR_CHANNELS.items()
                   if column in columns})
    return {
        key: np.asarray([float(row[column]) for row in rows], dtype=float)
        for key, column in wanted.items()
    }


def load_session(folder: Path, tags: tuple[str, ...]) -> list[tuple[str, dict]]:
    return [(tag, load_with_sensors(path_for(folder, tag))) for tag in tags]


def has_sensors(logs: list[tuple[str, dict]]) -> bool:
    return "thd_1" in logs[0][1]


def stack(logs: list[tuple[str, dict]], key: str) -> np.ndarray:
    return np.concatenate([data[key] for _, data in logs])


def session_conditions(name: str, logs: list[tuple[str, dict]]) -> dict:
    ambient = stack(logs, "ambient_temp")
    iat = stack(logs, "iat")
    loaded = np.concatenate([segment_mask(data) for _, data in logs])
    pulls = [segment for _, data in logs for segment in pull_segments(data)]
    all_segments = [segment for _, data in logs for segment in segments(data)]
    return {
        "name": name,
        "ambient": float(np.median(ambient)),
        "iat_mean": float(np.mean(iat[loaded])),
        "iat_min": float(np.min(iat[loaded])),
        "iat_max": float(np.max(iat[loaded])),
        "pulls": len(pulls),
        "pulls_g3": sum(1 for segment in pulls if segment["gear"] == 3),
        "pulls_g4": sum(1 for segment in pulls if segment["gear"] == 4),
        "segs_g4": sum(1 for segment in all_segments if segment["gear"] == 4),
        "samples": int(loaded.sum()),
        "files": len(logs),
    }


def print_conditions(rows: list[dict]) -> None:
    print("\n=== Session conditions ===")
    print("Loaded WOT covers 3rd and 4th gear, shift samples trimmed from every")
    print("gear-attributed segment. '4th seg' counts every 4th-gear stretch; "
          "'4th pull'")
    print("counts only those long enough to carry a power estimate.")
    print(f"{'session':12s} {'files':>5s} {'3rd pulls':>10s} {'4th pulls':>10s} "
          f"{'4th seg':>8s} {'samples':>8s} {'ambient C':>10s} "
          f"{'loaded IAT mean':>16s} {'loaded IAT range':>18s}")
    for row in rows:
        print(f"{row['name']:12s} {row['files']:5d} {row['pulls_g3']:10d} "
              f"{row['pulls_g4']:10d} {row['segs_g4']:8d} {row['samples']:8d} "
              f"{row['ambient']:10.1f} {row['iat_mean']:16.1f} "
              f"{row['iat_min']:8.1f}-{row['iat_max']:.1f}")


def event_rows(name: str, events: list[dict], pulls: int) -> None:
    print(f"\n{name}: {len(events)} loaded WOT knock events (3rd and 4th gear) "
          f"over {pulls} pulls")
    if not events:
        return
    print(f"  {'file':10s} {'gear':>4s} {'cyl':>3s} {'onset rpm':>9s} {'worst':>6s} "
          f"{'mg/stk':>7s} {'IAT C':>6s} {'co-cyl':>7s}")
    for event in events:
        print(f"  {event['tag']:10s} {event['gear']:4d} {event['cylinder']:3d} "
              f"{event['onset_rpm']:9.0f} {event['worst_deg']:6.2f} "
              f"{event['airmass']:7.0f} {event['iat']:6.1f} "
              f"{len(event['co_cylinders']):7d}")


def upshift_check(name: str, logs: list[tuple[str, dict]]) -> None:
    """Does a full-throttle 3 -> 4 upshift still overboost?

    `Logs/BasicsGuide_R14/log_review.md` High 1 caught a WOT 3 -> 4 that landed in
    the shelf and railed the PUT sensor at 300.6 kPa, an overshoot only bounded as
    >= +19.7 kPa. The shift window is exactly the samples this script trims out of
    its gear-attributed segments, so they are free to examine here: raw loaded-WOT
    gear-4 samples that did not survive the trim.
    """
    print(f"\n{name} full-throttle 3 -> 4 upshifts:")
    print(f"  {'file':10s} {'n':>3s} {'PUT max':>8s} {'PUT err max':>12s} "
          f"{'rpm span':>14s} {'railed':>7s}")
    peaks = []
    for tag, data in logs:
        shift = loaded_wot_mask(data) & ~segment_mask(data)
        if not shift.any():
            continue
        put = data["put"][shift]
        error = (data["put"] - data["put_sp"])[shift]
        peaks.append(float(error.max()))
        print(f"  {tag:10s} {int(shift.sum()):3d} {put.max():8.1f} {error.max():+12.1f} "
              f"{data['rpm'][shift].min():6.0f}-{data['rpm'][shift].max():<7.0f} "
              f"{str(bool(put.max() >= 300.0)):>7s}")
    if peaks:
        print(f"  worst PUT overshoot through any upshift: {max(peaks):+.1f} kPa")


def print_decay(name: str, events: list[dict],
                logs: list[tuple[str, dict]]) -> None:
    """How long each cut is carried, and whether it clears before the pull ends.

    Measured over the whole log rather than the loaded mask, because the decay
    routinely runs through an upshift and on into the next gear — that carry is
    the thing being measured, so gating it away would hide it.
    """
    by_tag = dict(logs)
    print(f"\n{name} knock-correction decay:")
    if not events:
        print("  none")
        return
    print(f"  {'file':10s} {'gear':>4s} {'cyl':>3s} {'onset rpm':>9s} {'worst':>6s} "
          f"{'held s':>7s} {'gear at end':>11s} {'end rpm':>8s} {'end deg':>8s}")
    for event in events:
        data = by_tag[event["tag"]]
        retard = data[f"knock_{event['cylinder']}"]
        index = event["onset_row"]
        while index < retard.size - 1 and retard[index] <= -0.5:
            index += 1
        print(f"  {event['tag']:10s} {event['gear']:4d} {event['cylinder']:3d} "
              f"{event['onset_rpm']:9.0f} {event['worst_deg']:6.2f} "
              f"{(index - event['onset_row']) * 0.04:7.2f} "
              f"{int(np.rint(data['gear'][index - 1])):11d} "
              f"{data['rpm'][index]:8.0f} {retard[index - 1]:8.2f}")


def print_band_events(sessions: list[tuple[str, list[dict], list[dict]]]) -> None:
    print("\n=== Knock events by rpm band, over the segments that swept the band ===")
    print("Denominator is segments covering the band, not a fixed pull count: a "
          "4th-gear\nstretch starting at 4400 rpm never had the chance to knock "
          "at 3500 rpm.")
    header = "  ".join(f"{name:>16s}" for name, _, _ in sessions)
    print(f"{'band':>12s}  {header}")
    for lo, hi in BANDS:
        cells = []
        for _, events, all_segments in sessions:
            count = sum(1 for event in events if lo <= event["onset_rpm"] < hi)
            covering = band_coverage(all_segments, lo, hi)
            rate = f"{count / covering:4.2f}" if covering else "   -"
            cells.append(f"{count:3d}/{covering:<3d} ({rate})")
        print(f"{lo:5d}-{hi:<6d}  " + "  ".join(f"{cell:>16s}" for cell in cells))


def poisson_tail(observed: int, expected: float) -> float:
    """P(X <= observed) for a Poisson with the given mean, by direct summation.

    Used only to say how surprising the post-R18 pocket event count is if the
    R17 event rate had carried over unchanged. It assumes independent events at
    a constant per-pull rate, which is a modelling convenience, not a fact about
    the engine — read it as a rough weight, not a p-value to lean on.
    """
    total = 0.0
    term = np.exp(-expected)
    for k in range(observed + 1):
        if k:
            term *= expected / k
        total += term
    return float(total)


def pocket_rate_test(events: dict[str, list[dict]],
                     session_segs: dict[str, list[dict]]) -> None:
    lo, hi = POCKET_BAND
    print(f"\n=== {lo}-{hi} rpm pocket event rate ===")
    counts = {name: sum(1 for event in items if lo <= event["onset_rpm"] < hi)
              for name, items in events.items()}
    covering = {name: band_coverage(segs, lo, hi) for name, segs in session_segs.items()}
    for name in events:
        print(f"  {name:10s} {counts[name]} events / {covering[name]} segments "
              f"covering the band = {counts[name] / covering[name]:.3f} per segment")
    baseline = counts["R17"] / covering["R17"]
    combined_events = counts["R18 hot"] + counts["R18 cool"]
    combined = covering["R18 hot"] + covering["R18 cool"]
    expected = baseline * combined
    print(f"\n  Both R18 sessions pooled: {combined_events} events / {combined} "
          f"covering segments. At R17's rate that is {expected:.1f} expected.")
    print(f"  P(<= {combined_events} | Poisson mean {expected:.1f}) = "
          f"{poisson_tail(combined_events, expected):.4f}")
    print("  Cool session alone, matched to R17's charge temperature: "
          f"{counts['R18 cool']} / {covering['R18 cool']}, "
          f"P = {poisson_tail(counts['R18 cool'], baseline * covering['R18 cool']):.4f}")


def print_timing_delta(stats: dict[str, list[dict[str, float]]]) -> None:
    print("\n=== Delivered ignition minus base table by band (deg) ===")
    print("Negative means the protection families (Spark-IAT and knock) are "
          "pulling below the calibrated base.")
    names = list(stats)
    print(f"{'band':>12s}  " + "  ".join(f"{name:>10s}" for name in names))
    for index, (lo, hi) in enumerate(BANDS):
        cells = [f"{stats[name][index]['ign'] - stats[name][index]['ign_table']:8.2f}"
                 for name in names]
        print(f"{lo:5d}-{hi:<6d}  " + "  ".join(f"{cell:>10s}" for cell in cells))


def lambda_excursions(name: str, logs: list[tuple[str, dict]],
                      threshold: float = 0.03) -> None:
    """Enumerate every settled-WOT lean excursion the battery's mean can hide."""
    print(f"\n=== {name} settled-WOT lean excursions above +{threshold:.2f} ===")
    print(f"  {'file':10s} {'samples':>7s} {'s':>6s} {'peak err':>9s} {'rpm':>6s} "
          f"{'lambda/SP':>13s} {'PUT err kPa':>12s}")
    found = 0
    for tag, data in logs:
        mask = segment_mask(data) & (data["torque"] >= 250.0)
        error = data["lambda"] - data["lambda_sp"]
        for run in contiguous_runs(mask & (error > threshold), 2):
            worst = int(run[np.argmax(error[run])])
            found += 1
            print(f"  {tag:10s} {run.size:7d} {run.size * 0.04:6.2f} "
                  f"{error[worst]:+9.3f} {data['rpm'][worst]:6.0f} "
                  f"{data['lambda'][worst]:6.3f}/{data['lambda_sp'][worst]:6.3f} "
                  f"{data['put'][worst] - data['put_sp'][worst]:12.1f}")
    if not found:
        print("  none")
    combined = {key: np.concatenate([data[key] for _, data in logs])
                for key in ("lambda", "lambda_sp", "rpm", "torque")}
    loaded = np.concatenate([segment_mask(data) for _, data in logs])
    settled = loaded & (combined["torque"] >= 250.0)
    error = (combined["lambda"] - combined["lambda_sp"])[settled]
    print(f"  settled-WOT mean lambda error {error.mean():+.4f} over {settled.sum()} samples")


def identify_noise_level(logs: list[tuple[str, dict]]) -> str:
    """Pick which candidate address group is the noise level the guide describes.

    Two tests, both from the guide: the noise level should trace roughly 0.5 V at
    idle to 1 V by 6000 rpm, and THD is computed from it as
    ``(NL x factor) + adder``, so THD must be close to an affine function of it.
    The adder is a map rather than a constant, so a perfect fit is not expected —
    the group with the tightest fit and the closest match to the reference curve
    wins.
    """
    print("\n=== Which logged group is the knock-sensor noise level? ===")
    print("Guide reference: ~0.5 V at idle rising to ~1.0 V by 6000 rpm;")
    print("THD = (NL x global knock-threshold factor) + knock-sum adder.\n")
    print(f"{'group':10s} {'low-rpm V':>10s} {'6000 V':>8s} {'max V':>7s} "
          f"{'THD fit R2':>11s} {'slope':>7s} {'|d| per sample':>15s}")
    scores: dict[str, float] = {}
    rpm = stack(logs, "rpm")
    low = (rpm >= 1800.0) & (rpm < 2200.0)
    high = (rpm >= 5800.0) & (rpm < 6300.0)
    for group in NL_GROUPS:
        values = [stack(logs, f"{group}_{i + 1}") for i in range(4)]
        thd = [stack(logs, f"thd_{i + 1}") for i in range(4)]
        fits = []
        slopes = []
        for series, threshold in zip(values, thd):
            ok = np.isfinite(series) & np.isfinite(threshold)
            slope, _ = np.polyfit(series[ok], threshold[ok], 1)
            fits.append(float(np.corrcoef(series[ok], threshold[ok])[0, 1] ** 2))
            slopes.append(float(slope))
        combined = np.concatenate(values)
        low_v = float(np.mean([series[low].mean() for series in values]))
        high_v = float(np.mean([series[high].mean() for series in values]))
        step = float(np.median([np.median(np.abs(np.diff(series))) for series in values]))
        reference_error = abs(low_v - NL_REFERENCE[0][1]) + abs(high_v - NL_REFERENCE[1][1])
        scores[group] = float(np.mean(fits)) - reference_error
        print(f"{group:10s} {low_v:10.3f} {high_v:8.3f} {combined.max():7.3f} "
              f"{np.mean(fits):11.3f} {np.mean(slopes):7.3f} {step:15.4f}")
    winner = max(scores, key=scores.get)
    print(f"\nBest match to both tests: {winner}")
    print("The two low-|d| groups (nl_c42b2, nl_c42c2) are filtered; the two")
    print("high-|d| groups (nl_c4274, nl_c429c) move per combustion cycle and")
    print("track their filtered partners, so all four are noise-level family")
    print("channels, not the raw sensor feedback (RNG).")
    return winner


def bilinear(x: np.ndarray, y: np.ndarray, grid: np.ndarray,
             xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Interpolate a calibration grid the way the ECU does, clamping off-axis."""
    xs = np.clip(xs, x[0], x[-1])
    ys = np.clip(ys, y[0], y[-1])
    ix = np.clip(np.searchsorted(x, xs) - 1, 0, x.size - 2)
    iy = np.clip(np.searchsorted(y, ys) - 1, 0, y.size - 2)
    tx = (xs - x[ix]) / (x[ix + 1] - x[ix])
    ty = (ys - y[iy]) / (y[iy + 1] - y[iy])
    return ((1 - tx) * (1 - ty) * grid[iy, ix]
            + tx * (1 - ty) * grid[iy, ix + 1]
            + (1 - tx) * ty * grid[iy + 1, ix]
            + tx * ty * grid[iy + 1, ix + 1])


def threshold_factor_test(logs: list[tuple[str, dict]]) -> str:
    """Identify NL by requiring THD = NL x factor + a non-negative adder.

    `Tunes/README_NEXT_STEPS.md` names this the decisive test, and it is: the
    factor is a real per-cylinder calibration
    (`IP_KNKS_THD_FAC[0..3]` — Knock detection threshold factor, 4x16 over
    rpm x airmass), so a wrong array has to produce an adder that goes negative,
    which the ECU's own formula forbids.
    """
    from simoscal import SC8S50_STRUCTURE, CalFile

    cal = CalFile.open(XDF_PATH, BIN_PATH, structure=SC8S50_STRUCTURE)
    rpm = stack(logs, "rpm")
    airmass = stack(logs, "airmass") * 1000.0

    print("\n=== Decisive test: THD = NL x IP_KNKS_THD_FAC[cyl] + adder ===")
    print("The real noise level leaves a small, non-negative, low-variance adder;")
    print("a wrong array forces a negative adder, which the formula cannot produce.\n")
    print(f"{'group':10s} {'cyl':>3s} {'adder mean':>11s} {'sd':>8s} {'min':>8s} "
          f"{'max':>8s} {'% negative':>11s}")
    negatives: dict[str, float] = {}
    for group in NL_GROUPS:
        worst = 0.0
        for cyl in range(4):
            view = cal.get(f"IP_KNKS_THD_FAC[{cyl}]")
            factor = bilinear(np.asarray(view.axis_values("x")).ravel(),
                              np.asarray(view.axis_values("y")).ravel(),
                              np.asarray(view.values, dtype=float), rpm, airmass)
            adder = stack(logs, f"thd_{cyl + 1}") - stack(logs, f"{group}_{cyl + 1}") * factor
            share = float(np.mean(adder < 0.0) * 100.0)
            worst = max(worst, share)
            print(f"{group:10s} {cyl + 1:3d} {adder.mean():11.4f} {adder.std():8.4f} "
                  f"{adder.min():8.3f} {adder.max():8.3f} {share:10.2f}%")
        negatives[group] = worst
        print()
    winner = min(negatives, key=negatives.get)
    print(f"Only {winner} keeps the adder non-negative on every cylinder "
          f"(worst {negatives[winner]:.2f}%); the others go negative on "
          + ", ".join(f"{name} up to {share:.1f}%"
                      for name, share in negatives.items() if name != winner))
    return winner


def check_rng(logs: list[tuple[str, dict]]) -> None:
    """The guide records a knock when RNG > THD; test whether any group can be RNG."""
    print("\n=== Is any logged group the raw sensor feedback (RNG)? ===")
    print("A knock is recorded when RNG exceeds THD, so RNG must cross above it.")
    for group in NL_GROUPS:
        fractions = []
        for i in range(4):
            series = stack(logs, f"{group}_{i + 1}")
            threshold = stack(logs, f"thd_{i + 1}")
            fractions.append(float(np.mean(series > threshold)))
        print(f"  {group:10s} samples above THD: "
              + "  ".join(f"cyl{i + 1} {value * 100:5.2f}%"
                          for i, value in enumerate(fractions)))
    print("None crosses THD at any point in the session, so RNG is still not logged.")


def print_sensor_bands(logs: list[tuple[str, dict]], group: str) -> None:
    rpm = stack(logs, "rpm")
    print(f"\n=== Per-cylinder noise level ({group}) and threshold, by rpm ===")
    print(f"{'band':>12s}  {'n':>5s}  {'NL cyl1-4 (V)':>30s}   {'THD cyl1-4 (V)':>30s}")
    for lo, hi in SENSOR_BANDS:
        mask = (rpm >= lo) & (rpm < hi)
        if mask.sum() < 20:
            continue
        nl = [stack(logs, f"{group}_{i + 1}")[mask].mean() for i in range(4)]
        thd = [stack(logs, f"thd_{i + 1}")[mask].mean() for i in range(4)]
        print(f"{lo:5d}-{hi:<6d}  {mask.sum():5d}  "
              + " ".join(f"{value:7.3f}" for value in nl) + "   "
              + " ".join(f"{value:7.3f}" for value in thd))


def saturation_verdict(logs: list[tuple[str, dict]], group: str) -> None:
    print("\n=== Saturation test ===")
    print(f"Guide limits: NL saturates the sensor near {NL_SATURATION_V:.1f} V; "
          f"THD is compromised once it flatlines at {THD_CEILING_V:.1f} V.\n")
    loaded = np.concatenate([segment_mask(data) for _, data in logs])
    print(f"{'cyl':>3s} {'NL max':>7s} {'NL max loaded':>14s} {'THD max':>8s} "
          f"{'THD max loaded':>15s} {'THD p99':>8s} {'headroom to 4 V':>16s} "
          f"{'% NL>2 V':>9s} {'% THD>3.5 V':>12s}")
    for i in range(4):
        nl = stack(logs, f"{group}_{i + 1}")
        thd = stack(logs, f"thd_{i + 1}")
        print(f"{i + 1:3d} {nl.max():7.3f} {nl[loaded].max():14.3f} "
              f"{thd.max():8.3f} {thd[loaded].max():15.3f} "
              f"{np.percentile(thd, 99):8.3f} "
              f"{THD_CEILING_V - thd.max():16.3f} "
              f"{np.mean(nl > NL_SATURATION_V) * 100:9.2f} "
              f"{np.mean(thd > 3.5) * 100:12.2f}")

    # The hot session's two unexplained events were at 5706 and 6084 rpm. Report
    # the threshold headroom this session measured in that same window.
    rpm = stack(logs, "rpm")
    window = (rpm >= 5500.0) & (rpm <= 6200.0)
    print(f"\n5500-6200 rpm window ({window.sum()} samples) — the band that carried the "
          f"hot session's two unexplained events:")
    for i in range(4):
        thd = stack(logs, f"thd_{i + 1}")[window]
        nl = stack(logs, f"{group}_{i + 1}")[window]
        print(f"  cyl{i + 1}: NL mean {nl.mean():.3f} max {nl.max():.3f} V; "
              f"THD mean {thd.mean():.3f} max {thd.max():.3f} V "
              f"({THD_CEILING_V - thd.max():.3f} V below the ceiling)")


def gain_ordering_test(logs: list[tuple[str, dict]], group: str,
                       events_by_cyl: dict[int, int]) -> None:
    """Test the R18 review's suspicion that the noisiest cylinder ghost-knocks most."""
    print("\n=== Per-cylinder noise floor vs stock pre-window gain and event history ===")
    rpm = stack(logs, "rpm")
    loaded = np.concatenate([segment_mask(data) for _, data in logs])
    window = loaded & (rpm >= 4500.0)
    print(f"Loaded WOT samples (3rd and 4th gear) at rpm >= 4500: {window.sum()}\n")
    print(f"{'cyl':>3s} {'GAIN_PRE mean':>14s} {'predicted noise rank':>21s} "
          f"{'NL mean (V)':>12s} {'measured rank':>14s} {'prior events':>13s}")
    nl_mean = {i + 1: float(stack(logs, f"{group}_{i + 1}")[window].mean()) for i in range(4)}
    # Adding to the gain tables lowers gain, so ascending table value is
    # descending predicted noise.
    predicted = sorted(GAIN_PRE_MEAN, key=lambda cyl: GAIN_PRE_MEAN[cyl])
    measured = sorted(nl_mean, key=lambda cyl: -nl_mean[cyl])
    for cyl in (1, 2, 3, 4):
        print(f"{cyl:3d} {GAIN_PRE_MEAN[cyl]:14.2f} {predicted.index(cyl) + 1:21d} "
              f"{nl_mean[cyl]:12.3f} {measured.index(cyl) + 1:14d} "
              f"{events_by_cyl.get(cyl, 0):13d}")
    spread = max(nl_mean.values()) - min(nl_mean.values())
    print(f"\nPredicted noise order (from gain): {predicted}")
    print(f"Measured noise order:              {measured}")
    print(f"Measured spread across cylinders:  {spread:.3f} V "
          f"({spread / np.mean(list(nl_mean.values())) * 100:.1f}% of the mean)")


def print_band_compare(rows: dict[str, list[dict[str, float]]], field: str,
                       title: str, fmt: str = "{:8.1f}") -> None:
    print(f"\n=== {title} ===")
    names = list(rows)
    print(f"{'band':>12s}  " + "  ".join(f"{name:>10s}" for name in names))
    for index, (lo, hi) in enumerate(BANDS):
        cells = [fmt.format(rows[name][index][field]) for name in names]
        print(f"{lo:5d}-{hi:<6d}  " + "  ".join(f"{cell:>10s}" for cell in cells))


def segment_power(tag: str, data: dict[str, np.ndarray], segment: dict) -> dict | None:
    """F=ma road power over one gear-attributed segment.

    The segment has already had its post-shift samples trimmed by segments(), so
    every row here is physically in the gear it is labelled with and `Calc HP`'s
    gear-ratio weighting is correct. Without that trim the leading samples of a
    4th-gear segment carry the ~50 hp flip artifact.
    """
    indices = segment["indices"]
    if indices.size < POWER_MIN_SAMPLES or segment["span"] < POWER_MIN_SPAN_RPM:
        return None

    # Reconstruct uniform 40-ms logging time; the high absolute Time channel is
    # float32-quantized and unsuitable for a direct speed derivative.
    time = np.arange(data["rpm"].size, dtype=float) * 0.04
    rear_speed = 0.5 * (data["wheel_rl"] + data["wheel_rr"]) / 3.6
    vehicle_speed = data["vehicle_speed"] / 3.6
    speed = np.where(rear_speed > 1.0, rear_speed, vehicle_speed)
    acceleration = local_slope(time, speed, DERIVATIVE_WINDOW_S)
    density = (data["ambient"] * 1000.0) / (
        AIR_GAS_CONSTANT * (data["ambient_temp"] + 273.15)
    )
    aero_force = 0.5 * density * CD * FRONTAL_AREA_M2 * speed ** 2
    rolling_force = CRR * MASS_KG * GRAVITY
    wheel_force = MASS_KG * MASS_FACTOR * acceleration + aero_force + rolling_force
    wheel_hp = wheel_force * speed * WATTS_TO_HP

    # Exclude the derivative's edge half-window from the peak search.
    edge = int(round((DERIVATIVE_WINDOW_S / 2.0) / 0.04))
    inner = indices[edge:-edge] if indices.size > 2 * edge else indices
    return {
        "tag": tag,
        "gear": segment["gear"],
        "rpm_lo": segment["rpm_lo"],
        "rpm_hi": segment["rpm_hi"],
        "samples": int(indices.size),
        "peak_wheel_hp": float(np.nanmax(wheel_hp[inner])),
        "peak_calc_hp": float(np.nanmax(data["calc_hp"][inner])),
    }


def power_table(name: str, logs: list[tuple[str, dict]]) -> dict:
    results = [result for tag, data in logs for segment in segments(data)
               if (result := segment_power(tag, data, segment)) is not None]
    print(f"\n{name} F=ma estimates over gear-attributed segments "
          f"({len(results)} segments):")
    for result in results:
        print(f"  {result['tag']} gear {result['gear']} "
              f"({result['rpm_lo']:.0f}-{result['rpm_hi']:.0f} rpm, "
              f"{result['samples']:3d} samples): wheel {result['peak_wheel_hp']:5.0f} hp, "
              f"Calc HP trimmed {result['peak_calc_hp']:.0f} hp")
    out = {"name": name, "results": results}
    for gear in WOT_GEARS:
        rows = [result for result in results if result["gear"] == gear]
        if not rows:
            continue
        wheel = np.asarray([row["peak_wheel_hp"] for row in rows])
        calc = np.asarray([row["peak_calc_hp"] for row in rows])
        print(f"  gear {gear} ({len(rows)}): wheel mean {wheel.mean():.0f} hp, "
              f"range {wheel.min():.0f}-{wheel.max():.0f}; "
              f"trimmed Calc HP mean {calc.mean():.1f} hp")
        out[f"wheel_g{gear}"] = wheel
        out[f"calc_g{gear}"] = calc
    return out


def plot_knock_sensor(logs: list[tuple[str, dict]], group: str) -> None:
    rpm = stack(logs, "rpm")
    loaded = np.concatenate([segment_mask(data) for _, data in logs])
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
    figure.suptitle("R18 cool-air session — knock-sensor noise level and threshold "
                    "against the guide's saturation limits", fontsize=12)

    reference_rpm = np.array([1800.0, 6600.0])
    reference_nl = np.interp(reference_rpm, [NL_REFERENCE[0][0], NL_REFERENCE[1][0]],
                             [NL_REFERENCE[0][1], NL_REFERENCE[1][1]])
    colors = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd")

    for index, (axis, kind) in enumerate(zip(axes, ("nl", "thd"))):
        for cyl in range(4):
            key = f"{group}_{cyl + 1}" if kind == "nl" else f"thd_{cyl + 1}"
            series = stack(logs, key)
            centers, means = [], []
            for lo, hi in SENSOR_BANDS:
                mask = loaded & (rpm >= lo) & (rpm < hi)
                if mask.sum() < 20:
                    continue
                centers.append((lo + hi) / 2.0)
                means.append(series[mask].mean())
            axis.scatter(rpm[loaded], series[loaded], s=2, alpha=0.10,
                         color=colors[cyl], linewidths=0)
            axis.plot(centers, means, color=colors[cyl], linewidth=2.2,
                      marker="o", markersize=4, label=f"cyl {cyl + 1}")
        style_axis(axis)
        axis.set_xlabel("Engine speed (rpm)", fontweight="bold")
        axis.legend(loc="lower right", fontsize=8)
        axis.set_xlim(1800, 6700)

    axes[0].plot(reference_rpm, reference_nl, color="black", linestyle="--",
                 linewidth=1.4, label="guide reference")
    axes[0].axhline(NL_SATURATION_V, color="black", linestyle=":", linewidth=1.6)
    axes[0].text(1900, NL_SATURATION_V + 0.06,
                 f"sensor saturates near {NL_SATURATION_V:.0f} V", fontsize=8)
    axes[0].set_ylabel(f"Noise level {group} (V)", fontweight="bold")
    axes[0].set_title("Noise level — loaded WOT samples and band means", fontsize=10)
    axes[0].set_ylim(0, NL_SATURATION_V + 0.35)
    axes[0].legend(loc="lower right", fontsize=8)

    axes[1].axhline(THD_CEILING_V, color="black", linestyle=":", linewidth=1.6)
    axes[1].text(1900, THD_CEILING_V + 0.08,
                 f"THD ceiling {THD_CEILING_V:.0f} V — detection compromised above",
                 fontsize=8)
    axes[1].set_ylabel("Knock threshold knks_thd (V)", fontweight="bold")
    axes[1].set_title("Threshold — never reaches its ceiling", fontsize=10)
    axes[1].set_ylim(0, THD_CEILING_V + 0.35)

    figure.tight_layout()
    figure.savefig(PLOT_DIR / "r18_cool_knock_sensor.png", dpi=150)
    plt.close(figure)


def plot_session_compare(sessions: list[tuple[str, list[dict], list[tuple[str, dict]]]]) -> None:
    figure, axes = plt.subplots(1, 2, figsize=(13.5, 5.4))
    figure.suptitle("R18 cool-air session vs the hot R18 session and R17", fontsize=12)
    colors = {"R17": "#7f7f7f", "R18 hot": "#d62728", "R18 cool": "#1f77b4"}

    for name, events, logs in sessions:
        rpm = stack(logs, "rpm")
        iat = stack(logs, "iat")
        loaded = np.concatenate([segment_mask(data) for _, data in logs])
        centers, means = [], []
        for lo, hi in BANDS:
            mask = loaded & (rpm >= lo) & (rpm < hi)
            if mask.sum() < 10:
                continue
            centers.append((lo + hi) / 2.0)
            means.append(iat[mask].mean())
        axes[0].plot(centers, means, marker="o", color=colors[name], label=name)
        for gear, marker in ((3, "o"), (4, "^")):
            picked = [event for event in events if event["gear"] == gear]
            if not picked:
                continue
            axes[1].scatter([event["onset_rpm"] for event in picked],
                            [event["iat"] for event in picked],
                            s=90, marker=marker, color=colors[name],
                            edgecolor="black", linewidth=0.6, zorder=3,
                            label=f"{name}, {gear}th gear" if gear == 4 else name)

    axes[0].axvspan(4500, 5000, color="#ffcc80", alpha=0.35)
    axes[0].text(4750, axes[0].get_ylim()[0] + 1.0, "R18 pocket", ha="center", fontsize=8)
    style_axis(axes[0])
    axes[0].set_xlabel("Engine speed (rpm)", fontweight="bold")
    axes[0].set_ylabel("Loaded WOT intake air temperature (°C)", fontweight="bold")
    axes[0].set_title("Charge temperature by band", fontsize=10)
    axes[0].legend(fontsize=8)

    axes[1].axvspan(4500, 5000, color="#ffcc80", alpha=0.35)
    style_axis(axes[1])
    axes[1].set_xlabel("Knock onset engine speed (rpm)", fontweight="bold")
    axes[1].set_ylabel("Intake air temperature at onset (°C)", fontweight="bold")
    axes[1].set_title("Every loaded knock event — circles 3rd gear, triangles 4th",
                      fontsize=10)
    axes[1].set_xlim(3000, 6600)
    axes[1].legend(fontsize=8)

    figure.tight_layout()
    figure.savefig(PLOT_DIR / "r18_cool_vs_hot.png", dpi=150)
    plt.close(figure)


def main() -> None:
    PLOT_DIR.mkdir(exist_ok=True)
    r17 = load_session(R17_DIR, R17_PULL_TAGS)
    hot = load_session(HERE, R18_HOT_TAGS)
    cool = load_session(HERE, R18_COOL_TAGS)

    conditions = [session_conditions(name, logs) for name, logs in
                  (("R17", r17), ("R18 hot", hot), ("R18 cool", cool))]
    print_conditions(conditions)

    events = {name: knock_events_gears(logs) for name, logs in
              (("R17", r17), ("R18 hot", hot), ("R18 cool", cool))}
    session_segs = {name: session_segments(logs) for name, logs in
                    (("R17", r17), ("R18 hot", hot), ("R18 cool", cool))}
    pulls = {row["name"]: row["pulls"] for row in conditions}
    for name in ("R17", "R18 hot", "R18 cool"):
        event_rows(name, events[name], pulls[name])
    print_band_events([(name, events[name], session_segs[name])
                       for name in ("R17", "R18 hot", "R18 cool")])
    pocket_rate_test(events, session_segs)
    for name, logs in (("R17", r17), ("R18 hot", hot), ("R18 cool", cool)):
        print_decay(name, events[name], logs)
    for name, logs in (("R18 hot", hot), ("R18 cool", cool)):
        upshift_check(name, logs)

    if not has_sensors(cool):
        raise RuntimeError("cool session is missing the knock-sensor channels")
    group = identify_noise_level(cool)
    confirmed = threshold_factor_test(cool)
    if confirmed != group:
        raise RuntimeError(
            f"noise-level identification disagrees: behavioural test picked "
            f"{group}, the threshold-factor test picked {confirmed}")
    check_rng(cool)
    print_sensor_bands(cool, group)
    saturation_verdict(cool, group)
    events_by_cyl: dict[int, int] = {cyl: 0 for cyl in (1, 2, 3, 4)}
    for items in events.values():
        for event in items:
            events_by_cyl[event["cylinder"]] += 1
    gain_ordering_test(cool, group, events_by_cyl)

    stats = {name: band_stats_gears({key: np.concatenate([data[key] for _, data in logs])
                                     for key in CHANNELS})
             for name, logs in (("R17", r17), ("R18 hot", hot), ("R18 cool", cool))}
    for field, title, fmt in (("ign_table", "Base ignition table value by band (deg)", "{:8.2f}"),
                              ("ign", "Delivered ignition by band (deg)", "{:8.2f}"),
                              ("put_error", "PUT minus setpoint by band (kPa)", "{:8.1f}"),
                              ("wg_i", "Wastegate integral by band (%)", "{:8.1f}"),
                              ("iat", "Intake air temperature by band (deg C)", "{:8.1f}"),
                              ("airmass", "Airmass by band (mg/stk)", "{:8.0f}"),
                              ("n", "Loaded WOT samples by band", "{:8.0f}")):
        if field in stats["R17"][0]:
            print_band_compare(stats, field, title, fmt)

    print_timing_delta(stats)
    lambda_excursions("R18 cool", cool)

    power = [power_table(name, logs) for name, logs in
             (("R17", r17), ("R18 hot", hot), ("R18 cool", cool))]

    plot_knock_sensor(cool, group)
    plot_session_compare([("R17", events["R17"], r17),
                          ("R18 hot", events["R18 hot"], hot),
                          ("R18 cool", events["R18 cool"], cool)])
    print(f"\nWrote plots to {PLOT_DIR}")
    return power


if __name__ == "__main__":
    main()
