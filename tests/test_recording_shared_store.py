"""Recording can tap a live FrameStore without a second capture loop."""

from __future__ import annotations

import time
from pathlib import Path

from screen_watch.config import Settings
from screen_watch.pipeline.frame_store import EncodedFrame, FrameStore
from screen_watch.recording.session import RecordingManager


def test_recording_taps_shared_store(tmp_path: Path) -> None:
    settings = Settings(
        recording_enabled=True,
        recordings_dir=tmp_path,
        idle_backoff=False,
    )
    store = FrameStore(history_size=4)
    store.set(
        EncodedFrame(
            jpeg=b"\xff\xd8\xff\xd9",
            width=10,
            height=10,
            timestamp_ms=time.time() * 1000.0,
            content_hash="abc123",
            unchanged=False,
            backend="mock",
            display_id=0,
        )
    )
    mgr = RecordingManager(settings)
    result = mgr.start(title="tap", shared_store=store)
    assert result["ok"] is True
    assert result["capture_source"] == "shared_store"
    deadline = time.time() + 2.0
    while time.time() < deadline:
        session = mgr.active
        if session is not None and session.frame_count >= 1:
            break
        time.sleep(0.05)
    assert mgr.active is not None
    assert mgr.active.frame_count >= 1
    stop = mgr.stop()
    assert stop["ok"] is True
    assert (tmp_path / stop["session"]["id"] / "frames" / "frame_000000.jpg").is_file()
