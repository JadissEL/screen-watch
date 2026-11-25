"""Simple minimum-interval gate for capture-heavy MCP calls."""

from __future__ import annotations

import threading
import time


class MinIntervalGate:
    """Serialize calls and enforce a minimum spacing between successful entries."""

    def __init__(self, min_interval_s: float = 0.15) -> None:
        self._min = max(0.0, float(min_interval_s))
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._min - (now - self._last)
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()
