"""FramePump continuous grab helper."""

from __future__ import annotations

import threading

from screen_watch.capture.loop import FramePump
from screen_watch.capture.mock_backend import MockBackend
from screen_watch.config import Settings


def test_frame_pump_yields_and_stops() -> None:
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
    frames = []
    for i, frame in enumerate(pump.frames()):
        frames.append(frame)
        if i >= 2:
            stop.set()
    assert len(frames) >= 3
    assert frames[0].jpeg[:2] == b"\xff\xd8" or frames[0].unchanged


def test_frame_pump_force_keyframe() -> None:
    settings = Settings(
        max_width=80,
        max_height=60,
        jpeg_quality=40,
        fps=5.0,
        idle_backoff=False,
        min_capture_interval_s=0.0,
    )
    pump = FramePump(MockBackend(160, 90), settings, fps_cap=5.0)
    frame = pump.force_keyframe()
    assert frame.unchanged is False
    assert frame.jpeg[:2] == b"\xff\xd8"
    assert pump.unchanged_streak == 0
