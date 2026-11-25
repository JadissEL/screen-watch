"""Resize frames to fit within max width/height."""

from __future__ import annotations

from PIL import Image

from screen_watch.capture.base import RawFrame


def downsample_rgb(
    frame: RawFrame,
    max_width: int,
    max_height: int,
) -> tuple[bytes, int, int]:
    """
    Fit frame inside max_width × max_height, preserving aspect ratio.

    Returns (rgb_bytes, width, height).
    """
    if frame.width <= max_width and frame.height <= max_height:
        return frame.rgb, frame.width, frame.height

    img = Image.frombytes("RGB", (frame.width, frame.height), frame.rgb)
    img.thumbnail((max_width, max_height), Image.Resampling.BILINEAR)
    out = img.tobytes()
    return out, img.width, img.height
