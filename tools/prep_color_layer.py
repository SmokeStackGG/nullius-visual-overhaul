#!/usr/bin/env python3
"""Desaturate a pre-painted color layer into a neutral grayscale tier/recipe mask.

Some asset packs ship the artist's actual paint-layer exports (e.g. the oxidizer's
oxidizer-hr-color1 / oxidizer-hr-color2). Unlike the hand-authored stencil masks,
these already define the paint REGION via their alpha -- but their RGB is a tinted
reference tone (a low-saturation blue/teal), not neutral gray. Tinting them
directly (multiply tint x colored) muddies the hue.

This script neutralizes hue: each pixel's RGB is replaced by its luminance
(so per-frame shading shows through the tint) and the original alpha is kept
(so the region and its soft edges are preserved). The packed result is then
tinted per tier (color1 -> -mask) or per recipe (color2 -> -recipe) by the loader.

  # 1. explode the color sheet into frames (same grid as the base animation)
  spritter split oxidizer-hr-color1-1.png 8 8 .work/oxidizer/color1

  # 2. neutralize hue -> grayscale luma + alpha
  python3 tools/prep_color_layer.py --frames .work/oxidizer/color1 --out .work/oxidizer/mask

  # 3. pack like any other layer; the folder name supplies the suffix
  spritter spritesheet -l -t 64 .work/oxidizer/mask graphics/entity/oxidizer -p oxidizer-

This is the color-layer analogue of apply_stencil.py: that derives luma INSIDE a
painted stencil; this derives luma from an already-painted (alpha-defined) layer.
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

from mask_ops import LUMA


def desaturate(frame, brighten=1.3, gamma=1.0):
    """Replace `frame` RGB with its luminance (x brighten), keep alpha.
    `frame` is an (H,W,4) array. Returns uint8 RGBA. gamma != 1 reshapes the
    luma ramp before brighten (gamma<1 lifts midtones)."""
    frame = np.asarray(frame, dtype=np.float32)
    luma = (frame[:, :, :3] * LUMA).sum(axis=2) / 255.0   # 0..1
    if gamma != 1.0:
        luma = np.power(np.clip(luma, 0, 1), gamma)
    gray = np.clip(luma * brighten * 255.0, 0, 255)
    out = np.zeros_like(frame)
    for ch in range(3):
        out[:, :, ch] = gray
    out[:, :, 3] = frame[:, :, 3]
    return out.astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", required=True, help="folder of color-layer frame PNGs")
    ap.add_argument("--out", required=True, help="output folder for grayscale frames")
    ap.add_argument("--brighten", type=float, default=1.3,
                    help="lift grayscale so the tint reads (default 1.3)")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help="reshape the luma ramp before brighten (default 1.0)")
    args = ap.parse_args()

    frames = sorted(glob.glob(os.path.join(args.frames, "*.png")))
    if not frames:
        sys.exit(f"no PNG frames found in {args.frames}")
    os.makedirs(args.out, exist_ok=True)

    kept = 0
    for fp in frames:
        frame = np.asarray(Image.open(fp).convert("RGBA"), dtype=np.float32)
        out = desaturate(frame, brighten=args.brighten, gamma=args.gamma)
        Image.fromarray(out, "RGBA").save(os.path.join(args.out, os.path.basename(fp)))
        kept += int((frame[:, :, 3] > 0).any())
    print(f"wrote {len(frames)} grayscale frames to {args.out}  "
          f"({kept} non-empty)")


if __name__ == "__main__":
    main()
