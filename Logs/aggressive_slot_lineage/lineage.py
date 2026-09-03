"""Every pull this car has ever run on the aggressive ~26 psi boost curve.

The slot *number* carrying that curve has moved three times — it was slot 3 when
R09 first cut the 26 psi shelf, slot 4 from R14, and slot 3 again from R22 — so
a folder-by-folder reading keyed on the number would mix three different
calibrations together. This module keys on the **curve** instead, which is
logged directly:

* `PUT SP` — Pressure up throttle setpoint is the slot's own boost cap read back
  out of the ECU, and the aggressive curve peaks at 2806-2809 hPa while every
  other slot this car has run peaks at 2699 or below. Above 3400 rpm the cap is
  binding, so one number separates them with ~100 hPa of margin.
* The five `Spark modifier` — map slot ignition offset grids were neutral until
  R20 wrote one, so every aggressive-curve pull up to R19 is base timing by
  construction. From R20 the offset has to be reconstructed per pull, which is
  what `_offset` does.

That gives one continuous base-timing series across seven sessions of pump 92
plus R22's four dosed control pulls — the population an R23 aggressive slot has
to be sized against.

Event definitions are R19's, unchanged, so rates here are comparable with every
prior review: a cylinder is in an event at <= -1.0 CRK, runs closer than ten
rows are one event, and a sample is loaded at pedal >= 90 %, rpm >= 3000,
airmass >= 0.9 g/stk and TPS >= 60 %.

Run:  Code/.venv/bin/python Logs/aggressive_slot_lineage/lineage.py
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LOGS = HERE.parent
REPO_ROOT = LOGS.parent

SAMPLE_S = 0.04

#: A pull is on the aggressive curve if its binding `PUT SP` peaks at or above
#: this. The aggressive cap is 2806-2809 hPa as logged; the next curve down
#: peaks at 2699, and the pre-R09 base ceiling at ~2630. 2780 sits in the gap.
AGGRESSIVE_PEAK_MIN_HPA = 2780.0
#: Below this the cap is not binding — every slot is still ramping onto it.
CAP_BINDING_RPM = 3400.0

#: From R20 on, a slot may carry a `Spark modifier` — map slot ignition offset.
#: A reconstructed offset at or below this is the neutral grid, i.e. base timing.
BASE_TIMING_OFFSET_MAX_DEG = 0.5
#: Reconstructing the offset needs the top of the grid, where it is written.
OFFSET_LOADED_MIN_MG = 1350.0
#: The first revision whose bin holds a non-neutral `Spark modifier` grid.
FIRST_MODIFIER_REVISION = 20

# --- R19's event definitions, carried over verbatim -------------------------- #
KNOCK_EVENT_DEG = -1.0
KNOCK_GAP_ROWS = 10
RECOVERED_DEG = -0.05

BANDS = ((3000, 3500), (3500, 4000), (4000, 4500), (4500, 5000),
         (5000, 5500), (5500, 6000), (6000, 6600))
#: Airmass bins in mg/stk, cut on the base ignition grid's own top breakpoints
#: (1049.97 / 1200.01 / 1400.00) so a rate can be read straight onto the row it
#: would be calibrated in.
AIR_BINS = ((900, 1050), (1050, 1200), (1200, 1400), (1400, 1800))

KNOCK_KEYS = ("knock_1", "knock_2", "knock_3", "knock_4")

#: Channel name -> the CSV headers it has appeared under. `Gear` is the one that
#: genuinely changes meaning with its header (see CLAUDE.md): `Gear ()` is
#: zero-indexed and needs +1, `Gear (gear)` is the actual gear.
COLUMNS = {
    "time": ("Time",),
    "rpm": ("Engine Speed (rpm)",),
    "pedal": ("Pedal Pos (%)",),
    "tps": ("TPS (%)",),
    "airmass": ("Airmass (g/stk)",),
    "put": ("PUT (kpa)",),
    "put_sp": ("PUT SP (kpa)",),
    "lambda": ("Lambda (l)",),
    "lambda_sp": ("Lambda SP (l)",),
    "hpfp": ("HPFP Eff Vol (%)",),
    "iat": ("IAT (°C)",),
    "ign": ("Ign Avg (°)",),
    "ign_table": ("Ign Table (°)",),
    "knock_1": ("Knock Cyl 1 (°)",),
    "knock_2": ("Knock Cyl 2 (°)",),
    "knock_3": ("Knock Cyl 3 (°)",),
    "knock_4": ("Knock Cyl 4 (°)",),
    "valve_lift": ("Valve Lift Pos ()",),
    "coolant": ("Coolant Temp (°C)",),
    "oil": ("Oil Temp (°C)",),
    "ambient_temp": ("Ambient Temp (°C)",),
}
GEAR_ZERO_INDEXED = "Gear ()"
GEAR_ACTUAL = "Gear (gear)"

#: Which tank each session ran. Only R22 was dosed with VP Octanium; every
#: earlier aggressive-curve session is plain 92 AKI. Recorded rather than
#: inferred, because the dose is one of the things being priced.
FUEL = {22: "dosed"}


def contiguous_runs(mask: np.ndarray, gap: int = 0) -> list[np.ndarray]:
    """Index runs of True, merging runs separated by fewer than ``gap`` rows."""
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(idx) > max(gap, 1))
    return [part for part in np.split(idx, breaks + 1) if part.size]


def load(path: Path) -> dict[str, np.ndarray] | None:
    """One log as float arrays, or ``None`` if it lacks a channel we need.

    Fails loud on a *malformed* file and quietly on a *short* one: an early
    session that never logged `HPFP Eff Vol` is not an error, it is a session
    that cannot answer the pump question, and the caller says which channels it
    actually needs.
    """
    with path.open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return None
    header = rows[0].keys()
    out: dict[str, np.ndarray] = {}
    for key, candidates in COLUMNS.items():
        column = next((c for c in candidates if c in header), None)
        if column is None:
            continue
        out[key] = np.asarray([float(r[column] or "nan") for r in rows], dtype=float)

    # Gear: the header decides whether an offset is owed. Anything else is
    # refused rather than guessed — a silent wrong gear is how a pull gets
    # attributed to the wrong ratio.
    if GEAR_ACTUAL in header:
        out["gear"] = np.asarray([float(r[GEAR_ACTUAL] or "nan") for r in rows])
    elif GEAR_ZERO_INDEXED in header:
        out["gear"] = np.asarray([float(r[GEAR_ZERO_INDEXED] or "nan") for r in rows]) + 1.0
    else:
        raise RuntimeError(f"{path.name}: no recognised gear column")
    return out


def loaded_mask(d: dict[str, np.ndarray]) -> np.ndarray:
    """R19's loaded-WOT gate, unchanged, all gears."""
    return ((d["pedal"] >= 90.0) & (d["rpm"] >= 3000.0)
            & (d["airmass"] >= 0.9) & (d["tps"] >= 60.0))


def _offset(d: dict[str, np.ndarray], sel: np.ndarray) -> float:
    """Median reconstructed `Spark modifier` offset over ``sel``, in CRK.

    `Ign Table` — the base map lookup carries no slot modifier, and the logged
    per-cylinder knock channels carry the retard, so
    ``Ign Avg - Ign Table - worst per-cylinder retard`` recovers the offset.
    It also picks up any other subtractive correction in force — the Spark IAT
    tables above all — which is why it is only used from R20 on, where the
    installed IAT table reads 0.00 across the logged range.
    """
    if not {"ign", "ign_table"} <= d.keys():
        return float("nan")
    worst = np.nanmin(np.vstack([d[k] for k in KNOCK_KEYS]), axis=0)
    off = d["ign"] - d["ign_table"] - worst
    use = sel & np.isfinite(off) & (d["airmass"] * 1000.0 >= OFFSET_LOADED_MIN_MG)
    return float(np.median(off[use])) if int(use.sum()) >= 4 else float("nan")


@dataclass
class Session:
    """One log file that ran the aggressive curve on base timing."""

    revision: int
    tag: str
    fuel: str
    data: dict[str, np.ndarray] = field(repr=False)
    put_peak_hpa: float
    offset_deg: float

    @property
    def loaded_s(self) -> float:
        return float(loaded_mask(self.data).sum()) * SAMPLE_S


def collect() -> tuple[list[Session], list[tuple[int, str, str]]]:
    """Every aggressive-curve base-timing log, plus why each other one was cut."""
    kept: list[Session] = []
    dropped: list[tuple[int, str, str]] = []
    for folder in sorted(LOGS.glob("BasicsGuide_R*"),
                         key=lambda p: int(p.name.split("_R")[1])):
        revision = int(folder.name.split("_R")[1])
        for path in sorted(folder.glob("simostools-*.csv")):
            tag = path.stem.split("-")[-1]
            d = load(path)
            #: The gate itself needs these; a log missing one cannot be
            #: classified at all, and guessing is how a pull ends up counted
            #: against the wrong calibration.
            required = ("put_sp", "rpm", "pedal", "tps", "airmass",
                        *KNOCK_KEYS)
            if d is None or not set(required) <= d.keys():
                missing = "none" if d is None else ", ".join(
                    sorted(set(required) - d.keys()))
                dropped.append((revision, tag, f"missing channels: {missing}"))
                continue
            binding = loaded_mask(d) & (d["rpm"] >= CAP_BINDING_RPM)
            if int(binding.sum()) < 10:
                dropped.append((revision, tag, "no binding loaded samples"))
                continue
            peak = float(np.nanmax(d["put_sp"][binding] * 10.0))
            if peak < AGGRESSIVE_PEAK_MIN_HPA:
                dropped.append((revision, tag,
                                f"boost cap peaks {peak:.0f} hPa — not the "
                                "aggressive curve"))
                continue
            offset = _offset(d, loaded_mask(d))
            if revision >= FIRST_MODIFIER_REVISION:
                if not np.isfinite(offset):
                    dropped.append((revision, tag,
                                    "modifier era, offset unreadable"))
                    continue
                if offset > BASE_TIMING_OFFSET_MAX_DEG:
                    dropped.append((revision, tag,
                                    f"carries a {offset:+.2f} CRK ignition "
                                    "offset — an octane slot, not base timing"))
                    continue
            kept.append(Session(revision, tag, FUEL.get(revision, "plain 92"),
                                d, peak, offset))
    return kept, dropped


def events(sessions: list[Session]) -> list[dict]:
    """R19's knock events over the given sessions."""
    out: list[dict] = []
    for s in sessions:
        loaded = loaded_mask(s.data)
        air = s.data["airmass"] * 1000.0
        for key in KNOCK_KEYS:
            retard = s.data[key]
            for run in contiguous_runs(loaded & (retard <= KNOCK_EVENT_DEG),
                                       KNOCK_GAP_ROWS):
                onset = int(run[0])
                worst = int(run[int(np.argmin(retard[run]))])
                after = np.flatnonzero(retard[worst:] >= RECOVERED_DEG)
                out.append({
                    "revision": s.revision, "tag": s.tag, "fuel": s.fuel,
                    "cylinder": int(key[-1]),
                    "onset_rpm": float(s.data["rpm"][onset]),
                    "worst_rpm": float(s.data["rpm"][worst]),
                    "worst_deg": float(retard[worst]),
                    "airmass": float(air[worst]),
                    "lambda_sp": float(s.data["lambda_sp"][worst])
                                 if "lambda_sp" in s.data else float("nan"),
                    "iat": float(s.data["iat"][worst]) if "iat" in s.data
                           else float("nan"),
                    "carry_s": float(((worst + after[0]) if after.size
                                      else retard.size - 1) - onset) * SAMPLE_S,
                })
    return sorted(out, key=lambda e: e["worst_rpm"])


def exposure(sessions: list[Session], lo: float, hi: float,
             air: tuple[float, float] | None = None) -> float:
    """Loaded seconds inside an rpm band, optionally inside an airmass bin."""
    total = 0.0
    for s in sessions:
        m = loaded_mask(s.data) & (s.data["rpm"] >= lo) & (s.data["rpm"] < hi)
        if air is not None:
            mg = s.data["airmass"] * 1000.0
            m &= (mg >= air[0]) & (mg < air[1])
        total += float(m.sum()) * SAMPLE_S
    return total


def channel_profile(sessions: list[Session], key: str,
                    bands=BANDS) -> dict[tuple[int, int], tuple[float, float, int]]:
    """Median, 95th percentile and sample count of a channel per rpm band."""
    out = {}
    for lo, hi in bands:
        pool = []
        for s in sessions:
            if key not in s.data:
                continue
            m = loaded_mask(s.data) & (s.data["rpm"] >= lo) & (s.data["rpm"] < hi)
            pool.append(s.data[key][m])
        vals = np.concatenate(pool) if pool else np.empty(0)
        vals = vals[np.isfinite(vals)]
        out[(lo, hi)] = ((float(np.median(vals)), float(np.percentile(vals, 95)),
                          int(vals.size)) if vals.size else
                         (float("nan"), float("nan"), 0))
    return out
