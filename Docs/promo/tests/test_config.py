"""U1 — config, timeline math, and the real-asset manifest."""

import config


def test_resolved_assets_all_exist():
    assets = config.resolve_assets()
    assert assets, "manifest is empty"
    for name, path in assets.items():
        assert path.exists(), f"{name} -> {path} does not exist"


def test_asset_resolution_excludes_test_subtree():
    out_dir = config.newest_tune_out_dir()
    assert "Test" not in out_dir.parts, "picked an other-model comparison run"
    assert out_dir.name.startswith("R")
    assert (out_dir / "report.html").is_file()


def test_newest_out_dir_sorts_by_revision_number(tmp_path):
    for name in ("R9_20260101-000000", "R14_20260810-111002", "R13_20260719-213357"):
        d = tmp_path / name
        d.mkdir()
        (d / "report.html").write_text("<html></html>")
    assert config.newest_tune_out_dir(tmp_path).name.startswith("R14_")


def test_log_plots_dir_is_newest_revision():
    plots = config.newest_log_plots_dir()
    assert plots.name == "plots"
    assert plots.parent.name.startswith("BasicsGuide_R")
    assert (plots / "analysis_knock.png").is_file()


def test_timeline_is_contiguous_and_ordered():
    beats = config.TIMELINE
    assert beats[0].start_s == 0.0
    for prev, nxt in zip(beats, beats[1:]):
        assert prev.end_s == nxt.start_s, f"gap/overlap between {prev.id} and {nxt.id}"
        assert prev.end_frame == nxt.start_frame
    assert len(config.BEATS) == len(beats) == 8


def test_total_frame_count_matches_target_duration():
    assert 2550 <= config.total_frames() <= 2850
    assert 85.0 <= config.total_duration_s() <= 95.0
    assert config.total_frames() == config.TIMELINE[-1].end_frame


def test_frame_index_and_frames_for():
    assert config.frame_index(0) == 0
    assert config.frame_index(1.0) == config.FPS
    assert config.frames_for("title") == config.frames_for(config.BEATS["title"])
    assert config.frames_for("title") == 6 * config.FPS


def test_fonts_present():
    assert config.FONT_DISPLAY.is_file()
    assert config.FONT_MONO.is_file()
