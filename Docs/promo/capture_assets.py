#!/usr/bin/env python3
"""Gather and normalise the real stills the promo is built from.

Writes into `Docs/promo/assets/`:

* `report.png`        — headless-Chrome screenshot of the newest tune `report.html`
* `surface_hero.png`  — `IP_FAC_BPA_SP[0]` — Map for boost pressure actuator
                        setpoint, before/after compare surface
* `heatmap_hero.png`  — the same table's compare heatmap
* `surface_ignition.png`, `log_*.png` — the other real outputs the montage uses
* `code_snippet.png`  — a rendered excerpt of the *actual* R14 revision script

Nothing here invents an image. Every asset is a copy or a screenshot of a real
simoscal output, and a missing source is a hard failure.

Run: `python3 Docs/promo/capture_assets.py`
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config

# --------------------------------------------------------------------- helpers


def _trim(img: Image.Image, pad: int = 24, tol: int = 8) -> Image.Image:
    """Crop uniform border padding, leaving `pad` px of it back.

    The background colour is taken from the bottom-right pixel, which is margin
    on every asset we handle (matplotlib figures and the report screenshot).
    """
    rgb = img.convert("RGB")
    a = np.asarray(rgb).astype(int)
    bg = a[-1, -1]
    diff = np.abs(a - bg).max(axis=2)
    mask = diff > tol
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if rows.size == 0 or cols.size == 0:
        return img
    top = max(int(rows.min()) - pad, 0)
    bottom = min(int(rows.max()) + pad + 1, img.height)
    left = max(int(cols.min()) - pad, 0)
    right = min(int(cols.max()) + pad + 1, img.width)
    return img.crop((left, top, right, bottom))


def _flatten(img: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    """RGBA -> RGB over a solid background (matplotlib writes RGBA)."""
    if img.mode != "RGBA":
        return img.convert("RGB")
    flat = Image.new("RGB", img.size, bg)
    flat.paste(img, mask=img.split()[3])
    return flat


def _assert_asset(path: Path, min_bytes: int = 10_000) -> None:
    if not path.is_file():
        raise SystemExit(f"asset not written: {path}")
    size = path.stat().st_size
    if size < min_bytes:
        raise SystemExit(f"asset suspiciously small ({size} B): {path}")


# -------------------------------------------------------------- report capture

REPORT_CSS_WIDTH = 1000      # layout width in CSS px — narrow reads better panned
REPORT_SCALE = 2             # device scale factor: crisp at 1:1 on a 1080p canvas
REPORT_MAX_CSS_HEIGHT = 5000 # tall enough to hold the whole report in one shot
REPORT_MIN_HEIGHT = 2500     # the "Changed this flash" section must be in frame


def capture_report(dest: Path, src_html: Path) -> Image.Image:
    """Screenshot `report.html` with headless Chrome, trimmed to its content.

    Chrome prints benign `task_policy_set` errors to stderr on macOS; success is
    keyed off the output PNG, not the exit chatter.
    """
    if not config.CHROME.is_file():
        raise SystemExit(
            f"Google Chrome not found at {config.CHROME}\n"
            "The report screenshot needs it. Install Chrome or edit CHROME in config.py."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()

    cmd = [
        str(config.CHROME),
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--force-device-scale-factor={REPORT_SCALE}",
        f"--window-size={REPORT_CSS_WIDTH},{REPORT_MAX_CSS_HEIGHT}",
        "--virtual-time-budget=5000",
        f"--screenshot={dest}",
        src_html.as_uri(),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if not dest.is_file():
        raise SystemExit(f"headless Chrome wrote no screenshot for {src_html}")

    img = _trim(Image.open(dest).convert("RGB"), pad=0)
    if img.height < REPORT_MIN_HEIGHT:
        raise SystemExit(
            f"report screenshot only {img.height}px tall — the 'Changed this flash' "
            "section is probably missing; raise REPORT_MAX_CSS_HEIGHT."
        )
    img.save(dest)
    _assert_asset(dest)
    return img


# ------------------------------------------------------------- code snippet art
# The snippet is lifted out of the real revision script by anchor text, so it
# cannot drift into being a prettified fake. If an anchor stops matching, the
# build fails rather than shipping invented code.

SNIPPET_BLOCKS: tuple[tuple[str, str], ...] = (
    ("MANIFOLD_PRESSURE_MAX_HPA =", "OVERBOOST_THRESHOLD_HPA ="),
    ("    tune.boost.manifold_pressure_max(", "    )"),
    ("    tune.limits.airmass_cap_mg(", "    )"),
)

SNIPPET_HEADER = "TUNE_Basics_Guide_R14.py"

KEYWORDS = {"def", "return", "import", "from", "for", "in", "if", "else", "with", "as", "not"}

CODE_BG = (13, 17, 23)
CODE_COLORS = {
    "comment": (110, 122, 140),
    "string": (255, 176, 106),
    "number": (134, 209, 255),
    "call": (240, 244, 250),
    "kwarg": (168, 220, 160),
    "const": (255, 214, 130),
    "plain": (206, 214, 226),
}


def extract_snippet(script: Path) -> list[str]:
    """Pull the anchored blocks verbatim out of the revision script."""
    lines = script.read_text().splitlines()
    out: list[str] = []
    for i, (first, last) in enumerate(SNIPPET_BLOCKS):
        try:
            start = next(n for n, ln in enumerate(lines) if ln.startswith(first))
        except StopIteration:
            raise SystemExit(f"snippet anchor not found in {script.name}: {first!r}")
        try:
            end = next(n for n in range(start + 1, len(lines)) if lines[n].startswith(last))
        except StopIteration:
            raise SystemExit(f"snippet end anchor not found after {first!r}: {last!r}")
        block = lines[start:end + 1]
        # Constant lines: keep the two declarations, drop the intervening ones.
        if i == 0:
            block = [ln for ln in block if re.match(r"^[A-Z_]+ *=", ln)]
        if out:
            out.append("")
        out.extend(ln.rstrip() for ln in block)
    return out


_TOKEN_RE = re.compile(
    r"(?P<comment>#.*$)"
    r"|(?P<string>\"[^\"]*\"|'[^']*')"
    r"|(?P<kwarg>\b[a-z_]+(?=\s*=[^=]))"
    r"|(?P<call>\b[a-z_][a-z_0-9]*(?=\())"
    r"|(?P<const>\b[A-Z][A-Z_0-9]{2,}\b)"
    r"|(?P<number>\b\d[\d_.]*\b)"
)


def _tokenize(line: str):
    """Yield `(text, color)` runs for one line of code."""
    pos = 0
    for m in _TOKEN_RE.finditer(line):
        if m.start() > pos:
            yield line[pos:m.start()], CODE_COLORS["plain"]
        kind = m.lastgroup
        yield m.group(), CODE_COLORS[kind]
        pos = m.end()
    if pos < len(line):
        yield line[pos:], CODE_COLORS["plain"]


def _mono(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(config.FONT_MONO), size)


def render_code_snippet(dest: Path, script: Path, target_width: int = 1680) -> Image.Image:
    """Render the real snippet as a dark code card sized to `target_width`."""
    lines = extract_snippet(script)
    pad_x, pad_y = 44, 40
    header_h = 56

    # Largest font size whose longest line still fits the card.
    size = 34
    while size > 12:
        font = _mono(size)
        widest = max(font.getlength(ln) for ln in lines)
        if widest + 2 * pad_x <= target_width:
            break
        size -= 1
    font = _mono(size)
    line_h = int(size * 1.55)

    height = pad_y * 2 + header_h + line_h * len(lines)
    img = Image.new("RGB", (target_width, height), CODE_BG)
    d = ImageDraw.Draw(img)

    # Window chrome: three dots and the source filename.
    for i, colour in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = pad_x + i * 26
        d.ellipse([cx, pad_y - 4, cx + 14, pad_y + 10], fill=colour)
    head_font = _mono(max(size - 8, 14))
    d.text((pad_x + 110, pad_y - 6), SNIPPET_HEADER, font=head_font, fill=(120, 132, 150))
    d.line([(0, pad_y + header_h - 22), (target_width, pad_y + header_h - 22)],
           fill=(32, 40, 52), width=2)

    y = pad_y + header_h
    for line in lines:
        x = pad_x
        for text, colour in _tokenize(line):
            d.text((x, y), text, font=font, fill=colour)
            x += font.getlength(text)
        y += line_h

    img.save(dest)
    _assert_asset(dest, min_bytes=5_000)
    return img


# --------------------------------------------------------------------- driver


def prepare_plot(dest: Path, src: Path, max_width: int = 1800) -> Image.Image:
    """Flatten, trim, and cap the width of a matplotlib output."""
    img = _trim(_flatten(Image.open(src)), pad=16)
    if img.width > max_width:
        h = round(img.height * max_width / img.width)
        img = img.resize((max_width, h), Image.LANCZOS)
    img.save(dest)
    _assert_asset(dest)
    return img


PLOT_KEYS = (
    "surface_hero", "heatmap_hero", "surface_ignition",
    "log_knock", "log_lambda", "log_rail", "log_boost", "log_coverage",
)


def main() -> None:
    src = config.resolve_assets()
    config.ASSET_DIR.mkdir(parents=True, exist_ok=True)

    report = capture_report(config.PREPARED["report"], src["report_html"])
    print(f"report.png        {report.size[0]}x{report.size[1]}  <- {src['report_html'].name}")

    for key in PLOT_KEYS:
        img = prepare_plot(config.PREPARED[key], src[key])
        print(f"{key + '.png':<18}{img.size[0]}x{img.size[1]}  <- {src[key].name}")

    code = render_code_snippet(config.PREPARED["code_snippet"], src["tune_script"])
    print(f"code_snippet.png  {code.size[0]}x{code.size[1]}  <- {src['tune_script'].name}")

    print(f"\n{len(PLOT_KEYS) + 2} assets in {config.ASSET_DIR}")


if __name__ == "__main__":
    sys.exit(main())
