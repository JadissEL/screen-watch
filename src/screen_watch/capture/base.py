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


@runtime_checkable
class FrameStream(Protocol):
    """
    Continuous frame source for FramePump.

    Native SCK / PipeWire / DXCam streams implement this; snapshot backends use
    ``SnapshotFrameStream`` (grab-per-tick) until a real stream ships.
    """

    @property
    def name(self) -> str:
        """Stream / backend identifier."""
        ...

    def read(self) -> RawFrame:
        """Block until the next frame (or return the latest snapshot)."""
        ...

    def close(self) -> None:
        """Release native resources. Idempotent."""
        ...


class SnapshotFrameStream:
    """Adapt a grab()-based ``CaptureBackend`` into a ``FrameStream``."""

    def __init__(self, backend: CaptureBackend, display_id: int | None = None) -> None:
        self._backend = backend
        self._display_id = display_id
        self._closed = False

    @property
    def name(self) -> str:
        return f"snapshot:{self._backend.name}"

    def read(self) -> RawFrame:
        if self._closed:
            raise CaptureError("SnapshotFrameStream is closed")
        return self._backend.grab(self._display_id)

    def close(self) -> None:
        self._closed = True


def open_capture_stream(
    backend: CaptureBackend,
    display_id: int | None = None,
) -> FrameStream:
    """
    Open a continuous stream for ``FramePump``.

    If the backend exposes ``open_stream(display_id)``, use it; otherwise wrap
    ``grab()`` in ``SnapshotFrameStream``.
    """
    opener = getattr(backend, "open_stream", None)
    if callable(opener):
        stream = opener(display_id)
        if stream is not None:
            return stream  # type: ignore[no-any-return]
    return SnapshotFrameStream(backend, display_id)
