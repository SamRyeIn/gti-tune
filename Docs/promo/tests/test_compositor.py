"""U3 — the frame compositor core."""

import pytest
from PIL import Image

import compositor as C
import config


# ------------------------------------------------------------------- easings

@pytest.mark.parametrize("fn", [C.linear, C.ease_in_out, C.ease_out, C.ease_in])
def test_easings_hit_their_endpoints(fn):
    assert fn(0.0) == pytest.approx(0.0, abs=1e-9)
    assert fn(1.0) == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("fn", [C.linear, C.ease_in_out, C.ease_out, C.ease_in])
def test_easings_are_monotonic_and_clamped(fn):
    vals = [fn(i / 50) for i in range(51)]
    assert all(b >= a - 1e-12 for a, b in zip(vals, vals[1:]))
    assert fn(-0.5) == 0.0 and fn(1.5) == 1.0


def test_pulse_peaks_in_the_middle():
    assert C.pulse(0.0) == pytest.approx(0.0, abs=1e-9)
    assert C.pulse(0.5) == pytest.approx(1.0)
    assert C.pulse(1.0) == pytest.approx(0.0, abs=1e-9)


def test_sub_window_ramps_between_bounds():
    assert C.sub(0.1, 0.2, 0.6) == 0.0
    assert C.sub(0.4, 0.2, 0.6) == pytest.approx(0.5)
    assert C.sub(0.9, 0.2, 0.6) == 1.0
    assert C.sub(0.5, 0.5, 0.5) == 1.0   # zero-width window is instantaneous


# --------------------------------------------------------------------- frame

def test_frame_is_canvas_sized_rgb_after_paste_and_text():
    f = C.Frame()
    f.paste(Image.new("RGB", (200, 120), (255, 0, 0)), (400, 300))
    f.text("simoscal", (100, 100), size=64)
    assert f.img.size == (config.WIDTH, config.HEIGHT)
    assert f.img.mode == "RGB"


def test_paste_respects_anchor_and_scale():
    f = C.Frame()
    box = f.paste(Image.new("RGB", (200, 100), (255, 255, 255)), (500, 400),
                  scale=2.0, anchor="topleft")
    assert box == (500, 400, 900, 600)


def test_paste_with_zero_alpha_draws_nothing():
    f = C.Frame()
    before = f.img.tobytes()
    f.paste(Image.new("RGB", (400, 400), (255, 255, 255)), (100, 100), alpha=0.0)
    assert f.img.tobytes() == before


def test_text_wraps_inside_max_width():
    f = C.Frame()
    long = "Checksum verified, read back off the saved file, and byte audited " \
           "against the previous revision before you ever plug in a cable."
    max_w = 700
    box = f.text(long, (100, 100), size=44, max_width=max_w)
    assert box[2] - box[0] <= max_w
    assert box[3] - box[1] > 44 * 1.3   # actually wrapped onto several lines


def test_text_centering_is_symmetric_about_the_anchor():
    f = C.Frame()
    box = f.text("Revise. Verify. Log. Repeat.", (f.cx, 500), size=60, align="center")
    assert abs((box[0] + box[2]) / 2 - f.cx) <= 1


def test_wrap_text_honours_explicit_newlines():
    fnt = C.font(40)
    assert C.wrap_text("a\nb", fnt, 10_000) == ["a", "b"]


# ----------------------------------------------------------------- ken burns

def _gradient(w=800, h=1600):
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(0, w, 8):
            for dx in range(8):
                px[x + dx, y] = (y % 256, (x * 3) % 256, 40)
    return img


def test_ken_burns_endpoints_match_direct_crops():
    img = _gradient()
    start = (0, 0, 800, 450)
    end = (0, 1150, 800, 1600)
    size = (config.WIDTH, config.HEIGHT)
    a = C.ken_burns(img, 0.0, start, end, size)
    b = C.ken_burns(img, 1.0, start, end, size)
    assert a.size == size and b.size == size
    assert a.tobytes() == img.resize(size, Image.LANCZOS, box=start).tobytes()
    assert b.tobytes() == img.resize(size, Image.LANCZOS, box=end).tobytes()
    assert a.tobytes() != b.tobytes()


def test_ken_burns_travels_monotonically():
    img = _gradient()
    start, end = (0, 0, 800, 450), (0, 1150, 800, 1600)
    seen = [C.ken_burns(img, t / 10, start, end, (192, 108)).tobytes() for t in range(11)]
    assert len(set(seen)) == 11    # every step is a different view


# --------------------------------------------------------------- transitions

def test_fade_blends_between_two_images():
    a = Image.new("RGB", (10, 10), (0, 0, 0))
    b = Image.new("RGB", (10, 10), (255, 255, 255))
    assert C.fade(a, b, 0.0).getpixel((0, 0)) == (0, 0, 0)
    assert C.fade(a, b, 1.0).getpixel((0, 0)) == (255, 255, 255)
    mid = C.fade(a, b, 0.5).getpixel((0, 0))[0]
    assert 120 <= mid <= 135


def test_wipe_reveals_from_the_named_edge():
    a = Image.new("RGB", (100, 50), (0, 0, 0))
    b = Image.new("RGB", (100, 50), (255, 255, 255))
    out = C.wipe(a, b, 0.5, "left")
    assert out.getpixel((10, 25)) == (255, 255, 255)
    assert out.getpixel((90, 25)) == (0, 0, 0)
    assert C.wipe(a, b, 0.0, "left").getpixel((10, 25)) == (0, 0, 0)
    assert C.wipe(a, b, 1.0, "left").getpixel((90, 25)) == (255, 255, 255)


def test_slide_offset_lands_at_zero():
    assert C.slide_offset(1.0, "left", 400) == (0.0, 0.0)
    assert C.slide_offset(0.0, "left", 400) == (-400.0, 0.0)
    assert C.slide_offset(0.0, "down", 400) == (0.0, 400.0)


def test_fit_scales_into_the_box():
    img = Image.new("RGB", (1600, 800))
    out = C.fit(img, max_w=800, max_h=800)
    assert out.size == (800, 400)


# --------------------------------------------------------------- frame writer

def test_frame_writer_numbers_frames_and_enforces_beat_windows(tmp_path):
    beat = config.Beat("stub", 0.0, 6 / config.FPS, "short stand-in beat")
    w = C.FrameWriter(tmp_path)
    w.begin(beat)
    for _ in range(beat.n_frames):
        w.write(C.Frame())
    w.end(beat)
    written = sorted(tmp_path.glob("frame_*.png"))
    assert len(written) == beat.n_frames == 6
    assert written[0].name == "frame_00000.png"
    assert written[-1].name == "frame_00005.png"
    assert config.frames_for("title") == config.BEATS["title"].n_frames


def test_raw_pipe_sink_emits_exactly_one_frame_of_rgb_bytes():
    class Buf:
        def __init__(self):
            self.chunks = []

        def write(self, b):
            self.chunks.append(b)

        def close(self):
            self.closed = True

    buf = Buf()
    w = C.FrameWriter(C.RawPipeSink(buf))
    w.write(C.Frame())
    assert len(buf.chunks) == 1
    assert len(buf.chunks[0]) == config.WIDTH * config.HEIGHT * 3


def test_frame_writer_rejects_a_short_beat(tmp_path):
    beat = config.BEATS["title"]
    w = C.FrameWriter(tmp_path)
    w.begin(beat)
    w.write(C.Frame())
    with pytest.raises(AssertionError, match="expected"):
        w.end(beat)


def test_frame_writer_rejects_writing_past_the_window(tmp_path):
    beat = config.Beat("tiny", 0.0, 2 / config.FPS, "t")
    w = C.FrameWriter(tmp_path)
    w.begin(beat)
    w.write(C.Frame())
    w.write(C.Frame())
    with pytest.raises(AssertionError, match="past its window"):
        w.write(C.Frame())


def test_frame_writer_rejects_a_beat_starting_at_the_wrong_index(tmp_path):
    w = C.FrameWriter(tmp_path)
    with pytest.raises(AssertionError, match="gap/overlap"):
        w.begin(config.BEATS["code"])   # starts at 180, nothing written yet


def test_frame_writer_rejects_a_wrong_sized_frame(tmp_path):
    w = C.FrameWriter(tmp_path)
    with pytest.raises(AssertionError, match="expected"):
        w.write(Image.new("RGB", (640, 480)))
