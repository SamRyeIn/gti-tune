#!/usr/bin/env python3
"""Render every beat, encode to H.264, then prove the result matches the spec.

    python3 Docs/promo/build_promo.py              # full build + QA
    python3 Docs/promo/build_promo.py --frames     # also keep frames/ as PNGs
    python3 Docs/promo/build_promo.py --only logs  # one beat, for iterating

Frames are piped straight into ffmpeg as raw RGB by default — at PNG speed the
encode step alone costs about half an hour. `--frames` swaps in the numbered-PNG
sink when you want to open individual frames.

The build fails loud rather than shipping something wrong: a missing asset, a
beat that renders the wrong number of frames, an ffmpeg failure, or a probe that
disagrees with the spec all stop it.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import compositor as C
import config
import music
import scene_surface
import scenes

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

DURATION_MIN_S, DURATION_MAX_S = 85.0, 95.0


def beat_renderer(beat: config.Beat):
    """The function that owns a beat — beat 5 lives in its own module."""
    return scene_surface.render_beat if beat.id == "surface" else scenes.render_beat


# ------------------------------------------------------------------- encoding

def _ffmpeg_cmd(out_path: Path, source: str, audio: Path | None = None) -> list[str]:
    """`source` is 'pipe' (raw RGB on stdin) or 'png' (numbered files).

    `audio` is the generated music bed (`music.py`), or None for a silent cut —
    a single-beat preview, where a bed cut for the whole timeline would start in
    the wrong place.
    """
    if source == "pipe":
        inputs = ["-f", "rawvideo", "-pix_fmt", "rgb24",
                  "-s", f"{config.WIDTH}x{config.HEIGHT}",
                  "-framerate", str(config.FPS), "-i", "-"]
    else:
        inputs = ["-framerate", str(config.FPS),
                  "-i", str(config.FRAME_DIR / "frame_%05d.png")]
    if audio is None:
        track = ["-an"]                         # no audio stream at all
    else:
        track = ["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
                 "-c:a", "aac", "-b:a", "192k", "-shortest"]
    return [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        *inputs,
        *track,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out_path),
    ]


def render(beats: tuple[config.Beat, ...], out_path: Path, keep_frames: bool,
           audio: Path | None = None) -> int:
    """Render `beats` into `out_path`; returns the number of frames written."""
    if FFMPEG is None:
        raise SystemExit("ffmpeg not found on PATH — install it (brew install ffmpeg)")

    if keep_frames:
        if config.FRAME_DIR.exists():
            shutil.rmtree(config.FRAME_DIR)     # stale frames must not leak in
        config.FRAME_DIR.mkdir(parents=True)
        sink = C.PngSink(config.FRAME_DIR)
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
        beat_renderer(beat)(writer, beat)
        print(f"  {beat.id:<8} {beat.n_frames:4d} frames  {time.time() - t0:6.1f} s", flush=True)
    writer.close()

    if proc is not None:
        if proc.wait() != 0:
            raise SystemExit(f"ffmpeg failed with exit code {proc.returncode}")
    else:
        subprocess.run(_ffmpeg_cmd(out_path, "png", audio), check=True)

    print(f"  rendered {writer.count} frames in {time.time() - started:.1f} s")
    return writer.count


# ------------------------------------------------------------------------- QA

def probe(path: Path) -> dict:
    if FFPROBE is None:
        raise SystemExit("ffprobe not found on PATH")
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def qa(path: Path, expected_frames: int, full_build: bool,
       expect_audio: bool = False) -> list[str]:
    """Check the encoded file against the spec. Returns a list of failures."""
    info = probe(path)
    streams = info["streams"]
    fmt = info["format"]
    problems: list[str] = []

    want = 2 if expect_audio else 1
    if len(streams) != want:
        problems.append(f"expected {want} stream(s), found {len(streams)}: "
                        + ", ".join(s["codec_type"] for s in streams))
    audio = next((s for s in streams if s["codec_type"] == "audio"), None)
    if expect_audio and audio is None:
        problems.append("no audio stream — the music bed did not make it in")
    elif expect_audio and audio["codec_name"] != "aac":
        problems.append(f"audio is {audio['codec_name']}, expected aac")
    elif not expect_audio and audio is not None:
        problems.append(f"an audio stream ({audio['codec_name']}) was encoded")
    video = next((s for s in streams if s["codec_type"] == "video"), None)
    if video is None:
        problems.append("no video stream")
        return problems

    if video["codec_name"] != "h264":
        problems.append(f"codec is {video['codec_name']}, expected h264")
    if video.get("pix_fmt") != "yuv420p":
        problems.append(f"pix_fmt is {video.get('pix_fmt')}, expected yuv420p")
    if (video["width"], video["height"]) != (config.WIDTH, config.HEIGHT):
        problems.append(f"frame is {video['width']}x{video['height']}, "
                        f"expected {config.WIDTH}x{config.HEIGHT}")

    frames = int(video.get("nb_frames", 0))
    if frames and frames != expected_frames:
        problems.append(f"encoded {frames} frames, expected {expected_frames}")

    duration = float(fmt["duration"])
    if full_build and not DURATION_MIN_S <= duration <= DURATION_MAX_S:
        problems.append(f"duration {duration:.1f}s is outside "
                        f"{DURATION_MIN_S:.0f}-{DURATION_MAX_S:.0f}s")

    print(f"  {video['width']}x{video['height']}  {video['codec_name']}/"
          f"{video['pix_fmt']}  {duration:.1f} s  {frames or expected_frames} frames  "
          f"{len(streams)} stream(s), "
          f"{'aac music bed' if audio else 'no audio'}  "
          f"{int(fmt['size']) / 1e6:.1f} MB")
    return problems


# ---------------------------------------------------------------------- driver

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--frames", action="store_true",
                    help="write numbered PNGs into frames/ instead of piping to ffmpeg")
    ap.add_argument("--only", metavar="BEAT", choices=list(config.BEATS),
                    help="render a single beat to preview_<beat>.mp4")
    ap.add_argument("--no-music", action="store_true",
                    help="encode silent, for dropping your own track on instead")
    args = ap.parse_args(argv)

    missing = [k for k, p in config.PREPARED.items() if not p.is_file()]
    if missing:
        raise SystemExit(
            "prepared assets missing: " + ", ".join(missing)
            + "\nRun `python3 Docs/promo/capture_assets.py` first."
        )

    if args.only:
        beats = (config.BEATS[args.only],)
        out_path = config.PROMO_DIR / f"preview_{args.only}.mp4"
    else:
        beats = config.TIMELINE
        out_path = config.OUT_MP4

    # A single-beat preview stays silent: the bed is cut to the whole timeline,
    # so a slice of it would start in the wrong bar.
    bed_path = None
    if not (args.only or args.no_music):
        bed_path = music.write_wav(music.bed_for(config.TIMELINE),
                                   config.PROMO_DIR / "bed.wav")
        print(f"  music bed: {bed_path.name}", flush=True)

    print(f"building {out_path.name}: {len(beats)} beat(s), "
          f"{sum(b.n_frames for b in beats)} frames @ {config.FPS} fps", flush=True)
    count = render(beats, out_path, keep_frames=args.frames, audio=bed_path)

    expected = sum(b.n_frames for b in beats)
    if count != expected:
        raise SystemExit(f"wrote {count} frames, expected {expected}")

    print("QA:")
    problems = qa(out_path, expected, full_build=not args.only,
                  expect_audio=bed_path is not None)
    print(f"  hero surface path: {scene_surface.SURFACE_PATH}")
    if problems:
        for p in problems:
            print(f"  FAIL  {p}")
        return 1

    print(f"\n{out_path}")
    if not args.only:
        print("Ready for Sam to review."
              + ("" if bed_path else " Silent — drop your own track on."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
