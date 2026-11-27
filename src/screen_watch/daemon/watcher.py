"""Background capture loop at capped FPS (via FramePump)."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from screen_watch.backoff import idle_wait_factor
from screen_watch.capture.loop import FramePump

if TYPE_CHECKING:
    from screen_watch.capture.base import CaptureBackend
    from screen_watch.config import Settings
    from screen_watch.pipeline.frame_store import FrameStore

logger = logging.getLogger(__name__)

# Re-export for older imports / tests
__all__ = ["WatchDaemon", "idle_wait_factor"]


class WatchDaemon:
    """Continuously capture → pipeline → FrameStore using ``FramePump``."""

    def __init__(
        self,
        backend: CaptureBackend,
        store: FrameStore,
        settings: Settings,
    ) -> None:
        self._backend = backend
        self._store = store
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._pump: FramePump | None = None
        self._last_error: str | None = None
        self._started_at: float | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def started_at(self) -> float | None:
        return self._started_at

    @property
    def unchanged_streak(self) -> int:
        return self._pump.unchanged_streak if self._pump is not None else 0

    @property
    def stream_name(self) -> str | None:
        return self._pump.stream_name if self._pump is not None else None

    def start(self) -> bool:
        """Start the loop. Idempotent. Returns True if newly started."""
        if self.running:
            return False
        self._stop.clear()
        self._started_at = time.time()
        self._pump = FramePump(self._backend, self._settings, stop_event=self._stop)
        self._thread = threading.Thread(target=self._run, name="screen-watch-daemon", daemon=True)
        self._thread.start()
        logger.info("Watch daemon started at %.2f FPS (FramePump)", self._settings.capped_fps())
        return True

    def stop(self) -> bool:
        """Stop the loop. Returns True if it was running."""
        if not self.running:
            return False
        self._stop.set()
        if self._pump is not None:
            self._pump.stop()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        self._pump = None
        logger.info("Watch daemon stopped")
        return True

    def _run(self) -> None:
        assert self._pump is not None
        try:
            for encoded in self._pump.frames():
                if self._stop.is_set():
                    break
                if encoded.unchanged:
                    prev = self._store.get()
                    if prev is not None and not encoded.jpeg:
                        encoded.jpeg = prev.jpeg
                        encoded.content_hash = prev.content_hash
                        encoded.width = prev.width
                        encoded.height = prev.height
                self._store.set(encoded)
                self._last_error = None
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("Watch daemon failed: %s", exc)
