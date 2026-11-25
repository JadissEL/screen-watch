"""set_display updates status."""

from __future__ import annotations

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.service import ScreenWatchService


def test_set_display() -> None:
    settings = Settings(display=None)
    store = FrameStore()
    backend = MockBackend()
    daemon = WatchDaemon(backend, store, settings)
    svc = ScreenWatchService(settings=settings, store=store, daemon=daemon, backend_name="mock")
    out = svc.set_display(2)
    assert out["ok"] is True
    assert svc.settings.display == 2
    assert svc.status()["display"] == 2
    svc.set_display(None)
    assert svc.settings.display is None
