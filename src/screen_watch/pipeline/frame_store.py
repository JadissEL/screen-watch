"""Thread-safe store for the latest encoded frame."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class EncodedFrame:
    """JPEG frame ready for MCP / disk."""

    jpeg: bytes
    width: int
    height: int
    timestamp_ms: float
    content_hash: str
    unchanged: bool
    backend: str
    display_id: int
    blur: bool = False


class FrameStore:
    """Atomic latest-frame holder."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: EncodedFrame | None = None

    def set(self, frame: EncodedFrame) -> None:
        with self._lock:
            self._frame = frame

    def get(self) -> EncodedFrame | None:
        with self._lock:
            return self._frame

    def age_ms(self) -> float | None:
        frame = self.get()
        if frame is None:
            return None
        return time.time() * 1000.0 - frame.timestamp_ms
