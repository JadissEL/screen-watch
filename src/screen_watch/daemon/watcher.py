"""Background capture loop at capped FPS."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from screen_watch.pipeline.process import process_raw_frame

if TYPE_CHECKING:
    from PIL import Image

    from screen_watch.capture.base import CaptureBackend
    from screen_watch.config import Settings
    from screen_watch.pipeline.frame_store import FrameStore

logger = logging.getLogger(__name__)


class WatchDaemon:
    """Continuously capture → pipeline → FrameStore."""

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
        self._thumb: Image.Image | None = None
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

    def start(self) -> bool:
        """Start the loop. Idempotent. Returns True if newly started."""
        if self.running:
            return False
        self._stop.clear()
        self._started_at = time.time()
        self._thread = threading.Thread(target=self._run, name="screen-watch-daemon", daemon=True)
        self._thread.start()
        logger.info("Watch daemon started at %.2f FPS", self._settings.capped_fps())
        return True

    def stop(self) -> bool:
        """Stop the loop. Returns True if it was running."""
        if not self.running:
            return False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._thread = None
        logger.info("Watch daemon stopped")
        return True

    def _run(self) -> None:
        interval = 1.0 / self._settings.capped_fps()
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                raw = self._backend.grab(self._settings.display)
                encoded, self._thumb = process_raw_frame(
                    raw, self._settings, previous_thumb=self._thumb
                )
                if encoded.unchanged:
                    prev = self._store.get()
                    if prev is not None:
                        encoded.jpeg = prev.jpeg
                        encoded.content_hash = prev.content_hash
                        encoded.width = prev.width
                        encoded.height = prev.height
                    else:
                        # First frame must encode
                        encoded, self._thumb = process_raw_frame(
                            raw,
                            self._settings,
                            previous_thumb=None,
                            skip_change_detect=True,
                        )
                self._store.set(encoded)
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("Watch tick failed: %s", exc)
            elapsed = time.perf_counter() - t0
            self._stop.wait(max(0.0, interval - elapsed))
