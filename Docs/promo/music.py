#!/usr/bin/env python3
"""The music bed — synthesised here, so it is ours and free to use anywhere.

A downloaded "free" track carries a licence you have to keep track of, an
attribution line, and a takedown risk on a video meant to be shared. This is
generated from numpy on every build instead: original by construction, no
attribution, no third-party rights, no asset to lose. Same deal as the rest of
the promo — nothing on screen or in the mix comes from somewhere we cannot point
at.

The style is the low-key dark loop those car edits run under: A minor, 96 BPM,
sub bass on the downbeats, a slow detuned pad, quiet offbeat hats, and a kick
that ducks the pad under it.

**It is cut to the video.** A bar is 2.5 s and the percussion starts at 3.0 s —
the frame the hook's first data beat appears — so every later cut in
`config.HOOK_TIMELINE` (8, 13, 18, 23, 28 s) lands on a two-bar downbeat, and the
chord changes with the beat on screen. Re-cut the timeline and `bed_for()`
re-derives the arrangement from it rather than drifting out of sync.

    python3 Docs/promo/music.py out.wav              # a bed for the hook
    python3 Docs/promo/music.py out.wav --seconds 90 # any length
    python3 Docs/promo/music.py --mux video.mp4      # add a bed to an existing cut
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

import config

SR = 48_000
BPM = 96.0
BEAT_S = 60.0 / BPM              # 0.625 s
BAR_S = BEAT_S * 4               # 2.5 s

#: When the drums come in — the frame the first data beat of the hook appears.
#: Before this the pad plays alone under the wordmark.
DROP_S = 3.0

#: A minor, one chord per two bars (5 s) so each chord owns one video beat.
#: i - VI - III - VII, the progression half these edits are built on.
PROGRESSION = (
    ("Am", (220.00, 261.63, 329.63)),      # A3 C4 E4
    ("F",  (174.61, 220.00, 261.63)),      # F3 A3 C4
    ("C",  (196.00, 261.63, 329.63)),      # G3 C4 E4
    ("G",  (196.00, 246.94, 293.66)),      # G3 B3 D4
)
ROOTS = {"Am": 55.00, "F": 43.65, "C": 65.41, "G": 49.00}   # one octave down, sub

CHORD_S = BAR_S * 2

# Levels, picked so the bed sits under a viewer's attention rather than on top
# of it. Everything is summed then soft-clipped, so these are relative.
LVL_PAD, LVL_BASS, LVL_KICK, LVL_HAT = 0.16, 0.30, 0.42, 0.045
PEAK_TARGET = 0.58               # AAC overshoots on encode, and a bed under a
                                 # video should not be flirting with full scale


def _t(n: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / SR


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    """A simple attack/exponential-decay envelope, `n` samples long."""
    t = _t(n)
    a = np.clip(t / max(attack, 1e-6), 0.0, 1.0)
    return a * np.exp(-t / max(decay, 1e-6))


def _add(buf: np.ndarray, at_s: float, sig: np.ndarray) -> None:
    """Mix `sig` into `buf` at `at_s`, clipped to the buffer."""
    i = int(round(at_s * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    j = min(i + len(sig), len(buf))
    _i = max(i, 0)
    buf[_i:j] += sig[_i - i:j - i]


def _pad(freqs: tuple[float, ...], dur_s: float) -> np.ndarray:
    """A soft detuned chord: two octaves, a little chorus, slow in and out."""
    n = int(dur_s * SR)
    t = _t(n)
    out = np.zeros(n)
    for f in freqs:
        for mult, amp in ((1.0, 1.0), (2.0, 0.32), (0.5, 0.45)):
            for detune in (-2.5, 2.5):           # cents-ish, for width
                w = 2 * np.pi * f * mult * (1 + detune / 2000.0)
                # A touch of odd harmonic keeps it from being a pure sine wash.
                out += amp * (np.sin(w * t) + 0.18 * np.sin(3 * w * t))
    out /= np.abs(out).max() or 1.0
    swell = np.minimum(_t(n) / 0.9, 1.0) * np.minimum((dur_s - _t(n)) / 0.7, 1.0)
    return out * np.clip(swell, 0.0, 1.0)


def _bass(freq: float, dur_s: float) -> np.ndarray:
    n = int(dur_s * SR)
    t = _t(n)
    w = 2 * np.pi * freq
    sig = np.sin(w * t) + 0.25 * np.sin(2 * w * t)
    return sig * _env(n, 0.008, dur_s * 0.42)


def _kick(dur_s: float = 0.42) -> np.ndarray:
    n = int(dur_s * SR)
    t = _t(n)
    # Pitch drop 105 -> 45 Hz: the click of the attack, then the body.
    f = 45.0 + 60.0 * np.exp(-t / 0.028)
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase) * _env(n, 0.001, 0.115)


def _hat(rng: np.random.Generator, dur_s: float = 0.055) -> np.ndarray:
    n = int(dur_s * SR)
    noise = rng.standard_normal(n)
    # Cheap high-pass: subtract a running mean, which is what is left of a hat.
    kernel = np.ones(24) / 24
    return (noise - np.convolve(noise, kernel, mode="same")) * _env(n, 0.0005, 0.018)


def _echo(sig: np.ndarray, taps=((0.115, 0.26), (0.237, 0.15))) -> np.ndarray:
    """A poor man's reverb: two attenuated delays. Enough to give the pad space."""
    out = sig.copy()
    for delay_s, amp in taps:
        d = int(delay_s * SR)
        out[d:] += sig[:-d] * amp
    return out


def bed(duration_s: float, drop_s: float = DROP_S, seed: int = 7) -> np.ndarray:
    """A stereo bed `duration_s` long, as float in [-1, 1], shape (n, 2)."""
    rng = np.random.default_rng(seed)
    n = int(duration_s * SR)
    pad = np.zeros(n)
    rhythm = np.zeros(n)

    # Chords run the whole length, changing every CHORD_S from the drop, so the
    # pad is already playing under the opening wordmark.
    k = 0
    at = 0.0
    while at < duration_s:
        name, freqs = PROGRESSION[k % len(PROGRESSION)]
        span = min(CHORD_S, duration_s - at)
        if span > 0.2:
            _add(pad, at, _pad(freqs, span) * LVL_PAD)
            # The sub follows the chord root, on beats 1 and 3 of each bar.
            if at + span > drop_s:
                for bar in range(2):
                    for beat in (0, 2):
                        hit = at + bar * BAR_S + beat * BEAT_S
                        if hit >= drop_s and hit < duration_s - 0.1:
                            _add(rhythm, hit,
                                 _bass(ROOTS[name], BEAT_S * 1.7) * LVL_BASS)
        at += CHORD_S
        k += 1

    # Kick on 1 and 3, hats on the offbeats — sparse, so it stays background.
    beat_i = 0
    at = drop_s
    while at < duration_s - 0.1:
        if beat_i % 4 in (0, 2):
            _add(rhythm, at, _kick() * LVL_KICK)
        _add(rhythm, at + BEAT_S / 2, _hat(rng) * LVL_HAT * (1.0 if beat_i % 2 else 0.7))
        at += BEAT_S
        beat_i += 1

    pad = _echo(pad)[:n]

    # Side-chain: duck the pad under every kick. This is most of what makes a
    # bed sound produced rather than assembled.
    duck = np.ones(n)
    at = drop_s
    beat_i = 0
    while at < duration_s - 0.1:
        if beat_i % 4 in (0, 2):
            i = int(at * SR)
            m = min(int(0.30 * SR), n - i)
            if m > 0:
                duck[i:i + m] = np.minimum(duck[i:i + m], 1.0 - 0.45 * np.exp(-_t(m) / 0.085))
        at += BEAT_S
        beat_i += 1

    mono = pad * duck + rhythm
    mono = np.tanh(mono * 1.25)                  # soft clip, no hard edges

    # Fade in from silence, and out to it — the cut loops, so neither end may click.
    fade_in, fade_out = int(1.2 * SR), int(2.0 * SR)
    mono[:fade_in] *= np.linspace(0.0, 1.0, fade_in)
    mono[-fade_out:] *= np.linspace(1.0, 0.0, fade_out)

    peak = np.abs(mono).max() or 1.0
    mono *= PEAK_TARGET / peak

    # Widen: the pad's echo sits a few ms later on the right.
    right = np.concatenate([np.zeros(int(0.012 * SR)), mono])[:n]
    return np.stack([mono, 0.82 * right + 0.18 * mono], axis=1)


def bed_for(timeline: tuple[config.Beat, ...]) -> np.ndarray:
    """The bed for a cut, dropping on its second beat so the music cuts with it."""
    total = sum(b.n_frames for b in timeline) / config.FPS
    drop = timeline[1].start_s if len(timeline) > 1 else 0.0
    return bed(total, drop_s=drop)


def write_wav(samples: np.ndarray, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


def mux(video: Path, audio: Path, out: Path) -> Path:
    """Put `audio` on `video` without re-encoding a single frame."""
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(video), "-i", str(audio),
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", str(out)],
        check=True)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", nargs="?", type=Path, help="wav to write")
    ap.add_argument("--seconds", type=float, help="length (default: the hook's)")
    ap.add_argument("--mux", type=Path, metavar="MP4",
                    help="write a bed of that file's length onto it, in place")
    ap.add_argument("--drop", type=float, default=DROP_S, metavar="S",
                    help=f"when the drums come in (default {DROP_S:.0f}s — set it to "
                         "the cut's second beat so the drop lands on a cut)")
    args = ap.parse_args(argv)

    if args.mux:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(args.mux)],
            capture_output=True, text=True, check=True).stdout.strip())
        tmp_wav = args.mux.with_suffix(".bed.wav")
        tmp_mp4 = args.mux.with_suffix(".muxed.mp4")
        write_wav(bed(dur, drop_s=args.drop), tmp_wav)
        mux(args.mux, tmp_wav, tmp_mp4)
        tmp_mp4.replace(args.mux)
        tmp_wav.unlink()
        print(f"{args.mux}  ({dur:.1f} s of bed, drop at {args.drop:.1f} s)")
        return 0

    out = args.out or (config.PROMO_DIR / "bed.wav")
    seconds = args.seconds or sum(b.n_frames for b in config.HOOK_TIMELINE) / config.FPS
    write_wav(bed(seconds, drop_s=args.drop), out)
    print(f"{out}  {seconds:.1f} s  {BPM:.0f} BPM  bar {BAR_S:.2f} s  "
          f"drop {args.drop:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
