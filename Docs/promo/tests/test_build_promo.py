"""U6 — orchestration, the ffmpeg invocation, and the QA gate."""

import json

import pytest

import build_promo as B
import config
import scene_surface
import scenes


def test_every_beat_has_a_renderer():
    for beat in config.TIMELINE:
        assert B.beat_renderer(beat) in (scenes.render_beat, scene_surface.render_beat)


def test_the_hero_beat_is_the_only_one_owned_by_scene_surface():
    owned = [b.id for b in config.TIMELINE
             if B.beat_renderer(b) is scene_surface.render_beat]
    assert owned == ["surface"]


def test_beats_tile_the_timeline_without_gaps_or_overlaps():
    expected = sum(b.n_frames for b in config.TIMELINE)
    assert expected == config.total_frames()
    assert config.TIMELINE[0].start_frame == 0
    for prev, nxt in zip(config.TIMELINE, config.TIMELINE[1:]):
        assert prev.end_frame == nxt.start_frame


# ------------------------------------------------------------ ffmpeg command

def test_pipe_command_declares_raw_rgb_at_canvas_size_and_no_audio(tmp_path):
    cmd = B._ffmpeg_cmd(tmp_path / "o.mp4", "pipe")
    assert "-an" in cmd, "an audio stream must never be encoded"
    assert f"{config.WIDTH}x{config.HEIGHT}" in cmd
    assert cmd[cmd.index("-pix_fmt") + 1] == "rgb24"          # input
    assert cmd[-6:-1] == ["libx264", "-preset", "medium", "-crf", "18"] or "libx264" in cmd
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "yuv420p" in cmd
    assert str(config.FPS) in cmd


def test_png_command_reads_the_numbered_frames(tmp_path):
    cmd = B._ffmpeg_cmd(tmp_path / "o.mp4", "png")
    assert str(config.FRAME_DIR / "frame_%05d.png") in cmd
    assert "-an" in cmd


# -------------------------------------------------------------------- QA gate

def _fake_probe(monkeypatch, *, streams=None, duration="90.0", frames="2700"):
    video = {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
             "width": config.WIDTH, "height": config.HEIGHT, "nb_frames": frames}
    info = {"streams": streams if streams is not None else [video],
            "format": {"duration": duration, "size": "12000000"}}
    monkeypatch.setattr(B, "probe", lambda path: json.loads(json.dumps(info)))


def test_qa_passes_a_conforming_file(monkeypatch, tmp_path):
    _fake_probe(monkeypatch)
    assert B.qa(tmp_path / "o.mp4", 2700, full_build=True) == []


def test_qa_rejects_an_audio_stream(monkeypatch, tmp_path):
    video = {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
             "width": config.WIDTH, "height": config.HEIGHT, "nb_frames": "2700"}
    _fake_probe(monkeypatch, streams=[video, {"codec_type": "audio", "codec_name": "aac"}])
    problems = B.qa(tmp_path / "o.mp4", 2700, full_build=True)
    assert any("expected 1 stream" in p for p in problems)


def test_qa_rejects_a_wrong_frame_count(monkeypatch, tmp_path):
    _fake_probe(monkeypatch, frames="2000")
    assert any("expected 2700" in p for p in B.qa(tmp_path / "o.mp4", 2700, full_build=True))


def test_qa_rejects_an_out_of_spec_duration(monkeypatch, tmp_path):
    _fake_probe(monkeypatch, duration="42.0")
    assert any("outside" in p for p in B.qa(tmp_path / "o.mp4", 2700, full_build=True))


def test_qa_ignores_duration_for_a_single_beat_preview(monkeypatch, tmp_path):
    _fake_probe(monkeypatch, duration="6.0", frames="180")
    assert B.qa(tmp_path / "o.mp4", 180, full_build=False) == []


def test_qa_rejects_the_wrong_frame_size(monkeypatch, tmp_path):
    video = {"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p",
             "width": 1280, "height": 720, "nb_frames": "2700"}
    _fake_probe(monkeypatch, streams=[video])
    assert any("1280x720" in p for p in B.qa(tmp_path / "o.mp4", 2700, full_build=True))


# ------------------------------------------------------------- missing assets

def test_build_refuses_to_run_without_the_prepared_assets(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "PREPARED", {"report": tmp_path / "nope.png"})
    with pytest.raises(SystemExit, match="capture_assets"):
        B.main([])


# ---------------------------------------------------------- the built artefact

@pytest.mark.skipif(not config.OUT_MP4.is_file(),
                    reason="run `python3 Docs/promo/build_promo.py` first")
def test_the_built_promo_matches_the_spec():
    assert B.qa(config.OUT_MP4, config.total_frames(), full_build=True) == []
