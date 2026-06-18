#!/usr/bin/env python3
"""Author and preview tier-color masks for Nullius: Visual Overhaul.

Tier coloring works by drawing a *mask* layer on top of the base art, tinted
per tier (see lib/tiers.lua + lib/sprite.lua). The mask is a grayscale image of
ONLY the regions you want colored, transparent everywhere else. Tinting that
mask colors just those regions, leaving the rest of the building untouched.

Workflow: author a binary *stencil* (white = paint region) once, then bake it
across every base frame with tools/apply_stencil.py. The GUI (tools/mask_ui.py)
is the usual way to author the stencil; this CLI covers the headless pieces.

Subcommands:

  bootstrap  Headless stencil maker: select a region by rectangle and/or colour
             and write a binary stencil (white = paint region, transparent
             elsewhere) -- the same output as the GUI's Export.

  frame      Pull a single frame out of a packed Spritter sheet for authoring.

  preview    Composite base + tinted mask for every tier colour (read straight
             from lib/tiers.lua) and write preview PNGs + a side-by-side strip,
             so you can see a baked mask without launching Factorio.

  preview-anim  Like preview but animated: loop the base animation in each tier
             colour and write a GIF per tier plus one combined side-by-side GIF.

  preview-emission  Compare how the emission glow interacts with the tier tint
             (no-glow / current untinted / whole-tinted / mask-only-tinted), one
             strip per tier, straight from the packed graphics.

  split-emission  Split the packed emission into outside (natural) + masked
             (tinted per tier) frame folders, so the tier colour survives where
             the building lights up. Pack both with Spritter.

  derive-icon  Make the tinted icon pair from a base frame + its baked mask.

Examples:
  # 1. bootstrap a stencil from a single base frame, selecting the brass panels
  python3 tools/mask_tool.py bootstrap \\
      --base /tmp/nvo-work/chemical-stager/base/0.png \\
      --near 150,120,60 --tol 60 --out /tmp/cs-stencil.png

  # ...or a rectangular region (repeat --rect for several)
  python3 tools/mask_tool.py bootstrap --base 0.png --rect 120,60,160,120 --out stencil.png

  # 2. bake the stencil across all frames, then pack with Spritter (see README)
  python3 tools/apply_stencil.py --stencil stencil.png \\
      --frames .work/chemical-stager/base --out .work/chemical-stager/mask

  # 3. preview a baked mask frame in all tiers
  python3 tools/mask_tool.py preview --base 0.png --mask .work/chemical-stager/mask/0.png \\
      --out /tmp/cs-preview
"""
import argparse
import os
import re
import sys
import numpy as np
from PIL import Image

import mask_ops


def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32)


def frame_box(fw, fh, cols, index):
    """Pixel box of frame `index` in a packed Spritter grid sheet."""
    c, r = index % cols, index // cols
    return (c * fw, r * fh, c * fw + fw, r * fh + fh)


def lua_num(text, key):
    m = re.search(rf'\["{key}"\]\s*=\s*([\d.]+)', text)
    return float(m.group(1)) if m else None


def cmd_frame(args):
    """Pull a single frame out of a packed Spritter sheet for authoring/preview."""
    sheet = Image.open(args.sheet).convert("RGBA")
    fw, fh, cols = args.fw, args.fh, args.cols
    lua = os.path.splitext(args.sheet)[0] + ".lua"
    if (not (fw and fh and cols)) and os.path.exists(lua):
        t = open(lua).read()
        fw = fw or int(lua_num(t, "width"))
        fh = fh or int(lua_num(t, "height"))
        cols = cols or int(lua_num(t, "line_length"))
    if not (fw and fh and cols):
        sys.exit("need --fw --fh --cols (or a sibling .lua next to the sheet)")
    box = frame_box(fw, fh, cols, args.index)
    sheet.crop(box).save(args.out)
    print(f"wrote {args.out}  frame {args.index} -> {fw}x{fh} at {box[:2]}")


def _crop_square(img, alpha_src, pad=0.06):
    """Crop to the building's bbox (from alpha_src) and pad to a square."""
    a = np.asarray(alpha_src)[:, :, 3]
    ys, xs = np.where(a > 0)
    if len(xs) == 0:
        return img
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    side = int(max(x1 - x0, y1 - y0) * (1 + pad))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
    return img.crop(box)


def cmd_derive_icon(args):
    """Make the tinted icon pair from a building frame + its mask, so the
    building art is the single source of truth (set icon_mask = true)."""
    base = Image.open(args.frame).convert("RGBA")
    mask = Image.open(args.mask).convert("RGBA")
    if mask.size != base.size:
        sys.exit(f"mask {mask.size} must match frame {base.size}")
    base_i = _crop_square(base, base).resize((args.size, args.size), Image.LANCZOS)
    mask_i = _crop_square(mask, base).resize((args.size, args.size), Image.LANCZOS)
    os.makedirs(args.outdir, exist_ok=True)
    bp = os.path.join(args.outdir, f"{args.source}-icon-base.png")
    mp = os.path.join(args.outdir, f"{args.source}-icon-mask.png")
    base_i.save(bp)
    mask_i.save(mp)
    print(f"wrote {bp}\n      {mp}\n-> set icon = true, icon_mask = true on the '{args.source}' entry")


def parse_tiers(lua_path):
    """Pull tier colours out of lib/tiers.lua: [n] = { r=.., g=.., b=.., a=.. }."""
    text = open(lua_path).read()
    tiers = {}
    for m in re.finditer(
        r"\[(\d+)\]\s*=\s*\{[^}]*?r\s*=\s*([\d.]+)[^}]*?g\s*=\s*([\d.]+)"
        r"[^}]*?b\s*=\s*([\d.]+)(?:[^}]*?a\s*=\s*([\d.]+))?",
        text,
    ):
        n, r, g, b, a = m.groups()
        tiers[int(n)] = (float(r), float(g), float(b), float(a) if a else 1.0)
    return dict(sorted(tiers.items()))


def cmd_bootstrap(args):
    """Headless stencil maker: select a region by rectangle and/or colour and
    write a binary stencil (white = paint region, transparent elsewhere) -- the
    same output as the GUI's Export. Feed it to apply_stencil.py."""
    base = load_rgba(args.base)
    h, w = base.shape[:2]
    rgb = base[:, :, :3]
    alpha = base[:, :, 3]

    sel = np.zeros((h, w), dtype=bool)
    for rect in args.rect or []:
        x, y, rw, rh = (int(v) for v in rect.split(","))
        sel[max(0, y):y + rh, max(0, x):x + rw] = True
    if args.near:
        target = np.array([int(v) for v in args.near.split(",")], dtype=np.float32)
        dist = np.sqrt(((rgb - target) ** 2).sum(axis=2))
        sel |= dist <= args.tol
    if not (args.rect or args.near):
        sys.exit("bootstrap needs --rect and/or --near to choose a region")

    # Only keep selected pixels that are actually part of the building.
    sel &= alpha > 0

    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[sel] = (255, 255, 255, 255)
    Image.fromarray(out, "RGBA").save(args.out)
    print(f"wrote stencil {args.out}  ({int(sel.sum())} px selected of {w}x{h})")


def composite(base, mask, tint):
    """base + (mask * tint) over, matching a Factorio tinted mask layer."""
    tr, tg, tb, ta = tint
    tinted = mask.copy()
    tinted[:, :, 0] *= tr
    tinted[:, :, 1] *= tg
    tinted[:, :, 2] *= tb
    a = (tinted[:, :, 3] * ta / 255.0)[:, :, None]
    out = base.copy()
    out[:, :, :3] = base[:, :, :3] * (1 - a) + tinted[:, :, :3] * a
    out[:, :, 3] = np.clip(base[:, :, 3] + tinted[:, :, 3] * ta * (1 - base[:, :, 3:4][:, :, 0] / 255.0), 0, 255)
    return out


def on_bg(img, shade=40):
    bg = np.empty_like(img)
    bg[:, :, :3] = shade
    bg[:, :, 3] = 255
    a = img[:, :, 3:4] / 255.0
    bg[:, :, :3] = img[:, :, :3] * a + bg[:, :, :3] * (1 - a)
    return bg.astype(np.uint8)


def cmd_preview(args):
    base = load_rgba(args.base)
    mask = load_rgba(args.mask)
    if mask.shape[:2] != base.shape[:2]:
        sys.exit(f"mask {mask.shape[:2]} must match base {base.shape[:2]}")
    tiers = parse_tiers(args.tiers)
    os.makedirs(args.out, exist_ok=True)

    panels = [on_bg(base)]
    names = ["base"]
    for n, tint in tiers.items():
        comp = composite(base, mask, tint)
        Image.fromarray(comp.astype(np.uint8), "RGBA").save(
            os.path.join(args.out, f"preview-tier{n}.png"))
        panels.append(on_bg(comp))
        names.append(f"tier{n} {tuple(round(c,2) for c in tint[:3])}")

    h = max(p.shape[0] for p in panels)
    gap = 8
    strip = np.full((h, sum(p.shape[1] for p in panels) + gap * (len(panels) - 1), 3),
                    20, dtype=np.uint8)
    x = 0
    for p in panels:
        strip[:p.shape[0], x:x + p.shape[1]] = p[:, :, :3]
        x += p.shape[1] + gap
    Image.fromarray(strip, "RGB").save(os.path.join(args.out, "preview-strip.png"))
    print("wrote previews to", args.out, "->", ", ".join(names))


def load_frames(path):
    """Load a single PNG or a folder of PNGs as a list of (H,W,4) float32 arrays.
    A folder is read in sorted filename order so frames stay in animation order."""
    if os.path.isdir(path):
        files = sorted(f for f in os.listdir(path) if f.lower().endswith(".png"))
        if not files:
            sys.exit(f"no PNG frames in {path}")
        return [load_rgba(os.path.join(path, f)) for f in files]
    return [load_rgba(path)]


def _scaled(rgb_u8, scale):
    if scale == 1.0:
        return rgb_u8
    h, w = rgb_u8.shape[:2]
    img = Image.fromarray(rgb_u8, "RGB").resize(
        (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return np.asarray(img, dtype=np.uint8)


def anim_tier_frames(base_frames, mask_frames, tint, bg=40, scale=1.0):
    """Composite each base frame with the (cycled) tinted mask for one tier.
    Returns a list of uint8 HxWx3 frames on a flat `bg`, one per base frame."""
    out = []
    n_mask = len(mask_frames)
    for i, base in enumerate(base_frames):
        comp = composite(base, mask_frames[i % n_mask], tint)
        out.append(_scaled(on_bg(comp, bg)[:, :, :3], scale))
    return out


def anim_combined_frames(panels, gap=8, bg=20):
    """Lay several equal-length panel sequences side by side per frame.
    `panels` is a list of frame-lists (each list[uint8 HxWx3]). Returns a list of
    uint8 rows, one per frame index."""
    n = min(len(p) for p in panels)
    h = max(p[0].shape[0] for p in panels)
    total_w = sum(p[0].shape[1] for p in panels) + gap * (len(panels) - 1)
    out = []
    for i in range(n):
        row = np.full((h, total_w, 3), bg, dtype=np.uint8)
        x = 0
        for p in panels:
            fr = p[i]
            row[:fr.shape[0], x:x + fr.shape[1]] = fr
            x += fr.shape[1] + gap
        out.append(row)
    return out


def _save_gif(frames, path, fps):
    imgs = [Image.fromarray(f, "RGB") for f in frames]
    imgs[0].save(path, save_all=True, append_images=imgs[1:],
                 duration=max(1, round(1000 / fps)), loop=0, optimize=False)


def cmd_preview_anim(args):
    """Animated tier preview: loop the base animation in each tier colour and
    write a GIF per tier plus one combined side-by-side GIF."""
    base = load_frames(args.frames)
    mask = load_frames(args.mask)
    if mask[0].shape[:2] != base[0].shape[:2]:
        sys.exit(f"mask {mask[0].shape[:2]} must match base {base[0].shape[:2]}")
    tiers = parse_tiers(args.tiers)
    os.makedirs(args.out, exist_ok=True)

    base_panel = [_scaled(on_bg(b, 40)[:, :, :3], args.scale) for b in base]
    _save_gif(base_panel, os.path.join(args.out, "preview-base.gif"), args.fps)
    panels = [base_panel]
    for n, tint in tiers.items():
        frames = anim_tier_frames(base, mask, tint, scale=args.scale)
        _save_gif(frames, os.path.join(args.out, f"preview-tier{n}.gif"), args.fps)
        panels.append(frames)

    combined = anim_combined_frames(panels)
    _save_gif(combined, os.path.join(args.out, "preview-all.gif"), args.fps)
    print(f"wrote {len(tiers) + 2} GIFs to {args.out} "
          f"({len(base)} frames @ {args.fps}fps): "
          f"preview-base.gif, " + ", ".join(f"preview-tier{n}.gif" for n in tiers)
          + ", preview-all.gif")


def _eval_num(s):
    s = s.strip()
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b)
    return float(s)


def lua_shift(text):
    """Parse a Spritter def's shift {x, y} (terms may be like "-45 / 64")."""
    m = re.search(r'\["shift"\]\s*=\s*\{([^}]*)\}', text)
    if not m:
        return (0.0, 0.0)
    parts = m.group(1).split(",")
    return (_eval_num(parts[0]), _eval_num(parts[1]))


def _extract_frame(sheet_path, index):
    """Crop frame `index` from a packed Spritter sheet using its sibling .lua.
    Returns (float32 RGBA array, (frame_w, frame_h))."""
    sheet = Image.open(sheet_path).convert("RGBA")
    t = open(os.path.splitext(sheet_path)[0] + ".lua").read()
    fw, fh, cols = int(lua_num(t, "width")), int(lua_num(t, "height")), int(lua_num(t, "line_length"))
    box = frame_box(fw, fh, cols, index)
    return np.asarray(sheet.crop(box), dtype=np.float32), (fw, fh)


def cmd_preview_emission(args):
    """Compare how the emission glow interacts with the tier tint: tinted mask
    with no glow, the current untinted glow, the whole glow tinted per tier, and
    the glow tinted only where it overlaps the mask. Writes one strip per tier so
    you can pick a glow treatment. Works straight from the shipped graphics."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(repo, "graphics", "entity", args.source)
    base_sheet = os.path.join(d, f"{args.source}-base.png")
    em_sheet = os.path.join(d, f"{args.source}-emission.png")
    mask_png = os.path.join(d, f"{args.source}-mask.png")
    for p in (base_sheet, em_sheet, mask_png):
        if not os.path.exists(p):
            sys.exit(f"missing {p} (need base, emission and mask packed in graphics/)")

    base, (fw, fh) = _extract_frame(base_sheet, args.frame)
    em, _ = _extract_frame(em_sheet, args.frame)
    mtext = open(os.path.splitext(mask_png)[0] + ".lua").read()
    mask_trim = np.asarray(Image.open(mask_png).convert("RGBA"), dtype=np.float32)
    mask_full = mask_ops.place_on_canvas(
        mask_trim, (fh, fw), lua_shift(mtext), lua_num(mtext, "scale")).astype(np.float32)
    inside = (mask_full[:, :, 3] > 0)[:, :, None]

    tiers = parse_tiers(args.tiers)
    if args.tier:
        tiers = {args.tier: tiers[args.tier]}
    os.makedirs(args.out, exist_ok=True)

    def glow(img, contrib):
        out = img.copy()
        out[:, :, :3] = np.clip(out[:, :, :3] + contrib, 0, 255)
        return out

    for n, tint in tiers.items():
        t3 = np.array(tint[:3])
        masked = composite(base, mask_full, tint)
        e = em[:, :, :3] * args.boost
        panels = [on_bg(masked), on_bg(glow(masked, e)),
                  on_bg(glow(masked, e * t3)),
                  on_bg(glow(masked, np.where(inside, e * t3, e)))]
        gap = 10
        h = panels[0].shape[0]
        strip = np.full((h, sum(p.shape[1] for p in panels) + gap * 3, 3), 18, np.uint8)
        x = 0
        for p in panels:
            strip[:, x:x + p.shape[1]] = p[:, :, :3]
            x += p.shape[1] + gap
        outp = os.path.join(args.out, f"emission-tier{n}.png")
        Image.fromarray(strip, "RGB").save(outp)
    print(f"wrote {len(tiers)} strip(s) to {args.out} "
          f"(boost {args.boost}); panels: 1 no-glow | 2 current/untinted | "
          "3 whole-tinted | 4 mask-only-tinted")


def cmd_split_emission(args):
    """Split the packed emission into two frame folders by the stencil region:
    `outside` (natural) and `masked` (the part to tint per tier). Pack both with
    Spritter as <src>-emission-outside and <src>-emission-mask."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    em_sheet = os.path.join(repo, "graphics", "entity", args.source,
                            f"{args.source}-emission.png")
    if not os.path.exists(em_sheet):
        sys.exit(f"no emission sheet: {em_sheet}")
    t = open(os.path.splitext(em_sheet)[0] + ".lua").read()
    fw, fh = int(lua_num(t, "width")), int(lua_num(t, "height"))
    n = int(lua_num(t, "sprite_count"))

    st = Image.open(args.stencil).convert("RGBA")
    if st.size != (fw, fh):
        st = st.resize((fw, fh), Image.NEAREST)
    sta = np.asarray(st, dtype=np.float32)
    cov = mask_ops.feather_coverage(mask_ops.stencil_selection(sta), args.feather)

    os.makedirs(args.out_natural, exist_ok=True)
    os.makedirs(args.out_masked, exist_ok=True)
    for i in range(n):
        em, _ = _extract_frame(em_sheet, i)
        outside, masked = mask_ops.split_emission_frame(em, cov)
        name = f"{i:04d}.png"
        Image.fromarray(outside, "RGBA").save(os.path.join(args.out_natural, name))
        Image.fromarray(masked, "RGBA").save(os.path.join(args.out_masked, name))
    print(f"split {n} emission frames -> {args.out_natural} (natural) + "
          f"{args.out_masked} (masked); pack both with Spritter")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("frame", help="extract one frame from a packed sheet")
    f.add_argument("--sheet", required=True)
    f.add_argument("--index", type=int, default=0)
    f.add_argument("--out", required=True)
    f.add_argument("--fw", type=int, help="frame width (else read sibling .lua)")
    f.add_argument("--fh", type=int, help="frame height")
    f.add_argument("--cols", type=int, help="frames per row (line_length)")
    f.set_defaults(func=cmd_frame)

    di = sub.add_parser("derive-icon", help="make tinted icon pair from frame+mask")
    di.add_argument("--frame", required=True, help="a building base frame")
    di.add_argument("--mask", required=True, help="the matching mask frame")
    di.add_argument("--source", required=True, help="source name, e.g. chemical-stager")
    di.add_argument("--outdir", required=True, help="e.g. graphics/icon/chemical-stager")
    di.add_argument("--size", type=int, default=64)
    di.set_defaults(func=cmd_derive_icon)

    b = sub.add_parser("bootstrap", help="make a binary stencil from the base (headless)")
    b.add_argument("--base", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--rect", action="append", metavar="X,Y,W,H",
                   help="rectangular region (repeatable)")
    b.add_argument("--near", metavar="R,G,B", help="select pixels near this colour")
    b.add_argument("--tol", type=float, default=50, help="colour distance for --near")
    b.set_defaults(func=cmd_bootstrap)

    p = sub.add_parser("preview", help="composite base + tinted mask per tier")
    p.add_argument("--base", required=True)
    p.add_argument("--mask", required=True)
    p.add_argument("--out", default="/tmp/nvo-tier-preview")
    p.add_argument("--tiers", default=os.path.join(os.path.dirname(__file__), "..", "lib", "tiers.lua"))
    p.set_defaults(func=cmd_preview)

    pa = sub.add_parser("preview-anim",
                        help="animated tier preview: a GIF per tier + combined")
    pa.add_argument("--frames", required=True,
                    help="folder of base frame PNGs (e.g. .work/<src>/base)")
    pa.add_argument("--mask", required=True,
                    help="baked mask: a single PNG or a folder of mask frames")
    pa.add_argument("--out", default="/tmp/nvo-tier-anim")
    pa.add_argument("--fps", type=float, default=20)
    pa.add_argument("--scale", type=float, default=1.0,
                    help="downscale GIFs (e.g. 0.5 for smaller files)")
    pa.add_argument("--tiers", default=os.path.join(os.path.dirname(__file__), "..", "lib", "tiers.lua"))
    pa.set_defaults(func=cmd_preview_anim)

    pe = sub.add_parser("preview-emission",
                        help="compare glow-vs-tint treatments (from graphics/)")
    pe.add_argument("--source", required=True, help="e.g. chemical-stager")
    pe.add_argument("--frame", type=int, default=0, help="animation frame to use")
    pe.add_argument("--tier", type=int, help="only this tier (default: all)")
    pe.add_argument("--boost", type=float, default=2.5,
                    help="amplify emission so the effect is visible (default 2.5)")
    pe.add_argument("--out", default="/tmp/nvo-emission-preview")
    pe.add_argument("--tiers", default=os.path.join(os.path.dirname(__file__), "..", "lib", "tiers.lua"))
    pe.set_defaults(func=cmd_preview_emission)

    se = sub.add_parser("split-emission",
                        help="split packed emission into outside+masked frame folders")
    se.add_argument("--source", required=True, help="e.g. chemical-stager")
    se.add_argument("--stencil", required=True, help="the building's stencil PNG")
    se.add_argument("--feather", type=float, default=1.0,
                    help="soften the split boundary, px (default 1.0)")
    se.add_argument("--out-natural", required=True, dest="out_natural")
    se.add_argument("--out-masked", required=True, dest="out_masked")
    se.set_defaults(func=cmd_split_emission)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
