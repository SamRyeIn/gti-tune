"""U2 — asset capture and preparation."""

import subprocess

import pytest
from PIL import Image

import capture_assets
import config

pytestmark = pytest.mark.usefixtures("assets_present")


@pytest.fixture(scope="session")
def assets_present():
    missing = [k for k, p in config.PREPARED.items() if not p.is_file()]
    if missing:
        pytest.skip(f"run `python3 Docs/promo/capture_assets.py` first (missing: {missing})")


def test_every_prepared_asset_exists_and_is_substantial():
    for name, path in config.PREPARED.items():
        assert path.is_file(), f"{name} missing"
        assert path.stat().st_size > 10_000, f"{name} is only {path.stat().st_size} B"


def test_report_capture_is_tall_enough_to_hold_the_changed_section():
    with Image.open(config.PREPARED["report"]) as img:
        assert img.height > capture_assets.REPORT_MIN_HEIGHT
        assert img.width > 1200


def test_prepared_plots_are_opaque_rgb():
    with Image.open(config.PREPARED["log_knock"]) as img:
        assert img.mode == "RGB"


def test_missing_chrome_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHROME", tmp_path / "no-such-chrome")
    with pytest.raises(SystemExit, match="Google Chrome not found"):
        capture_assets.capture_report(tmp_path / "out.png", config.resolve_assets()["report_html"])


def test_chrome_writing_nothing_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: None)
    with pytest.raises(SystemExit, match="wrote no screenshot"):
        capture_assets.capture_report(tmp_path / "out.png", config.resolve_assets()["report_html"])


def test_snippet_lines_are_verbatim_from_the_revision_script():
    script = config.resolve_assets()["tune_script"]
    source = script.read_text().splitlines()
    lines = capture_assets.extract_snippet(script)
    assert lines, "snippet is empty"
    for line in lines:
        if line:
            assert line in source, f"snippet line not present in {script.name}: {line!r}"


def test_snippet_shows_a_physical_units_call_with_an_intent():
    lines = capture_assets.extract_snippet(config.resolve_assets()["tune_script"])
    body = "\n".join(lines)
    assert "tune." in body
    assert "intent=" in body


def test_snippet_anchor_failure_is_loud(tmp_path, monkeypatch):
    script = tmp_path / "fake_tune.py"
    script.write_text("print('nothing to see')\n")
    with pytest.raises(SystemExit, match="anchor not found"):
        capture_assets.extract_snippet(script)


def test_trim_removes_uniform_border():
    img = Image.new("RGB", (200, 200), (255, 255, 255))
    img.paste(Image.new("RGB", (40, 20), (10, 10, 10)), (80, 90))
    out = capture_assets._trim(img, pad=0)
    assert out.size == (40, 20)


def test_tokenizer_colors_comments_and_strings():
    runs = dict((text.strip(), colour) for text, colour in
                capture_assets._tokenize('    intent="raise the cap",  # note'))
    assert runs['intent'] == capture_assets.CODE_COLORS["kwarg"]
    assert runs['"raise the cap"'] == capture_assets.CODE_COLORS["string"]
    assert runs['# note'] == capture_assets.CODE_COLORS["comment"]
