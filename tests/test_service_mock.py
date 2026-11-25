"""Service path with mock capture (headless)."""

from __future__ import annotations

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.focus.region import BBox
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService


def test_capture_once_with_mock(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(max_width=160, max_height=90, jpeg_quality=50)
    store = FrameStore()
    backend = MockBackend(320, 180)
    daemon = WatchDaemon(backend, store, settings)
    svc = ScreenWatchService(settings=settings, store=store, daemon=daemon, backend_name="mock")

    monkeypatch.setattr("screen_watch.service.create_backend", lambda _s=None: backend)

    frame = svc.capture_once()
    assert frame.jpeg[:2] == b"\xff\xd8"
    assert frame.width <= 160
    assert frame.height <= 90


def test_capture_region_with_mock(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(max_width=200, max_height=200)
    store = FrameStore()
    backend = MockBackend(400, 300, rgb=(255, 0, 0))
    daemon = WatchDaemon(backend, store, settings)
    svc = ScreenWatchService(settings=settings, store=store, daemon=daemon, backend_name="mock")
    monkeypatch.setattr("screen_watch.service.create_backend", lambda _s=None: backend)

    result = svc.capture_region(BBox(10, 10, 80, 60), also_full_frame=False)
    assert result["region_jpeg"][:2] == b"\xff\xd8"
    assert result["gesture"]["width"] == 80
