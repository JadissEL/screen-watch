"""WatchDaemon uses FramePump end-to-end."""

from __future__ import annotations

import time

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import FrameStore


def test_watch_daemon_fills_store() -> None:
    settings = Settings(
        max_width=80,
        max_height=60,
        jpeg_quality=40,
        fps=5.0,
        idle_backoff=False,
        min_capture_interval_s=0.0,
    )
    store = FrameStore(history_size=8)
    daemon = WatchDaemon(MockBackend(160, 90), store, settings)
    assert daemon.start() is True
    deadline = time.time() + 2.0
    while time.time() < deadline and store.get() is None:
        time.sleep(0.05)
    frame = store.get()
    assert frame is not None
    assert frame.jpeg[:2] == b"\xff\xd8" or frame.unchanged
    assert store.history_len() >= 1
    assert daemon.stop() is True
    assert daemon.running is False
