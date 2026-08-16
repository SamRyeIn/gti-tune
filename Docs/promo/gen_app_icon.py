"""Generates the Quick Edit Android launcher icon, reusing the promo video's
own palette and mono wordmark styling (see hook_scenes.py's logo_frame) so the
app icon and the promo clip read as the same brand: a boost gauge on the
video's near-black background under a "simoscal" wordmark, split
white/accent-orange like the video's.

The wordmark sits horizontal and centred across the top. It was originally
banked -24 degrees across the middle of the gauge, which looked like the promo
clip but did not survive being an icon: it overlapped the arc it was drawn on
top of, and at size//11 it downsampled to roughly four pixels per character.
A launcher icon is read at 48-192 px, so the wordmark is now sized by fitting
it to a fraction of the canvas width rather than by picking an em size, and the
gauge was shrunk and dropped to keep clear of it.

Even so, mdpi (48 px) cannot resolve eight characters legibly — that is a limit
of the density, not of this layout. The wordmark is meant to read from xhdpi up.

One-off asset generator, not part of the promo build pipeline — run directly
and copy the output PNGs into the Android module's mipmap folders.
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

OUT_DIR = Path(__file__).parent / "icon_out"
SIZE = 1024  # generate at high res, downsample per density

BG = config.PALETTE["bg"]
WHITE = config.PALETTE["text"]
ACCENT = config.PALETTE["accent"]

WORDMARK = ("simos", "cal")

# Wordmark occupies this much of the canvas width, and its cap-height band is
# centred here vertically. The gauge below is positioned to clear it.
WORDMARK_WIDTH_FRAC = 0.86
WORDMARK_CENTRE_FRAC = 0.18

# Boost gauge scale, in psi. The dial reads 0 to PSI_MAX with a labelled major
# tick every PSI_STEP; the needle rests at NEEDLE_PSI, which is roughly where
# this car's IS20 actually peaks, so the icon shows a plausible reading rather
# than a decorative one.
PSI_MAX = 35
PSI_STEP = 5
NEEDLE_PSI = 24


def gauge_layer(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    # Sized and dropped so the arc's crown clears the wordmark band above while
    # the open bottom of the sweep still lands inside the canvas.
    cx, cy = size * 0.5, size * 0.68
    r_outer = size * 0.325
    r_ticks = r_outer

    # Gauge sweep: 210 deg on the left to -30 deg on the right (PIL's arc
    # angles run clockwise from 3 o'clock), leaving the bottom open.
    start_deg, end_deg = 150, 390
    width = max(7, size // 48)
    draw.arc(
        [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
        start=start_deg, end=end_deg, fill=WHITE, width=width,
    )

    def psi_to_deg(psi: float) -> float:
        return math.radians(start_deg + (psi / PSI_MAX) * (end_deg - start_deg))

    # Major ticks every PSI_STEP, each with its number just inside the arc.
    label_fnt = ImageFont.truetype(str(config.FONT_MONO), max(9, size // 23))
    for psi in range(0, PSI_MAX + 1, PSI_STEP):
        deg = psi_to_deg(psi)
        cos_d, sin_d = math.cos(deg), math.sin(deg)

        r0, r1 = r_ticks * 0.87, r_ticks * 1.0
        draw.line(
            [(cx + r0 * cos_d, cy + r0 * sin_d), (cx + r1 * cos_d, cy + r1 * sin_d)],
            fill=WHITE, width=max(4, size // 120),
        )

        # Numbers upright rather than rotated to the tick — a rotated numeral
        # is unreadable once this is 96 px wide, and upright reads as a real
        # instrument cluster anyway.
        r_label = r_ticks * 0.70
        lx, ly = cx + r_label * cos_d, cy + r_label * sin_d
        draw.text((lx, ly), str(psi), font=label_fnt, fill=WHITE, anchor="mm")

    # "PSI" under the hub, so the dial reads as boost rather than as a
    # generic speedometer.
    unit_fnt = ImageFont.truetype(str(config.FONT_MONO), max(8, size // 28))
    draw.text(
        (cx, cy + r_outer * 0.44), "PSI", font=unit_fnt, fill=WHITE, anchor="mm",
    )

    # Needle, resting at NEEDLE_PSI — kept short so it stays clear of the
    # numbers it sweeps past.
    needle_deg = psi_to_deg(NEEDLE_PSI)
    r_needle = r_outer * 0.52
    nx, ny = cx + r_needle * math.cos(needle_deg), cy + r_needle * math.sin(needle_deg)
    draw.line([(cx, cy), (nx, ny)], fill=ACCENT, width=max(9, size // 40))
    hub = size * 0.032
    draw.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=ACCENT)

    return layer


def _fit_font(text: str, target_w: float, size: int) -> ImageFont.FreeTypeFont:
    """Largest mono size whose rendering of `text` stays within `target_w`.

    Picking an em size directly is what made the old wordmark unreadable: the
    fraction of the icon it covered depended on the font's metrics. Fitting to
    a width makes the layout the fixed quantity and the em size the derived
    one, so the wordmark fills the same span whatever font config supplies.
    """
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    best = 8
    for em in range(8, size):
        if probe.textlength(text, font=ImageFont.truetype(str(config.FONT_MONO), em)) > target_w:
            break
        best = em
    return ImageFont.truetype(str(config.FONT_MONO), best)


def wordmark_layer(size: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    full = WORDMARK[0] + WORDMARK[1]
    fnt = _fit_font(full, size * WORDMARK_WIDTH_FRAC, size)

    w0 = draw.textlength(WORDMARK[0], font=fnt)
    total_w = draw.textlength(full, font=fnt)

    # Centre the cap-height band, not the em box: mono fonts carry descender
    # room that "simoscal" (no descenders) never uses, which would otherwise
    # push the wordmark visibly high of where it was asked to sit.
    x0 = size * 0.5 - total_w / 2
    y_mid = size * WORDMARK_CENTRE_FRAC
    top, bottom = fnt.getbbox(full)[1], fnt.getbbox(full)[3]
    y0 = y_mid - (top + bottom) / 2

    draw.text((x0, y0), WORDMARK[0], font=fnt, fill=WHITE)
    draw.text((x0 + w0, y0), WORDMARK[1], font=fnt, fill=ACCENT)
    return layer


# How much the round icon's content shrinks to fit the inscribed circle.
# The square layout runs the wordmark to 0.86 of the width, which a circle
# clips at the "s" and the "l"; 0.80 pulls both ends inside the arc.
ROUND_CONTENT_SCALE = 0.80


def content_layer(size: int) -> Image.Image:
    """Gauge and wordmark on transparency, with no background painted."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.alpha_composite(gauge_layer(size))
    layer.alpha_composite(wordmark_layer(size))
    return layer


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (*BG, 255))
    img.alpha_composite(content_layer(SIZE))
    return img


def build_round() -> Image.Image:
    """The `roundIcon` variant: real circular artwork, not the square one.

    Android hands `android:roundIcon` to launchers that draw circular icons and
    uses it as-is, so shipping the square master here just puts clipped corners
    on the dial. The content is scaled into the inscribed circle rather than
    cropped to it, which keeps the whole wordmark.
    """
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([0, 0, SIZE - 1, SIZE - 1], fill=(*BG, 255))

    inner = int(SIZE * ROUND_CONTENT_SCALE)
    scaled = content_layer(SIZE).resize((inner, inner), Image.LANCZOS)
    offset = (SIZE - inner) // 2
    img.alpha_composite(scaled, (offset, offset))
    return img


DENSITIES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    master, master_round = build(), build_round()
    master.save(OUT_DIR / "ic_launcher_master_1024.png")
    master_round.save(OUT_DIR / "ic_launcher_round_master_1024.png")
    for name, px in DENSITIES.items():
        d = OUT_DIR / name
        d.mkdir(exist_ok=True)
        master.resize((px, px), Image.LANCZOS).save(d / "ic_launcher.png")
        master_round.resize((px, px), Image.LANCZOS).save(d / "ic_launcher_round.png")
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    main()
