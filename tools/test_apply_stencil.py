"""Tests for apply_stencil's pure core (run: python3 -m pytest tools/test_apply_stencil.py)."""
import numpy as np
import pytest

from apply_stencil import apply, fit_stencil


def _rgba(r, g, b, a):
    return np.array([[[r, g, b, a]]], dtype=np.float32)


def test_pixel_inside_stencil_gets_base_luma_and_alpha():
    stencil = _rgba(255, 255, 255, 255)        # selected
    frame = _rgba(100, 150, 200, 200)
    out = apply(stencil, frame, brighten=1.0, solid=False)
    # truncated to uint8, matching the existing tools' .astype(np.uint8) convention
    luma = int(0.299 * 100 + 0.587 * 150 + 0.114 * 200)  # 140
    assert tuple(out[0, 0]) == (luma, luma, luma, 200)


def test_pixel_outside_stencil_is_fully_transparent():
    stencil = _rgba(0, 0, 0, 0)                 # not selected
    frame = _rgba(100, 150, 200, 255)
    out = apply(stencil, frame, brighten=1.0, solid=False)
    assert tuple(out[0, 0]) == (0, 0, 0, 0)


def test_solid_fills_white_not_luma():
    stencil = _rgba(255, 255, 255, 255)
    frame = _rgba(10, 20, 30, 128)
    out = apply(stencil, frame, brighten=1.0, solid=True)
    assert tuple(out[0, 0]) == (255, 255, 255, 128)


def test_brighten_clamps_at_255():
    stencil = _rgba(255, 255, 255, 255)
    frame = _rgba(255, 255, 255, 255)
    out = apply(stencil, frame, brighten=2.0, solid=False)
    assert tuple(out[0, 0]) == (255, 255, 255, 255)


def test_white_on_black_opaque_stencil_treated_as_binary():
    # A stencil saved as opaque white-on-black (alpha 255 everywhere) must
    # still select only the white pixels, not the black background.
    stencil = np.array([[[255, 255, 255, 255], [0, 0, 0, 255]]], dtype=np.float32)
    frame = np.array([[[100, 100, 100, 255], [100, 100, 100, 255]]], dtype=np.float32)
    out = apply(stencil, frame, brighten=1.0, solid=True)
    assert tuple(out[0, 0]) == (255, 255, 255, 255)   # white -> selected
    assert tuple(out[0, 1]) == (0, 0, 0, 0)           # black -> not selected


def test_feather_softens_boundary_alpha():
    # 9x9 opaque frame, 7x7 stencil block; feathering yields partial edge alpha.
    stencil = np.zeros((9, 9, 4), np.float32)
    stencil[1:8, 1:8] = (255, 255, 255, 255)
    frame = np.full((9, 9, 4), 255, np.float32)
    out = apply(stencil, frame, brighten=1.0, solid=True, feather=1.0)
    assert out[4, 4, 3] >= 250                 # interior stays solid
    assert 0 < out[1, 4, 3] < 255              # boundary alpha is partial
    assert out[1, 4, 0] == 255                 # but RGB fill still present there


def test_fit_stencil_resizes_to_target_shape():
    stencil = np.full((2, 2, 4), 255, dtype=np.float32)
    fitted = fit_stencil(stencil, (4, 6))
    assert fitted.shape == (4, 6, 4)
