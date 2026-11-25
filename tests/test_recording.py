"""Recording manager — disabled by default."""

from __future__ import annotations

from pathlib import Path

from screen_watch.config import Settings
from screen_watch.recording.session import RecordingManager


def test_recording_disabled_by_default(tmp_path: Path) -> None:
    settings = Settings(recording_enabled=False, recordings_dir=tmp_path)
    mgr = RecordingManager(settings)
    result = mgr.start(title="test")
    assert result["ok"] is False
    assert "disabled" in result["error"].lower()
    assert "advice" in result
