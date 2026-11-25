"""Capture backend protocol and shared types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class CaptureError(RuntimeError):
    """Raised when a capture backend fails to grab a frame."""


@dataclass(frozen=True, slots=True)
class DisplayInfo:
    """A physical or virtual display."""

    id: int
    width: int
    height: int
    left: int = 0
    top: int = 0
    is_primary: bool = False
    name: str = ""


@dataclass(slots=True)
class RawFrame:
    """Unencoded RGB frame from a capture backend."""

    width: int
    height: int
    rgb: bytes  # packed RGB, length == width * height * 3
    timestamp_ms: float
    display_id: int
    backend: str
    origin_left: int = 0  # screen X of frame's top-left (virtual desktop)
    origin_top: int = 0  # screen Y of frame's top-left


@runtime_checkable
class CaptureBackend(Protocol):
    """Platform capture adapter. Implementations must be observation-only."""

    @property
    def name(self) -> str:
        """Backend identifier (mss, dxcam, …)."""
        ...

    def list_displays(self) -> list[DisplayInfo]:
        """Enumerate available displays."""
        ...

    def grab(self, display_id: int | None = None) -> RawFrame:
        """Grab one frame from the given display (None = primary)."""
        ...

    def grab_virtual(self) -> RawFrame:
        """Grab the full virtual desktop (all monitors). Defaults to primary if unsupported."""
        ...
