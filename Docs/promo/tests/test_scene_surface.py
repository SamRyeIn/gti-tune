"""U5 — the hero surface beat, both its rotation path and its parallax fallback."""

import numpy as np
import pytest

import compositor as C
import config
import scene_surface as S


@pytest.fixture(scope="session", autouse=True)
def assets_present():
    if not config.PREPARED["surface_hero"].is_file():
        pytest.skip("run `python3 Docs/promo/capture_assets.py` first")


@pytest.fixture
def grids():
    if not S.GRID_CACHE.is_file() and not (config.CODE_ROOT / "simoscal").is_dir():
        pytest.skip("neither the cached grids nor the simoscal library is available")
    g = S.hero_grids()
    if g is None:
        pytest.skip("rotation path unavailable on this machine")
    return g


# ------------------------------------------------------------- path selection

def test_exactly_one_path_is_taken_and_recorded(grids):
    assert S.SURFACE_PATH in {"rotation", "parallax"}
    assert (grids is not None) == (S.SURFACE_PATH == "rotation")


def test_rotation_path_is_the_one_this_repo_takes(grids):
    assert S.SURFACE_PATH == "rotation", "the real bins are here; expected true rotation"


# ------------------------------------------------------------------ real data

def test_grids_are_the_real_table_shape(grids):
    assert grids["stock"].shape == grids["tuned"].shape == (10, 16)
    assert grids["x"].shape == (16,) and grids["y"].shape == (10,)


def test_stock_and_tuned_actually_differ(grids):
    """If these matched, the hero beat would be showing a change that isn't there."""
    assert not np.array_equal(grids["stock"], grids["tuned"])


def test_delta_caption_matches_the_grids(grids):
    d = grids["tuned"] - grids["stock"]
    moved = int(np.count_nonzero(np.abs(d) > 1e-9))
    caption = S.delta_caption()
    assert f"{moved} of {d.size} cells moved" in caption
    assert f"{np.abs(d).max():+.2f}" in caption


# -------------------------------------------------------------------- motion

def test_azimuth_sweeps_monotonically_across_the_beat():
    n = config.BEATS["surface"].n_frames
    azims = [C.lerp(S.AZIM_START, S.AZIM_END, C.ease_in_out(i / (n - 1))) for i in range(n)]
    assert azims[0] == pytest.approx(S.AZIM_START)
    assert azims[-1] == pytest.approx(S.AZIM_END)
    assert all(b >= a for a, b in zip(azims, azims[1:]))
    assert azims[-1] > azims[0]


def test_rotating_the_camera_changes_the_render(grids):
    a = S.render_surface(S.AZIM_START, 1.0)
    b = S.render_surface(S.AZIM_END, 1.0)
    assert a.size == b.size == S.FIG_PX
    assert a.tobytes() != b.tobytes()


def test_morphing_stock_to_tuned_changes_the_render(grids):
    assert (S.render_surface(-140.0, 0.0).tobytes()
            != S.render_surface(-140.0, 1.0).tobytes())


def test_surface_beat_frames_are_canvas_sized_and_move(grids):
    n = config.BEATS["surface"].n_frames
    frames = [S.surface_frame(i, n) for i in (0, n // 2, n - 1)]
    for f in frames:
        assert f.img.size == (config.WIDTH, config.HEIGHT)
    assert len({f.img.tobytes() for f in frames}) == 3


# ------------------------------------------------------------------ fallback

def test_parallax_fallback_still_renders_and_moves(monkeypatch):
    monkeypatch.setattr(S, "hero_grids", lambda: None)
    n = config.BEATS["surface"].n_frames
    a = S.surface_frame(0, n)
    b = S.surface_frame(n - 1, n)
    assert a.img.size == b.img.size == (config.WIDTH, config.HEIGHT)
    assert a.img.tobytes() != b.img.tobytes()          # the push-in actually moves


def test_fallback_still_names_the_table(monkeypatch):
    monkeypatch.setattr(S, "hero_grids", lambda: None)
    n = config.BEATS["surface"].n_frames
    drawn = " ".join(S.surface_frame(n - 1, n).drawn_text)
    assert S.TABLE_ID in drawn and S.TABLE_DESC in drawn


# --------------------------------------------------------------------- naming

def test_on_frame_label_is_id_plus_plain_english(grids):
    n = config.BEATS["surface"].n_frames
    drawn = " ".join(S.surface_frame(n - 1, n).drawn_text)
    assert "IP_FAC_BPA_SP[0]" in drawn
    assert "Map for boost pressure actuator setpoint" in drawn


def test_render_beat_fills_its_window(tmp_path, grids):
    beat = config.Beat("surface", 42.0, 42.0 + 4 / config.FPS, "hero")
    writer = C.FrameWriter(tmp_path)
    writer.index = beat.start_frame
    S.render_beat(writer, beat)
    assert writer.count == beat.n_frames == 4
