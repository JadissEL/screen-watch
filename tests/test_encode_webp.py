"""Optional WebP encode path."""

from __future__ import annotations

from screen_watch.capture.base import RawFrame
from screen_watch.config import Settings, load_settings
from screen_watch.pipeline.encode import encode_image, sniff_format
from screen_watch.pipeline.process import process_raw_frame


def test_encode_webp_magic() -> None:
    rgb = bytes([10, 20, 30] * (16 * 12))
    data = encode_image(rgb, 16, 12, quality=50, image_format="webp")
    assert sniff_format(data) == "webp"


def test_process_raw_frame_webp() -> None:
    settings = Settings(
        max_width=64,
        max_height=48,
        jpeg_quality=40,
        image_format="webp",
        min_capture_interval_s=0.0,
    )
    raw = RawFrame(
        width=32,
        height=24,
        rgb=bytes([40, 50, 60] * (32 * 24)),
        timestamp_ms=1.0,
        display_id=1,
        backend="mock",
    )
    encoded, _thumb = process_raw_frame(raw, settings, previous_thumb=None, skip_change_detect=True)
    assert encoded.image_format == "webp"
    assert sniff_format(encoded.jpeg) == "webp"


def test_load_settings_image_format(monkeypatch) -> None:
    monkeypatch.setenv("SCREEN_WATCH_IMAGE_FORMAT", "webp")
    s = load_settings()
    assert s.image_format == "webp"
