"""FrameStream / SnapshotFrameStream seam."""

from __future__ import annotations

import threading

from screen_watch.capture.base import SnapshotFrameStream, open_capture_stream
from screen_watch.capture.loop import FramePump
from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings


def test_snapshot_stream_reads() -> None:
    backend = MockBackend(64, 48)
    stream = open_capture_stream(backend, 1)
    assert stream.name.startswith("snapshot:")
    frame = stream.read()
    assert frame.width == 64
    assert frame.height == 48
    stream.close()


def test_backend_open_stream_preferred() -> None:
    class StreamingMock(MockBackend):
        def open_stream(self, display_id: int | None = None) -> SnapshotFrameStream:
            return SnapshotFrameStream(self, display_id)

    backend = StreamingMock(32, 24)
    stream = open_capture_stream(backend, None)
    assert isinstance(stream, SnapshotFrameStream)
    assert stream.read().width == 32
    stream.close()


def test_frame_pump_exposes_stream_name() -> None:
    settings = Settings(
        max_width=80,
        max_height=60,
        jpeg_quality=40,
        fps=5.0,
        idle_backoff=False,
        min_capture_interval_s=0.0,
    )
    stop = threading.Event()
    pump = FramePump(MockBackend(160, 90), settings, stop_event=stop, fps_cap=5.0)
    for i, _frame in enumerate(pump.frames()):
        assert pump.stream_name is not None
        assert pump.stream_name.startswith("snapshot:")
        if i >= 1:
            stop.set()
