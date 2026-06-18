#!/usr/bin/env python3
"""Apply a binary stencil across a folder of base frames to bake the tier mask.

The stencil (white = paint region, transparent elsewhere) is authored ONCE on a
single base frame with tools/mask_ui.py. This script stamps it onto every base
frame, copying the base's grayscale luminance inside the region (so per-frame
shading shows through the tier tint) and leaving everything else transparent.
The result is a folder of mask frames ready for Spritter:

  # 1. explode the base sheet into frames (see README)
  spritter split <src>-hr-animation-1.png 10 10 .work/<src>/base

  # 2. author a stencil on one frame (GUI) and export stencil.png

  # 3. bake the mask across every frame
  python3 tools/apply_stencil.py \\
      --stencil stencil.png --frames .work/<src>/base --out .work/<src>/mask

  # 4. pack it like any other layer; the source folder name supplies the suffix
  spritter spritesheet -l -t 64 .work/<src>/mask graphics/entity/<src> -p <src>-

White = paint region; transparent elsewhere. The loader picks the packed
<src>-mask.png up via the mask/color/paint alias and tints it per tier.
"""
import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

from mask_ops import LUMA, feather_coverage, stencil_selection as _selected


def fit_stencil(stencil, shape):
    """Resize a stencil (H,W,4 array) to (h, w) of `shape` with nearest sampling
    so the binary edges stay crisp. Returns a float32 (h,w,4) array."""
    h, w = shape[0], shape[1]
    if stencil.shape[0] == h and stencil.shape[1] == w:
        return stencil
    img = Image.fromarray(stencil.astype(np.uint8), "RGBA").resize((w, h), Image.NEAREST)
    return np.asarray(img, dtype=np.float32)


def apply(stencil, frame, brighten=1.3, solid=False, feather=0.0, peel=None):
    """Stamp `stencil` onto a base `frame`. Both are (H,W,4) arrays of the same
    size. Inside the painted region: grayscale luma * brighten (or flat white if
    solid); outside: transparent. `feather` (px) anti-aliases the boundary by
    modulating alpha with a soft coverage ramp.

    `peel` is an optional (lo, hi) pair in 0..1. When set, the mask alpha fades
    out in the region's darker pixels so the bare base art shows through there
    (the "paint has peeled off the grime" look): the region's luminance is
    percentile-normalised to 0..1 and run through smoothstep(lo, hi), so pixels
    below `lo` lose all paint and pixels above `hi` keep it fully. Returns uint8
    RGBA."""
    stencil = np.asarray(stencil, dtype=np.float32)
    frame = np.asarray(frame, dtype=np.float32)
    sel = _selected(stencil)
    cov = feather_coverage(sel, feather)      # 0..1 coverage, soft if feather>0
    covered = cov > 0

    luma = (frame[:, :, :3] * LUMA).sum(axis=2)
    fill = np.full(frame.shape[:2], 255.0, dtype=np.float32) if solid \
        else np.clip(luma * brighten, 0, 255)

    alpha = frame[:, :, 3] * cov
    if peel is not None and covered.any():
        lo, hi = peel
        vals = luma[sel > 0]
        p10, p90 = np.percentile(vals, 10), np.percentile(vals, 90)
        n = np.clip((luma - p10) / max(1e-3, p90 - p10), 0, 1)   # 0=grime, 1=lit panel
        t = np.clip((n - lo) / max(1e-6, hi - lo), 0, 1)
        keep = t * t * (3 - 2 * t)                                # smoothstep
        alpha = alpha * keep

    out = np.zeros_like(frame)
    for ch in range(3):
        out[covered, ch] = fill[covered]
    out[:, :, 3] = alpha
    return out.astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stencil", required=True, help="binary stencil PNG")
    ap.add_argument("--frames", required=True, help="folder of base frame PNGs")
    ap.add_argument("--out", required=True, help="output folder for mask frames")
    ap.add_argument("--brighten", type=float, default=1.3,
                    help="lift grayscale so the tint reads (default 1.3)")
    ap.add_argument("--solid", action="store_true",
                    help="fill mask flat white instead of base grayscale")
    ap.add_argument("--feather", type=float, default=1.0,
                    help="anti-alias the mask edge, px (default 1.0; 0 = hard binary)")
    ap.add_argument("--peel", default=None, metavar="LO,HI",
                    help="fade paint out of dark/grimy pixels so bare metal shows "
                         "through (e.g. 0.15,0.55 = soft peel). Off by default.")
    args = ap.parse_args()

    peel = None
    if args.peel is not None:
        try:
            lo, hi = (float(x) for x in args.peel.split(","))
        except ValueError:
            sys.exit("--peel expects two comma-separated numbers, e.g. 0.15,0.55")
        peel = (lo, hi)

    frames = sorted(glob.glob(os.path.join(args.frames, "*.png")))
    if not frames:
        sys.exit(f"no PNG frames found in {args.frames}")
    stencil = np.asarray(Image.open(args.stencil).convert("RGBA"), dtype=np.float32)
    os.makedirs(args.out, exist_ok=True)

    for fp in frames:
        frame = np.asarray(Image.open(fp).convert("RGBA"), dtype=np.float32)
        st = fit_stencil(stencil, frame.shape)
        if st.shape[:2] != frame.shape[:2]:
            sys.exit(f"stencil {st.shape[:2]} != frame {frame.shape[:2]} for {fp}")
        out = apply(st, frame, brighten=args.brighten, solid=args.solid,
                    feather=args.feather, peel=peel)
        outp = os.path.join(args.out, os.path.basename(fp))
        Image.fromarray(out, "RGBA").save(outp)

    n_sel = int(_selected(fit_stencil(stencil, (frame.shape[0], frame.shape[1]))).sum())
    print(f"wrote {len(frames)} mask frames to {args.out}  ({n_sel} px selected per frame)")


if __name__ == "__main__":
    main()
