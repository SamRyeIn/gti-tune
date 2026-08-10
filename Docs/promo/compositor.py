#!/usr/bin/env python3
"""The frame engine: a thin, deterministic compositing layer over PIL.

Scenes never touch PIL directly — they build a `Frame`, paste prepared stills,
draw text, and hand the frame to a `FrameWriter`. Everything here is a pure
function of `(scene, frame index)`, so any beat can be re-rendered on its own
without rebuilding the whole video.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config

Color = tuple[int, int, int]
Rect = tuple[float, float, float, float]

# ------------------------------------------------------------------- utilities


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def sub(t01: float, start: float, end: float) -> float:
    """Re-normalise a scene-relative 0..1 time onto a `[start, end]` sub-window.

    `sub(t, 0.2, 0.5)` is 0 before 20% of the scene, ramps to 1 at 50%, then
    stays 1 — the workhorse for staging several elements inside one beat.
    """
    if end <= start:
        return 1.0 if t01 >= end else 0.0
    return clamp01((t01 - start) / (end - start))


def linear(t: float) -> float:
    return clamp01(t)


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1.0 - (1.0 - t) ** 3


def ease_in(t: float) -> float:
    t = clamp01(t)
    return t ** 3


def pulse(t: float) -> float:
    """0 -> 1 -> 0 over the window; for flashes and highlights."""
    return math.sin(math.pi * clamp01(t))


# ----------------------------------------------------------------------- fonts


@lru_cache(maxsize=256)
def font(size: int, mono: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    if mono:
        path = config.FONT_MONO
    elif italic and config.FONT_DISPLAY_ITALIC.is_file():
        path = config.FONT_DISPLAY_ITALIC
    else:
        path = config.FONT_DISPLAY
    if not Path(path).is_file():
        path = config.FONT_FALLBACK
    return ImageFont.truetype(str(path), size)


def wrap_text(text: str, fnt: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    """Greedy word wrap; explicit newlines are honoured."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if fnt.getlength(trial) <= max_width:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


# ------------------------------------------------------------------ image prep


@lru_cache(maxsize=64)
def load(path: str | Path) -> Image.Image:
    """Load a prepared asset once and keep it around (frames re-use them)."""
    return Image.open(str(path)).convert("RGB")


def fit(img: Image.Image, max_w: float | None = None, max_h: float | None = None) -> Image.Image:
    """Scale down (or up) to fit inside the given box, preserving aspect."""
    sx = max_w / img.width if max_w else math.inf
    sy = max_h / img.height if max_h else math.inf
    s = min(sx, sy)
    if not math.isfinite(s) or abs(s - 1.0) < 1e-6:
        return img
    return img.resize((max(round(img.width * s), 1), max(round(img.height * s), 1)), Image.LANCZOS)


def rounded(img: Image.Image, radius: int = 18) -> Image.Image:
    """Round the corners of an image, returning RGBA with a soft alpha edge."""
    out = img.convert("RGBA")
    mask = Image.new("L", out.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, out.size[0] - 1, out.size[1] - 1],
                                          radius=radius, fill=255)
    out.putalpha(mask)
    return out


def ken_burns(img: Image.Image, t01: float, start_rect: Rect, end_rect: Rect,
              size: tuple[int, int] | None = None) -> Image.Image:
    """A pan/zoom view of `img`: the crop rect lerps start -> end, scaled to `size`.

    Rects are `(x0, y0, x1, y1)` in source-image pixels and may be fractional;
    `t01` is expected pre-eased by the caller.
    """
    t = clamp01(t01)
    box = tuple(lerp(a, b, t) for a, b in zip(start_rect, end_rect))
    out_size = size or (config.WIDTH, config.HEIGHT)
    return img.resize(out_size, Image.LANCZOS, box=box)


# ------------------------------------------------------------------ transitions


def fade(a: Image.Image, b: Image.Image, t01: float) -> Image.Image:
    """Cross-dissolve from `a` to `b`."""
    return Image.blend(a.convert("RGB"), b.convert("RGB"), clamp01(t01))


def wipe(a: Image.Image, b: Image.Image, t01: float, direction: str = "left") -> Image.Image:
    """Hard-edged reveal of `b` over `a`, travelling in `direction`."""
    t = clamp01(t01)
    out = a.convert("RGB").copy()
    b = b.convert("RGB")
    w, h = out.size
    if direction in ("left", "right"):
        cut = round(w * t)
        if cut <= 0:
            return out
        box = (0, 0, cut, h) if direction == "left" else (w - cut, 0, w, h)
    else:
        cut = round(h * t)
        if cut <= 0:
            return out
        box = (0, 0, w, cut) if direction == "up" else (0, h - cut, w, h)
    out.paste(b.crop(box), box[:2])
    return out


def slide_offset(t01: float, direction: str, distance: float) -> tuple[float, float]:
    """Offset for an element sliding in from `direction` (0 at t=1)."""
    d = (1.0 - clamp01(t01)) * distance
    return {
        "left": (-d, 0.0),
        "right": (d, 0.0),
        "up": (0.0, -d),
        "down": (0.0, d),
    }[direction]


# ---------------------------------------------------------------------- frame


@dataclass
class Frame:
    """One 1920x1080 canvas under construction."""

    bg: Color | None = None
    size: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        self.size = self.size or (config.WIDTH, config.HEIGHT)
        self.img = Image.new("RGB", self.size, self.bg or config.PALETTE["bg"])
        self.draw = ImageDraw.Draw(self.img)

    # -- geometry helpers
    @property
    def w(self) -> int:
        return self.size[0]

    @property
    def h(self) -> int:
        return self.size[1]

    @property
    def cx(self) -> int:
        return self.size[0] // 2

    @property
    def cy(self) -> int:
        return self.size[1] // 2

    # -- primitives
    def paste(self, img: Image.Image, xy: tuple[float, float], scale: float = 1.0,
              alpha: float = 1.0, anchor: str = "center") -> tuple[int, int, int, int]:
        """Paste `img` at `xy`; returns the box it occupied.

        `anchor` is one of center / topleft / topcenter / bottomcenter / left / right.
        """
        alpha = clamp01(alpha)
        if alpha <= 0.0:
            return (0, 0, 0, 0)
        if abs(scale - 1.0) > 1e-6:
            img = img.resize((max(round(img.width * scale), 1), max(round(img.height * scale), 1)),
                             Image.LANCZOS)
        w, h = img.size
        x, y = xy
        dx, dy = {
            "center": (-w / 2, -h / 2),
            "topleft": (0, 0),
            "topcenter": (-w / 2, 0),
            "topright": (-w, 0),
            "bottomcenter": (-w / 2, -h),
            "bottomleft": (0, -h),
            "left": (0, -h / 2),
            "right": (-w, -h / 2),
        }[anchor]
        box = (round(x + dx), round(y + dy))

        if img.mode == "RGBA":
            mask = img.split()[3]
            if alpha < 1.0:
                mask = mask.point(lambda v: round(v * alpha))
            self.img.paste(img.convert("RGB"), box, mask)
        elif alpha < 1.0:
            mask = Image.new("L", img.size, round(255 * alpha))
            self.img.paste(img.convert("RGB"), box, mask)
        else:
            self.img.paste(img.convert("RGB"), box)
        return (box[0], box[1], box[0] + w, box[1] + h)

    def text(self, s: str, xy: tuple[float, float], size: int = 48,
             color: Color | str = "text", *, mono: bool = False, italic: bool = False,
             align: str = "left", valign: str = "top", max_width: float | None = None,
             line_spacing: float = 1.32, bold: bool = False, alpha: float = 1.0,
             tracking: float = 0.0) -> tuple[int, int, int, int]:
        """Draw (optionally wrapped) text; returns its bounding box.

        `tracking` adds per-character letter spacing, used for the small
        all-caps labels. Returns a zero box when fully transparent.
        """
        if clamp01(alpha) <= 0.0:
            return (0, 0, 0, 0)
        fnt = font(size, mono=mono, italic=italic)
        col = config.PALETTE[color] if isinstance(color, str) else color
        if alpha < 1.0:
            bg = config.PALETTE["bg"]
            col = tuple(round(lerp(b, c, alpha)) for b, c in zip(bg, col))

        lines = wrap_text(s, fnt, max_width) if max_width else s.split("\n")
        line_h = size * line_spacing
        total_h = line_h * len(lines)

        x, y = xy
        y0 = {"top": y, "middle": y - total_h / 2, "bottom": y - total_h}[valign]

        stroke = round(size * 0.022) if bold else 0
        widths = [self._line_width(line, fnt, tracking) for line in lines]
        left = min(
            {"left": x, "center": x - w / 2, "right": x - w}[align] for w in widths
        ) if widths else x
        right = max(
            {"left": x + w, "center": x + w / 2, "right": x}[align] for w in widths
        ) if widths else x

        for i, line in enumerate(lines):
            lw = widths[i]
            lx = {"left": x, "center": x - lw / 2, "right": x - lw}[align]
            ly = y0 + i * line_h
            if tracking:
                cx = lx
                for ch in line:
                    self.draw.text((cx, ly), ch, font=fnt, fill=col,
                                   stroke_width=stroke, stroke_fill=col)
                    cx += fnt.getlength(ch) + tracking
            else:
                self.draw.text((lx, ly), line, font=fnt, fill=col,
                               stroke_width=stroke, stroke_fill=col)
        return (round(left), round(y0), round(right), round(y0 + total_h))

    @staticmethod
    def _line_width(line: str, fnt: ImageFont.FreeTypeFont, tracking: float) -> float:
        if not tracking:
            return fnt.getlength(line)
        return sum(fnt.getlength(ch) + tracking for ch in line) - tracking if line else 0.0

    def rect(self, box: Rect, fill: Color | str | None = None,
             outline: Color | str | None = None, width: int = 2, radius: int = 0) -> None:
        f = config.PALETTE[fill] if isinstance(fill, str) else fill
        o = config.PALETTE[outline] if isinstance(outline, str) else outline
        box = [round(v) for v in box]
        if radius:
            self.draw.rounded_rectangle(box, radius=radius, fill=f, outline=o, width=width)
        else:
            self.draw.rectangle(box, fill=f, outline=o, width=width)

    def line(self, xy0: tuple[float, float], xy1: tuple[float, float],
             color: Color | str = "rule", width: int = 2) -> None:
        col = config.PALETTE[color] if isinstance(color, str) else color
        self.draw.line([xy0, xy1], fill=col, width=width)

    def card(self, img: Image.Image, xy: tuple[float, float], scale: float = 1.0,
             alpha: float = 1.0, anchor: str = "center", radius: int = 18,
             border: Color | str | None = "rule", shadow: bool = True
             ) -> tuple[int, int, int, int]:
        """Paste a still as a rounded, bordered card with a soft drop shadow."""
        if abs(scale - 1.0) > 1e-6:
            img = img.resize((max(round(img.width * scale), 1), max(round(img.height * scale), 1)),
                             Image.LANCZOS)
        if shadow and alpha > 0.05:
            pad = 30
            sh = Image.new("L", (img.width + pad * 2, img.height + pad * 2), 0)
            ImageDraw.Draw(sh).rounded_rectangle(
                [pad, pad + 8, pad + img.width, pad + img.height + 8],
                radius=radius, fill=round(150 * clamp01(alpha)))
            sh = sh.filter(ImageFilter.GaussianBlur(16))
            shadow_img = Image.new("RGB", sh.size, (0, 0, 0))
            box_probe = self._anchor_box(img.size, xy, anchor)
            self.img.paste(shadow_img, (box_probe[0] - pad, box_probe[1] - pad), sh)
        return self.paste(rounded(img, radius), xy, alpha=alpha, anchor=anchor)

    @staticmethod
    def _anchor_box(size: tuple[int, int], xy: tuple[float, float], anchor: str
                    ) -> tuple[int, int]:
        w, h = size
        x, y = xy
        dx, dy = {
            "center": (-w / 2, -h / 2),
            "topleft": (0, 0),
            "topcenter": (-w / 2, 0),
            "topright": (-w, 0),
            "bottomcenter": (-w / 2, -h),
            "bottomleft": (0, -h),
            "left": (0, -h / 2),
            "right": (-w, -h / 2),
        }[anchor]
        return (round(x + dx), round(y + dy))

    def vignette(self, strength: float = 0.35) -> None:
        """Darken the edges slightly so bright screenshots sit in the frame."""
        if strength <= 0:
            return
        mask = Image.new("L", self.size, 0)
        d = ImageDraw.Draw(mask)
        inset = round(min(self.size) * 0.06)
        d.rounded_rectangle([inset, inset, self.w - inset, self.h - inset],
                            radius=inset * 3, fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(inset))
        dark = Image.new("RGB", self.size, (0, 0, 0))
        self.img = Image.composite(self.img, Image.blend(self.img, dark, strength), mask)
        self.draw = ImageDraw.Draw(self.img)

    def fade_to(self, color: Color | str, amount: float) -> None:
        """Blend the whole canvas toward a colour — used for beat in/out dips."""
        amount = clamp01(amount)
        if amount <= 0:
            return
        col = config.PALETTE[color] if isinstance(color, str) else color
        self.img = Image.blend(self.img, Image.new("RGB", self.size, col), amount)
        self.draw = ImageDraw.Draw(self.img)

    def save(self, path: str | Path) -> None:
        self.img.save(str(path))


# ---------------------------------------------------------------- frame writer


class FrameWriter:
    """Writes numbered frames and enforces that beats tile the timeline exactly.

    A scene that renders too few or too many frames fails here, before the
    encode, rather than silently shifting every later beat.
    """

    def __init__(self, out_dir: Path, pattern: str = "frame_%05d.png") -> None:
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.pattern = pattern
        self.index = 0
        self.count = 0
        self._beat = None

    def begin(self, beat: config.Beat) -> None:
        if self.index != beat.start_frame:
            raise AssertionError(
                f"beat '{beat.id}' starts at frame {beat.start_frame} but "
                f"{self.index} frames have been written — timeline gap/overlap"
            )
        self._beat = beat

    def end(self, beat: config.Beat) -> None:
        if self.index != beat.end_frame:
            raise AssertionError(
                f"beat '{beat.id}' wrote {self.index - beat.start_frame} frames, "
                f"expected {beat.n_frames}"
            )
        self._beat = None

    def write(self, frame: Frame | Image.Image) -> Path:
        img = frame.img if isinstance(frame, Frame) else frame
        if img.size != (config.WIDTH, config.HEIGHT):
            raise AssertionError(f"frame is {img.size}, expected {(config.WIDTH, config.HEIGHT)}")
        if self._beat is not None and self.index >= self._beat.end_frame:
            raise AssertionError(
                f"beat '{self._beat.id}' tried to write past its window "
                f"(frame {self.index} >= {self._beat.end_frame})"
            )
        path = self.out_dir / (self.pattern % self.index)
        img.convert("RGB").save(path)
        self.index += 1
        self.count += 1
        return path
