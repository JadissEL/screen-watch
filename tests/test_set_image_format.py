"""Runtime image_format switching."""

from __future__ import annotations

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService


def test_set_image_format() -> None:
    settings = Settings(image_format="jpeg", max_width=64, max_height=48)
    store = FrameStore(history_size=2)
    svc = ScreenWatchService(
        settings=settings,
        store=store,
        daemon=WatchDaemon(MockBackend(80, 60), store, settings),
        backend_name="mock",
    )
    out = svc.set_image_format("webp")
    assert out["ok"] is True
    assert out["image_format"] == "webp"
    assert svc.settings.image_format == "webp"
    assert svc.set_image_format("JPEG")["image_format"] == "jpeg"
