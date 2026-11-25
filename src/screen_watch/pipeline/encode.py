"""JPEG encoding for agent-bound frames."""

from __future__ import annotations

import io

from PIL import Image


def encode_jpeg(rgb: bytes, width: int, height: int, quality: int = 60) -> bytes:
    """Encode packed RGB bytes as JPEG."""
    q = max(1, min(95, int(quality)))
    img = Image.frombytes("RGB", (width, height), rgb)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=q, optimize=True)
    return buf.getvalue()
