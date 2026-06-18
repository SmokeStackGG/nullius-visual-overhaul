#!/usr/bin/env python3
"""Render an "after" showcase of the overhauled buildings, running, per tier.

Reads the *shipped* packed sheets in graphics/entity/<source>/ and composites
them exactly the way the game loader does (lib/sprite.lua + lib/reskin.lua):

    base  ->  + mask x tier-tint  ->  + emission (additive glow)

Every layer is aligned by its own `shift` (in tiles; 1 tile = 32/scale source
px, i.e. 64 px at the usual scale 0.5), because the packed layers are cropped
differently and a single-frame mask is cycled across the animated base. Tier
tints are read straight from lib/tiers.lua (yellow / red / blue).

Deliberately omitted (cosmetic / need runtime context): the drop shadow and the
recipe-tint (color2) layer. Emission is shown always-lit so the building reads
as "running".

Outputs, under --out (default: showcase/):
  <source>/<source>-tier<N>.gif         one running GIF per building per tier
  group-N-*.gif                         the four composite grids (row per
                                        building, columns = tiers 1..3)

Run:  python3 tools/showcase.py            # everything
      python3 tools/showcase.py --only oxidizer scrubber
"""
import argparse
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTITY = os.path.join(ROOT, "graphics", "entity")
TIERS_LUA = os.path.join(ROOT, "lib", "tiers.lua")

# source folder -> (display name, building common name). Tiers come from the
# sheets themselves (sprite tints are tier-agnostic; we render 1..max_tier).
BUILDINGS = {
    "oxidizer":        "Electrolyzer",
    "chemical-stager": "Compressor",
    "scrubber":        "Air filter",
    "glass-furnace":   "Crusher",
    "manufacturer":    "Foundry",
    "fuel-refinery":   "Vacuum chamber",
    "fuel-refinery-water": "Flotation cell",
    "atom-forge":      "Nanofabricator",
    "arc-furnace":     "Geothermal plant",
    "thermal-plant":   "Hydro plant",
}

# Per-building tier count (nanofabricator is the only 1..2 line; rest are 1..3).
MAX_TIER = {"atom-forge": 2}

# The four composite groups (left->right buildings become top->bottom rows).
GROUPS = [
    ("group-1-electrolyzer-compressor",          ["oxidizer", "chemical-stager"]),
    ("group-2-airfilter-crusher-foundry",        ["scrubber", "glass-furnace", "manufacturer"]),
    ("group-3-vacuum-flotation-nanofabricator",  ["fuel-refinery", "fuel-refinery-water", "atom-forge"]),
    ("group-4-geothermal-hydro",                 ["arc-furnace", "thermal-plant"]),
]

# Layer file aliases, mirroring lib/sprite.lua layer_aliases.
ALIASES = {
    "base":             ["base", "main", "animation"],
    "mask":             ["mask", "color", "colour", "paint"],
    "emission":         ["emission", "light", "glow", "lights"],
    "emission_outside": ["emission-outside"],
    "emission_mask":    ["emission-mask"],
}


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def parse_tiers(path):
    """[n] = { r=.., g=.., b=.., a=.. } out of lib/tiers.lua."""
    text = open(path).read()
    tiers = {}
    for m in re.finditer(
        r"\[(\d+)\]\s*=\s*\{[^}]*?r\s*=\s*([\d.]+)[^}]*?g\s*=\s*([\d.]+)"
        r"[^}]*?b\s*=\s*([\d.]+)(?:[^}]*?a\s*=\s*([\d.]+))?",
        text,
    ):
        n, r, g, b, a = m.groups()
        tiers[int(n)] = (float(r), float(g), float(b), float(a) if a else 1.0)
    return dict(sorted(tiers.items()))


def _num(expr):
    """Evaluate a Spritter numeric expression like '2.5 / 64' or '-3'."""
    expr = expr.strip()
    if "/" in expr:
        a, b = expr.split("/")
        return float(a) / float(b)
    return float(expr)


def parse_def(path):
    """width, height, line_length, sprite_count, scale, shift(x,y) from a .lua."""
    text = open(path).read()

    def scalar(key, default=None):
        m = re.search(rf'\["{key}"\]\s*=\s*(-?[\d.]+)', text)
        return float(m.group(1)) if m else default

    sm = re.search(r'\["shift"\]\s*=\s*\{([^}]*)\}', text)
    shift = (0.0, 0.0)
    if sm:
        parts = sm.group(1).split(",")
        shift = (_num(parts[0]), _num(parts[1]))
    return {
        "width": int(scalar("width")),
        "height": int(scalar("height")),
        "line_length": int(scalar("line_length", 1)),
        "count": int(scalar("sprite_count", 1)),
        "scale": scalar("scale", 0.5),
        "shift": shift,
    }


def find_layer(source, logical):
    d = os.path.join(ENTITY, source)
    for alias in ALIASES[logical]:
        lua = os.path.join(d, f"{source}-{alias}.lua")
        png = os.path.join(d, f"{source}-{alias}.png")
        if os.path.exists(lua) and os.path.exists(png):
            return png, parse_def(lua)
    return None


# --------------------------------------------------------------------------- #
# frame slicing + alignment
# --------------------------------------------------------------------------- #
def slice_frames(png, d):
    """Return a list of RGBA float32 frames from a packed grid sheet."""
    sheet = np.asarray(Image.open(png).convert("RGBA"), dtype=np.float32)
    fw, fh, cols, n = d["width"], d["height"], d["line_length"], d["count"]
    frames = []
    for i in range(n):
        c, r = i % cols, i // cols
        frames.append(sheet[r * fh:r * fh + fh, c * fw:c * fw + fw, :].copy())
    return frames


def ppt(d):
    """Source pixels per tile for this layer (1 tile = 32 screen px / scale)."""
    return 32.0 / d["scale"]


def place(frame, d, cw, ch):
    """Drop a layer frame onto a (cw x ch) canvas, centered + shift (in tiles).

    Positive shift x = right, positive y = down, matching Factorio."""
    canvas = np.zeros((ch, cw, 4), dtype=np.float32)
    fh, fw = frame.shape[:2]
    p = ppt(d)
    cx = cw / 2.0 + d["shift"][0] * p
    cy = ch / 2.0 + d["shift"][1] * p
    x0 = int(round(cx - fw / 2.0))
    y0 = int(round(cy - fh / 2.0))
    # clip to canvas
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    w = min(fw - sx0, cw - dx0)
    h = min(fh - sy0, ch - dy0)
    if w > 0 and h > 0:
        canvas[dy0:dy0 + h, dx0:dx0 + w] = frame[sy0:sy0 + h, sx0:sx0 + w]
    return canvas


def canvas_size(defs):
    """Canvas big enough to hold every layer at its shifted position."""
    cw = ch = 0
    for d in defs:
        p = ppt(d)
        cw = max(cw, d["width"] + 2 * int(abs(d["shift"][0] * p)))
        ch = max(ch, d["height"] + 2 * int(abs(d["shift"][1] * p)))
    return cw + 8, ch + 8


# --------------------------------------------------------------------------- #
# compositing
# --------------------------------------------------------------------------- #
def over(dst, src):
    """Standard alpha-over of premultiplied-by-alpha src RGBA onto dst RGBA."""
    sa = src[:, :, 3:4] / 255.0
    out = dst.copy()
    out[:, :, :3] = src[:, :, :3] * sa + dst[:, :, :3] * (1 - sa)
    out[:, :, 3] = np.clip(src[:, :, 3] + dst[:, :, 3] * (1 - sa[:, :, 0]), 0, 255)
    return out


def tint_mask(mask, tint):
    """Multiply a mask layer by a tier tint (r,g,b,a)."""
    out = mask.copy()
    out[:, :, 0] *= tint[0]
    out[:, :, 1] *= tint[1]
    out[:, :, 2] *= tint[2]
    out[:, :, 3] *= tint[3]
    return out


def add_glow(rgb, em, tint=None):
    """Additive blend an emission layer's light onto an RGB canvas in place.

    Emission sheets are opaque black with baked-in glow, so additive makes the
    black vanish and only the light adds. Tier-tinted for the in-mask split."""
    light = em[:, :, :3].copy()
    a = em[:, :, 3:4] / 255.0
    if tint is not None:
        light[:, :, 0] *= tint[0]
        light[:, :, 1] *= tint[1]
        light[:, :, 2] *= tint[2]
    rgb[:, :, :3] = np.clip(rgb[:, :, :3] + light * a, 0, 255)


def cyc(frames, i):
    return frames[i % len(frames)]


def render_building(source, tiers, bg=40):
    """Return {tier: [RGBA uint8 frames]}, cropped to the building bbox.

    Frames are rendered onto an opaque background shade `bg`."""
    base = find_layer(source, "base")
    if not base:
        raise SystemExit(f"{source}: no base layer")
    mask = find_layer(source, "mask")
    em_out = find_layer(source, "emission_outside")
    em_msk = find_layer(source, "emission_mask")
    em_single = None if (em_out and em_msk) else find_layer(source, "emission")

    defs = [base[1]]
    for layer in (mask, em_out, em_msk, em_single):
        if layer:
            defs.append(layer[1])
    cw, ch = canvas_size(defs)

    base_frames = [place(f, base[1], cw, ch) for f in slice_frames(*base)]
    n = len(base_frames)

    def aligned(layer):
        if not layer:
            return None
        return [place(f, layer[1], cw, ch) for f in slice_frames(*layer)]

    mask_frames = aligned(mask)
    out_frames = aligned(em_out)
    msk_frames = aligned(em_msk)
    single_frames = aligned(em_single)

    # bbox from the union of base alpha across all frames (so moving parts fit).
    union = np.zeros((ch, cw), dtype=np.float32)
    for f in base_frames:
        union = np.maximum(union, f[:, :, 3])
    ys, xs = np.where(union > 8)
    if len(xs) == 0:
        x0, y0, x1, y1 = 0, 0, cw, ch
    else:
        pad = 6
        x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
        x1, y1 = min(cw, xs.max() + pad), min(ch, ys.max() + pad)

    result = {}
    for tier, tint in tiers.items():
        frames = []
        for i in range(n):
            canvas = np.zeros((ch, cw, 4), dtype=np.float32)
            canvas[:, :, :3] = bg
            canvas[:, :, 3] = 255
            canvas = over(canvas, base_frames[i])
            if mask_frames:
                canvas = over(canvas, tint_mask(cyc(mask_frames, i), tint))
            if out_frames and msk_frames:
                add_glow(canvas, cyc(out_frames, i), None)
                add_glow(canvas, cyc(msk_frames, i), tint)
            elif single_frames:
                add_glow(canvas, cyc(single_frames, i), None)
            crop = canvas[y0:y1, x0:x1]
            frames.append(np.clip(crop, 0, 255).astype(np.uint8))
        result[tier] = frames
    return result


# --------------------------------------------------------------------------- #
# grid + labels + gif
# --------------------------------------------------------------------------- #
def subsample(frames, max_frames):
    """Evenly pick at most `max_frames` items, preserving order + loop feel."""
    n = len(frames)
    if max_frames <= 0 or n <= max_frames:
        return frames
    idx = [round(i * n / max_frames) for i in range(max_frames)]
    return [frames[min(j, n - 1)] for j in idx]


def save_gif(frames_rgb, path, fps, max_frames):
    """Quantize to one shared palette + subsample so the GIF stays small."""
    frames_rgb = subsample(frames_rgb, max_frames)
    ref = frames_rgb[len(frames_rgb) // 2].quantize(colors=255, method=Image.MEDIANCUT)
    # No dither + disposal=1 keeps the static gutter/headers from re-encoding,
    # so `optimize` only stores the animated diff rectangles -> much smaller.
    pal = [f.quantize(palette=ref, dither=Image.NONE) for f in frames_rgb]
    pal[0].save(path, save_all=True, append_images=pal[1:],
                duration=int(1000 / fps), loop=0, optimize=True, disposal=1)
    return len(pal)


def _font(size):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def fit_cell(frame_u8, cell, bg):
    """Resize an RGBA frame to fit within a (cell x cell) box, centered on bg."""
    img = Image.fromarray(frame_u8, "RGBA").convert("RGB")
    w, h = img.size
    s = min(cell / w, cell / h)
    img = img.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    canvas = Image.new("RGB", (cell, cell), (bg, bg, bg))
    canvas.paste(img, ((cell - img.width) // 2, (cell - img.height) // 2))
    return canvas


def build_group_gif(group_name, sources, per_building, tiers, out_path,
                    cell=240, fps=20, bg=24, max_frames=48):
    """Tile buildings (rows) x tiers (cols) into one animated GIF with labels."""
    max_tiers = max(len(MAX_TIER_TIERS(s, tiers)) for s in sources)
    head_h = 30
    pad = 10
    name_w = 200

    cols = max_tiers
    grid_w = name_w + cols * (cell + pad) + pad
    grid_h = head_h + len(sources) * (cell + pad) + pad

    n_frames = max(
        len(per_building[s][min(per_building[s])]) for s in sources
    )
    font = _font(22)
    small = _font(18)

    gif_frames = []
    for fi in range(n_frames):
        im = Image.new("RGB", (grid_w, grid_h), (bg, bg, bg))
        dr = ImageDraw.Draw(im)
        # column headers
        for ci in range(cols):
            cx = name_w + ci * (cell + pad) + pad + cell // 2
            txt = f"Tier {ci + 1}"
            tb = dr.textbbox((0, 0), txt, font=small)
            dr.text((cx - (tb[2] - tb[0]) // 2, 6), txt, (220, 220, 220), font=small)
        # rows
        for ri, s in enumerate(sources):
            row_y = head_h + ri * (cell + pad) + pad
            # building name (left gutter, vertically centered on the row)
            nm = BUILDINGS[s]
            tb = dr.textbbox((0, 0), nm, font=font)
            dr.text((pad, row_y + cell // 2 - (tb[3] - tb[1]) // 2),
                    nm, (255, 255, 255), font=font)
            avail = sorted(per_building[s].keys())
            for ci in range(cols):
                tier = ci + 1
                cx = name_w + ci * (cell + pad) + pad
                if tier not in per_building[s]:
                    continue
                frames = per_building[s][tier]
                cellimg = fit_cell(frames[fi % len(frames)], cell, bg)
                im.paste(cellimg, (cx, row_y))
        gif_frames.append(im)

    written = save_gif(gif_frames, out_path, fps, max_frames)
    print(f"  wrote {out_path}  ({written} frames, {grid_w}x{grid_h})")


def MAX_TIER_TIERS(source, tiers):
    top = MAX_TIER.get(source, 3)
    return {t: c for t, c in tiers.items() if t <= top}


def save_single_gifs(source, per_building, out_dir, fps, bg, max_frames):
    os.makedirs(out_dir, exist_ok=True)
    for tier, frames in per_building.items():
        imgs = [Image.fromarray(f, "RGBA").convert("RGB") for f in frames]
        path = os.path.join(out_dir, f"{source}-tier{tier}.gif")
        save_gif(imgs, path, fps, max_frames)
    print(f"  {source}: {len(per_building)} tier GIFs")


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "showcase"))
    ap.add_argument("--only", nargs="*", help="restrict to these source folders")
    ap.add_argument("--fps", type=float, default=20)
    ap.add_argument("--cell", type=int, default=240, help="grid cell px")
    ap.add_argument("--bg", type=int, default=24, help="background shade 0-255")
    ap.add_argument("--max-frames", type=int, default=48,
                    help="cap GIF length by evenly subsampling frames (0 = all)")
    ap.add_argument("--no-singles", action="store_true",
                    help="skip per-building GIFs, only build the group grids")
    args = ap.parse_args()

    all_tiers = parse_tiers(TIERS_LUA)
    os.makedirs(args.out, exist_ok=True)

    want = set(args.only) if args.only else set(BUILDINGS)
    rendered = {}
    for source in BUILDINGS:
        if source not in want:
            continue
        tiers = MAX_TIER_TIERS(source, all_tiers)
        print(f"rendering {source} ({BUILDINGS[source]}) tiers {list(tiers)}")
        rendered[source] = render_building(source, tiers, bg=args.bg)
        if not args.no_singles:
            save_single_gifs(source, rendered[source],
                             os.path.join(args.out, source), args.fps, args.bg,
                             args.max_frames)

    for group_name, sources in GROUPS:
        srcs = [s for s in sources if s in rendered]
        if not srcs:
            continue
        print(f"composite {group_name}: {srcs}")
        build_group_gif(group_name, srcs, rendered, all_tiers,
                        os.path.join(args.out, f"{group_name}.gif"),
                        cell=args.cell, fps=args.fps, bg=args.bg,
                        max_frames=args.max_frames)


if __name__ == "__main__":
    main()
