"""change_bbox + get_change_region helpers."""

from __future__ import annotations

from io import BytesIO

from PIL import Image

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.change_detect import change_bbox
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService


def test_change_bbox_detects_corner() -> None:
    a = Image.new("RGB", (100, 80), (10, 10, 10))
    b = a.copy()
    for x in range(70, 100):
        for y in range(50, 80):
            b.putpixel((x, y), (200, 200, 200))
    box = change_bbox(a, b, frame_width=100, frame_height=80, pixel_threshold=20, pad=0.0)
    assert box is not None
    assert box["x"] >= 60
    assert box["y"] >= 40
    assert box["x"] + box["width"] <= 100
    assert box["y"] + box["height"] <= 80


def test_get_change_region_seeds_then_crops() -> None:
    settings = Settings(
        max_width=120,
        max_height=90,
        jpeg_quality=50,
        fps=5.0,
        idle_backoff=False,
        min_capture_interval_s=0.0,
    )
    store = FrameStore(history_size=2)
    svc = ScreenWatchService(
        settings=settings,
        store=store,
        daemon=WatchDaemon(MockBackend(160, 90, rgb=(20, 20, 20)), store, settings),
        backend_name="mock",
    )

    dark = Image.new("RGB", (80, 60), (20, 20, 20))
    bright = Image.new("RGB", (80, 60), (20, 20, 20))
    for x in range(40, 80):
        for y in range(30, 60):
            bright.putpixel((x, y), (220, 220, 220))

    def _jpeg(img: Image.Image) -> bytes:
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=50)
        return buf.getvalue()

    import time

    from screen_watch.pipeline.frame_store import EncodedFrame

    def _set(jpeg: bytes, digest: str) -> None:
        store.set(
            EncodedFrame(
                jpeg=jpeg,
                width=80,
                height=60,
                timestamp_ms=time.time() * 1000.0,
                content_hash=digest,
                unchanged=False,
                backend="mock",
                display_id=0,
            )
        )

    _set(_jpeg(dark), "dark")
    first = svc.get_change_region(include_crop=True)
    assert first["seeded"] is True
    assert first["bbox"] is None

    _set(_jpeg(bright), "bright")
    second = svc.get_change_region(include_crop=True)
    assert second["seeded"] is False
    assert second["bbox"] is not None
    assert second["region_jpeg"][:2] == b"\xff\xd8"
