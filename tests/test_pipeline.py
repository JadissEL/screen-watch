"""Unit tests for downsample, encode, change-detect, blur."""

from __future__ import annotations

from screen_watch.capture.base import RawFrame
from screen_watch.config import Settings
from screen_watch.pipeline.blur import pixelate_rgb
from screen_watch.pipeline.change_detect import frames_changed
from screen_watch.pipeline.downsample import downsample_rgb
from screen_watch.pipeline.encode import encode_jpeg
from screen_watch.pipeline.process import process_raw_frame


def _solid(w: int, h: int, rgb: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    r, g, b = rgb
    return bytes([r, g, b] * (w * h))


def test_downsample_fits_box() -> None:
    raw = RawFrame(1920, 1080, _solid(1920, 1080), 0.0, 1, "test")
    rgb, w, h = downsample_rgb(raw, 1280, 720)
    assert w <= 1280 and h <= 720
    assert len(rgb) == w * h * 3


def test_encode_jpeg_nonempty() -> None:
    rgb = _solid(64, 48)
    data = encode_jpeg(rgb, 64, 48, quality=60)
    assert data[:2] == b"\xff\xd8"
    assert len(data) > 50


def test_change_detect_identical() -> None:
    rgb = _solid(100, 80, (50, 50, 50))
    changed, thumb = frames_changed(rgb, 100, 80, None, threshold=2.0)
    assert changed is True
    changed2, _ = frames_changed(rgb, 100, 80, thumb, threshold=2.0)
    assert changed2 is False


def test_change_detect_different() -> None:
    a = _solid(100, 80, (0, 0, 0))
    b = _solid(100, 80, (255, 255, 255))
    _, thumb = frames_changed(a, 100, 80, None, threshold=2.0)
    changed, _ = frames_changed(b, 100, 80, thumb, threshold=2.0)
    assert changed is True


def test_pixelate_same_size() -> None:
    rgb = _solid(80, 60)
    out = pixelate_rgb(rgb, 80, 60, block=8)
    assert len(out) == len(rgb)


def test_process_raw_frame() -> None:
    raw = RawFrame(200, 100, _solid(200, 100, (1, 2, 3)), 123.0, 1, "test")
    settings = Settings(max_width=128, max_height=72, jpeg_quality=60)
    enc, thumb = process_raw_frame(raw, settings, skip_change_detect=True)
    assert enc.unchanged is False
    assert enc.jpeg[:2] == b"\xff\xd8"
    assert thumb is not None
