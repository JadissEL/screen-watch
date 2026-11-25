"""save_frame_to / path export."""

from __future__ import annotations

from pathlib import Path

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import load_settings
from screen_watch.pipeline.frame_store import FrameStore
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.service import ScreenWatchService, reset_service


def test_save_frame_to_tmp(tmp_path: Path, monkeypatch) -> None:
    reset_service()
    settings = load_settings(backend="mss")  # factory may ignore; we inject mock
    store = FrameStore()
    backend = MockBackend()
    daemon = WatchDaemon(backend, store, settings)
    svc = ScreenWatchService(
        settings=settings,
        store=store,
        daemon=daemon,
        backend_name=backend.name,
    )

    def _fake_create(_settings=None):
        return backend

    monkeypatch.setattr("screen_watch.service.create_backend", _fake_create)
    out = tmp_path / "nested" / "shot.jpg"
    meta = svc.save_frame_to(out, force_capture=True)
    assert meta["ok"] is True
    assert out.exists()
    assert out.stat().st_size == meta["bytes"] > 0
    reset_service()
