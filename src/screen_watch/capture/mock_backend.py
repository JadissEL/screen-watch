"""Deterministic in-memory backend for tests (no display required)."""

from __future__ import annotations

import time

from screen_watch.capture.base import DisplayInfo, RawFrame


class MockBackend:
    """Solid-color frames for unit tests."""

    def __init__(self, width: int = 320, height: int = 180, rgb: tuple[int, int, int] = (40, 80, 120)) -> None:
        self._w = width
        self._h = height
        self._rgb = bytes([rgb[0], rgb[1], rgb[2]] * (width * height))

    @property
    def name(self) -> str:
        return "mock"

    def list_displays(self) -> list[DisplayInfo]:
        return [DisplayInfo(id=1, width=self._w, height=self._h, is_primary=True, name="Mock")]

    def grab(self, display_id: int | None = None) -> RawFrame:
        return RawFrame(
            width=self._w,
            height=self._h,
            rgb=self._rgb,
            timestamp_ms=time.time() * 1000.0,
            display_id=display_id or 1,
            backend=self.name,
        )

    def grab_virtual(self) -> RawFrame:
        return self.grab(0)
