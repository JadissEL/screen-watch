"""Compose downsample → blur → change-detect → JPEG."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from screen_watch.pipeline.blur import pixelate_rgb
from screen_watch.pipeline.change_detect import frames_changed
from screen_watch.pipeline.downsample import downsample_rgb
from screen_watch.pipeline.encode import encode_jpeg
from screen_watch.pipeline.frame_store import EncodedFrame

if TYPE_CHECKING:
    from PIL import Image

    from screen_watch.capture.base import RawFrame
    from screen_watch.config import Settings


def process_raw_frame(
    raw: RawFrame,
    settings: Settings,
    *,
    previous_thumb: Image.Image | None = None,
    force_blur: bool | None = None,
    skip_change_detect: bool = False,
) -> tuple[EncodedFrame, Image.Image]:
    """
    Run the full pipeline.

    Returns (encoded_frame, new_thumb). If unchanged, jpeg may be empty and
    unchanged=True (caller can re-use prior JPEG from the store).
    """
    rgb, w, h = downsample_rgb(raw, settings.max_width, settings.max_height)
    apply_blur = settings.blur if force_blur is None else force_blur
    if apply_blur:
        rgb = pixelate_rgb(rgb, w, h, settings.blur_block)

    if skip_change_detect:
        changed, thumb = True, None  # type: ignore[assignment]
        from screen_watch.pipeline.change_detect import _thumb_gray

        thumb = _thumb_gray(rgb, w, h)
        changed = True
    else:
        changed, thumb = frames_changed(rgb, w, h, previous_thumb, settings.change_threshold)

    if not changed:
        digest = hashlib.sha256(rgb).hexdigest()[:16]
        return (
            EncodedFrame(
                jpeg=b"",
                width=w,
                height=h,
                timestamp_ms=raw.timestamp_ms,
                content_hash=digest,
                unchanged=True,
                backend=raw.backend,
                display_id=raw.display_id,
                blur=apply_blur,
            ),
            thumb,
        )

    jpeg = encode_jpeg(rgb, w, h, settings.jpeg_quality)
    digest = hashlib.sha256(jpeg).hexdigest()[:16]
    return (
        EncodedFrame(
            jpeg=jpeg,
            width=w,
            height=h,
            timestamp_ms=raw.timestamp_ms,
            content_hash=digest,
            unchanged=False,
            backend=raw.backend,
            display_id=raw.display_id,
            blur=apply_blur,
        ),
        thumb,
    )
