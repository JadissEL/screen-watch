"""Capture bench helper."""

from __future__ import annotations

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService


def test_bench_with_mock(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(max_width=80, max_height=60, jpeg_quality=40, min_capture_interval_s=0.0)
    store = FrameStore()
    backend = MockBackend(160, 90)
    daemon = WatchDaemon(backend, store, settings)
    svc = ScreenWatchService(settings=settings, store=store, daemon=daemon, backend_name="mock")
    monkeypatch.setattr("screen_watch.service.create_backend", lambda _s=None: backend)
    out = svc.bench(iterations=3)
    assert out["iterations"] == 3
    assert out["ms_mean"] >= 0
    assert out["jpeg_bytes"] and out["jpeg_bytes"] > 0
