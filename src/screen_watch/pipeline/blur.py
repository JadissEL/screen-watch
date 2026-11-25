"""Optional privacy blur / pixelation (off by default)."""

from __future__ import annotations

from PIL import Image


def pixelate_rgb(rgb: bytes, width: int, height: int, block: int = 16) -> bytes:
    """Pixelate the full frame by downscaling then nearest-neighbor upscaling."""
    b = max(2, int(block))
    img = Image.frombytes("RGB", (width, height), rgb)
    small_w = max(1, width // b)
    small_h = max(1, height // b)
    small = img.resize((small_w, small_h), Image.Resampling.BILINEAR)
    out = small.resize((width, height), Image.Resampling.NEAREST)
    return out.tobytes()
