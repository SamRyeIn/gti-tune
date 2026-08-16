#!/usr/bin/env python3
"""Render and encode the short hook cut (31 s, opening and closing on the mark).

    python3 Docs/promo/build_hook.py               # full build + QA
    python3 Docs/promo/build_hook.py --only dyno   # one beat, for iterating
    python3 Docs/promo/build_hook.py --frames      # keep frames_hook/ as PNGs

Same engine as the 90-second deep dive — `compositor` and `config` — pointed at
`config.HOOK_TIMELINE` and `hook_scenes`. Encoding, probing, and the QA gate are shared with
`build_promo`, so both cuts are checked the same way.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

import build_promo
import compositor as C
import config
import hook_scenes
import music
from hook_data import hook_data

FRAME_DIR = config.PROMO_DIR / "frames_hook"

# Derived from the timeline rather than hard-coded, so editing a beat's length
# does not leave a stale gate behind. The tolerance catches an encode that
# silently dropped or duplicated frames, not a deliberate re-cut.
_HOOK_S = config.hook_total_frames() / config.FPS
DURATION_MIN_S, DURATION_MAX_S = _HOOK_S - 0.5, _HOOK_S + 0.5


def _ffmpeg_cmd(out_path: Path, source: str, audio: Path | None = None) -> list[str]:
    if source == "pipe":
        inputs = ["-f", "rawvideo", "-pix_fmt", "rgb24",
                  "-s", f"{config.WIDTH}x{config.HEIGHT}",
                  "-framerate", str(config.FPS), "-i", "-"]
    else:
        inputs = ["-framerate", str(config.FPS),
                  "-i", str(FRAME_DIR / "frame_%05d.png")]
    if audio is None:
        track = ["-an"]                         # no audio stream at all
    else:
        track = ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:a", "aac", "-b:a", "192k", "-shortest"]
    return [
        build_promo.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *inputs,
        *track,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]


def render(beats: tuple[config.Beat, ...], out_path: Path, keep_frames: bool,
           audio: Path | None = None) -> int:
    if build_promo.FFMPEG is None:
        raise SystemExit("ffmpeg not found on PATH — install it (brew install ffmpeg)")

    if keep_frames:
        if FRAME_DIR.exists():
            shutil.rmtree(FRAME_DIR)            # stale frames must not leak in
        FRAME_DIR.mkdir(parents=True)
        sink = C.PngSink(FRAME_DIR)
        proc = None
    else:
        proc = subprocess.Popen(_ffmpeg_cmd(out_path, "pipe", audio),
                                stdin=subprocess.PIPE)
        sink = C.RawPipeSink(proc.stdin)

    writer = C.FrameWriter(sink)
    writer.index = beats[0].start_frame
    started = time.time()
    for beat in beats:
        t0 = time.time()
        hook_scenes.render_beat(writer, beat)
        print(f"  {beat.id:<6} {beat.n_frames:4d} frames  {time.time() - t0:6.1f} s",
              flush=True)
    writer.close()

    if proc is not None:
        if proc.wait() != 0:
            raise SystemExit(f"ffmpeg failed with exit code {proc.returncode}")
    else:
        subprocess.run(_ffmpeg_cmd(out_path, "png", audio), check=True)

    print(f"  rendered {writer.count} frames in {time.time() - started:.1f} s")
    return writer.count


def qa(path: Path, expected_frames: int, full_build: bool,
       expect_audio: bool = False) -> list[str]:
    """Same checks as the long cut, against the hook's own duration window."""
    lo, hi = build_promo.DURATION_MIN_S, build_promo.DURATION_MAX_S
    build_promo.DURATION_MIN_S, build_promo.DURATION_MAX_S = DURATION_MIN_S, DURATION_MAX_S
    try:
        return build_promo.qa(path, expected_frames, full_build, expect_audio)
    finally:
        build_promo.DURATION_MIN_S, build_promo.DURATION_MAX_S = lo, hi


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frames", action="store_true",
                    help="write numbered PNGs into frames_hook/ instead of piping")
    ap.add_argument("--only", metavar="BEAT", choices=list(config.HOOK_BEATS),
                    help="render a single beat to preview_hook_<beat>.mp4")
    ap.add_argument("--no-music", action="store_true",
                    help="encode silent, for dropping your own track on instead")
    args = ap.parse_args(argv)

    if args.only:
        beats = (config.HOOK_BEATS[args.only],)
        out_path = config.PROMO_DIR / f"preview_hook_{args.only}.mp4"
    else:
        beats = config.HOOK_TIMELINE
        out_path = config.OUT_HOOK_MP4

    d = hook_data()
    print(f"building {out_path.name}: {len(beats)} beat(s), "
          f"{sum(b.n_frames for b in beats)} frames @ {config.FPS} fps")
    print(f"  headline: {d.headline.rev} — {d.headline.hp:.0f} hp / "
          f"{d.headline.tq:.0f} Nm / {d.headline.boost:.1f} psi  "
          f"(+{d.hp_gain:.0f} hp over {d.baseline.rev})", flush=True)

    # Silent for a single-beat preview: the bed is cut to the whole timeline, so
    # a slice of it would start in the wrong bar.
    bed_path = None
    if not (args.only or args.no_music):
        bed_path = music.write_wav(music.bed_for(config.HOOK_TIMELINE),
                                   config.PROMO_DIR / "bed_hook.wav")
        print(f"  music bed: {bed_path.name}, drops at "
              f"{config.HOOK_TIMELINE[1].start_s:.0f} s with the first data beat",
              flush=True)

    count = render(beats, out_path, keep_frames=args.frames, audio=bed_path)
    expected = sum(b.n_frames for b in beats)
    if count != expected:
        raise SystemExit(f"wrote {count} frames, expected {expected}")

    print("QA:")
    problems = qa(out_path, expected, full_build=not args.only,
                  expect_audio=bed_path is not None)
    for x in d.excluded:
        print(f"  excluded {x['rev']}: {x['reason']}")
    for rev in d.boost_missing:
        print(f"  {rev} charted but not in the boost beat: no boost channel logged")
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    print(f"\n{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
