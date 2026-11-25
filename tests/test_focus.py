"""Guided region focus helpers."""

from __future__ import annotations

from screen_watch.focus.region import BBox, crop_rgb, normalize_bbox


def test_normalize_bbox_any_order() -> None:
    box = normalize_bbox(100, 50, 10, 80)
    assert box == BBox(10, 50, 90, 30)


def test_crop_rgb() -> None:
    # 4x2 image, solid rows
    row0 = bytes([255, 0, 0] * 4)
    row1 = bytes([0, 255, 0] * 4)
    rgb = row0 + row1
    out, w, h = crop_rgb(rgb, 4, 2, BBox(1, 0, 2, 1))
    assert w == 2 and h == 1
    assert out == bytes([255, 0, 0, 255, 0, 0])


def test_clamp() -> None:
    box = BBox(90, 90, 50, 50).clamp(100, 100)
    assert box.x == 90 and box.y == 90
    assert box.width == 10 and box.height == 10
