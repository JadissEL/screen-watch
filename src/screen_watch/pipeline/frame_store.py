"""Thread-safe store for the latest encoded frame (+ metadata history)."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


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


@dataclass(slots=True, frozen=True)
class FrameMeta:
    """Lightweight history entry (no image bytes)."""

    timestamp_ms: float
    content_hash: str
    unchanged: bool
    width: int
    height: int
    backend: str
    display_id: int
    blur: bool
    jpeg_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "content_hash": self.content_hash,
            "unchanged": self.unchanged,
            "width": self.width,
            "height": self.height,
            "backend": self.backend,
            "display_id": self.display_id,
            "blur": self.blur,
            "jpeg_bytes": self.jpeg_bytes,
        }


class FrameStore:
    """Atomic latest-frame holder with a bounded metadata ring buffer."""

    def __init__(self, history_size: int = 64) -> None:
        self._lock = threading.Lock()
        self._frame: EncodedFrame | None = None
        self._history: deque[FrameMeta] = deque(maxlen=max(1, int(history_size)))

    def set(self, frame: EncodedFrame) -> None:
        meta = FrameMeta(
            timestamp_ms=frame.timestamp_ms,
            content_hash=frame.content_hash,
            unchanged=frame.unchanged,
            width=frame.width,
            height=frame.height,
            backend=frame.backend,
            display_id=frame.display_id,
            blur=frame.blur,
            jpeg_bytes=len(frame.jpeg),
        )
        with self._lock:
            self._frame = frame
            self._history.append(meta)

    def get(self) -> EncodedFrame | None:
        with self._lock:
            return self._frame

    def age_ms(self) -> float | None:
        frame = self.get()
        if frame is None:
            return None
        return time.time() * 1000.0 - frame.timestamp_ms

    def history(
        self,
        *,
        limit: int = 20,
        changed_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return newest-first metadata entries (no JPEG bytes)."""
        with self._lock:
            items = list(self._history)
        if changed_only:
            items = [m for m in items if not m.unchanged]
        items.reverse()  # newest first
        n = max(1, min(int(limit), 200))
        return [m.as_dict() for m in items[:n]]

    def history_len(self) -> int:
        with self._lock:
            return len(self._history)
