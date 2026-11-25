"""Cheap change detection to avoid re-sending identical frames."""

from __future__ import annotations

from PIL import Image, ImageFilter


def _thumb_gray(rgb: bytes, width: int, height: int, size: int = 32) -> Image.Image:
    img = Image.frombytes("RGB", (width, height), rgb)
    img = img.resize((size, size), Image.Resampling.BILINEAR).convert("L")
    return img.filter(ImageFilter.BoxBlur(1))


def mean_abs_diff(a: Image.Image, b: Image.Image) -> float:
    """Mean absolute pixel difference in 0..255."""
    if a.size != b.size:
        b = b.resize(a.size, Image.Resampling.BILINEAR)
    if hasattr(a, "get_flattened_data"):
        pa = list(a.get_flattened_data())  # type: ignore[attr-defined]
        pb = list(b.get_flattened_data())  # type: ignore[attr-defined]
    else:  # pragma: no cover
        pa = list(a.getdata())
        pb = list(b.getdata())
    if not pa:
        return 0.0
    total = sum(abs(int(x) - int(y)) for x, y in zip(pa, pb, strict=True))
    return total / len(pa)


def frames_changed(
    rgb: bytes,
    width: int,
    height: int,
    previous_thumb: Image.Image | None,
    threshold: float,
) -> tuple[bool, Image.Image]:
    """
    Return (changed, new_thumb).

    If previous_thumb is None, always treat as changed.
    """
    thumb = _thumb_gray(rgb, width, height)
    if previous_thumb is None:
        return True, thumb
    diff = mean_abs_diff(thumb, previous_thumb)
    return diff >= threshold, thumb
