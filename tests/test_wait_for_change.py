"""wait_for_change service helper."""

from __future__ import annotations

import threading
import time

from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings
from screen_watch.daemon.watcher import WatchDaemon
from screen_watch.pipeline.frame_store import EncodedFrame, FrameStore
from screen_watch.service import ScreenWatchService


def _svc_with_store() -> ScreenWatchService:
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

    def _no_display_grab(**_kwargs: object) -> EncodedFrame:
        frame = svc.store.get()
        if frame is None:
            raise RuntimeError("no frame")
        return frame

    svc.capture_once = _no_display_grab  # type: ignore[method-assign]
    return svc


def test_wait_for_change_detects_new_hash() -> None:
    svc = _svc_with_store()
    svc.store.set(
        EncodedFrame(
            jpeg=b"\xff\xd8\xff\xd9",
            width=10,
            height=10,
            timestamp_ms=time.time() * 1000.0,
            content_hash="oldhash",
            unchanged=False,
            backend="mock",
            display_id=0,
            change_score=0.0,
        )
    )

    def _flip() -> None:
        time.sleep(0.15)
        svc.store.set(
            EncodedFrame(
                jpeg=b"\xff\xd8\xff\xd9",
                width=10,
                height=10,
                timestamp_ms=time.time() * 1000.0,
                content_hash="newhash",
                unchanged=False,
                backend="mock",
                display_id=0,
                change_score=12.0,
            )
        )

    threading.Thread(target=_flip, daemon=True).start()
    result = svc.wait_for_change(since_hash="oldhash", timeout_s=2.0, poll_s=0.05)
    assert result["ok"] is True
    assert result["changed"] is True
    assert result["timed_out"] is False
    assert result["content_hash"] == "newhash"


def test_wait_for_change_timeout() -> None:
    svc = _svc_with_store()
    svc.store.set(
        EncodedFrame(
            jpeg=b"\xff\xd8\xff\xd9",
            width=10,
            height=10,
            timestamp_ms=time.time() * 1000.0,
            content_hash="same",
            unchanged=True,
            backend="mock",
            display_id=0,
        )
    )
    result = svc.wait_for_change(since_hash="same", timeout_s=0.3, poll_s=0.05)
    assert result["ok"] is True
    assert result["changed"] is False
    assert result["timed_out"] is True
