"""Bounding-box helpers for guided region focus."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BBox:
    """Axis-aligned box in screen/image pixel coordinates."""

    x: int
    y: int
    width: int
    height: int

    def clamp(self, max_w: int, max_h: int) -> BBox:
        x = max(0, min(self.x, max_w - 1))
        y = max(0, min(self.y, max_h - 1))
        w = max(1, min(self.width, max_w - x))
        h = max(1, min(self.height, max_h - y))
        return BBox(x, y, w, h)


def normalize_bbox(x1: int, y1: int, x2: int, y2: int) -> BBox:
    """Build a BBox from two corners (any order)."""
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)
    return BBox(left, top, max(1, right - left), max(1, bottom - top))


def crop_rgb(rgb: bytes, width: int, height: int, box: BBox) -> tuple[bytes, int, int]:
    """Crop packed RGB bytes; returns (rgb, w, h)."""
    box = box.clamp(width, height)
    from PIL import Image

    img = Image.frombytes("RGB", (width, height), rgb)
    cropped = img.crop((box.x, box.y, box.x + box.width, box.y + box.height))
    return cropped.tobytes(), cropped.width, cropped.height
