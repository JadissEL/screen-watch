"""Timed frame pump — snapshot backends today; native streams can replace grab later."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Iterator
from typing import TYPE_CHECKING

from screen_watch.daemon.watcher import idle_wait_factor
from screen_watch.pipeline.frame_store import EncodedFrame
from screen_watch.pipeline.process import process_raw_frame

if TYPE_CHECKING:
    from PIL import Image

    from screen_watch.capture.base import CaptureBackend
    from screen_watch.config import Settings

logger = logging.getLogger(__name__)


class FramePump:
    """
    Yield processed frames at capped FPS with optional idle backoff.

    This is the continuous-capture seam: backends still ``grab()`` per tick until
    a native ScreenCaptureKit / PipeWire stream is wired behind the same API.
    """

    def __init__(
        self,
        backend: CaptureBackend,
        settings: Settings,
        *,
        stop_event: threading.Event | None = None,
        fps_cap: float | None = None,
    ) -> None:
        self._backend = backend
        self._settings = settings
        self._stop = stop_event or threading.Event()
        self._thumb: Image.Image | None = None
        self._unchanged_streak = 0
        self._fps_cap = fps_cap

    @property
    def unchanged_streak(self) -> int:
        return self._unchanged_streak

    def stop(self) -> None:
        self._stop.set()

    def frames(self) -> Iterator[EncodedFrame]:
        fps = self._settings.capped_fps()
        if self._fps_cap is not None:
            fps = max(0.1, min(float(self._fps_cap), fps))
        base = 1.0 / fps
        while not self._stop.is_set():
            t0 = time.perf_counter()
            try:
                raw = self._backend.grab(self._settings.display)
                encoded, self._thumb = process_raw_frame(
                    raw, self._settings, previous_thumb=self._thumb
                )
                if encoded.unchanged:
                    self._unchanged_streak += 1
                else:
                    self._unchanged_streak = 0
                yield encoded
            except Exception as exc:
                logger.warning("FramePump tick failed: %s", exc)
            elapsed = time.perf_counter() - t0
            factor = idle_wait_factor(
                self._unchanged_streak,
                enabled=self._settings.idle_backoff,
                max_factor=self._settings.idle_backoff_max,
            )
            self._stop.wait(max(0.0, base * factor - elapsed))
