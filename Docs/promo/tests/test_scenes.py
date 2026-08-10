"""U4 — the seven scripted beats (title, code, verify, report, flash, logs, outro)."""

import re

import pytest

import compositor as C
import config
import scenes


@pytest.fixture(scope="session", autouse=True)
def assets_present():
    missing = [k for k, p in config.PREPARED.items() if not p.is_file()]
    if missing:
        pytest.skip(f"run `python3 Docs/promo/capture_assets.py` first (missing: {missing})")


def _drawn(beat_id: str, at: float) -> list[str]:
    beat = config.BEATS[beat_id]
    i = round(C.clamp01(at) * (beat.n_frames - 1))
    return scenes.FRAME_BUILDERS[beat_id](i, beat.n_frames).drawn_text


# ------------------------------------------------------------------ structure

@pytest.mark.parametrize("beat_id", list(scenes.FRAME_BUILDERS))
def test_every_scripted_beat_renders_canvas_sized_frames(beat_id):
    beat = config.BEATS[beat_id]
    for i in (0, beat.n_frames // 2, beat.n_frames - 1):
        f = scenes.FRAME_BUILDERS[beat_id](i, beat.n_frames)
        assert f.img.size == (config.WIDTH, config.HEIGHT)
        assert f.img.mode == "RGB"


def test_all_seven_scripted_beats_are_covered():
    scripted = set(config.BEATS) - {"surface"}
    assert set(scenes.FRAME_BUILDERS) == scripted


def test_render_beat_fills_exactly_its_frame_window(tmp_path):
    # A stand-in for the real `flash` beat, shortened so the test stays quick.
    beat = config.Beat("flash", 56.0, 56.0 + 12 / config.FPS, "You flash it")
    writer = C.FrameWriter(tmp_path)
    writer.index = beat.start_frame           # as the orchestrator would leave it
    scenes.render_beat(writer, beat)
    assert writer.count == config.frames_for(beat) == beat.n_frames
    names = sorted(p.name for p in tmp_path.glob("frame_*.png"))
    assert names[0] == f"frame_{beat.start_frame:05d}.png"
    assert names[-1] == f"frame_{beat.end_frame - 1:05d}.png"


def test_scene_frames_are_deterministic():
    a = scenes.title_frame(42, 180).img.tobytes()
    b = scenes.title_frame(42, 180).img.tobytes()
    assert a == b


def test_frames_actually_change_over_a_beat():
    beat = config.BEATS["logs"]
    seen = {scenes.logs_frame(i, beat.n_frames).img.tobytes()
            for i in (0, beat.n_frames // 3, 2 * beat.n_frames // 3, beat.n_frames - 1)}
    assert len(seen) == 4


# ------------------------------------------------------------- report pan (4)

def test_report_pan_starts_at_the_top_and_ends_at_the_bottom():
    img = C.load(config.PREPARED["report"])
    view_h = (scenes.REPORT_CARD[3] - scenes.REPORT_CARD[1]) * (
        img.width / (scenes.REPORT_CARD[2] - scenes.REPORT_CARD[0]))
    first = scenes._report_pan_rect(0.0, img.width, img.height, view_h)
    last = scenes._report_pan_rect(1.0, img.width, img.height, view_h)
    assert first[1] == 0.0
    assert last[3] == pytest.approx(img.height)
    assert last[1] > first[1]


def test_report_pan_holds_on_each_stop():
    img = C.load(config.PREPARED["report"])
    view_h = 1000.0
    a = scenes._report_pan_rect(0.36, img.width, img.height, view_h)
    b = scenes._report_pan_rect(0.46, img.width, img.height, view_h)
    assert a[1] == pytest.approx(b[1])        # the pan pauses to be readable


def test_report_beat_traverses_the_document():
    beat = config.BEATS["report"]
    first = scenes.report_frame(0, beat.n_frames).img.tobytes()
    last = scenes.report_frame(beat.n_frames - 1, beat.n_frames).img.tobytes()
    assert first != last


# ------------------------------------------------------------------ the copy

def test_flash_beat_states_the_human_flash_boundary():
    """AE6 — the library never flashes, and the video says so out loud."""
    drawn = " ".join(_drawn("flash", 0.95))
    assert scenes.FLASH_HEADLINE in drawn
    assert "never" in drawn.lower() and "flash" in drawn.lower()
    assert "SimosTools" in drawn


def test_code_beat_names_the_table_by_id_and_description():
    drawn = " ".join(_drawn("code", 0.95))
    assert "C_M_AIR_CYL_SP_MAX" in drawn
    assert "Maximum allowed airmass setpoint" in drawn


def test_code_beat_gets_the_kg_per_stroke_store_right():
    """The one table where writing the physical number would be catastrophic."""
    drawn = " ".join(_drawn("code", 0.95))
    assert "0.002" in drawn
    assert re.search(r"2000\s*mg/stk", drawn)


def test_outro_closes_the_loop_with_all_five_steps():
    drawn = " ".join(_drawn("outro", 0.95))
    for node in scenes.LOOP_NODES:
        assert node in drawn
    assert scenes.OUTRO_TAGLINE in drawn
    assert "starting point, not a finished calibration" in drawn


def test_title_beat_carries_the_tagline_and_the_car():
    drawn = " ".join(_drawn("title", 1.0))
    assert scenes.TAGLINE in drawn
    assert "5G0906259L_0002" in drawn


# ---------------------------------------------------------------- honesty

def test_verification_rows_come_from_the_real_report():
    md = config.resolve_assets()["report_md"].read_text()
    rows = scenes.verification_facts()
    assert len(rows) == 4
    for label, state, detail in rows:
        assert state in {"CLEAN", "PASS"}
        assert detail in md, f"{label} detail is not verbatim from report.md"


def test_verification_parse_fails_loud_when_the_report_changes(monkeypatch):
    monkeypatch.setattr(scenes, "_read", lambda key: "nothing like a report")
    scenes.verification_facts.cache_clear()
    try:
        with pytest.raises(SystemExit, match="could not read"):
            scenes.verification_facts()
    finally:
        scenes.verification_facts.cache_clear()


def test_journal_counts_come_from_the_real_report():
    md = config.resolve_assets()["report_md"].read_text()
    for part in scenes.journal_counts().split(" · "):
        count, word = part.split(" ")
        assert f"**{word}**: {count}" in md


def test_every_figure_quoted_in_a_log_caption_is_in_the_analysis_output():
    findings = config.resolve_assets()["findings_md"].read_text()
    for key, heading, caption, _keep in scenes.LOG_CARDS:
        for figure in re.findall(r"[+-]?\d+\.\d+%?|\b\d{3,}\b", caption):
            assert figure in findings, (
                f"{key} caption quotes {figure}, which is not in analysis_findings.md"
            )


def test_log_cards_point_at_real_prepared_plots():
    for key, _heading, _caption, keep in scenes.LOG_CARDS:
        assert config.PREPARED[key].is_file()
        assert 0.0 < keep <= 1.0
