#!/usr/bin/env python3
"""Compose the mod-portal thumbnail: a building preview over a dark panel with
the mod title beneath it. Reproducible so the thumbnail can be regenerated if
the title or source art changes.

    python3 tools/make_thumbnail.py

Output: thumbnail.png (square, suitable for the Factorio mod portal).
"""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sprites/atom-forge/preview/atom-forge-preview-static.png")
OUT = os.path.join(ROOT, "thumbnail.png")

SIZE = 320                 # final square size
TITLE = ["Nullius:", "Hurricane Reskins"]
BG_TOP = (38, 44, 40)      # dark industrial green-grey
BG_BOT = (18, 20, 19)
ACCENT = (120, 230, 120)   # the atom-forge green


def load_font(size, bold=True):
    candidates = [
        "/System/Library/Fonts/Avenir Next.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def vertical_gradient(size, top, bottom):
    base = Image.new("RGB", (1, size), 0)
    for y in range(size):
        t = y / max(size - 1, 1)
        base.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return base.resize((size, size))


def main():
    canvas = vertical_gradient(SIZE, BG_TOP, BG_BOT).convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # Thin accent rule near the bottom, above the title band.
    band_h = 86
    draw.rectangle([0, SIZE - band_h, SIZE, SIZE], fill=(12, 14, 13, 235))
    draw.rectangle([0, SIZE - band_h, SIZE, SIZE - band_h + 2], fill=ACCENT + (255,))

    # Building art: crop to content, scale to fit the art area above the band.
    art = Image.open(SRC).convert("RGBA")
    bbox = art.getbbox()
    if bbox:
        art = art.crop(bbox)
    art_area_h = SIZE - band_h
    max_w, max_h = SIZE - 24, art_area_h - 12
    scale = min(max_w / art.width, max_h / art.height)
    art = art.resize((max(1, int(art.width * scale)), max(1, int(art.height * scale))), Image.LANCZOS)
    ax = (SIZE - art.width) // 2
    ay = (art_area_h - art.height) // 2 + 4
    canvas.alpha_composite(art, (ax, ay))

    # Title, two lines centered in the band.
    f1 = load_font(20)
    f2 = load_font(26)
    fonts = [f1, f2]
    total_h = sum(draw.textbbox((0, 0), t, font=fonts[i])[3] for i, t in enumerate(TITLE)) + 4
    y = SIZE - band_h + (band_h - total_h) // 2 + 2
    for i, line in enumerate(TITLE):
        f = fonts[i]
        w = draw.textbbox((0, 0), line, font=f)[2]
        color = (200, 206, 200) if i == 0 else (245, 248, 245)
        draw.text(((SIZE - w) // 2, y), line, font=f, fill=color)
        y += draw.textbbox((0, 0), line, font=f)[3] + 4

    canvas.convert("RGB").save(OUT)
    print("wrote", OUT, canvas.size)


if __name__ == "__main__":
    main()
