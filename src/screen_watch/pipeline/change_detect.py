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
) -> tuple[bool, Image.Image, float]:
    """
    Return (changed, new_thumb, mean_abs_diff_score).

    Score is 0..255 mean absolute grayscale thumb difference (0 if first frame).
    If previous_thumb is None, always treat as changed.
    """
    thumb = _thumb_gray(rgb, width, height)
    if previous_thumb is None:
        return True, thumb, 0.0
    diff = mean_abs_diff(thumb, previous_thumb)
    return diff >= threshold, thumb, diff


def change_bbox(
    previous: Image.Image,
    current: Image.Image,
    *,
    frame_width: int,
    frame_height: int,
    pixel_threshold: int = 12,
    pad: float = 0.04,
) -> dict[str, int] | None:
    """
    Bounding box of changed pixels, mapped into ``frame_width`` × ``frame_height``.

    Images are compared as grayscale (resized to a common thumb). Returns
    ``{x, y, width, height}`` or ``None`` if nothing exceeds ``pixel_threshold``.
    """
    tw, th = 64, 64
    a = previous.convert("L").resize((tw, th), Image.Resampling.BILINEAR)
    b = current.convert("L").resize((tw, th), Image.Resampling.BILINEAR)
    if hasattr(a, "get_flattened_data"):
        pa = list(a.get_flattened_data())  # type: ignore[attr-defined]
        pb = list(b.get_flattened_data())  # type: ignore[attr-defined]
    else:  # pragma: no cover
        pa = list(a.getdata())
        pb = list(b.getdata())
    ys: list[int] = []
    xs: list[int] = []
    for i, (x, y) in enumerate(zip(pa, pb, strict=True)):
        if abs(int(x) - int(y)) >= pixel_threshold:
            ys.append(i // tw)
            xs.append(i % tw)
    if not xs:
        return None
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    # Inclusive thumb cells → frame pixels
    x0 = int(min_x / tw * frame_width)
    x1 = int((max_x + 1) / tw * frame_width)
    y0 = int(min_y / th * frame_height)
    y1 = int((max_y + 1) / th * frame_height)
    pad_x = int(frame_width * pad)
    pad_y = int(frame_height * pad)
    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(frame_width, x1 + pad_x)
    y1 = min(frame_height, y1 + pad_y)
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    return {"x": x0, "y": y0, "width": w, "height": h}
