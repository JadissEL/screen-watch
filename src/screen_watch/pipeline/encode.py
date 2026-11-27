"""Image encoding for agent-bound frames (JPEG default, optional WebP)."""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image

ImageFormat = Literal["jpeg", "webp"]


def normalize_format(value: str | None) -> ImageFormat:
    raw = (value or "jpeg").strip().lower()
    if raw in {"webp", "image/webp"}:
        return "webp"
    return "jpeg"


def mime_for_format(fmt: ImageFormat) -> str:
    return "image/webp" if fmt == "webp" else "image/jpeg"


def extension_for_format(fmt: ImageFormat) -> str:
    return "webp" if fmt == "webp" else "jpg"


def sniff_format(data: bytes) -> ImageFormat | None:
    """Detect jpeg/webp from magic bytes."""
    if len(data) >= 2 and data[:2] == b"\xff\xd8":
        return "jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def encode_jpeg(rgb: bytes, width: int, height: int, quality: int = 60) -> bytes:
    """Encode packed RGB bytes as JPEG."""
    return encode_image(rgb, width, height, quality=quality, image_format="jpeg")


def encode_image(
    rgb: bytes,
    width: int,
    height: int,
    *,
    quality: int = 60,
    image_format: ImageFormat | str = "jpeg",
) -> bytes:
    """Encode packed RGB bytes as JPEG or WebP."""
    fmt = normalize_format(str(image_format))
    q = max(1, min(95, int(quality)))
    img = Image.frombytes("RGB", (width, height), rgb)
    buf = io.BytesIO()
    if fmt == "webp":
        img.save(buf, format="WEBP", quality=q, method=4)
    else:
        img.save(buf, format="JPEG", quality=q, optimize=True)
    return buf.getvalue()
