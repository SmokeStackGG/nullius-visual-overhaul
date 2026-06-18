"""Tests for mask_ops: edge-aware selection, feathering, and cleanup."""
import numpy as np

from mask_ops import (sobel_edges, edge_aware_region, feather_coverage,
                      despeckle, fill_holes, smooth, place_on_canvas,
                      split_emission_frame, stencil_selection)


def _uniform_with_seam():
    """9-wide image, uniform colour 100 except a 1px seam at x=4. The seam is
    within colour tolerance (euclidean dist ~43 < 50) but is a strong gradient."""
    rgb = np.full((5, 9, 3), 100.0, dtype=np.float32)
    rgb[:, 4, :] = 125.0
    alpha = np.full((5, 9), 255.0, dtype=np.float32)
    return rgb, alpha


def test_plain_flood_crosses_a_seam_that_is_within_tolerance():
    rgb, alpha = _uniform_with_seam()
    region = edge_aware_region(rgb, alpha, (2, 2), tol=50)  # no edge map
    assert region[2, 2] and region[2, 6]      # fills both sides of the seam


def test_edge_aware_flood_stops_at_the_seam():
    rgb, alpha = _uniform_with_seam()
    edges = sobel_edges(rgb)
    region = edge_aware_region(rgb, alpha, (2, 2), tol=50,
                              edges=edges, edge_thr=0.5)
    assert region[2, 2]                        # seed side selected
    assert not region[2, 6]                    # did not cross the seam


def test_by_colour_mode_ignores_connectivity():
    rgb, alpha = _uniform_with_seam()
    region = edge_aware_region(rgb, alpha, (2, 2), tol=5, contiguous=False)
    assert region[2, 0] and region[2, 8]       # all colour-matching px, both sides
    assert not region[2, 4]                     # the seam colour is out of tol


def test_feather_coverage_is_binary_when_disabled():
    sel = np.zeros((5, 5), bool); sel[1:4, 1:4] = True
    cov = feather_coverage(sel, 0)
    assert cov.dtype == np.float32
    assert set(np.unique(cov)).issubset({0.0, 1.0})


def test_feather_coverage_softens_the_boundary():
    sel = np.zeros((9, 9), bool); sel[2:7, 2:7] = True
    cov = feather_coverage(sel, 1.0)
    assert cov[4, 4] > 0.9                      # interior stays solid
    assert 0.0 < cov[2, 4] < 1.0               # boundary is partial
    assert cov[0, 0] < 0.05                     # far outside ~empty


def test_despeckle_removes_lone_pixels():
    sel = np.zeros((7, 7), bool); sel[3, 3] = True
    assert not despeckle(sel).any()


def test_fill_holes_closes_an_interior_gap():
    sel = np.ones((7, 7), bool); sel[3, 3] = False
    assert fill_holes(sel)[3, 3]


def test_smooth_returns_a_boolean_mask_of_same_shape():
    sel = np.zeros((9, 9), bool); sel[2:7, 2:7] = True
    out = smooth(sel)
    assert out.shape == sel.shape and out.dtype == bool


def test_stencil_selection_is_white_opaque_pixels():
    st = np.array([[[255, 255, 255, 255],   # white opaque -> selected
                    [0, 0, 0, 0],           # transparent  -> no
                    [0, 0, 0, 255],         # black opaque -> no (rgb 0)
                    [255, 255, 255, 40]]],   # white, partial alpha -> selected
                  np.float32)
    sel = stencil_selection(st)
    assert sel.tolist() == [[True, False, False, True]]


def test_split_emission_partitions_rgb_by_coverage():
    em = np.array([[[100, 80, 40, 255]]], np.float32)
    cov = np.array([[0.25]], np.float32)
    outside, masked = split_emission_frame(em, cov)
    assert tuple(outside[0, 0]) == (75, 60, 30, 255)   # rgb * (1-cov)
    assert tuple(masked[0, 0]) == (25, 20, 10, 255)     # rgb * cov
    # additive contributions sum back to the original glow
    assert tuple(outside[0, 0, :3] + masked[0, 0, :3]) == (100, 80, 40)


def test_split_emission_endpoints():
    em = np.array([[[200, 100, 50, 255]], [[200, 100, 50, 255]]], np.float32)
    cov = np.array([[0.0], [1.0]], np.float32)
    outside, masked = split_emission_frame(em, cov)
    assert tuple(masked[0, 0, :3]) == (0, 0, 0)         # cov 0 -> nothing masked
    assert tuple(outside[1, 0, :3]) == (0, 0, 0)        # cov 1 -> nothing outside
    assert tuple(masked[1, 0, :3]) == (200, 100, 50)


def test_place_on_canvas_reproduces_spritter_shift():
    # A 276x188 trimmed sprite with Spritter shift (-45/64,-40.5/64) at scale 0.5
    # lands at (14,64) on a 394x397 canvas (matches the verified IoU=1.0 case).
    trimmed = np.full((188, 276, 4), 255, np.uint8)
    out = place_on_canvas(trimmed, (397, 394), (-45 / 64, -40.5 / 64), 0.5)
    assert out.shape == (397, 394, 4)
    ys, xs = np.where(out[:, :, 3] > 0)
    assert (xs.min(), ys.min()) == (14, 64)
    assert (xs.max(), ys.max()) == (14 + 276 - 1, 64 + 188 - 1)
