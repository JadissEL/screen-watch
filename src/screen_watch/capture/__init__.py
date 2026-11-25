"""Screen capture backends."""

from __future__ import annotations

from screen_watch.capture.base import CaptureBackend, CaptureError, DisplayInfo, RawFrame
from screen_watch.capture.factory import create_backend

__all__ = [
    "CaptureBackend",
    "CaptureError",
    "DisplayInfo",
    "RawFrame",
    "create_backend",
]
