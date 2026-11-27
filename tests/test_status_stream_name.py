"""Watch status exposes FramePump stream_name."""

from __future__ import annotations

import time

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService


def test_status_includes_stream_name() -> None:
    settings = Settings(
        max_width=80,
        max_height=60,
        jpeg_quality=40,
        fps=5.0,
        idle_backoff=False,
        min_capture_interval_s=0.0,
    )
    store = FrameStore(history_size=4)
    daemon = WatchDaemon(MockBackend(160, 90), store, settings)
    svc = ScreenWatchService(
        settings=settings,
        store=store,
        daemon=daemon,
        backend_name="mock",
    )
    assert svc.status()["stream_name"] is None
    assert daemon.start() is True
    deadline = time.time() + 2.0
    while time.time() < deadline and svc.status().get("stream_name") is None:
        time.sleep(0.05)
    status = svc.status()
    assert status["stream_name"] is not None
    assert str(status["stream_name"]).startswith("snapshot:")
    assert daemon.stop() is True
