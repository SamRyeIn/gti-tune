#!/usr/bin/env python3
"""Render and encode the 20-second hook cut.

    python3 Docs/promo/build_hook.py               # full build + QA
    python3 Docs/promo/build_hook.py --only dyno   # one beat, for iterating
    python3 Docs/promo/build_hook.py --frames      # keep frames_hook/ as PNGs

Same engine as the 90-second deep dive — `compositor`, `config`, and the real
rotating surface out of `scene_surface` — pointed at `config.HOOK_TIMELINE` and
`hook_scenes`. Encoding, probing, and the QA gate are shared with
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
import scene_surface
from hook_data import hook_data

FRAME_DIR = config.PROMO_DIR / "frames_hook"

DURATION_MIN_S, DURATION_MAX_S = 18.0, 22.0


def _ffmpeg_cmd(out_path: Path, source: str) -> list[str]:
    if source == "pipe":
        inputs = ["-f", "rawvideo", "-pix_fmt", "rgb24",
                  "-s", f"{config.WIDTH}x{config.HEIGHT}",
                  "-framerate", str(config.FPS), "-i", "-"]
    else:
        inputs = ["-framerate", str(config.FPS),
                  "-i", str(FRAME_DIR / "frame_%05d.png")]
    return [
        build_promo.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *inputs,
        "-an",                                  # no audio stream at all
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]


def render(beats: tuple[config.Beat, ...], out_path: Path, keep_frames: bool) -> int:
    if build_promo.FFMPEG is None:
        raise SystemExit("ffmpeg not found on PATH — install it (brew install ffmpeg)")

    if keep_frames:
        if FRAME_DIR.exists():
            shutil.rmtree(FRAME_DIR)            # stale frames must not leak in
        FRAME_DIR.mkdir(parents=True)
        sink = C.PngSink(FRAME_DIR)
        proc = None
    else:
        proc = subprocess.Popen(_ffmpeg_cmd(out_path, "pipe"), stdin=subprocess.PIPE)
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
        subprocess.run(_ffmpeg_cmd(out_path, "png"), check=True)

    print(f"  rendered {writer.count} frames in {time.time() - started:.1f} s")
    return writer.count


def qa(path: Path, expected_frames: int, full_build: bool) -> list[str]:
    """Same checks as the long cut, against the hook's own duration window."""
    lo, hi = build_promo.DURATION_MIN_S, build_promo.DURATION_MAX_S
    build_promo.DURATION_MIN_S, build_promo.DURATION_MAX_S = DURATION_MIN_S, DURATION_MAX_S
    try:
        return build_promo.qa(path, expected_frames, full_build)
    finally:
        build_promo.DURATION_MIN_S, build_promo.DURATION_MAX_S = lo, hi


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frames", action="store_true",
                    help="write numbered PNGs into frames_hook/ instead of piping")
    ap.add_argument("--only", metavar="BEAT", choices=list(config.HOOK_BEATS),
                    help="render a single beat to preview_hook_<beat>.mp4")
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

    count = render(beats, out_path, keep_frames=args.frames)
    expected = sum(b.n_frames for b in beats)
    if count != expected:
        raise SystemExit(f"wrote {count} frames, expected {expected}")

    print("QA:")
    problems = qa(out_path, expected, full_build=not args.only)
    if any(b.id == "map" for b in beats):
        print(f"  hero surface path: {scene_surface.SURFACE_PATH}")
    for x in d.excluded:
        print(f"  excluded {x['rev']}: {x['reason']}")
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    print(f"\n{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
