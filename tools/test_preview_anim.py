"""Tests for the animated-preview frame builders in mask_tool."""
import numpy as np

from mask_tool import anim_tier_frames, anim_combined_frames


def _frames(n, h, w, val):
    return [np.full((h, w, 4), val, dtype=np.float32) for _ in range(n)]


def test_tier_frames_match_base_frame_count():
    base = _frames(5, 8, 8, 100)
    mask = _frames(5, 8, 8, 200)
    out = anim_tier_frames(base, mask, (1.0, 0.0, 0.0, 1.0))
    assert len(out) == 5
    assert out[0].shape == (8, 8, 3)
    assert out[0].dtype == np.uint8


def test_mask_cycles_when_shorter_than_base():
    base = _frames(4, 8, 8, 100)
    mask = _frames(1, 8, 8, 200)          # single static mask frame
    out = anim_tier_frames(base, mask, (1.0, 1.0, 1.0, 1.0))
    assert len(out) == 4                  # cycled across all base frames


def test_scale_resizes_output_frames():
    base = _frames(2, 10, 20, 100)
    mask = _frames(2, 10, 20, 200)
    out = anim_tier_frames(base, mask, (1.0, 1.0, 1.0, 1.0), scale=0.5)
    assert out[0].shape == (5, 10, 3)


def test_combined_frames_lay_panels_side_by_side():
    a = [np.zeros((6, 4, 3), np.uint8) for _ in range(3)]
    b = [np.zeros((6, 5, 3), np.uint8) for _ in range(3)]
    gap = 2
    out = anim_combined_frames([a, b], gap=gap, bg=20)
    assert len(out) == 3
    assert out[0].shape == (6, 4 + 5 + gap, 3)
