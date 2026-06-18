"""Pure (GUI-free) mask operations shared by the painter and the baker:
edge-aware selection, boundary feathering, and selection cleanup. Kept separate
from mask_ui.py so the logic is unit-testable without tkinter."""
import numpy as np
from scipy import ndimage

LUMA = np.array([0.299, 0.587, 0.114], dtype=np.float32)


def sobel_edges(rgb):
    """Normalized (0..1) Sobel gradient magnitude of an RGB image's luminance.
    High values mark seams/boundaries between panels."""
    g = (np.asarray(rgb, dtype=np.float32)[:, :, :3] * LUMA).sum(2)
    mag = np.hypot(ndimage.sobel(g, axis=1), ndimage.sobel(g, axis=0))
    return mag / (mag.max() + 1e-6)


def edge_aware_region(rgb, alpha, seed, tol, edges=None, edge_thr=None,
                      contiguous=True):
    """Select pixels near the seed colour. With `contiguous`, keep only the
    connected component containing the seed; if an `edges` map + `edge_thr` are
    given, the flood also stops at strong gradients (so it respects panel seams
    even when colour barely changes). Returns a boolean mask."""
    rgb = np.asarray(rgb, dtype=np.float32)[:, :, :3]
    alpha = np.asarray(alpha, dtype=np.float32)
    x, y = seed
    seed_col = rgb[y, x]
    similar = np.sqrt(((rgb - seed_col) ** 2).sum(2)) <= tol
    if alpha[y, x] > 0:                       # don't bleed into transparent
        similar &= alpha > 0
    if not contiguous:
        return similar

    passable = similar.copy()
    use_edges = edges is not None and edge_thr is not None
    if use_edges:
        passable &= np.asarray(edges) < edge_thr
        passable[y, x] = True                 # the seed is always passable
    lbl, _ = ndimage.label(passable)          # 4-connectivity
    if lbl[y, x] == 0:
        return np.zeros_like(similar)
    region = lbl == lbl[y, x]
    if use_edges:
        # reclaim the 1px seam ring bounding the region, staying within `similar`
        region = region | (ndimage.binary_dilation(region) & similar)
    return region


def feather_coverage(sel, feather):
    """Soft 0..1 coverage from a boolean selection. `feather` is the Gaussian
    sigma in pixels; <=0 returns a crisp binary coverage (the old behaviour)."""
    s = np.asarray(sel, dtype=np.float32)
    if feather <= 0:
        return s
    return np.clip(ndimage.gaussian_filter(s, sigma=feather), 0.0, 1.0).astype(np.float32)


def place_on_canvas(trimmed, canvas_hw, shift_xy, scale):
    """Reconstruct where a Spritter-trimmed sprite sits on the original frame
    canvas. `shift_xy` is the def's shift in tiles, `scale` its scale. Returns a
    (H,W,4) array of `trimmed`'s dtype with the sprite pasted at its true spot
    (the inverse of Spritter's trim+shift, so it re-aligns to the base frame)."""
    H, W = canvas_hw
    th, tw = trimmed.shape[:2]
    ppt = 32.0 / scale                       # source px per tile at this scale
    cx = W / 2.0 + shift_xy[0] * ppt
    cy = H / 2.0 + shift_xy[1] * ppt
    x0 = int(round(cx - tw / 2.0))
    y0 = int(round(cy - th / 2.0))
    out = np.zeros((H, W, 4), dtype=trimmed.dtype)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + tw), min(H, y0 + th)
    if dx1 > dx0 and dy1 > dy0:
        out[dy0:dy1, dx0:dx1] = trimmed[dy0 - y0:dy1 - y0, dx0 - x0:dx1 - x0]
    return out


def stencil_selection(stencil):
    """Boolean selection from a stencil image (H,W,4). Tolerant of both
    conventions: white+alpha (the painter export) and opaque white-on-black."""
    stencil = np.asarray(stencil, dtype=np.float32)
    return (stencil[:, :, 3] > 0) & (stencil[:, :, :3].max(axis=2) > 0)


def split_emission_frame(em, cov):
    """Split an emission frame (H,W,4) into two disjoint additive layers by mask
    coverage `cov` (H,W, 0..1): `outside` = rgb*(1-cov), `masked` = rgb*cov, both
    keeping the original alpha. As additive layers they sum back to the original
    glow, so tinting only `masked` recolours the glow inside the mask. Returns
    (outside, masked) as uint8 RGBA arrays."""
    em = np.asarray(em, dtype=np.float32)
    cov = np.asarray(cov, dtype=np.float32)[:, :, None]
    outside = em.copy()
    masked = em.copy()
    outside[:, :, :3] = em[:, :, :3] * (1.0 - cov[:, :, 0:1])
    masked[:, :, :3] = em[:, :, :3] * cov[:, :, 0:1]
    return outside.astype(np.uint8), masked.astype(np.uint8)


def despeckle(sel, size=1):
    """Remove isolated specks (binary opening)."""
    return ndimage.binary_opening(np.asarray(sel, bool), iterations=max(1, size))


def fill_holes(sel):
    """Fill enclosed holes in the selection."""
    return ndimage.binary_fill_holes(np.asarray(sel, bool))


def smooth(sel, size=1):
    """Smooth a jagged boundary (closing then opening)."""
    s = np.asarray(sel, bool)
    s = ndimage.binary_closing(s, iterations=max(1, size))
    return ndimage.binary_opening(s, iterations=max(1, size))
